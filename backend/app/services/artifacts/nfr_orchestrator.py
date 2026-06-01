"""NFR Artifact Orchestrator: versioning, generation, validation for the NFR artifact.

Mirrors brd_orchestrator.py (single-phase, manifest-driven) but:
- generation is SEQUENTIAL over NFR_TOPO_ORDER (overview → 7 categories → governance)
  because all category units share the nfr_requirements table and the GLOBAL NFR-nnn
  counter — parallel sessions would race the counter (gaps/dupes).
- every row in every section is editable / addable / deletable (table-agnostic CRUD).
- a server-computed Quality Radar summary ships in get_nfr_detail.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete as sa_delete, func, select, text as sa_text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.models.artifact import ArtifactDocument, ArtifactMessage, ArtifactSource
from app.models.document import Document
from app.models.nfr import (
    NfrDecision, NfrGlossary, NfrOpenQuestion, NfrReference, NfrRequirement,
    NfrRisk, NfrTextBlock, NfrTradeoff, NfrTraceability,
)
from app.models.project import Project
from app.services.artifacts.manifest.nfr import (
    NFR_CATEGORY_UNITS, NFR_MANIFEST_BY_KEY, NFR_TOPO_ORDER,
)
from app.services.context.docs_layer import depth_search
from app.services.context.projection import project_for_unit
from app.services.skills.dspy_nfr import run_nfr_unit

log = logging.getLogger(__name__)

# ── Table registry ─────────────────────────────────────────────────────────────

NFR_TABLE_MAP: dict[str, type] = {
    "nfr_requirements":   NfrRequirement,
    "nfr_risks":          NfrRisk,
    "nfr_tradeoffs":      NfrTradeoff,
    "nfr_open_questions": NfrOpenQuestion,
    "nfr_decisions":      NfrDecision,
    "nfr_references":     NfrReference,
    "nfr_glossary":       NfrGlossary,
    "nfr_text_blocks":    NfrTextBlock,
}

_NFR_TYPED_COLS: dict[str, list[str]] = {
    "nfr_requirements":   ["category", "attribute", "requirement", "priority", "rationale", "measurement", "brd_refs", "completeness", "confidence", "na"],
    "nfr_risks":          ["risk_id", "description", "affected_attribute", "impact", "likelihood", "mitigation", "owner", "risk_status"],
    "nfr_tradeoffs":      ["tradeoff", "options_considered", "decision", "rationale", "decided_on", "decision_maker"],
    "nfr_open_questions": ["question", "owner", "due_date", "oq_status"],
    "nfr_decisions":      ["description", "owner", "target_date", "decision_status"],
    "nfr_references":     ["ref_type", "title", "location", "notes"],
    "nfr_glossary":       ["term", "definition"],
    "nfr_text_blocks":    ["block_kind", "content"],
}

_NFR_INT_COLS: dict[str, set[str]] = {
    "nfr_requirements": {"completeness"},
}

# Row-key prefix per governance table (requirements use the global NFR-nnn counter).
_ROW_KEY_PREFIX: dict[str, str] = {
    "nfr_risks":          "NFR-R",
    "nfr_tradeoffs":      "NFR-TD",
    "nfr_open_questions": "NFR-OQ",
    "nfr_decisions":      "NFR-PD",
    "nfr_references":     "NFR-REF",
    "nfr_glossary":       "NFR-G",
}

# MoSCoW → weight for the Quality Radar.
_MOSCOW_WEIGHT = {"must": 4, "should": 3, "could": 2, "wont": 1}


# ── Row versioning ─────────────────────────────────────────────────────────────

async def upsert_nfr_rows(
    table_name: str,
    document_id: uuid.UUID,
    output_rows: list[dict],
    source: str,
    db: AsyncSession,
    user_id: uuid.UUID | None = None,
    scope_keys: set[str] | None = None,
) -> int:
    """Idempotent versioned upsert. Returns new versions created.

    Soft-deletes existing in-scope rows absent from output — but NEVER removes a
    locked row or a human-added row (source='human'), so manual content survives
    regeneration (R-CRUD-2).
    """
    model = NFR_TABLE_MAP[table_name]
    typed_cols = _NFR_TYPED_COLS[table_name]
    output_keys = {r["row_key"] for r in output_rows}
    new_versions = 0

    existing = (
        await db.execute(
            select(model).where(model.document_id == document_id, model.is_current.is_(True))
        )
    ).scalars().all()
    existing_by_key: dict[str, Any] = {r.row_key: r for r in existing}

    for row_data in output_rows:
        row_key = row_data["row_key"]
        row_data = _coerce_int_cols(table_name, row_data, existing_by_key.get(row_key))
        current = existing_by_key.get(row_key)
        if current is None:
            db.add(model(
                document_id=document_id, row_key=row_key, version=1,
                is_current=True, is_locked=False, status="active",
                source=source, created_by=user_id,
                **{c: row_data[c] for c in typed_cols if c in row_data},
            ))
            new_versions += 1
        elif current.is_locked or current.source == "human":
            continue  # protect locked + manual rows from regeneration
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
        if (in_scope and row_key not in output_keys and current.status != "removed"
                and not current.is_locked and current.source != "human"):
            current.status = "removed"

    return new_versions


def _coerce_int_cols(table: str, row: dict, existing: Any | None) -> dict:
    int_cols = _NFR_INT_COLS.get(table, set())
    if not int_cols:
        return row
    out = dict(row)
    for col in int_cols:
        if col in out and isinstance(out[col], str):
            try:
                out[col] = int(out[col])
            except (ValueError, TypeError):
                out[col] = getattr(existing, col, 0) if existing else 0
    return out


def _nfr_row_to_dict(row: Any, table_name: str) -> dict:
    typed_cols = _NFR_TYPED_COLS[table_name]
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


async def _current_nfr_rows_for(
    table_name: str, document_id: uuid.UUID, db: AsyncSession, *, category: str | None = None
) -> list[dict]:
    model = NFR_TABLE_MAP[table_name]
    conds = [model.document_id == document_id, model.is_current.is_(True), model.status == "active"]
    if category is not None and table_name == "nfr_requirements":
        conds.append(model.category == category)
    rows = (await db.execute(select(model).where(*conds))).scalars().all()
    return [_nfr_row_to_dict(r, table_name) for r in rows]


async def _locked_nfr_rows_for(
    table_name: str, document_id: uuid.UUID, db: AsyncSession, *, category: str | None = None
) -> list[dict]:
    model = NFR_TABLE_MAP[table_name]
    typed_cols = _NFR_TYPED_COLS[table_name]
    conds = [model.document_id == document_id, model.is_current.is_(True), model.is_locked.is_(True)]
    if category is not None and table_name == "nfr_requirements":
        conds.append(model.category == category)
    rows = (await db.execute(select(model).where(*conds))).scalars().all()
    return [{"row_key": r.row_key, **{c: getattr(r, c) for c in typed_cols}} for r in rows]


# ── Row-key allocation ──────────────────────────────────────────────────────────

async def _max_row_key_number(model: type, document_id: uuid.UUID, prefix: str, db: AsyncSession) -> int:
    """Highest numeric suffix among rows whose key starts with `{prefix}-` (incl. removed
    versions, so deletions never recycle a key)."""
    keys = (
        await db.execute(select(model.row_key).where(model.document_id == document_id).distinct())
    ).scalars().all()
    hi = 0
    for k in keys:
        if k and k.startswith(prefix + "-"):
            tail = k[len(prefix) + 1:]
            if tail.isdigit():
                hi = max(hi, int(tail))
    return hi


async def _next_global_nfr_number(document_id: uuid.UUID, db: AsyncSession) -> int:
    return await _max_row_key_number(NfrRequirement, document_id, "NFR", db) + 1


async def _next_nfr_row_key(document_id: uuid.UUID, table_name: str, db: AsyncSession) -> str:
    if table_name == "nfr_requirements":
        return f"NFR-{await _next_global_nfr_number(document_id, db):03d}"
    prefix = _ROW_KEY_PREFIX.get(table_name)
    if prefix is None:
        raise ValueError(f"Table {table_name} does not support add-row")
    model = NFR_TABLE_MAP[table_name]
    return f"{prefix}-{await _max_row_key_number(model, document_id, prefix, db) + 1:03d}"


# ── Document management ─────────────────────────────────────────────────────────

async def _ensure_nfr_document(project_id: uuid.UUID, db: AsyncSession) -> ArtifactDocument:
    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == "nfr",
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        try:
            async with db.begin_nested():
                doc = ArtifactDocument(project_id=project_id, artifact_type="nfr", status="in_interview")
                db.add(doc)
                await db.flush()
                project_docs = (
                    await db.execute(select(Document.id).where(Document.project_id == project_id))
                ).scalars().all()
                for doc_id in project_docs:
                    db.add(ArtifactSource(artifact_document_id=doc.id, source_document_id=doc_id, included=True))
                await db.flush()
        except IntegrityError:
            doc = (
                await db.execute(
                    select(ArtifactDocument).where(
                        ArtifactDocument.project_id == project_id,
                        ArtifactDocument.artifact_type == "nfr",
                    )
                )
            ).scalar_one()
    return doc


async def _next_nfr_seq(document_id: uuid.UUID, db: AsyncSession) -> int:
    cur = await db.scalar(
        select(func.coalesce(func.max(ArtifactMessage.seq), 0)).where(
            ArtifactMessage.document_id == document_id
        )
    )
    return (cur or 0) + 1


async def _read_initial_brief(document_id: uuid.UUID, db: AsyncSession) -> str:
    row = (
        await db.execute(
            select(ArtifactMessage)
            .where(ArtifactMessage.document_id == document_id, ArtifactMessage.role == "user")
            .order_by(ArtifactMessage.seq.desc())
        )
    ).scalars().all()
    for m in row:
        if (m.meta or {}).get("is_initial_brief"):
            return m.content
    return ""


async def _gather_nfr_unit_qa(document_id: uuid.UUID, unit_key: str, db: AsyncSession) -> str:
    rows = (
        await db.execute(
            select(ArtifactMessage)
            .where(ArtifactMessage.document_id == document_id, ArtifactMessage.role.in_(("question", "user")))
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


# ── Traceability ────────────────────────────────────────────────────────────────

async def _upsert_nfr_traceability(
    document_id: uuid.UUID, source_table: str, traces: list[dict], db: AsyncSession
) -> None:
    """Replace-all (per source_row_key) traceability rows."""
    if not traces:
        return
    source_row_keys = {t["source_row_key"] for t in traces}
    await db.execute(
        sa_delete(NfrTraceability).where(
            NfrTraceability.document_id == document_id,
            NfrTraceability.source_table == source_table,
            NfrTraceability.source_row_key.in_(source_row_keys),
        )
    )
    for t in traces:
        ref = (t.get("target_ref") or "").strip()
        kind = t.get("target_kind")
        if not ref or not kind:
            continue
        db.add(NfrTraceability(
            document_id=document_id, source_table=source_table,
            source_row_key=t["source_row_key"], target_kind=kind, target_ref=ref,
            target_label=t.get("target_label", ""), confidence=t.get("confidence", "high"),
        ))
    await db.flush()


# ── Persist unit output ─────────────────────────────────────────────────────────

async def _persist_nfr_unit_result(
    unit_key: str, document_id: uuid.UUID, result: dict, db: AsyncSession
) -> None:
    if unit_key == "overview":
        await upsert_nfr_rows(
            "nfr_text_blocks", document_id, result.get("text_blocks", []), "ai", db,
            scope_keys={"NFR-TB-overview", "NFR-TB-objectives"},
        )

    elif unit_key in NFR_CATEGORY_UNITS:
        reqs = result.get("requirements", [])
        for r in reqs:
            r.setdefault("category", unit_key)
        # Scope soft-delete to THIS category's existing rows only.
        existing_cat = await _current_nfr_rows_for("nfr_requirements", document_id, db, category=unit_key)
        scope = {r["row_key"] for r in existing_cat} | {r["row_key"] for r in reqs}
        await upsert_nfr_rows("nfr_requirements", document_id, reqs, "ai", db, scope_keys=scope)
        await _upsert_nfr_traceability(document_id, "nfr_requirements", result.get("traceability", []), db)

    elif unit_key == "governance":
        await upsert_nfr_rows("nfr_risks", document_id, result.get("risks", []), "ai", db)
        await upsert_nfr_rows("nfr_tradeoffs", document_id, result.get("tradeoffs", []), "ai", db)
        await upsert_nfr_rows("nfr_open_questions", document_id, result.get("open_questions_list", []), "ai", db)
        await upsert_nfr_rows("nfr_decisions", document_id, result.get("decisions", []), "ai", db)
        await upsert_nfr_rows("nfr_references", document_id, result.get("references", []), "ai", db)
        await upsert_nfr_rows("nfr_glossary", document_id, result.get("glossary", []), "ai", db)


# ── Core generation ─────────────────────────────────────────────────────────────

async def generate_nfr_unit(
    project: Project, unit_key: str, doc: ArtifactDocument, bundle, db: AsyncSession,
    *, brief: str = "",
) -> dict:
    """Run one NFR DSPy unit and persist its output rows."""
    spec = NFR_MANIFEST_BY_KEY[unit_key]
    query = f"{project.name} {project.description or ''} {unit_key} non-functional requirements".strip()
    doc_sections = await depth_search(project.id, db, query, artifact_document_id=doc.id)
    unit_ctx = project_for_unit(bundle, "nfr", unit_key, doc_sections=doc_sections)
    qa_pairs = await _gather_nfr_unit_qa(doc.id, unit_key, db)

    # current + locked rows for this unit's writes
    current_rows: dict[str, list[dict]] = {}
    locked_rows: dict[str, list[dict]] = {}
    cat = unit_key if unit_key in NFR_CATEGORY_UNITS else None
    for table in spec.writes:
        current_rows[table] = await _current_nfr_rows_for(table, doc.id, db, category=cat)
        locked_rows[table] = await _locked_nfr_rows_for(table, doc.id, db, category=cat)

    shared = dict(
        unit_instruction=spec.unit_instruction,
        project_name=project.name,
        business_unit=project.business_unit or "—",
        description=project.description or "—",
        brief=brief or "(none)",
        cb_context=unit_ctx.cb_context,
        brd_context=unit_ctx.brd_context or "(no BRD)",
        source_sections=unit_ctx.doc_sections,
        app_brain=unit_ctx.app_brain,
        qa_pairs=qa_pairs,
        current_rows=json.dumps(current_rows),
        locked_rows=json.dumps(locked_rows),
    )

    if unit_key in NFR_CATEGORY_UNITS:
        all_reqs = await _current_nfr_rows_for("nfr_requirements", doc.id, db)
        shared["category"] = unit_key
        shared["existing_nfr_keys"] = json.dumps(sorted(r["row_key"] for r in all_reqs))
    elif unit_key == "governance":
        all_reqs = await _current_nfr_rows_for("nfr_requirements", doc.id, db)
        shared["upstream"] = json.dumps(all_reqs)

    result = await run_nfr_unit(unit_key, **shared)
    await _persist_nfr_unit_result(unit_key, doc.id, result, db)

    # Atomic JSONB merge — safe even if a future revision parallelises units.
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
                "confidence": result.get("confidence", "low"),
            }}),
            "doc_id": str(doc.id),
        },
    )

    seq = await _next_nfr_seq(doc.id, db)
    db.add(ArtifactMessage(
        document_id=doc.id, project_id=project.id, role="synthesis",
        content=f"Generated NFR section: {spec.label}.",
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

    await audit.emit(db, event="nfr.unit_generated", actor_id=None,
                     metadata={"project_id": str(project.id), "unit_key": unit_key})
    return result


async def generate_nfr_all(
    project: Project, db: AsyncSession, *, brief: str | None = None,
) -> dict:
    """Run all 9 NFR units SEQUENTIALLY in TOPO order (global NFR-nnn counter safety)."""
    from app.services.context.project_context import gather_project_context

    doc = await _ensure_nfr_document(project.id, db)

    if brief and brief.strip():
        seq = await _next_nfr_seq(doc.id, db)
        db.add(ArtifactMessage(
            document_id=doc.id, project_id=project.id, role="user",
            content=brief.strip(), citations=[], meta={"is_initial_brief": True}, seq=seq,
        ))
        await db.flush()

    effective_brief = brief if (brief and brief.strip()) else await _read_initial_brief(doc.id, db)

    bundle = await gather_project_context(project.id, db, artifact_document_id=doc.id, artifact_type="nfr")

    doc.unit_status = {}
    doc.status = "generating"
    await db.commit()

    for unit_key in NFR_TOPO_ORDER:
        await db.execute(
            sa_text(
                "UPDATE artifact_documents"
                " SET unit_status = COALESCE(unit_status, '{}'::jsonb) || CAST(:patch AS jsonb)"
                " WHERE id = :doc_id"
            ),
            {"patch": json.dumps({"_current_unit": unit_key}), "doc_id": str(doc.id)},
        )
        await db.commit()
        await generate_nfr_unit(project, unit_key, doc, bundle, db, brief=effective_brief or "")
        await db.commit()

    await db.refresh(doc)
    us = dict(doc.unit_status or {})
    us.pop("_current_unit", None)
    doc.unit_status = us
    doc.status = "in_interview"
    await db.commit()
    return await get_nfr_detail(project.id, db)


async def run_nfr_generation(project_id: uuid.UUID, brief: str | None = None) -> None:
    """Background entry-point (called from the Celery task)."""
    from app.db import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        project = await db.get(Project, project_id)
        if project is None:
            log.error("run_nfr_generation: project %s not found", project_id)
            return
        await generate_nfr_all(project, db, brief=brief)


async def regenerate_nfr_unit(project_id: uuid.UUID, unit_key: str) -> None:
    """Background single-unit regeneration (called from the Celery task)."""
    from app.db import AsyncSessionLocal
    from app.services.context.project_context import gather_project_context
    async with AsyncSessionLocal() as db:
        project = await db.get(Project, project_id)
        doc = await _ensure_nfr_document(project_id, db)
        brief = await _read_initial_brief(doc.id, db)
        try:
            bundle = await gather_project_context(project_id, db, artifact_document_id=doc.id, artifact_type="nfr")
            await generate_nfr_unit(project, unit_key, doc, bundle, db, brief=brief)
            us = dict(doc.unit_status or {})
            us.pop("_current_unit", None)
            us.pop("_refine_error", None)
            doc.unit_status = us
            doc.status = "in_interview"
            await db.commit()
        except Exception:
            us = dict(doc.unit_status or {})
            us.pop("_current_unit", None)
            us["_refine_error"] = unit_key
            doc.unit_status = us
            await db.commit()
            raise


# ── Answer refinement ───────────────────────────────────────────────────────────

async def save_nfr_answer(
    project_id: uuid.UUID, answer: str, db: AsyncSession, seq: int | None = None
) -> dict:
    doc = await _ensure_nfr_document(project_id, db)
    s = await _next_nfr_seq(doc.id, db)
    db.add(ArtifactMessage(
        document_id=doc.id, project_id=project_id, role="user",
        content=answer, citations=[], meta={}, seq=s,
    ))
    await db.commit()
    return await get_nfr_detail(project_id, db)


# ── Row CRUD (table-agnostic across all 8 sections) ──────────────────────────────

async def edit_nfr_row(
    table_name: str, row_id: uuid.UUID, fields: dict,
    db: AsyncSession, user_id: uuid.UUID, lock: bool = True,
) -> dict:
    model = NFR_TABLE_MAP[table_name]
    typed_cols = _NFR_TYPED_COLS[table_name]
    current = await db.get(model, row_id)
    if current is None or not current.is_current:
        raise ValueError(f"Row {row_id} not found or not current")
    fields = _coerce_int_cols(table_name, fields, current)
    current.is_current = False
    new_row = model(
        document_id=current.document_id, row_key=current.row_key,
        version=current.version + 1, is_current=True, is_locked=lock,
        status="active", source="human", created_by=user_id,
        **{c: fields.get(c, getattr(current, c)) for c in typed_cols},
    )
    db.add(new_row)
    await db.flush()
    await db.refresh(new_row)
    return _nfr_row_to_dict(new_row, table_name)


async def delete_nfr_row(table_name: str, row_id: uuid.UUID, db: AsyncSession) -> dict:
    model = NFR_TABLE_MAP[table_name]
    row = await db.get(model, row_id)
    if row is None:
        raise ValueError(f"Row {row_id} not found")
    if row.is_locked:
        raise ValueError("Row is locked — unlock before deleting")
    row.status = "removed"
    await db.flush()
    return {"id": str(row_id), "status": "removed", "row_key": row.row_key}


async def unlock_nfr_row(table_name: str, row_id: uuid.UUID, db: AsyncSession) -> dict:
    model = NFR_TABLE_MAP[table_name]
    row = await db.get(model, row_id)
    if row is None:
        raise ValueError(f"Row {row_id} not found")
    row.is_locked = False
    await db.flush()
    return _nfr_row_to_dict(row, table_name)


async def restore_nfr_row(
    table_name: str, document_id: uuid.UUID, row_key: str, version: int,
    db: AsyncSession, user_id: uuid.UUID,
) -> dict:
    model = NFR_TABLE_MAP[table_name]
    typed_cols = _NFR_TYPED_COLS[table_name]
    target = (
        await db.execute(
            select(model).where(
                model.document_id == document_id, model.row_key == row_key, model.version == version,
            )
        )
    ).scalar_one_or_none()
    if target is None:
        raise ValueError(f"Version {version} of {row_key} not found")
    current = (
        await db.execute(
            select(model).where(
                model.document_id == document_id, model.row_key == row_key, model.is_current.is_(True),
            )
        )
    ).scalar_one_or_none()
    current_version = current.version if current else version
    if current:
        current.is_current = False
    new_row = model(
        document_id=document_id, row_key=row_key, version=current_version + 1,
        is_current=True, is_locked=False, status="active", source="human", created_by=user_id,
        **{c: getattr(target, c) for c in typed_cols},
    )
    db.add(new_row)
    await db.flush()
    await db.refresh(new_row)
    return _nfr_row_to_dict(new_row, table_name)


async def get_nfr_row_history(
    table_name: str, document_id: uuid.UUID, row_key: str, db: AsyncSession
) -> list[dict]:
    model = NFR_TABLE_MAP[table_name]
    rows = (
        await db.execute(
            select(model).where(model.document_id == document_id, model.row_key == row_key)
            .order_by(model.version.desc())
        )
    ).scalars().all()
    return [_nfr_row_to_dict(r, table_name) for r in rows]


async def add_nfr_row(
    document_id: uuid.UUID, table_name: str, fields: dict,
    db: AsyncSession, user_id: uuid.UUID, *, brd_links: list[dict] | None = None,
) -> dict:
    """Add a brand-new row to ANY section (R-CRUD-2). Allocates the next row_key."""
    if table_name not in NFR_TABLE_MAP:
        raise ValueError(f"Unknown NFR table: {table_name}")
    model = NFR_TABLE_MAP[table_name]
    typed_cols = _NFR_TYPED_COLS[table_name]
    row_key = await _next_nfr_row_key(document_id, table_name, db)
    fields = _coerce_int_cols(table_name, fields, None)

    new_row = model(
        document_id=document_id, row_key=row_key, version=1,
        is_current=True, is_locked=False, status="active", source="human", created_by=user_id,
        **{c: fields.get(c) for c in typed_cols if c in fields},
    )
    db.add(new_row)
    await db.flush()

    if table_name == "nfr_requirements" and brd_links:
        traces = [{
            "source_row_key": row_key,
            "target_kind": link["target_kind"],
            "target_ref": link["target_ref"],
            "target_label": link.get("target_label", ""),
            "confidence": link.get("confidence", "high"),
        } for link in brd_links]
        await _upsert_nfr_traceability(document_id, "nfr_requirements", traces, db)

    await db.refresh(new_row)
    return _nfr_row_to_dict(new_row, table_name)


# ── Validation ──────────────────────────────────────────────────────────────────

async def validate_nfr(project_id: uuid.UUID, db: AsyncSession, user_id: uuid.UUID) -> dict:
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
        raise ValueError("NFR document not found")

    findings = await run_nfr_validation(doc.id, doc, db)
    blocking = [f for f in findings if f["group"] in ("critical", "major")]
    if blocking:
        return {"ok": False, "findings": findings}

    # Bulk-lock all current rows so validated content is protected.
    for table_name, model in NFR_TABLE_MAP.items():
        rows = (
            await db.execute(
                select(model).where(
                    model.document_id == doc.id, model.is_current.is_(True), model.status == "active",
                )
            )
        ).scalars().all()
        for r in rows:
            r.is_locked = True

    doc.status = "validated"
    doc.validated_at = datetime.now(timezone.utc)
    doc.validated_by = user_id
    doc.updated_at = datetime.now(timezone.utc)
    doc.validated_snapshot_key = f"nfr:{project_id}:validated"

    await audit.emit(db, event="nfr.validated", actor_id=str(user_id),
                     metadata={"project_id": str(project_id)})
    await db.commit()
    return {"ok": True, "findings": findings}


# ── Detail query + Quality Radar ─────────────────────────────────────────────────

def _radar_summary(requirements: list[dict]) -> list[dict]:
    from app.services.artifacts.manifest.nfr import NFR_CATEGORY_UNITS
    by_cat: dict[str, list[dict]] = {c: [] for c in NFR_CATEGORY_UNITS}
    for r in requirements:
        if r.get("na"):
            continue
        by_cat.setdefault(r.get("category", ""), []).append(r)
    axes = []
    for cat in NFR_CATEGORY_UNITS:
        rows = by_cat.get(cat, [])
        by_priority = {"must": 0, "should": 0, "could": 0, "wont": 0}
        weighted = 0
        for r in rows:
            p = r.get("priority", "should")
            by_priority[p] = by_priority.get(p, 0) + 1
            weighted += _MOSCOW_WEIGHT.get(p, 0)
        axes.append({"category": cat, "count": len(rows), "weighted": weighted, "by_priority": by_priority})
    return axes


async def get_nfr_detail(project_id: uuid.UUID, db: AsyncSession) -> dict:
    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == "nfr",
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        return {"document": None, "sections": {}, "traceability_by_source": {},
                "radar": _radar_summary([]), "messages": [], "sources": []}

    sections: dict[str, list[dict]] = {}
    for table_name in NFR_TABLE_MAP:
        rows = await _current_nfr_rows_for(table_name, doc.id, db)
        if rows:
            sections[table_name] = rows

    traces = (
        await db.execute(select(NfrTraceability).where(NfrTraceability.document_id == doc.id))
    ).scalars().all()
    traceability_by_source: dict[str, list[dict]] = {}
    for t in traces:
        traceability_by_source.setdefault(t.source_row_key, []).append({
            "id": str(t.id), "source_table": t.source_table, "source_row_key": t.source_row_key,
            "target_kind": t.target_kind, "target_ref": t.target_ref,
            "target_label": t.target_label, "confidence": t.confidence,
        })

    messages_rows = (
        await db.execute(
            select(ArtifactMessage).where(ArtifactMessage.document_id == doc.id)
            .order_by(ArtifactMessage.seq)
        )
    ).scalars().all()
    messages = [
        {"id": str(m.id), "role": m.role, "content": m.content, "citations": m.citations,
         "meta": m.meta, "seq": m.seq, "created_at": m.created_at.isoformat()}
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
            "artifact_type": "nfr",
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
        "radar": _radar_summary(sections.get("nfr_requirements", [])),
        "messages": messages,
        "sources": sources,
    }
