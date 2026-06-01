"""Test Cases (E3) API router.

Endpoints under /api/projects/{project_id}/artifacts/test_cases. Generation is
gated on a validated FRS (require_artifact_validated('frs')). Mirrors frs.py.
"""
from __future__ import annotations

from uuid import UUID
from typing import Any

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_project_or_404, require_artifact_validated
from app.db import get_db
from app.models.artifact import ArtifactDocument
from app.models.project import Project
from app.models.user import User
from app.schemas.envelope import err, ok
from app.services.artifacts.manifest.test_cases import TC_TABLE_MAP
from app.services.artifacts.tc_orchestrator import (
    add_tc_case, delete_tc_row, edit_tc_row, generate_tc_all, get_tc_detail,
    get_tc_row_history, regenerate_tc_plan, reset_tc_generating, restore_tc_row,
    run_tc_stage_b, unlock_tc_row, _ensure_tc_document,
)

router = APIRouter(tags=["test_cases"])

VALID_TC_TABLES = set(TC_TABLE_MAP.keys())
_BASE = "/projects/{project_id}/artifacts/test_cases"


# ── GET detail ──────────────────────────────────────────────────────────────

@router.get(_BASE)
async def get_test_cases(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ok(await get_tc_detail(project_id, db))


# ── Readiness ───────────────────────────────────────────────────────────────

@router.post(_BASE + "/readiness")
async def check_tc_readiness(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.context.project_context import gather_project_context
    bundle = await gather_project_context(project_id, db, artifact_type="test_cases")
    r = bundle.readiness
    return ok({
        "can_generate": r.can_generate,
        "blocking_reason": r.blocking_reason,
        "frs_ready": r.frs_ready, "frs_status": r.frs_status,
        "brd_ready": r.brd_ready, "brd_status": r.brd_status,
        "cb_ready": r.cb_ready,
        "frs_module_count": len(bundle.frs.modules) if bundle.frs else 0,
        "frs_spec_count": len(bundle.frs.specs) if bundle.frs else 0,
    })


# ── Generate (Stage A + B) — gated on FRS validated ──────────────────────────

@router.post(_BASE + "/generate")
async def generate_test_cases_endpoint(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _gate: None = Depends(require_artifact_validated("frs")),
):
    from app.config import get_settings
    from app.services.context.project_context import gather_project_context

    bundle = await gather_project_context(project_id, db, artifact_type="test_cases")
    if not bundle.readiness.can_generate:
        err("test_cases_not_ready", bundle.readiness.blocking_reason or "Not ready", 409)

    if get_settings().llm_provider == "mock":
        return ok(await generate_tc_all(project, db, run_stage_b=True))

    doc = await _ensure_tc_document(project_id, db)
    doc.unit_status = {}
    doc.status = "generating"
    await db.commit()
    from workers.dispatch import dispatch
    from workers.tasks import generate_test_cases
    try:
        dispatch(generate_test_cases, str(project_id))
    except Exception:
        doc.status = "in_interview"
        await db.commit()
        err("broker_unavailable", "Background worker unavailable; try again.", 503)
    return ok(await get_tc_detail(project_id, db))


@router.post(_BASE + "/design-all-plans")
async def design_all_plans_endpoint(
    project_id: UUID,
    body: dict = Body(default_factory=dict),
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _gate: None = Depends(require_artifact_validated("frs")),
):
    from app.config import get_settings
    skip_designed = bool(body.get("skip_designed", True))
    module_row_key = body.get("module_row_key") or None
    if get_settings().llm_provider == "mock":
        return ok(await run_tc_stage_b(project, db, skip_designed=skip_designed, module_row_key=module_row_key))
    doc = await _ensure_tc_document(project_id, db)
    doc.status = "generating"
    await db.commit()
    from workers.dispatch import dispatch
    from workers.tasks import design_all_test_plans
    try:
        # Only pass module_row_key when set, so a not-yet-restarted worker running
        # the older 2-arg task signature still accepts the project-level call.
        if module_row_key:
            dispatch(design_all_test_plans, str(project_id), skip_designed, module_row_key)
        else:
            dispatch(design_all_test_plans, str(project_id), skip_designed)
    except Exception:
        doc.status = "in_interview"
        await db.commit()
        err("broker_unavailable", "Background worker unavailable; try again.", 503)
    return ok(await get_tc_detail(project_id, db))


@router.post(_BASE + "/plans/{spec_row_key}/design")
@router.post(_BASE + "/plans/{spec_row_key}/regenerate")
async def regenerate_plan_endpoint(
    project_id: UUID,
    spec_row_key: str,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _gate: None = Depends(require_artifact_validated("frs")),
):
    from app.config import get_settings
    if get_settings().llm_provider == "mock":
        return ok(await regenerate_tc_plan(project, spec_row_key, db))
    doc = await _ensure_tc_document(project_id, db)
    doc.status = "generating"
    await db.commit()
    from workers.dispatch import dispatch
    from workers.tasks import regenerate_test_cases_plan
    try:
        dispatch(regenerate_test_cases_plan, str(project_id), spec_row_key)
    except Exception:
        doc.status = "in_interview"
        await db.commit()
        err("broker_unavailable", "Background worker unavailable; try again.", 503)
    return ok(await get_tc_detail(project_id, db))


@router.post(_BASE + "/reset-generating")
async def reset_tc_generating_endpoint(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = await reset_tc_generating(project_id, db)
    await db.commit()
    return ok({"status": doc.status, "doc_id": str(doc.id)})


# ── Coverage ────────────────────────────────────────────────────────────────

@router.get(_BASE + "/coverage")
async def get_tc_coverage_endpoint(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.context.tc_coverage import build_tc_coverage
    return ok(await build_tc_coverage(project_id, db))


# ── Findings + validate ───────────────────────────────────────────────────────

@router.get(_BASE + "/findings")
async def get_tc_findings(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.artifacts.validators.test_cases import run_tc_validation, summarize_findings
    doc = await _tc_doc(project_id, db)
    if doc is None:
        return ok({"summary": {"total": 0, "blocking": 0}, "findings": []})
    findings = await run_tc_validation(doc.id, doc, db)
    return ok({"summary": summarize_findings(findings), "findings": findings})


@router.post(_BASE + "/validate")
async def validate_tc_endpoint(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from datetime import datetime, timezone
    from sqlalchemy import update as sa_update
    from app.models.test_cases import TestSuite, TestPlan, TestCase
    from app.services.artifacts.validators.test_cases import run_tc_validation, summarize_findings

    doc = await _tc_doc(project_id, db)
    if doc is None:
        err("test_cases_not_found", "No test-cases artifact exists for this project.", 404)

    findings = await run_tc_validation(doc.id, doc, db)
    summary = summarize_findings(findings)
    if summary["blocking"] > 0:
        return ok({"ok": False, "summary": summary, "findings": findings})

    locked = 0
    for model in (TestSuite, TestPlan, TestCase):
        r = await db.execute(
            sa_update(model).where(
                model.document_id == doc.id, model.is_current.is_(True),
                model.status == "active", model.is_locked.is_(False),
            ).values(is_locked=True)
        )
        locked += r.rowcount or 0
    doc.status = "validated"
    doc.validated_at = datetime.now(timezone.utc)
    doc.validated_by = current_user.id
    await db.commit()
    return ok({"ok": True, "summary": summary, "findings": findings, "locked_row_count": locked})


# ── Add manual case + link ────────────────────────────────────────────────────

class _AddCaseLinks(BaseModel):
    scenario_refs: list[str] = []
    fr_refs: list[str] = []
    br_refs: list[str] = []


class _AddCaseIn(BaseModel):
    title: str
    test_type: str = "functional"
    given: str = ""
    when: str = ""
    then: str = ""
    steps: list[dict[str, Any]] = []
    preconditions: str = ""
    key_assertions: list[str] = []
    test_data: dict[str, Any] = {}
    expected_result: str = ""
    expected_observability: list[dict[str, Any]] = []
    viewports: list[str] = []
    auth_required: bool = False
    auth_role: str | None = None
    priority: str = "P1"
    links: _AddCaseLinks = _AddCaseLinks()


@router.post(_BASE + "/plans/{plan_row_key}/cases")
async def add_test_case_endpoint(
    project_id: UUID,
    plan_row_key: str,
    body: _AddCaseIn,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _gate: None = Depends(require_artifact_validated("frs")),
):
    payload = body.model_dump()
    try:
        result = await add_tc_case(project_id, plan_row_key, payload, db, user_id=current_user.id)
        await db.commit()
        return ok(result)
    except ValueError as e:
        msg = str(e)
        if msg.startswith("invalid_") or msg == "at_least_one_link_required":
            err("invalid_links", msg, 422)
        if msg.startswith("plan_not_found"):
            err("plan_not_found", msg, 404)
        err("add_case_failed", msg, 400)


# ── Generic row CRUD ──────────────────────────────────────────────────────────

class _EditIn(BaseModel):
    fields: dict[str, Any]
    lock: bool = False
    expected_version: int | None = None


@router.post(_BASE + "/{table}/{row_id}/edit")
async def edit_tc_row_endpoint(
    project_id: UUID, table: str, row_id: UUID, body: _EditIn,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if table not in VALID_TC_TABLES:
        err("invalid_table", f"Unknown test-cases table: {table}", 400)
    doc = await _tc_doc(project_id, db)
    if doc is None:
        err("test_cases_not_found", "No test-cases artifact.", 404)
    try:
        new_row = await edit_tc_row(doc.id, table, row_id, body.fields, db,
                                    user_id=current_user.id, lock=body.lock,
                                    expected_version=body.expected_version)
        await db.commit()
        return ok({"id": str(new_row.id), "row_key": new_row.row_key, "version": new_row.version})
    except ValueError as e:
        msg = str(e)
        if msg.startswith("version_conflict"):
            err("version_conflict", msg, 409)
        err("row_not_found", msg, 404)


@router.post(_BASE + "/{table}/{row_id}/delete")
async def delete_tc_row_endpoint(
    project_id: UUID, table: str, row_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if table not in VALID_TC_TABLES:
        err("invalid_table", f"Unknown test-cases table: {table}", 400)
    doc = await _tc_doc(project_id, db)
    if doc is None:
        err("test_cases_not_found", "No test-cases artifact.", 404)
    try:
        await delete_tc_row(doc.id, table, row_id, db)
        await db.commit()
        return ok({"deleted": True})
    except ValueError as e:
        msg = str(e)
        if msg.startswith("row_locked"):
            err("row_locked", msg, 409)
        err("row_not_found", msg, 404)


@router.post(_BASE + "/{table}/{row_id}/unlock")
async def unlock_tc_row_endpoint(
    project_id: UUID, table: str, row_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if table not in VALID_TC_TABLES:
        err("invalid_table", f"Unknown test-cases table: {table}", 400)
    doc = await _tc_doc(project_id, db)
    if doc is None:
        err("test_cases_not_found", "No test-cases artifact.", 404)
    try:
        await unlock_tc_row(doc.id, table, row_id, db)
        await db.commit()
        return ok({"unlocked": True})
    except ValueError as e:
        err("row_not_found", str(e), 404)


@router.post(_BASE + "/{table}/{row_id}/restore")
async def restore_tc_row_endpoint(
    project_id: UUID, table: str, row_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if table not in VALID_TC_TABLES:
        err("invalid_table", f"Unknown test-cases table: {table}", 400)
    doc = await _tc_doc(project_id, db)
    if doc is None:
        err("test_cases_not_found", "No test-cases artifact.", 404)
    try:
        new_row = await restore_tc_row(doc.id, table, row_id, db, user_id=current_user.id)
        await db.commit()
        return ok({"id": str(new_row.id), "row_key": new_row.row_key, "version": new_row.version})
    except ValueError as e:
        err("row_not_found", str(e), 404)


@router.get(_BASE + "/{table}/{row_id}/history")
async def tc_row_history_endpoint(
    project_id: UUID, table: str, row_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if table not in VALID_TC_TABLES:
        err("invalid_table", f"Unknown test-cases table: {table}", 400)
    doc = await _tc_doc(project_id, db)
    if doc is None:
        err("test_cases_not_found", "No test-cases artifact.", 404)
    try:
        return ok({"versions": await get_tc_row_history(doc.id, table, row_id, db)})
    except ValueError as e:
        err("row_not_found", str(e), 404)


@router.get(_BASE + "/orphans")
async def tc_orphans_endpoint(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Traceability whose target FRS row no longer exists (stale after FRS regen)."""
    from app.services.artifacts.validators.test_cases import _active_frs_keys
    from app.models.test_cases import TestCaseTraceability
    doc = await _tc_doc(project_id, db)
    if doc is None:
        return ok({"orphans": []})
    active = await _active_frs_keys(project_id, db)
    rows = (
        await db.execute(select(TestCaseTraceability).where(
            TestCaseTraceability.document_id == doc.id,
            TestCaseTraceability.target_kind.in_((
                "frs_acceptance_scenario", "frs_functional_requirement",
                "frs_business_rule", "frs_screen",
            )),
        ))
    ).scalars().all()
    orphans = [{
        "source_row_key": t.source_row_key, "target_kind": t.target_kind, "target_ref": t.target_ref,
    } for t in rows if t.target_ref not in active]
    return ok({"orphans": orphans})


# ── helper ────────────────────────────────────────────────────────────────────

async def _tc_doc(project_id: UUID, db: AsyncSession) -> ArtifactDocument | None:
    return (
        await db.execute(select(ArtifactDocument).where(
            ArtifactDocument.project_id == project_id,
            ArtifactDocument.artifact_type == "test_cases",
        ))
    ).scalar_one_or_none()


# ── Gap-fill: author cases only for uncovered FRS elements (append-only) ──────

@router.post(_BASE + "/gap-fill")
async def gap_fill_all_endpoint(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _gate: None = Depends(require_artifact_validated("frs")),
):
    """Fill ALL coverage gaps across the project — author cases only for FRS
    elements that currently have no test case. Existing cases are untouched."""
    from app.config import get_settings
    if get_settings().llm_provider == "mock":
        from app.services.artifacts.tc_orchestrator import gap_fill_tc
        return ok(await gap_fill_tc(project, db))
    doc = await _ensure_tc_document(project_id, db)
    doc.status = "generating"
    await db.commit()
    from workers.dispatch import dispatch
    from workers.tasks import gap_fill_test_cases
    try:
        dispatch(gap_fill_test_cases, str(project_id), None)
    except Exception:
        doc.status = "in_interview"
        await db.commit()
        err("broker_unavailable", "Background worker unavailable; try again.", 503)
    return ok(await get_tc_detail(project_id, db))


@router.post(_BASE + "/repair")
async def repair_test_cases_endpoint(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _gate: None = Depends(require_artifact_validated("frs")),
):
    """Surgical fix for the messy-history state behind blocking validation:
    1. cleanup_tc_refs (inline, no LLM) — strip dangling refs/traceability that
       point at FRS rows that no longer exist → clears every `orphan_case`.
    2. Regenerate ONLY the specs that still fail validation (thin/uncovered),
       preserving locked + human cases.
    Returns the cleanup summary immediately; the regen runs in-process (mock) or
    in the background worker (real provider, status='generating')."""
    from app.config import get_settings
    from app.services.artifacts.tc_orchestrator import cleanup_tc_refs, regen_thin_tc

    cleanup = await cleanup_tc_refs(project, db)

    if get_settings().llm_provider == "mock":
        detail = await regen_thin_tc(project, db)
        return ok({"cleanup": cleanup, "detail": detail})

    doc = await _ensure_tc_document(project_id, db)
    doc.status = "generating"
    # Transient marker so the repair screen shows "Starting…" immediately; the
    # worker overwrites unit_status with the full manifest as soon as it runs.
    doc.unit_status = {"_repair": {"active": True, "total": 0}, "_repair_specs": []}
    await db.commit()
    from workers.dispatch import dispatch
    from workers.tasks import regen_thin_test_cases
    try:
        dispatch(regen_thin_test_cases, str(project_id))
    except Exception:
        doc.status = "in_interview"
        await db.commit()
        err("broker_unavailable", "Background worker unavailable; try again.", 503)
    return ok({"cleanup": cleanup, "detail": await get_tc_detail(project_id, db)})


@router.post(_BASE + "/plans/{spec_row_key}/gap-fill")
async def gap_fill_spec_endpoint(
    project_id: UUID,
    spec_row_key: str,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _gate: None = Depends(require_artifact_validated("frs")),
):
    """Fill coverage gaps for ONE spec only."""
    from app.config import get_settings
    if get_settings().llm_provider == "mock":
        from app.services.artifacts.tc_orchestrator import gap_fill_tc
        return ok(await gap_fill_tc(project, db, spec_row_key=spec_row_key))
    doc = await _ensure_tc_document(project_id, db)
    doc.status = "generating"
    await db.commit()
    from workers.dispatch import dispatch
    from workers.tasks import gap_fill_test_cases
    try:
        dispatch(gap_fill_test_cases, str(project_id), spec_row_key)
    except Exception:
        doc.status = "in_interview"
        await db.commit()
        err("broker_unavailable", "Background worker unavailable; try again.", 503)
    return ok(await get_tc_detail(project_id, db))
