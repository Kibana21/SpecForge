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
    beat_schedule={
        "purge-expired-refresh-tokens": {
            "task": "workers.tasks.purge_expired_refresh_tokens",
            "schedule": crontab(hour=3, minute=0),  # daily 03:00 UTC
        },
    },
)
