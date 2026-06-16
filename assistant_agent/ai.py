from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .config import Settings
from .http_client import HttpError, request_json
from .models import EmailItem


@dataclass
class EmailAnalysis:
    priority: str
    requires_response: bool
    summary: str
    draft_reply: str


class OpenAIAnalyzer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(self.settings.openai_api_key and self.settings.openai_model)

    def analyze_email(self, email: EmailItem) -> EmailAnalysis | None:
        if not self.configured:
            return None

        prompt = {
            "subject": email.subject,
            "sender": email.sender,
            "received_at": email.received_at,
            "snippet": email.snippet,
            "body": email.body[:4000],
        }
        instructions = (
            "You are a native Hebrew executive assistant. Classify the email "
            "as urgent, important, routine, or fyi. Return compact JSON only "
            "with keys: priority, requires_response, summary, draft_reply. "
            "The summary and draft_reply must be in professional, warm, business Hebrew. "
            "Avoid literal translations and robotic phrasing. Draft replies must be polite, "
            "concise, ready for human approval, and must not claim that an email was sent "
            "or a calendar change was made."
        )

        try:
            response = request_json(
                "https://api.openai.com/v1/responses",
                method="POST",
                headers={
                    "Authorization": f"Bearer {self.settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                body={
                    "model": self.settings.openai_model,
                    "input": [
                        {"role": "system", "content": instructions},
                        {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                    ],
                    "text": {"format": {"type": "json_object"}},
                },
                timeout=25,
            )
        except HttpError:
            return None

        text = _response_text(response)
        if not text:
            return None

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return None

        priority = str(payload.get("priority", "routine")).lower()
        if priority not in {"urgent", "important", "routine", "fyi"}:
            priority = "routine"

        return EmailAnalysis(
            priority=priority,
            requires_response=bool(payload.get("requires_response")),
            summary=str(payload.get("summary", "")).strip(),
            draft_reply=str(payload.get("draft_reply", "")).strip(),
        )


def _response_text(response: Any) -> str:
    if isinstance(response, dict):
        text = response.get("output_text")
        if isinstance(text, str):
            return text.strip()
        for item in response.get("output", []):
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"}:
                    value = content.get("text")
                    if isinstance(value, str):
                        return value.strip()
    return ""
