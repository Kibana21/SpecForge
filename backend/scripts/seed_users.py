#!/usr/bin/env python3
"""
Seed one test user per role into the database.
Safe to re-run: skips if test users already exist.

Usage (from repo root):
    make seed
"""
import asyncio
import sys
from pathlib import Path

# Make app importable when run directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.core.security import hash_password
from app.models.user import User

SEED_USERS = [
    ("admin@specforge.test",      "platform_admin",       "Platform Admin"),
    ("analyst@specforge.test",    "business_analyst",     "Business Analyst"),
    ("owner@specforge.test",      "product_owner",        "Product Owner"),
    ("architect@specforge.test",  "solution_architect",   "Solution Architect"),
    ("appowner@specforge.test",   "app_owner",            "App Owner"),
    ("qa@specforge.test",         "qa_lead",              "QA Lead"),
    ("reviewer@specforge.test",   "compliance_reviewer",  "Compliance Reviewer"),
]
DEFAULT_PASSWORD = "SpecForge#Test2026!"


async def seed() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as db:
        result = await db.execute(select(User).where(User.is_test == True).limit(1))  # noqa: E712
        if result.scalar_one_or_none():
            print("Test users already seeded — skipping.")
            await engine.dispose()
            return

        for email, role, display_name in SEED_USERS:
            db.add(User(
                email=email,
                display_name=display_name,
                password_hash=hash_password(DEFAULT_PASSWORD),
                role=role,
                status="active",
                is_test=True,
            ))
        await db.commit()

    await engine.dispose()

    print(f"Seeded {len(SEED_USERS)} test users  (password: {DEFAULT_PASSWORD})")
    for email, role, _ in SEED_USERS:
        print(f"  {email:40s}  {role}")


if __name__ == "__main__":
    asyncio.run(seed())
