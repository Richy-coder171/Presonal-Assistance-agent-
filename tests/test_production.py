from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import inspect
from starlette.testclient import TestClient

from assistant_agent.config import Settings
from assistant_agent.db import OAuthToken, init_database
from assistant_agent.google_oauth import GMAIL_SEND_SCOPE, GoogleDatabaseTokenStore, GoogleTokenStore
from assistant_agent.models import EmailItem
from assistant_agent.server import create_app
from assistant_agent.service import AssistantService
from assistant_agent.storage import StateStore
from assistant_agent.worker import run_scheduled_briefings_once


class DatabaseProductionTests(unittest.TestCase):
    def test_init_database_creates_production_tables(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_url = _sqlite_url(Path(directory) / "agent.db")
            engine = init_database(database_url)
            tables = set(inspect(engine).get_table_names())
            self.assertTrue(
                {
                    "users",
                    "provider_connections",
                    "oauth_tokens",
                    "emails",
                    "calendar_events",
                    "tasks",
                    "approvals",
                    "briefings",
                    "audit_logs",
                }.issubset(tables)
            )
            engine.dispose()

    def test_state_store_persists_workflow_state_in_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.json")
            state = store.load()
            state["emails"] = [
                EmailItem(
                    id="email_db",
                    subject="Database backed",
                    sender="client@example.com",
                    received_at="2026-06-16T08:00:00+00:00",
                    snippet="Stored in SQL",
                ).to_dict()
            ]
            store.save(state)
            self.assertEqual(store.load()["emails"][0]["id"], "email_db")
            store.engine.dispose()


class TokenEncryptionProductionTests(unittest.TestCase):
    def test_json_token_store_does_not_save_plaintext_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tokens.json"
            store = GoogleTokenStore(path)
            store.save_token_response(
                {
                    "access_token": "plain-access-token",
                    "refresh_token": "plain-refresh-token",
                    "id_token": "plain-id-token",
                    "scope": GMAIL_SEND_SCOPE,
                    "expires_in": 3600,
                }
            )
            raw = path.read_text(encoding="utf-8")
            self.assertNotIn("plain-access-token", raw)
            self.assertNotIn("plain-refresh-token", raw)
            self.assertNotIn("plain-id-token", raw)
            self.assertEqual(store.refresh_token(), "plain-refresh-token")

    def test_database_token_store_encrypts_oauth_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = replace(
                _settings(Path(directory) / "state.json"),
                database_url=_sqlite_url(Path(directory) / "agent.db"),
                token_encryption_key="test-token-key",
                admin_email="admin@example.com",
            )
            store = GoogleDatabaseTokenStore(settings)
            store.save_token_response(
                {
                    "access_token": "db-access-token",
                    "refresh_token": "db-refresh-token",
                    "scope": GMAIL_SEND_SCOPE,
                    "expires_in": 3600,
                }
            )
            with store.Session() as session:
                row = session.query(OAuthToken).filter_by(provider="google").one()
                self.assertNotEqual(row.token_payload["access_token"], "db-access-token")
                self.assertTrue(row.token_payload["access_token"].startswith("enc:v1:"))
            self.assertEqual(store.refresh_token(), "db-refresh-token")
            store.engine.dispose()


class AuthAndApiProductionTests(unittest.TestCase):
    def test_auth_rejects_unauthorized_api_and_accepts_admin_session(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = replace(
                _settings(Path(directory) / "state.json"),
                auth_enabled=True,
                admin_email="admin@example.com",
                admin_password="secret",
                session_secret="session-secret",
            )
            service = AssistantService(settings, StateStore(settings.data_path))
            client = TestClient(create_app(settings, service))

            self.assertEqual(client.get("/api/dashboard").status_code, 401)
            bad_login = client.post(
                "/auth/login",
                json={"email": "admin@example.com", "password": "wrong"},
            )
            self.assertEqual(bad_login.status_code, 401)

            login = client.post(
                "/auth/login",
                json={"email": "admin@example.com", "password": "secret"},
            )
            self.assertEqual(login.status_code, 200)
            self.assertEqual(client.get("/api/dashboard").status_code, 200)
            service.store.engine.dispose()

    def test_health_and_status_routes_return_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = _settings(Path(directory) / "state.json")
            service = AssistantService(settings, StateStore(settings.data_path))
            client = TestClient(create_app(settings, service))

            health = client.get("/health")
            status = client.get("/api/status")
            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.json()["status"], "ok")
            self.assertEqual(status.status_code, 200)
            self.assertTrue(status.json()["demo_mode"])
            service.store.engine.dispose()


class ApprovalAndAuditProductionTests(unittest.TestCase):
    def test_unsupported_email_deletion_is_blocked_and_audited(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = _settings(Path(directory) / "state.json")
            service = AssistantService(settings, StateStore(settings.data_path))
            approval = service.create_approval({"action_type": "delete_email", "payload": {"id": "email_1"}})
            completed = service.approve_item(approval.id)
            logs = service.audit_logs()

            self.assertEqual(completed.status, "failed")
            self.assertIn("deletion is not supported", completed.error)
            self.assertTrue(any(log["action"] == "approval_created" for log in logs))
            self.assertTrue(any(log["action"] == "delete_email" and log["status"] == "failure" for log in logs))
            service.store.engine.dispose()

    def test_approved_write_scope_is_required_before_provider_call(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = _settings(Path(directory) / "state.json")
            service = AssistantService(settings, StateStore(settings.data_path))
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
            with patch.object(service.google_provider, "send_email") as send_email:
                completed = service.approve_item(approval.id)
            self.assertEqual(completed.status, "failed")
            send_email.assert_not_called()
            service.store.engine.dispose()


class WorkerProductionTests(unittest.TestCase):
    def test_worker_retries_scheduler_failures(self) -> None:
        settings = replace(_settings(Path("state.json")), scheduler_retry_attempts=2, scheduler_retry_delay_seconds=0)
        service = _FlakySchedulerService()
        result = run_scheduled_briefings_once(settings=settings, service=service)
        self.assertEqual(result["status"], "generated")
        self.assertEqual(service.calls, 2)
        self.assertTrue(any(log["status"] == "failure" for log in service.logs))
        self.assertTrue(any(log["status"] == "success" for log in service.logs))


class _FlakySchedulerService:
    def __init__(self) -> None:
        self.calls = 0
        self.logs: list[dict] = []

    def run_scheduler_once(self, now=None) -> dict:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary scheduler failure")
        return {"status": "generated"}

    def log_audit(self, action: str, status: str, **kwargs) -> None:
        self.logs.append({"action": action, "status": status, **kwargs})


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


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


if __name__ == "__main__":
    unittest.main()
