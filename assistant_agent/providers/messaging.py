from __future__ import annotations

from ..config import Settings
from ..http_client import request_json
from .base import Messenger


class SlackMessenger(Messenger):
    name = "Slack"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(self.settings.slack_webhook_url)

    def send(self, text: str) -> dict:
        request_json(self.settings.slack_webhook_url, method="POST", body={"text": text})
        return {"channel": self.name, "status": "sent"}


class WhatsAppMessenger(Messenger):
    name = "WhatsApp"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(
            self.settings.whatsapp_access_token
            and self.settings.whatsapp_phone_number_id
            and self.settings.whatsapp_to
        )

    def send(self, text: str) -> dict:
        url = (
            "https://graph.facebook.com/v19.0/"
            f"{self.settings.whatsapp_phone_number_id}/messages"
        )
        request_json(
            url,
            method="POST",
            headers={"Authorization": f"Bearer {self.settings.whatsapp_access_token}"},
            body={
                "messaging_product": "whatsapp",
                "to": self.settings.whatsapp_to,
                "type": "text",
                "text": {"preview_url": False, "body": text},
            },
        )
        return {"channel": self.name, "status": "sent"}


class CompositeMessenger(Messenger):
    name = "Composite"

    def __init__(self, messengers: list[Messenger]) -> None:
        self.messengers = messengers

    @property
    def configured(self) -> bool:
        return any(messenger.configured for messenger in self.messengers)

    def send(self, text: str) -> dict:
        results = []
        errors = []
        for messenger in self.messengers:
            if not messenger.configured:
                continue
            try:
                results.append(messenger.send(text))
            except Exception as exc:  # noqa: BLE001 - surfaced to the dashboard.
                errors.append({"channel": messenger.name, "error": str(exc)})
        return {"sent": results, "errors": errors}

