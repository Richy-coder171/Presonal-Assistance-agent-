# Operations Runbook

## Start Services

```bash
python -m assistant_agent.init_db
uvicorn assistant_agent.server:create_app_from_env --factory --host 0.0.0.0 --port 8765
python -m assistant_agent.worker
```

## Health Checks

- `GET /health`
- authenticated `GET /api/status`

## Common Incidents

### OAuth connection fails

Check provider client ID, client secret, redirect URI, consent screen, and requested scopes.

### Scheduled briefing is missing

Check worker logs, `SCHEDULER_ENABLED`, `BRIEFING_HOUR`, timezone, and `audit_logs` entries with `scheduled_briefing` or `scheduled_job`.

### Approval execution fails

Open the approval queue and audit logs. Most write failures are caused by write scopes being disabled or missing from the connected provider account.

### Token decryption fails

Confirm the deployment is using the same `TOKEN_ENCRYPTION_KEY` that encrypted the stored tokens.
