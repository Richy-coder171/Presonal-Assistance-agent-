from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

from .config import Settings
from .google_oauth import SecureJsonStore
from .http_client import HttpError, request_json


GRAPH_SCOPE_PREFIX = "https://graph.microsoft.com/"
MS_MAIL_READ = "Mail.Read"
MS_CALENDAR_READ = "Calendars.Read"
MS_MAIL_SEND = "Mail.Send"
MS_CALENDAR_WRITE = "Calendars.ReadWrite"
MS_BASE_SCOPES = ("offline_access", MS_MAIL_READ, MS_CALENDAR_READ)


class MicrosoftOAuthError(RuntimeError):
    """A user-facing Microsoft OAuth failure."""


class MicrosoftTokenStore(SecureJsonStore):
    def connected(self) -> bool:
        tokens = self.load()
        return bool(tokens.get("access_token") or tokens.get("refresh_token"))

    def has_scope(self, scope: str) -> bool:
        if not self.connected():
            return False
        return scope.casefold() in {item.casefold() for item in self.scopes()}

    def scopes(self) -> set[str]:
        value = self.load().get("scope", "")
        if isinstance(value, list):
            return {str(item).replace(GRAPH_SCOPE_PREFIX, "") for item in value}
        return {item.replace(GRAPH_SCOPE_PREFIX, "") for item in str(value).split()}

    def valid_access_token(self) -> str | None:
        tokens = self.load()
        access_token = str(tokens.get("access_token", "")).strip()
        if not access_token:
            return None
        expires_at = tokens.get("expires_at")
        if not expires_at:
            return access_token
        parsed = _parse_datetime(str(expires_at))
        if parsed <= datetime.now(timezone.utc) + timedelta(seconds=60):
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


class MicrosoftOAuthManager:
    def __init__(
        self,
        settings: Settings,
        token_store: MicrosoftTokenStore | None = None,
        state_store: SecureJsonStore | None = None,
    ) -> None:
        self.settings = settings
        self.token_store = token_store or MicrosoftTokenStore(settings.ms_token_path)
        self.state_store = state_store or SecureJsonStore(settings.ms_oauth_state_path)

    @property
    def configured(self) -> bool:
        return bool(self.settings.ms_client_id and self.settings.ms_client_secret)

    def connection_status(self) -> dict[str, Any]:
        legacy_connected = bool(
            self.settings.ms_graph_access_token or self.settings.ms_refresh_token
        )
        return {
            "oauth_configured": self.configured,
            "mail_connected": legacy_connected or self.token_store.has_scope(MS_MAIL_READ),
            "calendar_connected": legacy_connected or self.token_store.has_scope(MS_CALENDAR_READ),
            "mail_send_enabled": self.token_store.has_scope(MS_MAIL_SEND),
            "calendar_write_enabled": self.token_store.has_scope(MS_CALENDAR_WRITE),
        }

    def authorization_url(self, redirect_uri: str) -> str:
        if not self.configured:
            raise MicrosoftOAuthError(
                "Microsoft OAuth is not configured. Add MS_CLIENT_ID and "
                "MS_CLIENT_SECRET to .env."
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
        tenant = self.settings.ms_tenant_id or "common"
        query = urlencode(
            {
                "client_id": self.settings.ms_client_id,
                "response_type": "code",
                "redirect_uri": redirect_uri,
                "response_mode": "query",
                "scope": " ".join(self._requested_scopes()),
                "state": state,
                "prompt": "select_account",
            }
        )
        return f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize?{query}"

    def complete(self, *, code: str, state: str, error: str = "") -> dict[str, Any]:
        pending = self._consume_state(state)
        if error:
            raise MicrosoftOAuthError(f"Microsoft authorization was not completed: {error}")
        if not code:
            raise MicrosoftOAuthError("Microsoft OAuth callback did not include an authorization code.")
        tenant = self.settings.ms_tenant_id or "common"
        try:
            response = request_json(
                f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
                method="POST",
                form={
                    "client_id": self.settings.ms_client_id,
                    "client_secret": self.settings.ms_client_secret,
                    "code": code,
                    "redirect_uri": str(pending["redirect_uri"]),
                    "grant_type": "authorization_code",
                    "scope": " ".join(self._requested_scopes()),
                },
                timeout=25,
            )
        except HttpError as exc:
            raise MicrosoftOAuthError(
                "Microsoft rejected the OAuth token exchange. Check the app registration, "
                "redirect URI, client secret, and delegated permissions."
            ) from exc
        if not response.get("access_token"):
            raise MicrosoftOAuthError("Microsoft OAuth completed without an access token.")
        if not response.get("scope"):
            response["scope"] = " ".join(self._requested_scopes())
        self.token_store.save_token_response(response)
        return self.connection_status()

    def _requested_scopes(self) -> tuple[str, ...]:
        if not self.settings.ms_enable_write_actions:
            return MS_BASE_SCOPES
        return (*MS_BASE_SCOPES, MS_MAIL_SEND, MS_CALENDAR_WRITE)

    def _consume_state(self, received_state: str) -> dict[str, Any]:
        pending = self.state_store.load()
        self.state_store.clear()
        if not pending or not received_state:
            raise MicrosoftOAuthError("Microsoft OAuth state is missing or expired. Start the connection again.")
        if not secrets.compare_digest(str(pending.get("state", "")), received_state):
            raise MicrosoftOAuthError("Microsoft OAuth state validation failed. Start the connection again.")
        expires_at = _parse_datetime(str(pending.get("expires_at", "")))
        if expires_at <= datetime.now(timezone.utc):
            raise MicrosoftOAuthError("Microsoft OAuth state expired. Start the connection again.")
        return pending


def _parse_datetime(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
