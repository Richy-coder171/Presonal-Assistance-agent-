from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .models import CalendarEvent, EmailItem, TaskItem, now_iso


def sample_emails(timezone: str) -> list[EmailItem]:
    now = datetime.now(ZoneInfo(timezone))
    return [
        EmailItem(
            id="demo_email_urgent_client",
            subject="דחוף: אישור סופי להצעת המחיר היום",
            sender="Dana Levi <dana@example.com>",
            received_at=(now - timedelta(minutes=34)).isoformat(),
            snippet="צריך אישור עד 12:00 כדי להוציא הזמנה ללקוח.",
            body="היי, אפשר לאשר את ההצעה עד 12:00? הלקוח מחכה ומבקש תשובה היום.",
            source="demo",
        ),
        EmailItem(
            id="demo_email_meeting",
            subject="Meeting follow-up and next steps",
            sender="Amit Cohen <amit@example.com>",
            received_at=(now - timedelta(hours=2)).isoformat(),
            snippet="Can you confirm the action items and schedule the next review?",
            body="Can you confirm the action items and schedule the next review for next week?",
            source="demo",
        ),
        EmailItem(
            id="demo_email_invoice",
            subject="חשבונית לתשלום - מאי",
            sender="Finance <finance@example.com>",
            received_at=(now - timedelta(hours=4)).isoformat(),
            snippet="מצורפת חשבונית לתשלום עבור חודש מאי.",
            body="מצורפת חשבונית לתשלום. נשמח לאישור.",
            source="demo",
        ),
        EmailItem(
            id="demo_email_newsletter",
            subject="Weekly industry digest",
            sender="newsletter@example.com",
            received_at=(now - timedelta(hours=7)).isoformat(),
            snippet="A short weekly digest of product and market updates.",
            body="FYI only. No action required.",
            source="demo",
        ),
    ]


def sample_events(timezone: str) -> list[CalendarEvent]:
    now = datetime.now(ZoneInfo(timezone))
    base = now.replace(hour=9, minute=0, second=0, microsecond=0)
    return [
        CalendarEvent(
            id="demo_event_strategy",
            title="ישיבת אסטרטגיה",
            start=base.isoformat(),
            end=(base + timedelta(hours=1)).isoformat(),
            attendees=["ceo@example.com", "ops@example.com"],
            location="Zoom",
            source="demo",
        ),
        CalendarEvent(
            id="demo_event_client",
            title="שיחת לקוח - Nofit LTD",
            start=(base + timedelta(minutes=45)).isoformat(),
            end=(base + timedelta(hours=1, minutes=30)).isoformat(),
            attendees=["dana@example.com"],
            location="Google Meet",
            source="demo",
        ),
        CalendarEvent(
            id="demo_event_focus",
            title="Focus time",
            start=(base + timedelta(hours=2)).isoformat(),
            end=(base + timedelta(hours=3, minutes=30)).isoformat(),
            attendees=[],
            source="demo",
        ),
    ]


def sample_tasks(timezone: str) -> list[TaskItem]:
    now = datetime.now(ZoneInfo(timezone))
    return [
        TaskItem(
            id="demo_task_quote",
            title="לאשר הצעת מחיר ללקוח",
            notes="נדרש לפני הצהריים",
            due_at=now.replace(hour=12, minute=0, second=0, microsecond=0).isoformat(),
            priority="urgent",
            source="demo",
        ),
        TaskItem(
            id="demo_task_brief",
            title="לשלוח סיכום פגישת אסטרטגיה",
            due_at=now.replace(hour=15, minute=0, second=0, microsecond=0).isoformat(),
            priority="important",
            source="demo",
        ),
    ]

