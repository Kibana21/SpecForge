"""BRD Artifact Orchestrator: versioning, generation, validation for the BRD artifact type.

Mirrors the pattern in orchestrator.py (CB) but uses:
- ProjectContextBundle (full-corpus context requirement)
- BRD manifest (22 units + DAG)
- BRD DSPy modules (dspy_brd.py)
- BRD-specific typed tables (21 tables + traceability)
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, text as sa_text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.models.artifact import ArtifactDocument, ArtifactMessage, ArtifactSource
from app.models.brd import (
    BrdActor, BrdAssumption, BrdBusinessRequirement, BrdConstraint, BrdDataEntity,
    BrdDecision, BrdDependency, BrdGlossaryEntry, BrdKpi, BrdMilestone, BrdObjective,
    BrdOpenQuestion, BrdPhase, BrdProcessStep, BrdReference, BrdReportRequirement,
    BrdRisk, BrdScopeItem, BrdStakeholder, BrdTextBlock, BrdTraceability,
)
from app.models.document import Document
from app.models.project import Project
from app.services.artifacts.manifest.brd import (
    BRD_MANIFEST_BY_KEY, BRD_TOPO_ORDER, BrdUnitSpec,
)
from app.services.context.docs_layer import depth_search
from app.services.context.projection import project_for_unit
from app.services.skills.dspy_brd import run_brd_unit

log = logging.getLogger(__name__)

# ── Table registry ─────────────────────────────────────────────────────────────

BRD_TABLE_MAP: dict[str, type] = {
    "brd_text_blocks":             BrdTextBlock,
    "brd_objectives":              BrdObjective,
    "brd_stakeholders":            BrdStakeholder,
    "brd_actors":                  BrdActor,
    "brd_scope_items":             BrdScopeItem,
    "brd_process_steps":           BrdProcessStep,
    "brd_business_requirements":   BrdBusinessRequirement,
    "brd_data_entities":           BrdDataEntity,
    "brd_report_requirements":     BrdReportRequirement,
    "brd_assumptions":             BrdAssumption,
    "brd_constraints":             BrdConstraint,
    "brd_dependencies":            BrdDependency,
    "brd_risks":                   BrdRisk,
    "brd_phases":                  BrdPhase,
    "brd_milestones":              BrdMilestone,
    "brd_kpis":                    BrdKpi,
    "brd_open_questions":          BrdOpenQuestion,
    "brd_decisions":               BrdDecision,
    "brd_references":              BrdReference,
    "brd_glossary_entries":        BrdGlossaryEntry,
}

# Typed columns per table (used by upsert_brd_rows)
_BRD_TYPED_COLS: dict[str, list[str]] = {
    "brd_text_blocks":             ["field_key", "text"],
    "brd_objectives":              ["statement", "category", "priority", "owner", "cb_outcome_ref"],
    "brd_stakeholders":            ["name", "stakeholder_type", "role", "interest", "influence"],
    "brd_actors":                  ["name", "actor_type", "description", "interactions"],
    "brd_scope_items":             ["kind", "text", "rationale", "cb_scope_ref"],
    "brd_process_steps":           ["step_type", "step_number", "actor", "action", "pain_point", "improvement"],
    "brd_business_requirements":   ["title", "description", "priority", "category", "acceptance_criteria", "objective_refs", "stakeholder_refs", "rationale", "completeness", "confidence"],
    "brd_data_entities":           ["entity_name", "description", "owner_system", "data_sensitivity", "key_attributes"],
    "brd_report_requirements":     ["report_name", "description", "audience", "frequency", "key_metrics"],
    "brd_assumptions":             ["assumption", "impact_if_wrong", "owner", "cb_scope_ref"],
    "brd_constraints":             ["constraint_text", "constraint_type", "source_ref"],
    "brd_dependencies":            ["dependency", "dependency_type", "owner", "due_date"],
    "brd_risks":                   ["risk", "description", "severity", "likelihood", "mitigation", "owner"],
    "brd_phases":                  ["phase_name", "description", "target_date", "included_br_refs"],
    "brd_milestones":              ["milestone", "target", "description", "phase_ref", "cb_milestone_ref"],
    "brd_kpis":                    ["kpi_name", "description", "baseline", "target", "timeframe", "data_source", "objective_ref", "cb_metric_ref"],
    "brd_open_questions":          ["question", "context", "owner", "due_date"],
    "brd_decisions":               ["decision", "rationale", "owner", "decision_date", "alternatives_considered"],
    "brd_references":              ["title", "reference_type", "location", "description"],
    "brd_glossary_entries":        ["term", "definition", "source_ref"],
}

# Columns that must be coerced to int when coming in as strings from the UI
_BRD_INT_COLS: dict[str, set[str]] = {
    "brd_process_steps": {"step_number"},
}


# ── Row versioning ─────────────────────────────────────────────────────────────

async def upsert_brd_rows(
    table_name: str,
    document_id: uuid.UUID,
    output_rows: list[dict],
    source: str,
    db: AsyncSession,
    user_id: uuid.UUID | None = None,
    scope_keys: set[str] | None = None,
) -> int:
    """Idempotent versioned upsert for BRD typed tables. Returns new versions created."""
    model = BRD_TABLE_MAP[table_name]
    typed_cols = _BRD_TYPED_COLS[table_name]
    output_keys = {r["row_key"] for r in output_rows}
    new_versions = 0

    existing = (
        await db.execute(
            select(model).where(
                model.document_id == document_id,
                model.is_current.is_(True),
            )
        )
    ).scalars().all()
    existing_by_key: dict[str, Any] = {r.row_key: r for r in existing}

    for row_data in output_rows:
        row_key = row_data["row_key"]
        current = existing_by_key.get(row_key)

        if current is None:
            db.add(model(
                document_id=document_id, row_key=row_key, version=1,
                is_current=True, is_locked=False, status="active",
                source=source, created_by=user_id,
                **{c: row_data[c] for c in typed_cols if c in row_data},
            ))
            new_versions += 1
        elif current.is_locked:
            continue
        else:
            changed = any(getattr(current, c) != row_data.get(c) for c in typed_cols if c in row_data)
            if changed:
                current.is_current = False
                db.add(model(
                    document_id=document_id, row_key=row_key, version=current.version + 1,
                    is_current=True, is_locked=False, status="active",
                    source=source, created_by=user_id,
                    **{c: row_data[c] for c in typed_cols if c in row_data},
                ))
                new_versions += 1

    for row_key, current in existing_by_key.items():
        in_scope = scope_keys is None or row_key in scope_keys
        if in_scope and row_key not in output_keys and current.status != "removed":
            current.status = "removed"

    return new_versions


async def _current_brd_rows_for(
    table_name: str, document_id: uuid.UUID, db: AsyncSession
) -> list[dict]:
    model = BRD_TABLE_MAP[table_name]
    rows = (
        await db.execute(
            select(model).where(
                model.document_id == document_id,
                model.is_current.is_(True),
                model.status == "active",
            )
        )
    ).scalars().all()
    return [_brd_row_to_dict(r, table_name) for r in rows]


async def _locked_brd_rows_for(
    table_name: str, document_id: uuid.UUID, db: AsyncSession
) -> list[dict]:
    model = BRD_TABLE_MAP[table_name]
    typed_cols = _BRD_TYPED_COLS[table_name]
    rows = (
        await db.execute(
            select(model).where(
                model.document_id == document_id,
                model.is_current.is_(True),
                model.is_locked.is_(True),
            )
        )
    ).scalars().all()
    return [{"row_key": r.row_key, **{c: getattr(r, c) for c in typed_cols}} for r in rows]


def _brd_row_to_dict(row: Any, table_name: str) -> dict:
    typed_cols = _BRD_TYPED_COLS[table_name]
    return {
        "id": str(row.id),
        "document_id": str(row.document_id),
        "row_key": row.row_key,
        "version": row.version,
        "is_current": row.is_current,
        "is_locked": row.is_locked,
        "status": row.status,
        "source": row.source,
        "created_by": str(row.created_by) if row.created_by else None,
        "created_at": row.created_at.isoformat(),
        **{c: getattr(row, c) for c in typed_cols},
    }


# ── Document management ────────────────────────────────────────────────────────

async def _ensure_brd_document(
    project_id: uuid.UUID, db: AsyncSession
) -> ArtifactDocument:
    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == "brd",
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        try:
            async with db.begin_nested():
                doc = ArtifactDocument(
                    project_id=project_id, artifact_type="brd", status="in_interview"
                )
                db.add(doc)
                await db.flush()
                project_docs = (
                    await db.execute(select(Document.id).where(Document.project_id == project_id))
                ).scalars().all()
                for doc_id in project_docs:
                    db.add(ArtifactSource(
                        artifact_document_id=doc.id,
                        source_document_id=doc_id,
                        included=True,
                    ))
                await db.flush()
        except IntegrityError:
            doc = (
                await db.execute(
                    select(ArtifactDocument).where(
                        ArtifactDocument.project_id == project_id,
                        ArtifactDocument.artifact_type == "brd",
                    )
                )
            ).scalar_one()
    return doc


async def _next_brd_seq(document_id: uuid.UUID, db: AsyncSession) -> int:
    cur = await db.scalar(
        select(func.coalesce(func.max(ArtifactMessage.seq), 0)).where(
            ArtifactMessage.document_id == document_id
        )
    )
    return (cur or 0) + 1


# ── Q&A helpers ────────────────────────────────────────────────────────────────

async def _gather_brd_unit_qa(document_id: uuid.UUID, unit_key: str, db: AsyncSession) -> str:
    rows = (
        await db.execute(
            select(ArtifactMessage)
            .where(
                ArtifactMessage.document_id == document_id,
                ArtifactMessage.role.in_(("question", "user")),
            )
            .order_by(ArtifactMessage.seq)
        )
    ).scalars().all()
    relevant = []
    for m in rows:
        uk = m.meta.get("unit_key") if m.meta else None
        if uk is None or uk == unit_key:
            prefix = "Q" if m.role == "question" else "A"
            relevant.append(f"{prefix}: {m.content}")
    return "\n".join(relevant) or "(none yet)"


# ── Persist unit output ────────────────────────────────────────────────────────

async def _persist_brd_unit_result(
    unit_key: str, document_id: uuid.UUID, result: dict, db: AsyncSession
) -> None:
    """Route unit output to the correct BRD table(s)."""

    async def _upsert(table: str, rows: list[dict], scope_keys: set[str] | None = None) -> None:
        if rows:
            await upsert_brd_rows(table, document_id, rows, "ai", db, scope_keys=scope_keys)

    if unit_key == "business_context":
        rows = [{"row_key": "business_context", "field_key": "business_context",
                 "text": result.get("business_context", "")}]
        await _upsert("brd_text_blocks", rows, scope_keys={"business_context"})

    elif unit_key == "problem_statement":
        ps = result.get("problem_statement", "")
        root_causes = result.get("root_causes", [])
        rows = [{"row_key": "problem_statement", "field_key": "problem_statement", "text": ps}]
        if root_causes:
            rows.append({"row_key": "root_causes", "field_key": "root_causes",
                         "text": "\n".join(f"• {rc}" for rc in root_causes)})
        await _upsert("brd_text_blocks", rows, scope_keys={"problem_statement", "root_causes"})

    elif unit_key == "objectives":
        await _upsert("brd_objectives", result.get("objectives", []))
        traces = result.get("traceability", [])
        if traces:
            await _upsert_traceability(document_id, "brd_objectives", traces, db)

    elif unit_key == "stakeholders":
        await _upsert("brd_stakeholders", result.get("stakeholders", []))

    elif unit_key == "actors":
        await _upsert("brd_actors", result.get("actors", []))

    elif unit_key == "scope":
        await _upsert("brd_scope_items", result.get("scope_items", []))

    elif unit_key == "asis_process":
        steps = result.get("steps", [])
        for s in steps:
            s["step_type"] = "asis"
        # Use row_key prefix to scope correctly
        asis_keys = {s["row_key"] for s in steps}
        await _upsert("brd_process_steps", steps, scope_keys=asis_keys)

    elif unit_key == "tobe_process":
        steps = result.get("steps", [])
        for s in steps:
            s["step_type"] = "tobe"
        tobe_keys = {s["row_key"] for s in steps}
        await _upsert("brd_process_steps", steps, scope_keys=tobe_keys)

    elif unit_key == "business_requirements":
        brs = result.get("business_requirements", [])
        # Convert acceptance_criteria list[AcceptanceCriterion] to JSON-ready list
        for br in brs:
            if isinstance(br.get("acceptance_criteria"), list):
                br["acceptance_criteria"] = [
                    ac if isinstance(ac, dict) else ac.model_dump() if hasattr(ac, "model_dump") else ac
                    for ac in br["acceptance_criteria"]
                ]
        await _upsert("brd_business_requirements", brs)
        # Persist traceability rows
        traces = result.get("traceability", [])
        if traces:
            await _upsert_traceability(document_id, "brd_business_requirements", traces, db)

    elif unit_key == "data_entities":
        entities = result.get("entities", [])
        for e in entities:
            if "key_attributes" not in e:
                e["key_attributes"] = []
        await _upsert("brd_data_entities", entities)

    elif unit_key == "report_requirements":
        rrs = result.get("report_requirements", [])
        for rr in rrs:
            if "key_metrics" not in rr:
                rr["key_metrics"] = []
        await _upsert("brd_report_requirements", rrs)

    elif unit_key == "assumptions":
        await _upsert("brd_assumptions", result.get("assumptions", []))

    elif unit_key == "constraints":
        await _upsert("brd_constraints", result.get("constraints", []))

    elif unit_key == "dependencies":
        await _upsert("brd_dependencies", result.get("dependencies", []))

    elif unit_key == "risks":
        await _upsert("brd_risks", result.get("risks", []))
        traces = result.get("traceability", [])
        if traces:
            await _upsert_traceability(document_id, "brd_risks", traces, db)

    elif unit_key == "implementation_phases":
        phases = result.get("phases", [])
        for p in phases:
            if "included_br_refs" not in p:
                p["included_br_refs"] = []
        await _upsert("brd_phases", phases)

    elif unit_key == "milestones":
        await _upsert("brd_milestones", result.get("milestones", []))

    elif unit_key == "kpis":
        await _upsert("brd_kpis", result.get("kpis", []))
        traces = result.get("traceability", [])
        if traces:
            await _upsert_traceability(document_id, "brd_kpis", traces, db)

    elif unit_key == "open_questions":
        oqs = result.get("open_questions_list", [])
        await _upsert("brd_open_questions", oqs)

    elif unit_key == "decisions":
        await _upsert("brd_decisions", result.get("decisions", []))

    elif unit_key == "references":
        await _upsert("brd_references", result.get("references", []))

    elif unit_key == "glossary":
        await _upsert("brd_glossary_entries", result.get("glossary", []))


async def _upsert_traceability(
    document_id: uuid.UUID,
    source_table: str,
    traces: list[dict],
    db: AsyncSession,
) -> None:
    """Insert/replace traceability rows for a source table (no versioning — replace all)."""
    from sqlalchemy import delete as sa_delete
    source_row_keys = {t["source_row_key"] for t in traces}
    await db.execute(
        sa_delete(BrdTraceability).where(
            BrdTraceability.document_id == document_id,
            BrdTraceability.source_table == source_table,
            BrdTraceability.source_row_key.in_(source_row_keys),
        )
    )
    for t in traces:
        db.add(BrdTraceability(
            document_id=document_id,
            source_table=source_table,
            source_row_key=t["source_row_key"],
            target_kind=t["target_kind"],
            target_ref=t["target_ref"],
            target_label=t.get("target_label", ""),
            confidence=t.get("confidence", "high"),
        ))
    await db.flush()


# ── Core generation ────────────────────────────────────────────────────────────

async def generate_brd_unit(
    project: Project,
    unit_key: str,
    doc: ArtifactDocument,
    bundle,
    db: AsyncSession,
    discover_context: str = "",
) -> dict:
    """Run one BRD DSPy unit and persist its output rows."""
    from app.services.artifacts.manifest.brd import BRD_MANIFEST_BY_KEY
    spec = BRD_MANIFEST_BY_KEY[unit_key]
    query = f"{project.name} {project.description or ''} {unit_key} business requirements".strip()

    # Depth search for this unit's specific query
    doc_sections = await depth_search(
        project.id, db, query, artifact_document_id=doc.id
    )

    # Project the bundle to this unit's needs
    unit_ctx = project_for_unit(bundle, "brd", unit_key, doc_sections=doc_sections)

    # Gather Q&A (discover context + refinement answers)
    qa_pairs = await _gather_brd_unit_qa(doc.id, unit_key, db)
    if discover_context:
        qa_pairs = discover_context + ("\n\n" + qa_pairs if qa_pairs != "(none yet)" else "")

    # Upstream rows
    upstream: dict[str, list[dict]] = {}
    for dep_key in spec.depends_on:
        dep_spec = BRD_MANIFEST_BY_KEY[dep_key]
        upstream[dep_key] = {}
        for table in dep_spec.writes:
            rows = await _current_brd_rows_for(table, doc.id, db)
            if rows:
                upstream[dep_key][table] = rows

    # Current + locked rows
    current_rows: dict[str, list[dict]] = {}
    locked_rows: dict[str, list[dict]] = {}
    for table in spec.writes:
        current_rows[table] = await _current_brd_rows_for(table, doc.id, db)
        locked_rows[table] = await _locked_brd_rows_for(table, doc.id, db)

    result = await run_brd_unit(
        unit_key=unit_key,
        project_name=project.name,
        business_unit=project.business_unit or "—",
        description=project.description or "—",
        cb_context=unit_ctx.cb_context,
        source_sections=unit_ctx.doc_sections,
        app_brain=unit_ctx.app_brain,
        qa_pairs=qa_pairs,
        upstream=json.dumps(upstream),
        current_rows=json.dumps(current_rows),
        locked_rows=json.dumps(locked_rows),
    )

    await _persist_brd_unit_result(unit_key, doc.id, result, db)

    # Atomic JSONB merge — safe for concurrent unit sessions.
    # Use CAST(:param AS jsonb) not :param::jsonb — asyncpg misparses :: on named params.
    await db.execute(
        sa_text(
            "UPDATE artifact_documents"
            " SET unit_status = COALESCE(unit_status, '{}'::jsonb) || CAST(:patch AS jsonb),"
            "     updated_at  = NOW()"
            " WHERE id = :doc_id"
        ),
        {
            "patch": json.dumps({unit_key: {
                "completeness": result.get("completeness", 0),
                "confidence":   result.get("confidence", "low"),
            }}),
            "doc_id": str(doc.id),
        },
    )

    # Emit open questions as messages
    seq = await _next_brd_seq(doc.id, db)
    db.add(ArtifactMessage(
        document_id=doc.id, project_id=project.id, role="synthesis",
        content=f"Generated BRD section: {unit_key.replace('_', ' ')}.",
        citations=[], meta={"unit_key": unit_key}, seq=seq,
    ))
    seq += 1
    for oq in result.get("open_questions", []):
        db.add(ArtifactMessage(
            document_id=doc.id, project_id=project.id, role="question",
            content=oq.get("question", ""), citations=[],
            meta={"unit_key": unit_key, "field": oq.get("field"), "why": oq.get("why"),
                  "example": oq.get("example", "")},
            seq=seq,
        ))
        seq += 1

    await audit.emit(db, event="brd.unit_generated", actor_id=None,
                     metadata={"project_id": str(project.id), "unit_key": unit_key})
    return result


async def generate_brd_all(
    project: Project,
    db: AsyncSession,
    discover_context: str | None = None,
    context: str | None = None,
) -> dict:
    """Run all 22 BRD units in topological order with parallel branches.

    Each parallel unit gets its own AsyncSession to avoid SQLAlchemy's
    "concurrent operations not permitted" constraint on a shared session.
    unit_status updates use an atomic JSONB || merge so concurrent writes
    never clobber each other.
    """
    from app.db import AsyncSessionLocal
    from app.services.context.project_context import gather_project_context

    doc = await _ensure_brd_document(project.id, db)

    if context and context.strip():
        seq = await _next_brd_seq(doc.id, db)
        db.add(ArtifactMessage(
            document_id=doc.id, project_id=project.id, role="user",
            content=context.strip(), citations=[], meta={"is_initial_context": True}, seq=seq,
        ))
        await db.flush()
        await db.commit()

    # Assemble full-corpus context bundle once (readiness already checked by caller)
    bundle = await gather_project_context(project.id, db, artifact_document_id=doc.id)

    doc_id = doc.id  # capture before entering parallel scope
    MAX_CONCURRENCY = 4
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    completed: set[str] = set()

    async def _run_with_sem(unit_key: str) -> None:
        async with semaphore:
            # Each unit owns its session — no concurrent writes on a shared session
            async with AsyncSessionLocal() as unit_db:
                unit_doc = (
                    await unit_db.execute(
                        select(ArtifactDocument).where(ArtifactDocument.id == doc_id)
                    )
                ).scalar_one()

                await generate_brd_unit(
                    project, unit_key, unit_doc, bundle, unit_db,
                    discover_context=discover_context or "",
                )
                completed.add(unit_key)
                await unit_db.commit()

    # Clear previous run's unit_status so the DAG theater starts from blank
    doc.unit_status = {}
    doc.status = "generating"
    await db.commit()

    # Execute in topological waves (batch units whose deps are all done)
    remaining = list(BRD_TOPO_ORDER)
    while remaining:
        ready = [k for k in remaining if all(dep in completed for dep in BRD_MANIFEST_BY_KEY[k].depends_on)]
        if not ready:
            log.error("BRD generation stalled — cyclic dependency or missing unit")
            break
        await asyncio.gather(*[_run_with_sem(k) for k in ready])
        remaining = [k for k in remaining if k not in completed]

    # Final status update on the outer session
    await db.refresh(doc)
    us = dict(doc.unit_status or {})
    us.pop("_current_unit", None)
    doc.unit_status = us
    doc.status = "in_interview"
    await db.commit()
    return await get_brd_detail(project.id, db)


# ── Answer refinement ──────────────────────────────────────────────────────────

async def save_brd_answer(
    project_id: uuid.UUID, answer: str, db: AsyncSession, seq: int | None = None
) -> dict:
    doc = await _ensure_brd_document(project_id, db)
    s = await _next_brd_seq(doc.id, db)
    db.add(ArtifactMessage(
        document_id=doc.id, project_id=project_id, role="user",
        content=answer, citations=[], meta={}, seq=s,
    ))
    await db.flush()
    target_unit = await _resolve_brd_target_unit(doc.id, seq, db)
    us = dict(doc.unit_status or {})
    us.pop("_refine_error", None)
    us["_current_unit"] = target_unit
    doc.unit_status = us
    await db.commit()
    return await get_brd_detail(project_id, db)


async def _resolve_brd_target_unit(
    document_id: uuid.UUID, question_seq: int | None, db: AsyncSession
) -> str | None:
    if question_seq is not None:
        pinned = (await db.execute(
            select(ArtifactMessage).where(
                ArtifactMessage.document_id == document_id,
                ArtifactMessage.role == "question",
                ArtifactMessage.seq == question_seq,
            )
        )).scalar_one_or_none()
        if pinned:
            return (pinned.meta or {}).get("unit_key")
    questions = (await db.execute(
        select(ArtifactMessage)
        .where(ArtifactMessage.document_id == document_id, ArtifactMessage.role == "question")
        .order_by(ArtifactMessage.seq.desc())
    )).scalars().all()
    return (questions[0].meta or {}).get("unit_key") if questions else None


async def run_brd_regeneration(project_id: uuid.UUID, question_seq: int | None = None) -> None:
    """Background entry-point (called from Celery)."""
    from app.db import AsyncSessionLocal
    from app.services.context.project_context import gather_project_context
    async with AsyncSessionLocal() as db:
        doc = await _ensure_brd_document(project_id, db)
        project = await db.get(Project, project_id)
        target_unit = await _resolve_brd_target_unit(doc.id, question_seq, db)
        try:
            bundle = await gather_project_context(project_id, db, artifact_document_id=doc.id)
            if target_unit and target_unit in BRD_MANIFEST_BY_KEY:
                await generate_brd_unit(project, target_unit, doc, bundle, db)
            else:
                for unit_key in BRD_TOPO_ORDER:
                    await generate_brd_unit(project, unit_key, doc, bundle, db)

            us = dict(doc.unit_status or {})
            us.pop("_current_unit", None)
            us.pop("_refine_error", None)
            doc.unit_status = us
            doc.status = "in_interview"
            await db.commit()
        except Exception:
            us = dict(doc.unit_status or {})
            us.pop("_current_unit", None)
            us["_refine_error"] = target_unit or "unknown"
            doc.unit_status = us
            await db.commit()
            raise


# ── Row editing ────────────────────────────────────────────────────────────────

async def edit_brd_row(
    table_name: str, row_id: uuid.UUID, fields: dict,
    db: AsyncSession, user_id: uuid.UUID, lock: bool = True
) -> dict:
    model = BRD_TABLE_MAP[table_name]
    typed_cols = _BRD_TYPED_COLS[table_name]
    current = await db.get(model, row_id)
    if current is None or not current.is_current:
        raise ValueError(f"Row {row_id} not found or not current")
    int_cols = _BRD_INT_COLS.get(table_name, set())

    def _coerce(col: str, val: object) -> object:
        if col in int_cols and isinstance(val, str):
            try:
                return int(val)
            except (ValueError, TypeError):
                return getattr(current, col)
        return val

    current.is_current = False
    new_row = model(
        document_id=current.document_id, row_key=current.row_key,
        version=current.version + 1, is_current=True, is_locked=lock,
        status="active", source="human", created_by=user_id,
        **{c: _coerce(c, fields.get(c, getattr(current, c))) for c in typed_cols},
    )
    db.add(new_row)
    await db.flush()
    await db.refresh(new_row)
    return _brd_row_to_dict(new_row, table_name)


# ── Validation ─────────────────────────────────────────────────────────────────

async def validate_brd(
    project_id: uuid.UUID, db: AsyncSession, user_id: uuid.UUID
) -> dict:
    """Run the BRD validation checklist (A-G). On pass, set status=validated."""
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
        raise ValueError("BRD document not found")

    findings = await run_brd_validation(doc.id, doc, db)
    blocking = [f for f in findings if f["group"] in ("critical", "major")]
    if blocking:
        return {"ok": False, "findings": findings}

    doc.status = "validated"
    doc.validated_at = datetime.now(timezone.utc)
    doc.validated_by = user_id
    doc.updated_at = datetime.now(timezone.utc)
    doc.validated_snapshot_key = f"brd:{project_id}:validated"

    await audit.emit(db, event="brd.validated", actor_id=str(user_id),
                     metadata={"project_id": str(project_id)})
    await db.commit()
    return {"ok": True, "findings": findings}


# ── Detail query ───────────────────────────────────────────────────────────────

async def get_brd_detail(project_id: uuid.UUID, db: AsyncSession) -> dict:
    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == "brd",
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        return {"document": None, "sections": {}, "messages": [], "sources": []}

    sections: dict[str, list[dict]] = {}
    for table_name in BRD_TABLE_MAP:
        rows = await _current_brd_rows_for(table_name, doc.id, db)
        if rows:
            sections[table_name] = rows

    # Traceability
    traces = (
        await db.execute(
            select(BrdTraceability).where(BrdTraceability.document_id == doc.id)
        )
    ).scalars().all()
    traceability_by_source: dict[str, list[dict]] = {}
    for t in traces:
        traceability_by_source.setdefault(t.source_row_key, []).append({
            "id": str(t.id),
            "source_table": t.source_table,
            "source_row_key": t.source_row_key,
            "target_kind": t.target_kind,
            "target_ref": t.target_ref,
            "target_label": t.target_label,
            "confidence": t.confidence,
        })

    messages_rows = (
        await db.execute(
            select(ArtifactMessage).where(ArtifactMessage.document_id == doc.id)
            .order_by(ArtifactMessage.seq)
        )
    ).scalars().all()
    messages = [
        {"id": str(m.id), "role": m.role, "content": m.content,
         "citations": m.citations, "meta": m.meta, "seq": m.seq,
         "created_at": m.created_at.isoformat()}
        for m in messages_rows
    ]

    sources_rows = (
        await db.execute(
            select(ArtifactSource, Document.filename, Document.parse_status)
            .join(Document, Document.id == ArtifactSource.source_document_id)
            .where(ArtifactSource.artifact_document_id == doc.id)
        )
    ).all()
    sources = [
        {"id": str(s.id), "source_document_id": str(s.source_document_id),
         "filename": filename, "parse_status": parse_status, "included": s.included}
        for s, filename, parse_status in sources_rows
    ]

    return {
        "document": {
            "id": str(doc.id),
            "project_id": str(doc.project_id),
            "artifact_type": "brd",
            "status": doc.status,
            "unit_status": doc.unit_status,
            "validated_at": doc.validated_at.isoformat() if doc.validated_at else None,
            "validated_by": str(doc.validated_by) if doc.validated_by else None,
            "validated_snapshot_key": doc.validated_snapshot_key,
            "created_at": doc.created_at.isoformat(),
            "updated_at": doc.updated_at.isoformat(),
        },
        "sections": sections,
        "traceability_by_source": traceability_by_source,
        "messages": messages,
        "sources": sources,
    }
