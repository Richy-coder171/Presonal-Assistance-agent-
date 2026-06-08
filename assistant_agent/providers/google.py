from __future__ import annotations

import base64
import email.utils
from datetime import datetime
from typing import Any
from urllib.parse import quote, urlencode

from ..config import Settings
from ..google_oauth import (
    CALENDAR_READONLY_SCOPE,
    GMAIL_READONLY_SCOPE,
    GOOGLE_TOKEN_URL,
    GoogleTokenStore,
)
from ..http_client import request_json
from ..models import CalendarEvent, EmailItem, now_iso
from .base import CalendarProvider, EmailProvider


class GoogleWorkspaceProvider(EmailProvider, CalendarProvider):
    name = "Google Workspace"

    def __init__(self, settings: Settings, token_store: GoogleTokenStore | None = None) -> None:
        self.settings = settings
        self.token_store = token_store or GoogleTokenStore(settings.google_token_path)

    @property
    def configured(self) -> bool:
        return bool(
            self.settings.google_access_token
            or self.token_store.connected()
            or (
                self.settings.google_client_id
                and self.settings.google_client_secret
                and self.settings.google_refresh_token
            )
        )

    @property
    def gmail_connected(self) -> bool:
        return bool(
            self.settings.google_access_token
            or self.settings.google_refresh_token
            or self.token_store.has_scope(GMAIL_READONLY_SCOPE)
        )

    @property
    def calendar_connected(self) -> bool:
        return bool(
            self.settings.google_access_token
            or self.settings.google_refresh_token
            or self.token_store.has_scope(CALENDAR_READONLY_SCOPE)
        )

    def list_recent_emails(self, limit: int = 25) -> list[EmailItem]:
        token = self._token()
        query = urlencode({"maxResults": str(limit), "q": "newer_than:7d in:inbox"})
        listing = request_json(
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages?{query}",
            headers={"Authorization": f"Bearer {token}"},
        )
        messages = listing.get("messages", [])
        emails: list[EmailItem] = []
        for message in messages:
            item = request_json(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message['id']}?format=full",
                headers={"Authorization": f"Bearer {token}"},
            )
            emails.append(_gmail_to_email(item))
        return emails

    def list_events(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        token = self._token()
        calendar_id = quote(self.settings.google_calendar_id or "primary", safe="")
        query = urlencode(
            {
                "timeMin": start.isoformat(),
                "timeMax": end.isoformat(),
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": "80",
            }
        )
        payload = request_json(
            f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events?{query}",
            headers={"Authorization": f"Bearer {token}"},
        )
        return [_google_event_to_model(event) for event in payload.get("items", [])]

    def _token(self) -> str:
        if self.settings.google_access_token:
            return self.settings.google_access_token

        stored_access_token = self.token_store.valid_access_token()
        if stored_access_token:
            return stored_access_token

        refresh_token = self.token_store.refresh_token() or self.settings.google_refresh_token
        if not refresh_token:
            raise RuntimeError("Google account is not connected.")

        payload = request_json(
            GOOGLE_TOKEN_URL,
            method="POST",
            form={
                "client_id": self.settings.google_client_id,
                "client_secret": self.settings.google_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        self.token_store.save_token_response(payload)
        return payload["access_token"]


def _gmail_to_email(data: dict[str, Any]) -> EmailItem:
    headers = {
        header.get("name", "").lower(): header.get("value", "")
        for header in data.get("payload", {}).get("headers", [])
    }
    received_at = now_iso()
    if headers.get("date"):
        try:
            parsed = email.utils.parsedate_to_datetime(headers["date"])
            received_at = parsed.isoformat()
        except (TypeError, ValueError):
            pass

    return EmailItem(
        id=f"gmail_{data.get('id', '')}",
        subject=headers.get("subject", "(no subject)"),
        sender=headers.get("from", ""),
        received_at=received_at,
        snippet=data.get("snippet", ""),
        body=_extract_gmail_body(data.get("payload", {})),
        labels=list(data.get("labelIds", [])),
        source="gmail",
    )


def _extract_gmail_body(payload: dict[str, Any]) -> str:
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return _decode_b64(payload["body"]["data"])
    for part in payload.get("parts", []) or []:
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            return _decode_b64(part["body"]["data"])
        nested = _extract_gmail_body(part)
        if nested:
            return nested
    return ""


def _decode_b64(value: str) -> str:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8", errors="replace")


def _google_event_to_model(data: dict[str, Any]) -> CalendarEvent:
    start = data.get("start", {}).get("dateTime") or data.get("start", {}).get("date") or now_iso()
    end = data.get("end", {}).get("dateTime") or data.get("end", {}).get("date") or start
    attendees = [item.get("email", "") for item in data.get("attendees", []) if item.get("email")]
    return CalendarEvent(
        id=f"gcal_{data.get('id', '')}",
        title=data.get("summary", "(busy)"),
        start=start,
        end=end,
        source="google_calendar",
        attendees=attendees,
        location=data.get("location", ""),
        description=data.get("description", ""),
    )
