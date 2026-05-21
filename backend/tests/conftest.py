"""
Shared pytest fixtures for API tests.
Requires a running PostgreSQL with schema applied (alembic upgrade head).
"""
import os
import uuid

# Must be set before any app imports so db.py uses NullPool and settings pick up mock provider
os.environ["TEST_DATABASE"] = "1"
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("JWT_SECRET", "test-secret-not-used-directly")
os.environ.setdefault("BCRYPT_ROUNDS", "4")  # fast hashing in tests

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def client():
    from app.main import app
    from app.core.rbac import get_current_user
    from app.core.security import hash_password
    from app.db import AsyncSessionLocal
    from app.models.project import Project
    from app.models.user import User
    from sqlalchemy import delete

    test_user_id = uuid.uuid4()

    # Persist a real user row so owner_id FK constraints are satisfied
    async with AsyncSessionLocal() as db:
        db.add(User(
            id=test_user_id,
            email=f"test-{test_user_id}@specforge.test",
            display_name="Test User",
            password_hash=hash_password("test"),
            role="platform_admin",
            status="active",
        ))
        await db.commit()

    # Inject a detached User object — no session needed for attribute access
    test_user = User(
        id=test_user_id,
        email=f"test-{test_user_id}@specforge.test",
        display_name="Test User",
        role="platform_admin",
        status="active",
    )

    # Bypass JWT + Redis — return the pre-built user for every request
    app.dependency_overrides[get_current_user] = lambda: test_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()

    # Teardown: delete test user's projects (cascades to docs/specs/gaps/reviews) then the user
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Project).where(Project.owner_id == test_user_id))
        await db.execute(delete(User).where(User.id == test_user_id))
        await db.commit()
