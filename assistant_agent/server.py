from __future__ import annotations

import argparse
import json
import mimetypes
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from .config import ROOT_DIR, Settings
from .google_oauth import GoogleOAuthError
from .microsoft_oauth import MicrosoftOAuthError
from .service import AssistantService


WEB_DIR = ROOT_DIR / "web"


class AssistantRequestHandler(BaseHTTPRequestHandler):
    service: AssistantService

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/status":
            self._json(self.service.status())
        elif path == "/api/analytics":
            self._json(self.service.analytics())
        elif path == "/api/approvals":
            self._json({"approvals": self.service.list_approvals()})
        elif path == "/api/connections":
            self._json(self.service.connection_status())
        elif path == "/oauth/google/start":
            self._start_google_oauth()
        elif path == "/oauth/google/callback":
            self._complete_google_oauth()
        elif path == "/oauth/microsoft/start":
            self._start_microsoft_oauth()
        elif path == "/oauth/microsoft/callback":
            self._complete_microsoft_oauth()
        elif path == "/api/dashboard":
            self._json(self.service.dashboard())
        else:
            self._static(path)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/run/email":
                self._json(self.service.refresh_emails())
            elif path == "/api/run/calendar":
                self._json(self.service.refresh_calendar())
            elif path == "/api/run/briefing":
                briefing = self.service.generate_briefing()
                self._json(briefing.to_dict())
            elif path == "/api/run/scheduler":
                self._json(self.service.run_scheduler_once())
            elif path == "/api/briefing/send":
                payload = self._body()
                if not payload.get("approved"):
                    self._json({"error": "Sending requires explicit approval"}, status=403)
                else:
                    self._json(self.service.send_latest_briefing(approved=True))
            elif path == "/api/demo/load":
                self._json(self.service.load_demo())
            elif path == "/api/tasks":
                task = self.service.create_task(self._body())
                self._json(task.to_dict(), status=201)
            elif path == "/api/approvals":
                approval = self.service.create_approval(self._body())
                self._json(approval.to_dict(), status=201)
            elif path.startswith("/api/approvals/") and path.endswith("/approve"):
                approval_id = unquote(path.split("/")[-2])
                self._json(self.service.approve_item(approval_id))
            elif path.startswith("/api/approvals/") and path.endswith("/reject"):
                approval_id = unquote(path.split("/")[-2])
                self._json(self.service.reject_item(approval_id))
            else:
                self._json({"error": "Not found"}, status=404)
        except ValueError as exc:
            self._json({"error": str(exc)}, status=400)
        except Exception as exc:  # noqa: BLE001 - report API errors to the dashboard.
            self._json({"error": str(exc)}, status=500)

    def do_OPTIONS(self) -> None:
        self._json({})

    def do_PATCH(self) -> None:
        path = urlparse(self.path).path
        if not path.startswith("/api/tasks/"):
            self._json({"error": "Not found"}, status=404)
            return
        task_id = unquote(path.rsplit("/", 1)[-1])
        try:
            task = self.service.update_task(task_id, self._body())
            self._json(task.to_dict())
        except KeyError as exc:
            self._json({"error": str(exc)}, status=404)
        except Exception as exc:  # noqa: BLE001 - report API errors to the dashboard.
            self._json({"error": str(exc)}, status=500)

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        if not path.startswith("/api/tasks/"):
            self._json({"error": "Not found"}, status=404)
            return
        task_id = unquote(path.rsplit("/", 1)[-1])
        try:
            self._json(self.service.delete_task(task_id))
        except KeyError as exc:
            self._json({"error": str(exc)}, status=404)
        except Exception as exc:  # noqa: BLE001 - report API errors to the dashboard.
            self._json({"error": str(exc)}, status=500)

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def _json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PATCH,DELETE,OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location: str) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _start_google_oauth(self) -> None:
        try:
            self._redirect(
                self.service.google_authorization_url(self._google_redirect_uri())
            )
        except GoogleOAuthError as exc:
            self._redirect(f"/?oauth_error={quote(str(exc))}")

    def _complete_google_oauth(self) -> None:
        query = parse_qs(urlparse(self.path).query)
        try:
            self.service.complete_google_oauth(
                code=_query_value(query, "code"),
                state=_query_value(query, "state"),
                error=_query_value(query, "error"),
            )
            self._redirect("/?oauth=success")
        except GoogleOAuthError as exc:
            self._redirect(f"/?oauth_error={quote(str(exc))}")
        except Exception as exc:  # noqa: BLE001 - OAuth callback needs a visible UI error.
            self._redirect(f"/?oauth_error={quote(str(exc))}")

    def _start_microsoft_oauth(self) -> None:
        try:
            self._redirect(
                self.service.microsoft_authorization_url(self._microsoft_redirect_uri())
            )
        except MicrosoftOAuthError as exc:
            self._redirect(f"/?oauth_error={quote(str(exc))}")

    def _complete_microsoft_oauth(self) -> None:
        query = parse_qs(urlparse(self.path).query)
        try:
            self.service.complete_microsoft_oauth(
                code=_query_value(query, "code"),
                state=_query_value(query, "state"),
                error=_query_value(query, "error"),
            )
            self._redirect("/?oauth=microsoft_success")
        except MicrosoftOAuthError as exc:
            self._redirect(f"/?oauth_error={quote(str(exc))}")
        except Exception as exc:  # noqa: BLE001 - OAuth callback needs a visible UI error.
            self._redirect(f"/?oauth_error={quote(str(exc))}")

    def _google_redirect_uri(self) -> str:
        if self.service.settings.google_redirect_uri:
            return self.service.settings.google_redirect_uri
        host = self.headers.get(
            "Host",
            f"{self.service.settings.host}:{self.service.settings.port}",
        )
        return f"http://{host}/oauth/google/callback"

    def _microsoft_redirect_uri(self) -> str:
        if self.service.settings.ms_redirect_uri:
            return self.service.settings.ms_redirect_uri
        host = self.headers.get(
            "Host",
            f"{self.service.settings.host}:{self.service.settings.port}",
        )
        return f"http://{host}/oauth/microsoft/callback"

    def _static(self, request_path: str) -> None:
        if request_path == "/":
            request_path = "/index.html"
        target = (WEB_DIR / request_path.lstrip("/")).resolve()
        if WEB_DIR.resolve() not in target.parents and target != WEB_DIR.resolve():
            self._json({"error": "Invalid path"}, status=400)
            return
        if not target.exists() or not target.is_file():
            self._json({"error": "Not found"}, status=404)
            return
        content = target.read_bytes()
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if target.suffix in {".html", ".css", ".js"}:
            content_type += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def build_server(host: str, port: int) -> ThreadingHTTPServer:
    settings = Settings.from_env()
    service = AssistantService(settings)
    AssistantRequestHandler.service = service
    _start_scheduler(service)
    return ThreadingHTTPServer((host, port), AssistantRequestHandler)


def main() -> None:
    settings = Settings.from_env()
    parser = argparse.ArgumentParser(description="Run the Personal Assistant Agent web app.")
    parser.add_argument("--host", default=settings.host)
    parser.add_argument("--port", type=int, default=settings.port)
    args = parser.parse_args()
    server = build_server(args.host, args.port)
    print(f"Personal Assistant Agent running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down")


def _query_value(query: dict[str, list[str]], key: str) -> str:
    values = query.get(key, [""])
    return values[0] if values else ""


def _start_scheduler(service: AssistantService) -> None:
    if not service.settings.scheduler_enabled:
        return

    def loop() -> None:
        while True:
            try:
                service.run_scheduler_once()
            except Exception as exc:  # noqa: BLE001 - keep scheduler alive.
                print(f"Scheduler error: {exc}")
            time.sleep(60)

    thread = threading.Thread(target=loop, name="briefing-scheduler", daemon=True)
    thread.start()


if __name__ == "__main__":
    main()
