from __future__ import annotations

from .config import Settings
from .db import init_database


def main() -> None:
    settings = Settings.from_env()
    init_database(settings.database_url)
    print("Database tables are ready.")


if __name__ == "__main__":
    main()
