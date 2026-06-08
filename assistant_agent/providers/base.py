from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from ..models import CalendarEvent, EmailItem


class EmailProvider(ABC):
    name: str

    @property
    @abstractmethod
    def configured(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def list_recent_emails(self, limit: int = 25) -> list[EmailItem]:
        raise NotImplementedError


class CalendarProvider(ABC):
    name: str

    @property
    @abstractmethod
    def configured(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def list_events(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        raise NotImplementedError


class Messenger(ABC):
    name: str

    @property
    @abstractmethod
    def configured(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def send(self, text: str) -> dict:
        raise NotImplementedError

