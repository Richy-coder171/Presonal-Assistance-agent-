from __future__ import annotations

from datetime import datetime
from html import unescape
from typing import Any
from urllib.parse import urlencode

from ..config import Settings
from ..http_client import request_json
from ..models import CalendarEvent, EmailItem, now_iso
from .base import CalendarProvider, EmailProvider


GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class Microsoft365Provider(EmailProvider, CalendarProvider):
    name = "Microsoft 365"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._access_token: str | None = None

    @property
    def configured(self) -> bool:
        return bool(
            self.settings.ms_graph_access_token
            or (
                self.settings.ms_client_id
                and self.settings.ms_client_secret
                and self.settings.ms_refresh_token
            )
        )

    def list_recent_emails(self, limit: int = 25) -> list[EmailItem]:
        token = self._token()
        query = urlencode(
            {
                "$top": str(limit),
                "$orderby": "receivedDateTime desc",
                "$select": "id,subject,from,receivedDateTime,bodyPreview,body,importance,isRead",
            }
        )
        payload = request_json(
            f"{GRAPH_BASE}/me/mailFolders/inbox/messages?{query}",
            headers={"Authorization": f"Bearer {token}"},
        )
        return [_message_to_email(item) for item in payload.get("value", [])]

    def list_events(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        token = self._token()
        query = urlencode(
            {
                "startDateTime": start.isoformat(),
                "endDateTime": end.isoformat(),
                "$top": "80",
                "$orderby": "start/dateTime",
                "$select": "id,subject,start,end,attendees,location,bodyPreview",
            }
        )
        payload = request_json(
            f"{GRAPH_BASE}/me/calendarView?{query}",
            headers={"Authorization": f"Bearer {token}", "Prefer": 'outlook.timezone="UTC"'},
        )
        return [_event_to_model(item) for item in payload.get("value", [])]

    def _token(self) -> str:
        if self._access_token:
            return self._access_token
        if self.settings.ms_graph_access_token:
            self._access_token = self.settings.ms_graph_access_token
            return self._access_token

        tenant = self.settings.ms_tenant_id or "common"
        payload = request_json(
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            method="POST",
            form={
                "client_id": self.settings.ms_client_id,
                "client_secret": self.settings.ms_client_secret,
                "refresh_token": self.settings.ms_refresh_token,
                "grant_type": "refresh_token",
                "scope": "offline_access Mail.Read Calendars.Read",
            },
        )
        self._access_token = payload["access_token"]
        return self._access_token


def _message_to_email(data: dict[str, Any]) -> EmailItem:
    sender = data.get("from", {}).get("emailAddress", {})
    body = data.get("body", {}).get("content", "")
    return EmailItem(
        id=f"outlook_{data.get('id', '')}",
        subject=data.get("subject", "(no subject)"),
        sender=sender.get("name") or sender.get("address", ""),
        received_at=data.get("receivedDateTime", now_iso()),
        snippet=data.get("bodyPreview", ""),
        body=_plain(body),
        source="outlook",
        labels=[data.get("importance", "normal")],
    )


def _event_to_model(data: dict[str, Any]) -> CalendarEvent:
    attendees = [
        item.get("emailAddress", {}).get("address", "")
        for item in data.get("attendees", [])
        if item.get("emailAddress", {}).get("address")
    ]
    location = data.get("location", {}).get("displayName", "")
    return CalendarEvent(
        id=f"outlook_cal_{data.get('id', '')}",
        title=data.get("subject", "(busy)"),
        start=data.get("start", {}).get("dateTime", now_iso()),
        end=data.get("end", {}).get("dateTime", now_iso()),
        source="outlook_calendar",
        attendees=attendees,
        location=location,
        description=data.get("bodyPreview", ""),
    )


def _plain(value: str) -> str:
    text = unescape(value)
    return text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")

