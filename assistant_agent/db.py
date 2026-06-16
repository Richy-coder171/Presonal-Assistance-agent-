from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from sqlalchemy import Boolean, Column, ForeignKey, Index, String, Text, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker
from sqlalchemy.types import JSON

from .config import ROOT_DIR


Base = declarative_base()
DEFAULT_USER_EMAIL = "admin@example.local"


class User(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False, default="")
    role = Column(String(64), nullable=False, default="admin")
    is_active = Column(Boolean, nullable=False, default=True)
    last_briefing_date = Column(String(32), nullable=False, default="")
    settings_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(String(64), nullable=False, default="")
    updated_at = Column(String(64), nullable=False, default="")

    provider_connections = relationship("ProviderConnection", cascade="all, delete-orphan")
    oauth_tokens = relationship("OAuthToken", cascade="all, delete-orphan")


class ProviderConnection(Base):
    __tablename__ = "provider_connections"

    id = Column(String(96), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    provider = Column(String(64), nullable=False, index=True)
    account_email = Column(String(255), nullable=False, default="")
    scopes_json = Column(JSON, nullable=False, default=list)
    read_enabled = Column(Boolean, nullable=False, default=True)
    write_enabled = Column(Boolean, nullable=False, default=False)
    connected_at = Column(String(64), nullable=False, default="")
    updated_at = Column(String(64), nullable=False, default="")
    status = Column(String(64), nullable=False, default="connected")
    metadata_json = Column(JSON, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_provider_connections_user_provider", "user_id", "provider", unique=True),
    )


class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    id = Column(String(96), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    provider = Column(String(64), nullable=False, index=True)
    token_payload = Column(JSON, nullable=False, default=dict)
    scopes_json = Column(JSON, nullable=False, default=list)
    expires_at = Column(String(64), nullable=False, default="")
    updated_at = Column(String(64), nullable=False, default="")

    __table_args__ = (
        Index("ix_oauth_tokens_user_provider", "user_id", "provider", unique=True),
    )


class EmailRecord(Base):
    __tablename__ = "emails"

    id = Column(String(128), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    source = Column(String(64), nullable=False, default="")
    subject = Column(Text, nullable=False, default="")
    sender = Column(Text, nullable=False, default="")
    received_at = Column(String(64), nullable=False, default="")
    priority = Column(String(32), nullable=False, default="routine")
    requires_response = Column(Boolean, nullable=False, default=False)
    payload = Column(JSON, nullable=False, default=dict)


class CalendarEventRecord(Base):
    __tablename__ = "calendar_events"

    id = Column(String(128), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    source = Column(String(64), nullable=False, default="")
    title = Column(Text, nullable=False, default="")
    start = Column(String(64), nullable=False, default="")
    end = Column(String(64), nullable=False, default="")
    payload = Column(JSON, nullable=False, default=dict)


class TaskRecord(Base):
    __tablename__ = "tasks"

    id = Column(String(128), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(Text, nullable=False, default="")
    status = Column(String(32), nullable=False, default="open")
    priority = Column(String(32), nullable=False, default="routine")
    due_at = Column(String(64), nullable=True)
    source = Column(String(64), nullable=False, default="manual")
    created_at = Column(String(64), nullable=False, default="")
    payload = Column(JSON, nullable=False, default=dict)


class ApprovalRecord(Base):
    __tablename__ = "approvals"

    id = Column(String(128), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    action_type = Column(String(96), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="pending", index=True)
    risk = Column(String(96), nullable=False, default="external_action")
    created_at = Column(String(64), nullable=False, default="")
    payload = Column(JSON, nullable=False, default=dict)


class BriefingRecord(Base):
    __tablename__ = "briefings"

    id = Column(String(128), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    generated_at = Column(String(64), nullable=False, default="", index=True)
    sent_at = Column(String(64), nullable=True)
    payload = Column(JSON, nullable=False, default=dict)


class AuditLogRecord(Base):
    __tablename__ = "audit_logs"

    id = Column(String(128), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    action = Column(String(96), nullable=False, index=True)
    status = Column(String(64), nullable=False, index=True)
    provider = Column(String(64), nullable=False, default="")
    entity_type = Column(String(96), nullable=False, default="")
    entity_id = Column(String(128), nullable=False, default="")
    message = Column(Text, nullable=False, default="")
    error = Column(Text, nullable=False, default="")
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(String(64), nullable=False, default="", index=True)


def init_database(engine_or_url: Engine | str | None = None) -> Engine:
    engine = engine_or_url if isinstance(engine_or_url, Engine) else create_engine_for_url(engine_or_url)
    Base.metadata.create_all(engine)
    return engine


def create_engine_for_url(database_url: str | None = None) -> Engine:
    url = normalize_database_url(database_url or default_sqlite_url())
    connect_args: dict[str, Any] = {}
    if url.startswith("sqlite:"):
        connect_args["check_same_thread"] = False
        _ensure_sqlite_parent(url)
    return create_engine(url, future=True, connect_args=connect_args)


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return "postgresql+psycopg://" + database_url[len("postgres://"):]
    return database_url


def default_sqlite_url() -> str:
    path = ROOT_DIR / "data" / "assistant.db"
    return sqlite_url_for_path(path)


def sqlite_url_for_path(path: Path) -> str:
    target = path
    if target.suffix.lower() == ".json":
        target = target.with_suffix(".sqlite3")
    return f"sqlite:///{target.resolve().as_posix()}"


def ensure_user(session: Session, email: str | None = None) -> User:
    user_email = (email or DEFAULT_USER_EMAIL).strip().lower() or DEFAULT_USER_EMAIL
    user_id = user_id_for_email(user_email)
    user = session.get(User, user_id)
    if user:
        return user
    user = User(
        id=user_id,
        email=user_email,
        display_name=user_email,
        role="admin",
        is_active=True,
    )
    session.add(user)
    session.flush()
    return user


def user_id_for_email(email: str) -> str:
    digest = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()[:16]
    return f"user_{digest}"


def _ensure_sqlite_parent(url: str) -> None:
    if url == "sqlite:///:memory:":
        return
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return
    path_text = url[len(prefix):]
    Path(path_text).parent.mkdir(parents=True, exist_ok=True)
