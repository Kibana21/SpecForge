"""FRS validation checklist.

Stage A (modularize) rules (THIS FILE):
- Critical: zero_modules, module_zero_backlog, cross_module_cycle
- Major: module_tech_name (capability-language enforcement)
- Coverage: br_uncovered_in_modules (Must-priority BRs)
- Warnings: module_under_decomposed, module_over_loaded, open_module_decision,
  nfr_arch_docs_absent, interface_asymmetry

Stage B rules (added when Stage B ships) cover:
- Figma link missing on UI specs
- <6 acceptance scenarios or <2 negatives
- FR with no scenario / scenario with no FR
- depends_on cycles, depends_on missing
- BR with no FRS trace

Returns findings sorted: critical → major → minor → coverage → warnings.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import ArtifactDocument
from app.models.brd import BrdBusinessRequirement
from app.models.frs import (
    FrsAcceptanceScenario, FrsFunctionalRequirement,
    FrsModule, FrsModuleInterface, FrsScreen, FrsSpec, FrsSpecDecision,
    FrsTraceability,
)

# Severity sort order (lower = higher priority)
_GROUP_ORDER = {"critical": 0, "major": 1, "minor": 2, "coverage": 3, "warnings": 4}

# Capability-language enforcement: any of these tokens in a module name → finding
_TECH_TOKENS: set[str] = {
    "api", "db", "service", "lambda", "kafka", "postgres", "redis",
    "microservice", "gateway", "mongodb", "dynamodb", "queue", "stream",
    "function", "handler", "worker", "daemon", "endpoint", "schema",
}


def _finding(
    check_id: str,
    description: str,
    group: str,
    row_key: str | None = None,
    suggested_fix: str = "",
    target_ref: str | None = None,
) -> dict:
    return {
        "check_id": check_id,
        "description": description,
        "group": group,
        "row_key": row_key,
        "suggested_fix": suggested_fix,
        "target_ref": target_ref,
    }


async def _active_rows(model: type, document_id: uuid.UUID, db: AsyncSession) -> list[Any]:
    return (
        await db.execute(
            select(model).where(
                model.document_id == document_id,
                model.is_current.is_(True),
                model.status == "active",
            )
        )
    ).scalars().all()


def _detect_cross_module_cycle(interfaces: list[Any]) -> list[str] | None:
    """Build a directed graph of inter-module dependencies (outbound interfaces)
    and detect cycles via DFS. Returns the cycle path or None."""
    graph: dict[str, set[str]] = {}
    for iface in interfaces:
        if iface.direction == "outbound" and iface.counterpart:
            graph.setdefault(iface.module_row_key, set()).add(iface.counterpart)

    visited: dict[str, str] = {}  # WHITE (absent) / GREY / BLACK
    path: list[str] = []

    def _dfs(node: str) -> list[str] | None:
        if visited.get(node) == "GREY":
            # Back-edge → cycle
            idx = path.index(node) if node in path else 0
            return path[idx:] + [node]
        if visited.get(node) == "BLACK":
            return None
        visited[node] = "GREY"
        path.append(node)
        for neighbor in graph.get(node, set()):
            cycle = _dfs(neighbor)
            if cycle:
                return cycle
        path.pop()
        visited[node] = "BLACK"
        return None

    for n in list(graph.keys()):
        if visited.get(n) != "BLACK":
            cycle = _dfs(n)
            if cycle:
                return cycle
    return None


async def _must_br_row_keys(project_id: uuid.UUID, db: AsyncSession) -> set[str]:
    """Return the set of Must-priority BR row_keys from the validated BRD."""
    brd_doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == "brd",
            )
        )
    ).scalar_one_or_none()
    if brd_doc is None:
        return set()
    rows = (
        await db.execute(
            select(BrdBusinessRequirement.row_key).where(
                BrdBusinessRequirement.document_id == brd_doc.id,
                BrdBusinessRequirement.is_current.is_(True),
                BrdBusinessRequirement.status == "active",
                BrdBusinessRequirement.priority == "must",
            )
        )
    ).scalars().all()
    return set(rows)


async def run_frs_validation(
    document_id: uuid.UUID,
    doc: ArtifactDocument,
    db: AsyncSession,
) -> list[dict]:
    """Run Stage-A validation checks. Returns findings sorted by severity."""
    findings: list[dict] = []

    modules = await _active_rows(FrsModule, document_id, db)
    specs = await _active_rows(FrsSpec, document_id, db)
    interfaces = await _active_rows(FrsModuleInterface, document_id, db)
    decisions = await _active_rows(FrsSpecDecision, document_id, db)

    # ── CRITICAL ────────────────────────────────────────────────────────────

    if len(modules) == 0:
        findings.append(_finding(
            check_id="zero_modules",
            description="No modules generated. Stage A must produce ≥1 module before Stage B can run.",
            group="critical",
            suggested_fix="Re-run modularize. If still empty, check that BRD is validated and discover Q&A is sufficient.",
        ))

    # Per-module: must have ≥1 backlog stub
    specs_by_module: dict[str, list] = {}
    for s in specs:
        specs_by_module.setdefault(s.module_row_key, []).append(s)
    for m in modules:
        stub_count = len(specs_by_module.get(m.row_key, []))
        if stub_count == 0:
            findings.append(_finding(
                check_id="module_zero_backlog",
                description=f"Module {m.row_key} '{m.name}' has zero FRS backlog stubs. Cannot proceed to Stage B.",
                group="critical",
                row_key=m.row_key,
                suggested_fix="Re-run modularize for this module, or manually add at least one FRS stub.",
            ))

    # Cross-module cycle detection
    cycle = _detect_cross_module_cycle(interfaces)
    if cycle:
        findings.append(_finding(
            check_id="cross_module_cycle",
            description=f"Cyclic dependency between modules detected: {' → '.join(cycle)}",
            group="critical",
            suggested_fix="Decouple via async events or extract shared logic into a Cross-cutting Standards module.",
        ))

    # ── MAJOR ───────────────────────────────────────────────────────────────

    # Capability-language enforcement
    for m in modules:
        name_lower = m.name.lower()
        # Match whole words to reduce false positives (e.g. 'database' shouldn't trip 'db')
        for tok in _TECH_TOKENS:
            # Word-boundary-ish check: token is either a separate word or at start/end
            words = set(name_lower.replace("-", " ").split())
            if tok in words:
                findings.append(_finding(
                    check_id="module_tech_name",
                    description=(
                        f"Module '{m.name}' uses tech-specific language "
                        f"('{tok}'). Use capability/role names instead."
                    ),
                    group="major",
                    row_key=m.row_key,
                    suggested_fix=(
                        f"Rename to a business capability (e.g., 'Authentication' "
                        f"not 'Auth API'). Edit the module's name field to fix."
                    ),
                ))
                break

    # ── COVERAGE ────────────────────────────────────────────────────────────

    # Every Must-priority BR must be referenced by at least one backlog stub
    must_brs = await _must_br_row_keys(doc.project_id, db)
    if must_brs:
        covered_brs: set[str] = set()
        for s in specs:
            for br_key in (s.br_refs or []):
                covered_brs.add(br_key)
        uncovered = must_brs - covered_brs
        for br_key in sorted(uncovered):
            findings.append(_finding(
                check_id="br_uncovered_in_modules",
                description=(
                    f"BR {br_key} (priority='must') is not referenced by any "
                    f"FRS backlog stub. Stage B cannot cover it."
                ),
                group="coverage",
                target_ref=br_key,
                suggested_fix=(
                    "Re-run modularize with an explicit hint, or manually add a "
                    "stub referencing this BR."
                ),
            ))

    # ── WARNINGS ────────────────────────────────────────────────────────────

    # Under/over-decomposed modules
    for m in modules:
        stub_count = len(specs_by_module.get(m.row_key, []))
        if stub_count == 1:
            findings.append(_finding(
                check_id="module_under_decomposed",
                description=(
                    f"Module {m.row_key} '{m.name}' has only 1 backlog stub. "
                    "May indicate under-decomposition or that it should merge "
                    "into another module."
                ),
                group="warnings",
                row_key=m.row_key,
                suggested_fix=(
                    "Consider merging this module into a related one, or expanding "
                    "its backlog."
                ),
            ))
        elif stub_count > 15:
            findings.append(_finding(
                check_id="module_over_loaded",
                description=(
                    f"Module {m.row_key} '{m.name}' has {stub_count} stubs "
                    "(>15). May indicate over-loading; consider splitting."
                ),
                group="warnings",
                row_key=m.row_key,
                suggested_fix=(
                    "Consider splitting by sub-capability or lifecycle stage."
                ),
            ))

    # Open decisions (module-scoped only — spec-scoped are Stage B)
    for d in decisions:
        if d.spec_row_key is not None:
            continue  # spec-scoped, defer to Stage B
        if d.resolution_status == "open":
            findings.append(_finding(
                check_id="open_module_decision",
                description=(
                    f"Decision {d.row_key} is unresolved. AI recommends option "
                    f"{d.recommended_index}. Open question: {d.question[:80]}…"
                ),
                group="warnings",
                row_key=d.row_key,
                suggested_fix="Confirm AI's recommendation or override via the Decision panel.",
            ))

    # Interface symmetry warning: every outbound API/event should have a matching inbound
    by_module = {m.row_key: m for m in modules}
    for iface in interfaces:
        if iface.direction != "outbound" or not iface.counterpart:
            continue
        if iface.interface_kind == "ui_surface":
            continue
        # Look for matching inbound on the counterpart module (by name + transport)
        target_module = by_module.get(iface.counterpart)
        if target_module is None:
            # Counterpart isn't a module in this FRS (could be external system)
            continue
        matched = any(
            i.module_row_key == iface.counterpart
            and i.direction == "inbound"
            and i.name == iface.name
            for i in interfaces
        )
        if not matched:
            findings.append(_finding(
                check_id="interface_asymmetry",
                description=(
                    f"Module {iface.module_row_key} has outbound interface "
                    f"'{iface.name}' → {iface.counterpart}, but {iface.counterpart} "
                    f"has no matching inbound interface."
                ),
                group="warnings",
                row_key=f"{iface.module_row_key}/{iface.name}",
                suggested_fix=(
                    f"Add an inbound interface '{iface.name}' on module "
                    f"{iface.counterpart} (or re-run modularize)."
                ),
            ))

    # Stage B rules (only fire on specs that have been designed)
    findings.extend(await _validate_stage_b(document_id, doc, db, modules, specs, interfaces))

    # Sort: critical → major → minor → coverage → warnings
    findings.sort(key=lambda f: _GROUP_ORDER.get(f["group"], 99))
    return findings


# ─── Stage B validation ──────────────────────────────────────────────────────


async def _validate_stage_b(
    document_id: uuid.UUID,
    doc: ArtifactDocument,
    db: AsyncSession,
    modules: list[Any],
    specs: list[Any],
    interfaces: list[Any],
) -> list[dict]:
    """14 Stage B checks. Only fires on specs that have been designed
    (completeness > 0); pure stubs from Stage A are ignored.
    """
    findings: list[dict] = []

    designed_specs = [s for s in specs if (s.completeness or 0) > 0]
    if not designed_specs:
        return findings  # Stage B hasn't run yet

    # Index helpers
    specs_by_module: dict[str, list] = {}
    for s in specs:
        specs_by_module.setdefault(s.module_row_key, []).append(s)
    all_spec_keys = {s.row_key for s in specs}

    # Pull Stage B sub-rows
    scenarios = await _active_rows(FrsAcceptanceScenario, document_id, db)
    frs_list = await _active_rows(FrsFunctionalRequirement, document_id, db)
    screens = await _active_rows(FrsScreen, document_id, db)
    decisions_all = await _active_rows(FrsSpecDecision, document_id, db)

    scenarios_by_spec: dict[str, list] = {}
    for sc in scenarios:
        scenarios_by_spec.setdefault(sc.spec_row_key, []).append(sc)
    frs_by_spec: dict[str, list] = {}
    for fr in frs_list:
        frs_by_spec.setdefault(fr.spec_row_key, []).append(fr)
    screens_by_spec: dict[str, list] = {}
    for sc in screens:
        screens_by_spec.setdefault(sc.spec_row_key, []).append(sc)

    # Traceability — for spec_no_br_trace + br_uncovered_in_frs
    traceability = (
        await db.execute(
            select(FrsTraceability).where(FrsTraceability.document_id == document_id)
        )
    ).scalars().all()
    spec_br_traces: dict[str, set[str]] = {}
    for t in traceability:
        if t.target_kind == "brd_business_requirement":
            spec_br_traces.setdefault(t.source_row_key, set()).add(t.target_ref)

    # ── CRITICAL ────────────────────────────────────────────────────────────

    # module_empty — a module with backlog stubs but 0 designed specs
    # (Stage A `module_zero_backlog` covers truly empty modules; this catches the
    # "designed = 0 of N" case.)
    for m in modules:
        mod_specs = specs_by_module.get(m.row_key, [])
        if not mod_specs:
            continue  # Stage A's `module_zero_backlog` already flagged
        mod_designed = [s for s in mod_specs if (s.completeness or 0) > 0]
        if mod_designed:
            continue  # at least one spec designed → not empty
        # All stubs in this module are still stubs (Stage B failed for module)
        # Only flag if SOME specs in document have been designed (else Stage B
        # just hasn't started for this module yet — not a defect)
        # The outer designed_specs guard already confirmed Stage B has run somewhere
        findings.append(_finding(
            check_id="module_empty",
            description=(
                f"Module {m.row_key} '{m.name}' has {len(mod_specs)} backlog "
                f"stub(s) but Stage B has produced 0 designed specs."
            ),
            group="critical",
            row_key=m.row_key,
            suggested_fix=f"Re-run design_module for {m.row_key}.",
        ))

    # depends_on_cycle — cyclic depends_on graph
    if _has_depends_on_cycle(designed_specs):
        findings.append(_finding(
            check_id="depends_on_cycle",
            description="Cyclic depends_on graph among FRS specs.",
            group="critical",
            suggested_fix=(
                "Restructure dependencies; consider extracting shared logic into "
                "a Cross-cutting Standards FRS."
            ),
        ))

    # ── MAJOR — per-spec rules ──────────────────────────────────────────────

    for spec in designed_specs:
        # spec_no_br_trace — spec lacks ≥1 BR traceability
        if not spec_br_traces.get(spec.row_key):
            findings.append(_finding(
                check_id="spec_no_br_trace",
                description=(
                    f"FRS {spec.row_key} does not trace to any BR. "
                    "Every spec must trace to ≥1 BR."
                ),
                group="major",
                row_key=spec.row_key,
                suggested_fix=(
                    "Re-run this spec — AI will infer the BR from the module's "
                    "stub br_refs."
                ),
            ))

        # figma_link_missing — module has ui_surface but no real figma_link
        module_has_ui_surface = any(
            i.module_row_key == spec.module_row_key and i.interface_kind == "ui_surface"
            for i in interfaces
        )
        spec_screens = screens_by_spec.get(spec.row_key, [])
        has_real_figma = any(
            s.figma_link and s.figma_link != "__none__" for s in spec_screens
        )
        if module_has_ui_surface and not has_real_figma:
            # Distinguish: skipped (sentinel set) vs truly missing
            had_sentinel = any(s.figma_link == "__none__" for s in spec_screens)
            if not had_sentinel:
                findings.append(_finding(
                    check_id="figma_link_missing",
                    description=(
                        f"FRS {spec.row_key} module has UI surfaces but no Figma "
                        "link has been provided."
                    ),
                    group="major",
                    row_key=spec.row_key,
                    suggested_fix=(
                        "Provide a Figma URL via the [Add Figma link] prompt, or "
                        "click 'Skip — UI design TBD'."
                    ),
                ))

        # too_few_scenarios + too_few_negative_scenarios
        spec_scenarios = scenarios_by_spec.get(spec.row_key, [])
        if len(spec_scenarios) < 6:
            findings.append(_finding(
                check_id="too_few_scenarios",
                description=(
                    f"FRS {spec.row_key} has {len(spec_scenarios)} acceptance "
                    "scenarios (need ≥6)."
                ),
                group="major",
                row_key=spec.row_key,
                suggested_fix="Re-run this spec; AI will add scenarios.",
            ))
        negative_count = sum(1 for sc in spec_scenarios if sc.is_negative)
        if negative_count < 2:
            findings.append(_finding(
                check_id="too_few_negative_scenarios",
                description=(
                    f"FRS {spec.row_key} has {negative_count} negative scenarios "
                    "(need ≥2)."
                ),
                group="major",
                row_key=spec.row_key,
                suggested_fix="Re-run this spec; AI will add failure/error cases.",
            ))

        # FR ↔ scenario coverage (bidirectional)
        spec_frs = frs_by_spec.get(spec.row_key, [])
        scenario_keys = {sc.row_key for sc in spec_scenarios}
        fr_keys = {fr.row_key for fr in spec_frs}
        for fr in spec_frs:
            if not any(ref in scenario_keys for ref in (fr.scenario_refs or [])):
                findings.append(_finding(
                    check_id="fr_no_scenario",
                    description=(
                        f"FR {fr.row_key} ('{fr.fr_id}') references no acceptance "
                        "scenario."
                    ),
                    group="major",
                    row_key=fr.row_key,
                    suggested_fix=(
                        f"Add scenario_refs to FR {fr.fr_id} or re-run spec."
                    ),
                ))
        for sc in spec_scenarios:
            if not any(ref in fr_keys for ref in (sc.fr_refs or [])):
                findings.append(_finding(
                    check_id="scenario_no_fr",
                    description=(
                        f"Acceptance scenario {sc.row_key} (#{sc.scenario_index}) "
                        "references no FR."
                    ),
                    group="major",
                    row_key=sc.row_key,
                    suggested_fix="Add fr_refs to this scenario or re-run spec.",
                ))

        # depends_on_missing — spec lists a depends_on row_key that doesn't exist
        for dep in (spec.depends_on or []):
            if dep not in all_spec_keys:
                findings.append(_finding(
                    check_id="depends_on_missing",
                    description=(
                        f"FRS {spec.row_key} depends on {dep}, which does not exist."
                    ),
                    group="major",
                    row_key=spec.row_key,
                    suggested_fix=f"Either remove the dependency or create FRS {dep}.",
                ))

    # ── MINOR ───────────────────────────────────────────────────────────────

    for spec in designed_specs:
        if spec.completeness < 90:
            findings.append(_finding(
                check_id="spec_completeness",
                description=(
                    f"FRS {spec.row_key} completeness {spec.completeness}%."
                ),
                group="minor",
                row_key=spec.row_key,
                suggested_fix=(
                    "Review the AI's notes in narrative or open_questions; "
                    "address gaps and re-run."
                ),
            ))

    # ── COVERAGE ────────────────────────────────────────────────────────────

    # br_uncovered_in_frs — every Must-priority BR must be traced from ≥1 FRS
    must_brs = await _must_br_row_keys(doc.project_id, db)
    if must_brs:
        covered_brs: set[str] = set()
        for traced_brs in spec_br_traces.values():
            covered_brs.update(traced_brs)
        for br_key in sorted(must_brs - covered_brs):
            findings.append(_finding(
                check_id="br_uncovered_in_frs",
                description=(
                    f"BR {br_key} (priority='must') is not traced from any FRS."
                ),
                group="coverage",
                target_ref=br_key,
                suggested_fix=(
                    "Add the BR to a backlog stub via [Edit module backlog] and "
                    "re-run that spec."
                ),
            ))

    # ── WARNINGS ────────────────────────────────────────────────────────────

    # open_spec_decision — every spec-scoped decision with status='open'
    for d in decisions_all:
        if d.spec_row_key is None:
            continue  # module-scoped covered in Stage A rules
        if d.resolution_status == "open":
            findings.append(_finding(
                check_id="open_spec_decision",
                description=(
                    f"Spec decision {d.row_key} is open. AI recommends option "
                    f"{d.recommended_index}: {d.question[:80]}…"
                ),
                group="warnings",
                row_key=d.row_key,
                suggested_fix="Resolve via the Decision panel.",
            ))

    # figma_link_skipped — informational
    for spec in designed_specs:
        spec_screens = screens_by_spec.get(spec.row_key, [])
        if any(s.figma_link == "__none__" for s in spec_screens):
            findings.append(_finding(
                check_id="figma_link_skipped",
                description=(
                    f"FRS {spec.row_key} has UI specs marked 'TBD' via the "
                    "figma-skip sentinel."
                ),
                group="warnings",
                row_key=spec.row_key,
                suggested_fix=(
                    "Provide a real Figma URL when design is ready, then this "
                    "spec will be re-authored."
                ),
            ))

    return findings


def _has_depends_on_cycle(specs: list[Any]) -> bool:
    """DFS cycle detector on the depends_on graph. Local copy of the
    orchestrator helper to avoid an import cycle (validators → orchestrator).
    """
    graph: dict[str, set[str]] = {
        s.row_key: set(s.depends_on or []) for s in specs
    }
    WHITE, GREY, BLACK = 0, 1, 2
    color: dict[str, int] = {k: WHITE for k in graph}

    def _dfs(n: str) -> bool:
        c = color.get(n, BLACK)
        if c == GREY:
            return True
        if c == BLACK:
            return False
        color[n] = GREY
        for nb in graph.get(n, set()):
            if nb in color and _dfs(nb):
                return True
        color[n] = BLACK
        return False

    return any(_dfs(n) for n in list(graph) if color[n] == WHITE)


def summarize_findings(findings: list[dict]) -> dict:
    """Return a count summary for the findings drawer header."""
    out = {"total": len(findings), "critical": 0, "major": 0, "minor": 0,
           "coverage": 0, "warnings": 0, "blocking": 0}
    for f in findings:
        g = f["group"]
        if g in out:
            out[g] += 1
        if g in ("critical", "major"):
            out["blocking"] += 1
    return out
