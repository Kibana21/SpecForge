"""BRD (Business Requirements Document) API router."""
from __future__ import annotations

import asyncio
import uuid
from uuid import UUID

from fastapi import APIRouter, Body, Depends
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_project_or_404
from app.db import get_db
from app.models.artifact import ArtifactDocument
from app.models.project import Project
from app.models.user import User
from app.schemas.envelope import err, ok
from app.services.artifacts.brd_orchestrator import (
    BRD_TABLE_MAP,
    edit_brd_row,
    get_brd_detail,
    save_brd_answer,
    validate_brd,
)

router = APIRouter(tags=["brd"])

VALID_BRD_TABLES = set(BRD_TABLE_MAP.keys())


# ── GET detail ─────────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/artifacts/brd")
async def get_brd(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    detail = await get_brd_detail(project_id, db)
    return ok(detail)


# ── Readiness check ────────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/artifacts/brd/readiness")
async def check_brd_readiness(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.context.project_context import gather_project_context
    bundle = await gather_project_context(project_id, db)
    r = bundle.readiness
    return ok({
        "can_generate": r.can_generate,
        "blocking_reason": r.blocking_reason,
        "docs_all_ready": r.docs_all_ready,
        "cb_ready": r.cb_ready,
        "cb_status": r.cb_status,
        "pending_doc_count": r.docs_pending_names.__len__(),
        "failed_doc_count": r.docs_failed_names.__len__(),
        "docs": [
            {
                "id": e.doc_id,
                "filename": e.filename,
                "indexing_status": e.indexing_status,
                "page_count": e.page_count,
            }
            for e in bundle.docs.inventory
        ],
    })


# ── Reset stuck generating status ─────────────────────────────────────────────

@router.post("/projects/{project_id}/artifacts/brd/reset-generating")
async def reset_brd_generating(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reset a BRD stuck in 'generating' back to 'in_interview'.

    Safe to call after a worker crash — existing generated rows are preserved.
    """
    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == "brd",
                ArtifactDocument.status == "generating",
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        err("not_generating", "BRD is not currently in generating state.", 400)
    doc.status = "in_interview"
    await db.commit()
    return ok({"status": "in_interview", "doc_id": str(doc.id)})


# ── Generate BRD ───────────────────────────────────────────────────────────────

class _BrdGenerateIn(BaseModel):
    context: str | None = None
    discover_context: str | None = None


@router.post("/projects/{project_id}/artifacts/brd/generate")
async def generate_brd_endpoint(
    project_id: UUID,
    body: _BrdGenerateIn = Body(default_factory=_BrdGenerateIn),
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.config import get_settings
    from app.services.artifacts.brd_orchestrator import _ensure_brd_document, generate_brd_all
    from app.services.context.project_context import gather_project_context

    # Check readiness before generating
    bundle = await gather_project_context(project_id, db)
    readiness = bundle.readiness
    if hasattr(readiness, "can_generate") and not readiness.can_generate:
        blocking = getattr(readiness, "blocking_reason", "Context bundle is not ready for generation.")
        err("brd_not_ready", blocking, 409)

    settings = get_settings()
    if settings.llm_provider == "mock":
        detail = await generate_brd_all(
            project, db, context=body.context, discover_context=body.discover_context
        )
        return ok(detail)

    # Production: set status → generating, dispatch Celery task
    doc = await _ensure_brd_document(project_id, db)
    doc.status = "generating"
    await db.commit()

    from workers.dispatch import dispatch
    from workers.tasks import generate_brd
    dispatch(generate_brd, str(project_id), body.context, body.discover_context)

    return ok(await get_brd_detail(project_id, db))


# ── Save answer ────────────────────────────────────────────────────────────────

class _BrdAnswerIn(BaseModel):
    answer: str
    seq: int | None = None


@router.post("/projects/{project_id}/artifacts/brd/answer")
async def answer_brd_question(
    project_id: UUID,
    body: _BrdAnswerIn,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.config import get_settings
    settings = get_settings()

    if settings.llm_provider == "mock":
        from app.services.artifacts.brd_orchestrator import run_brd_regeneration
        detail = await save_brd_answer(project_id, body.answer, db, body.seq)
        await run_brd_regeneration(project_id, body.seq)
        return ok(await get_brd_detail(project_id, db))

    # Real LLM: persist answer immediately, dispatch regeneration to Celery, return fast
    detail = await save_brd_answer(project_id, body.answer, db, body.seq)
    from workers.dispatch import dispatch
    from workers.tasks import incorporate_brd_answer_task
    dispatch(incorporate_brd_answer_task, str(project_id), body.seq)
    return ok(detail)


# ── Validate ───────────────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/artifacts/brd/validate")
async def validate_brd_endpoint(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = await validate_brd(project_id, db, current_user.id)
    except ValueError as e:
        err("not_found", str(e), 404)
    if not result["ok"]:
        err("validation_failed", "BRD validation failed — see findings for details.", 409,
            details={"findings": result["findings"]})
    return ok(result)


# ── Findings (no status change) ────────────────────────────────────────────────

@router.get("/projects/{project_id}/artifacts/brd/findings")
async def get_brd_findings(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.artifacts.validators.brd import run_brd_validation
    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == "brd",
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        return ok({"findings": [], "summary": {"total": 0, "critical": 0, "major": 0, "minor": 0}})
    findings = await run_brd_validation(doc.id, doc, db)
    summary = {
        "total": len(findings),
        "critical": sum(1 for f in findings if f["group"] == "critical"),
        "major": sum(1 for f in findings if f["group"] == "major"),
        "minor": sum(1 for f in findings if f["group"] == "minor"),
        "coverage": sum(1 for f in findings if f["group"] == "coverage"),
        "warnings": sum(1 for f in findings if f["group"] == "warnings"),
    }
    return ok({"findings": findings, "summary": summary})


# ── Export markdown ────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/artifacts/brd/export")
async def export_brd_markdown(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.export.brd_markdown import export_brd_markdown as _export
    detail = await get_brd_detail(project_id, db)
    if detail.get("document") is None:
        err("not_found", "BRD document not found", 404)
    md = _export(detail, project)
    slug = project.name.lower().replace(" ", "-")[:40]
    return PlainTextResponse(
        md,
        headers={"Content-Disposition": f'attachment; filename="brd-{slug}.md"'},
        media_type="text/markdown",
    )


# ── Coverage report ────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/artifacts/brd/coverage")
async def get_brd_coverage(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import func as sa_func
    from app.services.context.coverage import compute_coverage
    from app.services.artifacts.brd_orchestrator import BRD_TABLE_MAP

    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == "brd",
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        return ok({"all_covered": False, "covered_count": 0, "total_count": 0, "entries": []})

    # Approximate unit row counts via table counts
    _UNIT_TABLE_MAP: dict[str, list[str]] = {
        "business_context":      ["brd_text_blocks"],
        "problem_statement":     ["brd_text_blocks"],
        "objectives":            ["brd_objectives"],
        "stakeholders":          ["brd_stakeholders"],
        "actors":                ["brd_actors"],
        "scope":                 ["brd_scope_items"],
        "asis_process":          ["brd_process_steps"],
        "tobe_process":          ["brd_process_steps"],
        "business_requirements": ["brd_business_requirements"],
        "data_entities":         ["brd_data_entities"],
        "report_requirements":   ["brd_report_requirements"],
        "assumptions":           ["brd_assumptions"],
        "constraints":           ["brd_constraints"],
        "dependencies":          ["brd_dependencies"],
        "risks":                 ["brd_risks"],
        "implementation_phases": ["brd_phases"],
        "milestones":            ["brd_milestones"],
        "kpis":                  ["brd_kpis"],
        "open_questions":        ["brd_open_questions"],
        "decisions":             ["brd_decisions"],
        "references":            ["brd_references"],
        "glossary":              ["brd_glossary_entries"],
    }
    table_counts: dict[str, int] = {}
    for table_name, model in BRD_TABLE_MAP.items():
        cnt = await db.scalar(
            select(sa_func.count(model.id)).where(
                model.document_id == doc.id,
                model.is_current.is_(True),
                model.status == "active",
            )
        ) or 0
        table_counts[table_name] = cnt

    unit_row_counts: dict[str, int] = {
        uk: max((table_counts.get(t, 0) for t in tables), default=0)
        for uk, tables in _UNIT_TABLE_MAP.items()
    }
    report = compute_coverage(unit_row_counts)
    return ok({
        "all_covered": report.all_covered,
        "covered_count": report.covered_count,
        "total_count": report.total_count,
        "uncovered_keys": report.uncovered_keys,
        "entries": [
            {
                "cb_element_key": e.cb_element_key,
                "brd_units": e.brd_units,
                "is_covered": e.is_covered,
                "uncovered_reason": e.uncovered_reason,
            }
            for e in report.entries
        ],
    })


# ── Discover: analyze ──────────────────────────────────────────────────────────

class _DiscoverAnalyzeIn(BaseModel):
    brief_text: str = ""


@router.post("/projects/{project_id}/artifacts/brd/discover/analyze")
async def brd_discover_analyze(
    project_id: UUID,
    body: _DiscoverAnalyzeIn,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.config import get_settings
    if get_settings().llm_provider == "mock":
        from app.services.artifacts.discover import analyze_brief, question_to_dict
        questions = await analyze_brief(project, "brd", body.brief_text, db)
        return ok({"questions": [question_to_dict(q) for q in questions], "analyzing": False})

    from app.services.artifacts.discover import _ensure_discover_document
    doc = await _ensure_discover_document(project.id, "brd", db)
    doc.discover_analyzing = True
    await db.commit()

    from workers.dispatch import dispatch
    from workers.tasks import analyze_discover
    dispatch(analyze_discover, str(project.id), "brd", body.brief_text)

    return ok({"questions": [], "analyzing": True})


# ── Discover: answer one question ──────────────────────────────────────────────

class _DiscoverAnswerIn(BaseModel):
    answer: str


@router.post("/projects/{project_id}/artifacts/brd/discover/{q_key}/answer")
async def brd_discover_answer(
    project_id: UUID,
    q_key: str,
    body: _DiscoverAnswerIn,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.artifact import CbDiscoverQuestion
    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == "brd",
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        err("not_found", "BRD discover document not found — run analyze first", 404)

    question = (
        await db.execute(
            select(CbDiscoverQuestion).where(
                CbDiscoverQuestion.artifact_document_id == doc.id,
                CbDiscoverQuestion.question_key == q_key,
            )
        )
    ).scalar_one_or_none()
    if question is None:
        err("not_found", f"Discover question '{q_key}' not found", 404)

    from app.services.artifacts.discover import answer_question, question_to_dict
    try:
        q = await answer_question(question.id, body.answer, db)
        return ok(question_to_dict(q))
    except ValueError as e:
        err("not_found", str(e), 404)


# ── Discover: enhance answer ───────────────────────────────────────────────────

class _DiscoverEnhanceIn(BaseModel):
    brief_text: str


@router.post("/projects/{project_id}/artifacts/brd/discover/enhance")
async def brd_discover_enhance(
    project_id: UUID,
    body: _DiscoverEnhanceIn,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.artifacts.discover import enhance_brief
    try:
        result = await asyncio.wait_for(
            enhance_brief(project, "brd", body.brief_text, db),
            timeout=60.0,
        )
        return ok(result)
    except asyncio.TimeoutError:
        err("enhance_timeout", "Enhancement timed out — try again or shorten your brief", 504)
    except Exception as e:
        err("enhance_failed", str(e), 500)


# ── Row edit ───────────────────────────────────────────────────────────────────

class _BrdRowEditIn(BaseModel):
    fields: dict
    lock: bool = True


@router.post("/projects/{project_id}/artifacts/brd/{table}/{row_id}/edit")
async def edit_brd_row_endpoint(
    project_id: UUID,
    table: str,
    row_id: UUID,
    body: _BrdRowEditIn,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if table not in VALID_BRD_TABLES:
        err("invalid_table", f"Unknown BRD table: {table}", 400)
    try:
        result = await edit_brd_row(table, row_id, body.fields, db, current_user.id, body.lock)
        await db.commit()
        return ok(result)
    except ValueError as e:
        err("not_found", str(e), 404)


# ── Row history ────────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/artifacts/brd/{table}/{row_id}/history")
async def brd_row_history(
    project_id: UUID,
    table: str,
    row_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if table not in VALID_BRD_TABLES:
        err("invalid_table", f"Unknown BRD table: {table}", 400)

    model = BRD_TABLE_MAP[table]
    # Find row_key for this row_id
    row = await db.get(model, row_id)
    if row is None:
        err("not_found", f"Row {row_id} not found in {table}", 404)

    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == "brd",
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        return ok([])

    history_rows = (
        await db.execute(
            select(model).where(
                model.document_id == doc.id,
                model.row_key == row.row_key,
            ).order_by(model.version.desc())
        )
    ).scalars().all()

    from app.services.artifacts.brd_orchestrator import _brd_row_to_dict
    return ok([_brd_row_to_dict(r, table) for r in history_rows])


# ── Row restore ────────────────────────────────────────────────────────────────

class _BrdRowRestoreIn(BaseModel):
    version: int


@router.post("/projects/{project_id}/artifacts/brd/{table}/{row_id}/restore")
async def restore_brd_row(
    project_id: UUID,
    table: str,
    row_id: UUID,
    body: _BrdRowRestoreIn,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if table not in VALID_BRD_TABLES:
        err("invalid_table", f"Unknown BRD table: {table}", 400)

    model = BRD_TABLE_MAP[table]
    from app.services.artifacts.brd_orchestrator import _BRD_TYPED_COLS

    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == "brd",
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        err("not_found", "BRD artifact document not found", 404)

    # Find the target version row
    row = await db.get(model, row_id)
    if row is None:
        err("not_found", f"Row {row_id} not found", 404)

    target_version = (
        await db.execute(
            select(model).where(
                model.document_id == doc.id,
                model.row_key == row.row_key,
                model.version == body.version,
            )
        )
    ).scalar_one_or_none()
    if target_version is None:
        err("not_found", f"Version {body.version} of row '{row.row_key}' not found", 404)

    # Mark current as non-current, create new version from target
    current = (
        await db.execute(
            select(model).where(
                model.document_id == doc.id,
                model.row_key == row.row_key,
                model.is_current.is_(True),
            )
        )
    ).scalar_one_or_none()

    typed_cols = _BRD_TYPED_COLS[table]
    next_version = (current.version + 1) if current else (body.version + 1)
    if current:
        current.is_current = False

    restored = model(
        document_id=doc.id,
        row_key=row.row_key,
        version=next_version,
        is_current=True,
        is_locked=False,
        status="active",
        source="human",
        created_by=current_user.id,
        **{c: getattr(target_version, c) for c in typed_cols},
    )
    db.add(restored)
    await db.flush()
    await db.refresh(restored)
    await db.commit()

    from app.services.artifacts.brd_orchestrator import _brd_row_to_dict
    return ok(_brd_row_to_dict(restored, table))


# ── Row unlock ─────────────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/artifacts/brd/{table}/{row_id}/unlock")
async def unlock_brd_row(
    project_id: UUID,
    table: str,
    row_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if table not in VALID_BRD_TABLES:
        err("invalid_table", f"Unknown BRD table: {table}", 400)
    model = BRD_TABLE_MAP[table]
    row = await db.get(model, row_id)
    if row is None or not row.is_current:
        err("not_found", f"Row {row_id} not found or not current", 404)
    row.is_locked = False
    await db.commit()
    from app.services.artifacts.brd_orchestrator import _brd_row_to_dict
    return ok(_brd_row_to_dict(row, table))


# ── Single-unit regenerate ─────────────────────────────────────────────────────

@router.post("/projects/{project_id}/artifacts/brd/units/{unit_key}/regenerate")
async def regenerate_brd_unit(
    project_id: UUID,
    unit_key: str,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Regenerate a single BRD unit in-place with full-corpus context.
    Does not affect any other unit's rows or status."""
    from app.services.artifacts.brd_orchestrator import (
        BRD_MANIFEST_BY_KEY, generate_brd_unit,
    )
    from app.services.context.project_context import gather_project_context

    if unit_key not in BRD_MANIFEST_BY_KEY:
        err("invalid_unit", f"Unknown BRD unit: {unit_key}", 400)

    doc = (await db.execute(
        select(ArtifactDocument).where(
            ArtifactDocument.project_id == project_id,
            ArtifactDocument.artifact_type == "brd",
        )
    )).scalar_one_or_none()
    if doc is None:
        err("not_found", "BRD document not found — generate first", 404)

    bundle = await gather_project_context(project_id, db, artifact_document_id=doc.id)
    await generate_brd_unit(project, unit_key, doc, bundle, db)
    await db.commit()
    return ok({"unit_key": unit_key, "status": "regenerated"})


# ── Row delete (soft) ──────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/artifacts/brd/{table}/{row_id}/delete")
async def delete_brd_row(
    project_id: UUID,
    table: str,
    row_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if table not in VALID_BRD_TABLES:
        err("invalid_table", f"Unknown BRD table: {table}", 400)
    model = BRD_TABLE_MAP[table]
    row = await db.get(model, row_id)
    if row is None or not row.is_current:
        err("not_found", f"Row {row_id} not found or not current in {table}", 404)
    row.status = "removed"
    await db.commit()
    return ok({"deleted": True, "row_key": row.row_key})
