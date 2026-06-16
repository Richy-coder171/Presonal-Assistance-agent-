from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime

from .config import Settings
from .service import AssistantService


LOGGER = logging.getLogger("assistant_agent.worker")


def run_scheduled_briefings_once(
    settings: Settings | None = None,
    service: AssistantService | None = None,
    now: datetime | None = None,
) -> dict:
    settings = settings or Settings.from_env()
    service = service or AssistantService(settings)
    attempts = max(1, settings.scheduler_retry_attempts)
    last_error = ""
    for attempt in range(1, attempts + 1):
        try:
            result = service.run_scheduler_once(now)
            service.log_audit(
                "scheduled_job",
                "success",
                message="Briefing scheduler tick completed",
                metadata={"attempt": attempt, "result": result.get("status")},
            )
            return result
        except Exception as exc:  # noqa: BLE001 - retry and audit scheduled jobs.
            last_error = str(exc)
            service.log_audit(
                "scheduled_job",
                "failure",
                error=last_error,
                metadata={"attempt": attempt, "max_attempts": attempts},
            )
            if attempt < attempts:
                time.sleep(max(0, settings.scheduler_retry_delay_seconds))
    return {"status": "failed", "error": last_error}


def main() -> None:
    settings = Settings.from_env()
    parser = argparse.ArgumentParser(description="Run the Personal Assistant Agent worker.")
    parser.add_argument("--once", action="store_true", help="Run one scheduler tick and exit.")
    parser.add_argument("--interval-seconds", type=int, default=60)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.once:
        print(run_scheduled_briefings_once(settings))
        return

    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
    except ModuleNotFoundError:
        LOGGER.warning("APScheduler is not installed; using a simple polling loop.")
        while True:
            LOGGER.info(run_scheduled_briefings_once(settings))
            time.sleep(max(5, args.interval_seconds))
    else:
        scheduler = BlockingScheduler(timezone=settings.timezone)
        scheduler.add_job(
            lambda: LOGGER.info(run_scheduled_briefings_once(settings)),
            "interval",
            seconds=max(5, args.interval_seconds),
            id="daily_briefing_tick",
            max_instances=1,
            coalesce=True,
        )
        LOGGER.info("Personal Assistant Agent worker started")
        scheduler.start()


if __name__ == "__main__":
    main()
