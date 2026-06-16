# Agent Profile: Personal Assistant Agent

## Summary

Personal Assistant Agent is a Hebrew-first executive assistant for email triage, Hebrew reply drafts, calendar conflict detection, task tracking, daily Hebrew briefings, analytics, and approval-gated external actions.

## Core Workflows

- Email triage across Gmail and Outlook.
- Hebrew reply drafting without automatic sending.
- Daily Hebrew briefing generation.
- Calendar conflict detection across Google Calendar and Outlook Calendar.
- Task creation, updates, completion, and deletion.
- Analytics for response workload, conflicts, focus time, and task backlog.
- Human approval queue for messages, email sending, and calendar writes.
- Slack and WhatsApp messaging after approval.
- Demo mode for marketplace review without live credentials.

## Safety Positioning

The agent is read-first and approval-gated. It never deletes Gmail or Outlook messages. Email sends and calendar writes require both an approved queue item and configured provider write scopes. OAuth tokens are encrypted at rest and kept server-side.

## Target Buyer

Israeli SMB executives, operations teams, and founder-led companies that need Hebrew-first administrative support with clear human control over external actions.
