"""NFR (Non-Functional Requirements) API router.

Standalone artifact gated on a validated BRD. Core generation runs on Celery
(mock mode runs in-process). Every row in every section is editable / addable /
deletable. An optional ad-hoc brief on the landing page can be AI-enhanced.
"""
from __future__ import annotations

import asyncio
import uuid
from uuid import UUID

from fastapi import APIRouter, Body, Depends
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_project_or_404, require_artifact_validated
from app.db import get_db
from app.models.artifact import ArtifactDocument
from app.models.project import Project
from app.models.user import User
from app.schemas.envelope import err, ok
from app.services.artifacts.nfr_orchestrator import (
    NFR_TABLE_MAP,
    add_nfr_row,
    delete_nfr_row,
    edit_nfr_row,
    get_nfr_detail,
    get_nfr_row_history,
    restore_nfr_row,
    save_nfr_answer,
    unlock_nfr_row,
    validate_nfr,
)

router = APIRouter(tags=["nfr"])

VALID_NFR_TABLES = set(NFR_TABLE_MAP.keys())

# NFR unlocks only once the BRD is validated (standalone, parallel to FRS).
_brd_gate = Depends(require_artifact_validated("brd"))


# ── GET detail ───────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/artifacts/nfr")
async def get_nfr(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ok(await get_nfr_detail(project_id, db))


# ── Readiness ──────────────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/artifacts/nfr/readiness")
async def check_nfr_readiness(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.context.project_context import gather_project_context
    bundle = await gather_project_context(project_id, db, artifact_type="nfr")
    r = bundle.readiness
    return ok({
        "can_generate": r.can_generate,
        "blocking_reason": r.blocking_reason,
        "docs_all_ready": r.docs_all_ready,
        "cb_ready": r.cb_ready,
        "cb_status": r.cb_status,
        "brd_ready": r.brd_ready,
        "brd_status": r.brd_status,
        "docs": [
            {"id": e.doc_id, "filename": e.filename, "indexing_status": e.indexing_status,
             "page_count": e.page_count}
            for e in bundle.docs.inventory
        ],
    })


# ── Reset stuck generating status ──────────────────────────────────────────────

@router.post("/projects/{project_id}/artifacts/nfr/reset-generating")
async def reset_nfr_generating(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == "nfr",
                ArtifactDocument.status == "generating",
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        err("not_generating", "NFR is not currently in generating state.", 400)
    doc.status = "in_interview"
    await db.commit()
    return ok({"status": "in_interview", "doc_id": str(doc.id)})


# ── AI-enhance the optional ad-hoc brief (landing page) ─────────────────────────

class _NfrEnhanceIn(BaseModel):
    brief_text: str


@router.post("/projects/{project_id}/artifacts/nfr/enhance", dependencies=[_brd_gate])
async def nfr_enhance_brief(
    project_id: UUID,
    body: _NfrEnhanceIn,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.artifacts.discover import enhance_brief
    try:
        result = await asyncio.wait_for(enhance_brief(project, "nfr", body.brief_text, db), timeout=60.0)
        return ok(result)
    except asyncio.TimeoutError:
        err("enhance_timeout", "Enhancement timed out — try again or shorten your brief", 504)
    except Exception as e:  # noqa: BLE001
        err("enhance_failed", str(e), 500)


# ── Generate (Celery) ───────────────────────────────────────────────────────────

class _NfrGenerateIn(BaseModel):
    brief: str | None = None


@router.post("/projects/{project_id}/artifacts/nfr/generate", dependencies=[_brd_gate])
async def generate_nfr_endpoint(
    project_id: UUID,
    body: _NfrGenerateIn = Body(default_factory=_NfrGenerateIn),
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.config import get_settings
    from app.services.artifacts.nfr_orchestrator import _ensure_nfr_document, generate_nfr_all
    from app.services.context.project_context import gather_project_context

    bundle = await gather_project_context(project_id, db, artifact_type="nfr")
    if not bundle.readiness.can_generate:
        err("nfr_not_ready", bundle.readiness.blocking_reason or "Not ready", 409)

    settings = get_settings()
    if settings.llm_provider == "mock":
        return ok(await generate_nfr_all(project, db, brief=body.brief))

    doc = await _ensure_nfr_document(project_id, db)
    doc.unit_status = {}
    doc.status = "generating"
    await db.commit()

    from workers.dispatch import dispatch
    from workers.tasks import generate_nfr
    task = dispatch(generate_nfr, str(project_id), body.brief)
    if task is None:
        doc.status = "in_interview"
        await db.commit()
        err("worker_unavailable", "Generation worker is not reachable. Start the Celery worker and retry.", 503)
    return ok(await get_nfr_detail(project_id, db))


# ── Regenerate a single unit (Celery) ───────────────────────────────────────────

@router.post("/projects/{project_id}/artifacts/nfr/units/{unit_key}/regenerate", dependencies=[_brd_gate])
async def regenerate_nfr_unit_endpoint(
    project_id: UUID,
    unit_key: str,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.config import get_settings
    from app.services.artifacts.manifest.nfr import NFR_MANIFEST_BY_KEY
    from app.services.artifacts.nfr_orchestrator import (
        _ensure_nfr_document, _read_initial_brief, generate_nfr_unit,
    )
    from app.services.context.project_context import gather_project_context

    if unit_key not in NFR_MANIFEST_BY_KEY:
        err("invalid_unit", f"Unknown NFR unit: {unit_key}", 400)

    settings = get_settings()
    if settings.llm_provider == "mock":
        doc = await _ensure_nfr_document(project_id, db)
        brief = await _read_initial_brief(doc.id, db)
        bundle = await gather_project_context(project_id, db, artifact_document_id=doc.id, artifact_type="nfr")
        await generate_nfr_unit(project, unit_key, doc, bundle, db, brief=brief)
        await db.commit()
        return ok({"unit_key": unit_key, "status": "regenerated"})

    doc = await _ensure_nfr_document(project_id, db)
    doc.status = "generating"
    await db.commit()
    from workers.dispatch import dispatch
    from workers.tasks import regenerate_nfr_unit
    task = dispatch(regenerate_nfr_unit, str(project_id), unit_key)
    if task is None:
        doc.status = "in_interview"
        await db.commit()
        err("worker_unavailable", "Generation worker is not reachable. Start the Celery worker and retry.", 503)
    return ok(await get_nfr_detail(project_id, db))


# ── Save answer ─────────────────────────────────────────────────────────────────

class _NfrAnswerIn(BaseModel):
    answer: str
    seq: int | None = None


@router.post("/projects/{project_id}/artifacts/nfr/answer", dependencies=[_brd_gate])
async def answer_nfr_question(
    project_id: UUID,
    body: _NfrAnswerIn,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ok(await save_nfr_answer(project_id, body.answer, db, body.seq))


# ── Validate ──────────────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/artifacts/nfr/validate", dependencies=[_brd_gate])
async def validate_nfr_endpoint(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = await validate_nfr(project_id, db, current_user.id)
    except ValueError as e:
        err("not_found", str(e), 404)
    if not result["ok"]:
        err("validation_failed", "NFR validation failed — see findings for details.", 409,
            details={"findings": result["findings"]})
    return ok(result)


# ── Findings (no status change) ─────────────────────────────────────────────────

@router.get("/projects/{project_id}/artifacts/nfr/findings")
async def get_nfr_findings(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.artifacts.validators.nfr import run_nfr_validation
    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == "nfr",
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        return ok({"findings": [], "summary": {"total": 0, "critical": 0, "major": 0, "minor": 0, "warnings": 0, "blocking": 0}})
    findings = await run_nfr_validation(doc.id, doc, db)
    summary = {
        "total": len(findings),
        "critical": sum(1 for f in findings if f["group"] == "critical"),
        "major": sum(1 for f in findings if f["group"] == "major"),
        "minor": sum(1 for f in findings if f["group"] == "minor"),
        "warnings": sum(1 for f in findings if f["group"] == "warnings"),
        "blocking": sum(1 for f in findings if f["group"] in ("critical", "major")),
    }
    return ok({"findings": findings, "summary": summary})


# ── Add a row to ANY section ────────────────────────────────────────────────────

class _NfrAddIn(BaseModel):
    fields: dict
    brd_links: list[dict] | None = None


@router.post("/projects/{project_id}/artifacts/nfr/{table}/add", dependencies=[_brd_gate])
async def add_nfr_row_endpoint(
    project_id: UUID,
    table: str,
    body: _NfrAddIn,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if table not in VALID_NFR_TABLES:
        err("invalid_table", f"Unknown NFR table: {table}", 400)
    from app.services.artifacts.nfr_orchestrator import _ensure_nfr_document
    doc = await _ensure_nfr_document(project_id, db)
    # Validate BRD links resolve to active BRD rows.
    if table == "nfr_requirements" and body.brd_links:
        await _validate_brd_links(project_id, body.brd_links, db)
    try:
        result = await add_nfr_row(doc.id, table, body.fields, db, current_user.id, brd_links=body.brd_links)
        await db.commit()
        return ok(result)
    except ValueError as e:
        err("invalid_request", str(e), 400)


async def _validate_brd_links(project_id: UUID, links: list[dict], db: AsyncSession) -> None:
    from app.models.brd import BrdBusinessRequirement, BrdObjective
    brd_doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == "brd",
            )
        )
    ).scalar_one_or_none()
    if brd_doc is None:
        err("invalid_link", "No BRD to link to.", 422)
    model_by_kind = {"brd_objective": BrdObjective, "brd_business_requirement": BrdBusinessRequirement}
    for link in links:
        model = model_by_kind.get(link.get("target_kind"))
        if model is None:
            continue  # other kinds (kpi/risk/text_block) are not strictly validated here
        exists = (
            await db.execute(
                select(model.id).where(
                    model.document_id == brd_doc.id,
                    model.row_key == link.get("target_ref"),
                    model.is_current.is_(True),
                    model.status == "active",
                )
            )
        ).scalar_one_or_none()
        if exists is None:
            err("invalid_link", f"BRD row '{link.get('target_ref')}' not found.", 422)


# ── Row edit ──────────────────────────────────────────────────────────────────

class _NfrRowEditIn(BaseModel):
    fields: dict
    lock: bool = True


@router.post("/projects/{project_id}/artifacts/nfr/{table}/{row_id}/edit", dependencies=[_brd_gate])
async def edit_nfr_row_endpoint(
    project_id: UUID,
    table: str,
    row_id: UUID,
    body: _NfrRowEditIn,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if table not in VALID_NFR_TABLES:
        err("invalid_table", f"Unknown NFR table: {table}", 400)
    try:
        result = await edit_nfr_row(table, row_id, body.fields, db, current_user.id, body.lock)
        await db.commit()
        return ok(result)
    except ValueError as e:
        err("not_found", str(e), 404)


# ── Row delete (soft) ───────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/artifacts/nfr/{table}/{row_id}/delete", dependencies=[_brd_gate])
async def delete_nfr_row_endpoint(
    project_id: UUID,
    table: str,
    row_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if table not in VALID_NFR_TABLES:
        err("invalid_table", f"Unknown NFR table: {table}", 400)
    try:
        result = await delete_nfr_row(table, row_id, db)
        await db.commit()
        return ok(result)
    except ValueError as e:
        err("conflict", str(e), 409)


# ── Row unlock ──────────────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/artifacts/nfr/{table}/{row_id}/unlock", dependencies=[_brd_gate])
async def unlock_nfr_row_endpoint(
    project_id: UUID,
    table: str,
    row_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if table not in VALID_NFR_TABLES:
        err("invalid_table", f"Unknown NFR table: {table}", 400)
    try:
        result = await unlock_nfr_row(table, row_id, db)
        await db.commit()
        return ok(result)
    except ValueError as e:
        err("not_found", str(e), 404)


# ── Row restore ─────────────────────────────────────────────────────────────────

class _NfrRowRestoreIn(BaseModel):
    version: int


@router.post("/projects/{project_id}/artifacts/nfr/{table}/{row_id}/restore", dependencies=[_brd_gate])
async def restore_nfr_row_endpoint(
    project_id: UUID,
    table: str,
    row_id: UUID,
    body: _NfrRowRestoreIn,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if table not in VALID_NFR_TABLES:
        err("invalid_table", f"Unknown NFR table: {table}", 400)
    model = NFR_TABLE_MAP[table]
    row = await db.get(model, row_id)
    if row is None:
        err("not_found", f"Row {row_id} not found", 404)
    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == "nfr",
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        err("not_found", "NFR document not found", 404)
    try:
        result = await restore_nfr_row(table, doc.id, row.row_key, body.version, db, current_user.id)
        await db.commit()
        return ok(result)
    except ValueError as e:
        err("not_found", str(e), 404)


# ── Row history ─────────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/artifacts/nfr/{table}/{row_id}/history")
async def nfr_row_history(
    project_id: UUID,
    table: str,
    row_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if table not in VALID_NFR_TABLES:
        err("invalid_table", f"Unknown NFR table: {table}", 400)
    model = NFR_TABLE_MAP[table]
    row = await db.get(model, row_id)
    if row is None:
        err("not_found", f"Row {row_id} not found in {table}", 404)
    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == "nfr",
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        return ok([])
    return ok(await get_nfr_row_history(table, doc.id, row.row_key, db))


# ── Export markdown ─────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/artifacts/nfr/export")
async def export_nfr(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.export.nfr_markdown import export_nfr_markdown
    detail = await get_nfr_detail(project_id, db)
    if detail.get("document") is None:
        err("not_found", "NFR document not found", 404)
    md = export_nfr_markdown(detail, project)
    slug = project.name.lower().replace(" ", "-")[:40]
    return PlainTextResponse(
        md,
        headers={"Content-Disposition": f'attachment; filename="nfr-{slug}.md"'},
        media_type="text/markdown",
    )
