from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class HttpError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, body: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.body = body


def request_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: Any = None,
    form: dict[str, str] | None = None,
    timeout: int = 20,
) -> Any:
    payload: bytes | None = None
    request_headers = dict(headers or {})

    if body is not None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    elif form is not None:
        payload = urlencode(form).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")

    request = Request(url, data=payload, method=method, headers=request_headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise HttpError(f"HTTP {exc.code} for {url}", exc.code, body_text) from exc
    except URLError as exc:
        raise HttpError(f"Request failed for {url}: {exc.reason}") from exc

    if not raw:
        return {}
    return json.loads(raw)

