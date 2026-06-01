"""FRS layer: all validated FRS rows + traceability, for Test-Case generation.

Populated only for test-case generation (artifact_type='test_cases'). The
readiness check enforces frs_status == 'validated'. The formatted_context is the
per-corpus projection; the orchestrator additionally builds a per-spec context
pack (full spec + its sub-rows) for each Stage B author_plan call.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.context.project_context import FrsLayer


async def build_frs_layer(project_id: uuid.UUID, db: AsyncSession) -> FrsLayer:
    """Load the full validated FRS corpus for a project.

    Returns an empty FrsLayer (frs_status=None) when no FRS exists. Callers use
    BundleReadiness to enforce validation status.
    """
    from app.models.artifact import ArtifactDocument
    from app.models.frs import (
        FrsModule, FrsModuleActor, FrsSpec, FrsScreen, FrsUiComponent,
        FrsEndpoint, FrsDataEntity, FrsBusinessRule, FrsAcceptanceScenario,
        FrsFunctionalRequirement, FrsTraceability,
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
        return FrsLayer(
            frs_document_id=None, frs_status=None,
            frs_validated_at=None, frs_snapshot_key=None,
            modules=[], specs=[], acceptance_scenarios=[],
            functional_requirements=[], business_rules=[], screens=[],
            ui_components=[], endpoints=[], data_entities=[], module_actors=[],
            traceability=[], formatted_context="(no FRS found)",
        )

    async def _load(model, cols: list[str]) -> list[dict]:
        rows = (
            await db.execute(
                select(model).where(
                    model.document_id == doc.id,
                    model.is_current.is_(True),
                    model.status == "active",
                )
            )
        ).scalars().all()
        return [
            {"row_key": r.row_key, **{c: getattr(r, c) for c in cols}}
            for r in rows
        ]

    modules = await _load(FrsModule, ["name", "slug", "layer", "scope_in", "scope_out", "summary"])
    module_actors = await _load(FrsModuleActor, ["module_row_key", "actor_name", "relationship", "notes"])
    specs = await _load(FrsSpec, [
        "module_row_key", "title", "priority", "layer", "br_refs", "nfr_refs",
        "depends_on", "narrative", "independent_test", "data_and_validation",
        "errors_and_edge_cases", "observability",
    ])
    scenarios = await _load(FrsAcceptanceScenario, [
        "spec_row_key", "scenario_index", "given", "when", "then", "is_negative", "fr_refs",
    ])
    frs = await _load(FrsFunctionalRequirement, ["spec_row_key", "fr_id", "requirement_text", "scenario_refs"])
    rules = await _load(FrsBusinessRule, ["spec_row_key", "rule_id", "description", "applies_to", "logic_decision"])
    screens = await _load(FrsScreen, ["spec_row_key", "screen_name", "purpose", "user_roles", "layout", "navigation", "interactive_behavior"])
    ui_components = await _load(FrsUiComponent, ["spec_row_key", "screen_row_key", "component_name", "component_type", "validation", "behavior", "actions"])
    endpoints = await _load(FrsEndpoint, ["spec_row_key", "endpoint_name", "method", "url", "request_spec", "response_spec", "error_handling", "security"])
    data_entities = await _load(FrsDataEntity, ["spec_row_key", "entity_name", "description", "columns", "keys_constraints", "relationships"])

    traces = (
        await db.execute(select(FrsTraceability).where(FrsTraceability.document_id == doc.id))
    ).scalars().all()
    trace_dicts = [{
        "source_table": t.source_table,
        "source_row_key": t.source_row_key,
        "target_kind": t.target_kind,
        "target_ref": t.target_ref,
        "target_label": t.target_label,
        "confidence": t.confidence,
    } for t in traces]

    formatted = _format_frs_context(modules, specs, scenarios, frs, rules, screens)

    return FrsLayer(
        frs_document_id=str(doc.id),
        frs_status=doc.status,
        frs_validated_at=doc.validated_at.isoformat() if doc.validated_at else None,
        frs_snapshot_key=doc.validated_snapshot_key,
        modules=modules, specs=specs, acceptance_scenarios=scenarios,
        functional_requirements=frs, business_rules=rules, screens=screens,
        ui_components=ui_components, endpoints=endpoints, data_entities=data_entities,
        module_actors=module_actors, traceability=trace_dicts,
        formatted_context=formatted,
    )


def _format_frs_context(modules, specs, scenarios, frs, rules, screens) -> str:
    """Render the validated FRS as a compact prompt-ready string.

    Used for Stage A (plan_journeys) which needs a project-wide view of every
    module + spec to lay out the test suites and plan stubs.
    """
    lines: list[str] = ["=== Validated FRS ===\n"]

    specs_by_mod: dict[str, list] = {}
    for s in specs:
        specs_by_mod.setdefault(s["module_row_key"], []).append(s)
    scen_by_spec: dict[str, list] = {}
    for sc in scenarios:
        scen_by_spec.setdefault(sc["spec_row_key"], []).append(sc)
    fr_by_spec: dict[str, list] = {}
    for f in frs:
        fr_by_spec.setdefault(f["spec_row_key"], []).append(f)
    rule_by_spec: dict[str, list] = {}
    for r in rules:
        rule_by_spec.setdefault(r["spec_row_key"], []).append(r)
    screen_by_spec: dict[str, list] = {}
    for sc in screens:
        screen_by_spec.setdefault(sc["spec_row_key"], []).append(sc)

    for m in modules:
        lines.append(f"\n## Module [{m['row_key']}] {m['name']} ({m['layer']})")
        if m.get("summary"):
            lines.append(f"  {m['summary']}")
        for s in specs_by_mod.get(m["row_key"], []):
            br_refs = ", ".join(s.get("br_refs") or [])
            lines.append(f"\n  ### Spec [{s['row_key']}] ({s['priority']}) {s['title']} — BRs: {br_refs or '—'}")
            mod_scen = scen_by_spec.get(s["row_key"], [])
            mod_fr = fr_by_spec.get(s["row_key"], [])
            mod_rule = rule_by_spec.get(s["row_key"], [])
            mod_screen = screen_by_spec.get(s["row_key"], [])
            neg = sum(1 for x in mod_scen if x.get("is_negative"))
            lines.append(
                f"    coverage targets → {len(mod_scen)} scenarios ({neg} negative), "
                f"{len(mod_fr)} FRs, {len(mod_rule)} business rules, {len(mod_screen)} screens"
            )
            if s.get("independent_test"):
                lines.append(f"    Independent test: {s['independent_test'][:160]}")

    return "\n".join(lines)
