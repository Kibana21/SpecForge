"""Artifact orchestrator: versioning, generation, Q&A, validation."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Type

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.models.artifact import (
    ArtifactDocument, ArtifactMessage, ArtifactSource,
    CbCapability, CbContextMap, CbGateCriterion, CbMetric,
    CbMilestone, CbOutcome, CbScopeItem, CbTextBlock,
)
from app.models.document import Document
from app.models.project import Project
from app.models.project_source import DocumentTree
from app.services.artifacts.app_context import gather_impacted_apps_context
from app.services.artifacts.manifest.concept_brief import (
    MANIFEST, MANIFEST_BY_KEY, TOPO_ORDER, VALIDATION_CHECKS, downstream_of,
)
from app.services.corpus_index import IndexedDoc, get_corpus_index_provider
from app.services.skills.dspy_artifacts import run_unit

log = logging.getLogger(__name__)

# CB table whitelist (maps table name → model class)
CB_TABLE_MAP: dict[str, type] = {
    "cb_text_blocks":  CbTextBlock,
    "cb_context_map":  CbContextMap,
    "cb_outcomes":     CbOutcome,
    "cb_metrics":      CbMetric,
    "cb_capabilities": CbCapability,
    "cb_scope_items":  CbScopeItem,
    "cb_milestones":   CbMilestone,
    "cb_gate_criteria": CbGateCriterion,
}

# Typed content columns per table (for change-detection in upsert_rows)
_TYPED_COLS: dict[str, list[str]] = {
    "cb_text_blocks":   ["field_key", "text"],
    "cb_context_map":   ["dimension", "detail"],
    "cb_outcomes":      ["outcome", "description"],
    "cb_metrics":       ["metric", "description", "quantifiable"],
    "cb_capabilities":  ["capability", "description"],
    "cb_scope_items":   ["kind", "text"],
    "cb_milestones":    ["milestone", "target", "description"],
    "cb_gate_criteria": ["criterion", "gate_status", "notes"],
}


# ── Core versioning ───────────────────────────────────────────────────────────

async def upsert_rows(
    table_name: str,
    document_id: uuid.UUID,
    output_rows: list[dict],
    source: str,
    db: AsyncSession,
    user_id: uuid.UUID | None = None,
    scope_keys: set[str] | None = None,
) -> int:
    """Idempotent row versioning. Returns number of new versions created.

    scope_keys: if provided, removal of stale rows is limited to this key set.
    This prevents one unit from marking another unit's rows (in the same shared
    table, e.g. cb_text_blocks) as removed.
    """
    model = CB_TABLE_MAP[table_name]
    typed_cols = _TYPED_COLS[table_name]
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

    # Only mark rows as removed if they fall within this unit's scope
    for row_key, current in existing_by_key.items():
        in_scope = scope_keys is None or row_key in scope_keys
        if in_scope and row_key not in output_keys and current.status != "removed":
            current.status = "removed"

    return new_versions


# ── Document management ───────────────────────────────────────────────────────

async def _ensure_document(
    project_id: uuid.UUID, artifact_type: str, db: AsyncSession
) -> ArtifactDocument:
    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == artifact_type,
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        try:
            async with db.begin_nested():
                doc = ArtifactDocument(
                    project_id=project_id, artifact_type=artifact_type, status="in_interview"
                )
                db.add(doc)
                await db.flush()
                project_docs = (
                    await db.execute(
                        select(Document.id).where(Document.project_id == project_id)
                    )
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
                        ArtifactDocument.artifact_type == artifact_type,
                    )
                )
            ).scalar_one()
    return doc


async def _next_seq(document_id: uuid.UUID, db: AsyncSession) -> int:
    cur = await db.scalar(
        select(func.coalesce(func.max(ArtifactMessage.seq), 0)).where(
            ArtifactMessage.document_id == document_id
        )
    )
    return (cur or 0) + 1


# ── Grounding helpers ─────────────────────────────────────────────────────────

async def _retrieve_artifact_sections(
    project_id: uuid.UUID, document_id: uuid.UUID, query: str, db: AsyncSession
) -> str:
    # Get included source doc ids for this artifact
    included_ids = (
        await db.execute(
            select(ArtifactSource.source_document_id).where(
                ArtifactSource.artifact_document_id == document_id,
                ArtifactSource.included.is_(True),
            )
        )
    ).scalars().all()

    if not included_ids:
        return "(no source sections)"

    from app.config import get_settings
    rows = (
        await db.execute(
            select(DocumentTree, Document.filename)
            .join(Document, Document.id == DocumentTree.document_id)
            .where(
                DocumentTree.project_id == project_id,
                DocumentTree.document_id.in_(included_ids),
            )
        )
    ).all()
    if not rows:
        return "(no source sections)"

    docs = [
        IndexedDoc(document_id=t.document_id, doc_name=name, tree=t.tree_json, page_texts=t.page_texts)
        for t, name in rows
    ]
    top_k = get_settings().tree_search_top_k
    sections = await get_corpus_index_provider().tree_search(query=query, docs=docs, top_k=top_k)
    if not sections:
        return "(no source sections)"
    return "\n\n".join(
        f"[S{i}] {s.doc_name} › {s.title}\n{s.text[:1200]}"
        for i, s in enumerate(sections, start=1)
    )


async def _gather_unit_qa(document_id: uuid.UUID, unit_key: str, db: AsyncSession) -> str:
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


async def _current_rows_for(
    table_name: str, document_id: uuid.UUID, db: AsyncSession
) -> list[dict]:
    model = CB_TABLE_MAP[table_name]
    rows = (
        await db.execute(
            select(model).where(
                model.document_id == document_id,
                model.is_current.is_(True),
                model.status == "active",
            )
        )
    ).scalars().all()
    return [_row_to_dict(r, table_name) for r in rows]


async def _locked_rows_for(
    table_name: str, document_id: uuid.UUID, db: AsyncSession
) -> list[dict]:
    model = CB_TABLE_MAP[table_name]
    rows = (
        await db.execute(
            select(model).where(
                model.document_id == document_id,
                model.is_current.is_(True),
                model.is_locked.is_(True),
            )
        )
    ).scalars().all()
    typed_cols = _TYPED_COLS[table_name]
    return [
        {"row_key": r.row_key, **{c: getattr(r, c) for c in typed_cols}}
        for r in rows
    ]


# ── Generation ────────────────────────────────────────────────────────────────

async def generate_unit(
    project: Project, unit_key: str, doc: ArtifactDocument, db: AsyncSession
) -> dict:
    """Run a single DSPy unit and persist its output."""
    spec = MANIFEST_BY_KEY[unit_key]
    query = f"{project.name}. {project.description or ''} {unit_key}".strip()

    # Gather grounding
    source_sections = await _retrieve_artifact_sections(project.id, doc.id, query, db)
    impacted_apps = await gather_impacted_apps_context(project.id, db)
    qa_pairs = await _gather_unit_qa(doc.id, unit_key, db)

    # Upstream rows (dependencies)
    upstream: dict[str, list[dict]] = {}
    for dep_key in spec.depends_on:
        dep_spec = MANIFEST_BY_KEY[dep_key]
        upstream[dep_key] = {}
        for table in dep_spec.writes:
            rows = await _current_rows_for(table, doc.id, db)
            if rows:
                upstream[dep_key][table] = rows

    # Current and locked rows for this unit's tables
    current_rows: dict[str, list[dict]] = {}
    locked_rows: dict[str, list[dict]] = {}
    for table in spec.writes:
        current_rows[table] = await _current_rows_for(table, doc.id, db)
        locked_rows[table] = await _locked_rows_for(table, doc.id, db)

    result = await run_unit(
        unit_key=unit_key,
        project_name=project.name,
        business_unit=project.business_unit or "—",
        description=project.description or "—",
        source_sections=source_sections,
        impacted_apps=impacted_apps or "(no impacted apps)",
        qa_pairs=qa_pairs,
        upstream=json.dumps(upstream),
        current_rows=json.dumps(current_rows),
        locked_rows=json.dumps(locked_rows),
    )

    # Persist rows per table
    await _persist_unit_result(unit_key, doc.id, result, db)

    # Update unit_status on document
    unit_status = dict(doc.unit_status or {})
    unit_status[unit_key] = {
        "completeness": result.get("completeness", 0),
        "confidence": result.get("confidence", "low"),
    }
    doc.unit_status = unit_status
    doc.updated_at = datetime.now(timezone.utc)

    # Append messages
    seq = await _next_seq(doc.id, db)
    db.add(ArtifactMessage(
        document_id=doc.id, project_id=project.id, role="synthesis",
        content=f"Generated {unit_key.replace('_', ' ')} section.",
        citations=[], meta={"unit_key": unit_key}, seq=seq,
    ))
    seq += 1
    for oq in result.get("open_questions", []):
        db.add(ArtifactMessage(
            document_id=doc.id, project_id=project.id, role="question",
            content=oq.get("question", ""), citations=[],
            meta={"unit_key": unit_key, "field": oq.get("field"), "why": oq.get("why")},
            seq=seq,
        ))
        seq += 1

    await audit.emit(db, event="artifact.unit_generated", actor_id=None,
                     metadata={"project_id": str(project.id), "unit_key": unit_key})
    return result


async def _persist_unit_result(
    unit_key: str, document_id: uuid.UUID, result: dict, db: AsyncSession
) -> None:
    """Map unit output fields to their respective cb_* tables."""
    if unit_key == "problem_context":
        text_rows = [
            {"row_key": "business_context", "field_key": "business_context", "text": result.get("business_context", "")},
            {"row_key": "problem_statement", "field_key": "problem_statement", "text": result.get("problem_statement", "")},
        ]
        await upsert_rows("cb_text_blocks", document_id, text_rows, "ai", db,
                          scope_keys={"business_context", "problem_statement"})
        await upsert_rows("cb_context_map", document_id, result.get("context_map", []), "ai", db)

    elif unit_key == "value_hypothesis":
        text_rows = [
            {"row_key": "value_hypothesis_if", "field_key": "value_hypothesis_if", "text": result.get("value_hypothesis_if", "")},
            {"row_key": "value_hypothesis_then", "field_key": "value_hypothesis_then", "text": result.get("value_hypothesis_then", "")},
        ]
        await upsert_rows("cb_text_blocks", document_id, text_rows, "ai", db,
                          scope_keys={"value_hypothesis_if", "value_hypothesis_then"})
        await upsert_rows("cb_outcomes", document_id, result.get("outcomes", []), "ai", db)

    elif unit_key == "metrics":
        await upsert_rows("cb_metrics", document_id, result.get("metrics", []), "ai", db)

    elif unit_key == "capabilities":
        await upsert_rows("cb_capabilities", document_id, result.get("capabilities", []), "ai", db)

    elif unit_key == "scope":
        await upsert_rows("cb_scope_items", document_id, result.get("scope_items", []), "ai", db)

    elif unit_key == "milestones":
        await upsert_rows("cb_milestones", document_id, result.get("milestones", []), "ai", db)


async def generate_all(project: Project, artifact_type: str, db: AsyncSession, context: str | None = None) -> dict:
    """Run all units in topological order and return the document state."""
    doc = await _ensure_document(project.id, artifact_type, db)

    # Store optional user-provided context as first message
    if context and context.strip():
        seq = await _next_seq(doc.id, db)
        db.add(ArtifactMessage(
            document_id=doc.id, project_id=project.id, role="user",
            content=context.strip(), citations=[], meta={"is_initial_context": True}, seq=seq,
        ))
        await db.flush()

    processed: set[str] = set()
    for unit_key in TOPO_ORDER:
        spec = MANIFEST_BY_KEY[unit_key]
        if all(dep in processed for dep in spec.depends_on):
            # Mark which unit is in progress (frontend polls this)
            us = dict(doc.unit_status or {})
            us["_current_unit"] = unit_key
            doc.unit_status = us
            await db.commit()

            await generate_unit(project, unit_key, doc, db)
            processed.add(unit_key)
            await db.commit()  # make this unit's rows visible immediately

    # Clear progress marker, set final status
    us = dict(doc.unit_status or {})
    us.pop("_current_unit", None)
    doc.unit_status = us
    doc.status = "in_interview"
    await refresh_gate(doc, db)
    await db.commit()
    return await get_artifact_detail(project.id, artifact_type, db)


async def incorporate_answer(
    project_id: uuid.UUID, artifact_type: str, answer: str, db: AsyncSession, seq: int | None = None
) -> dict:
    """Append user answer and re-run the tagged unit + its downstream dependents."""
    project = await db.get(Project, project_id)
    doc = await _ensure_document(project_id, artifact_type, db)

    next_seq = await _next_seq(doc.id, db)
    db.add(ArtifactMessage(
        document_id=doc.id, project_id=project_id, role="user",
        content=answer, citations=[], meta={}, seq=next_seq,
    ))
    await db.flush()

    # Find which unit to re-run (last unanswered question's unit_key)
    questions = (
        await db.execute(
            select(ArtifactMessage)
            .where(ArtifactMessage.document_id == doc.id, ArtifactMessage.role == "question")
            .order_by(ArtifactMessage.seq.desc())
        )
    ).scalars().all()
    target_unit = questions[0].meta.get("unit_key") if questions else None

    if target_unit and target_unit in MANIFEST_BY_KEY:
        units_to_run = [target_unit] + downstream_of(target_unit)
        for unit_key in units_to_run:
            if unit_key in MANIFEST_BY_KEY:
                await generate_unit(project, unit_key, doc, db)
    else:
        # Re-run all
        for unit_key in TOPO_ORDER:
            await generate_unit(project, unit_key, doc, db)

    await refresh_gate(doc, db)
    await db.commit()
    return await get_artifact_detail(project_id, artifact_type, db)


async def regenerate_unit(
    project: Project, unit_key: str, artifact_type: str, directive: str | None, db: AsyncSession
) -> dict:
    doc = await _ensure_document(project.id, artifact_type, db)
    if directive:
        seq = await _next_seq(doc.id, db)
        db.add(ArtifactMessage(
            document_id=doc.id, project_id=project.id, role="user",
            content=directive, citations=[], meta={"unit_key": unit_key}, seq=seq,
        ))
        await db.flush()
    await generate_unit(project, unit_key, doc, db)
    await db.commit()
    return await get_artifact_detail(project.id, artifact_type, db)


# ── Row editing ───────────────────────────────────────────────────────────────

async def edit_row(
    table_name: str, row_id: uuid.UUID, fields: dict,
    db: AsyncSession, user_id: uuid.UUID, lock: bool = True
) -> dict:
    model = CB_TABLE_MAP[table_name]
    typed_cols = _TYPED_COLS[table_name]
    current = await db.get(model, row_id)
    if current is None or not current.is_current:
        raise ValueError(f"Row {row_id} not found or not current")

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
    return _row_to_dict(new_row, table_name)


async def restore_row(
    table_name: str, document_id: uuid.UUID, row_key: str, version: int,
    db: AsyncSession, user_id: uuid.UUID
) -> dict:
    model = CB_TABLE_MAP[table_name]
    typed_cols = _TYPED_COLS[table_name]
    target = (
        await db.execute(
            select(model).where(
                model.document_id == document_id,
                model.row_key == row_key,
                model.version == version,
            )
        )
    ).scalar_one_or_none()
    if target is None:
        raise ValueError(f"Version {version} of {row_key} not found")

    # Mark current as no longer current
    current = (
        await db.execute(
            select(model).where(
                model.document_id == document_id,
                model.row_key == row_key,
                model.is_current.is_(True),
            )
        )
    ).scalar_one_or_none()
    if current:
        current.is_current = False
        current_version = current.version
    else:
        current_version = version

    new_row = model(
        document_id=document_id, row_key=row_key, version=current_version + 1,
        is_current=True, is_locked=False, status="active", source="human",
        created_by=user_id,
        **{c: getattr(target, c) for c in typed_cols},
    )
    db.add(new_row)
    await db.flush()
    await db.refresh(new_row)
    return _row_to_dict(new_row, table_name)


async def unlock_row(table_name: str, row_id: uuid.UUID, db: AsyncSession) -> dict:
    model = CB_TABLE_MAP[table_name]
    row = await db.get(model, row_id)
    if row is None:
        raise ValueError(f"Row {row_id} not found")
    row.is_locked = False
    await db.flush()
    return _row_to_dict(row, table_name)


def _row_to_dict(row: Any, table_name: str) -> dict:
    typed_cols = _TYPED_COLS[table_name]
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


async def get_row_history(
    table_name: str, document_id: uuid.UUID, row_key: str, db: AsyncSession
) -> list[dict]:
    model = CB_TABLE_MAP[table_name]
    rows = (
        await db.execute(
            select(model).where(
                model.document_id == document_id,
                model.row_key == row_key,
            ).order_by(model.version.desc())
        )
    ).scalars().all()
    return [_row_to_dict(r, table_name) for r in rows]


# ── Gate & validation ─────────────────────────────────────────────────────────

async def refresh_gate(doc: ArtifactDocument, db: AsyncSession) -> None:
    """Recompute clarity from unit_status completeness; keep go_no_go as-is."""
    unit_status = doc.unit_status or {}
    completeness_values = [v.get("completeness", 0) for v in unit_status.values()]
    if completeness_values:
        avg = sum(completeness_values) / len(completeness_values)
    else:
        avg = 0

    if avg >= 90:
        clarity_status = "Pass"
    elif avg >= 60:
        clarity_status = "Partial"
    else:
        clarity_status = "Fail"

    clarity_notes = f"Average completeness: {avg:.0f}% across {len(completeness_values)} unit(s)"

    # Upsert gate criteria rows
    for row_key, criterion, status_val, notes_val in [
        ("clarity",   "Clarity ≥90%",  clarity_status,  clarity_notes),
        ("go_no_go",  "Go / No-Go",    _current_go_no_go(doc.id, db), "Pending human validation"),
    ]:
        existing = (
            await db.execute(
                select(CbGateCriterion).where(
                    CbGateCriterion.document_id == doc.id,
                    CbGateCriterion.row_key == row_key,
                    CbGateCriterion.is_current.is_(True),
                )
            )
        ).scalar_one_or_none()

        if row_key == "go_no_go":
            # Don't overwrite a human-approved go_no_go
            if existing and existing.gate_status == "Approved":
                continue
            new_status = "Pending"
            new_notes = "Pending human validation"
        else:
            new_status = status_val
            new_notes = notes_val

        if existing is None:
            db.add(CbGateCriterion(
                document_id=doc.id, row_key=row_key, version=1, is_current=True,
                is_locked=False, status="active", source="ai",
                criterion=criterion, gate_status=new_status, notes=new_notes,
            ))
        elif existing.gate_status != new_status or existing.notes != new_notes:
            existing.is_current = False
            db.add(CbGateCriterion(
                document_id=doc.id, row_key=row_key, version=existing.version + 1,
                is_current=True, is_locked=False, status="active", source="ai",
                criterion=criterion, gate_status=new_status, notes=new_notes,
            ))

    await db.flush()


def _current_go_no_go(doc_id: uuid.UUID, db: AsyncSession) -> str:
    return "Pending"


async def validate(
    project_id: uuid.UUID, artifact_type: str, db: AsyncSession, user_id: uuid.UUID
) -> dict:
    """Run validation checklist; on pass set status=validated and pin snapshot."""
    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == artifact_type,
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        raise ValueError("Artifact document not found")

    failures = await _run_validation_checklist(doc.id, doc, db)
    if failures:
        return {"ok": False, "failures": failures}

    # Approve go_no_go
    go_no_go = (
        await db.execute(
            select(CbGateCriterion).where(
                CbGateCriterion.document_id == doc.id,
                CbGateCriterion.row_key == "go_no_go",
                CbGateCriterion.is_current.is_(True),
            )
        )
    ).scalar_one_or_none()

    if go_no_go:
        go_no_go.is_current = False
        db.add(CbGateCriterion(
            document_id=doc.id, row_key="go_no_go", version=go_no_go.version + 1,
            is_current=True, is_locked=True, status="active", source="human",
            criterion="Go / No-Go", gate_status="Approved",
            notes=f"Validated by user at {datetime.now(timezone.utc).isoformat()}",
            created_by=user_id,
        ))
    else:
        db.add(CbGateCriterion(
            document_id=doc.id, row_key="go_no_go", version=1,
            is_current=True, is_locked=True, status="active", source="human",
            criterion="Go / No-Go", gate_status="Approved",
            notes=f"Validated by user at {datetime.now(timezone.utc).isoformat()}",
            created_by=user_id,
        ))

    doc.status = "validated"
    doc.validated_at = datetime.now(timezone.utc)
    doc.validated_by = user_id
    doc.updated_at = datetime.now(timezone.utc)

    # Pin version snapshot
    snapshot_key = f"concept_brief:{project_id}:validated"
    doc.validated_snapshot_key = snapshot_key

    await audit.emit(db, event="artifact.validated", actor_id=str(user_id),
                     metadata={"project_id": str(project_id), "artifact_type": artifact_type})
    await db.commit()
    return {"ok": True, "failures": []}


async def _run_validation_checklist(
    document_id: uuid.UUID, doc: ArtifactDocument, db: AsyncSession
) -> list[str]:
    failures = []

    async def _get_text(field_key: str) -> str:
        row = (
            await db.execute(
                select(CbTextBlock).where(
                    CbTextBlock.document_id == document_id,
                    CbTextBlock.row_key == field_key,
                    CbTextBlock.is_current.is_(True),
                    CbTextBlock.status == "active",
                )
            )
        ).scalar_one_or_none()
        return row.text if row else ""

    async def _count(model, extra=None):
        stmt = select(func.count(model.id)).where(
            model.document_id == document_id,
            model.is_current.is_(True),
            model.status == "active",
        )
        if extra is not None:
            stmt = stmt.where(extra)
        return await db.scalar(stmt) or 0

    ps = await _get_text("problem_statement")
    if len(ps.strip()) < 20:
        failures.append("problem_statement_present: Problem statement must be present and non-trivial")

    vh_if = await _get_text("value_hypothesis_if")
    vh_then = await _get_text("value_hypothesis_then")
    if len(vh_if.strip()) < 10 or len(vh_then.strip()) < 10:
        failures.append("value_hypothesis_present: Value hypothesis (if/then) must be present")

    quant_count = await _count(CbMetric, CbMetric.quantifiable.is_(True))
    if quant_count < 1:
        failures.append("quantifiable_metric: At least one quantifiable metric required")

    if await _count(CbCapability) < 1:
        failures.append("capability_present: At least one capability required")

    in_count = await db.scalar(
        select(func.count(CbScopeItem.id)).where(
            CbScopeItem.document_id == document_id,
            CbScopeItem.is_current.is_(True),
            CbScopeItem.status == "active",
            CbScopeItem.kind == "in_scope",
        )
    ) or 0
    if in_count < 1:
        failures.append("in_scope_present: At least one in-scope item required")

    out_count = await db.scalar(
        select(func.count(CbScopeItem.id)).where(
            CbScopeItem.document_id == document_id,
            CbScopeItem.is_current.is_(True),
            CbScopeItem.status == "active",
            CbScopeItem.kind == "out_of_scope",
        )
    ) or 0
    if out_count < 1:
        failures.append("out_of_scope_present: At least one out-of-scope item required")

    assumption_count = await db.scalar(
        select(func.count(CbScopeItem.id)).where(
            CbScopeItem.document_id == document_id,
            CbScopeItem.is_current.is_(True),
            CbScopeItem.status == "active",
            CbScopeItem.kind == "assumption",
        )
    ) or 0
    if assumption_count < 1:
        failures.append("assumption_present: At least one assumption required")

    if await _count(CbMilestone) < 1:
        failures.append("milestone_present: At least one milestone required")

    unit_status = doc.unit_status or {}
    incomplete = [k for k, v in unit_status.items() if v.get("completeness", 0) < 90]
    if incomplete:
        failures.append(f"clarity_pass: Units below 90% completeness: {', '.join(incomplete)}")

    return failures


# ── Detail query ──────────────────────────────────────────────────────────────

async def get_artifact_detail(
    project_id: uuid.UUID, artifact_type: str, db: AsyncSession
) -> dict:
    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == artifact_type,
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        return {"document": None, "sections": {}, "messages": [], "sources": []}

    # Gather all current rows per table
    sections: dict[str, list[dict]] = {}
    for table_name in CB_TABLE_MAP:
        rows = await _current_rows_for(table_name, doc.id, db)
        if rows:
            sections[table_name] = rows

    # Messages
    messages_rows = (
        await db.execute(
            select(ArtifactMessage).where(ArtifactMessage.document_id == doc.id).order_by(ArtifactMessage.seq)
        )
    ).scalars().all()
    messages = [
        {
            "id": str(m.id),
            "document_id": str(m.document_id),
            "role": m.role,
            "content": m.content,
            "citations": m.citations,
            "meta": m.meta,
            "seq": m.seq,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages_rows
    ]

    # Sources
    sources_rows = (
        await db.execute(
            select(ArtifactSource, Document.filename, Document.parse_status)
            .join(Document, Document.id == ArtifactSource.source_document_id)
            .where(ArtifactSource.artifact_document_id == doc.id)
        )
    ).all()
    sources = [
        {
            "id": str(s.id),
            "source_document_id": str(s.source_document_id),
            "filename": filename,
            "parse_status": parse_status,
            "included": s.included,
        }
        for s, filename, parse_status in sources_rows
    ]

    return {
        "document": {
            "id": str(doc.id),
            "project_id": str(doc.project_id),
            "artifact_type": doc.artifact_type,
            "status": doc.status,
            "unit_status": doc.unit_status,
            "validated_at": doc.validated_at.isoformat() if doc.validated_at else None,
            "validated_by": str(doc.validated_by) if doc.validated_by else None,
            "created_at": doc.created_at.isoformat(),
            "updated_at": doc.updated_at.isoformat(),
        },
        "sections": sections,
        "messages": messages,
        "sources": sources,
    }
