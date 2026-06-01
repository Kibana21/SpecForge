"""Test Cases Artifact Orchestrator (Stage A plan_journeys + Stage B author_plan).

Mirrors frs_orchestrator.py:
- Versioned row upsert with lock + soft-delete semantics (human rows preserved)
- Atomic JSONB unit_status merges (concurrent-safe; nested per-module via jsonb_set)
- Mock-first DSPy (run_* → deterministic synthesis in mock mode)
- Replace-all traceability per source row
- Stage B is per-FRS-spec; modules parallelize (semaphore), specs sequential.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from sqlalchemy import func, select, text as sa_text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import ArtifactDocument, ArtifactMessage, ArtifactSource
from app.models.document import Document
from app.models.project import Project
from app.models.test_cases import TestCaseTraceability
from app.services.artifacts.manifest.test_cases import (
    TC_INT_COLS, TC_TABLE_MAP, TC_TYPED_COLS,
)
from app.services.context.project_context import (
    ProjectContextBundle, gather_project_context,
)
from app.services.skills.dspy_test_cases import run_author_plan, run_plan_journeys

log = logging.getLogger(__name__)

ARTIFACT_TYPE = "test_cases"


# ═══════════════════════════════════════════════════════════════════════════════
# Versioned row upsert (mirrors upsert_frs_rows; human rows protected from regen)
# ═══════════════════════════════════════════════════════════════════════════════


async def upsert_tc_rows(
    table_name: str,
    document_id: uuid.UUID,
    output_rows: list[dict[str, Any]],
    source: str,
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
    scope_keys: set[str] | None = None,
    protect_human: bool = True,
) -> int:
    """Idempotent versioned upsert for test-cases typed tables.

    Same semantics as upsert_frs_rows. When protect_human=True, rows whose current
    version has source='human' are never soft-deleted (manual/edited rows survive
    AI regeneration).
    """
    model = TC_TABLE_MAP[table_name]
    typed_cols = TC_TYPED_COLS[table_name]
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

    for row_key, current in existing_by_key.items():
        in_scope = scope_keys is None or row_key in scope_keys
        if (in_scope and row_key not in output_keys
                and current.status != "removed"
                and not current.is_locked
                and not (protect_human and current.source == "human")):
            current.status = "removed"

    return new_versions


def _strip_nul(obj: Any) -> Any:
    """Recursively remove NUL (\\u0000) from all strings.

    LLMs occasionally emit a NUL byte inside generated text; Postgres text/jsonb
    columns cannot store it (asyncpg raises UntranslatableCharacterError), which
    would otherwise fail the whole spec's insert. Strip it everywhere before persist.
    """
    if isinstance(obj, str):
        return obj.replace("\x00", "") if "\x00" in obj else obj
    if isinstance(obj, dict):
        return {k: _strip_nul(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_strip_nul(v) for v in obj]
    return obj


def _sanitize_refs(result: dict, target_spec: dict) -> dict:
    """Drop any case ref / traceability pointer that is not a real FRS row_key for
    this spec. Guarantees no `orphan_case` ever gets persisted, regardless of what
    the model emitted. Mutates + returns result.
    """
    scen = {x["row_key"] for x in target_spec.get("scenarios", [])}
    fr = {x["row_key"] for x in target_spec.get("functional_requirements", [])}
    br = {x["row_key"] for x in target_spec.get("business_rules", [])}
    scr = {x["row_key"] for x in target_spec.get("screens", [])}
    spec_key = target_spec.get("row_key")
    brd = set(target_spec.get("br_refs", []) or [])
    any_frs = scen | fr | br | scr | ({spec_key} if spec_key else set())
    allowed = {
        "frs_acceptance_scenario": scen, "frs_functional_requirement": fr,
        "frs_business_rule": br, "frs_screen": scr,
        "frs_spec": {spec_key} if spec_key else set(),
        "brd_business_requirement": brd,
    }
    for c in result.get("test_cases", []):
        c["scenario_refs"] = [k for k in (c.get("scenario_refs") or []) if k in scen]
        c["fr_refs"] = [k for k in (c.get("fr_refs") or []) if k in fr]
        c["br_refs"] = [k for k in (c.get("br_refs") or []) if k in br]
        if c.get("source_ref") and c["source_ref"] not in any_frs:
            c["source_ref"] = None
    kept = []
    for t in result.get("traceability", []):
        kind = t.get("target_kind")
        if kind == "within_test_cases" or kind not in allowed or t.get("target_ref") in allowed[kind]:
            kept.append(t)
    result["traceability"] = kept
    return result


def _coerce_int_cols(table: str, row: dict, existing: Any | None) -> dict:
    int_cols = TC_INT_COLS.get(table, set())
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


def _tc_row_to_dict(row: Any, table_name: str) -> dict:
    typed_cols = TC_TYPED_COLS[table_name]
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


async def _current_tc_rows_for(table_name: str, document_id: uuid.UUID, db: AsyncSession) -> list[dict]:
    model = TC_TABLE_MAP[table_name]
    rows = (
        await db.execute(
            select(model).where(
                model.document_id == document_id,
                model.is_current.is_(True),
                model.status == "active",
            )
        )
    ).scalars().all()
    return [_tc_row_to_dict(r, table_name) for r in rows]


# ═══════════════════════════════════════════════════════════════════════════════
# Document lifecycle + progress
# ═══════════════════════════════════════════════════════════════════════════════


async def _ensure_tc_document(project_id: uuid.UUID, db: AsyncSession) -> ArtifactDocument:
    """Get-or-create the test_cases ArtifactDocument. Idempotent + race-safe."""
    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == ARTIFACT_TYPE,
            )
        )
    ).scalar_one_or_none()
    if doc is not None:
        return doc
    try:
        async with db.begin_nested():
            doc = ArtifactDocument(project_id=project_id, artifact_type=ARTIFACT_TYPE, status="in_interview")
            db.add(doc)
            await db.flush()
            doc_ids = (
                await db.execute(select(Document.id).where(Document.project_id == project_id))
            ).scalars().all()
            for did in doc_ids:
                db.add(ArtifactSource(artifact_document_id=doc.id, source_document_id=did, included=True))
            await db.flush()
        return doc
    except IntegrityError:
        return (
            await db.execute(
                select(ArtifactDocument).where(
                    ArtifactDocument.project_id == project_id,
                    ArtifactDocument.artifact_type == ARTIFACT_TYPE,
                )
            )
        ).scalar_one()


async def _merge_unit_status(doc_id: uuid.UUID, patch: dict, db: AsyncSession) -> None:
    """Shallow-merge top-level keys into unit_status."""
    await db.execute(sa_text(
        "UPDATE artifact_documents "
        "SET unit_status = COALESCE(unit_status, '{}'::jsonb) || CAST(:patch AS jsonb), "
        "    updated_at = NOW() WHERE id = :doc_id"
    ), {"patch": json.dumps(patch), "doc_id": str(doc_id)})


async def _set_nested_status(doc_id: uuid.UUID, path: list[str], value: Any, db: AsyncSession) -> None:
    """Race-free nested set via jsonb_set (siblings preserved). Creates missing parents.

    The path is bound as a Python list (asyncpg encodes it as Postgres text[]).
    """
    from sqlalchemy import bindparam
    from sqlalchemy.dialects.postgresql import ARRAY
    from sqlalchemy import String

    if len(path) > 1:
        stmt = sa_text(
            "UPDATE artifact_documents "
            "SET unit_status = jsonb_set(COALESCE(unit_status,'{}'::jsonb), :ppath, "
            "    COALESCE(unit_status #> :ppath, '{}'::jsonb), true) WHERE id = :doc_id"
        ).bindparams(bindparam("ppath", type_=ARRAY(String)))
        await db.execute(stmt, {"ppath": path[:-1], "doc_id": str(doc_id)})
    stmt = sa_text(
        "UPDATE artifact_documents "
        "SET unit_status = jsonb_set(COALESCE(unit_status,'{}'::jsonb), :path, CAST(:val AS jsonb), true), "
        "    updated_at = NOW() WHERE id = :doc_id"
    ).bindparams(bindparam("path", type_=ARRAY(String)))
    await db.execute(stmt, {"path": path, "val": json.dumps(value), "doc_id": str(doc_id)})


# ═══════════════════════════════════════════════════════════════════════════════
# Traceability (replace-all per source row)
# ═══════════════════════════════════════════════════════════════════════════════


async def _upsert_tc_traceability(
    document_id: uuid.UUID, source_table: str, source_row_key: str,
    rows: list[dict[str, Any]], db: AsyncSession,
) -> int:
    inserted = 0
    async with db.begin_nested():
        await db.execute(sa_text(
            "DELETE FROM test_case_traceability "
            "WHERE document_id = :doc AND source_table = :st AND source_row_key = :sk"
        ), {"doc": str(document_id), "st": source_table, "sk": source_row_key})
        for r in rows:
            target_ref = (r.get("target_ref") or "").strip()
            target_kind = r.get("target_kind")
            if not target_ref or not target_kind:
                continue
            db.add(TestCaseTraceability(
                id=uuid.uuid4(), document_id=document_id,
                source_table=source_table, source_row_key=source_row_key,
                target_kind=target_kind, target_ref=target_ref,
                target_label=r.get("target_label", ""), confidence=r.get("confidence", "high"),
            ))
            inserted += 1
    return inserted


# ═══════════════════════════════════════════════════════════════════════════════
# FRS layer → DSPy input helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _index_frs(frs) -> dict[str, dict[str, list[dict]]]:
    """Group FRS sub-rows by spec_row_key for fast per-spec assembly."""
    def _grp(rows):
        out: dict[str, list[dict]] = {}
        for r in rows:
            out.setdefault(r.get("spec_row_key"), []).append(r)
        return out
    actors_by_mod: dict[str, list[str]] = {}
    for a in frs.module_actors:
        actors_by_mod.setdefault(a.get("module_row_key"), []).append(a.get("actor_name", ""))
    return {
        "scenarios": _grp(frs.acceptance_scenarios),
        "frs": _grp(frs.functional_requirements),
        "rules": _grp(frs.business_rules),
        "screens": _grp(frs.screens),
        "actors_by_mod": actors_by_mod,
    }


def _build_specs_json(frs, idx) -> str:
    """SLIM spec list for Stage A — just enough structure to lay out suites + plan
    stubs and write journey narratives. Element row_keys are NOT sent (the LLM
    doesn't need to echo them; coverage_targets are computed deterministically via
    _coverage_targets_by_spec). Keeps the single plan_journeys call small."""
    specs = []
    for s in frs.specs:
        skey = s["row_key"]
        specs.append({
            "row_key": skey,
            "title": s.get("title", ""),
            "priority": s.get("priority", "P1"),
            "module_row_key": s.get("module_row_key", ""),
            "narrative": (s.get("narrative", "") or "")[:200],
            "n_scenarios": len(idx["scenarios"].get(skey, [])),
            "n_frs": len(idx["frs"].get(skey, [])),
            "n_rules": len(idx["rules"].get(skey, [])),
            "n_screens": len(idx["screens"].get(skey, [])),
        })
    return json.dumps(specs)


def _coverage_targets_by_spec(frs, idx) -> dict[str, dict]:
    """Deterministic coverage_targets per spec (no LLM needed)."""
    out: dict[str, dict] = {}
    for s in frs.specs:
        skey = s["row_key"]
        out[skey] = {
            "scenarios": [x["row_key"] for x in idx["scenarios"].get(skey, [])],
            "frs": [x["row_key"] for x in idx["frs"].get(skey, [])],
            "business_rules": [x["row_key"] for x in idx["rules"].get(skey, [])],
            "screens": [x["row_key"] for x in idx["screens"].get(skey, [])],
        }
    return out


def _build_target_spec(frs, idx, spec: dict) -> dict:
    skey = spec["row_key"]
    mkey = spec.get("module_row_key", "")
    return {
        "row_key": skey,
        "title": spec.get("title", ""),
        "priority": spec.get("priority", "P1"),
        "module_row_key": mkey,
        "narrative": spec.get("narrative", ""),
        "independent_test": spec.get("independent_test", ""),
        "data_and_validation": spec.get("data_and_validation", ""),
        "errors_and_edge_cases": spec.get("errors_and_edge_cases", ""),
        "observability": spec.get("observability", ""),
        "br_refs": spec.get("br_refs", []) or [],
        "actors": idx["actors_by_mod"].get(mkey, []),
        "scenarios": [
            {"row_key": x["row_key"], "given": x.get("given", ""), "when": x.get("when", ""),
             "then": x.get("then", ""), "is_negative": x.get("is_negative", False),
             "fr_refs": x.get("fr_refs", []) or []}
            for x in idx["scenarios"].get(skey, [])
        ],
        "functional_requirements": [
            {"row_key": x["row_key"], "fr_id": x.get("fr_id", ""), "requirement_text": x.get("requirement_text", "")}
            for x in idx["frs"].get(skey, [])
        ],
        "business_rules": [
            {"row_key": x["row_key"], "rule_id": x.get("rule_id", ""), "description": x.get("description", "")}
            for x in idx["rules"].get(skey, [])
        ],
        "screens": [
            {"row_key": x["row_key"], "screen_name": x.get("screen_name", "")}
            for x in idx["screens"].get(skey, [])
        ],
    }


def _focused_brd(bundle: ProjectContextBundle, br_refs: list[str]) -> str:
    """Compact BRD slice: only the business requirements this spec traces to.

    Keeps the per-spec author_plan completion small instead of shipping the entire
    BRD on every one of N specs.
    """
    if bundle.brd is None:
        return "(no BRD)"
    refs = set(br_refs or [])
    brs = [b for b in bundle.brd.business_requirements if b.get("row_key") in refs]
    if not brs:
        return "(no linked business requirements)"
    lines = ["=== Linked Business Requirements ==="]
    for b in brs:
        desc = (b.get("description") or "")[:300]
        lines.append(f"[{b['row_key']}] ({b.get('priority', '')}) {b.get('title', '')}: {desc}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# Stage A — plan_journeys
# ═══════════════════════════════════════════════════════════════════════════════


async def generate_tc_plan_journeys(
    project: Project, doc: ArtifactDocument, bundle: ProjectContextBundle, db: AsyncSession,
) -> dict:
    frs = bundle.frs
    if frs is None or not frs.specs:
        return {"suites": 0, "plans": 0}
    idx = _index_frs(frs)
    await _merge_unit_status(doc.id, {"_current_unit": "plan_journeys"}, db)

    modules_json = json.dumps([
        {"row_key": m["row_key"], "name": m.get("name", ""), "layer": m.get("layer", "vertical")}
        for m in frs.modules
    ])
    specs_json = _build_specs_json(frs, idx)

    # Stage A is structural narrative only — it does NOT need the full BRD/CB/docs.
    # Sending just the FRS module/spec outline keeps this single call small + fast
    # (the heavy corpus only matters when authoring actual cases in Stage B).
    result = await run_plan_journeys(
        project_name=project.name, business_unit=project.business_unit or "—",
        frs_context=frs.formatted_context,
        brd_context="", cb_context="", app_brain="",
        source_sections="", qa_pairs="",
        modules_json=modules_json, specs_json=specs_json,
        current_plans="{}", locked_plans="[]",
    )
    result = _strip_nul(result)

    suites = result.get("suites", [])
    plans = result.get("plans", [])
    # coverage_targets are authoritative from the FRS index, not the LLM echo.
    cov = _coverage_targets_by_spec(frs, idx)
    for p in plans:
        p["coverage_targets"] = cov.get(p.get("spec_row_key"), {})
    n_suites = await upsert_tc_rows("test_suites", doc.id, suites, "ai", db, scope_keys=None)
    n_plans = await upsert_tc_rows("test_plans", doc.id, plans, "ai", db, scope_keys=None)
    return {"suites": n_suites, "plans": n_plans}


# ═══════════════════════════════════════════════════════════════════════════════
# Stage B — author_plan (one FRS spec)
# ═══════════════════════════════════════════════════════════════════════════════


async def generate_tc_author_plan(
    project: Project, spec_row_key: str, doc: ArtifactDocument,
    bundle: ProjectContextBundle, db: AsyncSession, *, quality: str = "fast",
) -> dict:
    frs = bundle.frs
    if frs is None:
        return {"cases": 0}
    spec = next((s for s in frs.specs if s["row_key"] == spec_row_key), None)
    if spec is None:
        return {"cases": 0}

    idx = _index_frs(frs)
    module_key = spec.get("module_row_key", "")
    plan_key = f"TP-{spec_row_key}"
    suite_key = f"TS-{module_key}"
    target_spec = _build_target_spec(frs, idx, spec)

    await _merge_unit_status(doc.id, {"_current_unit": f"author_plan_{spec_row_key}"}, db)

    # current cases for idempotency
    existing_cases = [
        c for c in await _current_tc_rows_for("test_cases", doc.id, db)
        if c.get("plan_row_key") == plan_key
    ]
    sibling = [
        {"row_key": p["row_key"], "title": p.get("title", "")}
        for p in await _current_tc_rows_for("test_plans", doc.id, db)
        if p.get("module_row_key") == module_key and p["row_key"] != plan_key
    ]

    result = await run_author_plan(
        quality=quality,
        project_name=project.name, business_unit=project.business_unit or "—",
        target_spec_row_key=spec_row_key, plan_row_key=plan_key,
        suite_row_key=suite_key, module_row_key=module_key,
        target_spec=json.dumps(target_spec),
        module_context=json.dumps({"module_row_key": module_key, "actors": target_spec["actors"]}),
        sibling_plans_summary=json.dumps(sibling),
        # Trimmed context: a per-spec author only needs the BRs THIS spec traces to
        # (not the whole BRD) plus App Brain domain truths. The full spec + sub-rows
        # already carry the doc-derived content, so cb/doc sections are dropped to
        # keep each Vertex completion small + fast.
        brd_context=_focused_brd(bundle, target_spec.get("br_refs") or []),
        cb_context="", app_brain=bundle.apps.formatted_context,
        nfr_context="", source_sections="", qa_pairs="",
        current_plan=json.dumps({"cases": existing_cases}),
    )
    result = _sanitize_refs(_strip_nul(result), target_spec)

    # Persist the filled-out plan
    plan_full = result.get("plan")
    if plan_full:
        await upsert_tc_rows("test_plans", doc.id, [plan_full], "ai", db, scope_keys={plan_key})

    # Persist cases — scope soft-delete to this plan's AI children only
    cases = result.get("test_cases", [])
    for c in cases:
        c.setdefault("plan_row_key", plan_key)
        c.setdefault("spec_row_key", spec_row_key)
        c.setdefault("module_row_key", module_key)
    ai_scope = {c["row_key"] for c in existing_cases if c.get("source") != "human"}
    ai_scope |= {c["row_key"] for c in cases}
    n_cases = await upsert_tc_rows("test_cases", doc.id, cases, "ai", db, scope_keys=ai_scope)

    # Replace-all traceability grouped by (source_table, source_row_key)
    grouped: dict[tuple[str, str], list[dict]] = {}
    for t in result.get("traceability", []):
        grouped.setdefault((t["source_table"], t["source_row_key"]), []).append(t)
    for (st, sk), rows in grouped.items():
        await _upsert_tc_traceability(doc.id, st, sk, rows, db)

    await _set_nested_status(doc.id, [plan_key],
                             {"status": "done", "module": module_key,
                              "completeness": 100, "cases_authored": len(cases)}, db)
    return {"cases": n_cases, "plan_row_key": plan_key}


# ═══════════════════════════════════════════════════════════════════════════════
# Full pipeline
# ═══════════════════════════════════════════════════════════════════════════════


# Default concurrent specs authored together. Spec-level (not module-level) so a
# single large module doesn't bottleneck the run. Configured via settings
# (TC_PARALLEL_SPECS in .env); read lazily so .env changes apply on worker restart.
def _default_parallel_specs() -> int:
    from app.config import get_settings
    return max(1, get_settings().tc_parallel_specs)


def _repair_parallel_specs() -> int:
    """Concurrency for the repair / 'Fix automatically' pass. It runs alone (no bulk
    generation competing for the Vertex budget), so it can fan out wider than bulk
    generation. Tunable via TC_REPAIR_PARALLEL_SPECS."""
    from app.config import get_settings
    return max(1, get_settings().tc_repair_parallel_specs)


async def _author_specs_parallel(
    project: Project, doc: ArtifactDocument, bundle: ProjectContextBundle,
    specs_by_mod: dict[str, list[str]], db: AsyncSession, *, max_parallel_specs: int,
    quality: str = "fast",
) -> None:
    """Author every spec's plan with SPEC-level concurrency (global semaphore).

    All specs across all modules share one pool of `max_parallel_specs` workers, so
    several specs author at once regardless of which module they belong to. Module
    progress bars advance as each spec completes (asyncio increments are race-free
    on a single loop). Each spec gets its own DB session.
    """
    from app.db import AsyncSessionLocal

    for mod_key, spec_keys in specs_by_mod.items():
        await _set_nested_status(doc.id, ["_module_progress", mod_key],
                                 {"specs_total": len(spec_keys), "specs_done": 0}, db)
    await db.commit()

    done: dict[str, int] = {mod: 0 for mod in specs_by_mod}
    sem = asyncio.Semaphore(max_parallel_specs)
    flat = [(mod, sk) for mod, sks in specs_by_mod.items() for sk in sks]

    async def _one(mod_key: str, spec_key: str) -> None:
        async with sem:
            async with AsyncSessionLocal() as unit_db:
                unit_doc = await unit_db.get(ArtifactDocument, doc.id)
                if unit_doc is None:
                    return
                plan_key = f"TP-{spec_key}"
                # Mark in-flight + commit BEFORE the ~60s LLM call so the theater
                # shows live "authoring" feedback instead of looking frozen.
                await _set_nested_status(doc.id, [plan_key],
                                         {"status": "authoring", "module": mod_key, "cases_authored": 0}, unit_db)
                await unit_db.commit()
                try:
                    await generate_tc_author_plan(project, spec_key, unit_doc, bundle, unit_db, quality=quality)
                    await unit_db.commit()
                except Exception:
                    log.exception("tc.author_plan.failed", extra={"doc_id": str(doc.id), "spec": spec_key})
                    await unit_db.rollback()
                    await _set_nested_status(doc.id, [plan_key], {"status": "failed", "module": mod_key}, unit_db)
                done[mod_key] += 1  # race-free on the single asyncio loop
                await _set_nested_status(doc.id, ["_module_progress", mod_key, "specs_done"], done[mod_key], unit_db)
                await unit_db.commit()

    await asyncio.gather(*[_one(m, s) for m, s in flat])


async def generate_tc_all(
    project: Project, db: AsyncSession, *,
    run_stage_b: bool = True, max_parallel_specs: int | None = None,
) -> dict:
    """Stage A (plan_journeys) → Stage B (author_plan per spec, spec-level parallel)."""
    max_parallel_specs = max_parallel_specs or _default_parallel_specs()
    doc = await _ensure_tc_document(project.id, db)
    doc.unit_status = {}
    doc.status = "generating"
    await db.commit()

    bundle = await gather_project_context(
        project.id, db, artifact_document_id=doc.id, artifact_type=ARTIFACT_TYPE,
    )
    if not bundle.readiness.can_generate:
        doc.status = "in_interview"
        await db.commit()
        raise RuntimeError(f"Test-case generation blocked: {bundle.readiness.blocking_reason}")

    await generate_tc_plan_journeys(project, doc, bundle, db)
    await db.commit()

    if run_stage_b and bundle.frs is not None:
        specs_by_mod: dict[str, list[str]] = {}
        for s in bundle.frs.specs:
            specs_by_mod.setdefault(s.get("module_row_key", ""), []).append(s["row_key"])
        await _author_specs_parallel(project, doc, bundle, specs_by_mod, db, max_parallel_specs=max_parallel_specs)

    await db.refresh(doc)
    doc.status = "in_interview"
    doc.unit_status = {**(doc.unit_status or {}), "_current_unit": None}
    await db.commit()
    return await get_tc_detail(project.id, db)


async def run_tc_stage_b(
    project: Project, db: AsyncSession, *, skip_designed: bool = True,
    max_parallel_specs: int | None = None, module_row_key: str | None = None,
    spec_keys: set[str] | None = None, quality: str = "fast",
) -> dict:
    """Run Stage B (author all/remaining plans) without re-running Stage A.

    skip_designed=True  → only specs whose plan has no cases yet ('design remaining').
    skip_designed=False → re-author every spec ('regenerate all'), preserving
                          locked + human cases.
    module_row_key      → restrict to one module (module-level regenerate).
    spec_keys           → restrict to an explicit set of spec row_keys (surgical
                          'regenerate only these specs', e.g. the thin ones).
    """
    max_parallel_specs = max_parallel_specs or _default_parallel_specs()
    doc = await _ensure_tc_document(project.id, db)
    bundle = await gather_project_context(project.id, db, artifact_document_id=doc.id, artifact_type=ARTIFACT_TYPE)
    if bundle.frs is None:
        return await get_tc_detail(project.id, db)

    existing_cases = await _current_tc_rows_for("test_cases", doc.id, db)
    plans_with_cases = {c["plan_row_key"] for c in existing_cases}

    specs_by_mod: dict[str, list[str]] = {}
    for s in bundle.frs.specs:
        if module_row_key and s.get("module_row_key") != module_row_key:
            continue
        if spec_keys is not None and s["row_key"] not in spec_keys:
            continue
        if skip_designed and f"TP-{s['row_key']}" in plans_with_cases:
            continue
        specs_by_mod.setdefault(s.get("module_row_key", ""), []).append(s["row_key"])

    doc.status = "generating"
    await db.commit()
    await _author_specs_parallel(project, doc, bundle, specs_by_mod, db,
                                 max_parallel_specs=max_parallel_specs, quality=quality)

    await db.refresh(doc)
    doc.status = "in_interview"
    doc.unit_status = {**(doc.unit_status or {}), "_current_unit": None}
    await db.commit()
    return await get_tc_detail(project.id, db)


async def regenerate_tc_plan(project: Project, spec_row_key: str, db: AsyncSession) -> dict:
    """Re-author a single plan (preserves locked + human cases)."""
    doc = await _ensure_tc_document(project.id, db)
    bundle = await gather_project_context(project.id, db, artifact_document_id=doc.id, artifact_type=ARTIFACT_TYPE)
    # Single-plan regenerate is targeted → use high-quality (ChainOfThought) so the
    # re-authored cases are rich.
    await generate_tc_author_plan(project, spec_row_key, doc, bundle, db, quality="high")
    await _merge_unit_status(doc.id, {"_current_unit": None}, db)
    await db.commit()
    return await get_tc_detail(project.id, db)


# ═══════════════════════════════════════════════════════════════════════════════
# Repair: clean up dangling refs (no LLM) + regenerate only the thin specs
# ═══════════════════════════════════════════════════════════════════════════════

# Findings a Stage-B re-author can actually fix (richness, coverage, missing
# negatives, leftover orphans). Excludes must_br_untested (resolves transitively)
# and pure warnings/minors that don't block.
_REGEN_FIXABLE = {
    "case_not_rich", "case_no_trace", "orphan_case", "no_negative_test",
    "scenario_uncovered", "fr_uncovered", "responsive_no_viewports",
    "plan_zero_cases", "independent_test_uncovered", "business_rule_uncovered",
}


def _spec_from_rowkey(rk: str | None) -> str | None:
    """Map a finding's row_key back to its FRS spec_row_key.

    Cases are 'TP-{spec}-TC-001', plans are 'TP-{spec}', and spec-level findings
    carry the spec_row_key directly. BR/other keys return as-is (harmless — the
    caller intersects against real spec keys).
    """
    import re
    if not rk:
        return None
    m = re.match(r"TP-(.+?)-TC-\d+$", rk)
    if m:
        return m.group(1)
    if rk.startswith("TP-"):
        return rk[3:]
    return rk


async def cleanup_tc_refs(project: Project, db: AsyncSession) -> dict:
    """Strip refs/traceability that point at FRS rows which no longer exist.

    Purely a data-quality pass (no LLM): leftovers from earlier multi-version
    runs where the model emitted BRD/doc codes (BR-001, CON-001, …) into a case's
    FRS-ref columns. Removing them clears every `orphan_case` finding instantly.
    Edits the current row in place (no version churn) and deletes dangling
    FRS-element traceability rows. Idempotent. Returns a summary.
    """
    from app.models.test_cases import TestCase
    from app.services.artifacts.validators.test_cases import _active_frs_keys

    doc = await _ensure_tc_document(project.id, db)
    active = await _active_frs_keys(project.id, db)

    cases = (
        await db.execute(select(TestCase).where(
            TestCase.document_id == doc.id, TestCase.is_current.is_(True),
            TestCase.status == "active",
        ))
    ).scalars().all()

    cases_cleaned = 0
    refs_removed = 0
    for c in cases:
        changed = False
        for col in ("scenario_refs", "fr_refs", "br_refs"):
            cur = list(getattr(c, col) or [])
            kept = [k for k in cur if k in active]
            if len(kept) != len(cur):
                refs_removed += len(cur) - len(kept)
                setattr(c, col, kept)
                changed = True
        if c.source_ref and c.source_ref not in active:
            c.source_ref = None
            changed = True
        if changed:
            cases_cleaned += 1

    trows = (
        await db.execute(select(TestCaseTraceability).where(
            TestCaseTraceability.document_id == doc.id,
            TestCaseTraceability.target_kind.in_((
                "frs_acceptance_scenario", "frs_functional_requirement",
                "frs_business_rule", "frs_screen",
            )),
        ))
    ).scalars().all()
    traces_removed = 0
    for t in trows:
        if t.target_ref not in active:
            await db.delete(t)
            traces_removed += 1

    await db.commit()
    return {"cases_cleaned": cases_cleaned, "refs_removed": refs_removed,
            "traces_removed": traces_removed}


async def thin_tc_spec_keys(doc: ArtifactDocument, db: AsyncSession) -> set[str]:
    """Spec row_keys whose plans still have a regen-fixable finding."""
    from app.services.artifacts.validators.test_cases import run_tc_validation
    findings = await run_tc_validation(doc.id, doc, db)
    specs: set[str] = set()
    for f in findings:
        if f.get("check_id") not in _REGEN_FIXABLE:
            continue
        sk = _spec_from_rowkey(f.get("row_key"))
        if sk:
            specs.add(sk)
    return specs


async def regen_thin_tc(project: Project, db: AsyncSession) -> dict:
    """Re-author only the specs that still fail validation (the 'thin' ones).

    Preserves locked + human cases. A no-op (returns current detail) when nothing
    is thin. Pairs with cleanup_tc_refs for the surgical 'clean up + fix' flow.
    """
    doc = await _ensure_tc_document(project.id, db)
    thin = await thin_tc_spec_keys(doc, db)
    if not thin:
        await db.refresh(doc)
        doc.status = "in_interview"
        await db.commit()
        return await get_tc_detail(project.id, db)

    # Seed a "repair manifest" into unit_status so the UI can show — by FEATURE
    # NAME, not row code — which tests are pending / running / done as it goes.
    # _author_specs_parallel then flips each TP-<spec> entry pending→authoring→done.
    plans = await _current_tc_rows_for("test_plans", doc.id, db)
    title_by_spec = {p["spec_row_key"]: (p.get("title") or p["spec_row_key"]) for p in plans}
    mod_by_spec = {p["spec_row_key"]: p.get("module_row_key", "") for p in plans}
    manifest = [
        {"key": f"TP-{s}", "spec": s, "title": title_by_spec.get(s, s), "module": mod_by_spec.get(s, "")}
        for s in sorted(thin)
    ]
    seeded: dict[str, Any] = {"_repair": {"active": True, "total": len(manifest)}, "_repair_specs": manifest}
    for m in manifest:
        seeded[m["key"]] = {"status": "pending", "module": m["module"], "cases_authored": 0}
    doc.unit_status = seeded
    doc.status = "generating"
    await db.commit()

    # High-quality re-author: the whole point is to make thin cases rich, so use
    # ChainOfThought + full reasoning (otherwise we'd just reproduce thin cases).
    # Fan out as wide as the thin-spec count allows, up to the repair cap — the
    # repair runs alone so it can use more of the Vertex budget than bulk gen.
    mp = min(len(thin), _repair_parallel_specs())
    detail = await run_tc_stage_b(project, db, skip_designed=False, spec_keys=thin,
                                  quality="high", max_parallel_specs=mp)
    await _merge_unit_status(doc.id, {"_repair": {"active": False, "total": len(manifest)}}, db)
    await db.commit()
    return detail


# ═══════════════════════════════════════════════════════════════════════════════
# CRUD (mirrors edit/delete/unlock/restore/history_frs_row)
# ═══════════════════════════════════════════════════════════════════════════════

_LINKERS = ("suite_row_key", "spec_row_key", "module_row_key", "plan_row_key")


async def edit_tc_row(
    document_id: uuid.UUID, table_name: str, row_id: uuid.UUID, fields: dict[str, Any],
    db: AsyncSession, *, user_id: uuid.UUID | None = None, lock: bool = False,
    expected_version: int | None = None,
) -> Any:
    model = TC_TABLE_MAP[table_name]
    typed_cols = TC_TYPED_COLS[table_name]
    current = (
        await db.execute(select(model).where(model.id == row_id, model.is_current.is_(True)))
    ).scalar_one_or_none()
    if current is None:
        raise ValueError(f"row_not_found: {table_name}/{row_id}")
    if expected_version is not None and current.version != expected_version:
        raise ValueError(f"version_conflict: row at v{current.version}, sent {expected_version}")

    coerced = _coerce_int_cols(table_name, fields, current)
    current.is_current = False
    new_row_data = {c: getattr(current, c) for c in typed_cols}
    for c in typed_cols:
        if c in coerced:
            new_row_data[c] = coerced[c]
    new_row = model(
        document_id=current.document_id, row_key=current.row_key,
        version=current.version + 1, is_current=True,
        is_locked=lock or current.is_locked, status="active",
        source="human", created_by=user_id, **new_row_data,
    )
    db.add(new_row)
    await db.flush()
    return new_row


async def delete_tc_row(document_id: uuid.UUID, table_name: str, row_id: uuid.UUID, db: AsyncSession) -> None:
    model = TC_TABLE_MAP[table_name]
    current = (
        await db.execute(select(model).where(model.id == row_id, model.is_current.is_(True)))
    ).scalar_one_or_none()
    if current is None:
        raise ValueError(f"row_not_found: {table_name}/{row_id}")
    if current.is_locked:
        raise ValueError(f"row_locked: {table_name}/{row_id}")
    current.status = "removed"


async def unlock_tc_row(document_id: uuid.UUID, table_name: str, row_id: uuid.UUID, db: AsyncSession) -> None:
    model = TC_TABLE_MAP[table_name]
    current = (
        await db.execute(select(model).where(model.id == row_id, model.is_current.is_(True)))
    ).scalar_one_or_none()
    if current is None:
        raise ValueError(f"row_not_found: {table_name}/{row_id}")
    current.is_locked = False


async def restore_tc_row(
    document_id: uuid.UUID, table_name: str, target_row_id: uuid.UUID, db: AsyncSession,
    *, user_id: uuid.UUID | None = None,
) -> Any:
    model = TC_TABLE_MAP[table_name]
    typed_cols = TC_TYPED_COLS[table_name]
    target = await db.get(model, target_row_id)
    if target is None:
        raise ValueError(f"row_not_found: {table_name}/{target_row_id}")
    current = (
        await db.execute(select(model).where(
            model.document_id == target.document_id, model.row_key == target.row_key,
            model.is_current.is_(True),
        ))
    ).scalar_one_or_none()
    if current is not None:
        current.is_current = False
    new_version = (current.version + 1) if current else 1
    payload = {c: getattr(target, c) for c in typed_cols}
    new_row = model(
        document_id=target.document_id, row_key=target.row_key, version=new_version,
        is_current=True, is_locked=False, status="active", source="human",
        created_by=user_id, **payload,
    )
    db.add(new_row)
    await db.flush()
    return new_row


async def get_tc_row_history(document_id: uuid.UUID, table_name: str, row_id: uuid.UUID, db: AsyncSession) -> list[dict]:
    model = TC_TABLE_MAP[table_name]
    anchor = await db.get(model, row_id)
    if anchor is None:
        raise ValueError(f"row_not_found: {table_name}/{row_id}")
    rows = (
        await db.execute(
            select(model).where(
                model.document_id == anchor.document_id, model.row_key == anchor.row_key,
            ).order_by(model.version.desc())
        )
    ).scalars().all()
    return [_tc_row_to_dict(r, table_name) for r in rows]


async def add_tc_case(
    project_id: uuid.UUID, plan_row_key: str, payload: dict[str, Any], db: AsyncSession,
    *, user_id: uuid.UUID | None = None,
) -> dict:
    """Add a manual test case to a plan and persist its FRS link(s) as traceability.

    Validates every link resolves to an active FRS row (raises ValueError otherwise).
    """
    from app.models.test_cases import TestCase, TestPlan

    doc = (
        await db.execute(select(ArtifactDocument).where(
            ArtifactDocument.project_id == project_id,
            ArtifactDocument.artifact_type == ARTIFACT_TYPE,
        ))
    ).scalar_one_or_none()
    if doc is None:
        raise ValueError("test_cases_document_not_found")

    plan = (
        await db.execute(select(TestPlan).where(
            TestPlan.document_id == doc.id, TestPlan.row_key == plan_row_key,
            TestPlan.is_current.is_(True), TestPlan.status == "active",
        ))
    ).scalar_one_or_none()
    if plan is None:
        raise ValueError(f"plan_not_found: {plan_row_key}")

    links = payload.get("links") or {}
    scenario_refs = list(links.get("scenario_refs") or [])
    fr_refs = list(links.get("fr_refs") or [])
    br_refs = list(links.get("br_refs") or [])
    if not (scenario_refs or fr_refs or br_refs):
        raise ValueError("at_least_one_link_required")

    # Validate links resolve to active FRS rows
    await _validate_frs_links(project_id, scenario_refs, fr_refs, br_refs, db)

    # Next row_key
    existing = (
        await db.execute(select(TestCase.row_key).where(
            TestCase.document_id == doc.id, TestCase.plan_row_key == plan_row_key,
        ))
    ).scalars().all()
    max_n = 0
    for rk in existing:
        if "-TC-" in rk:
            try:
                max_n = max(max_n, int(rk.rsplit("-TC-", 1)[1]))
            except ValueError:
                pass
    new_key = f"{plan_row_key}-TC-{max_n + 1:03d}"

    source_ref = (scenario_refs or fr_refs or br_refs)[0]
    case_row = {
        "row_key": new_key, "plan_row_key": plan_row_key,
        "spec_row_key": plan.spec_row_key, "module_row_key": plan.module_row_key,
        "title": payload.get("title", "Untitled test case"),
        "test_type": payload.get("test_type", "functional"),
        "source_kind": "manual", "source_ref": source_ref,
        "given": payload.get("given", ""), "when": payload.get("when", ""),
        "then": payload.get("then", ""), "steps": payload.get("steps", []),
        "preconditions": payload.get("preconditions", ""),
        "key_assertions": payload.get("key_assertions", []),
        "test_data": payload.get("test_data", {}),
        "expected_result": payload.get("expected_result", ""),
        "expected_observability": payload.get("expected_observability", []),
        "viewports": payload.get("viewports", []),
        "auth_required": payload.get("auth_required", False),
        "auth_role": payload.get("auth_role"),
        "priority": payload.get("priority", "P1"),
        "fr_refs": fr_refs, "scenario_refs": scenario_refs, "br_refs": br_refs,
    }
    await upsert_tc_rows("test_cases", doc.id, [case_row], "human", db, user_id=user_id, scope_keys=set())

    # Traceability for the manual case + transitive BRD trace from the spec
    traces = []
    for k in scenario_refs:
        traces.append({"source_table": "test_cases", "source_row_key": new_key,
                       "target_kind": "frs_acceptance_scenario", "target_ref": k})
    for k in fr_refs:
        traces.append({"source_table": "test_cases", "source_row_key": new_key,
                       "target_kind": "frs_functional_requirement", "target_ref": k})
    for k in br_refs:
        traces.append({"source_table": "test_cases", "source_row_key": new_key,
                       "target_kind": "frs_business_rule", "target_ref": k})
    for br in await _spec_brd_refs(project_id, plan.spec_row_key, db):
        traces.append({"source_table": "test_cases", "source_row_key": new_key,
                       "target_kind": "brd_business_requirement", "target_ref": br})
    await _upsert_tc_traceability(doc.id, "test_cases", new_key, traces, db)
    await db.flush()
    return {"row_key": new_key}


async def _validate_frs_links(
    project_id: uuid.UUID, scenario_refs: list[str], fr_refs: list[str], br_refs: list[str], db: AsyncSession,
) -> None:
    from app.models.artifact import ArtifactDocument as AD
    from app.models.frs import FrsAcceptanceScenario, FrsBusinessRule, FrsFunctionalRequirement

    frs_doc = (
        await db.execute(select(AD).where(AD.project_id == project_id, AD.artifact_type == "frs"))
    ).scalar_one_or_none()
    if frs_doc is None:
        raise ValueError("frs_not_found")

    async def _active_keys(model) -> set[str]:
        rows = (
            await db.execute(select(model.row_key).where(
                model.document_id == frs_doc.id, model.is_current.is_(True), model.status == "active",
            ))
        ).scalars().all()
        return set(rows)

    if scenario_refs:
        valid = await _active_keys(FrsAcceptanceScenario)
        missing = [k for k in scenario_refs if k not in valid]
        if missing:
            raise ValueError(f"invalid_scenario_refs: {missing}")
    if fr_refs:
        valid = await _active_keys(FrsFunctionalRequirement)
        missing = [k for k in fr_refs if k not in valid]
        if missing:
            raise ValueError(f"invalid_fr_refs: {missing}")
    if br_refs:
        valid = await _active_keys(FrsBusinessRule)
        missing = [k for k in br_refs if k not in valid]
        if missing:
            raise ValueError(f"invalid_br_refs: {missing}")


async def _spec_brd_refs(project_id: uuid.UUID, spec_row_key: str, db: AsyncSession) -> list[str]:
    """The BRD BR row_keys an FRS spec traces to (for transitive rollup)."""
    from app.models.artifact import ArtifactDocument as AD
    from app.models.frs import FrsTraceability

    frs_doc = (
        await db.execute(select(AD).where(AD.project_id == project_id, AD.artifact_type == "frs"))
    ).scalar_one_or_none()
    if frs_doc is None:
        return []
    rows = (
        await db.execute(select(FrsTraceability.target_ref).where(
            FrsTraceability.document_id == frs_doc.id,
            FrsTraceability.source_row_key == spec_row_key,
            FrsTraceability.target_kind == "brd_business_requirement",
        ))
    ).scalars().all()
    return list(dict.fromkeys(rows))


# ═══════════════════════════════════════════════════════════════════════════════
# Detail + recovery
# ═══════════════════════════════════════════════════════════════════════════════


async def get_tc_detail(project_id: uuid.UUID, db: AsyncSession) -> dict:
    """Hydrate suites → plans → cases + traceability for the GET endpoint."""
    doc = (
        await db.execute(select(ArtifactDocument).where(
            ArtifactDocument.project_id == project_id,
            ArtifactDocument.artifact_type == ARTIFACT_TYPE,
        ))
    ).scalar_one_or_none()
    if doc is None:
        return {"document": None, "suites": [], "messages": [], "sources": []}

    suites = await _current_tc_rows_for("test_suites", doc.id, db)
    plans = await _current_tc_rows_for("test_plans", doc.id, db)
    cases = await _current_tc_rows_for("test_cases", doc.id, db)

    trace_rows = (
        await db.execute(select(TestCaseTraceability).where(TestCaseTraceability.document_id == doc.id))
    ).scalars().all()
    traceability = [{
        "id": str(t.id), "source_table": t.source_table, "source_row_key": t.source_row_key,
        "target_kind": t.target_kind, "target_ref": t.target_ref,
        "target_label": t.target_label or "", "confidence": t.confidence or "high",
    } for t in trace_rows]

    trace_by_source: dict[str, list[dict]] = {}
    for t in traceability:
        trace_by_source.setdefault(t["source_row_key"], []).append(t)

    cases_by_plan: dict[str, list[dict]] = {}
    for c in cases:
        c["traceability"] = trace_by_source.get(c["row_key"], [])
        cases_by_plan.setdefault(c["plan_row_key"], []).append(c)

    plans_by_suite: dict[str, list[dict]] = {}
    for p in plans:
        p["cases"] = sorted(cases_by_plan.get(p["row_key"], []), key=lambda x: x["row_key"])
        p["traceability"] = trace_by_source.get(p["row_key"], [])
        plans_by_suite.setdefault(p["suite_row_key"], []).append(p)

    suites_hydrated = []
    for s in suites:
        s["plans"] = sorted(plans_by_suite.get(s["row_key"], []), key=lambda x: x["row_key"])
        suites_hydrated.append(s)

    messages = (
        await db.execute(select(ArtifactMessage).where(ArtifactMessage.document_id == doc.id).order_by(ArtifactMessage.seq))
    ).scalars().all()
    sources = (
        await db.execute(select(ArtifactSource).where(ArtifactSource.artifact_document_id == doc.id))
    ).scalars().all()

    return {
        "document": {
            "id": str(doc.id), "project_id": str(doc.project_id),
            "artifact_type": doc.artifact_type, "status": doc.status,
            "unit_status": doc.unit_status or {},
            "validated_at": doc.validated_at.isoformat() if doc.validated_at else None,
            "validated_by": str(doc.validated_by) if doc.validated_by else None,
            "validated_snapshot_key": doc.validated_snapshot_key,
            "created_at": doc.created_at.isoformat(),
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
        },
        "suites": sorted(suites_hydrated, key=lambda x: x["row_key"]),
        "messages": [{
            "id": str(m.id), "seq": m.seq, "role": m.role, "content": m.content,
            "citations": m.citations or [], "meta": m.meta or {}, "created_at": m.created_at.isoformat(),
        } for m in messages],
        "sources": [{
            "id": str(s.id),
            "source_document_id": str(s.source_document_id) if s.source_document_id else None,
            "included": s.included,
        } for s in sources],
    }


async def reset_tc_generating(project_id: uuid.UUID, db: AsyncSession) -> ArtifactDocument:
    doc = await _ensure_tc_document(project_id, db)
    if doc.status == "generating":
        doc.status = "in_interview"
        doc.unit_status = {**(doc.unit_status or {}), "_current_unit": None}
    return doc


# ═══════════════════════════════════════════════════════════════════════════════
# Gap-fill — author cases ONLY for currently-uncovered FRS elements (append-only)
# ═══════════════════════════════════════════════════════════════════════════════


def _tc_num(row_key: str) -> int:
    if "-TC-" in row_key:
        try:
            return int(row_key.rsplit("-TC-", 1)[1])
        except ValueError:
            return 0
    return 0


async def _covered_frs_keys(document_id: uuid.UUID, db: AsyncSession) -> tuple[set[str], set[str]]:
    """Return (covered FRS element row_keys, spec keys whose independent_test is covered)."""
    covered: set[str] = set()
    e2e_specs: set[str] = set()
    active_keys: set[str] = set()
    for c in await _current_tc_rows_for("test_cases", document_id, db):
        active_keys.add(c["row_key"])
        for k in (c.get("scenario_refs") or []):
            covered.add(k)
        for k in (c.get("fr_refs") or []):
            covered.add(k)
        for k in (c.get("br_refs") or []):
            covered.add(k)
        if c.get("source_ref"):
            covered.add(c["source_ref"])
        if c.get("test_type") == "e2e" or c.get("source_kind") == "independent_test":
            e2e_specs.add(c.get("spec_row_key"))
    # Only count traceability from ACTIVE cases — a deleted case's lingering trace
    # rows must not keep an element looking "covered".
    rows = (
        await db.execute(select(
            TestCaseTraceability.source_row_key, TestCaseTraceability.target_ref,
        ).where(
            TestCaseTraceability.document_id == document_id,
            TestCaseTraceability.source_table == "test_cases",
            TestCaseTraceability.target_kind.in_((
                "frs_acceptance_scenario", "frs_functional_requirement",
                "frs_business_rule", "frs_screen",
            )),
        ))
    ).all()
    for src, ref in rows:
        if src in active_keys:
            covered.add(ref)
    return covered, e2e_specs


def _spec_gaps(spec: dict, idx: dict, covered: set[str], e2e_specs: set[str]) -> tuple[dict, int]:
    """Uncovered elements for one spec + total count."""
    skey = spec["row_key"]
    scenarios = [
        {"row_key": x["row_key"], "given": x.get("given", ""), "when": x.get("when", ""),
         "then": x.get("then", ""), "is_negative": x.get("is_negative", False),
         "fr_refs": x.get("fr_refs", []) or []}
        for x in idx["scenarios"].get(skey, []) if x["row_key"] not in covered
    ]
    frs = [
        {"row_key": x["row_key"], "fr_id": x.get("fr_id", ""), "requirement_text": x.get("requirement_text", "")}
        for x in idx["frs"].get(skey, []) if x["row_key"] not in covered
    ]
    rules = [
        {"row_key": x["row_key"], "rule_id": x.get("rule_id", ""), "description": x.get("description", "")}
        for x in idx["rules"].get(skey, []) if x["row_key"] not in covered
    ]
    screens = [
        {"row_key": x["row_key"], "screen_name": x.get("screen_name", "")}
        for x in idx["screens"].get(skey, []) if x["row_key"] not in covered
    ]
    indep = spec.get("independent_test", "") if (spec.get("independent_test") and skey not in e2e_specs) else ""
    gaps = {"scenarios": scenarios, "functional_requirements": frs, "business_rules": rules, "screens": screens}
    if indep:
        gaps["independent_test"] = indep
    total = len(scenarios) + len(frs) + len(rules) + len(screens) + (1 if indep else 0)
    return gaps, total


async def gap_fill_tc(
    project: Project, db: AsyncSession, *, spec_row_key: str | None = None,
    max_parallel_specs: int | None = None,
) -> dict:
    """Author cases ONLY for uncovered FRS elements and APPEND them (existing cases
    untouched). spec_row_key=None fills every spec with gaps; else just that spec."""
    from app.services.skills.dspy_test_cases import run_gap_fill

    max_parallel_specs = max_parallel_specs or _default_parallel_specs()
    doc = await _ensure_tc_document(project.id, db)
    bundle = await gather_project_context(project.id, db, artifact_document_id=doc.id, artifact_type=ARTIFACT_TYPE)
    frs = bundle.frs
    if frs is None:
        return await get_tc_detail(project.id, db)
    idx = _index_frs(frs)
    covered, e2e_specs = await _covered_frs_keys(doc.id, db)

    targets = []
    for s in frs.specs:
        if spec_row_key is not None and s["row_key"] != spec_row_key:
            continue
        gaps, total = _spec_gaps(s, idx, covered, e2e_specs)
        if total > 0:
            targets.append((s, gaps))
    if not targets:
        return await get_tc_detail(project.id, db)

    doc.status = "generating"
    await db.commit()
    sem = asyncio.Semaphore(max_parallel_specs)

    async def _fill(s: dict, gaps: dict) -> None:
        from app.db import AsyncSessionLocal
        skey = s["row_key"]
        mkey = s.get("module_row_key", "")
        plan_key = f"TP-{skey}"
        target_spec = _build_target_spec(frs, idx, s)
        async with sem:
            async with AsyncSessionLocal() as udb:
                await _set_nested_status(doc.id, [plan_key, "status"], "authoring", udb)
                await udb.commit()
                try:
                    existing = [c for c in await _current_tc_rows_for("test_cases", doc.id, udb)
                                if c.get("plan_row_key") == plan_key]
                    start = 1 + max([_tc_num(c["row_key"]) for c in existing] + [0])
                    res = await run_gap_fill(
                        project_name=project.name, spec_row_key=skey, plan_row_key=plan_key,
                        module_row_key=mkey, target_spec=json.dumps(target_spec),
                        gaps=json.dumps(gaps),
                        brd_context=_focused_brd(bundle, target_spec.get("br_refs") or []),
                        app_brain=bundle.apps.formatted_context,
                    )
                    res = _sanitize_refs(_strip_nul(res), target_spec)
                    cases = res.get("test_cases", [])
                    remap: dict[str, str] = {}
                    for i, c in enumerate(cases):
                        new_rk = f"{plan_key}-TC-{start + i:03d}"
                        remap[c.get("row_key")] = new_rk
                        c["row_key"] = new_rk
                        c["plan_row_key"] = plan_key
                        c["spec_row_key"] = skey
                        c["module_row_key"] = mkey
                    await upsert_tc_rows("test_cases", doc.id, cases, "ai", udb, scope_keys=set())
                    grouped: dict[str, list[dict]] = {}
                    for t in res.get("traceability", []):
                        src = remap.get(t.get("source_row_key"), t.get("source_row_key"))
                        grouped.setdefault(src, []).append({**t, "source_row_key": src})
                    for src, rows in grouped.items():
                        await _upsert_tc_traceability(doc.id, "test_cases", src, rows, udb)
                    await _set_nested_status(doc.id, [plan_key, "status"], "done", udb)
                    await udb.commit()
                except Exception:
                    log.exception("tc.gap_fill.failed", extra={"doc_id": str(doc.id), "spec": skey})
                    await udb.rollback()

    await asyncio.gather(*[_fill(s, g) for s, g in targets])
    await db.refresh(doc)
    doc.status = "in_interview"
    doc.unit_status = {**(doc.unit_status or {}), "_current_unit": None}
    await db.commit()
    return await get_tc_detail(project.id, db)
