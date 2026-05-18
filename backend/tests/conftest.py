"""
Shared pytest fixtures for API tests.
Requires a running PostgreSQL with schema applied (alembic upgrade head).
"""
import os

# Must be set before any app imports so db.py uses NullPool and settings pick up mock provider
os.environ["TEST_DATABASE"] = "1"
os.environ.setdefault("LLM_PROVIDER", "mock")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def client():
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
