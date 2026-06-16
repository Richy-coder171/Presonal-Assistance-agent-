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
    google_redirect_uri: str = ""
    google_token_path: Path = ROOT_DIR / "data" / "google_oauth_tokens.json"
    google_oauth_state_path: Path = ROOT_DIR / "data" / "google_oauth_state.json"
    google_enable_write_actions: bool = False
    ms_redirect_uri: str = ""
    ms_token_path: Path = ROOT_DIR / "data" / "microsoft_oauth_tokens.json"
    ms_oauth_state_path: Path = ROOT_DIR / "data" / "microsoft_oauth_state.json"
    ms_enable_write_actions: bool = False
    scheduler_enabled: bool = True
    briefing_hour: int = 8
    database_url: str = ""
    token_encryption_key: str = ""
    admin_email: str = ""
    admin_password: str = ""
    admin_password_hash: str = ""
    session_secret: str = ""
    auth_enabled: bool = False
    single_user_mode: bool = True
    cors_origins: tuple[str, ...] = ("http://127.0.0.1:8765",)
    scheduler_retry_attempts: int = 3
    scheduler_retry_delay_seconds: int = 5

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        default_cors = f"http://{os.getenv('APP_HOST', '127.0.0.1')}:{os.getenv('APP_PORT', '8765')}"
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
            google_redirect_uri=os.getenv("GOOGLE_REDIRECT_URI", ""),
            google_token_path=Path(
                os.getenv(
                    "GOOGLE_TOKEN_PATH",
                    str(ROOT_DIR / "data" / "google_oauth_tokens.json"),
                )
            ),
            google_oauth_state_path=Path(
                os.getenv(
                    "GOOGLE_OAUTH_STATE_PATH",
                    str(ROOT_DIR / "data" / "google_oauth_state.json"),
                )
            ),
            google_enable_write_actions=_env_bool("GOOGLE_ENABLE_WRITE_ACTIONS", False),
            ms_redirect_uri=os.getenv("MS_REDIRECT_URI", ""),
            ms_token_path=Path(
                os.getenv(
                    "MS_TOKEN_PATH",
                    str(ROOT_DIR / "data" / "microsoft_oauth_tokens.json"),
                )
            ),
            ms_oauth_state_path=Path(
                os.getenv(
                    "MS_OAUTH_STATE_PATH",
                    str(ROOT_DIR / "data" / "microsoft_oauth_state.json"),
                )
            ),
            ms_enable_write_actions=_env_bool("MS_ENABLE_WRITE_ACTIONS", False),
            scheduler_enabled=_env_bool("SCHEDULER_ENABLED", True),
            briefing_hour=int(os.getenv("BRIEFING_HOUR", "8")),
            database_url=os.getenv("DATABASE_URL", _default_sqlite_url()),
            token_encryption_key=os.getenv("TOKEN_ENCRYPTION_KEY", ""),
            admin_email=os.getenv("ADMIN_EMAIL", ""),
            admin_password=os.getenv("ADMIN_PASSWORD", ""),
            admin_password_hash=os.getenv("ADMIN_PASSWORD_HASH", ""),
            session_secret=os.getenv("SESSION_SECRET", ""),
            auth_enabled=_env_bool("AUTH_ENABLED", False),
            single_user_mode=_env_bool("SINGLE_USER_MODE", True),
            cors_origins=_env_list("CORS_ORIGINS", (default_cors,)),
            scheduler_retry_attempts=int(os.getenv("SCHEDULER_RETRY_ATTEMPTS", "3")),
            scheduler_retry_delay_seconds=int(os.getenv("SCHEDULER_RETRY_DELAY_SECONDS", "5")),
        )


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.getenv(name)
    if value is None:
        return default
    items = tuple(item.strip() for item in value.split(",") if item.strip())
    return items or default


def _default_sqlite_url() -> str:
    path = (ROOT_DIR / "data" / "assistant.db").resolve().as_posix()
    return f"sqlite:///{path}"
