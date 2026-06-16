# Security Model

## Authentication

The first production release uses single-user session authentication. Set:

- `AUTH_ENABLED=true`
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD_HASH` or temporary `ADMIN_PASSWORD`
- `SESSION_SECRET`

Dashboard and API routes reject unauthorized requests when auth is enabled.

## Token Protection

OAuth access tokens, refresh tokens, and ID tokens are encrypted with `TOKEN_ENCRYPTION_KEY` before storage. Production storage uses the `oauth_tokens` PostgreSQL table. Legacy path-based token stores also encrypt sensitive token fields for compatibility.

## External Action Controls

External side effects are approval-gated:

- `send_email`
- `send_message`
- `create_calendar_event`
- `reschedule_event`
- `create_focus_time`
- `send_briefing`

Email sending additionally requires provider write scopes. Calendar modifications additionally require calendar write scopes. Gmail and Outlook email deletion is unsupported.

## Audit Logging

The `audit_logs` table records approval creation, approval/rejection, execution success/failure, scheduled jobs, and external action attempts.
