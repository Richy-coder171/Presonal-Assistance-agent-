from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path | None = None) -> None:
    env_path = path or ROOT_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    timezone: str
    demo_mode: bool
    data_path: Path
    openai_api_key: str
    openai_model: str
    google_client_id: str
    google_client_secret: str
    google_refresh_token: str
    google_access_token: str
    google_calendar_id: str
    ms_client_id: str
    ms_client_secret: str
    ms_refresh_token: str
    ms_tenant_id: str
    ms_graph_access_token: str
    slack_webhook_url: str
    whatsapp_access_token: str
    whatsapp_phone_number_id: str
    whatsapp_to: str

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            host=os.getenv("APP_HOST", "127.0.0.1"),
            port=int(os.getenv("APP_PORT", "8765")),
            timezone=os.getenv("APP_TIMEZONE", "Asia/Jerusalem"),
            demo_mode=_env_bool("DEMO_MODE", True),
            data_path=Path(os.getenv("DATA_PATH", str(ROOT_DIR / "data" / "state.json"))),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_model=os.getenv("OPENAI_MODEL", ""),
            google_client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
            google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
            google_refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN", ""),
            google_access_token=os.getenv("GOOGLE_ACCESS_TOKEN", ""),
            google_calendar_id=os.getenv("GOOGLE_CALENDAR_ID", "primary"),
            ms_client_id=os.getenv("MS_CLIENT_ID", ""),
            ms_client_secret=os.getenv("MS_CLIENT_SECRET", ""),
            ms_refresh_token=os.getenv("MS_REFRESH_TOKEN", ""),
            ms_tenant_id=os.getenv("MS_TENANT_ID", "common"),
            ms_graph_access_token=os.getenv("MS_GRAPH_ACCESS_TOKEN", ""),
            slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL", ""),
            whatsapp_access_token=os.getenv("WHATSAPP_ACCESS_TOKEN", ""),
            whatsapp_phone_number_id=os.getenv("WHATSAPP_PHONE_NUMBER_ID", ""),
            whatsapp_to=os.getenv("WHATSAPP_TO", ""),
        )


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

