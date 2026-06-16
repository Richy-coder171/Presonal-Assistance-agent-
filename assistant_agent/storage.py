from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any

from .db import (
    ApprovalRecord,
    AuditLogRecord,
    BriefingRecord,
    CalendarEventRecord,
    EmailRecord,
    TaskRecord,
    create_engine_for_url,
    ensure_user,
    init_database,
    session_factory,
    sqlite_url_for_path,
)
from .models import new_id, now_iso


DEFAULT_STATE = {
    "emails": [],
    "events": [],
    "tasks": [],
    "briefings": [],
    "approvals": [],
    "scheduler": {},
}

_STATE_LOCK = Lock()


class StateStore:
    def __init__(
        self,
        path: Path,
        database_url: str | None = None,
        user_email: str | None = None,
    ) -> None:
        self.path = path
        self.database_url = database_url or sqlite_url_for_path(path)
        self.user_email = user_email
        self.engine = init_database(create_engine_for_url(self.database_url))
        self.Session = session_factory(self.engine)

    def load(self) -> dict[str, Any]:
        with _STATE_LOCK:
            with self.Session() as session:
                user = ensure_user(session, self.user_email)
                session.commit()
                state = _fresh_state()
                state["emails"] = [
                    dict(row.payload)
                    for row in session.query(EmailRecord)
                    .filter_by(user_id=user.id)
                    .order_by(EmailRecord.received_at.desc())
                    .all()
                ]
                state["events"] = [
                    dict(row.payload)
                    for row in session.query(CalendarEventRecord)
                    .filter_by(user_id=user.id)
                    .order_by(CalendarEventRecord.start.asc())
                    .all()
                ]
                state["tasks"] = [
                    dict(row.payload)
                    for row in session.query(TaskRecord)
                    .filter_by(user_id=user.id)
                    .order_by(TaskRecord.created_at.desc())
                    .all()
                ]
                state["briefings"] = [
                    dict(row.payload)
                    for row in session.query(BriefingRecord)
                    .filter_by(user_id=user.id)
                    .order_by(BriefingRecord.generated_at.desc())
                    .all()
                ]
                state["approvals"] = [
                    dict(row.payload)
                    for row in session.query(ApprovalRecord)
                    .filter_by(user_id=user.id)
                    .order_by(ApprovalRecord.created_at.desc())
                    .all()
                ]
                state["scheduler"] = {"last_briefing_date": user.last_briefing_date or ""}
                return state

    def save(self, state: dict[str, Any]) -> None:
        with _STATE_LOCK:
            with self.Session() as session:
                user = ensure_user(session, self.user_email)
                scheduler = dict(state.get("scheduler", {}))
                user.last_briefing_date = str(scheduler.get("last_briefing_date", ""))
                _replace_emails(session, user.id, list(state.get("emails", [])))
                _replace_events(session, user.id, list(state.get("events", [])))
                _replace_tasks(session, user.id, list(state.get("tasks", [])))
                _replace_briefings(session, user.id, list(state.get("briefings", [])))
                _replace_approvals(session, user.id, list(state.get("approvals", [])))
                session.commit()

    def append_audit_log(
        self,
        *,
        action: str,
        status: str,
        provider: str = "",
        entity_type: str = "",
        entity_id: str = "",
        message: str = "",
        error: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        record = {
            "id": new_id("audit"),
            "action": action,
            "status": status,
            "provider": provider,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "message": message,
            "error": error,
            "metadata": dict(metadata or {}),
            "created_at": now_iso(),
        }
        with _STATE_LOCK:
            with self.Session() as session:
                user = ensure_user(session, self.user_email)
                session.add(
                    AuditLogRecord(
                        id=record["id"],
                        user_id=user.id,
                        action=action,
                        status=status,
                        provider=provider,
                        entity_type=entity_type,
                        entity_id=entity_id,
                        message=message,
                        error=error,
                        metadata_json=record["metadata"],
                        created_at=record["created_at"],
                    )
                )
                session.commit()
        return record

    def list_audit_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        with _STATE_LOCK:
            with self.Session() as session:
                user = ensure_user(session, self.user_email)
                session.commit()
                rows = (
                    session.query(AuditLogRecord)
                    .filter_by(user_id=user.id)
                    .order_by(AuditLogRecord.created_at.desc())
                    .limit(limit)
                    .all()
                )
                return [
                    {
                        "id": row.id,
                        "action": row.action,
                        "status": row.status,
                        "provider": row.provider,
                        "entity_type": row.entity_type,
                        "entity_id": row.entity_id,
                        "message": row.message,
                        "error": row.error,
                        "metadata": dict(row.metadata_json or {}),
                        "created_at": row.created_at,
                    }
                    for row in rows
                ]


def _fresh_state() -> dict[str, Any]:
    return {key: _clone_default(value) for key, value in DEFAULT_STATE.items()}


def _clone_default(value: Any) -> Any:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, dict):
        return dict(value)
    return value


def _replace_emails(session: Any, user_id: str, items: list[dict[str, Any]]) -> None:
    session.query(EmailRecord).filter_by(user_id=user_id).delete()
    for item in items:
        session.add(
            EmailRecord(
                id=str(item.get("id") or new_id("email")),
                user_id=user_id,
                source=str(item.get("source", "")),
                subject=str(item.get("subject", "")),
                sender=str(item.get("sender", "")),
                received_at=str(item.get("received_at", "")),
                priority=str(item.get("priority", "routine")),
                requires_response=bool(item.get("requires_response", False)),
                payload=dict(item),
            )
        )


def _replace_events(session: Any, user_id: str, items: list[dict[str, Any]]) -> None:
    session.query(CalendarEventRecord).filter_by(user_id=user_id).delete()
    for item in items:
        session.add(
            CalendarEventRecord(
                id=str(item.get("id") or new_id("event")),
                user_id=user_id,
                source=str(item.get("source", "")),
                title=str(item.get("title", "")),
                start=str(item.get("start", "")),
                end=str(item.get("end", "")),
                payload=dict(item),
            )
        )


def _replace_tasks(session: Any, user_id: str, items: list[dict[str, Any]]) -> None:
    session.query(TaskRecord).filter_by(user_id=user_id).delete()
    for item in items:
        session.add(
            TaskRecord(
                id=str(item.get("id") or new_id("task")),
                user_id=user_id,
                title=str(item.get("title", "")),
                status=str(item.get("status", "open")),
                priority=str(item.get("priority", "routine")),
                due_at=item.get("due_at"),
                source=str(item.get("source", "manual")),
                created_at=str(item.get("created_at", "")),
                payload=dict(item),
            )
        )


def _replace_briefings(session: Any, user_id: str, items: list[dict[str, Any]]) -> None:
    session.query(BriefingRecord).filter_by(user_id=user_id).delete()
    for item in items:
        session.add(
            BriefingRecord(
                id=str(item.get("id") or new_id("briefing")),
                user_id=user_id,
                generated_at=str(item.get("generated_at", "")),
                sent_at=item.get("sent_at"),
                payload=dict(item),
            )
        )


def _replace_approvals(session: Any, user_id: str, items: list[dict[str, Any]]) -> None:
    session.query(ApprovalRecord).filter_by(user_id=user_id).delete()
    for item in items:
        session.add(
            ApprovalRecord(
                id=str(item.get("id") or new_id("approval")),
                user_id=user_id,
                action_type=str(item.get("action_type", "")),
                status=str(item.get("status", "pending")),
                risk=str(item.get("risk", "external_action")),
                created_at=str(item.get("created_at", "")),
                payload=dict(item),
            )
        )
