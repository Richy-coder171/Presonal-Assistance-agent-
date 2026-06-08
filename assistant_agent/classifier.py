from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from .models import CalendarEvent, EmailItem, TaskItem

URGENT_TERMS = {
    "urgent",
    "asap",
    "immediately",
    "today",
    "deadline",
    "blocked",
    "production",
    "דחוף",
    "בהול",
    "מיידי",
    "היום",
    "תקלה",
    "חסום",
    "אישור דחוף",
}

IMPORTANT_TERMS = {
    "contract",
    "invoice",
    "payment",
    "approval",
    "proposal",
    "client",
    "meeting",
    "board",
    "budget",
    "חוזה",
    "חשבונית",
    "תשלום",
    "אישור",
    "לקוח",
    "פגישה",
    "תקציב",
    "הצעה",
}

FYI_TERMS = {
    "newsletter",
    "digest",
    "fyi",
    "receipt",
    "no-reply",
    "noreply",
    "עדכון",
    "ניוזלטר",
    "לידיעה",
    "קבלה",
}

RESPONSE_TERMS = {
    "please reply",
    "can you",
    "could you",
    "approve",
    "confirm",
    "schedule",
    "let me know",
    "אשמח",
    "אפשר",
    "תוכל",
    "תוכלי",
    "לאשר",
    "לקבוע",
    "לעדכן",
    "להחזיר תשובה",
}

PRIORITY_LABELS = {
    "urgent": "דחוף",
    "important": "חשוב",
    "routine": "שגרתי",
    "fyi": "לידיעה",
}


def classify_email(email: EmailItem) -> tuple[str, bool]:
    text = _normalize(f"{email.sender} {email.subject} {email.snippet} {email.body}")
    urgent_score = _count_terms(text, URGENT_TERMS)
    important_score = _count_terms(text, IMPORTANT_TERMS)
    fyi_score = _count_terms(text, FYI_TERMS)
    response_score = _count_terms(text, RESPONSE_TERMS)

    if urgent_score >= 1:
        priority = "urgent"
    elif important_score >= 1:
        priority = "important"
    elif fyi_score >= 1 and response_score == 0:
        priority = "fyi"
    else:
        priority = "routine"

    requires_response = response_score > 0 or priority in {"urgent", "important"}
    if "no-reply" in text or "noreply" in text:
        requires_response = False
    return priority, requires_response


def summarize_email(email: EmailItem) -> str:
    subject = email.subject.strip() or "ללא נושא"
    sender = readable_sender(email.sender)
    snippet = re.sub(r"\s+", " ", email.snippet or email.body).strip()
    if len(snippet) > 170:
        snippet = snippet[:167].rstrip() + "..."
    if snippet:
        return f"{sender}: {subject} - {snippet}"
    return f"{sender}: {subject}"


def draft_hebrew_reply(email: EmailItem, priority: str) -> str:
    sender = readable_sender(email.sender)
    subject = email.subject.strip() or "הפנייה"

    if priority == "urgent":
        body = (
            "תודה על העדכון. קיבלתי את הנושא הדחוף ואבדוק אותו בעדיפות גבוהה. "
            "אעדכן בהקדם עם סטטוס והצעדים הבאים."
        )
    elif "meeting" in _normalize(subject) or "פגישה" in subject:
        body = (
            "תודה, קיבלתי את הבקשה לתיאום. אבדוק את היומן ואחזור עם חלונות זמן מתאימים."
        )
    elif priority == "important":
        body = (
            "תודה על ההודעה. קיבלתי את הפרטים ואעבור עליהם היום. "
            "אם יש דדליין מסוים, אשמח לדעת כדי לתעדף נכון."
        )
    else:
        body = "תודה על ההודעה. קיבלתי ואחזור עם מענה מסודר בהקדם."

    return f"שלום {sender},\n\n{body}\n\nבברכה"


def detect_conflicts(events: list[CalendarEvent]) -> list[dict]:
    conflicts: list[dict] = []
    parsed = sorted(
        ((event, _parse_dt(event.start), _parse_dt(event.end)) for event in events),
        key=lambda item: item[1],
    )
    for index, (current, current_start, current_end) in enumerate(parsed):
        for other, other_start, other_end in parsed[index + 1 :]:
            if other_start >= current_end:
                break
            if current_start < other_end and other_start < current_end:
                conflicts.append(
                    {
                        "event_ids": [current.id, other.id],
                        "titles": [current.title, other.title],
                        "start": max(current_start, other_start).isoformat(),
                        "end": min(current_end, other_end).isoformat(),
                    }
                )
    return conflicts


def build_briefing_text(
    emails: list[EmailItem],
    events: list[CalendarEvent],
    tasks: list[TaskItem],
    conflicts: list[dict],
    timezone: str,
) -> str:
    now = datetime.now(ZoneInfo(timezone))
    urgent = [item for item in emails if item.priority == "urgent"]
    important = [item for item in emails if item.priority == "important"]
    open_tasks = [task for task in tasks if task.status != "done"]
    todays_events = [event for event in events if _is_today(event.start, timezone)]

    lines = [
        f"בוקר טוב. דוח יומי לתאריך {now.strftime('%d/%m/%Y')}.",
        "",
        f"פריטים דחופים: {len(urgent)}",
    ]
    lines.extend(f"- {summarize_email(item)}" for item in urgent[:5])

    lines.append("")
    lines.append(f"פריטים חשובים: {len(important)}")
    lines.extend(f"- {summarize_email(item)}" for item in important[:5])

    lines.append("")
    lines.append(f"יומן היום: {len(todays_events)} פגישות")
    for event in todays_events[:8]:
        lines.append(f"- {_format_time(event.start, timezone)}-{_format_time(event.end, timezone)} {event.title}")

    lines.append("")
    if conflicts:
        lines.append(f"קונפליקטים ביומן: {len(conflicts)}")
        for conflict in conflicts[:4]:
            lines.append(f"- {' מול '.join(conflict['titles'])}")
    else:
        lines.append("קונפליקטים ביומן: אין")

    lines.append("")
    lines.append(f"משימות פתוחות: {len(open_tasks)}")
    for task in open_tasks[:6]:
        due = f" עד {_format_time(task.due_at, timezone)}" if task.due_at else ""
        lines.append(f"- {task.title}{due}")

    lines.append("")
    lines.append("המלצה: להתחיל בפריטים הדחופים, לשמור חלון מיקוד אחד, ולסגור תגובות קצרות לפני הצהריים.")
    return "\n".join(lines).strip()


def readable_sender(sender: str) -> str:
    sender = sender.strip()
    match = re.search(r"([^<]+)<", sender)
    if match:
        sender = match.group(1).strip().strip('"')
    if "@" in sender and not sender.startswith("<"):
        sender = sender.split("@", 1)[0]
    return sender or "שם"


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold())


def _count_terms(text: str, terms: set[str]) -> int:
    return sum(1 for term in terms if term.casefold() in text)


def _parse_dt(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _is_today(value: str, timezone: str) -> bool:
    dt = _parse_dt(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(timezone))
    return dt.astimezone(ZoneInfo(timezone)).date() == datetime.now(ZoneInfo(timezone)).date()


def _format_time(value: str | None, timezone: str) -> str:
    if not value:
        return ""
    dt = _parse_dt(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(timezone))
    return dt.astimezone(ZoneInfo(timezone)).strftime("%H:%M")

