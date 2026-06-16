# Client Readiness Checklist

Use this checklist before sending the MVP to a client or recording the demo video.

## Screenshots Needed

- [ ] Dashboard overview in English.
- [ ] Dashboard overview in Hebrew.
- [ ] Email triage with urgent, important, routine, and FYI labels.
- [ ] Hebrew draft reply.
- [ ] Daily Hebrew briefing.
- [ ] Calendar conflict example.
- [ ] Approval queue.
- [ ] Analytics panel.
- [ ] Mobile dashboard view.

## Demo Video Needed

- [ ] Record a 1-2 minute walkthrough using `DEMO_SCRIPT.md`.
- [ ] Show demo mode first.
- [ ] Show provider connection status.
- [ ] Show email triage and Hebrew draft reply.
- [ ] Show daily briefing.
- [ ] Show calendar conflict.
- [ ] Show approval queue.
- [ ] Show analytics.
- [ ] Mention that risky actions require human approval.

## OAuth Setup Completed

- [ ] Google Cloud project created.
- [ ] Gmail API enabled.
- [ ] Google Calendar API enabled.
- [ ] Google OAuth redirect URI configured.
- [ ] Microsoft Entra app registration created.
- [ ] Microsoft redirect URI configured.
- [ ] `.env` contains only the credentials required for the selected demo.
- [ ] OAuth tokens are stored under `data/`, not in frontend files.

## Safety Rules Verified

- [ ] Emails are drafted, not sent automatically.
- [ ] Calendar events are not created, edited, or deleted automatically.
- [ ] Slack and WhatsApp messages require approval.
- [ ] Approval queue is visible in the UI.
- [ ] Risky provider write actions require provider write scopes.
- [ ] Demo mode works without OAuth credentials.

## Test Commands Passed

- [ ] `python -m unittest discover -s tests -v`
- [ ] `python -m compileall assistant_agent tests -q`

## Deployment Notes Completed

- [ ] Decide local demo, private server, or hosted deployment.
- [ ] Set production `GOOGLE_REDIRECT_URI` and `MS_REDIRECT_URI`.
- [ ] Replace local token storage with encrypted secret storage for production.
- [ ] Add authentication before multi-user deployment.
- [ ] Add audit logging before enabling real write actions for production users.
- [ ] Capture final screenshots in `docs/screenshots/`.
