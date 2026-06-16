from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4


Priority = Literal["urgent", "important", "routine", "fyi"]
TaskStatus = Literal["open", "done"]
ApprovalStatus = Literal["pending", "approved", "rejected", "completed", "failed"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


@dataclass
class EmailItem:
    id: str
    subject: str
    sender: str
    received_at: str
    snippet: str
    body: str = ""
    source: str = "demo"
    labels: list[str] = field(default_factory=list)
    priority: Priority = "routine"
    requires_response: bool = False
    summary: str = ""
    draft_reply: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EmailItem":
        return cls(
            id=str(data.get("id") or new_id("email")),
            subject=str(data.get("subject", "")),
            sender=str(data.get("sender", "")),
            received_at=str(data.get("received_at") or now_iso()),
            snippet=str(data.get("snippet", "")),
            body=str(data.get("body", "")),
            source=str(data.get("source", "demo")),
            labels=list(data.get("labels", [])),
            priority=data.get("priority", "routine"),
            requires_response=bool(data.get("requires_response", False)),
            summary=str(data.get("summary", "")),
            draft_reply=str(data.get("draft_reply", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CalendarEvent:
    id: str
    title: str
    start: str
    end: str
    source: str = "demo"
    attendees: list[str] = field(default_factory=list)
    location: str = ""
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CalendarEvent":
        return cls(
            id=str(data.get("id") or new_id("event")),
            title=str(data.get("title", "")),
            start=str(data.get("start") or now_iso()),
            end=str(data.get("end") or now_iso()),
            source=str(data.get("source", "demo")),
            attendees=list(data.get("attendees", [])),
            location=str(data.get("location", "")),
            description=str(data.get("description", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TaskItem:
    id: str
    title: str
    notes: str = ""
    due_at: str | None = None
    priority: Priority = "routine"
    status: TaskStatus = "open"
    created_at: str = field(default_factory=now_iso)
    source: str = "manual"
    related_item_id: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskItem":
        return cls(
            id=str(data.get("id") or new_id("task")),
            title=str(data.get("title", "")),
            notes=str(data.get("notes", "")),
            due_at=data.get("due_at"),
            priority=data.get("priority", "routine"),
            status=data.get("status", "open"),
            created_at=str(data.get("created_at") or now_iso()),
            source=str(data.get("source", "manual")),
            related_item_id=str(data.get("related_item_id", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DailyBriefing:
    id: str
    generated_at: str
    text: str
    urgent_count: int
    important_count: int
    conflict_count: int
    open_task_count: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DailyBriefing":
        return cls(
            id=str(data.get("id") or new_id("briefing")),
            generated_at=str(data.get("generated_at") or now_iso()),
            text=str(data.get("text", "")),
            urgent_count=int(data.get("urgent_count", 0)),
            important_count=int(data.get("important_count", 0)),
            conflict_count=int(data.get("conflict_count", 0)),
            open_task_count=int(data.get("open_task_count", 0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ApprovalItem:
    id: str
    action_type: str
    title: str
    description: str
    payload: dict[str, Any] = field(default_factory=dict)
    status: ApprovalStatus = "pending"
    risk: str = "external_action"
    created_at: str = field(default_factory=now_iso)
    approved_at: str | None = None
    completed_at: str | None = None
    result: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ApprovalItem":
        return cls(
            id=str(data.get("id") or new_id("approval")),
            action_type=str(data.get("action_type", "")),
            title=str(data.get("title", "")),
            description=str(data.get("description", "")),
            payload=dict(data.get("payload", {})),
            status=data.get("status", "pending"),
            risk=str(data.get("risk", "external_action")),
            created_at=str(data.get("created_at") or now_iso()),
            approved_at=data.get("approved_at"),
            completed_at=data.get("completed_at"),
            result=dict(data.get("result", {})),
            error=str(data.get("error", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
