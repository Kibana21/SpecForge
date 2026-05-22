from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "specforge",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    # The WORKER should retry the broker on startup (resilient). API-side dispatch
    # fast-fail is handled separately by workers/dispatch.py (a TCP pre-flight before
    # .delay()), so we do NOT disable broker retries here — doing so makes the worker
    # quit on startup when the broker isn't instantly reachable.
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "purge-expired-refresh-tokens": {
            "task": "workers.tasks.purge_expired_refresh_tokens",
            "schedule": crontab(hour=3, minute=0),  # daily 03:00 UTC
        },
        "reset-stale-rebuild-status": {
            "task": "workers.tasks.reset_stale_rebuild_status",
            "schedule": crontab(minute="*/30"),  # every 30 minutes
        },
        "recompute-triage": {
            "task": "workers.tasks.recompute_triage",
            "schedule": crontab(minute="*/15"),  # every 15 minutes (BR-M1-005)
        },
    },
)
