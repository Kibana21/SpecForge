import difflib
import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.version_snapshot import VersionSnapshot


async def create_snapshot(
    db: AsyncSession,
    *,
    document_key: str,
    actor_id: Optional[uuid.UUID] = None,
    generation_type: str = "human",
    change_note: Optional[str] = None,
    changed_sections: Optional[dict] = None,
    change_count: int = 0,
    content_ref: Optional[str] = None,
    is_immutable: bool = False,
) -> VersionSnapshot:
    result = await db.execute(
        select(func.coalesce(func.max(VersionSnapshot.version_no), 0)).where(
            VersionSnapshot.document_key == document_key
        )
    )
    next_ver: int = result.scalar_one() + 1

    snap = VersionSnapshot(
        document_key=document_key,
        version_no=next_ver,
        actor_id=actor_id,
        generation_type=generation_type,
        change_note=change_note,
        changed_sections=changed_sections,
        change_count=change_count,
        content_ref=content_ref,
        is_immutable=is_immutable,
    )
    db.add(snap)
    await db.flush()
    return snap


async def get_timeline(db: AsyncSession, document_key: str) -> list[VersionSnapshot]:
    result = await db.execute(
        select(VersionSnapshot)
        .where(VersionSnapshot.document_key == document_key)
        .order_by(VersionSnapshot.version_no.desc())
    )
    return list(result.scalars().all())


async def get_version(
    db: AsyncSession, document_key: str, version_no: int
) -> Optional[VersionSnapshot]:
    result = await db.execute(
        select(VersionSnapshot).where(
            VersionSnapshot.document_key == document_key,
            VersionSnapshot.version_no == version_no,
        )
    )
    return result.scalar_one_or_none()


def diff_content(a_text: str, b_text: str) -> dict:
    """Unified diff between two text strings. Returns additions/deletions counts."""
    a_lines = a_text.splitlines(keepends=True)
    b_lines = b_text.splitlines(keepends=True)
    diff_lines = list(difflib.unified_diff(a_lines, b_lines, fromfile="v_a", tofile="v_b", lineterm=""))
    additions = sum(1 for ln in diff_lines if ln.startswith("+") and not ln.startswith("+++"))
    deletions = sum(1 for ln in diff_lines if ln.startswith("-") and not ln.startswith("---"))
    return {
        "diff": "".join(diff_lines),
        "additions": additions,
        "deletions": deletions,
    }
