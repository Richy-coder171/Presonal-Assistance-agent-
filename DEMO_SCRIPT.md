# Personal Assistant Agent Demo Script

Use this as a 1-2 minute video script for a client demo.

## Opening

"This is a Hebrew-first Personal Assistant Agent MVP for daily email management, calendar coordination, task tracking, and morning briefings. It runs safely in demo mode, so I can show the full workflow without connecting a real inbox."

## Step-by-Step Talking Points

1. Dashboard overview
   "The dashboard gives one executive view: inbox priorities, calendar, tasks, daily briefing, approvals, and analytics."

2. Connection status
   "This panel shows which providers are connected: Gmail, Google Calendar, Outlook, Microsoft Calendar, OpenAI, Slack, and WhatsApp. OAuth tokens are stored on the server, not in the frontend."

3. Email triage
   "The assistant reviews incoming emails and classifies them as urgent, important, routine, or FYI. In this demo, we have urgent client approval, important payment and board-prep items, a routine delivery request, and an FYI market update."

4. Hebrew reply drafts
   "For emails that need a response, the assistant prepares a polite Hebrew draft. The draft is ready for review, but it is not sent automatically."

5. Daily briefing
   "The morning briefing summarizes urgent items, important follow-ups, the day calendar, conflicts, open tasks, and a practical recommendation."

6. Calendar conflicts
   "The calendar detects overlapping meetings. Here, the management sync conflicts with a client review call, so the user knows what needs attention before the day starts."

7. Task tracking
   "Important emails can become follow-up tasks with priorities and due dates, so the assistant does not only summarize work; it helps organize execution."

8. Approval queue
   "Any risky action, such as sending an email, sending a WhatsApp or Slack update, creating focus time, or rescheduling a meeting, goes into the approval queue. Nothing external happens until the user approves it."

9. Analytics
   "The analytics panel shows response workload, calendar conflicts, focus blocks, and open tasks. These are the operational signals a busy executive assistant needs."

## Hebrew Sample Briefing

```text
בוקר טוב, הנה הדוח היומי לתאריך 16/06/2026.
ריכזתי את הנושאים שדורשים תשומת לב, לצד היומן והמשימות הפתוחות.

עדיפויות דחופות: 1
- דנה לוי: דחוף: אישור סופי להצעת המחיר ללקוח היום - צריך אישור עד 12:00 כדי לשלוח את ההצעה המעודכנת ללקוח.

פריטים חשובים למעקב: 2
- רועי בן דוד: אישור תשלום לספק - חשבונית יוני - מצורפת חשבונית מספק הלוגיסטיקה, נשמח לאישור לפני 15:00.
- Amit Cohen: Board prep: Q3 KPI deck for review - Please review the KPI deck before the management sync.

קונפליקטים ביומן: 1
- ישיבת הנהלה שבועית מול שיחת לקוח אסטרטגי - הצעת מחיר

המלצה: להתחיל בפריטים הדחופים, לפתור קונפליקטים ביומן לפני תחילת הפגישות, ולשמור חלון מיקוד אחד לעבודה אסטרטגית.
```

## Closing

"This MVP proves the core assistant workflow end to end: email triage, Hebrew communication, calendar awareness, task organization, daily briefings, provider integrations, and human approval before any external action."
