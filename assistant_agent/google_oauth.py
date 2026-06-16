from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from .config import Settings
from .db import OAuthToken, ProviderConnection, create_engine_for_url, ensure_user, init_database, session_factory
from .http_client import HttpError, request_json
from .token_crypto import decrypt_token_payload, encrypt_token_payload


GOOGLE_AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
CALENDAR_READONLY_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
CALENDAR_EVENTS_SCOPE = "https://www.googleapis.com/auth/calendar.events"
GOOGLE_READONLY_SCOPES = (GMAIL_READONLY_SCOPE, CALENDAR_READONLY_SCOPE)


class GoogleOAuthError(RuntimeError):
    """A user-facing Google OAuth failure."""


class SecureJsonStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        if not isinstance(payload, dict):
            return {}
        return decrypt_token_payload(payload)

    def save(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        temp_path.write_text(
            json.dumps(encrypt_token_payload(payload), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _restrict_permissions(temp_path)
        temp_path.replace(self.path)
        _restrict_permissions(self.path)

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()


class GoogleTokenStore(SecureJsonStore):
    def connected(self) -> bool:
        tokens = self.load()
        return bool(tokens.get("access_token") or tokens.get("refresh_token"))

    def has_scope(self, scope: str) -> bool:
        if not self.connected():
            return False
        return scope in self.scopes()

    def scopes(self) -> set[str]:
        value = self.load().get("scope", "")
        if isinstance(value, list):
            return {str(item) for item in value}
        return set(str(value).split())

    def valid_access_token(self) -> str | None:
        tokens = self.load()
        access_token = str(tokens.get("access_token", "")).strip()
        if not access_token:
            return None
        expires_at = tokens.get("expires_at")
        if not expires_at:
            return access_token
        try:
            expiry = _parse_datetime(str(expires_at))
        except ValueError:
            return None
        if expiry <= datetime.now(timezone.utc) + timedelta(seconds=60):
            return None
        return access_token

    def refresh_token(self) -> str:
        return str(self.load().get("refresh_token", "")).strip()

    def save_token_response(self, response: dict[str, Any]) -> None:
        existing = self.load()
        merged = dict(existing)
        for key in ("access_token", "refresh_token", "token_type", "scope", "id_token"):
            if response.get(key):
                merged[key] = response[key]
        if response.get("expires_in"):
            merged["expires_at"] = (
                datetime.now(timezone.utc)
                + timedelta(seconds=int(response["expires_in"]))
            ).isoformat()
        merged["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.save(merged)


class GoogleDatabaseTokenStore(GoogleTokenStore):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.provider = "google"
        self.path = settings.google_token_path
        self.engine = init_database(create_engine_for_url(settings.database_url))
        self.Session = session_factory(self.engine)

    def load(self) -> dict[str, Any]:
        with self.Session() as session:
            user = ensure_user(session, self.settings.admin_email)
            session.commit()
            row = (
                session.query(OAuthToken)
                .filter_by(user_id=user.id, provider=self.provider)
                .one_or_none()
            )
            if not row:
                return {}
            return decrypt_token_payload(
                dict(row.token_payload or {}),
                self.settings.token_encryption_key,
            )

    def save(self, payload: dict[str, Any]) -> None:
        encrypted = encrypt_token_payload(payload, self.settings.token_encryption_key)
        scopes = _scope_list(payload.get("scope", ""))
        now = datetime.now(timezone.utc).isoformat()
        with self.Session() as session:
            user = ensure_user(session, self.settings.admin_email)
            row = (
                session.query(OAuthToken)
                .filter_by(user_id=user.id, provider=self.provider)
                .one_or_none()
            )
            if row is None:
                row = OAuthToken(
                    id=f"oauth_{self.provider}_{user.id}",
                    user_id=user.id,
                    provider=self.provider,
                )
                session.add(row)
            row.token_payload = encrypted
            row.scopes_json = scopes
            row.expires_at = str(payload.get("expires_at", ""))
            row.updated_at = now

            connection = (
                session.query(ProviderConnection)
                .filter_by(user_id=user.id, provider=self.provider)
                .one_or_none()
            )
            if connection is None:
                connection = ProviderConnection(
                    id=f"provider_{self.provider}_{user.id}",
                    user_id=user.id,
                    provider=self.provider,
                    connected_at=now,
                )
                session.add(connection)
            connection.scopes_json = scopes
            connection.read_enabled = True
            connection.write_enabled = any(
                scope in {GMAIL_SEND_SCOPE, CALENDAR_EVENTS_SCOPE}
                for scope in scopes
            )
            connection.updated_at = now
            connection.status = "connected"
            session.commit()

    def clear(self) -> None:
        with self.Session() as session:
            user = ensure_user(session, self.settings.admin_email)
            session.query(OAuthToken).filter_by(user_id=user.id, provider=self.provider).delete()
            session.query(ProviderConnection).filter_by(user_id=user.id, provider=self.provider).delete()
            session.commit()


class GoogleOAuthManager:
    def __init__(
        self,
        settings: Settings,
        token_store: GoogleTokenStore | None = None,
        state_store: SecureJsonStore | None = None,
    ) -> None:
        self.settings = settings
        self.token_store = token_store or GoogleTokenStore(settings.google_token_path)
        self.state_store = state_store or SecureJsonStore(settings.google_oauth_state_path)

    @property
    def configured(self) -> bool:
        return bool(self.settings.google_client_id and self.settings.google_client_secret)

    def connection_status(self) -> dict[str, Any]:
        legacy_connected = bool(
            self.settings.google_access_token or self.settings.google_refresh_token
        )
        return {
            "oauth_configured": self.configured,
            "gmail_connected": legacy_connected
            or self.token_store.has_scope(GMAIL_READONLY_SCOPE),
            "calendar_connected": legacy_connected
            or self.token_store.has_scope(CALENDAR_READONLY_SCOPE),
            "gmail_send_enabled": self.token_store.has_scope(GMAIL_SEND_SCOPE),
            "calendar_write_enabled": self.token_store.has_scope(CALENDAR_EVENTS_SCOPE),
            "read_only": True,
        }

    def authorization_url(self, redirect_uri: str) -> str:
        if not self.configured:
            raise GoogleOAuthError(
                "Google OAuth is not configured. Add GOOGLE_CLIENT_ID and "
                "GOOGLE_CLIENT_SECRET to .env."
            )

        state = secrets.token_urlsafe(32)
        self.state_store.save(
            {
                "state": state,
                "redirect_uri": redirect_uri,
                "expires_at": (
                    datetime.now(timezone.utc) + timedelta(minutes=10)
                ).isoformat(),
            }
        )
        query = urlencode(
            {
                "client_id": self.settings.google_client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": " ".join(self._requested_scopes()),
                "access_type": "offline",
                "include_granted_scopes": "true",
                "prompt": "consent",
                "state": state,
            }
        )
        return f"{GOOGLE_AUTHORIZATION_URL}?{query}"

    def complete(self, *, code: str, state: str, error: str = "") -> dict[str, Any]:
        pending = self._consume_state(state)
        if error:
            raise GoogleOAuthError(f"Google authorization was not completed: {error}")
        if not code:
            raise GoogleOAuthError("Google OAuth callback did not include an authorization code.")

        try:
            response = request_json(
                GOOGLE_TOKEN_URL,
                method="POST",
                form={
                    "code": code,
                    "client_id": self.settings.google_client_id,
                    "client_secret": self.settings.google_client_secret,
                    "redirect_uri": str(pending["redirect_uri"]),
                    "grant_type": "authorization_code",
                },
                timeout=25,
            )
        except HttpError as exc:
            raise GoogleOAuthError(
                "Google rejected the OAuth token exchange. Check the OAuth client, "
                "redirect URI, consent screen, and enabled APIs."
            ) from exc

        if not response.get("access_token"):
            raise GoogleOAuthError("Google OAuth completed without an access token.")
        if not response.get("scope"):
            response["scope"] = " ".join(self._requested_scopes())
        self.token_store.save_token_response(response)
        return self.connection_status()

    def disconnect(self) -> None:
        self.token_store.clear()

    def _consume_state(self, received_state: str) -> dict[str, Any]:
        pending = self.state_store.load()
        self.state_store.clear()
        if not pending or not received_state:
            raise GoogleOAuthError("Google OAuth state is missing or expired. Start the connection again.")
        if not secrets.compare_digest(str(pending.get("state", "")), received_state):
            raise GoogleOAuthError("Google OAuth state validation failed. Start the connection again.")
        try:
            expires_at = _parse_datetime(str(pending.get("expires_at", "")))
        except ValueError as exc:
            raise GoogleOAuthError("Google OAuth state is invalid. Start the connection again.") from exc
        if expires_at <= datetime.now(timezone.utc):
            raise GoogleOAuthError("Google OAuth state expired. Start the connection again.")
        return pending

    def _requested_scopes(self) -> tuple[str, ...]:
        if not self.settings.google_enable_write_actions:
            return GOOGLE_READONLY_SCOPES
        return (
            GMAIL_READONLY_SCOPE,
            CALENDAR_READONLY_SCOPE,
            GMAIL_SEND_SCOPE,
            CALENDAR_EVENTS_SCOPE,
        )


def _parse_datetime(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _restrict_permissions(path: Path) -> None:
    try:
        os.chmod(path, 0o600)
    except OSError:
        # Windows ACLs are controlled by the user profile; the file remains
        # server-side and is excluded from version control.
        pass


def _scope_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return [item for item in str(value).split() if item]
