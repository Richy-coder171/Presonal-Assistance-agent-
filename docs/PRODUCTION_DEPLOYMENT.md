# Production Deployment

## Prerequisites

- Python 3.12+ or Docker.
- PostgreSQL 14+.
- A strong `TOKEN_ENCRYPTION_KEY`, `SESSION_SECRET`, and `ADMIN_EMAIL`.
- Google and Microsoft OAuth apps with production redirect URLs.

## Local Development

```powershell
python -m assistant_agent.init_db
python -m assistant_agent.server --port 8765
```

Run the worker in a second terminal:

```powershell
python -m assistant_agent.worker
```

## Docker Compose

```powershell
Copy-Item .env.production.example .env.production
docker compose up --build
```

The compose stack starts `web`, `worker`, and `postgres`. APScheduler runs in the worker, not in the web lifecycle.

## Production

1. Set `DEMO_MODE=false`, `AUTH_ENABLED=true`, `ADMIN_EMAIL`, `TOKEN_ENCRYPTION_KEY`, and `SESSION_SECRET`.
2. Set `DATABASE_URL` to managed PostgreSQL.
3. Run `python -m assistant_agent.init_db` during release.
4. Run web with:

```bash
uvicorn assistant_agent.server:create_app_from_env --factory --host 0.0.0.0 --port 8765
```

5. Run worker with:

```bash
python -m assistant_agent.worker
```

6. Configure HTTPS and restrict `CORS_ORIGINS` to the deployed dashboard origin.

## Verification

```powershell
python -m unittest discover -s tests -v
python -m compileall assistant_agent tests -q
```

Check:

- `GET /health`
- authenticated `GET /api/status`
- dashboard login
- audit log entries after approval creation/rejection/execution
