"""SDLC Artifacts API — generic over artifact_type (concept-brief, brd, …)."""
from __future__ import annotations

import uuid
from uuid import UUID

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_project_or_404
from app.db import get_db
from app.models.artifact import ArtifactDocument, ArtifactSource
from app.models.project import Project
from app.models.user import User
from app.schemas.artifact import (
    AnswerIn, ArtifactDetailResponse, RowEditIn, RowRestoreIn,
    SourceToggleIn, UnitRegenerateIn, ValidationResponse,
)
from app.schemas.envelope import err, ok
from app.services.artifacts.orchestrator import (
    CB_TABLE_MAP, edit_row, get_artifact_detail,
    get_row_history, incorporate_answer, regenerate_unit, restore_row,
    unlock_row, validate,
)
from app.services.artifacts.orchestrator import _ensure_document as _orch_ensure_document

router = APIRouter(tags=["artifacts"])

_ARTIFACT_TYPE_MAP = {
    "concept-brief": "concept_brief",
}

VALID_TABLES = set(CB_TABLE_MAP.keys())


def _resolve_type(artifact_type_slug: str) -> str:
    t = _ARTIFACT_TYPE_MAP.get(artifact_type_slug)
    if t is None:
        err("invalid_artifact_type", f"Unknown artifact type: {artifact_type_slug}", 400)
    return t  # type: ignore[return-value]


# ── GET detail ────────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/artifacts/{artifact_type}")
async def get_artifact(
    project_id: UUID,
    artifact_type: str,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    atype = _resolve_type(artifact_type)
    detail = await get_artifact_detail(project_id, atype, db)
    return ok(detail)


# ── Generate all ──────────────────────────────────────────────────────────────

class _GenerateIn(BaseModel):
    context: str | None = None


@router.post("/projects/{project_id}/artifacts/{artifact_type}/generate")
async def generate_artifact(
    project_id: UUID,
    artifact_type: str,
    body: _GenerateIn = Body(default_factory=_GenerateIn),
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_project_or_404),
    _user: User = Depends(get_current_user),
):
    from app.config import get_settings
    atype = _resolve_type(artifact_type)
    if get_settings().llm_provider == "mock":
        from app.services.artifacts.orchestrator import generate_all
        detail = await generate_all(project, atype, db, context=body.context)
        return ok(detail)
    doc = await _orch_ensure_document(project.id, atype, db)
    doc.status = "generating"
    await db.commit()
    from workers.dispatch import dispatch
    from workers.tasks import generate_concept_brief
    dispatch(generate_concept_brief, str(project.id), atype, body.context)
    return ok(await get_artifact_detail(project.id, atype, db))


# ── Generate/regenerate individual unit ───────────────────────────────────────

@router.post("/projects/{project_id}/artifacts/{artifact_type}/units/{unit_key}/generate")
async def generate_unit_endpoint(
    project_id: UUID,
    artifact_type: str,
    unit_key: str,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.artifacts.manifest.concept_brief import MANIFEST_BY_KEY
    from app.services.artifacts.orchestrator import _ensure_document, generate_unit, refresh_gate
    atype = _resolve_type(artifact_type)
    if unit_key not in MANIFEST_BY_KEY:
        err("invalid_unit", f"Unknown unit: {unit_key}", 400)
    doc = await _ensure_document(project_id, atype, db)
    await generate_unit(project, unit_key, doc, db)
    await refresh_gate(doc, db)
    await db.commit()
    return ok(await get_artifact_detail(project_id, atype, db))


@router.post("/projects/{project_id}/artifacts/{artifact_type}/units/{unit_key}/regenerate")
async def regenerate_unit_endpoint(
    project_id: UUID,
    artifact_type: str,
    unit_key: str,
    body: UnitRegenerateIn,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.artifacts.manifest.concept_brief import MANIFEST_BY_KEY
    atype = _resolve_type(artifact_type)
    if unit_key not in MANIFEST_BY_KEY:
        err("invalid_unit", f"Unknown unit: {unit_key}", 400)
    detail = await regenerate_unit(project, unit_key, atype, body.directive, db)
    return ok(detail)


# ── Answer a question ─────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/artifacts/{artifact_type}/answer")
async def answer_question(
    project_id: UUID,
    artifact_type: str,
    body: AnswerIn,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    atype = _resolve_type(artifact_type)
    detail = await incorporate_answer(project_id, atype, body.answer, db, body.seq)
    return ok(detail)


# ── Row history ───────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/artifacts/{artifact_type}/units/{unit_key}/rows/{row_key}/history")
async def row_history(
    project_id: UUID,
    artifact_type: str,
    unit_key: str,
    row_key: str,
    table: str,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if table not in VALID_TABLES:
        err("invalid_table", f"Unknown table: {table}", 400)
    atype = _resolve_type(artifact_type)
    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == atype,
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        return ok([])
    history = await get_row_history(table, doc.id, row_key, db)
    return ok(history)


# ── Row PATCH / restore / unlock ──────────────────────────────────────────────

@router.patch("/projects/{project_id}/artifacts/{artifact_type}/rows/{table}/{row_id}")
async def patch_row(
    project_id: UUID,
    artifact_type: str,
    table: str,
    row_id: UUID,
    body: RowEditIn,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if table not in VALID_TABLES:
        err("invalid_table", f"Unknown table: {table}", 400)
    _resolve_type(artifact_type)
    try:
        result = await edit_row(table, row_id, body.fields, db, current_user.id, body.lock)
        await db.commit()
        return ok(result)
    except ValueError as e:
        err("not_found", str(e), 404)


@router.post("/projects/{project_id}/artifacts/{artifact_type}/rows/{table}/{row_id}/restore")
async def restore_row_endpoint(
    project_id: UUID,
    artifact_type: str,
    table: str,
    row_id: UUID,
    body: RowRestoreIn,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if table not in VALID_TABLES:
        err("invalid_table", f"Unknown table: {table}", 400)
    _resolve_type(artifact_type)
    atype = _resolve_type(artifact_type)
    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == atype,
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        err("not_found", "Artifact document not found", 404)
    model = CB_TABLE_MAP[table]
    row = await db.get(model, row_id)
    if row is None:
        err("not_found", f"Row {row_id} not found", 404)
    try:
        result = await restore_row(table, doc.id, row.row_key, body.version, db, current_user.id)
        await db.commit()
        return ok(result)
    except ValueError as e:
        err("not_found", str(e), 404)


@router.post("/projects/{project_id}/artifacts/{artifact_type}/rows/{table}/{row_id}/unlock")
async def unlock_row_endpoint(
    project_id: UUID,
    artifact_type: str,
    table: str,
    row_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if table not in VALID_TABLES:
        err("invalid_table", f"Unknown table: {table}", 400)
    _resolve_type(artifact_type)
    try:
        result = await unlock_row(table, row_id, db)
        await db.commit()
        return ok(result)
    except ValueError as e:
        err("not_found", str(e), 404)


# ── Source material ───────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/artifacts/{artifact_type}/sources")
async def list_sources(
    project_id: UUID,
    artifact_type: str,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.document import Document
    atype = _resolve_type(artifact_type)
    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == atype,
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        return ok([])
    rows = (
        await db.execute(
            select(ArtifactSource, Document.filename, Document.parse_status)
            .join(Document, Document.id == ArtifactSource.source_document_id)
            .where(ArtifactSource.artifact_document_id == doc.id)
        )
    ).all()
    return ok([
        {"id": str(s.id), "source_document_id": str(s.source_document_id),
         "filename": fn, "parse_status": ps, "included": s.included}
        for s, fn, ps in rows
    ])


@router.patch("/projects/{project_id}/artifacts/{artifact_type}/sources/{source_id}")
async def toggle_source(
    project_id: UUID,
    artifact_type: str,
    source_id: UUID,
    body: SourceToggleIn,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _resolve_type(artifact_type)
    source = await db.get(ArtifactSource, source_id)
    if source is None:
        err("not_found", "Source not found", 404)
    source.included = body.included
    await db.commit()
    return ok({"id": str(source.id), "included": source.included})


# ── Validate ──────────────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/artifacts/{artifact_type}/validate")
async def validate_artifact(
    project_id: UUID,
    artifact_type: str,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    atype = _resolve_type(artifact_type)
    result = await validate(project_id, atype, db, current_user.id)
    if not result["ok"]:
        err("validation_failed", "Concept Brief validation failed", 409,
            details={"failures": result["failures"]})
    return ok(result)


# ── Export markdown ───────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/artifacts/{artifact_type}/export/markdown")
async def export_markdown(
    project_id: UUID,
    artifact_type: str,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    atype = _resolve_type(artifact_type)
    if atype == "concept_brief":
        from app.services.export.artifact_markdown import export_concept_brief
        md = await export_concept_brief(project_id, db)
        slug = project.name.lower().replace(" ", "-")[:40]
        return PlainTextResponse(
            md,
            headers={"Content-Disposition": f'attachment; filename="concept-brief-{slug}.md"'},
            media_type="text/markdown",
        )
    err("not_implemented", f"Export for {atype} not yet implemented", 501)
