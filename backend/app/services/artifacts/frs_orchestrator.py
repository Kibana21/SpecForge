"""FRS Artifact Orchestrator (Stage A — modularize).

Mirrors `brd_orchestrator.py` exactly but for the FRS artifact:
- Versioned row upsert with lock + soft-delete semantics
- Atomic JSONB `unit_status` merges (concurrent-safe)
- Mock-first DSPy (run_modularize → fixture in mock mode)
- Per-row savepoints (a single bad row doesn't poison the whole batch)
- Idempotent regen via current_modules / locked_modules JSON to the LLM

Stage B's `generate_frs_design_module` will be added to this same file when
Stage B ships.
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

from app.models.artifact import ArtifactDocument, ArtifactMessage, ArtifactSource
from app.models.document import Document
from app.models.project import Project
from app.services.artifacts.manifest.frs import (
    FRS_INT_COLS, FRS_MANIFEST_BY_KEY, FRS_TABLE_MAP, FRS_TYPED_COLS,
)
from app.services.context.project_context import (
    ProjectContextBundle, gather_project_context,
)
from app.services.context.projection import project_for_unit
from app.services.skills.dspy_frs import run_design_spec, run_modularize

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Versioned row upsert (the rugged core)
# ═══════════════════════════════════════════════════════════════════════════════


async def upsert_frs_rows(
    table_name: str,
    document_id: uuid.UUID,
    output_rows: list[dict[str, Any]],
    source: str,
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
    scope_keys: set[str] | None = None,
) -> int:
    """Idempotent versioned upsert for FRS typed tables.

    Returns count of new versions created.

    For each row by row_key:
      1. If no existing current row: insert as v1.
      2. If existing current row is locked: skip (preserve verbatim).
      3. If row's typed columns are unchanged: no-op.
      4. Otherwise: mark old is_current=False; insert new with version+1.

    Rows present in `scope_keys` but absent from `output_rows` get
    status='removed' (soft delete).
    """
    model = FRS_TABLE_MAP[table_name]
    typed_cols = FRS_TYPED_COLS[table_name]
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

        # Coerce string→int for known integer columns
        row_data = _coerce_int_cols(table_name, row_data, current)

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
            changed = any(
                getattr(current, c) != row_data.get(c)
                for c in typed_cols if c in row_data
            )
            if changed:
                current.is_current = False
                db.add(model(
                    document_id=document_id, row_key=row_key,
                    version=current.version + 1,
                    is_current=True, is_locked=False, status="active",
                    source=source, created_by=user_id,
                    **{c: row_data[c] for c in typed_cols if c in row_data},
                ))
                new_versions += 1

    # Soft-delete rows in scope but absent from output.
    # Locked rows are preserved verbatim — they survive regen even when the LLM
    # forgets to include them in its output.
    for row_key, current in existing_by_key.items():
        in_scope = scope_keys is None or row_key in scope_keys
        if (in_scope and row_key not in output_keys
                and current.status != "removed"
                and not current.is_locked):
            current.status = "removed"

    return new_versions


def _coerce_int_cols(table: str, row: dict, existing: Any | None) -> dict:
    """LLM/UI sometimes ships ints as strings; coerce them per FRS_INT_COLS."""
    int_cols = FRS_INT_COLS.get(table, set())
    if not int_cols:
        return row
    out = dict(row)
    for col in int_cols:
        if col in out and isinstance(out[col], str):
            try:
                out[col] = int(out[col])
            except (ValueError, TypeError):
                out[col] = getattr(existing, col) if existing else None
    return out


async def _current_frs_rows_for(
    table_name: str, document_id: uuid.UUID, db: AsyncSession,
) -> list[dict]:
    model = FRS_TABLE_MAP[table_name]
    rows = (
        await db.execute(
            select(model).where(
                model.document_id == document_id,
                model.is_current.is_(True),
                model.status == "active",
            )
        )
    ).scalars().all()
    return [_frs_row_to_dict(r, table_name) for r in rows]


async def _locked_frs_rows_for(
    table_name: str, document_id: uuid.UUID, db: AsyncSession,
) -> list[dict]:
    model = FRS_TABLE_MAP[table_name]
    typed_cols = FRS_TYPED_COLS[table_name]
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


def _frs_row_to_dict(row: Any, table_name: str) -> dict:
    typed_cols = FRS_TYPED_COLS[table_name]
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


# ═══════════════════════════════════════════════════════════════════════════════
# Document lifecycle
# ═══════════════════════════════════════════════════════════════════════════════


async def _ensure_frs_document(
    project_id: uuid.UUID, db: AsyncSession,
) -> ArtifactDocument:
    """Get-or-create the FRS ArtifactDocument for a project. Idempotent + race-safe."""
    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == "frs",
            )
        )
    ).scalar_one_or_none()
    if doc is not None:
        return doc

    try:
        async with db.begin_nested():
            doc = ArtifactDocument(
                project_id=project_id, artifact_type="frs", status="in_interview",
            )
            db.add(doc)
            await db.flush()
            # Auto-enroll every project document as an FRS source
            doc_ids = (
                await db.execute(
                    select(Document.id).where(Document.project_id == project_id)
                )
            ).scalars().all()
            for did in doc_ids:
                db.add(ArtifactSource(
                    artifact_document_id=doc.id,
                    source_document_id=did,
                    included=True,
                ))
            await db.flush()
        return doc
    except IntegrityError:
        # Race: another caller created it first
        doc = (
            await db.execute(
                select(ArtifactDocument).where(
                    ArtifactDocument.project_id == project_id,
                    ArtifactDocument.artifact_type == "frs",
                )
            )
        ).scalar_one()
        return doc


async def _next_frs_seq(document_id: uuid.UUID, db: AsyncSession) -> int:
    cur = await db.scalar(
        select(func.coalesce(func.max(ArtifactMessage.seq), 0)).where(
            ArtifactMessage.document_id == document_id
        )
    )
    return (cur or 0) + 1


async def _set_current_unit(
    doc_id: uuid.UUID, unit_key: str | None, db: AsyncSession,
) -> None:
    """Atomic JSONB merge to update _current_unit pointer."""
    await db.execute(sa_text(
        "UPDATE artifact_documents "
        "SET unit_status = COALESCE(unit_status, '{}'::jsonb) || CAST(:patch AS jsonb), "
        "    updated_at = NOW() "
        "WHERE id = :doc_id"
    ), {"patch": json.dumps({"_current_unit": unit_key}), "doc_id": str(doc_id)})


async def _read_initial_brief(doc_id: uuid.UUID, db: AsyncSession) -> str:
    """Return the most recent user message with meta.is_initial_brief=True, else ''."""
    rows = (
        await db.execute(
            select(ArtifactMessage)
            .where(
                ArtifactMessage.document_id == doc_id,
                ArtifactMessage.role == "user",
            )
            .order_by(ArtifactMessage.seq.desc())
            .limit(20)
        )
    ).scalars().all()
    for m in rows:
        if m.meta and m.meta.get("is_initial_brief"):
            return m.content or ""
    return ""


async def _gather_frs_unit_qa(
    document_id: uuid.UUID, unit_key: str, db: AsyncSession,
) -> str:
    """Collect discover questions + user answers + synthesis messages for a unit.

    Messages with no `meta.unit_key` (general refinement) are included for every unit.
    """
    rows = (
        await db.execute(
            select(ArtifactMessage)
            .where(
                ArtifactMessage.document_id == document_id,
                ArtifactMessage.role.in_(("question", "user", "synthesis")),
            )
            .order_by(ArtifactMessage.seq)
        )
    ).scalars().all()
    relevant = []
    for m in rows:
        uk = m.meta.get("unit_key") if m.meta else None
        if uk is None or uk == unit_key:
            prefix = {"question": "Q", "user": "A", "synthesis": "S"}.get(m.role, m.role)
            relevant.append(f"{prefix}: {m.content}")
    return "\n".join(relevant) or "(none yet)"


async def _serialize_current_modules_with_children(
    document_id: uuid.UUID, db: AsyncSession,
) -> list[dict]:
    """JSON-serializable snapshot of current modules + all child rows.

    Used as `current_modules` input to the LLM for idempotent regen.
    """
    from app.models.frs import (
        FrsModule, FrsModuleActor, FrsModuleResponsibility,
        FrsModuleInterface, FrsModuleDataEntity, FrsSpec,
    )

    modules = (
        await db.execute(
            select(FrsModule).where(
                FrsModule.document_id == document_id,
                FrsModule.is_current.is_(True),
                FrsModule.status == "active",
            )
        )
    ).scalars().all()

    async def _children(model: type, mod_row_key: str, cols: list[str]) -> list[dict]:
        rows = (
            await db.execute(
                select(model).where(
                    model.document_id == document_id,
                    model.module_row_key == mod_row_key,  # type: ignore[attr-defined]
                    model.is_current.is_(True),
                    model.status == "active",
                )
            )
        ).scalars().all()
        out = []
        for r in rows:
            entry = {"row_key": r.row_key, "_is_locked": r.is_locked}
            for c in cols:
                if c == "module_row_key":  # already implied by container
                    continue
                entry[c] = getattr(r, c)
            out.append(entry)
        return out

    snapshot = []
    for m in modules:
        snapshot.append({
            "row_key": m.row_key,
            "name": m.name, "slug": m.slug, "layer": m.layer,
            "scope_in": m.scope_in, "scope_out": m.scope_out, "summary": m.summary,
            "figma_root_link": m.figma_root_link,
            "_is_locked": m.is_locked,
            "actors": await _children(
                FrsModuleActor, m.row_key,
                ["module_row_key", "actor_name", "relationship", "notes"],
            ),
            "responsibilities": await _children(
                FrsModuleResponsibility, m.row_key,
                ["module_row_key", "responsibility", "frs_refs"],
            ),
            "interfaces": await _children(
                FrsModuleInterface, m.row_key,
                ["module_row_key", "interface_kind", "direction", "transport",
                 "name", "counterpart", "user_role", "purpose", "frs_ref"],
            ),
            "data_entities": await _children(
                FrsModuleDataEntity, m.row_key,
                ["module_row_key", "entity_name", "business_purpose", "source_of_truth"],
            ),
            "frs_backlog": await _children(
                FrsSpec, m.row_key,
                ["module_row_key", "title", "priority", "layer", "br_refs",
                 "narrative", "completeness", "confidence"],
            ),
        })
    return snapshot


# ═══════════════════════════════════════════════════════════════════════════════
# Stage A — generate_frs_modularize
# ═══════════════════════════════════════════════════════════════════════════════


async def generate_frs_modularize(
    project: Project,
    doc: ArtifactDocument,
    bundle: ProjectContextBundle,
    db: AsyncSession,
) -> dict:
    """Run the modularize DSPy unit and persist its output across 6 tables.

    Atomic + idempotent. Existing locked rows are preserved verbatim. Soft-deletes
    modules removed by the AI.
    """
    spec = FRS_MANIFEST_BY_KEY["modularize"]

    # Signal that we're on Phase A
    await _set_current_unit(doc.id, "modularize", db)
    await db.flush()

    unit_ctx = project_for_unit(bundle, "frs", "modularize")
    qa_pairs = await _gather_frs_unit_qa(doc.id, "modularize", db)
    brief = await _read_initial_brief(doc.id, db)
    current_modules = await _serialize_current_modules_with_children(doc.id, db)
    locked_modules = [m for m in current_modules if m.get("_is_locked")]

    log.info(
        "frs.modularize.start",
        extra={
            "project_id": str(project.id), "doc_id": str(doc.id),
            "brd_status": bundle.brd.brd_status if bundle.brd else None,
            "current_module_count": len(current_modules),
            "locked_count": len(locked_modules),
        },
    )

    try:
        result = await asyncio.wait_for(
            run_modularize(
                project_name=project.name,
                business_unit=project.business_unit or "—",
                brief=brief,
                brd_context=bundle.brd.formatted_context if bundle.brd else "(no BRD)",
                cb_context=bundle.cb.formatted_context,
                app_brain=bundle.apps.formatted_context,
                source_sections=unit_ctx.doc_sections,
                qa_pairs=qa_pairs,
                current_modules=json.dumps(current_modules),
                locked_modules=json.dumps(locked_modules),
            ),
            timeout=spec.timeout_seconds,
        )
    except asyncio.TimeoutError:
        log.error("frs.modularize.timeout", extra={"doc_id": str(doc.id)})
        await _set_current_unit(doc.id, None, db)
        raise

    log.info(
        "frs.modularize.complete",
        extra={
            "doc_id": str(doc.id),
            "module_count": len(result.get("modules", [])),
            "decision_count": len(result.get("spec_decisions", [])),
            "completeness": result.get("completeness"),
            "confidence": result.get("confidence"),
        },
    )

    await _persist_modularize_result(doc.id, result, db)

    # Atomic unit_status update
    await db.execute(sa_text(
        "UPDATE artifact_documents "
        "SET unit_status = COALESCE(unit_status, '{}'::jsonb) || CAST(:patch AS jsonb), "
        "    updated_at = NOW() "
        "WHERE id = :doc_id"
    ), {
        "patch": json.dumps({
            "modularize": {
                "completeness": result.get("completeness", 0),
                "confidence": result.get("confidence", "low"),
            },
            "_current_unit": None,
        }),
        "doc_id": str(doc.id),
    })

    await _emit_modularize_messages(doc, result, db)
    return result


async def _persist_modularize_result(
    document_id: uuid.UUID, result: dict, db: AsyncSession,
) -> None:
    """Route the modularize output to the 7 Stage-A tables.

    Order matters: modules first (parent), then child rows (FK semantic).
    Soft-delete child rows not in the new output by scoping per-module-row_key.
    """
    modules = result.get("modules", [])

    # 1. frs_modules (top-level; scope_keys = all module row_keys)
    module_rows = [
        {
            "row_key": m["row_key"],
            "name": m["name"],
            "slug": m["slug"],
            "layer": m["layer"],
            "scope_in": m.get("scope_in", ""),
            "scope_out": m.get("scope_out", ""),
            "summary": m.get("summary", ""),
            "figma_root_link": m.get("figma_root_link"),
            "completeness": result.get("completeness", 0),
            "confidence": result.get("confidence", "low"),
        }
        for m in modules
    ]
    module_keys = {m["row_key"] for m in module_rows}
    await upsert_frs_rows(
        "frs_modules", document_id, module_rows, "ai", db,
        scope_keys=module_keys,
    )

    # 2-5. Child tables per module
    # IMPORTANT: per-module upserts must scope soft-delete to THIS module's
    # row_keys only, otherwise the second-module upsert will mark the first-
    # module's rows as removed. We pass scope_keys = the output row_keys for
    # this module so only this module's deleted children are soft-deleted.
    for m in modules:
        mod_key = m["row_key"]

        # Actors
        actor_rows = [
            {
                "row_key": f"{mod_key}-ACT-{i}",
                "module_row_key": mod_key,
                "actor_name": a["actor_name"],
                "relationship": a["relationship"],
                "notes": a.get("notes", ""),
            }
            for i, a in enumerate(m.get("actors", []), 1)
        ]
        await upsert_frs_rows(
            "frs_module_actors", document_id, actor_rows, "ai", db,
            scope_keys=await _module_child_existing_keys(
                "frs_module_actors", document_id, mod_key, db,
            ),
        )

        # Responsibilities
        resp_rows = [
            {
                "row_key": f"{mod_key}-R-{i}",
                "module_row_key": mod_key,
                "responsibility": r["responsibility"],
                "frs_refs": r.get("frs_refs", []),
            }
            for i, r in enumerate(m.get("responsibilities", []), 1)
        ]
        await upsert_frs_rows(
            "frs_module_responsibilities", document_id, resp_rows, "ai", db,
            scope_keys=await _module_child_existing_keys(
                "frs_module_responsibilities", document_id, mod_key, db,
            ),
        )

        # Interfaces
        iface_rows = [
            {
                "row_key": f"{mod_key}-IF-{i}",
                "module_row_key": mod_key,
                "interface_kind": iface["interface_kind"],
                "direction": iface.get("direction"),
                "transport": iface.get("transport"),
                "name": iface["name"],
                "counterpart": iface.get("counterpart"),
                "user_role": iface.get("user_role"),
                "purpose": iface.get("purpose", ""),
                "frs_ref": iface.get("frs_ref"),
            }
            for i, iface in enumerate(m.get("interfaces", []), 1)
        ]
        await upsert_frs_rows(
            "frs_module_interfaces", document_id, iface_rows, "ai", db,
            scope_keys=await _module_child_existing_keys(
                "frs_module_interfaces", document_id, mod_key, db,
            ),
        )

        # Data entities (module-level)
        de_rows = [
            {
                "row_key": f"{mod_key}-E-{i}",
                "module_row_key": mod_key,
                "entity_name": e["entity_name"],
                "business_purpose": e.get("business_purpose", ""),
                "source_of_truth": e.get("source_of_truth", ""),
            }
            for i, e in enumerate(m.get("data_entities", []), 1)
        ]
        await upsert_frs_rows(
            "frs_module_data_entities", document_id, de_rows, "ai", db,
            scope_keys=await _module_child_existing_keys(
                "frs_module_data_entities", document_id, mod_key, db,
            ),
        )

        # Backlog stubs → frs_specs (stub form, completeness=0)
        stub_rows = [
            {
                "row_key": stub["row_key"],
                "module_row_key": mod_key,
                "title": stub["title"],
                "priority": stub["priority"],
                "layer": m["layer"],
                "br_refs": stub.get("br_refs", []),
                "nfr_refs": [],
                "depends_on": [],
                "narrative": stub.get("description", ""),
                "independent_test": "",
                "data_and_validation": "",
                "errors_and_edge_cases": "",
                "observability": "",
                "implementation_tasks": [],
                "completeness": 0,
                "confidence": "low",
            }
            for stub in m.get("frs_backlog", [])
        ]
        # Scope soft-delete to this module's existing stubs only (other modules'
        # stubs are preserved). Stage B specs that already exist for this module
        # are preserved too: their row_keys will be in the existing set and won't
        # be in stub_rows unless the AI explicitly re-emitted them — see Stage B
        # plan for the merge story.
        await upsert_frs_rows(
            "frs_specs", document_id, stub_rows, "ai", db,
            scope_keys=await _module_child_existing_keys(
                "frs_specs", document_id, mod_key, db,
            ),
        )

    # 7. Module-scoped decisions
    decision_rows = []
    for d in result.get("spec_decisions", []):
        if d.get("spec_row_key"):  # spec-scoped — defer to Stage B
            continue
        decision_rows.append({
            "row_key": d["row_key"],
            "module_row_key": d.get("module_row_key"),
            "spec_row_key": None,
            "question": d["question"],
            "options": d.get("options", []),
            "recommended_index": d.get("recommended_index", 0),
            "recommended_rationale": d.get("recommended_rationale", ""),
            "user_chosen_index": None,
            "resolution_status": "open",
        })
    if decision_rows:
        await upsert_frs_rows("frs_spec_decisions", document_id, decision_rows, "ai", db)


async def _module_child_existing_keys(
    table_name: str,
    document_id: uuid.UUID,
    module_row_key: str,
    db: AsyncSession,
) -> set[str]:
    """Return the set of current-active row_keys for `table_name` belonging to
    `module_row_key`. Used as `scope_keys` for the per-module upsert so soft-
    delete is scoped to THIS module's rows only (not other modules')."""
    model = FRS_TABLE_MAP[table_name]
    rows = (
        await db.execute(
            select(model.row_key).where(
                model.document_id == document_id,
                model.module_row_key == module_row_key,  # type: ignore[attr-defined]
                model.is_current.is_(True),
                model.status == "active",
            )
        )
    ).scalars().all()
    return set(rows)


async def _emit_modularize_messages(
    doc: ArtifactDocument, result: dict, db: AsyncSession,
) -> None:
    """Emit synthesis + open-decision messages into artifact_messages."""
    seq = await _next_frs_seq(doc.id, db)

    # 1. Synthesis message
    mod_count = len(result.get("modules", []))
    total_stubs = sum(len(m.get("frs_backlog", [])) for m in result.get("modules", []))
    synthesis = (
        f"Modularization complete: {mod_count} module{'s' if mod_count != 1 else ''}, "
        f"{total_stubs} FRS backlog stub{'s' if total_stubs != 1 else ''}. "
        f"Confidence: {result.get('confidence', 'low')}."
    )
    db.add(ArtifactMessage(
        document_id=doc.id, project_id=doc.project_id,
        role="synthesis", content=synthesis, citations=[],
        meta={"unit_key": "modularize"}, seq=seq,
    ))
    seq += 1

    # 2. One question message per open SpecDecision (module-scoped)
    for d in result.get("spec_decisions", []):
        if d.get("spec_row_key"):
            continue
        body = (
            f"[SPEC-DECISION] {d['question']}\n"
            f"AI recommends option {d.get('recommended_index', 0)}: "
            f"{d.get('recommended_rationale', '(no rationale)')}"
        )
        db.add(ArtifactMessage(
            document_id=doc.id, project_id=doc.project_id,
            role="question", content=body, citations=[],
            meta={
                "unit_key": "modularize",
                "type": "spec_decision_open",
                "decision_row_key": d["row_key"],
                "module_row_key": d.get("module_row_key"),
            },
            seq=seq,
        ))
        seq += 1


# ═══════════════════════════════════════════════════════════════════════════════
# Stage B — design_module helpers + persistence
# ═══════════════════════════════════════════════════════════════════════════════


async def _serialize_module_with_children(
    document_id: uuid.UUID, module_row_key: str, db: AsyncSession,
) -> dict:
    """JSON-serializable snapshot of one module + all its child rows.

    Used as `module_context` input to the design_module LLM call.
    """
    snapshots = await _serialize_current_modules_with_children(document_id, db)
    for s in snapshots:
        if s["row_key"] == module_row_key:
            return s
    raise ValueError(f"module {module_row_key} not found in document {document_id}")


async def _summarize_other_modules(
    document_id: uuid.UUID, exclude_module_row_key: str, db: AsyncSession,
) -> list[dict]:
    """Compact summary of sibling modules — used so each design_module call has
    cross-module awareness (for depends_on + interface counterparts).
    """
    from app.models.frs import FrsModule, FrsModuleInterface

    modules = (
        await db.execute(
            select(FrsModule).where(
                FrsModule.document_id == document_id,
                FrsModule.is_current.is_(True),
                FrsModule.status == "active",
                FrsModule.row_key != exclude_module_row_key,
            )
        )
    ).scalars().all()

    out: list[dict] = []
    for m in modules:
        ifaces = (
            await db.execute(
                select(FrsModuleInterface).where(
                    FrsModuleInterface.document_id == document_id,
                    FrsModuleInterface.module_row_key == m.row_key,
                    FrsModuleInterface.is_current.is_(True),
                    FrsModuleInterface.status == "active",
                )
            )
        ).scalars().all()
        out.append({
            "row_key": m.row_key,
            "name": m.name,
            "layer": m.layer,
            "summary": m.summary,
            "interfaces": [{
                "kind": i.interface_kind,
                "direction": i.direction,
                "transport": i.transport,
                "name": i.name,
                "counterpart": i.counterpart,
                "purpose": i.purpose,
            } for i in ifaces],
        })
    return out


async def _serialize_module_specs(
    document_id: uuid.UUID, module_row_key: str, db: AsyncSession,
) -> list[dict]:
    """All current specs in a module + their sub-rows. Used as `current_specs`
    input to the design_module LLM call for idempotent regeneration."""
    from app.models.frs import (
        FrsSpec, FrsScreen, FrsUiComponent, FrsEndpoint,
        FrsDataEntity, FrsBusinessRule,
        FrsAcceptanceScenario, FrsFunctionalRequirement,
    )

    specs = (
        await db.execute(
            select(FrsSpec).where(
                FrsSpec.document_id == document_id,
                FrsSpec.module_row_key == module_row_key,
                FrsSpec.is_current.is_(True),
                FrsSpec.status == "active",
            )
        )
    ).scalars().all()

    async def _spec_children(model, spec_row_key, cols):
        rows = (
            await db.execute(
                select(model).where(
                    model.document_id == document_id,
                    model.spec_row_key == spec_row_key,
                    model.is_current.is_(True),
                    model.status == "active",
                )
            )
        ).scalars().all()
        return [{**{c: getattr(r, c) for c in cols},
                 "row_key": r.row_key, "_is_locked": r.is_locked} for r in rows]

    out: list[dict] = []
    for s in specs:
        out.append({
            "row_key": s.row_key,
            "module_row_key": s.module_row_key,
            "title": s.title,
            "priority": s.priority,
            "layer": s.layer,
            "br_refs": s.br_refs or [],
            "nfr_refs": s.nfr_refs or [],
            "depends_on": s.depends_on or [],
            "narrative": s.narrative or "",
            "completeness": s.completeness,
            "confidence": s.confidence,
            "_is_locked": s.is_locked,
            "screens": await _spec_children(FrsScreen, s.row_key, FRS_TYPED_COLS["frs_screens"]),
            "ui_components": await _spec_children(FrsUiComponent, s.row_key, FRS_TYPED_COLS["frs_ui_components"]),
            "endpoints": await _spec_children(FrsEndpoint, s.row_key, FRS_TYPED_COLS["frs_endpoints"]),
            "data_entities": await _spec_children(FrsDataEntity, s.row_key, FRS_TYPED_COLS["frs_data_entities"]),
            "business_rules": await _spec_children(FrsBusinessRule, s.row_key, FRS_TYPED_COLS["frs_business_rules"]),
            "scenarios": await _spec_children(FrsAcceptanceScenario, s.row_key, FRS_TYPED_COLS["frs_acceptance_scenarios"]),
            "functional_requirements": await _spec_children(FrsFunctionalRequirement, s.row_key, FRS_TYPED_COLS["frs_functional_requirements"]),
        })
    return out


async def _serialize_resolved_decisions(
    document_id: uuid.UUID, module_row_key: str, db: AsyncSession,
) -> list[dict]:
    """Decisions where the user has chosen an option (accepted_ai or overridden).
    The LLM uses these to author the spec against the user's choice.
    """
    from app.models.frs import FrsSpecDecision

    rows = (
        await db.execute(
            select(FrsSpecDecision).where(
                FrsSpecDecision.document_id == document_id,
                FrsSpecDecision.is_current.is_(True),
                FrsSpecDecision.status == "active",
                FrsSpecDecision.resolution_status.in_(("accepted_ai", "overridden")),
            )
        )
    ).scalars().all()
    out: list[dict] = []
    for d in rows:
        # Only carry decisions scoped to this module or its specs
        if d.module_row_key == module_row_key:
            scope = "module"
        elif d.spec_row_key and d.spec_row_key.startswith(_spec_prefix_for_module(module_row_key)):
            scope = "spec"
        else:
            continue
        chosen = d.user_chosen_index if d.user_chosen_index is not None else d.recommended_index
        out.append({
            "row_key": d.row_key,
            "scope": scope,
            "module_row_key": d.module_row_key,
            "spec_row_key": d.spec_row_key,
            "question": d.question,
            "chosen_index": chosen,
            "chosen_option": (d.options or [{}])[chosen] if chosen < len(d.options or []) else None,
            "resolution_status": d.resolution_status,
        })
    return out


def _spec_prefix_for_module(module_row_key: str) -> str:
    """MOD-001 → M001-  ;  MOD-014 → M014-  ;  MOD-000 → M000-."""
    if module_row_key.startswith("MOD-"):
        return "M" + module_row_key[len("MOD-"):] + "-"
    return module_row_key + "-"


async def _upsert_frs_traceability(
    document_id: uuid.UUID,
    source_table: str,
    source_row_key: str,
    rows: list[dict[str, Any]],
    db: AsyncSession,
) -> int:
    """Replace-all traceability for (source_table, source_row_key).

    Deletes existing rows for the source then bulk-inserts. Atomic via
    db.begin_nested(). Skips entries with empty target_ref.

    Returns the number of rows actually inserted.
    """
    from app.models.frs import FrsTraceability

    inserted = 0
    async with db.begin_nested():
        await db.execute(sa_text(
            "DELETE FROM frs_traceability "
            "WHERE document_id = :doc AND source_table = :st AND source_row_key = :sk"
        ), {"doc": str(document_id), "st": source_table, "sk": source_row_key})
        for r in rows:
            target_ref = (r.get("target_ref") or "").strip()
            target_kind = r.get("target_kind")
            if not target_ref or not target_kind:
                continue
            db.add(FrsTraceability(
                id=uuid.uuid4(),
                document_id=document_id,
                source_table=source_table,
                source_row_key=source_row_key,
                target_kind=target_kind,
                target_ref=target_ref,
                target_label=r.get("target_label", ""),
                confidence=r.get("confidence", "medium"),
            ))
            inserted += 1
    return inserted


async def _persist_design_module_result(
    document_id: uuid.UUID, specs: list[dict], db: AsyncSession,
    *, actor_user_id: uuid.UUID | None = None,
    fallback_module_row_key: str | None = None,
) -> dict[str, int]:
    """Route each spec's content to the 9 spec-level tables.

    For each spec:
      1. upsert_frs_rows('frs_specs', ...)         # promote stub → full
      2. screens + ui_components (if not ui_blocked)
      3. endpoints
      4. data_entities
      5. business_rules
      6. acceptance_scenarios
      7. functional_requirements
      8. spec_decisions (spec-scoped)
      9. _upsert_frs_traceability(...)             # replace-all per source row

    Returns counts per table for observability.
    """
    counts: dict[str, int] = {
        "frs_specs": 0, "frs_screens": 0, "frs_ui_components": 0,
        "frs_endpoints": 0, "frs_data_entities": 0, "frs_business_rules": 0,
        "frs_acceptance_scenarios": 0, "frs_functional_requirements": 0,
        "frs_spec_decisions": 0, "frs_traceability": 0,
    }

    for spec in specs:
        spec_row_key = spec["row_key"]
        ui_blocked = bool(spec.get("ui_blocked_reason"))

        # 1. frs_specs — update the stub row to full
        # NOTE: module_row_key is set in Stage A; we DON'T touch it here.
        spec_payload = {
            "row_key": spec_row_key,
            "title": spec["title"],
            "priority": spec["priority"],
            "layer": spec["layer"],
            "br_refs": spec.get("br_refs", []),
            "nfr_refs": spec.get("nfr_refs", []),
            "depends_on": spec.get("depends_on", []),
            "narrative": spec.get("narrative", ""),
            "independent_test": spec.get("independent_test", ""),
            "data_and_validation": spec.get("data_and_validation", ""),
            "errors_and_edge_cases": spec.get("errors_and_edge_cases", ""),
            "observability": spec.get("observability", ""),
            "implementation_tasks": spec.get("implementation_tasks", []),
            "completeness": int(spec.get("completeness", 0) or 0),
            "confidence": spec.get("confidence", "low"),
        }
        # carry module_row_key from the existing stub row (don't override)
        from app.models.frs import FrsSpec as _FrsSpec
        existing = (
            await db.execute(
                select(_FrsSpec).where(
                    _FrsSpec.document_id == document_id,
                    _FrsSpec.row_key == spec_row_key,
                    _FrsSpec.is_current.is_(True),
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            # If the existing spec belongs to a different module than the one
            # being designed, skip — design_module only writes to its own module.
            if (fallback_module_row_key is not None
                    and existing.module_row_key != fallback_module_row_key):
                log.debug(
                    "frs.design_module.skip_cross_module_spec",
                    extra={
                        "spec_row_key": spec_row_key,
                        "existing_module": existing.module_row_key,
                        "target_module": fallback_module_row_key,
                    },
                )
                continue
            spec_payload["module_row_key"] = existing.module_row_key
        elif fallback_module_row_key is not None:
            spec_payload["module_row_key"] = fallback_module_row_key
        else:
            # Last-resort: derive MOD-XXX from M-prefixed spec row_key
            if spec_row_key.startswith("M") and "-FRS" in spec_row_key:
                spec_payload["module_row_key"] = "MOD-" + spec_row_key[1:4]
            else:
                log.warning(
                    "frs.design_module.missing_module_row_key",
                    extra={"spec_row_key": spec_row_key},
                )
                continue  # skip the row rather than insert a NULL FK
        # Scope soft-delete to ONLY this row_key — without scoping, every other
        # spec in the document would be wiped by the per-spec iteration.
        counts["frs_specs"] += await upsert_frs_rows(
            "frs_specs", document_id, [spec_payload], "ai", db,
            scope_keys={spec_row_key},
            user_id=actor_user_id,
        )

        # 2. screens + ui_components — only when UI is not blocked
        if not ui_blocked:
            screen_rows = [{
                **{c: s.get(c) for c in FRS_TYPED_COLS["frs_screens"]},
                "row_key": s["row_key"],
                "spec_row_key": spec_row_key,
            } for s in spec.get("screens", [])]
            counts["frs_screens"] += await upsert_frs_rows(
                "frs_screens", document_id, screen_rows, "ai", db,
                scope_keys=await _spec_child_keys("frs_screens", document_id, spec_row_key, db),
                user_id=actor_user_id,
            )

            uic_rows = [{
                **{c: c_.get(c) for c in FRS_TYPED_COLS["frs_ui_components"]},
                "row_key": c_["row_key"],
                "spec_row_key": spec_row_key,
            } for c_ in spec.get("ui_components", [])]
            counts["frs_ui_components"] += await upsert_frs_rows(
                "frs_ui_components", document_id, uic_rows, "ai", db,
                scope_keys=await _spec_child_keys("frs_ui_components", document_id, spec_row_key, db),
                user_id=actor_user_id,
            )

        # 3. endpoints
        ep_rows = [{
            **{c: e.get(c) for c in FRS_TYPED_COLS["frs_endpoints"]},
            "row_key": e["row_key"],
            "spec_row_key": spec_row_key,
        } for e in spec.get("endpoints", [])]
        counts["frs_endpoints"] += await upsert_frs_rows(
            "frs_endpoints", document_id, ep_rows, "ai", db,
            scope_keys=await _spec_child_keys("frs_endpoints", document_id, spec_row_key, db),
            user_id=actor_user_id,
        )

        # 4. data entities
        de_rows = [{
            **{c: e.get(c) for c in FRS_TYPED_COLS["frs_data_entities"]},
            "row_key": e["row_key"],
            "spec_row_key": spec_row_key,
        } for e in spec.get("data_entities", [])]
        counts["frs_data_entities"] += await upsert_frs_rows(
            "frs_data_entities", document_id, de_rows, "ai", db,
            scope_keys=await _spec_child_keys("frs_data_entities", document_id, spec_row_key, db),
            user_id=actor_user_id,
        )

        # 5. business rules
        br_rows = [{
            **{c: r.get(c) for c in FRS_TYPED_COLS["frs_business_rules"]},
            "row_key": r["row_key"],
            "spec_row_key": spec_row_key,
        } for r in spec.get("business_rules", [])]
        counts["frs_business_rules"] += await upsert_frs_rows(
            "frs_business_rules", document_id, br_rows, "ai", db,
            scope_keys=await _spec_child_keys("frs_business_rules", document_id, spec_row_key, db),
            user_id=actor_user_id,
        )

        # 6. acceptance scenarios
        sc_rows = [{
            **{c: s.get(c) for c in FRS_TYPED_COLS["frs_acceptance_scenarios"]},
            "row_key": s["row_key"],
            "spec_row_key": spec_row_key,
        } for s in spec.get("acceptance_scenarios", [])]
        counts["frs_acceptance_scenarios"] += await upsert_frs_rows(
            "frs_acceptance_scenarios", document_id, sc_rows, "ai", db,
            scope_keys=await _spec_child_keys("frs_acceptance_scenarios", document_id, spec_row_key, db),
            user_id=actor_user_id,
        )

        # 7. functional requirements
        fr_rows = [{
            **{c: f.get(c) for c in FRS_TYPED_COLS["frs_functional_requirements"]},
            "row_key": f["row_key"],
            "spec_row_key": spec_row_key,
        } for f in spec.get("functional_requirements", [])]
        counts["frs_functional_requirements"] += await upsert_frs_rows(
            "frs_functional_requirements", document_id, fr_rows, "ai", db,
            scope_keys=await _spec_child_keys("frs_functional_requirements", document_id, spec_row_key, db),
            user_id=actor_user_id,
        )

        # 8. spec decisions (spec-scoped)
        dec_rows = []
        for i, d in enumerate(spec.get("spec_decisions", []), 1):
            row_key = d.get("row_key") or f"{spec_row_key}-DEC-{i}"
            dec_rows.append({
                "row_key": row_key,
                "spec_row_key": spec_row_key,
                "module_row_key": None,
                "question": d["question"],
                "options": d.get("options", []),
                "recommended_index": int(d.get("recommended_index", 0) or 0),
                "recommended_rationale": d.get("recommended_rationale", ""),
                "user_chosen_index": None,
                "resolution_status": "open",
            })
        counts["frs_spec_decisions"] += await upsert_frs_rows(
            "frs_spec_decisions", document_id, dec_rows, "ai", db,
            user_id=actor_user_id,
        )

        # 9. traceability — replace-all per source row
        # Group emitted trace rows by (source_table, source_row_key) and replace each group
        traces = spec.get("traceability", [])
        by_source: dict[tuple[str, str], list[dict]] = {}
        for t in traces:
            key = (t.get("source_table", "frs_specs"), t.get("source_row_key", spec_row_key))
            by_source.setdefault(key, []).append(t)
        for (src_table, src_key), src_rows in by_source.items():
            counts["frs_traceability"] += await _upsert_frs_traceability(
                document_id, src_table, src_key, src_rows, db,
            )

    return counts


async def _persist_ui_only_result(
    document_id: uuid.UUID, specs: list[dict], db: AsyncSession,
    *, actor_user_id: uuid.UUID | None = None,
) -> dict[str, int]:
    """Used by the figma-link handler: only touch screens + ui_components for the
    target spec(s). Leaves endpoints/entities/scenarios/etc. untouched.
    """
    counts: dict[str, int] = {"frs_screens": 0, "frs_ui_components": 0}
    for spec in specs:
        spec_row_key = spec["row_key"]
        if spec.get("ui_blocked_reason"):
            continue
        screen_rows = [{
            **{c: s.get(c) for c in FRS_TYPED_COLS["frs_screens"]},
            "row_key": s["row_key"],
            "spec_row_key": spec_row_key,
        } for s in spec.get("screens", [])]
        counts["frs_screens"] += await upsert_frs_rows(
            "frs_screens", document_id, screen_rows, "ai", db,
            scope_keys=await _spec_child_keys("frs_screens", document_id, spec_row_key, db),
            user_id=actor_user_id,
        )
        uic_rows = [{
            **{c: c_.get(c) for c in FRS_TYPED_COLS["frs_ui_components"]},
            "row_key": c_["row_key"],
            "spec_row_key": spec_row_key,
        } for c_ in spec.get("ui_components", [])]
        counts["frs_ui_components"] += await upsert_frs_rows(
            "frs_ui_components", document_id, uic_rows, "ai", db,
            scope_keys=await _spec_child_keys("frs_ui_components", document_id, spec_row_key, db),
            user_id=actor_user_id,
        )
    return counts


async def _spec_child_keys(
    table_name: str, document_id: uuid.UUID, spec_row_key: str, db: AsyncSession,
) -> set[str]:
    """Set of current-active row_keys for a child table belonging to a spec.

    Used as `scope_keys` so soft-delete is scoped to THIS spec's rows only.
    """
    model = FRS_TABLE_MAP[table_name]
    rows = (
        await db.execute(
            select(model.row_key).where(
                model.document_id == document_id,
                model.spec_row_key == spec_row_key,  # type: ignore[attr-defined]
                model.is_current.is_(True),
                model.status == "active",
            )
        )
    ).scalars().all()
    return set(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# Stage B — generate_frs_design_module
# ═══════════════════════════════════════════════════════════════════════════════


async def generate_frs_design_module(
    project: Project,
    module_row_key: str,
    doc: ArtifactDocument,
    bundle: ProjectContextBundle,
    db: AsyncSession,
    *,
    target_spec_row_key: str | None = None,
    ui_only: bool = False,
) -> dict:
    """Design one module's worth of FRS specs.

    target_spec_row_key: if set, only persist that one spec (single-spec regen).
    ui_only: if True, only update screens + ui_components for the target spec(s).

    Returns the LLM output dict (after filtering to target spec if applicable).
    """
    unit_spec = FRS_MANIFEST_BY_KEY["design_module"]

    # 1. mark _current_unit
    await _set_current_unit(doc.id, f"design_mod_{module_row_key}", db)

    # 2. gather context
    module_context = await _serialize_module_with_children(doc.id, module_row_key, db)
    other_modules = await _summarize_other_modules(doc.id, module_row_key, db)
    current_specs = await _serialize_module_specs(doc.id, module_row_key, db)
    locked_specs = [s for s in current_specs if s.get("_is_locked")]
    resolved_decisions = await _serialize_resolved_decisions(doc.id, module_row_key, db)

    # 3. project per-unit context (CB + BRD + apps + docs)
    unit_ctx = project_for_unit(bundle, "frs", "design_module")
    qa_pairs = await _gather_frs_unit_qa(doc.id, "design_module", db)

    log.info(
        "frs.design_module.start",
        extra={
            "project_id": str(project.id), "doc_id": str(doc.id),
            "module_row_key": module_row_key,
            "spec_count_before": len(current_specs),
            "locked_spec_count": len(locked_specs),
            "target_spec_row_key": target_spec_row_key,
            "ui_only": ui_only,
        },
    )

    # 4. Decide which stubs to design.
    #    target_spec_row_key → just that one (single-spec regen);
    #    otherwise every stub in the module (whole-module design).
    specs_by_key = {s["row_key"]: s for s in current_specs}
    locked_keys = {s["row_key"] for s in locked_specs}
    if target_spec_row_key:
        stub_keys = [target_spec_row_key]
    else:
        stub_keys = [s["row_key"] for s in current_specs]

    # Compact sibling summary (row_key + title) so each per-spec call stays aware
    # of its peers for depends_on / non-overlap — full grounding, just compact.
    sibling_summary = [
        {"row_key": s["row_key"], "title": s.get("title", "")}
        for s in current_specs
    ]

    # Shared grounding handed to EVERY per-spec call. No context is dropped:
    # the full BRD, Concept Brief, App Brain, module context, sibling specs,
    # other modules, project docs and discover Q&A go into each call. Only the
    # OUTPUT shrinks to a single spec — which is what keeps the call fast and
    # reliable (a whole-module output truncates / times out on gemini-2.5-flash).
    shared_ctx = dict(
        project_name=project.name,
        business_unit=project.business_unit or "—",
        module_row_key=module_row_key,
        module_context=json.dumps(module_context, default=str),
        sibling_specs_summary=json.dumps(sibling_summary, default=str),
        other_modules_summary=json.dumps(other_modules, default=str),
        brd_context=bundle.brd.formatted_context if bundle.brd else "(no BRD)",
        cb_context=bundle.cb.formatted_context,
        app_brain=bundle.apps.formatted_context,
        source_sections=unit_ctx.doc_sections,
        qa_pairs=qa_pairs,
        resolved_decisions=json.dumps(resolved_decisions, default=str),
    )

    # 5. Generate ONE spec per LLM call, persisting each as it completes so that
    #    a later timeout never loses already-finished specs.
    designed_specs: list[dict] = []
    open_questions: list[dict] = []
    completeness_vals: list[int] = []

    for sk in stub_keys:
        if sk in locked_keys:
            continue  # locked spec → preserve verbatim, never regenerate
        stub = specs_by_key.get(sk, {"row_key": sk})

        # Mark THIS spec as the one being written, BEFORE the LLM call, so the
        # frontend "Now writing" view names the in-progress spec (not the last
        # finished one). current_spec_key is cleared in the final patch below.
        await db.execute(sa_text(
            "UPDATE artifact_documents "
            "SET unit_status = COALESCE(unit_status, '{}'::jsonb) || CAST(:patch AS jsonb), "
            "    updated_at = NOW() "
            "WHERE id = :doc_id"
        ), {
            "patch": json.dumps({
                f"design_mod_{module_row_key}": {
                    "current_spec_key": sk,
                    "specs_done": len(designed_specs),
                    "specs_total": len(stub_keys),
                },
            }),
            "doc_id": str(doc.id),
        })
        await db.commit()

        try:
            one = await asyncio.wait_for(
                run_design_spec(
                    **shared_ctx,
                    target_spec_row_key=sk,
                    target_spec_stub=json.dumps(stub, default=str),
                    current_spec=json.dumps(stub, default=str),
                ),
                timeout=unit_spec.timeout_seconds,
            )
        except asyncio.TimeoutError:
            log.error(
                "frs.design_spec.timeout",
                extra={"doc_id": str(doc.id), "module_row_key": module_row_key,
                       "spec_row_key": sk},
            )
            continue  # skip this spec; keep designing the rest

        spec_out = one.get("spec")
        if not spec_out:
            continue
        spec_out["row_key"] = sk  # defensive: pin to the stub key
        designed_specs.append(spec_out)
        completeness_vals.append(int(spec_out.get("completeness", 0) or 0))
        open_questions.extend(one.get("open_questions", []) or [])

        # 6. Persist THIS spec immediately + commit so the rail updates live and
        #    partial progress survives a subsequent failure.
        if ui_only:
            await _persist_ui_only_result(doc.id, [spec_out], db)
        else:
            await _persist_design_module_result(
                doc.id, [spec_out], db, fallback_module_row_key=module_row_key,
            )
        await db.commit()
        # The backlog stub's completeness now reflects this spec as designed —
        # that's the ground-truth signal the frontend reads. specs_done updates
        # on the next iteration's pre-call patch.

    avg_completeness = (
        int(sum(completeness_vals) / len(completeness_vals)) if completeness_vals else 0
    )
    overall_confidence = (
        "high" if avg_completeness >= 90
        else "medium" if avg_completeness >= 70
        else "low"
    )
    result = {
        "specs": designed_specs,
        "open_questions": open_questions,
        "completeness": avg_completeness,
        "confidence": overall_confidence,
    }
    specs_to_persist = designed_specs

    log.info(
        "frs.design_module.complete",
        extra={
            "doc_id": str(doc.id),
            "module_row_key": module_row_key,
            "spec_count": len(specs_to_persist),
            "completeness": avg_completeness,
            "confidence": overall_confidence,
        },
    )

    # 7. atomic unit_status merge for this module
    await db.execute(sa_text(
        "UPDATE artifact_documents "
        "SET unit_status = COALESCE(unit_status, '{}'::jsonb) || CAST(:patch AS jsonb), "
        "    updated_at = NOW() "
        "WHERE id = :doc_id"
    ), {
        "patch": json.dumps({
            f"design_mod_{module_row_key}": {
                "completeness": avg_completeness,
                "confidence": overall_confidence,
                "spec_count": len(specs_to_persist),
                "current_spec_key": None,   # module done — no spec in flight
            },
            "_current_unit": None,
        }),
        "doc_id": str(doc.id),
    })

    # 8. emit messages for figma_link_required + open spec_decisions
    await _emit_design_messages(doc, module_row_key, result, specs_to_persist, db)

    return result


async def _emit_design_messages(
    doc: ArtifactDocument,
    module_row_key: str,
    result: dict,
    specs_persisted: list[dict],
    db: AsyncSession,
) -> None:
    """Emit synthesis + figma-link + open-decision messages into artifact_messages."""
    seq = await _next_frs_seq(doc.id, db)

    # Synthesis
    spec_count = len(specs_persisted)
    synthesis = (
        f"Module {module_row_key} design complete: {spec_count} FRS "
        f"spec{'s' if spec_count != 1 else ''}. "
        f"Confidence: {result.get('confidence', 'low')}."
    )
    db.add(ArtifactMessage(
        document_id=doc.id, project_id=doc.project_id,
        role="synthesis", content=synthesis, citations=[],
        meta={"unit_key": "design_module", "module_row_key": module_row_key}, seq=seq,
    ))
    seq += 1

    # Figma-link blocked specs
    for s in specs_persisted:
        if s.get("ui_blocked_reason") == "figma_link_required":
            body = (
                f"[FIGMA-LINK-REQUIRED] FRS {s['row_key']} ({s.get('title','')}) "
                f"has UI surfaces but no Figma link. Please provide a Figma URL "
                f"or click 'Skip — UI design TBD'."
            )
            db.add(ArtifactMessage(
                document_id=doc.id, project_id=doc.project_id,
                role="question", content=body, citations=[],
                meta={
                    "unit_key": "design_module",
                    "type": "figma_link_required",
                    "spec_row_key": s["row_key"],
                    "module_row_key": module_row_key,
                },
                seq=seq,
            ))
            seq += 1

    # Open spec-scoped decisions
    for s in specs_persisted:
        for d in s.get("spec_decisions", []):
            body = (
                f"[SPEC-DECISION] {d['question']}\n"
                f"AI recommends option {d.get('recommended_index', 0)}: "
                f"{d.get('recommended_rationale', '(no rationale)')}"
            )
            db.add(ArtifactMessage(
                document_id=doc.id, project_id=doc.project_id,
                role="question", content=body, citations=[],
                meta={
                    "unit_key": "design_module",
                    "type": "spec_decision_open",
                    "decision_row_key": d.get("row_key"),
                    "spec_row_key": s["row_key"],
                    "module_row_key": module_row_key,
                },
                seq=seq,
            ))
            seq += 1


# ═══════════════════════════════════════════════════════════════════════════════
# Stage B — set_figma_link + regenerate_frs_spec
# ═══════════════════════════════════════════════════════════════════════════════


FIGMA_SKIP_SENTINEL = "__none__"


async def _load_spec_row(
    document_id: uuid.UUID, spec_row_key: str, db: AsyncSession,
) -> Any:
    """Return the current active FrsSpec row for a spec_row_key, or None."""
    from app.models.frs import FrsSpec
    return (
        await db.execute(
            select(FrsSpec).where(
                FrsSpec.document_id == document_id,
                FrsSpec.row_key == spec_row_key,
                FrsSpec.is_current.is_(True),
            )
        )
    ).scalar_one_or_none()


async def _current_screens_for_spec(
    document_id: uuid.UUID, spec_row_key: str, db: AsyncSession,
) -> list[Any]:
    from app.models.frs import FrsScreen
    return (
        await db.execute(
            select(FrsScreen).where(
                FrsScreen.document_id == document_id,
                FrsScreen.spec_row_key == spec_row_key,
                FrsScreen.is_current.is_(True),
                FrsScreen.status == "active",
            )
        )
    ).scalars().all()


async def set_figma_link(
    project: Project,
    spec_row_key: str,
    link: str,
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
    bundle: ProjectContextBundle | None = None,
) -> dict[str, Any]:
    """Set figma_link on every screen of a spec (or sentinel '__none__' to skip).

    Behaviour:
      - link == '__none__' → write sentinel on each screen; do NOT regenerate
      - no screens yet (UI was previously blocked) → create one placeholder
        screen with the link, then trigger a UI-only design_module regeneration
      - screens exist → update the link on each, then trigger UI-only regen

    Returns a summary dict: {status, spec_row_key, link, regenerated, screen_count}.
    """
    doc = await _ensure_frs_document(project.id, db)
    spec = await _load_spec_row(doc.id, spec_row_key, db)
    if spec is None:
        raise ValueError(f"spec {spec_row_key} not found in project {project.id}")

    screens = await _current_screens_for_spec(doc.id, spec_row_key, db)

    if link == FIGMA_SKIP_SENTINEL:
        # User opted out → mark every screen with the sentinel, no regen
        for s in screens:
            if s.is_locked:
                continue
            await edit_frs_row(
                doc.id, "frs_screens", s.id,
                {"figma_link": FIGMA_SKIP_SENTINEL},
                db, user_id=user_id,
            )
        log.info(
            "frs.figma_link.set",
            extra={
                "doc_id": str(doc.id), "spec_row_key": spec_row_key,
                "link_type": "skip", "screen_count": len(screens),
            },
        )
        return {
            "status": "skipped",
            "spec_row_key": spec_row_key,
            "link": FIGMA_SKIP_SENTINEL,
            "regenerated": False,
            "screen_count": len(screens),
        }

    # Real link → write it onto each screen (or create a placeholder)
    if not screens:
        await upsert_frs_rows("frs_screens", doc.id, [{
            "row_key": f"{spec_row_key}-SCR-1",
            "spec_row_key": spec_row_key,
            "screen_name": "Primary Screen",
            "figma_link": link,
            "purpose": "",
            "user_roles": [],
            "layout": "",
            "navigation": "",
            "interactive_behavior": "",
        }], "human", db, user_id=user_id)
    else:
        for s in screens:
            if s.is_locked:
                continue
            await edit_frs_row(
                doc.id, "frs_screens", s.id,
                {"figma_link": link},
                db, user_id=user_id,
            )

    await db.commit()

    # Trigger UI-only regen for this spec
    if bundle is None:
        bundle = await gather_project_context(
            project.id, db,
            artifact_document_id=doc.id,
            artifact_type="frs",
        )

    module_row_key = spec.module_row_key
    if not module_row_key:
        raise ValueError(f"spec {spec_row_key} has no module_row_key (data integrity issue)")

    await generate_frs_design_module(
        project, module_row_key, doc, bundle, db,
        target_spec_row_key=spec_row_key, ui_only=True,
    )

    log.info(
        "frs.figma_link.set",
        extra={
            "doc_id": str(doc.id), "spec_row_key": spec_row_key,
            "link_type": "real", "screen_count": len(screens) or 1,
            "regenerated": True,
        },
    )
    return {
        "status": "regenerated",
        "spec_row_key": spec_row_key,
        "link": link,
        "regenerated": True,
        "screen_count": len(screens) or 1,
    }


async def regenerate_frs_spec(
    project: Project,
    spec_row_key: str,
    db: AsyncSession,
    *,
    scope: str = "full",
    user_id: uuid.UUID | None = None,
    bundle: ProjectContextBundle | None = None,
) -> dict[str, Any]:
    """Re-run design_module narrowed to a single spec.

    scope='full'      → re-author every section of the spec
    scope='ui_only'   → only update screens + ui_components (used by figma flow)

    Returns the orchestrator result dict.
    """
    if scope not in ("full", "ui_only"):
        raise ValueError(f"scope must be 'full' or 'ui_only'; got {scope!r}")

    doc = await _ensure_frs_document(project.id, db)
    spec = await _load_spec_row(doc.id, spec_row_key, db)
    if spec is None:
        raise ValueError(f"spec {spec_row_key} not found in project {project.id}")

    if not spec.module_row_key:
        raise ValueError(f"spec {spec_row_key} has no module_row_key (data integrity issue)")

    if bundle is None:
        bundle = await gather_project_context(
            project.id, db,
            artifact_document_id=doc.id,
            artifact_type="frs",
        )

    log.info(
        "frs.spec.regenerate",
        extra={
            "doc_id": str(doc.id),
            "spec_row_key": spec_row_key,
            "module_row_key": spec.module_row_key,
            "scope": scope,
        },
    )

    return await generate_frs_design_module(
        project, spec.module_row_key, doc, bundle, db,
        target_spec_row_key=spec_row_key,
        ui_only=(scope == "ui_only"),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Full pipeline (Stage A → Stage B, parallel per module)
# ═══════════════════════════════════════════════════════════════════════════════


async def generate_frs_all(
    project: Project,
    db: AsyncSession,
    *,
    brief: str | None = None,
    run_stage_b: bool = False,
    max_parallel_modules: int = 3,
) -> dict:
    """Full FRS pipeline: Stage A (modularize) → Stage B (per-module design).

    Stage B runs the per-module design in parallel, capped at `max_parallel_modules`
    to avoid Vertex rate-spikes. Each module gets its own AsyncSessionLocal to
    avoid event-loop binding.

    Pass run_stage_b=False to run Stage A only (legacy behavior; useful for tests).
    """
    doc = await _ensure_frs_document(project.id, db)

    # Persist initial brief if provided
    if brief and brief.strip():
        seq = await _next_frs_seq(doc.id, db)
        db.add(ArtifactMessage(
            document_id=doc.id, project_id=project.id,
            role="user", content=brief.strip(), citations=[],
            meta={"is_initial_brief": True}, seq=seq,
        ))
        await db.flush()

    # Reset unit_status + flip to generating
    doc.unit_status = {}
    doc.status = "generating"
    await db.commit()

    # Snapshot full corpus once (BRD + CB + apps + docs + discover Q&A)
    bundle = await gather_project_context(
        project.id, db,
        artifact_document_id=doc.id,
        artifact_type="frs",
    )

    if not bundle.readiness.can_generate:
        # Reset status and bail with a descriptive error
        doc.status = "in_interview"
        await db.commit()
        raise RuntimeError(
            f"FRS generation blocked: {bundle.readiness.blocking_reason}"
        )

    # Stage A
    await generate_frs_modularize(project, doc, bundle, db)
    await db.commit()

    # Stage B — parallel per module, capped concurrency
    if run_stage_b:
        from app.models.frs import FrsModule

        modules = (
            await db.execute(
                select(FrsModule).where(
                    FrsModule.document_id == doc.id,
                    FrsModule.is_current.is_(True),
                    FrsModule.status == "active",
                )
            )
        ).scalars().all()
        module_keys = [m.row_key for m in modules]

        sem = asyncio.Semaphore(max_parallel_modules)

        async def _design_one(mod_row_key: str) -> None:
            from app.db import AsyncSessionLocal
            async with sem:
                async with AsyncSessionLocal() as unit_db:
                    unit_doc = await unit_db.get(ArtifactDocument, doc.id)
                    if unit_doc is None:
                        return
                    try:
                        await generate_frs_design_module(
                            project, mod_row_key, unit_doc, bundle, unit_db,
                        )
                        await unit_db.commit()
                    except Exception:
                        log.exception(
                            "frs.design_module.failed",
                            extra={"doc_id": str(doc.id), "module_row_key": mod_row_key},
                        )
                        await unit_db.rollback()

        await asyncio.gather(*[_design_one(mk) for mk in module_keys])

    # Finalize → in_interview
    await db.refresh(doc)
    doc.status = "in_interview"
    await db.commit()
    return await get_frs_detail(project.id, db)


# ═══════════════════════════════════════════════════════════════════════════════
# Stage B only — run_frs_stage_b
# ═══════════════════════════════════════════════════════════════════════════════


async def run_frs_stage_b(
    project: Project,
    db: AsyncSession,
    *,
    skip_designed: bool = True,
    max_parallel_modules: int = 3,
) -> dict:
    """Run Stage B per-module design without re-running Stage A.

    skip_designed=True (default): modules where unit_status already contains a
    design_mod_<key> entry with completeness > 0 are skipped, making this safe
    to call after partial completion or as a "design remaining" action.

    Context is gathered once and shared across all module coroutines.
    """
    from app.models.frs import FrsModule

    doc = await _ensure_frs_document(project.id, db)

    if doc.status == "validated":
        raise RuntimeError("FRS is validated — unlock before regenerating")

    # NOTE: we intentionally do NOT bail when status == 'generating'. The API
    # endpoint pre-sets 'generating' for immediate UI feedback before dispatching
    # this task, so seeing 'generating' here is expected — bailing would leave the
    # status stuck. Concurrent-run protection lives in the endpoint.

    bundle = await gather_project_context(
        project.id, db,
        artifact_document_id=doc.id,
        artifact_type="frs",
    )

    if not bundle.readiness.can_generate:
        raise RuntimeError(
            f"FRS generation blocked: {bundle.readiness.blocking_reason}"
        )

    modules = (
        await db.execute(
            select(FrsModule).where(
                FrsModule.document_id == doc.id,
                FrsModule.is_current.is_(True),
                FrsModule.status == "active",
            )
        )
    ).scalars().all()

    if skip_designed:
        # A module is "designed" only when EVERY active backlog stub has a spec
        # (completeness > 0). A module whose loop finished but left some specs
        # missing (spec-level timeouts) must be re-run — so it is NOT skipped.
        from app.models.frs import FrsSpec
        specs = (
            await db.execute(
                select(FrsSpec.module_row_key, FrsSpec.completeness).where(
                    FrsSpec.document_id == doc.id,
                    FrsSpec.is_current.is_(True),
                    FrsSpec.status == "active",
                )
            )
        ).all()
        total_by_mod: dict[str, int] = {}
        designed_by_mod: dict[str, int] = {}
        for mod_key, comp in specs:
            total_by_mod[mod_key] = total_by_mod.get(mod_key, 0) + 1
            if (comp or 0) > 0:
                designed_by_mod[mod_key] = designed_by_mod.get(mod_key, 0) + 1
        module_keys = [
            m.row_key for m in modules
            if total_by_mod.get(m.row_key, 0) == 0
            or designed_by_mod.get(m.row_key, 0) < total_by_mod.get(m.row_key, 0)
        ]
    else:
        module_keys = [m.row_key for m in modules]

    if not module_keys:
        # Nothing to design (everything already complete). Make sure we don't
        # strand the doc in 'generating' — the endpoint may have pre-set it.
        if doc.status == "generating":
            await db.execute(sa_text(
                "UPDATE artifact_documents "
                "SET status = 'in_interview', "
                "    unit_status = COALESCE(unit_status, '{}'::jsonb) || '{\"_current_unit\": null}'::jsonb, "
                "    updated_at = NOW() "
                "WHERE id = :doc_id"
            ), {"doc_id": str(doc.id)})
            await db.commit()
        return await get_frs_detail(project.id, db)

    # Mark generating (preserve existing unit_status — skip_designed reads it)
    await db.execute(sa_text(
        "UPDATE artifact_documents "
        "SET status = 'generating', updated_at = NOW() "
        "WHERE id = :doc_id"
    ), {"doc_id": str(doc.id)})
    await db.commit()

    sem = asyncio.Semaphore(max_parallel_modules)

    async def _design_one(mod_row_key: str) -> None:
        from app.db import AsyncSessionLocal
        async with sem:
            async with AsyncSessionLocal() as unit_db:
                unit_doc = await unit_db.get(ArtifactDocument, doc.id)
                if unit_doc is None:
                    return
                try:
                    await generate_frs_design_module(
                        project, mod_row_key, unit_doc, bundle, unit_db,
                    )
                    await unit_db.commit()
                except Exception:
                    log.exception(
                        "run_frs_stage_b.module_failed",
                        extra={"doc_id": str(doc.id), "module_row_key": mod_row_key},
                    )
                    await unit_db.rollback()

    await asyncio.gather(*[_design_one(mk) for mk in module_keys])

    async with AsyncSessionLocal() as fin_db:
        fin_doc = await fin_db.get(ArtifactDocument, doc.id)
        if fin_doc:
            fin_doc.status = "in_interview"
            await fin_db.commit()

    return await get_frs_detail(project.id, db)


# ═══════════════════════════════════════════════════════════════════════════════
# Row CRUD (edit / delete / restore / unlock)
# ═══════════════════════════════════════════════════════════════════════════════


async def edit_frs_row(
    document_id: uuid.UUID,
    table_name: str,
    row_id: uuid.UUID,
    fields: dict[str, Any],
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
    lock: bool = False,
    expected_version: int | None = None,
) -> Any:
    """Versioned edit: marks old row is_current=False, inserts new version+1.

    expected_version: if provided and current row is at a higher version, raises
    ValueError("version_conflict") so callers can return 409 Conflict.
    """
    model = FRS_TABLE_MAP[table_name]
    typed_cols = FRS_TYPED_COLS[table_name]

    current = (
        await db.execute(
            select(model).where(
                model.id == row_id,
                model.is_current.is_(True),
            )
        )
    ).scalar_one_or_none()
    if current is None:
        raise ValueError(f"row_not_found: {table_name}/{row_id}")
    if expected_version is not None and current.version != expected_version:
        raise ValueError(
            f"version_conflict: row at v{current.version}, "
            f"client sent expected_version={expected_version}"
        )

    coerced = _coerce_int_cols(table_name, fields, current)
    current.is_current = False
    new_row_data = {c: getattr(current, c) for c in typed_cols}
    for c in typed_cols:
        if c in coerced:
            new_row_data[c] = coerced[c]
    # Preserve key linkers (e.g. module_row_key / spec_row_key) when present
    for linker in ("module_row_key", "spec_row_key", "screen_row_key"):
        if hasattr(current, linker) and linker not in new_row_data:
            new_row_data[linker] = getattr(current, linker)

    new_row = model(
        document_id=current.document_id,
        row_key=current.row_key,
        version=current.version + 1,
        is_current=True,
        is_locked=lock or current.is_locked,
        status="active",
        source="human",
        created_by=user_id,
        **new_row_data,
    )
    db.add(new_row)
    await db.flush()
    return new_row


async def delete_frs_row(
    document_id: uuid.UUID,
    table_name: str,
    row_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Soft-delete: mark current row status='removed'."""
    model = FRS_TABLE_MAP[table_name]
    current = (
        await db.execute(
            select(model).where(
                model.id == row_id, model.is_current.is_(True),
            )
        )
    ).scalar_one_or_none()
    if current is None:
        raise ValueError(f"row_not_found: {table_name}/{row_id}")
    if current.is_locked:
        raise ValueError(f"row_locked: {table_name}/{row_id}")
    current.status = "removed"


async def unlock_frs_row(
    document_id: uuid.UUID,
    table_name: str,
    row_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Unset is_locked on the current row."""
    model = FRS_TABLE_MAP[table_name]
    current = (
        await db.execute(
            select(model).where(
                model.id == row_id, model.is_current.is_(True),
            )
        )
    ).scalar_one_or_none()
    if current is None:
        raise ValueError(f"row_not_found: {table_name}/{row_id}")
    current.is_locked = False


async def restore_frs_row(
    document_id: uuid.UUID,
    table_name: str,
    target_row_id: uuid.UUID,
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
) -> Any:
    """Restore an old version: copy its data into a new version+1 at the head."""
    model = FRS_TABLE_MAP[table_name]
    typed_cols = FRS_TYPED_COLS[table_name]
    target = await db.get(model, target_row_id)
    if target is None:
        raise ValueError(f"row_not_found: {table_name}/{target_row_id}")

    current = (
        await db.execute(
            select(model).where(
                model.document_id == target.document_id,
                model.row_key == target.row_key,
                model.is_current.is_(True),
            )
        )
    ).scalar_one_or_none()
    if current is not None:
        current.is_current = False
    new_version = (current.version + 1) if current else 1
    payload = {c: getattr(target, c) for c in typed_cols}
    for linker in ("module_row_key", "spec_row_key", "screen_row_key"):
        if hasattr(target, linker):
            payload[linker] = getattr(target, linker)

    new_row = model(
        document_id=target.document_id,
        row_key=target.row_key,
        version=new_version,
        is_current=True,
        is_locked=False,
        status="active",
        source="human",
        created_by=user_id,
        **payload,
    )
    db.add(new_row)
    await db.flush()
    return new_row


async def get_frs_row_history(
    document_id: uuid.UUID,
    table_name: str,
    row_id: uuid.UUID,
    db: AsyncSession,
) -> list[dict]:
    """Return all versions of a row_key (the current row + all prior versions)."""
    model = FRS_TABLE_MAP[table_name]
    anchor = await db.get(model, row_id)
    if anchor is None:
        raise ValueError(f"row_not_found: {table_name}/{row_id}")
    rows = (
        await db.execute(
            select(model)
            .where(
                model.document_id == anchor.document_id,
                model.row_key == anchor.row_key,
            )
            .order_by(model.version.desc())
        )
    ).scalars().all()
    return [_frs_row_to_dict(r, table_name) for r in rows]


# ═══════════════════════════════════════════════════════════════════════════════
# Refine / answer flow
# ═══════════════════════════════════════════════════════════════════════════════


async def save_frs_answer(
    project_id: uuid.UUID, answer: str, db: AsyncSession,
    seq: int | None = None,
) -> dict:
    """Persist a user free-text answer; orchestrator schedules a re-modularize task."""
    doc = await _ensure_frs_document(project_id, db)
    s = await _next_frs_seq(doc.id, db)
    db.add(ArtifactMessage(
        document_id=doc.id, project_id=project_id,
        role="user", content=answer, citations=[],
        meta={"unit_key": "modularize"}, seq=s,
    ))
    await db.flush()
    # Caller (api/frs.py) is responsible for dispatching the regen Celery task.
    return {"seq": s, "status": "queued"}


async def resolve_frs_decision(
    document_id: uuid.UUID,
    decision_row_id: uuid.UUID,
    *,
    chosen_index: int,
    resolution_status: str,   # accepted_ai | overridden | dismissed
    db: AsyncSession,
    user_id: uuid.UUID | None = None,
) -> Any:
    """Resolve a [SPEC-DECISION] MCQ; versions the row + records the choice."""
    from app.models.frs import FrsSpecDecision

    current = (
        await db.execute(
            select(FrsSpecDecision).where(
                FrsSpecDecision.id == decision_row_id,
                FrsSpecDecision.is_current.is_(True),
            )
        )
    ).scalar_one_or_none()
    if current is None:
        raise ValueError(f"decision_not_found: {decision_row_id}")

    current.is_current = False
    new_row = FrsSpecDecision(
        document_id=current.document_id,
        row_key=current.row_key,
        version=current.version + 1,
        is_current=True,
        is_locked=False,
        status="active",
        source="human",
        created_by=user_id,
        spec_row_key=current.spec_row_key,
        module_row_key=current.module_row_key,
        question=current.question,
        options=current.options,
        recommended_index=current.recommended_index,
        recommended_rationale=current.recommended_rationale,
        user_chosen_index=chosen_index,
        resolution_status=resolution_status,
    )
    db.add(new_row)
    await db.flush()
    return new_row


# ═══════════════════════════════════════════════════════════════════════════════
# Detail hydration (for GET /artifacts/frs)
# ═══════════════════════════════════════════════════════════════════════════════


async def get_frs_detail(
    project_id: uuid.UUID, db: AsyncSession,
) -> dict:
    """Hydrate the full FRS state for the GET endpoint.

    Returns:
      {
        "document": {id, status, unit_status, validated_at, …},
        "modules": [<module + nested actors/responsibilities/interfaces/data/backlog>],
        "messages": [<ArtifactMessage rows ordered by seq>],
        "sources": [<ArtifactSource rows>],
        "decisions": [<open + resolved>],
      }
    """
    from app.models.frs import (
        FrsModule, FrsModuleActor, FrsModuleResponsibility,
        FrsModuleInterface, FrsModuleDataEntity, FrsSpec, FrsSpecDecision,
    )

    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == "frs",
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        return {"document": None, "modules": [], "messages": [], "sources": [], "decisions": []}

    # All current modules + child rows
    modules = await _current_frs_rows_for("frs_modules", doc.id, db)
    actors = await _current_frs_rows_for("frs_module_actors", doc.id, db)
    resps = await _current_frs_rows_for("frs_module_responsibilities", doc.id, db)
    ifaces = await _current_frs_rows_for("frs_module_interfaces", doc.id, db)
    des = await _current_frs_rows_for("frs_module_data_entities", doc.id, db)
    specs = await _current_frs_rows_for("frs_specs", doc.id, db)
    decisions = await _current_frs_rows_for("frs_spec_decisions", doc.id, db)

    # Stage B sub-rows (hydrated onto each spec below)
    screens = await _current_frs_rows_for("frs_screens", doc.id, db)
    components = await _current_frs_rows_for("frs_ui_components", doc.id, db)
    endpoints = await _current_frs_rows_for("frs_endpoints", doc.id, db)
    data_entities = await _current_frs_rows_for("frs_data_entities", doc.id, db)
    business_rules = await _current_frs_rows_for("frs_business_rules", doc.id, db)
    scenarios = await _current_frs_rows_for("frs_acceptance_scenarios", doc.id, db)
    functional_requirements = await _current_frs_rows_for("frs_functional_requirements", doc.id, db)

    # Traceability (not versioned — replace-all)
    from app.models.frs import FrsTraceability
    trace_rows = (
        await db.execute(
            select(FrsTraceability).where(FrsTraceability.document_id == doc.id)
        )
    ).scalars().all()
    traceability = [{
        "id": str(t.id),
        "document_id": str(t.document_id),
        "source_table": t.source_table,
        "source_row_key": t.source_row_key,
        "target_kind": t.target_kind,
        "target_ref": t.target_ref,
        "target_label": t.target_label or "",
        "confidence": t.confidence or "medium",
    } for t in trace_rows]

    # Group children by module
    def _by_module(rows: list[dict]) -> dict[str, list[dict]]:
        out: dict[str, list[dict]] = {}
        for r in rows:
            out.setdefault(r["module_row_key"], []).append(r)
        return out

    actors_by_mod = _by_module(actors)
    resps_by_mod = _by_module(resps)
    ifaces_by_mod = _by_module(ifaces)
    des_by_mod = _by_module(des)

    # Group Stage B sub-rows by spec_row_key
    def _by_spec(rows: list[dict]) -> dict[str, list[dict]]:
        out: dict[str, list[dict]] = {}
        for r in rows:
            k = r.get("spec_row_key")
            if k:
                out.setdefault(k, []).append(r)
        return out

    screens_by_spec = _by_spec(screens)
    components_by_spec = _by_spec(components)
    endpoints_by_spec = _by_spec(endpoints)
    data_entities_by_spec = _by_spec(data_entities)
    business_rules_by_spec = _by_spec(business_rules)
    scenarios_by_spec = _by_spec(scenarios)
    functional_requirements_by_spec = _by_spec(functional_requirements)
    spec_decisions_by_spec: dict[str, list[dict]] = {}
    for d in decisions:
        if d.get("spec_row_key"):
            spec_decisions_by_spec.setdefault(d["spec_row_key"], []).append(d)

    # Traceability rows whose source is THIS spec
    traceability_by_source: dict[str, list[dict]] = {}
    for t in traceability:
        traceability_by_source.setdefault(t["source_row_key"], []).append(t)

    # Hydrate each spec with its Stage B sub-rows
    specs_hydrated = []
    for s in specs:
        srk = s["row_key"]
        specs_hydrated.append({
            **s,
            "screens": screens_by_spec.get(srk, []),
            "ui_components": components_by_spec.get(srk, []),
            "endpoints": endpoints_by_spec.get(srk, []),
            "data_entities": data_entities_by_spec.get(srk, []),
            "business_rules": business_rules_by_spec.get(srk, []),
            "scenarios": scenarios_by_spec.get(srk, []),
            "functional_requirements": functional_requirements_by_spec.get(srk, []),
            "decisions": spec_decisions_by_spec.get(srk, []),
            "traceability": traceability_by_source.get(srk, []),
        })
    specs_by_mod = _by_module(specs_hydrated)

    # Module decisions (module-scoped only)
    module_decisions_by_key: dict[str, list[dict]] = {}
    for d in decisions:
        if d.get("module_row_key") and not d.get("spec_row_key"):
            module_decisions_by_key.setdefault(d["module_row_key"], []).append(d)

    modules_hydrated = []
    for m in modules:
        modules_hydrated.append({
            **m,
            "actors": actors_by_mod.get(m["row_key"], []),
            "responsibilities": resps_by_mod.get(m["row_key"], []),
            "interfaces": ifaces_by_mod.get(m["row_key"], []),
            "data_entities": des_by_mod.get(m["row_key"], []),
            "backlog": specs_by_mod.get(m["row_key"], []),
            "decisions": module_decisions_by_key.get(m["row_key"], []),
        })

    # Messages + sources
    messages = (
        await db.execute(
            select(ArtifactMessage)
            .where(ArtifactMessage.document_id == doc.id)
            .order_by(ArtifactMessage.seq)
        )
    ).scalars().all()
    sources = (
        await db.execute(
            select(ArtifactSource).where(ArtifactSource.artifact_document_id == doc.id)
        )
    ).scalars().all()

    return {
        "document": {
            "id": str(doc.id),
            "project_id": str(doc.project_id),
            "artifact_type": doc.artifact_type,
            "status": doc.status,
            "unit_status": doc.unit_status or {},
            "validated_at": doc.validated_at.isoformat() if doc.validated_at else None,
            "validated_by": str(doc.validated_by) if doc.validated_by else None,
            "validated_snapshot_key": doc.validated_snapshot_key,
            "created_at": doc.created_at.isoformat(),
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
        },
        "modules": modules_hydrated,
        "messages": [
            {
                "id": str(m.id), "seq": m.seq, "role": m.role,
                "content": m.content, "citations": m.citations or [],
                "meta": m.meta or {},
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
        "sources": [
            {
                "id": str(s.id),
                "source_document_id": str(s.source_document_id) if s.source_document_id else None,
                "included": s.included,
            }
            for s in sources
        ],
        "decisions": decisions,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Recovery helpers
# ═══════════════════════════════════════════════════════════════════════════════


async def reset_frs_generating(
    project_id: uuid.UUID, db: AsyncSession,
) -> ArtifactDocument:
    """If FRS is stuck in 'generating', reset to 'in_interview'. Idempotent."""
    doc = await _ensure_frs_document(project_id, db)
    if doc.status == "generating":
        doc.status = "in_interview"
        doc.unit_status = {**(doc.unit_status or {}), "_current_unit": None}
    return doc
