from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .ai import OpenAIAnalyzer
from .classifier import build_briefing_text, classify_email, detect_conflicts, draft_hebrew_reply, summarize_email
from .config import Settings
from .http_client import HttpError
from .models import CalendarEvent, DailyBriefing, EmailItem, TaskItem, new_id, now_iso
from .providers import (
    CalendarProvider,
    CompositeMessenger,
    EmailProvider,
    GoogleWorkspaceProvider,
    Microsoft365Provider,
    SlackMessenger,
    WhatsAppMessenger,
)
from .sample_data import sample_emails, sample_events, sample_tasks
from .storage import StateStore


class AssistantService:
    def __init__(self, settings: Settings, store: StateStore | None = None) -> None:
        self.settings = settings
        self.store = store or StateStore(settings.data_path)
        google = GoogleWorkspaceProvider(settings)
        microsoft = Microsoft365Provider(settings)
        self.email_providers: list[EmailProvider] = [google, microsoft]
        self.calendar_providers: list[CalendarProvider] = [google, microsoft]
        self.messenger = CompositeMessenger(
            [SlackMessenger(settings), WhatsAppMessenger(settings)]
        )
        self.analyzer = OpenAIAnalyzer(settings)

    def status(self) -> dict:
        state = self.store.load()
        return {
            "configured": {
                "gmail_or_google_calendar": any(
                    provider.configured and provider.name == "Google Workspace"
                    for provider in self.email_providers
                ),
                "outlook_or_microsoft_calendar": any(
                    provider.configured and provider.name == "Microsoft 365"
                    for provider in self.email_providers
                ),
                "openai": self.analyzer.configured,
                "messaging": self.messenger.configured,
            },
            "counts": {
                "emails": len(state["emails"]),
                "events": len(state["events"]),
                "tasks": len(state["tasks"]),
                "briefings": len(state["briefings"]),
            },
            "demo_mode": self.settings.demo_mode,
            "timezone": self.settings.timezone,
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
            "metrics": {
                "urgent_emails": len(urgent),
                "important_emails": len(important),
                "open_tasks": len([task for task in tasks if task.status != "done"]),
                "calendar_conflicts": len(conflicts),
            },
        }

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
        if not incoming and self.settings.demo_mode:
            incoming = sample_emails(self.settings.timezone)
            used_demo = live_provider_count == 0

        analyzed = [self._analyze_email(item) for item in incoming]
        state = self.store.load()
        state["emails"] = _merge_by_id([EmailItem.from_dict(item) for item in state["emails"]], analyzed, limit=80)
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
        if not incoming and self.settings.demo_mode:
            incoming = sample_events(self.settings.timezone)
            used_demo = live_provider_count == 0

        state = self.store.load()
        state["events"] = _merge_by_id([CalendarEvent.from_dict(item) for item in state["events"]], incoming, limit=120)
        self.store.save(state)
        return {"events": [item.to_dict() for item in incoming], "conflicts": detect_conflicts(incoming), "errors": errors, "used_demo": used_demo}

    def load_demo(self) -> dict:
        emails = [self._analyze_email(item) for item in sample_emails(self.settings.timezone)]
        events = sample_events(self.settings.timezone)
        tasks = sample_tasks(self.settings.timezone)
        state = self.store.load()
        state["emails"] = _merge_by_id([EmailItem.from_dict(item) for item in state["emails"]], emails, limit=80)
        state["events"] = _merge_by_id([CalendarEvent.from_dict(item) for item in state["events"]], events, limit=120)
        state["tasks"] = _merge_by_id([TaskItem.from_dict(item) for item in state["tasks"]], tasks, limit=120)
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


def _merge_by_id(existing: list, incoming: list, limit: int) -> list[dict]:
    merged = {item.id: item for item in existing}
    for item in incoming:
        merged[item.id] = item
    return [item.to_dict() for item in list(merged.values())[:limit]]
