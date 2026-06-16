# Personal Assistant Agent

Personal Assistant Agent is a Hebrew-first executive assistant MVP for daily email triage, calendar coordination, task tracking, scheduled morning briefings, analytics, and approval-gated communication workflows.

The project is designed for client demonstration immediately. It runs in demo mode without credentials, and it can connect to Gmail, Google Calendar, Outlook mail, and Outlook Calendar through server-side OAuth token storage when real accounts are configured.

## Project Overview

This MVP shows how an AI assistant can support an Israeli business user or executive team by reviewing incoming messages, identifying urgent work, drafting professional Hebrew responses, detecting calendar conflicts, organizing follow-up tasks, and preparing a clear daily briefing.

The app is intentionally safe by default. It can read real inbox and calendar data after OAuth connection, but actions that send messages or modify calendars are routed through a human approval queue.

## Client Demo Flow

Use this flow for a 1-2 minute client walkthrough:

1. Start the app and open the dashboard.
2. Load demo data to show a realistic Israeli executive-assistant inbox.
3. Show the connection status panel: Gmail, Google Calendar, Outlook, Outlook Calendar, OpenAI, Slack, and WhatsApp.
4. Open the inbox section and point out urgent, important, routine, and FYI classification.
5. Open a Hebrew draft reply and explain that replies are prepared for human approval, not sent automatically.
6. Generate or show the Daily Report / Morning Briefing in Hebrew.
7. Show the calendar section and the overlapping meeting conflict.
8. Show open tasks created from urgent and important emails.
9. Show the approval queue for risky actions such as sending a briefing, sending an email, creating focus time, rescheduling a meeting, or notifying participants.
10. Show analytics for response workload, calendar conflicts, focus blocks, and open tasks.

Use **Reset Demo** before recording or presenting. It reseeds demo-only emails, calendar events, tasks, approvals, analytics, and a fresh Hebrew briefing without removing real provider records.

Recommended demo command:

```powershell
python -m assistant_agent.server --port 8765
```

Open:

```text
http://127.0.0.1:8765
```

## What This MVP Proves

- The assistant can triage email into urgent, important, routine, and FYI categories.
- The assistant can draft warm, business-ready Hebrew replies.
- The assistant can generate native-sounding Hebrew morning briefings.
- The assistant can detect meeting conflicts from calendar data.
- The assistant can organize follow-up tasks with priorities and due dates.
- The assistant can connect to Google and Microsoft ecosystems through OAuth.
- The assistant keeps OAuth tokens server-side, away from frontend files.
- The assistant can support Slack or WhatsApp messaging after explicit approval.
- The assistant has a working approval queue for actions that affect external systems.
- Demo mode works without any OAuth setup, which makes the MVP easy to review.

## Features

- Email management: recent inbox review, priority classification, summaries, and reply drafts.
- Calendar management: upcoming events, conflict detection, focus-time suggestions, and safe proposed changes.
- Daily briefing: Hebrew morning report with urgent emails, important follow-ups, calendar view, conflicts, tasks, and recommendations.
- Task management: create, update, complete, delete, and persist tasks in `data/state.json`.
- OAuth connections: Gmail, Google Calendar, Outlook mail, and Outlook Calendar.
- Messaging channels: Slack webhook and WhatsApp Cloud API support for approved messages.
- Analytics: email response workload, calendar conflicts, meeting load, focus blocks, and open tasks.
- Bilingual UI: English and Hebrew dashboard labels through `web/i18n.js`.
- Demo mode: realistic Israeli business sample data without external credentials.

## Architecture

```text
Browser dashboard
  -> Python standard-library HTTP server
    -> Assistant service
      -> Email workflow
      -> Calendar workflow
      -> Task workflow
      -> Briefing workflow
      -> Scheduler
      -> Analytics
      -> Approval queue
      -> Provider adapters
        -> Google Workspace
        -> Microsoft 365
        -> Slack
        -> WhatsApp
        -> OpenAI enrichment
    -> JSON state store
    -> Server-only OAuth token stores
```

Provider adapters live under `assistant_agent/providers/`, so real integrations can be improved without rewriting the dashboard or workflow engine.

## Folder Structure

```text
.
|-- assistant_agent/
|   |-- ai.py
|   |-- classifier.py
|   |-- config.py
|   |-- google_oauth.py
|   |-- http_client.py
|   |-- microsoft_oauth.py
|   |-- models.py
|   |-- sample_data.py
|   |-- server.py
|   |-- service.py
|   |-- storage.py
|   `-- providers/
|       |-- base.py
|       |-- google.py
|       |-- messaging.py
|       `-- microsoft.py
|-- docs/
|   |-- CLIENT_READINESS_CHECKLIST.md
|   |-- DEPLOYMENT.md
|   |-- README.md
|   `-- screenshots/
|       `-- README.md
|-- tests/
|   `-- test_workflows.py
|-- web/
|   |-- app.js
|   |-- i18n.js
|   |-- index.html
|   `-- styles.css
|-- CLIENT_PROPOSAL.md
|-- DEMO_SCRIPT.md
|-- SUBMISSION_MESSAGE.md
|-- .env.example
`-- README.md
```

## Run Commands

Start the local app:

```powershell
python -m assistant_agent.server --port 8765
```

Run tests:

```powershell
python -m unittest discover -s tests -v
python -m compileall assistant_agent tests -q
```

## Configuration

Copy `.env.example` to `.env`:

```powershell
Copy-Item .env.example .env
```

Fill in only the providers needed for the demo or client environment.

## Demo Mode

```env
DEMO_MODE=true
```

When demo mode is enabled and no provider is connected, the assistant uses local sample emails, calendar events, and tasks. This is the safest way to record a demo video or present the MVP before OAuth credentials are ready.

Use real-only mode after OAuth is configured:

```env
DEMO_MODE=false
```

## Scheduler

```env
SCHEDULER_ENABLED=true
BRIEFING_HOUR=8
```

The scheduler runs only while the Python server is running. It generates one daily briefing approval after the configured hour. It does not send the briefing automatically.

## Google OAuth

Register this redirect URI in Google Cloud for local development:

```text
http://127.0.0.1:8765/oauth/google/callback
```

```env
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://127.0.0.1:8765/oauth/google/callback
GOOGLE_TOKEN_PATH=data/google_oauth_tokens.json
GOOGLE_OAUTH_STATE_PATH=data/google_oauth_state.json
GOOGLE_CALENDAR_ID=primary
GOOGLE_ENABLE_WRITE_ACTIONS=false
```

Default Google scopes:

```text
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/calendar.readonly
```

Optional write scopes when `GOOGLE_ENABLE_WRITE_ACTIONS=true`:

```text
https://www.googleapis.com/auth/gmail.send
https://www.googleapis.com/auth/calendar.events
```

Write scopes are still approval-gated.

## Microsoft OAuth

Register this redirect URI in Microsoft Entra ID for local development:

```text
http://127.0.0.1:8765/oauth/microsoft/callback
```

```env
MS_CLIENT_ID=your-client-id
MS_CLIENT_SECRET=your-client-secret
MS_TENANT_ID=common
MS_REDIRECT_URI=http://127.0.0.1:8765/oauth/microsoft/callback
MS_TOKEN_PATH=data/microsoft_oauth_tokens.json
MS_OAUTH_STATE_PATH=data/microsoft_oauth_state.json
MS_ENABLE_WRITE_ACTIONS=false
```

Default Microsoft delegated scopes:

```text
offline_access
Mail.Read
Calendars.Read
```

Optional write scopes when `MS_ENABLE_WRITE_ACTIONS=true`:

```text
Mail.Send
Calendars.ReadWrite
```

Write scopes are still approval-gated.

## OpenAI Enrichment

```env
OPENAI_API_KEY=
OPENAI_MODEL=
```

OpenAI is optional. Without it, the app uses deterministic local Hebrew logic for classification, summaries, and reply drafts.

## Messaging Channels

```env
SLACK_WEBHOOK_URL=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_TO=
```

## Safety and Human Approval

This project is built for safe assistant behavior:

- Email replies are drafted, not sent automatically.
- Calendar changes are proposed, not applied automatically.
- Gmail and Outlook messages are never deleted by the app.
- Sending email requires both a pending approval item and a connected provider write scope.
- Creating, rescheduling, or deleting calendar events requires both approval and a connected calendar write scope.
- Slack and WhatsApp messages require explicit approval before sending.
- OAuth access and refresh tokens are stored only under `data/` on the server side.
- OAuth tokens are never written into frontend files.
- Demo mode uses local sample data only.

Supported approval actions:

- `send_briefing`
- `send_message`
- `send_email`
- `create_focus_time`
- `create_calendar_event`
- `reschedule_event`
- `delete_event`
- `coordinate_meeting`
- `send_reminder`
- `send_prep_material`
- `notify_participants`

## API Status

The health endpoint is available at:

```text
GET /api/status
```

It returns demo mode status, scheduler status, provider connection status, record counts, timezone, and current local date/time.

## Screenshots and Demo Assets

Store screenshots in `docs/screenshots/`.

Suggested screenshots:

- `docs/screenshots/dashboard-en.png`
- `docs/screenshots/dashboard-he.png`
- `docs/screenshots/mobile-dashboard.png`
- `docs/screenshots/approval-queue.png`
- `docs/screenshots/calendar-conflict.png`

Client-facing support files:

- `DEMO_SCRIPT.md`
- `CLIENT_PROPOSAL.md`
- `docs/CLIENT_READINESS_CHECKLIST.md`
- `docs/DEPLOYMENT.md`
- `SUBMISSION_MESSAGE.md`

## Known Limitations

- OAuth setup is local/manual.
- Local token storage is suitable for single-user local demos; production should use encrypted secret storage.
- Meeting-attendance analytics require provider or meeting-platform attendance data and are currently represented as a future calendar analytics enhancement.
- Background scheduling runs only while the local Python server is running.
- OpenAI enrichment depends on the configured model and API key.
- Public Google apps that request sensitive or restricted scopes may require Google verification.

## Production Roadmap

1. Encrypted production secret storage.
2. User authentication and account separation.
3. Audit log for every provider action.
4. Hosted OAuth setup for Google and Microsoft.
5. Background worker service for scheduled jobs.
6. Rich approval payload review for calendar changes.
7. Email response-time tracking from approved sent-message events.
8. Meeting-attendance and calendar efficiency analytics from provider or meeting platform data.
9. Deployment packaging, monitoring, and backup strategy.
10. Multi-user workspace support.
