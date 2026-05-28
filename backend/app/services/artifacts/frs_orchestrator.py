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
from app.services.skills.dspy_frs import run_modularize

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

    # Soft-delete rows in scope but absent from output
    for row_key, current in existing_by_key.items():
        in_scope = scope_keys is None or row_key in scope_keys
        if in_scope and row_key not in output_keys and current.status != "removed":
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
# Full pipeline (Stage A only for now; Stage B added when shipped)
# ═══════════════════════════════════════════════════════════════════════════════


async def generate_frs_all(
    project: Project,
    db: AsyncSession,
    *,
    brief: str | None = None,
) -> dict:
    """Stage-A pipeline: ensure doc → mark generating → modularize → in_interview.

    Stage B (per-module FRS authoring) will be triggered next when shipped.
    For v1-Stage-A-only mode, returns the FRS detail after modularize completes.
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

    # Finalize → in_interview
    await db.refresh(doc)
    doc.status = "in_interview"
    await db.commit()
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
    specs_by_mod = _by_module(specs)

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
