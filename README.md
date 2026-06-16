# Personal Assistant Agent

Personal Assistant Agent is a Hebrew-first executive assistant dashboard for daily email triage, calendar coordination, task tracking, analytics, scheduled briefings, and approval-gated communications.

The app runs immediately in demo mode. When credentials are added, it can read Gmail, Google Calendar, Outlook mail, and Outlook Calendar. Risky actions such as email sends, calendar changes, reminders, prep-material messages, and participant notifications are routed through an approval queue.

## Project Overview

The assistant helps busy professionals review messages, identify urgent work, detect calendar conflicts, organize tasks, and generate a clear daily briefing. The dashboard supports English and Hebrew UI labels through `web/i18n.js`.

Demo mode is enabled by default so the full workflow can be tested locally without connecting real accounts.

## Features

- Inbox triage: pulls recent inbox messages and classifies them as urgent, important, routine, or FYI.
- Hebrew reply drafts: prepares warm, professional Hebrew draft replies for messages that need a response.
- Calendar overview: reads upcoming events and detects schedule conflicts.
- Daily report: generates a morning briefing with urgent messages, key meetings, conflicts, tasks, and recommendations.
- Scheduler: checks after the configured 8 AM briefing hour and creates one daily briefing approval per day.
- Analytics: tracks email response workload, calendar conflicts, focus blocks, task status, and success targets.
- Approval queue: stores proposed sends and calendar changes until a human approves or rejects them.
- Google OAuth: connects Gmail and Google Calendar with server-side token storage.
- Microsoft OAuth: connects Outlook mail and Outlook Calendar through Microsoft Graph.
- Optional write execution: email sends and calendar changes can execute only after write scopes are enabled and an approval item is approved.
- Messaging: sends approved briefings, reminders, prep materials, and notifications through Slack or WhatsApp when configured.
- Bilingual UI: English and Hebrew labels for the dashboard.

## Architecture

```text
Browser dashboard
  -> Python HTTP server
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

The server uses the Python standard library. Provider adapters are isolated under `assistant_agent/providers/`.

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
|-- .env.example
`-- README.md
```

## Run Commands

```powershell
python -m assistant_agent.server --port 8765
```

Open:

```text
http://127.0.0.1:8765
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

## Demo Mode

```env
DEMO_MODE=true
```

Use real-only mode after OAuth is configured:

```env
DEMO_MODE=false
```

When a real provider is connected, an empty inbox/calendar or provider error does not silently load demo records.

## Scheduler

```env
SCHEDULER_ENABLED=true
BRIEFING_HOUR=8
```

The scheduler runs only while the Python server is running. It generates one briefing per local day after the configured hour and creates a pending approval to send it. It does not send messages by itself.

## Google OAuth

Register this local redirect URI in Google Cloud:

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

Register this local redirect URI in Microsoft Entra ID:

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

Without OpenAI, the app uses deterministic local Hebrew logic.

## Messaging Channels

```env
SLACK_WEBHOOK_URL=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_TO=
```

## Approval Workflow

1. The assistant creates an approval item for a risky action.
2. The user reviews the title, description, payload, and risk.
3. The user approves or rejects it.
4. Only approved actions execute.
5. The result or error is stored on the approval item.

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

## Safety Rules

- Email sends require an approval item and provider write scope.
- Calendar creates, updates, and deletes require an approval item and provider write scope.
- The app never deletes Gmail messages or Outlook messages.
- OAuth tokens are stored server-side under `data/`, never in frontend code.
- OAuth state is short-lived and validated before token exchange.
- Demo mode uses sample data only.
- Human review is required before any workflow sends messages or changes calendar state.

## Screenshots

Store screenshots in `docs/screenshots/`.

Suggested files:

- `docs/screenshots/dashboard-en.png`
- `docs/screenshots/dashboard-he.png`
- `docs/screenshots/mobile-dashboard.png`

## Known Limitations

- OAuth setup is local/manual.
- Local token storage is suitable for single-user local use; production should use encrypted secret storage.
- Attendance-rate analytics require an external attendance signal and currently show unavailable.
- Background scheduling runs only while the local Python server is running.
- OpenAI enrichment depends on the configured model and API key.
- Public Google apps that request sensitive or restricted scopes may require Google verification.

## Production Roadmap

1. Encrypted production secret storage.
2. User authentication and account separation.
3. Audit log for every provider action.
4. Hosted OAuth setup for Google and Microsoft.
5. Background worker service for scheduled jobs.
6. Rich approval payload diffing for calendar changes.
7. Email response-time tracking from sent-message events.
8. Calendar attendance analytics from provider data or meeting platform exports.
9. Deployment packaging, monitoring, and backup strategy.
10. Multi-user workspace support.
