from __future__ import annotations

import argparse
import json
import logging
import mimetypes
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote
from uuid import uuid4

import uvicorn
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response

try:  # FastAPI is the production dependency; Starlette keeps local tests light.
    from fastapi import FastAPI
except ModuleNotFoundError:  # pragma: no cover - exercised in minimal local envs.
    FastAPI = None  # type: ignore[assignment]
    from starlette.applications import Starlette

from .auth import SESSION_USER_KEY, session_secret, verify_login
from .config import ROOT_DIR, Settings
from .google_oauth import GoogleOAuthError
from .microsoft_oauth import MicrosoftOAuthError
from .service import AssistantService


WEB_DIR = ROOT_DIR / "web"
LOGGER = logging.getLogger("assistant_agent.server")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Response:
        request_id = request.headers.get("X-Request-ID", uuid4().hex)
        request.state.request_id = request_id
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except PermissionError as exc:
            if str(exc) == "login_required":
                response = RedirectResponse("/login", status_code=302)
            else:
                response = json_error(request, "unauthorized", "Unauthorized", status_code=401)
        except Exception as exc:  # noqa: BLE001 - middleware owns API error shape.
            LOGGER.exception("Unhandled request failure")
            response = json_error(
                request,
                "internal_error",
                str(exc),
                status_code=500,
            )
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        LOGGER.info(
            json.dumps(
                {
                    "event": "request",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                },
                ensure_ascii=False,
            )
        )
        return response


def create_app(
    settings: Settings | None = None,
    service: AssistantService | None = None,
) -> Any:
    settings = settings or Settings.from_env()
    service = service or AssistantService(settings)
    app = FastAPI(title="Personal Assistant Agent") if FastAPI else Starlette(debug=False)
    app.state.settings = settings
    app.state.service = service

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret(settings),
        same_site="lax",
        https_only=not settings.demo_mode and settings.auth_enabled,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )

    _add_route(app, "/health", health, ["GET"])
    _add_route(app, "/api/status", api_status, ["GET"])
    _add_route(app, "/auth/login", login, ["GET", "POST"])
    _add_route(app, "/auth/logout", logout, ["POST"])
    _add_route(app, "/login", login_page, ["GET"])
    _add_route(app, "/api/dashboard", dashboard, ["GET"])
    _add_route(app, "/api/analytics", analytics, ["GET"])
    _add_route(app, "/api/approvals", approvals, ["GET", "POST"])
    _add_route(app, "/api/audit-logs", audit_logs, ["GET"])
    _add_route(app, "/api/connections", connections, ["GET"])
    _add_route(app, "/api/run/email", run_email, ["POST"])
    _add_route(app, "/api/run/calendar", run_calendar, ["POST"])
    _add_route(app, "/api/run/briefing", run_briefing, ["POST"])
    _add_route(app, "/api/run/scheduler", run_scheduler, ["POST"])
    _add_route(app, "/api/briefing/send", queue_briefing_send, ["POST"])
    _add_route(app, "/api/demo/load", demo_reset, ["POST"])
    _add_route(app, "/api/demo/reset", demo_reset, ["POST"])
    _add_route(app, "/api/tasks", tasks, ["POST"])
    _add_route(app, "/api/tasks/{task_id}", task_item, ["PATCH", "DELETE"])
    _add_route(app, "/api/approvals/{approval_id}/approve", approve_item, ["POST"])
    _add_route(app, "/api/approvals/{approval_id}/reject", reject_item, ["POST"])
    _add_route(app, "/oauth/google/start", google_start, ["GET"])
    _add_route(app, "/oauth/google/callback", google_callback, ["GET"])
    _add_route(app, "/oauth/microsoft/start", microsoft_start, ["GET"])
    _add_route(app, "/oauth/microsoft/callback", microsoft_callback, ["GET"])
    _add_route(app, "/{path:path}", static_files, ["GET"])
    return app


def create_app_from_env() -> Any:
    return create_app(Settings.from_env())


async def health(request: Request) -> Response:
    return JSONResponse({"status": "ok", "service": "personal-assistant-agent"})


async def api_status(request: Request) -> Response:
    require_auth(request)
    return JSONResponse(service(request).status())


async def dashboard(request: Request) -> Response:
    require_auth(request)
    return JSONResponse(service(request).dashboard())


async def analytics(request: Request) -> Response:
    require_auth(request)
    return JSONResponse(service(request).analytics())


async def approvals(request: Request) -> Response:
    require_auth(request)
    assistant = service(request)
    if request.method == "GET":
        return JSONResponse({"approvals": assistant.list_approvals()})
    try:
        approval = assistant.create_approval(await body(request))
        return JSONResponse(approval.to_dict(), status_code=201)
    except ValueError as exc:
        return json_error(request, "bad_request", str(exc), 400)


async def audit_logs(request: Request) -> Response:
    require_auth(request)
    return JSONResponse({"audit_logs": service(request).audit_logs()})


async def connections(request: Request) -> Response:
    require_auth(request)
    return JSONResponse(service(request).connection_status())


async def run_email(request: Request) -> Response:
    require_auth(request)
    return JSONResponse(service(request).refresh_emails())


async def run_calendar(request: Request) -> Response:
    require_auth(request)
    return JSONResponse(service(request).refresh_calendar())


async def run_briefing(request: Request) -> Response:
    require_auth(request)
    return JSONResponse(service(request).generate_briefing().to_dict())


async def run_scheduler(request: Request) -> Response:
    require_auth(request)
    return JSONResponse(service(request).run_scheduler_once())


async def queue_briefing_send(request: Request) -> Response:
    require_auth(request)
    assistant = service(request)
    state = assistant.store.load()
    briefing = state["briefings"][0] if state["briefings"] else assistant.generate_briefing().to_dict()
    approval = assistant.create_approval(
        {
            "action_type": "send_briefing",
            "title": "Send daily briefing",
            "description": "Send the generated daily briefing through configured messaging channels.",
            "payload": {"briefing_id": briefing["id"]},
            "risk": "external_message",
        }
    )
    return JSONResponse({"queued": True, "approval": approval.to_dict()}, status_code=202)


async def demo_reset(request: Request) -> Response:
    require_auth(request)
    return JSONResponse(service(request).reset_demo())


async def tasks(request: Request) -> Response:
    require_auth(request)
    try:
        task = service(request).create_task(await body(request))
        return JSONResponse(task.to_dict(), status_code=201)
    except ValueError as exc:
        return json_error(request, "bad_request", str(exc), 400)


async def task_item(request: Request) -> Response:
    require_auth(request)
    task_id = request.path_params["task_id"]
    try:
        if request.method == "PATCH":
            task = service(request).update_task(task_id, await body(request))
            return JSONResponse(task.to_dict())
        return JSONResponse(service(request).delete_task(task_id))
    except KeyError as exc:
        return json_error(request, "not_found", str(exc), 404)
    except ValueError as exc:
        return json_error(request, "bad_request", str(exc), 400)


async def approve_item(request: Request) -> Response:
    require_auth(request)
    try:
        approval = service(request).approve_item(request.path_params["approval_id"])
        return JSONResponse(approval.to_dict())
    except (KeyError, ValueError) as exc:
        return json_error(request, "bad_request", str(exc), 400)


async def reject_item(request: Request) -> Response:
    require_auth(request)
    try:
        approval = service(request).reject_item(request.path_params["approval_id"])
        return JSONResponse(approval.to_dict())
    except (KeyError, ValueError) as exc:
        return json_error(request, "bad_request", str(exc), 400)


async def google_start(request: Request) -> Response:
    require_auth(request, redirect=True)
    try:
        return RedirectResponse(
            service(request).google_authorization_url(google_redirect_uri(request))
        )
    except GoogleOAuthError as exc:
        return RedirectResponse(f"/?oauth_error={quote(str(exc))}")


async def google_callback(request: Request) -> Response:
    try:
        service(request).complete_google_oauth(
            code=request.query_params.get("code", ""),
            state=request.query_params.get("state", ""),
            error=request.query_params.get("error", ""),
        )
        return RedirectResponse("/?oauth=success")
    except Exception as exc:  # noqa: BLE001 - OAuth callback needs visible UI feedback.
        return RedirectResponse(f"/?oauth_error={quote(str(exc))}")


async def microsoft_start(request: Request) -> Response:
    require_auth(request, redirect=True)
    try:
        return RedirectResponse(
            service(request).microsoft_authorization_url(microsoft_redirect_uri(request))
        )
    except MicrosoftOAuthError as exc:
        return RedirectResponse(f"/?oauth_error={quote(str(exc))}")


async def microsoft_callback(request: Request) -> Response:
    try:
        service(request).complete_microsoft_oauth(
            code=request.query_params.get("code", ""),
            state=request.query_params.get("state", ""),
            error=request.query_params.get("error", ""),
        )
        return RedirectResponse("/?oauth=microsoft_success")
    except Exception as exc:  # noqa: BLE001 - OAuth callback needs visible UI feedback.
        return RedirectResponse(f"/?oauth_error={quote(str(exc))}")


async def login_page(request: Request) -> Response:
    if not settings(request).auth_enabled:
        return RedirectResponse("/")
    return HTMLResponse(LOGIN_HTML)


async def login(request: Request) -> Response:
    if request.method == "GET":
        return await login_page(request)
    payload = await body(request)
    result = verify_login(
        settings(request),
        str(payload.get("email", "")),
        str(payload.get("password", "")),
    )
    if not result.ok:
        return json_error(request, "unauthorized", result.message, 401)
    request.session[SESSION_USER_KEY] = str(payload.get("email", "")).strip().lower()
    return JSONResponse({"authenticated": True, "email": request.session[SESSION_USER_KEY]})


async def logout(request: Request) -> Response:
    request.session.clear()
    return JSONResponse({"authenticated": False})


async def static_files(request: Request) -> Response:
    if settings(request).auth_enabled and not is_authenticated(request):
        return RedirectResponse("/login")
    request_path = "/" + request.path_params.get("path", "")
    if request_path == "/":
        request_path = "/index.html"
    target = (WEB_DIR / request_path.lstrip("/")).resolve()
    if WEB_DIR.resolve() not in target.parents and target != WEB_DIR.resolve():
        return json_error(request, "bad_request", "Invalid path", 400)
    if not target.exists() or not target.is_file():
        return json_error(request, "not_found", "Not found", 404)
    media_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
    return FileResponse(target, media_type=media_type)


async def body(request: Request) -> dict[str, Any]:
    if not request.headers.get("content-length"):
        return {}
    try:
        payload = await request.json()
    except (json.JSONDecodeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def service(request: Request) -> AssistantService:
    return request.app.state.service


def settings(request: Request) -> Settings:
    return request.app.state.settings


def is_authenticated(request: Request) -> bool:
    configured_email = (settings(request).admin_email or "").strip().lower()
    session_email = str(request.session.get(SESSION_USER_KEY, "")).strip().lower()
    return bool(configured_email and session_email == configured_email)


def require_auth(request: Request, redirect: bool = False) -> None:
    if not settings(request).auth_enabled:
        return
    if is_authenticated(request):
        return
    if redirect:
        raise PermissionError("login_required")
    raise PermissionError("Unauthorized")


def json_error(request: Request, code: str, message: str, status_code: int) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "")
    return JSONResponse(
        {
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id,
            }
        },
        status_code=status_code,
    )


def google_redirect_uri(request: Request) -> str:
    configured = settings(request).google_redirect_uri
    if configured:
        return configured
    return f"{request.url.scheme}://{request.headers.get('host')}/oauth/google/callback"


def microsoft_redirect_uri(request: Request) -> str:
    configured = settings(request).ms_redirect_uri
    if configured:
        return configured
    return f"{request.url.scheme}://{request.headers.get('host')}/oauth/microsoft/callback"


def _add_route(app: Any, path: str, endpoint: Any, methods: list[str]) -> None:
    if FastAPI:
        app.add_api_route(path, endpoint, methods=methods, include_in_schema=path.startswith("/api") or path == "/health")
    else:
        app.add_route(path, endpoint, methods=methods)


def main() -> None:
    settings = Settings.from_env()
    parser = argparse.ArgumentParser(description="Run the Personal Assistant Agent web app.")
    parser.add_argument("--host", default=settings.host)
    parser.add_argument("--port", type=int, default=settings.port)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(f"Personal Assistant Agent running at http://{args.host}:{args.port}")
    uvicorn.run(create_app(settings), host=args.host, port=args.port, log_level="info")


LOGIN_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Login - Personal Assistant Agent</title>
    <style>
      body { margin: 0; min-height: 100vh; display: grid; place-items: center; font-family: Segoe UI, Arial, sans-serif; background: #f4f6f8; color: #152033; }
      form { width: min(380px, calc(100% - 32px)); display: grid; gap: 12px; padding: 24px; border: 1px solid #d8dee7; border-radius: 8px; background: #fff; }
      h1 { margin: 0 0 4px; font-size: 1.35rem; }
      input, button { min-height: 42px; border-radius: 8px; border: 1px solid #c4ccd8; padding: 0 12px; font: inherit; }
      button { color: #fff; border-color: #2457c5; background: #2457c5; cursor: pointer; }
      p { margin: 0; color: #647084; }
      .error { color: #b73535; min-height: 20px; }
    </style>
  </head>
  <body>
    <form id="login-form">
      <h1>Personal Assistant Agent</h1>
      <p>Sign in with the configured admin account.</p>
      <input name="email" type="email" placeholder="Admin email" autocomplete="username" required>
      <input name="password" type="password" placeholder="Password" autocomplete="current-password" required>
      <button type="submit">Sign in</button>
      <p id="error" class="error"></p>
    </form>
    <script>
      document.querySelector("#login-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const form = new FormData(event.currentTarget);
        const response = await fetch("/auth/login", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({email: form.get("email"), password: form.get("password")})
        });
        const payload = await response.json();
        if (!response.ok) {
          document.querySelector("#error").textContent = payload.error?.message || "Sign in failed";
          return;
        }
        window.location.assign("/");
      });
    </script>
  </body>
</html>"""


if __name__ == "__main__":
    main()
