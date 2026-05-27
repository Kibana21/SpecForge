"""BRD validation checklist: run_brd_validation returns findings sorted by severity."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import ArtifactDocument
from app.models.brd import (
    BrdBusinessRequirement, BrdKpi, BrdObjective, BrdRisk,
    BrdTextBlock, BrdTraceability,
)
from app.services.artifacts.manifest.brd import BRD_MANIFEST_BY_KEY
from app.services.context.coverage import BRD_CONTEXT_PROJECTION, compute_coverage

# Severity sort order (lower = higher priority)
_GROUP_ORDER = {"critical": 0, "major": 1, "minor": 2, "coverage": 3, "warnings": 4}

# Tables that must have ≥1 active row (critical)
_CRITICAL_TABLES: list[tuple[str, type, str]] = [
    ("brd_text_blocks",           BrdTextBlock,            "Business context/problem text blocks"),
    ("brd_objectives",            BrdObjective,            "Strategic objectives"),
    ("brd_business_requirements", BrdBusinessRequirement,  "Business requirements"),
    ("brd_risks",                 BrdRisk,                 "Risks"),
    ("brd_kpis",                  BrdKpi,                  "KPIs"),
]

# Units whose writes map to row-count keys used by compute_coverage
# Maps coverage unit_key → table(s) it populates
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


def _finding(
    check_id: str,
    description: str,
    group: str,
    row_key: str | None = None,
    suggested_fix: str = "",
) -> dict:
    return {
        "check_id": check_id,
        "description": description,
        "group": group,
        "row_key": row_key,
        "suggested_fix": suggested_fix,
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


async def run_brd_validation(
    document_id: uuid.UUID,
    doc: ArtifactDocument,
    db: AsyncSession,
) -> list[dict]:
    """Run all BRD validation checks. Returns findings sorted by severity."""
    findings: list[dict] = []

    # ── CRITICAL: required tables must have ≥1 active row ─────────────────────
    for table_name, model, label in _CRITICAL_TABLES:
        count = await db.scalar(
            select(func.count(model.id)).where(
                model.document_id == document_id,
                model.is_current.is_(True),
                model.status == "active",
            )
        ) or 0
        if count == 0:
            findings.append(_finding(
                check_id=f"required_{table_name}",
                description=f"Required section is empty: {label} ({table_name})",
                group="critical",
                row_key=None,
                suggested_fix=f"Generate or manually populate {table_name} before validating.",
            ))

    # ── MAJOR: BR quality checks ───────────────────────────────────────────────
    br_rows = await _active_rows(BrdBusinessRequirement, document_id, db)
    obj_rows = await _active_rows(BrdObjective, document_id, db)
    kpi_rows = await _active_rows(BrdKpi, document_id, db)
    risk_rows = await _active_rows(BrdRisk, document_id, db)

    # All traced row keys (source_row_key → count)
    trace_rows = (
        await db.execute(
            select(BrdTraceability).where(BrdTraceability.document_id == document_id)
        )
    ).scalars().all()
    traced_keys: set[str] = {t.source_row_key for t in trace_rows}

    for br in br_rows:
        row_key = br.row_key

        # AC quality for "must" BRs
        if br.priority == "must":
            ac = br.acceptance_criteria or []
            # acceptance_criteria is stored as list[dict] with given/when/then
            valid_ac = [
                c for c in ac
                if isinstance(c, dict) and c.get("given") and c.get("when") and c.get("then")
            ]
            if len(valid_ac) < 2:
                findings.append(_finding(
                    check_id="br_must_have_ac",
                    description=(
                        f"BR {row_key} has priority='must' but only {len(valid_ac)} "
                        "valid Given-When-Then acceptance criteria (need ≥2)."
                    ),
                    group="major",
                    row_key=row_key,
                    suggested_fix="Add at least 2 Given-When-Then acceptance criteria to this BR.",
                ))

        # objective_refs
        obj_refs = br.objective_refs or []
        if not obj_refs:
            findings.append(_finding(
                check_id="br_objective_ref",
                description=f"BR {row_key} has no objective_refs — every BR must reference ≥1 objective.",
                group="major",
                row_key=row_key,
                suggested_fix="Link this BR to at least one BRD objective (OBJ-xxx row_key).",
            ))

        # stakeholder_refs
        stk_refs = br.stakeholder_refs or []
        if not stk_refs:
            findings.append(_finding(
                check_id="br_stakeholder_ref",
                description=f"BR {row_key} has no stakeholder_refs — every BR must reference ≥1 stakeholder.",
                group="major",
                row_key=row_key,
                suggested_fix="Link this BR to at least one BRD stakeholder (STK-xxx row_key).",
            ))

        # outward traceability
        if row_key not in traced_keys:
            findings.append(_finding(
                check_id="outward_traceability",
                description=f"BR {row_key} has no entry in brd_traceability — every BR must have ≥1 outward trace.",
                group="major",
                row_key=row_key,
                suggested_fix="Regenerate the business_requirements unit to produce traceability entries.",
            ))

    # KPI completeness
    for kpi in kpi_rows:
        row_key = kpi.row_key
        missing: list[str] = []
        if not (kpi.baseline and str(kpi.baseline).strip()):
            missing.append("baseline")
        if not (kpi.target and str(kpi.target).strip()):
            missing.append("target")
        if not (kpi.timeframe and str(kpi.timeframe).strip()):
            missing.append("timeframe")
        if missing:
            findings.append(_finding(
                check_id="kpi_baseline_target" if "baseline" in missing or "target" in missing else "kpi_timeframe",
                description=f"KPI {row_key} is missing required fields: {', '.join(missing)}.",
                group="major",
                row_key=row_key,
                suggested_fix=f"Populate {', '.join(missing)} for this KPI.",
            ))
        # outward traceability
        if row_key not in traced_keys:
            findings.append(_finding(
                check_id="outward_traceability",
                description=f"KPI {row_key} has no entry in brd_traceability — every KPI must have ≥1 outward trace.",
                group="major",
                row_key=row_key,
                suggested_fix="Regenerate the kpis unit to produce traceability entries.",
            ))

    # Objective outward traceability
    for obj in obj_rows:
        row_key = obj.row_key
        if row_key not in traced_keys:
            findings.append(_finding(
                check_id="outward_traceability",
                description=f"Objective {row_key} has no entry in brd_traceability.",
                group="major",
                row_key=row_key,
                suggested_fix="Regenerate the objectives unit to produce traceability entries.",
            ))

    # Risk mitigation + outward traceability
    for risk in risk_rows:
        row_key = risk.row_key
        if not (risk.mitigation and str(risk.mitigation).strip()):
            findings.append(_finding(
                check_id="risk_mitigation",
                description=f"Risk {row_key} has an empty mitigation field — every risk must have a mitigation strategy.",
                group="major",
                row_key=row_key,
                suggested_fix="Add a non-empty mitigation strategy to this risk.",
            ))
        if row_key not in traced_keys:
            findings.append(_finding(
                check_id="outward_traceability",
                description=f"Risk {row_key} has no entry in brd_traceability.",
                group="major",
                row_key=row_key,
                suggested_fix="Regenerate the risks unit to produce traceability entries.",
            ))

    # ── MINOR: unit completeness < 90 ─────────────────────────────────────────
    unit_status: dict = doc.unit_status or {}
    for unit_key, status_val in unit_status.items():
        if unit_key.startswith("_"):
            continue
        if not isinstance(status_val, dict):
            continue
        completeness = status_val.get("completeness", 0)
        if completeness < 90:
            findings.append(_finding(
                check_id="unit_completeness",
                description=(
                    f"Unit '{unit_key}' has completeness={completeness}% (threshold: 90%). "
                    "The AI rated this section as incomplete."
                ),
                group="minor",
                row_key=None,
                suggested_fix=f"Review and enrich the {unit_key} section, then regenerate.",
            ))

    # ── COVERAGE: CB element coverage ─────────────────────────────────────────
    # Build unit_row_counts: map unit_key → number of rows it generated
    # We approximate this by counting rows in each unit's target table(s).
    from app.services.artifacts.brd_orchestrator import BRD_TABLE_MAP
    # Count active rows per table
    table_counts: dict[str, int] = {}
    for table_name, model in BRD_TABLE_MAP.items():
        cnt = await db.scalar(
            select(func.count(model.id)).where(
                model.document_id == document_id,
                model.is_current.is_(True),
                model.status == "active",
            )
        ) or 0
        table_counts[table_name] = cnt

    # Map unit → max rows across its tables
    unit_row_counts: dict[str, int] = {}
    for unit_key, tables in _UNIT_TABLE_MAP.items():
        unit_row_counts[unit_key] = max(
            (table_counts.get(t, 0) for t in tables), default=0
        )

    coverage = compute_coverage(unit_row_counts)
    if not coverage.all_covered:
        for key in coverage.uncovered_keys:
            brd_units = BRD_CONTEXT_PROJECTION.get(key, [])
            findings.append(_finding(
                check_id="cb_coverage",
                description=(
                    f"CB element '{key}' is not consumed: "
                    f"units {brd_units} have no rows."
                ),
                group="coverage",
                row_key=None,
                suggested_fix=(
                    f"Generate the following units to cover this CB element: "
                    f"{', '.join(brd_units)}."
                ),
            ))

    # ── WARNINGS: orphan trace refs ────────────────────────────────────────────
    # Collect all current active row_keys across BRD tables
    all_current_row_keys: set[str] = set()
    for table_name, model in BRD_TABLE_MAP.items():
        rkeys = (
            await db.execute(
                select(model.row_key).where(
                    model.document_id == document_id,
                    model.is_current.is_(True),
                    model.status == "active",
                )
            )
        ).scalars().all()
        all_current_row_keys.update(rkeys)

    for t in trace_rows:
        if t.source_row_key not in all_current_row_keys:
            findings.append(_finding(
                check_id="orphan_traces",
                description=(
                    f"Traceability row points to source_row_key='{t.source_row_key}' "
                    "which no longer exists as an active row."
                ),
                group="warnings",
                row_key=t.source_row_key,
                suggested_fix="Regenerate the relevant BRD units to refresh traceability.",
            ))

    # Sort: critical → major → minor → coverage → warnings
    findings.sort(key=lambda f: _GROUP_ORDER.get(f["group"], 99))
    return findings
