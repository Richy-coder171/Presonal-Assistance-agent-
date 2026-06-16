from __future__ import annotations

from datetime import datetime
from email.message import EmailMessage
from html import unescape
from typing import Any
from urllib.parse import urlencode

from ..config import Settings
from ..http_client import request_json
from ..microsoft_oauth import (
    MS_CALENDAR_READ,
    MS_CALENDAR_WRITE,
    MS_MAIL_READ,
    MS_MAIL_SEND,
    MicrosoftTokenStore,
)
from ..models import CalendarEvent, EmailItem, now_iso
from .base import CalendarProvider, EmailProvider


GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class Microsoft365Provider(EmailProvider, CalendarProvider):
    name = "Microsoft 365"

    def __init__(self, settings: Settings, token_store: MicrosoftTokenStore | None = None) -> None:
        self.settings = settings
        self.token_store = token_store or MicrosoftTokenStore(settings.ms_token_path)

    @property
    def configured(self) -> bool:
        return bool(
            self.settings.ms_graph_access_token
            or self.token_store.connected()
            or (
                self.settings.ms_client_id
                and self.settings.ms_client_secret
                and self.settings.ms_refresh_token
            )
        )

    @property
    def mail_connected(self) -> bool:
        return bool(
            self.settings.ms_graph_access_token
            or self.settings.ms_refresh_token
            or self.token_store.has_scope(MS_MAIL_READ)
        )

    @property
    def calendar_connected(self) -> bool:
        return bool(
            self.settings.ms_graph_access_token
            or self.settings.ms_refresh_token
            or self.token_store.has_scope(MS_CALENDAR_READ)
        )

    @property
    def can_send_email(self) -> bool:
        return bool(self.settings.ms_graph_access_token or self.token_store.has_scope(MS_MAIL_SEND))

    @property
    def can_write_calendar(self) -> bool:
        return bool(self.settings.ms_graph_access_token or self.token_store.has_scope(MS_CALENDAR_WRITE))

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

    def send_email(self, to: str, subject: str, body: str) -> dict:
        if not self.can_send_email:
            raise RuntimeError("Microsoft Mail.Send scope is not connected.")
        request_json(
            f"{GRAPH_BASE}/me/sendMail",
            method="POST",
            headers={"Authorization": f"Bearer {self._token()}"},
            body={
                "message": {
                    "subject": subject,
                    "body": {"contentType": "Text", "content": body},
                    "toRecipients": [
                        {"emailAddress": {"address": to}},
                    ],
                },
                "saveToSentItems": True,
            },
        )
        return {"sent": True, "to": to}

    def create_event(self, payload: dict[str, Any]) -> dict:
        if not self.can_write_calendar:
            raise RuntimeError("Microsoft Calendars.ReadWrite scope is not connected.")
        return request_json(
            f"{GRAPH_BASE}/me/events",
            method="POST",
            headers={"Authorization": f"Bearer {self._token()}"},
            body=_graph_event_payload(payload),
        )

    def update_event(self, event_id: str, payload: dict[str, Any]) -> dict:
        if not self.can_write_calendar:
            raise RuntimeError("Microsoft Calendars.ReadWrite scope is not connected.")
        return request_json(
            f"{GRAPH_BASE}/me/events/{event_id}",
            method="PATCH",
            headers={"Authorization": f"Bearer {self._token()}"},
            body=_graph_event_payload(payload),
        )

    def delete_event(self, event_id: str) -> dict:
        if not self.can_write_calendar:
            raise RuntimeError("Microsoft Calendars.ReadWrite scope is not connected.")
        request_json(
            f"{GRAPH_BASE}/me/events/{event_id}",
            method="DELETE",
            headers={"Authorization": f"Bearer {self._token()}"},
        )
        return {"deleted": event_id}

    def _token(self) -> str:
        if self.settings.ms_graph_access_token:
            return self.settings.ms_graph_access_token

        stored_access_token = self.token_store.valid_access_token()
        if stored_access_token:
            return stored_access_token

        tenant = self.settings.ms_tenant_id or "common"
        refresh_token = self.token_store.refresh_token() or self.settings.ms_refresh_token
        if not refresh_token:
            raise RuntimeError("Microsoft account is not connected.")
        payload = request_json(
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            method="POST",
            form={
                "client_id": self.settings.ms_client_id,
                "client_secret": self.settings.ms_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "scope": " ".join(self.token_store.scopes() or {"offline_access", "Mail.Read", "Calendars.Read"}),
            },
        )
        self.token_store.save_token_response(payload)
        return payload["access_token"]


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


def _graph_event_payload(payload: dict[str, Any]) -> dict[str, Any]:
    event = {
        "subject": payload.get("title") or payload.get("subject") or "Focus time",
        "body": {"contentType": "Text", "content": payload.get("description", "")},
        "location": {"displayName": payload.get("location", "")},
    }
    if payload.get("start"):
        event["start"] = {"dateTime": payload["start"], "timeZone": "UTC"}
    if payload.get("end"):
        event["end"] = {"dateTime": payload["end"], "timeZone": "UTC"}
    attendees = payload.get("attendees") or []
    if attendees:
        event["attendees"] = [
            {
                "emailAddress": {"address": email},
                "type": "required",
            }
            for email in attendees
        ]
    return event
