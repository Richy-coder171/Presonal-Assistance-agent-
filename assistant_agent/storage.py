from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_STATE = {
    "emails": [],
    "events": [],
    "tasks": [],
    "briefings": [],
}


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return _fresh_state()
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return _fresh_state()
        for key, value in DEFAULT_STATE.items():
            state.setdefault(key, list(value))
        return state

    def save(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(self.path)


def _fresh_state() -> dict[str, Any]:
    return {key: list(value) for key, value in DEFAULT_STATE.items()}

