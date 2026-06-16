from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .models import CalendarEvent, EmailItem, TaskItem, now_iso


def sample_emails(timezone: str) -> list[EmailItem]:
    now = datetime.now(ZoneInfo(timezone))
    return [
        EmailItem(
            id="demo_email_urgent_nofit_quote",
            subject="דחוף: אישור סופי להצעת המחיר ללקוח היום",
            sender="דנה לוי <dana.levi@nofit.co.il>",
            received_at=(now - timedelta(minutes=22)).isoformat(),
            snippet="צריך אישור עד 12:00 כדי לשלוח את ההצעה המעודכנת ללקוח.",
            body=(
                "היי, אפשר לאשר את הצעת המחיר המעודכנת עד 12:00? "
                "הלקוח מחכה לתשובה היום, ואם נאשר בזמן נוכל להוציא הזמנה לפני סוף היום."
            ),
            source="demo",
        ),
        EmailItem(
            id="demo_email_important_payment",
            subject="אישור תשלום לספק - חשבונית יוני",
            sender="רועי בן דוד <finance@nofit.co.il>",
            received_at=(now - timedelta(hours=1, minutes=15)).isoformat(),
            snippet="מצורפת חשבונית מספק הלוגיסטיקה, נשמח לאישור לפני 15:00.",
            body=(
                "מצורפת חשבונית מספק הלוגיסטיקה עבור חודש יוני. "
                "נשמח לאישור לפני 15:00 כדי להכניס את התשלום למחזור התשלומים הקרוב."
            ),
            source="demo",
        ),
        EmailItem(
            id="demo_email_important_board_deck",
            subject="Board prep: Q3 KPI deck for review",
            sender="Amit Cohen <amit.cohen@nofit.co.il>",
            received_at=(now - timedelta(hours=2, minutes=20)).isoformat(),
            snippet="Please review the KPI deck before the management sync.",
            body=(
                "Please review the Q3 KPI deck before the management sync. "
                "The CEO asked for comments on revenue, churn, and operations risks by 16:00."
            ),
            source="demo",
        ),
        EmailItem(
            id="demo_email_routine_delivery",
            subject="Office supplies delivery window",
            sender="Tal Office Supplies <service@tal-office.co.il>",
            received_at=(now - timedelta(hours=3, minutes=5)).isoformat(),
            snippet="Could you confirm whether 14:00-16:00 works for delivery tomorrow?",
            body="Could you confirm whether 14:00-16:00 works for delivery tomorrow? No urgency.",
            source="demo",
        ),
        EmailItem(
            id="demo_email_newsletter",
            subject="עדכון שבועי: חדשות שוק ורגולציה",
            sender="no-reply@industrynews.co.il",
            received_at=(now - timedelta(hours=6, minutes=30)).isoformat(),
            snippet="לידיעה בלבד: סיכום קצר של עדכוני שוק ורגולציה רלוונטיים.",
            body="לידיעה בלבד. אין צורך בפעולה.",
            source="demo",
        ),
    ]


def sample_events(timezone: str) -> list[CalendarEvent]:
    now = datetime.now(ZoneInfo(timezone))
    base = now.replace(hour=9, minute=0, second=0, microsecond=0)
    return [
        CalendarEvent(
            id="demo_event_management_sync",
            title="ישיבת הנהלה שבועית",
            start=base.isoformat(),
            end=(base + timedelta(hours=1)).isoformat(),
            attendees=["ceo@nofit.co.il", "ops@nofit.co.il", "finance@nofit.co.il"],
            location="Zoom",
            description="סקירת KPI, סיכוני תפעול והחלטות להמשך השבוע.",
            source="demo",
        ),
        CalendarEvent(
            id="demo_event_client_review",
            title="שיחת לקוח אסטרטגי - הצעת מחיר",
            start=(base + timedelta(minutes=30)).isoformat(),
            end=(base + timedelta(hours=1, minutes=15)).isoformat(),
            attendees=["dana.levi@nofit.co.il", "client@example.com"],
            location="Google Meet",
            description="שיחה להכנת הצעת מחיר סופית ולוחות זמנים לאישור.",
            source="demo",
        ),
        CalendarEvent(
            id="demo_event_vendor_payment",
            title="אישור תשלום מול ספק לוגיסטיקה",
            start=(base + timedelta(hours=2)).isoformat(),
            end=(base + timedelta(hours=2, minutes=30)).isoformat(),
            attendees=["finance@nofit.co.il", "vendor@example.com"],
            location="Microsoft Teams",
            description="בדיקת חשבונית, תנאי תשלום ואישור להמשך טיפול.",
            source="demo",
        ),
        CalendarEvent(
            id="demo_event_focus",
            title="חלון מיקוד - הכנת חומרים לדירקטוריון",
            start=(base + timedelta(hours=3)).isoformat(),
            end=(base + timedelta(hours=4, minutes=30)).isoformat(),
            attendees=[],
            location="Office",
            description="זמן מוגן לעבודה אסטרטגית ללא פגישות.",
            source="demo",
        ),
        CalendarEvent(
            id="demo_event_preparation",
            title="הכנת חומרי רקע לפגישת לקוח",
            start=(base + timedelta(hours=5)).isoformat(),
            end=(base + timedelta(hours=5, minutes=45)).isoformat(),
            attendees=["assistant@nofit.co.il"],
            location="Office",
            source="demo",
        ),
    ]


def sample_tasks(timezone: str) -> list[TaskItem]:
    now = datetime.now(ZoneInfo(timezone))
    return [
        TaskItem(
            id="demo_task_quote",
            title="לאשר הצעת מחיר מעודכנת ללקוח אסטרטגי",
            notes="נדרש לפני 12:00 כדי לא לעכב הזמנה.",
            due_at=now.replace(hour=12, minute=0, second=0, microsecond=0).isoformat(),
            priority="urgent",
            source="demo",
        ),
        TaskItem(
            id="demo_task_payment",
            title="לאשר תשלום לספק לוגיסטיקה",
            notes="לבדוק התאמה לחשבונית ולסגור מול הנהלת חשבונות.",
            due_at=now.replace(hour=15, minute=0, second=0, microsecond=0).isoformat(),
            priority="important",
            source="demo",
        ),
        TaskItem(
            id="demo_task_board_pack",
            title="לעבור על מצגת KPI לדירקטוריון",
            notes="להוסיף הערות על הכנסות, נטישה וסיכוני תפעול.",
            due_at=now.replace(hour=16, minute=0, second=0, microsecond=0).isoformat(),
            priority="important",
            source="demo",
        ),
        TaskItem(
            id="demo_task_delivery",
            title="לאשר חלון משלוח לציוד משרדי",
            notes="בדיקה אם חלון 14:00-16:00 מתאים למחר.",
            due_at=(now + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat(),
            priority="routine",
            source="demo",
        ),
    ]
