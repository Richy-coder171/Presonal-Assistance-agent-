from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .ai import OpenAIAnalyzer
from .classifier import build_briefing_text, classify_email, detect_conflicts, draft_hebrew_reply, summarize_email
from .config import Settings
from .google_oauth import GoogleOAuthManager, GoogleTokenStore
from .http_client import HttpError
from .microsoft_oauth import MicrosoftOAuthManager, MicrosoftTokenStore
from .models import ApprovalItem, CalendarEvent, DailyBriefing, EmailItem, TaskItem, new_id, now_iso
from .providers import (
    CalendarProvider,
    CompositeMessenger,
    EmailProvider,
    GoogleWorkspaceProvider,
    Microsoft365Provider,
    SlackMessenger,
    WhatsAppMessenger,
)
from .sample_data import sample_approvals, sample_emails, sample_events, sample_tasks
from .storage import StateStore


class AssistantService:
    def __init__(self, settings: Settings, store: StateStore | None = None) -> None:
        self.settings = settings
        self.store = store or StateStore(settings.data_path)
        self.google_token_store = GoogleTokenStore(settings.google_token_path)
        self.google_oauth = GoogleOAuthManager(settings, self.google_token_store)
        google = GoogleWorkspaceProvider(settings, self.google_token_store)
        self.google_provider = google
        self.microsoft_token_store = MicrosoftTokenStore(settings.ms_token_path)
        self.microsoft_oauth = MicrosoftOAuthManager(settings, self.microsoft_token_store)
        microsoft = Microsoft365Provider(settings, self.microsoft_token_store)
        self.microsoft_provider = microsoft
        self.email_providers: list[EmailProvider] = [google, microsoft]
        self.calendar_providers: list[CalendarProvider] = [google, microsoft]
        self.messenger = CompositeMessenger(
            [SlackMessenger(settings), WhatsAppMessenger(settings)]
        )
        self.analyzer = OpenAIAnalyzer(settings)

    def status(self) -> dict:
        state = self.store.load()
        local_now = datetime.now(ZoneInfo(self.settings.timezone))
        scheduler_status = "disabled"
        if self.settings.scheduler_enabled:
            last_briefing_date = state.get("scheduler", {}).get("last_briefing_date", "")
            if last_briefing_date == local_now.date().isoformat():
                scheduler_status = "briefing_generated_today"
            elif local_now.hour < self.settings.briefing_hour:
                scheduler_status = "waiting_for_briefing_hour"
            else:
                scheduler_status = "ready_to_generate"
        return {
            "configured": {
                "gmail_or_google_calendar": self.google_provider.configured,
                "outlook_or_microsoft_calendar": any(
                    provider.configured and provider.name == "Microsoft 365"
                    for provider in self.email_providers
                ),
                "openai": self.analyzer.configured,
                "messaging": self.messenger.configured,
            },
            "connections": self.connection_status(),
            "counts": {
                "emails": len(state["emails"]),
                "events": len(state["events"]),
                "tasks": len(state["tasks"]),
                "briefings": len(state["briefings"]),
            },
            "demo_mode": self.settings.demo_mode,
            "timezone": self.settings.timezone,
            "current_datetime": local_now.isoformat(),
            "current_date": local_now.date().isoformat(),
            "current_time": local_now.strftime("%H:%M:%S"),
            "scheduler": {
                "enabled": self.settings.scheduler_enabled,
                "status": scheduler_status,
                "briefing_hour": self.settings.briefing_hour,
                "last_briefing_date": state.get("scheduler", {}).get("last_briefing_date", ""),
            },
        }

    def connection_status(self) -> dict:
        google_status = self.google_oauth.connection_status()
        microsoft_status = self.microsoft_oauth.connection_status()
        return {
            "gmail": {
                "connected": google_status["gmail_connected"],
                "read_only": True,
            },
            "calendar": {
                "connected": google_status["calendar_connected"],
                "read_only": True,
            },
            "outlook_mail": {
                "connected": microsoft_status["mail_connected"],
                "read_only": not microsoft_status["mail_send_enabled"],
            },
            "outlook_calendar": {
                "connected": microsoft_status["calendar_connected"],
                "read_only": not microsoft_status["calendar_write_enabled"],
            },
            "openai": {
                "connected": self.analyzer.configured,
                "read_only": False,
            },
            "google_oauth_configured": google_status["oauth_configured"],
            "microsoft_oauth_configured": microsoft_status["oauth_configured"],
            "write_actions": {
                "google_gmail": google_status["gmail_send_enabled"],
                "google_calendar": google_status["calendar_write_enabled"],
                "microsoft_mail": microsoft_status["mail_send_enabled"],
                "microsoft_calendar": microsoft_status["calendar_write_enabled"],
            },
        }

    def google_authorization_url(self, redirect_uri: str) -> str:
        return self.google_oauth.authorization_url(redirect_uri)

    def microsoft_authorization_url(self, redirect_uri: str) -> str:
        return self.microsoft_oauth.authorization_url(redirect_uri)

    def complete_google_oauth(self, *, code: str, state: str, error: str = "") -> dict:
        status = self.google_oauth.complete(code=code, state=state, error=error)
        self._clear_demo_content()
        email_result = self.refresh_emails()
        calendar_result = self.refresh_calendar()
        return {
            "connections": status,
            "emails": email_result,
            "calendar": calendar_result,
        }

    def complete_microsoft_oauth(self, *, code: str, state: str, error: str = "") -> dict:
        status = self.microsoft_oauth.complete(code=code, state=state, error=error)
        self._clear_demo_content()
        email_result = self.refresh_emails()
        calendar_result = self.refresh_calendar()
        return {
            "connections": status,
            "emails": email_result,
            "calendar": calendar_result,
        }

    def dashboard(self) -> dict:
        state = self.store.load()
        emails = [EmailItem.from_dict(item) for item in state["emails"]]
        events = [CalendarEvent.from_dict(item) for item in state["events"]]
        tasks = [TaskItem.from_dict(item) for item in state["tasks"]]
        conflicts = detect_conflicts(events)
        urgent = [email for email in emails if email.priority == "urgent"]
        important = [email for email in emails if email.priority == "important"]
        latest_briefing = state["briefings"][0] if state["briefings"] else None
        return {
            "status": self.status(),
            "emails": [item.to_dict() for item in sorted(emails, key=lambda item: item.received_at, reverse=True)],
            "events": [item.to_dict() for item in sorted(events, key=lambda item: item.start)],
            "tasks": [item.to_dict() for item in sorted(tasks, key=lambda item: (item.status, item.due_at or ""))],
            "conflicts": conflicts,
            "latest_briefing": latest_briefing,
            "approvals": self.list_approvals(),
            "analytics": self.analytics(),
            "metrics": {
                "urgent_emails": len(urgent),
                "important_emails": len(important),
                "open_tasks": len([task for task in tasks if task.status != "done"]),
                "calendar_conflicts": len(conflicts),
            },
        }

    def analytics(self) -> dict:
        state = self.store.load()
        emails = [EmailItem.from_dict(item) for item in state["emails"]]
        events = [CalendarEvent.from_dict(item) for item in state["events"]]
        tasks = [TaskItem.from_dict(item) for item in state["tasks"]]
        conflicts = detect_conflicts(events)
        response_tasks = [
            task for task in tasks
            if task.source == "email" and task.status != "done"
        ]
        meetings = [event for event in events if event.attendees]
        focus_blocks = [
            event for event in events
            if "focus" in event.title.casefold() or "מיקוד" in event.title
        ]
        return {
            "email": {
                "total": len(emails),
                "urgent": len([item for item in emails if item.priority == "urgent"]),
                "important": len([item for item in emails if item.priority == "important"]),
                "requires_response": len([item for item in emails if item.requires_response]),
                "pending_response_tasks": len(response_tasks),
                "target_response_minutes": 30,
            },
            "calendar": {
                "events": len(events),
                "meetings": len(meetings),
                "conflicts": len(conflicts),
                "focus_blocks": len(focus_blocks),
                "meeting_attendance_rate": None,
                "target_meeting_attendance_rate": 0.95,
            },
            "tasks": {
                "open": len([task for task in tasks if task.status != "done"]),
                "done": len([task for task in tasks if task.status == "done"]),
            },
        }

    def list_approvals(self) -> list[dict]:
        state = self.store.load()
        approvals = [ApprovalItem.from_dict(item) for item in state["approvals"]]
        return [
            item.to_dict()
            for item in sorted(approvals, key=lambda item: item.created_at, reverse=True)
        ]

    def create_approval(self, payload: dict) -> ApprovalItem:
        action_type = str(payload.get("action_type", "")).strip()
        if not action_type:
            raise ValueError("Approval action_type is required")
        approval = ApprovalItem(
            id=new_id("approval"),
            action_type=action_type,
            title=str(payload.get("title") or _approval_title(action_type)),
            description=str(payload.get("description") or ""),
            payload=dict(payload.get("payload", {})),
            risk=str(payload.get("risk", "external_action")),
        )
        state = self.store.load()
        state["approvals"] = [approval.to_dict(), *state["approvals"]]
        self.store.save(state)
        return approval

    def approve_item(self, approval_id: str) -> ApprovalItem:
        return self._update_approval(approval_id, approve=True)

    def reject_item(self, approval_id: str) -> ApprovalItem:
        return self._update_approval(approval_id, approve=False)

    def run_scheduler_once(self, now: datetime | None = None) -> dict:
        timezone = ZoneInfo(self.settings.timezone)
        now = now or datetime.now(timezone)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone)
        now = now.astimezone(timezone)
        if not self.settings.scheduler_enabled:
            return {"status": "disabled"}
        if now.hour < self.settings.briefing_hour:
            return {"status": "waiting", "briefing_hour": self.settings.briefing_hour}

        state = self.store.load()
        today = now.date().isoformat()
        scheduler = dict(state.get("scheduler", {}))
        if scheduler.get("last_briefing_date") == today:
            return {"status": "already_generated", "date": today}

        briefing = self.generate_briefing()
        scheduler["last_briefing_date"] = today
        state = self.store.load()
        state["scheduler"] = scheduler
        self.store.save(state)
        approval = self.create_approval(
            {
                "action_type": "send_briefing",
                "title": "Send daily briefing",
                "description": "Send the generated daily briefing through configured messaging channels.",
                "payload": {"briefing_id": briefing.id},
                "risk": "external_message",
            }
        )
        return {"status": "generated", "briefing": briefing.to_dict(), "approval": approval.to_dict()}

    def _update_approval(self, approval_id: str, approve: bool) -> ApprovalItem:
        state = self.store.load()
        approvals = [ApprovalItem.from_dict(item) for item in state["approvals"]]
        for approval in approvals:
            if approval.id != approval_id:
                continue
            if approval.status != "pending":
                raise ValueError("Approval is not pending")
            if not approve:
                approval.status = "rejected"
                approval.completed_at = now_iso()
            else:
                approval.status = "approved"
                approval.approved_at = now_iso()
                state["approvals"] = [item.to_dict() for item in approvals]
                self.store.save(state)
                try:
                    approval.result = self._execute_approval(approval)
                    approval.status = "completed"
                    approval.completed_at = now_iso()
                except Exception as exc:  # noqa: BLE001 - persisted for user review.
                    approval.status = "failed"
                    approval.error = str(exc)
                    approval.completed_at = now_iso()
            state["approvals"] = [item.to_dict() for item in approvals]
            self.store.save(state)
            return approval
        raise KeyError(f"Approval not found: {approval_id}")

    def _execute_approval(self, approval: ApprovalItem) -> dict:
        if approval.status != "approved":
            raise RuntimeError("Approval must be approved before execution.")
        if not self._approval_is_approved_in_store(approval.id):
            raise RuntimeError("Approval must exist in the approval queue before execution.")
        payload = approval.payload
        action = approval.action_type
        if action == "send_briefing":
            return self.send_latest_briefing(approved=True)
        if action == "send_message":
            return self.messenger.send(str(payload.get("text", "")))
        if action == "send_email":
            provider = self._provider_for_action(str(payload.get("provider", "google")))
            return provider.send_email(
                str(payload.get("to", "")),
                str(payload.get("subject", "")),
                str(payload.get("body", "")),
            )
        if action in {"create_focus_time", "create_calendar_event"}:
            provider = self._provider_for_action(str(payload.get("provider", "google")))
            return provider.create_event(payload)
        if action == "reschedule_event":
            provider = self._provider_for_action(str(payload.get("provider", "google")))
            return provider.update_event(str(payload.get("event_id", "")), payload)
        if action == "delete_event":
            provider = self._provider_for_action(str(payload.get("provider", "google")))
            return provider.delete_event(str(payload.get("event_id", "")))
        if action in {"coordinate_meeting", "send_reminder", "send_prep_material", "notify_participants"}:
            text = str(payload.get("text") or approval.description or approval.title)
            return self.messenger.send(text)
        raise ValueError(f"Unsupported approval action: {action}")

    def _approval_is_approved_in_store(self, approval_id: str) -> bool:
        state = self.store.load()
        for item in state["approvals"]:
            if item.get("id") == approval_id and item.get("status") == "approved":
                return True
        return False

    def _provider_for_action(self, provider: str):
        if provider.lower() in {"outlook", "microsoft", "microsoft365"}:
            return self.microsoft_provider
        return self.google_provider

    def refresh_emails(self) -> dict:
        incoming: list[EmailItem] = []
        errors: list[dict] = []
        live_provider_count = 0

        for provider in self.email_providers:
            if not provider.configured:
                continue
            live_provider_count += 1
            try:
                incoming.extend(provider.list_recent_emails(limit=25))
            except HttpError as exc:
                errors.append({"provider": provider.name, "error": str(exc), "body": exc.body[:400]})
            except Exception as exc:  # noqa: BLE001 - provider failures should not stop other workflows.
                errors.append({"provider": provider.name, "error": str(exc)})

        used_demo = False
        if not incoming and self.settings.demo_mode and live_provider_count == 0:
            incoming = sample_emails(self.settings.timezone)
            used_demo = live_provider_count == 0

        analyzed = [self._analyze_email(item) for item in incoming]
        state = self.store.load()
        existing = [EmailItem.from_dict(item) for item in state["emails"]]
        if live_provider_count > 0:
            existing = [item for item in existing if item.source != "demo"]
        state["emails"] = _merge_by_id(existing, analyzed, limit=80)
        self.store.save(state)
        self._create_tasks_from_emails(analyzed)
        return {"emails": [item.to_dict() for item in analyzed], "errors": errors, "used_demo": used_demo}

    def refresh_calendar(self) -> dict:
        now = datetime.now(ZoneInfo(self.settings.timezone))
        end = now + timedelta(days=7)
        incoming: list[CalendarEvent] = []
        errors: list[dict] = []
        live_provider_count = 0

        for provider in self.calendar_providers:
            if not provider.configured:
                continue
            live_provider_count += 1
            try:
                incoming.extend(provider.list_events(now, end))
            except HttpError as exc:
                errors.append({"provider": provider.name, "error": str(exc), "body": exc.body[:400]})
            except Exception as exc:  # noqa: BLE001 - provider failures should not stop other workflows.
                errors.append({"provider": provider.name, "error": str(exc)})

        used_demo = False
        if not incoming and self.settings.demo_mode and live_provider_count == 0:
            incoming = sample_events(self.settings.timezone)
            used_demo = live_provider_count == 0

        state = self.store.load()
        existing = [CalendarEvent.from_dict(item) for item in state["events"]]
        if live_provider_count > 0:
            existing = [item for item in existing if item.source != "demo"]
        state["events"] = _merge_by_id(existing, incoming, limit=120)
        self.store.save(state)
        return {"events": [item.to_dict() for item in incoming], "conflicts": detect_conflicts(incoming), "errors": errors, "used_demo": used_demo}

    def load_demo(self) -> dict:
        return self.reset_demo()

    def reset_demo(self) -> dict:
        emails = [self._analyze_email(item) for item in sample_emails(self.settings.timezone)]
        events = sample_events(self.settings.timezone)
        tasks = sample_tasks(self.settings.timezone)
        state = self.store.load()
        state["emails"] = _merge_by_id(
            [EmailItem.from_dict(item) for item in state["emails"] if item.get("source") != "demo"],
            emails,
            limit=80,
        )
        state["events"] = _merge_by_id(
            [CalendarEvent.from_dict(item) for item in state["events"] if item.get("source") != "demo"],
            events,
            limit=120,
        )
        state["tasks"] = _merge_by_id(
            [TaskItem.from_dict(item) for item in state["tasks"] if item.get("source") != "demo"],
            tasks,
            limit=120,
        )
        state["approvals"] = []
        state["scheduler"] = {}
        self.store.save(state)
        briefing = self.generate_briefing()
        state = self.store.load()
        state["approvals"] = [
            item.to_dict() for item in sample_approvals(self.settings.timezone, briefing.id)
        ]
        self.store.save(state)
        return self.dashboard()

    def create_task(self, payload: dict) -> TaskItem:
        title = str(payload.get("title", "")).strip()
        if not title:
            raise ValueError("Task title is required")
        task = TaskItem(
            id=new_id("task"),
            title=title,
            notes=str(payload.get("notes", "")).strip(),
            due_at=payload.get("due_at") or None,
            priority=payload.get("priority", "routine"),
            source=str(payload.get("source", "manual")),
            related_item_id=str(payload.get("related_item_id", "")),
        )
        state = self.store.load()
        state["tasks"] = [task.to_dict(), *state["tasks"]]
        self.store.save(state)
        return task

    def update_task(self, task_id: str, payload: dict) -> TaskItem:
        state = self.store.load()
        tasks = [TaskItem.from_dict(item) for item in state["tasks"]]
        for task in tasks:
            if task.id != task_id:
                continue
            if "title" in payload:
                task.title = str(payload["title"]).strip() or task.title
            if "notes" in payload:
                task.notes = str(payload["notes"])
            if "due_at" in payload:
                task.due_at = payload["due_at"] or None
            if "priority" in payload and payload["priority"] in {"urgent", "important", "routine", "fyi"}:
                task.priority = payload["priority"]
            if "status" in payload and payload["status"] in {"open", "done"}:
                task.status = payload["status"]
            state["tasks"] = [item.to_dict() for item in tasks]
            self.store.save(state)
            return task
        raise KeyError(f"Task not found: {task_id}")

    def delete_task(self, task_id: str) -> dict:
        state = self.store.load()
        tasks = [TaskItem.from_dict(item) for item in state["tasks"]]
        kept = [task for task in tasks if task.id != task_id]
        if len(kept) == len(tasks):
            raise KeyError(f"Task not found: {task_id}")
        state["tasks"] = [task.to_dict() for task in kept]
        self.store.save(state)
        return {"deleted": task_id}

    def generate_briefing(self) -> DailyBriefing:
        state = self.store.load()
        if self.settings.demo_mode and not state["emails"]:
            self.refresh_emails()
            state = self.store.load()
        if self.settings.demo_mode and not state["events"]:
            self.refresh_calendar()
            state = self.store.load()
        if self.settings.demo_mode and not state["tasks"]:
            state["tasks"] = [item.to_dict() for item in sample_tasks(self.settings.timezone)]
            self.store.save(state)

        emails = [EmailItem.from_dict(item) for item in state["emails"]]
        events = [CalendarEvent.from_dict(item) for item in state["events"]]
        tasks = [TaskItem.from_dict(item) for item in state["tasks"]]
        conflicts = detect_conflicts(events)
        text = build_briefing_text(emails, events, tasks, conflicts, self.settings.timezone)
        briefing = DailyBriefing(
            id=new_id("briefing"),
            generated_at=now_iso(),
            text=text,
            urgent_count=len([item for item in emails if item.priority == "urgent"]),
            important_count=len([item for item in emails if item.priority == "important"]),
            conflict_count=len(conflicts),
            open_task_count=len([task for task in tasks if task.status != "done"]),
        )
        state["briefings"] = [briefing.to_dict(), *state["briefings"][:20]]
        self.store.save(state)
        return briefing

    def send_latest_briefing(self, approved: bool = False) -> dict:
        if not approved:
            return {"sent": [], "errors": [{"channel": "approval", "error": "Sending requires explicit approval"}]}
        state = self.store.load()
        briefing = state["briefings"][0] if state["briefings"] else self.generate_briefing().to_dict()
        if not self.messenger.configured:
            return {"sent": [], "errors": [{"channel": "messaging", "error": "No Slack or WhatsApp channel configured"}]}
        return self.messenger.send(briefing["text"])

    def _analyze_email(self, email: EmailItem) -> EmailItem:
        ai_analysis = self.analyzer.analyze_email(email)
        if ai_analysis:
            email.priority = ai_analysis.priority
            email.requires_response = ai_analysis.requires_response
            email.summary = ai_analysis.summary or summarize_email(email)
            email.draft_reply = ai_analysis.draft_reply or draft_hebrew_reply(email, email.priority)
            return email

        priority, requires_response = classify_email(email)
        email.priority = priority
        email.requires_response = requires_response
        email.summary = summarize_email(email)
        email.draft_reply = draft_hebrew_reply(email, priority) if requires_response else ""
        return email

    def _create_tasks_from_emails(self, emails: list[EmailItem]) -> None:
        action_emails = [item for item in emails if item.requires_response and item.priority in {"urgent", "important"}]
        if not action_emails:
            return
        state = self.store.load()
        tasks = [TaskItem.from_dict(item) for item in state["tasks"]]
        existing_related = {task.related_item_id for task in tasks}
        new_tasks = []
        for email in action_emails:
            if email.id in existing_related:
                continue
            new_tasks.append(
                TaskItem(
                    id=new_id("task"),
                    title=f"לטפל במייל: {email.subject}",
                    notes=email.summary,
                    priority=email.priority,
                    source="email",
                    related_item_id=email.id,
                )
            )
        if new_tasks:
            state["tasks"] = [item.to_dict() for item in new_tasks] + state["tasks"]
            self.store.save(state)

    def _clear_demo_content(self) -> None:
        state = self.store.load()
        state["emails"] = [
            item for item in state["emails"] if item.get("source") != "demo"
        ]
        state["events"] = [
            item for item in state["events"] if item.get("source") != "demo"
        ]
        state["tasks"] = [
            item for item in state["tasks"] if item.get("source") != "demo"
        ]
        self.store.save(state)


def _merge_by_id(existing: list, incoming: list, limit: int) -> list[dict]:
    merged = {item.id: item for item in existing}
    for item in incoming:
        merged[item.id] = item
    return [item.to_dict() for item in list(merged.values())[:limit]]


def _approval_title(action_type: str) -> str:
    return {
        "send_briefing": "Send daily briefing",
        "send_message": "Send message",
        "send_email": "Send email",
        "create_focus_time": "Create focus time",
        "create_calendar_event": "Create calendar event",
        "reschedule_event": "Reschedule event",
        "delete_event": "Delete calendar event",
        "coordinate_meeting": "Coordinate meeting",
        "send_reminder": "Send reminder",
        "send_prep_material": "Send preparation material",
        "notify_participants": "Notify participants",
    }.get(action_type, action_type.replace("_", " ").title())
