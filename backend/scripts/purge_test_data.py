#!/usr/bin/env python3
"""
Purge test/demo clutter from the dev database — projects and apps NOT in the
keep-list. FK ON DELETE CASCADE removes their documents, trees, chunks, facts,
RU, interview messages, assumptions, specs, etc. Users are never touched.

Dry-run by default (prints what WOULD be deleted). Add --apply to execute.

    cd backend && .venv/bin/python scripts/purge_test_data.py          # preview
    cd backend && .venv/bin/python scripts/purge_test_data.py --apply  # delete
"""
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.models.app import App  # noqa: E402
from app.models.project import Project  # noqa: E402

# Projects to KEEP (by human_id). Everything else is treated as test clutter.
KEEP_PROJECT_HUMAN_IDS = {"PRJ-0001"}

# Test APPS are created by the suite with a random hex suffix (e.g. pay1a2b3c4d).
# Only these are deleted — any clean-named app (ipos, payhub, claimsezy, …) is kept.
_TEST_APP_RE = re.compile(r"^(hyb|prc|pay|clm|sg)[0-9a-f]{8}$")


async def purge(apply: bool) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as db:
        projects = (await db.execute(select(Project))).scalars().all()
        apps = (await db.execute(select(App))).scalars().all()

        del_projects = [p for p in projects if p.human_id not in KEEP_PROJECT_HUMAN_IDS]
        del_apps = [a for a in apps if _TEST_APP_RE.match(a.short_name)]

        print(f"Projects: {len(projects)} total → delete {len(del_projects)}, keep {len(projects) - len(del_projects)}")
        for p in del_projects[:40]:
            print(f"  - {p.human_id or '(no id)':10} {p.name}")
        if len(del_projects) > 40:
            print(f"  … and {len(del_projects) - 40} more")
        print(f"\nApps: {len(apps)} total → delete {len(del_apps)}, keep {len(apps) - len(del_apps)}")
        for a in del_apps:
            print(f"  - {a.short_name:12} {a.name}")
        kept_apps = sorted(a.short_name for a in apps if not _TEST_APP_RE.match(a.short_name))
        print(f"\nKeeping projects {sorted(KEEP_PROJECT_HUMAN_IDS)}.")
        print(f"Keeping apps: {kept_apps}")

        if not apply:
            print("\nDRY RUN — re-run with --apply to delete. Nothing changed.")
            await engine.dispose()
            return

        if del_projects:
            await db.execute(delete(Project).where(Project.id.in_([p.id for p in del_projects])))
        if del_apps:
            await db.execute(delete(App).where(App.id.in_([a.id for a in del_apps])))
        await db.commit()
        print(f"\nDeleted {len(del_projects)} projects and {len(del_apps)} apps (cascaded children).")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(purge(apply="--apply" in sys.argv))
