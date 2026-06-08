from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from assistant_agent.classifier import classify_email, detect_conflicts
from assistant_agent.config import Settings
from assistant_agent.models import CalendarEvent, EmailItem
from assistant_agent.service import AssistantService
from assistant_agent.storage import StateStore


class ClassifierTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
