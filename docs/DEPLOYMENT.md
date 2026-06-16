# Deployment Notes

This project is dependency-light and runs with the Python standard library. It is ready for a local client demo and can be deployed as a small web service for review.

## Local Setup

```powershell
Copy-Item .env.example .env
python -m assistant_agent.server --port 8765
```

Open:

```text
http://127.0.0.1:8765
```

Health check:

```text
http://127.0.0.1:8765/api/status
```

For a safe client walkthrough, keep:

```env
DEMO_MODE=true
```

Use the **Reset Demo** button to reseed demo emails, calendar events, tasks, approvals, analytics, and the Hebrew briefing. The reset preserves non-demo provider records.

## Render Deployment Notes

Render web services must bind to `0.0.0.0` and the platform-provided `PORT` value. Render's web service docs also describe setting environment variables, health checks, and persistent disks from the service settings.

Suggested settings:

```text
Build Command:
python -m compileall assistant_agent tests -q

Start Command:
python -m assistant_agent.server --host 0.0.0.0 --port $PORT

Health Check Path:
/api/status
```

Set environment variables in the Render dashboard rather than committing `.env`.

Useful reference: https://render.com/docs/web-services

## Railway Deployment Notes

Railway supports Python services and lets you configure variables and the start command from the project/service settings.

Suggested settings:

```text
Start Command:
python -m assistant_agent.server --host 0.0.0.0 --port $PORT
```

If Railway asks for a health check path, use:

```text
/api/status
```

Set environment variables in Railway Variables. Do not commit `.env` or token files.

Useful reference: https://docs.railway.com/

## Environment Variables

Minimum local demo:

```env
DEMO_MODE=true
APP_TIMEZONE=Asia/Jerusalem
SCHEDULER_ENABLED=true
BRIEFING_HOUR=8
```

Google OAuth:

```env
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=https://your-domain.example/oauth/google/callback
GOOGLE_TOKEN_PATH=data/google_oauth_tokens.json
GOOGLE_OAUTH_STATE_PATH=data/google_oauth_state.json
GOOGLE_CALENDAR_ID=primary
GOOGLE_ENABLE_WRITE_ACTIONS=false
```

Microsoft OAuth:

```env
MS_CLIENT_ID=
MS_CLIENT_SECRET=
MS_TENANT_ID=common
MS_REDIRECT_URI=https://your-domain.example/oauth/microsoft/callback
MS_TOKEN_PATH=data/microsoft_oauth_tokens.json
MS_OAUTH_STATE_PATH=data/microsoft_oauth_state.json
MS_ENABLE_WRITE_ACTIONS=false
```

OpenAI enrichment:

```env
OPENAI_API_KEY=
OPENAI_MODEL=
```

Messaging:

```env
SLACK_WEBHOOK_URL=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_TO=
```

## OAuth Redirect URI Notes

For local development:

```text
http://127.0.0.1:8765/oauth/google/callback
http://127.0.0.1:8765/oauth/microsoft/callback
```

For production, register the exact deployed HTTPS URLs:

```text
https://your-domain.example/oauth/google/callback
https://your-domain.example/oauth/microsoft/callback
```

The value in `.env` or platform variables must match the URI registered with Google Cloud or Microsoft Entra ID.

## Data Storage Warning

The local JSON store under `data/` is appropriate for a demo or single-user local review. Production should replace it with:

- Encrypted database storage for assistant state.
- Encrypted secret storage for OAuth access and refresh tokens.
- Server-side session/authentication controls.
- Audit logs for approval decisions and provider actions.
- Backups and restore procedures.

Never store OAuth tokens in frontend files.
