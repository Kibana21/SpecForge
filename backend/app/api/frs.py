"""FRS (Functional Requirements Specification) API router — Stage A.

Stage B endpoints (per-spec figma-link, per-spec regenerate, design-module) are
added when Stage B ships.
"""
from __future__ import annotations

import uuid
from uuid import UUID
from typing import Any

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_project_or_404
from app.db import get_db
from app.models.artifact import ArtifactDocument
from app.models.project import Project
from app.models.user import User
from app.schemas.envelope import err, ok
from app.services.artifacts.frs_orchestrator import (
    delete_frs_row,
    edit_frs_row,
    generate_frs_all,
    generate_frs_modularize,
    get_frs_detail,
    get_frs_row_history,
    reset_frs_generating,
    resolve_frs_decision,
    restore_frs_row,
    save_frs_answer,
    unlock_frs_row,
    _ensure_frs_document,
)
from app.services.artifacts.manifest.frs import FRS_TABLE_MAP

router = APIRouter(tags=["frs"])

VALID_FRS_TABLES = set(FRS_TABLE_MAP.keys())


# ═══════════════════════════════════════════════════════════════════════════════
# GET detail
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/projects/{project_id}/artifacts/frs")
async def get_frs(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    detail = await get_frs_detail(project_id, db)
    return ok(detail)


# ═══════════════════════════════════════════════════════════════════════════════
# Readiness check
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/projects/{project_id}/artifacts/frs/readiness")
async def check_frs_readiness(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.context.project_context import gather_project_context
    bundle = await gather_project_context(project_id, db, artifact_type="frs")
    r = bundle.readiness
    return ok({
        "can_generate": r.can_generate,
        "blocking_reason": r.blocking_reason,
        "docs_all_ready": r.docs_all_ready,
        "docs_ready_count": r.docs_ready_count,
        "docs_total_count": r.docs_total_count,
        "docs_pending_names": r.docs_pending_names,
        "docs_failed_names": r.docs_failed_names,
        "cb_ready": r.cb_ready,
        "cb_status": r.cb_status,
        "brd_ready": r.brd_ready,
        "brd_status": r.brd_status,
        "brd_summary": {
            "br_count": len(bundle.brd.business_requirements) if bundle.brd else 0,
            "objective_count": len(bundle.brd.objectives) if bundle.brd else 0,
            "risk_count": len(bundle.brd.risks) if bundle.brd else 0,
            "kpi_count": len(bundle.brd.kpis) if bundle.brd else 0,
            "stakeholder_count": len(bundle.brd.stakeholders) if bundle.brd else 0,
        } if bundle.brd else None,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# Reset stuck generating status
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/projects/{project_id}/artifacts/frs/reset-generating")
async def reset_frs_generating_endpoint(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reset a stuck 'generating' status back to 'in_interview'. Safety hatch."""
    doc = await reset_frs_generating(project_id, db)
    await db.commit()
    return ok({"status": doc.status, "doc_id": str(doc.id)})


# ═══════════════════════════════════════════════════════════════════════════════
# Generate (full pipeline: Stage A modularize)
# ═══════════════════════════════════════════════════════════════════════════════


class _FrsGenerateIn(BaseModel):
    brief: str | None = None


@router.post("/projects/{project_id}/artifacts/frs/generate")
async def generate_frs_endpoint(
    project_id: UUID,
    body: _FrsGenerateIn = Body(default_factory=_FrsGenerateIn),
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger the FRS Stage A pipeline (modularize).

    In mock mode runs in-process. In production dispatches to Celery and returns
    immediately with status='generating' so the client can poll for progress.
    """
    from app.config import get_settings
    from app.services.context.project_context import gather_project_context

    bundle = await gather_project_context(project_id, db, artifact_type="frs")
    if not bundle.readiness.can_generate:
        err("frs_not_ready", bundle.readiness.blocking_reason or "Not ready", 409)

    settings = get_settings()
    if settings.llm_provider == "mock":
        detail = await generate_frs_all(project, db, brief=body.brief)
        return ok(detail)

    # Production: persist initial brief, mark generating, dispatch to Celery
    doc = await _ensure_frs_document(project_id, db)
    if body.brief and body.brief.strip():
        from app.models.artifact import ArtifactMessage
        from app.services.artifacts.frs_orchestrator import _next_frs_seq
        seq = await _next_frs_seq(doc.id, db)
        db.add(ArtifactMessage(
            document_id=doc.id, project_id=project_id, role="user",
            content=body.brief.strip(), citations=[],
            meta={"is_initial_brief": True}, seq=seq,
        ))
    doc.unit_status = {}
    doc.status = "generating"
    await db.commit()

    from workers.dispatch import dispatch
    from workers.tasks import generate_frs
    dispatch(generate_frs, str(project_id))

    return ok(await get_frs_detail(project_id, db))


# ═══════════════════════════════════════════════════════════════════════════════
# Re-run modularize (Stage A only)
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/projects/{project_id}/artifacts/frs/modularize")
async def modularize_frs_endpoint(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-run the modularize unit. Locked modules preserved verbatim."""
    from app.config import get_settings
    from app.services.context.project_context import gather_project_context

    bundle = await gather_project_context(project_id, db, artifact_type="frs")
    if not bundle.readiness.can_generate:
        err("frs_not_ready", bundle.readiness.blocking_reason or "Not ready", 409)

    doc = await _ensure_frs_document(project_id, db)
    settings = get_settings()
    if settings.llm_provider == "mock":
        doc.status = "generating"
        await db.commit()
        await generate_frs_modularize(project, doc, bundle, db)
        doc.status = "in_interview"
        await db.commit()
        return ok(await get_frs_detail(project_id, db))

    doc.status = "generating"
    await db.commit()
    from workers.dispatch import dispatch
    from workers.tasks import generate_frs
    dispatch(generate_frs, str(project_id))
    return ok(await get_frs_detail(project_id, db))


# ═══════════════════════════════════════════════════════════════════════════════
# Save user answer (refine)
# ═══════════════════════════════════════════════════════════════════════════════


class _FrsAnswerIn(BaseModel):
    answer: str
    seq: int | None = None


@router.post("/projects/{project_id}/artifacts/frs/answer")
async def answer_frs_question(
    project_id: UUID,
    body: _FrsAnswerIn,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist a user free-text answer. In production, dispatches a regen task."""
    from app.config import get_settings

    await save_frs_answer(project_id, body.answer, db, body.seq)
    await db.commit()

    settings = get_settings()
    if settings.llm_provider != "mock":
        from workers.dispatch import dispatch
        from workers.tasks import generate_frs
        # For Stage A, any answer triggers a re-modularize
        dispatch(generate_frs, str(project_id))

    return ok(await get_frs_detail(project_id, db))


# ═══════════════════════════════════════════════════════════════════════════════
# Validate (Stage A only for now)
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/projects/{project_id}/artifacts/frs/validate")
async def validate_frs_endpoint(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run Stage-A validation. Returns findings; commits status='validated' if clean.

    For Stage-A-only mode, 'validated' means "ready for Stage B".
    """
    from app.services.artifacts.validators.frs import run_frs_validation, summarize_findings

    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == "frs",
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        err("frs_not_found", "No FRS artifact exists for this project.", 404)

    findings = await run_frs_validation(doc.id, doc, db)
    summary = summarize_findings(findings)

    if summary["blocking"] > 0:
        return ok({
            "ok": False,
            "summary": summary,
            "findings": findings,
        })

    # Clean — mark stage_a_approved (used by Stage B to know when to start)
    doc.unit_status = {**(doc.unit_status or {}), "_stage_a_approved": True}
    await db.commit()
    return ok({
        "ok": True,
        "summary": summary,
        "findings": findings,
    })


@router.get("/projects/{project_id}/artifacts/frs/findings")
async def get_frs_findings(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Read-only validation report (drives 'Check & Validate' UI)."""
    from app.services.artifacts.validators.frs import run_frs_validation, summarize_findings

    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == "frs",
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        return ok({"summary": {"total": 0, "blocking": 0}, "findings": []})

    findings = await run_frs_validation(doc.id, doc, db)
    return ok({
        "summary": summarize_findings(findings),
        "findings": findings,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# Decision resolution
# ═══════════════════════════════════════════════════════════════════════════════


class _FrsDecisionResolveIn(BaseModel):
    chosen_index: int
    status: str   # accepted_ai | overridden | dismissed


@router.post("/projects/{project_id}/artifacts/frs/decisions/{decision_row_id}/resolve")
async def resolve_frs_decision_endpoint(
    project_id: UUID,
    decision_row_id: UUID,
    body: _FrsDecisionResolveIn,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.status not in ("accepted_ai", "overridden", "dismissed"):
        err("invalid_status", "status must be accepted_ai | overridden | dismissed", 400)

    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == "frs",
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        err("frs_not_found", "No FRS artifact exists for this project.", 404)

    try:
        new_row = await resolve_frs_decision(
            doc.id, decision_row_id,
            chosen_index=body.chosen_index,
            resolution_status=body.status,
            db=db,
            user_id=current_user.id,
        )
    except ValueError as e:
        err("decision_not_found", str(e), 404)
    await db.commit()
    return ok({"row_key": new_row.row_key, "resolution_status": new_row.resolution_status})


# ═══════════════════════════════════════════════════════════════════════════════
# Generic row CRUD (works for any FRS table)
# ═══════════════════════════════════════════════════════════════════════════════


class _FrsRowEditIn(BaseModel):
    fields: dict[str, Any]
    lock: bool = False
    expected_version: int | None = None


@router.post("/projects/{project_id}/artifacts/frs/{table}/{row_id}/edit")
async def edit_frs_row_endpoint(
    project_id: UUID,
    table: str,
    row_id: UUID,
    body: _FrsRowEditIn,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if table not in VALID_FRS_TABLES:
        err("invalid_table", f"Unknown FRS table: {table}", 400)
    try:
        new_row = await edit_frs_row(
            project_id, table, row_id, body.fields, db,
            user_id=current_user.id,
            lock=body.lock,
            expected_version=body.expected_version,
        )
        await db.commit()
        # Return the new row id + version for the client to optimistically reconcile
        return ok({"id": str(new_row.id), "row_key": new_row.row_key, "version": new_row.version})
    except ValueError as e:
        msg = str(e)
        if msg.startswith("version_conflict"):
            err("version_conflict", msg, 409)
        if msg.startswith("row_locked"):
            err("row_locked", msg, 409)
        err("row_not_found", msg, 404)


@router.post("/projects/{project_id}/artifacts/frs/{table}/{row_id}/delete")
async def delete_frs_row_endpoint(
    project_id: UUID,
    table: str,
    row_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if table not in VALID_FRS_TABLES:
        err("invalid_table", f"Unknown FRS table: {table}", 400)
    try:
        await delete_frs_row(project_id, table, row_id, db)
        await db.commit()
        return ok({"deleted": True})
    except ValueError as e:
        msg = str(e)
        if msg.startswith("row_locked"):
            err("row_locked", msg, 409)
        err("row_not_found", msg, 404)


@router.post("/projects/{project_id}/artifacts/frs/{table}/{row_id}/unlock")
async def unlock_frs_row_endpoint(
    project_id: UUID,
    table: str,
    row_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if table not in VALID_FRS_TABLES:
        err("invalid_table", f"Unknown FRS table: {table}", 400)
    try:
        await unlock_frs_row(project_id, table, row_id, db)
        await db.commit()
        return ok({"unlocked": True})
    except ValueError as e:
        err("row_not_found", str(e), 404)


@router.post("/projects/{project_id}/artifacts/frs/{table}/{row_id}/restore")
async def restore_frs_row_endpoint(
    project_id: UUID,
    table: str,
    row_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if table not in VALID_FRS_TABLES:
        err("invalid_table", f"Unknown FRS table: {table}", 400)
    try:
        new_row = await restore_frs_row(
            project_id, table, row_id, db, user_id=current_user.id,
        )
        await db.commit()
        return ok({"id": str(new_row.id), "row_key": new_row.row_key, "version": new_row.version})
    except ValueError as e:
        err("row_not_found", str(e), 404)


@router.get("/projects/{project_id}/artifacts/frs/{table}/{row_id}/history")
async def get_frs_row_history_endpoint(
    project_id: UUID,
    table: str,
    row_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if table not in VALID_FRS_TABLES:
        err("invalid_table", f"Unknown FRS table: {table}", 400)
    try:
        history = await get_frs_row_history(project_id, table, row_id, db)
        return ok(history)
    except ValueError as e:
        err("row_not_found", str(e), 404)


# ═══════════════════════════════════════════════════════════════════════════════
# Discover phase (FRS catalog, 12 questions, 9 categories)
# ═══════════════════════════════════════════════════════════════════════════════
# Reuse the existing discover pattern from the BRD/CB routes.
# Catalog routing via get_catalog_for_artifact('frs').


@router.post("/projects/{project_id}/artifacts/frs/discover/analyze")
async def frs_discover_analyze(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the FRS discover catalog (12 questions across 9 categories).

    Stage-A v1: returns the catalog as-is. The AI-inference path (pre-filling
    answers from BRD + apps + docs) lives in the discover service and will be
    wired in when the discover UI surface is built.
    """
    from app.services.artifacts.discover_catalog import (
        FRS_DISCOVER_CATEGORIES, FRS_DISCOVER_QUESTIONS,
    )
    return ok({
        "categories": FRS_DISCOVER_CATEGORIES,
        "questions": FRS_DISCOVER_QUESTIONS,
    })


class _FrsDiscoverAnswerIn(BaseModel):
    answer: str


@router.post("/projects/{project_id}/artifacts/frs/discover/{q_key}/answer")
async def frs_discover_answer(
    project_id: UUID,
    q_key: str,
    body: _FrsDiscoverAnswerIn,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist a user answer to a discover question."""
    from app.services.artifacts.discover_catalog import FRS_QUESTION_BY_KEY
    if q_key not in FRS_QUESTION_BY_KEY:
        err("invalid_question_key", f"Unknown FRS discover question: {q_key}", 400)

    doc = await _ensure_frs_document(project_id, db)
    from app.models.artifact import ArtifactMessage
    from app.services.artifacts.frs_orchestrator import _next_frs_seq
    seq = await _next_frs_seq(doc.id, db)

    # Persist as a Q/A pair: question + user answer
    q_meta = FRS_QUESTION_BY_KEY[q_key]
    db.add(ArtifactMessage(
        document_id=doc.id, project_id=project_id, role="question",
        content=q_meta["text"], citations=[],
        meta={"unit_key": "modularize", "type": "discover", "question_key": q_key,
              "category": q_meta["category"]},
        seq=seq,
    ))
    db.add(ArtifactMessage(
        document_id=doc.id, project_id=project_id, role="user",
        content=body.answer, citations=[],
        meta={"unit_key": "modularize", "type": "discover_answer", "question_key": q_key},
        seq=seq + 1,
    ))
    await db.commit()
    return ok({"q_key": q_key, "answered": True})


class _FrsDiscoverEnhanceIn(BaseModel):
    brief: str


@router.post("/projects/{project_id}/artifacts/frs/discover/enhance")
async def frs_discover_enhance(
    project_id: UUID,
    body: _FrsDiscoverEnhanceIn,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """LLM-polish a draft FRS brief. v1: returns the brief unchanged in mock mode.

    Real LLM path uses the same discover-enhance pattern as BRD/CB.
    """
    from app.config import get_settings
    settings = get_settings()
    if settings.llm_provider == "mock":
        # Hand-crafted enhancement: add a structure hint
        enhanced = (
            f"{body.brief.strip()}\n\n"
            f"Focus modules on: customer-facing intake flows, identity verification, "
            f"backend orchestration, and notifications. Hoist common error envelope "
            f"and audit conventions into a Cross-cutting Standards module."
        )
        return ok({"enhanced": enhanced})
    # Real LLM path TBD: route through dspy_frs.run_enhance_brief
    return ok({"enhanced": body.brief})
