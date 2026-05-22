"""Best-effort Celery task dispatch.

`.delay()` connects to the broker and (despite retry config) can hang ~20s when
the broker is down. This helper does a fast TCP pre-flight so dispatch never
hangs or raises — work stays durable and can be re-triggered later.
"""
import logging
import socket
from urllib.parse import urlparse

from app.config import get_settings

log = logging.getLogger(__name__)


def _broker_reachable(timeout: float = 0.3) -> bool:
    try:
        url = urlparse(get_settings().celery_broker_url)
        host = url.hostname or "localhost"
        port = url.port or 6379
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def dispatch(task, *args, **kwargs):
    """Enqueue a task if the broker is reachable; otherwise log and skip (no hang)."""
    if not _broker_reachable():
        log.warning("broker unreachable — skipped dispatch of %s (re-trigger later)", task.name)
        return None
    try:
        return task.delay(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        log.warning("dispatch failed for %s: %s", task.name, exc)
        return None
