from __future__ import annotations

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from assistant_agent.classifier import classify_email, detect_conflicts
from assistant_agent.config import Settings
from assistant_agent.google_oauth import (
    CALENDAR_READONLY_SCOPE,
    GMAIL_READONLY_SCOPE,
    GoogleOAuthManager,
    GoogleTokenStore,
)
from assistant_agent.microsoft_oauth import (
    MS_CALENDAR_READ,
    MS_MAIL_READ,
    MicrosoftOAuthManager,
)
from assistant_agent.models import ApprovalItem, CalendarEvent, EmailItem, TaskItem
from assistant_agent.sample_data import sample_emails, sample_events, sample_tasks
from assistant_agent.service import AssistantService
from assistant_agent.storage import StateStore


class ClassifierTests(unittest.TestCase):
    def test_priority_classification_covers_client_demo_categories(self) -> None:
        cases = [
            (
                EmailItem(
                    id="urgent",
                    subject="דחוף: אישור הצעת מחיר היום",
                    sender="client@example.com",
                    received_at=datetime.now(timezone.utc).isoformat(),
                    snippet="אפשר לאשר עד הצהריים?",
                ),
                "urgent",
                True,
            ),
            (
                EmailItem(
                    id="important",
                    subject="חשבונית ותשלום לספק",
                    sender="finance@example.com",
                    received_at=datetime.now(timezone.utc).isoformat(),
                    snippet="מצורפת חשבונית לאישור.",
                ),
                "important",
                True,
            ),
            (
                EmailItem(
                    id="routine",
                    subject="Office delivery window",
                    sender="service@example.com",
                    received_at=datetime.now(timezone.utc).isoformat(),
                    snippet="Could you confirm whether tomorrow afternoon works?",
                ),
                "routine",
                True,
            ),
            (
                EmailItem(
                    id="fyi",
                    subject="עדכון שבועי לידיעה",
                    sender="no-reply@example.com",
                    received_at=datetime.now(timezone.utc).isoformat(),
                    snippet="לידיעה בלבד. אין צורך בפעולה.",
                ),
                "fyi",
                False,
            ),
        ]
        for email, expected_priority, expected_response in cases:
            with self.subTest(email=email.id):
                priority, requires_response = classify_email(email)
                self.assertEqual(priority, expected_priority)
                self.assertEqual(requires_response, expected_response)

    def test_urgent_hebrew_email_requires_response(self) -> None:
        email = EmailItem(
            id="e1",
            subject="דחוף: צריך אישור היום",
            sender="client@example.com",
            received_at=datetime.now(timezone.utc).isoformat(),
            snippet="אפשר לאשר עד הצהריים?",
        )
        priority, requires_response = classify_email(email)
        self.assertEqual(priority, "urgent")
        self.assertTrue(requires_response)

    def test_newsletter_is_fyi_without_response(self) -> None:
        email = EmailItem(
            id="e2",
            subject="Weekly newsletter",
            sender="no-reply@example.com",
            received_at=datetime.now(timezone.utc).isoformat(),
            snippet="FYI digest",
        )
        priority, requires_response = classify_email(email)
        self.assertEqual(priority, "fyi")
        self.assertFalse(requires_response)


class CalendarTests(unittest.TestCase):
    def test_detects_overlapping_events(self) -> None:
        start = datetime(2026, 6, 8, 9, tzinfo=timezone.utc)
        events = [
            CalendarEvent(id="a", title="A", start=start.isoformat(), end=(start + timedelta(hours=1)).isoformat()),
            CalendarEvent(id="b", title="B", start=(start + timedelta(minutes=30)).isoformat(), end=(start + timedelta(hours=2)).isoformat()),
        ]
        conflicts = detect_conflicts(events)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["titles"], ["A", "B"])


class DemoDataTests(unittest.TestCase):
    def test_demo_data_has_client_ready_coverage(self) -> None:
        emails = sample_emails("Asia/Jerusalem")
        events = sample_events("Asia/Jerusalem")
        tasks = sample_tasks("Asia/Jerusalem")
        priorities = [classify_email(email)[0] for email in emails]
        hebrew_emails = [
            email for email in emails
            if any("\u0590" <= char <= "\u05ff" for char in f"{email.subject} {email.body}")
        ]
        english_emails = [
            email for email in emails
            if any("a" <= char.casefold() <= "z" for char in f"{email.subject} {email.body}")
        ]

        self.assertGreaterEqual(priorities.count("urgent"), 2)
        self.assertGreaterEqual(priorities.count("important"), 2)
        self.assertGreaterEqual(priorities.count("routine"), 2)
        self.assertGreaterEqual(priorities.count("fyi"), 2)
        self.assertGreaterEqual(len(hebrew_emails), 2)
        self.assertGreaterEqual(len(english_emails), 1)
        self.assertGreaterEqual(len(detect_conflicts(events)), 1)
        self.assertTrue(any("מיקוד" in event.title or "focus" in event.title.casefold() for event in events))
        self.assertGreaterEqual(len(tasks), 5)
        self.assertTrue(all(task.due_at for task in tasks))
        self.assertTrue({"urgent", "important", "routine"}.issubset({task.priority for task in tasks}))


class ServiceTests(unittest.TestCase):
    def test_demo_briefing_populates_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = _settings(Path(directory) / "state.json")
            service = AssistantService(settings, StateStore(settings.data_path))
            briefing = service.generate_briefing()
            dashboard = service.dashboard()
            self.assertIn("בוקר טוב", briefing.text)
            self.assertGreaterEqual(dashboard["metrics"]["urgent_emails"], 1)
            self.assertGreaterEqual(len(dashboard["tasks"]), 1)

    def test_task_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = _settings(Path(directory) / "state.json")
            service = AssistantService(settings, StateStore(settings.data_path))
            task = service.create_task({"title": "בדיקה", "priority": "routine"})
            updated = service.update_task(task.id, {"status": "done"})
            deleted = service.delete_task(task.id)
            self.assertEqual(updated.status, "done")
            self.assertEqual(deleted["deleted"], task.id)

    def test_briefing_send_requires_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = _settings(Path(directory) / "state.json")
            service = AssistantService(settings, StateStore(settings.data_path))
            result = service.send_latest_briefing()
            self.assertEqual(result["sent"], [])
            self.assertEqual(result["errors"][0]["channel"], "approval")

    def test_approval_queue_can_reject_pending_action(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = _settings(Path(directory) / "state.json")
            service = AssistantService(settings, StateStore(settings.data_path))
            approval = service.create_approval(
                {
                    "action_type": "send_message",
                    "title": "Send client update",
                    "payload": {"text": "Draft only"},
                }
            )
            queued = service.list_approvals()
            self.assertEqual(queued[0]["status"], "pending")
            self.assertEqual(queued[0]["id"], approval.id)

            rejected = service.reject_item(approval.id)
            self.assertEqual(rejected.status, "rejected")

    def test_risky_email_action_does_not_execute_while_pending(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = _settings(Path(directory) / "state.json")
            service = AssistantService(settings, StateStore(settings.data_path))
            with patch.object(service.google_provider, "send_email") as send_email:
                approval = service.create_approval(
                    {
                        "action_type": "send_email",
                        "payload": {
                            "provider": "google",
                            "to": "client@example.com",
                            "subject": "Draft",
                            "body": "Draft body",
                        },
                    }
                )
                self.assertEqual(approval.status, "pending")
                send_email.assert_not_called()

    def test_direct_approval_execution_requires_recorded_approved_item(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = _settings(Path(directory) / "state.json")
            service = AssistantService(settings, StateStore(settings.data_path))
            pending = service.create_approval(
                {"action_type": "send_message", "payload": {"text": "Draft only"}}
            )
            with self.assertRaisesRegex(RuntimeError, "approved"):
                service._execute_approval(ApprovalItem.from_dict(pending.to_dict()))

            forged = ApprovalItem(
                id="approval_not_recorded",
                action_type="send_message",
                title="Forged",
                description="Not in queue",
                payload={"text": "Should not send"},
                status="approved",
            )
            with self.assertRaisesRegex(RuntimeError, "approval queue"):
                service._execute_approval(forged)

    def test_approved_email_action_executes_only_after_queue_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = _settings(Path(directory) / "state.json")
            service = AssistantService(settings, StateStore(settings.data_path))
            approval = service.create_approval(
                {
                    "action_type": "send_email",
                    "payload": {"provider": "google", "to": "client@example.com", "subject": "Hi", "body": "Body"},
                }
            )
            with patch.object(service.google_provider, "send_email", return_value={"sent": True}) as send_email:
                completed = service.approve_item(approval.id)
            self.assertEqual(completed.status, "completed")
            send_email.assert_called_once_with("client@example.com", "Hi", "Body")

    def test_scheduler_creates_briefing_approval_once_per_day(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = _settings(Path(directory) / "state.json")
            service = AssistantService(settings, StateStore(settings.data_path))
            now = datetime(2026, 6, 8, 8, 5, tzinfo=timezone.utc)
            first = service.run_scheduler_once(now)
            second = service.run_scheduler_once(now)
            approvals = service.list_approvals()
            self.assertEqual(first["status"], "generated")
            self.assertEqual(second["status"], "already_generated")
            self.assertEqual(approvals[0]["action_type"], "send_briefing")

    def test_approval_for_email_send_fails_without_write_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = _settings(Path(directory) / "state.json")
            service = AssistantService(settings, StateStore(settings.data_path))
            approval = service.create_approval(
                {
                    "action_type": "send_email",
                    "payload": {"provider": "google", "to": "a@example.com", "subject": "Hi", "body": "Body"},
                }
            )
            completed = service.approve_item(approval.id)
            self.assertEqual(completed.status, "failed")
            self.assertIn("scope", completed.error)

    def test_calendar_write_approval_fails_without_write_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = _settings(Path(directory) / "state.json")
            service = AssistantService(settings, StateStore(settings.data_path))
            approval = service.create_approval(
                {
                    "action_type": "create_focus_time",
                    "payload": {
                        "provider": "google",
                        "title": "Focus time",
                        "start": "2026-06-16T10:00:00+03:00",
                        "end": "2026-06-16T11:00:00+03:00",
                    },
                }
            )
            completed = service.approve_item(approval.id)
            self.assertEqual(completed.status, "failed")
            self.assertIn("scope", completed.error)

    def test_connection_status_uses_stored_google_scopes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            settings = replace(
                _settings(base / "state.json"),
                google_token_path=base / "tokens.json",
                google_oauth_state_path=base / "oauth_state.json",
            )
            GoogleTokenStore(settings.google_token_path).save_token_response(
                {
                    "access_token": "access",
                    "refresh_token": "refresh",
                    "expires_in": 3600,
                    "scope": f"{GMAIL_READONLY_SCOPE} {CALENDAR_READONLY_SCOPE}",
                }
            )
            service = AssistantService(settings, StateStore(settings.data_path))
            connections = service.connection_status()
            self.assertTrue(connections["gmail"]["connected"])
            self.assertTrue(connections["calendar"]["connected"])

    def test_demo_mode_runs_without_oauth_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = _settings(Path(directory) / "state.json")
            service = AssistantService(settings, StateStore(settings.data_path))
            email_result = service.refresh_emails()
            calendar_result = service.refresh_calendar()
            briefing = service.generate_briefing()

            self.assertTrue(email_result["used_demo"])
            self.assertTrue(calendar_result["used_demo"])
            self.assertEqual(email_result["errors"], [])
            self.assertEqual(calendar_result["errors"], [])
            self.assertIn("בוקר טוב", briefing.text)
            self.assertFalse(service.connection_status()["gmail"]["connected"])
            self.assertFalse(service.connection_status()["outlook_mail"]["connected"])

    def test_demo_reset_preserves_real_provider_data_and_seeds_approvals(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = _settings(Path(directory) / "state.json")
            store = StateStore(settings.data_path)
            service = AssistantService(settings, store)
            state = store.load()
            state["emails"] = [
                EmailItem(
                    id="gmail_real",
                    subject="Real provider email",
                    sender="real@example.com",
                    received_at=datetime.now(timezone.utc).isoformat(),
                    snippet="Keep me",
                    source="gmail",
                ).to_dict()
            ]
            state["events"] = [
                CalendarEvent(
                    id="gcal_real",
                    title="Real provider event",
                    start=datetime.now(timezone.utc).isoformat(),
                    end=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                    source="google_calendar",
                ).to_dict()
            ]
            state["tasks"] = [
                TaskItem(id="manual_real", title="Real manual task", source="manual").to_dict()
            ]
            state["approvals"] = [
                ApprovalItem(
                    id="real_approval",
                    action_type="send_message",
                    title="Real approval",
                    description="Preserve me",
                    payload={"text": "real"},
                ).to_dict()
            ]
            store.save(state)

            dashboard = service.reset_demo()
            saved = store.load()

            self.assertTrue(any(item["id"] == "gmail_real" for item in saved["emails"]))
            self.assertTrue(any(item["id"] == "gcal_real" for item in saved["events"]))
            self.assertTrue(any(item["id"] == "manual_real" for item in saved["tasks"]))
            self.assertFalse(any(item["id"] == "real_approval" for item in saved["approvals"]))
            self.assertGreaterEqual(len([item for item in saved["emails"] if item["source"] == "demo"]), 8)
            self.assertGreaterEqual(len([item for item in saved["events"] if item["source"] == "demo"]), 5)
            self.assertGreaterEqual(len([item for item in saved["tasks"] if item["source"] == "demo"]), 5)
            self.assertTrue(all(item["id"].startswith("demo_approval") for item in saved["approvals"]))
            self.assertGreaterEqual(len(saved["approvals"]), 4)
            self.assertGreaterEqual(dashboard["analytics"]["email"]["total"], 8)
            self.assertTrue(dashboard["latest_briefing"]["text"])

    def test_status_includes_runtime_and_scheduler_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = _settings(Path(directory) / "state.json")
            service = AssistantService(settings, StateStore(settings.data_path))
            status = service.status()

            self.assertTrue(status["demo_mode"])
            self.assertIn("current_datetime", status)
            self.assertIn("current_date", status)
            self.assertIn("current_time", status)
            self.assertIn(status["scheduler"]["status"], {"waiting_for_briefing_hour", "ready_to_generate"})
            self.assertIn("connections", status)


class StorageTests(unittest.TestCase):
    def test_state_store_handles_concurrent_saves(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.json")

            def save_state(index: int) -> None:
                state = store.load()
                state["tasks"] = [{"id": f"task_{index}", "title": f"Task {index}"}]
                store.save(state)

            with ThreadPoolExecutor(max_workers=4) as executor:
                list(executor.map(save_state, range(12)))

            state = store.load()
            self.assertIn("tasks", state)
            self.assertEqual(len(list(Path(directory).glob("*.tmp"))), 0)


class GoogleOAuthTests(unittest.TestCase):
    def test_authorization_url_uses_readonly_scopes_and_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = _google_settings(Path(directory))
            manager = GoogleOAuthManager(settings)
            url = manager.authorization_url("http://127.0.0.1:8765/oauth/google/callback")
            query = parse_qs(urlparse(url).query)
            scopes = set(query["scope"][0].split())
            self.assertEqual(query["response_type"][0], "code")
            self.assertEqual(query["access_type"][0], "offline")
            self.assertIn(GMAIL_READONLY_SCOPE, scopes)
            self.assertIn(CALENDAR_READONLY_SCOPE, scopes)
            self.assertTrue(query["state"][0])

    def test_oauth_callback_stores_tokens_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = _google_settings(Path(directory))
            manager = GoogleOAuthManager(settings)
            manager.authorization_url("http://127.0.0.1:8765/oauth/google/callback")
            state = manager.state_store.load()["state"]
            with patch(
                "assistant_agent.google_oauth.request_json",
                return_value={
                    "access_token": "access",
                    "refresh_token": "refresh",
                    "expires_in": 3600,
                    "scope": f"{GMAIL_READONLY_SCOPE} {CALENDAR_READONLY_SCOPE}",
                },
            ):
                status = manager.complete(code="code", state=state)
            self.assertTrue(status["gmail_connected"])
            self.assertTrue(status["calendar_connected"])
            self.assertEqual(GoogleTokenStore(settings.google_token_path).refresh_token(), "refresh")


class MicrosoftOAuthTests(unittest.TestCase):
    def test_authorization_url_uses_read_scopes_and_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = _microsoft_settings(Path(directory))
            manager = MicrosoftOAuthManager(settings)
            url = manager.authorization_url("http://127.0.0.1:8765/oauth/microsoft/callback")
            query = parse_qs(urlparse(url).query)
            scopes = set(query["scope"][0].split())
            self.assertEqual(query["response_type"][0], "code")
            self.assertIn("offline_access", scopes)
            self.assertIn(MS_MAIL_READ, scopes)
            self.assertIn(MS_CALENDAR_READ, scopes)


class ProjectSafetyTests(unittest.TestCase):
    def test_provider_code_does_not_delete_email_messages(self) -> None:
        root = Path(__file__).resolve().parents[1]
        google_code = (root / "assistant_agent" / "providers" / "google.py").read_text(encoding="utf-8").casefold()
        microsoft_code = (root / "assistant_agent" / "providers" / "microsoft.py").read_text(encoding="utf-8").casefold()

        self.assertNotIn("delete_email", google_code + microsoft_code)
        self.assertNotIn("delete_message", google_code + microsoft_code)
        self.assertNotIn("messages/delete", google_code)
        self.assertNotIn("/trash", google_code)
        self.assertNotIn("/me/messages/", microsoft_code)
        self.assertNotIn("mailfolders/inbox/messages/", microsoft_code)

    def test_frontend_contains_no_oauth_tokens_or_secrets(self) -> None:
        root = Path(__file__).resolve().parents[1]
        forbidden = {
            "access_token",
            "refresh_token",
            "client_secret",
            "google_client_secret",
            "ms_client_secret",
            "authorization: bearer",
        }
        for path in (root / "web").glob("*"):
            if path.is_file():
                text = path.read_text(encoding="utf-8").casefold()
                for term in forbidden:
                    with self.subTest(path=path.name, term=term):
                        self.assertNotIn(term, text)


def _settings(path: Path) -> Settings:
    return Settings(
        host="127.0.0.1",
        port=8765,
        timezone="Asia/Jerusalem",
        demo_mode=True,
        data_path=path,
        openai_api_key="",
        openai_model="",
        google_client_id="",
        google_client_secret="",
        google_refresh_token="",
        google_access_token="",
        google_calendar_id="primary",
        ms_client_id="",
        ms_client_secret="",
        ms_refresh_token="",
        ms_tenant_id="common",
        ms_graph_access_token="",
        slack_webhook_url="",
        whatsapp_access_token="",
        whatsapp_phone_number_id="",
        whatsapp_to="",
    )


def _google_settings(directory: Path) -> Settings:
    return replace(
        _settings(directory / "state.json"),
        google_client_id="client-id",
        google_client_secret="client-secret",
        google_redirect_uri="http://127.0.0.1:8765/oauth/google/callback",
        google_token_path=directory / "tokens.json",
        google_oauth_state_path=directory / "oauth_state.json",
    )


def _microsoft_settings(directory: Path) -> Settings:
    return replace(
        _settings(directory / "state.json"),
        ms_client_id="client-id",
        ms_client_secret="client-secret",
        ms_redirect_uri="http://127.0.0.1:8765/oauth/microsoft/callback",
        ms_token_path=directory / "tokens.json",
        ms_oauth_state_path=directory / "oauth_state.json",
    )


if __name__ == "__main__":
    unittest.main()
