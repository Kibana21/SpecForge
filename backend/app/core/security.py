import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import HTTPException, status
from jose import JWTError, jwt

from app.config import get_settings

_DUMMY_HASH: bytes | None = None


def _get_dummy_hash() -> bytes:
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = bcrypt.hashpw(b"dummy-placeholder", bcrypt.gensalt(rounds=4))
    return _DUMMY_HASH


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(plain: str) -> str:
    settings = get_settings()
    hashed = bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=settings.bcrypt_rounds))
    return hashed.decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def bcrypt_dummy_verify() -> None:
    """Run a bcrypt verify to equalize timing when the user is not found during login."""
    bcrypt.checkpw(b"dummy", _get_dummy_hash())


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def generate_raw_token() -> str:
    return secrets.token_urlsafe(32)


def create_access_token(user_id: str, role: str) -> tuple[str, str]:
    """Returns (encoded_jwt, jti)."""
    settings = get_settings()
    now = now_utc()
    jti = str(uuid.uuid4())
    payload = {
        "sub": user_id,
        "role": role,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
        "iat": now,
        "jti": jti,
        "iss": "spec-forge",
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return token, jti


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            issuer="spec-forge",
            options={"require": ["exp", "iat", "sub", "jti", "iss"]},
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload
