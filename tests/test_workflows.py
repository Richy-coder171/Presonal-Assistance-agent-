from __future__ import annotations

import tempfile
import unittest
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
from assistant_agent.models import CalendarEvent, EmailItem
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
