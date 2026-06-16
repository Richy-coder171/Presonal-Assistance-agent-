# Privacy Model

## Data Stored

The agent stores user records, provider connection metadata, encrypted OAuth token payloads, email metadata/content needed for triage, calendar event metadata, tasks, approvals, briefings, and audit logs.

## Data Not Stored

- OAuth secrets are not stored in frontend files.
- OAuth tokens are not stored in plaintext.
- Gmail and Outlook messages are not deleted by the agent.

## Demo Mode

Demo mode uses sample local data and does not require provider credentials. It is suitable for marketplace review and sales demos.

## Retention

The current release keeps operational records in PostgreSQL until manually purged. A production customer deployment should define retention windows for emails, briefings, approvals, and audit logs.
