import asyncio
import logging
from datetime import datetime, timezone

from workers.celery_app import celery_app

log = logging.getLogger(__name__)


@celery_app.task(name="workers.tasks.ping", bind=True)
def ping(self) -> dict:
    log.info("ping task executed task_id=%s", self.request.id)
    return {"ok": True, "ts": datetime.now(timezone.utc).isoformat()}


@celery_app.task(name="workers.tasks.purge_expired_refresh_tokens")
def purge_expired_refresh_tokens() -> dict:
    return asyncio.run(_purge_expired_tokens())


async def _purge_expired_tokens() -> dict:
    from sqlalchemy import delete

    from app.db import AsyncSessionLocal
    from app.models.auth import RefreshToken

    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            delete(RefreshToken).where(RefreshToken.expires_at < now)
        )
        await db.commit()
        count = result.rowcount

    log.info("purged_expired_refresh_tokens count=%d", count)
    return {"ok": True, "purged": count}
