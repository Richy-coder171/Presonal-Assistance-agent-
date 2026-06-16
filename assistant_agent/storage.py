from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4


DEFAULT_STATE = {
    "emails": [],
    "events": [],
    "tasks": [],
    "briefings": [],
    "approvals": [],
    "scheduler": {},
}

_STATE_LOCK = Lock()


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, Any]:
        with _STATE_LOCK:
            if not self.path.exists():
                return _fresh_state()
            try:
                state = json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return _fresh_state()
            for key, value in DEFAULT_STATE.items():
                state.setdefault(key, _clone_default(value))
            return state

    def save(self, state: dict[str, Any]) -> None:
        with _STATE_LOCK:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.path.with_name(f"{self.path.name}.{uuid4().hex}.tmp")
            try:
                temp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
                temp_path.replace(self.path)
            finally:
                if temp_path.exists():
                    temp_path.unlink()


def _fresh_state() -> dict[str, Any]:
    return {key: _clone_default(value) for key, value in DEFAULT_STATE.items()}


def _clone_default(value: Any) -> Any:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, dict):
        return dict(value)
    return value
