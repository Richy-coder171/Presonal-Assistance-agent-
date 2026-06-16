from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .models import ApprovalItem, CalendarEvent, EmailItem, TaskItem, now_iso


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
            id="demo_email_urgent_ops_blocker",
            subject="בהול: תקלה במשלוח ללקוח VIP",
            sender="מאיה אברמוב <operations@nofit.co.il>",
            received_at=(now - timedelta(minutes=48)).isoformat(),
            snippet="המשלוח ללקוח VIP חסום במחסן וצריך החלטה מיידית לגבי חלופה.",
            body=(
                "יש תקלה במשלוח ללקוח VIP. החבילה חסומה במחסן בגלל חוסר במסמך שילוח, "
                "והלקוח ביקש עדכון מיידי. אפשר לאשר חלופת שליחה עם שליח פרטי?"
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
            id="demo_email_important_legal",
            subject="טיוטת חוזה לשותפות - דרוש מעבר לפני פגישה",
            sender="עו״ד נועה שפיר <legal@nofit.co.il>",
            received_at=(now - timedelta(hours=1, minutes=55)).isoformat(),
            snippet="שלחתי טיוטת חוזה מעודכנת, כדאי לעבור עליה לפני פגישת ההנהלה.",
            body=(
                "מצורפת טיוטת חוזה מעודכנת לשותפות. יש שני סעיפים מסחריים שכדאי לאשר "
                "לפני פגישת ההנהלה: תנאי תשלום וסעיף יציאה."
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
            id="demo_email_routine_travel",
            subject="Travel options for Haifa site visit",
            sender="Michal Travel Desk <travel@nofit.co.il>",
            received_at=(now - timedelta(hours=4, minutes=10)).isoformat(),
            snippet="Two train options and one car option are available for next week's site visit.",
            body=(
                "For next week's Haifa site visit, there are two train options and one car option. "
                "Please let me know which one is preferred when convenient."
            ),
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
        EmailItem(
            id="demo_email_fyi_bank",
            subject="FYI: Monthly bank statement is available",
            sender="no-reply@bank.example",
            received_at=(now - timedelta(hours=8, minutes=20)).isoformat(),
            snippet="Your monthly statement is available. This is an automatic notification.",
            body="FYI only. No action required.",
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
        TaskItem(
            id="demo_task_ops_blocker",
            title="להחליט על חלופת שילוח ללקוח VIP",
            notes="להחזיר תשובה לתפעול וללקוח לפני סיום הבוקר.",
            due_at=now.replace(hour=11, minute=30, second=0, microsecond=0).isoformat(),
            priority="urgent",
            source="demo",
        ),
        TaskItem(
            id="demo_task_legal_review",
            title="לעבור על סעיפי חוזה השותפות",
            notes="תנאי תשלום וסעיף יציאה לפני פגישת הנהלה.",
            due_at=now.replace(hour=14, minute=30, second=0, microsecond=0).isoformat(),
            priority="important",
            source="demo",
        ),
    ]


def sample_approvals(timezone: str, briefing_id: str = "") -> list[ApprovalItem]:
    now = datetime.now(ZoneInfo(timezone))
    focus_start = now.replace(hour=13, minute=0, second=0, microsecond=0)
    focus_end = focus_start + timedelta(hours=1, minutes=30)
    return [
        ApprovalItem(
            id="demo_approval_send_briefing",
            action_type="send_briefing",
            title="Send daily briefing",
            description="Demo approval: send the Hebrew morning briefing to the configured channel.",
            payload={"source": "demo", "briefing_id": briefing_id},
            risk="external_message",
        ),
        ApprovalItem(
            id="demo_approval_email_reply",
            action_type="send_email",
            title="Approve client email draft",
            description="Demo approval: send a drafted Hebrew reply about the price proposal.",
            payload={
                "source": "demo",
                "provider": "google",
                "to": "dana.levi@nofit.co.il",
                "subject": "אישור הצעת מחיר",
                "body": "שלום דנה,\n\nקיבלתי את הבקשה ואעדכן לאחר בדיקה סופית.\n\nבברכה,\nהעוזר האישי",
            },
            risk="external_email",
        ),
        ApprovalItem(
            id="demo_approval_focus_time",
            action_type="create_focus_time",
            title="Create protected focus time",
            description="Demo approval: block focused work time for board materials.",
            payload={
                "source": "demo",
                "provider": "google",
                "title": "חלון מיקוד - הכנת חומרים לדירקטוריון",
                "start": focus_start.isoformat(),
                "end": focus_end.isoformat(),
                "description": "זמן מוגן לעבודה אסטרטגית לפני פגישת הנהלה.",
            },
            risk="calendar_write",
        ),
        ApprovalItem(
            id="demo_approval_reminder",
            action_type="send_reminder",
            title="Send meeting reminder",
            description="Demo approval: remind participants to review prep materials before the client call.",
            payload={
                "source": "demo",
                "text": "תזכורת: נא לעבור על הצעת המחיר והערות הלקוח לפני השיחה.",
            },
            risk="external_message",
        ),
    ]
