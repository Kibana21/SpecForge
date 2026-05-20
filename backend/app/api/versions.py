from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.rbac import get_current_user
from app.schemas.envelope import ok
from app.services.version_service import diff_content, get_timeline, get_version

router = APIRouter(
    prefix="/api/documents",
    tags=["versions"],
    dependencies=[Depends(get_current_user)],
)


def _snap_summary(s) -> dict:
    return {
        "id": str(s.id),
        "document_key": s.document_key,
        "version_no": s.version_no,
        "actor_id": str(s.actor_id) if s.actor_id else None,
        "created_at": s.created_at.isoformat(),
        "change_note": s.change_note,
        "change_count": s.change_count,
        "generation_type": s.generation_type,
        "is_immutable": s.is_immutable,
        "changed_sections": s.changed_sections,
    }


@router.get("/{document_key}/versions")
async def list_versions(
    document_key: str,
    db: AsyncSession = Depends(get_db),
):
    timeline = await get_timeline(db, document_key)
    return ok([_snap_summary(s) for s in timeline])


@router.get("/{document_key}/versions/compare")
async def compare_versions(
    document_key: str,
    a: int = Query(..., description="Version number A"),
    b: int = Query(..., description="Version number B"),
    db: AsyncSession = Depends(get_db),
):
    ver_a = await get_version(db, document_key, a)
    ver_b = await get_version(db, document_key, b)
    if not ver_a or not ver_b:
        raise HTTPException(404, "One or both versions not found")
    payload = diff_content(ver_a.content_ref or "", ver_b.content_ref or "")
    return ok({"document_key": document_key, "from_version": a, "to_version": b, **payload})


@router.get("/{document_key}/versions/{version_no}")
async def get_version_detail(
    document_key: str,
    version_no: int,
    db: AsyncSession = Depends(get_db),
):
    snap = await get_version(db, document_key, version_no)
    if not snap:
        raise HTTPException(404, "Version not found")
    return ok({**_snap_summary(snap), "content_ref": snap.content_ref})
