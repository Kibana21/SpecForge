from redis.asyncio import Redis

from app.config import get_settings

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def is_jti_revoked(jti: str) -> bool:
    try:
        r = get_redis()
        return bool(await r.sismember("revoked_jtis", jti))
    except Exception:
        return False


async def revoke_jti(jti: str, ttl_seconds: int = 900) -> None:
    try:
        r = get_redis()
        await r.sadd("revoked_jtis", jti)
        await r.expire("revoked_jtis", ttl_seconds)
    except Exception:
        pass
