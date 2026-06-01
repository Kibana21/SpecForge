"""Test Cases validation checklist.

Findings groups (sorted critical → major → minor → coverage → warnings):
- CRITICAL (block): zero_plans, plan_zero_cases (P0/P1 spec impl. must-BR),
  must_br_untested
- MAJOR (block): scenario_uncovered, fr_uncovered, no_negative_test, orphan_case,
  case_no_trace, responsive_no_viewports, case_not_rich
- MINOR: business_rule_uncovered, plan_completeness, independent_test_uncovered,
  missing_observability_assertion
- COVERAGE (non-block): uncovered scenario/FR on P2/P3 spec
- WARNINGS: screen_no_responsive

blocking = critical + major.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import ArtifactDocument

_GROUP_ORDER = {"critical": 0, "major": 1, "minor": 2, "coverage": 3, "warnings": 4}


def _finding(check_id: str, description: str, group: str,
             row_key: str | None = None, suggested_fix: str = "",
             target_ref: str | None = None) -> dict:
    return {"check_id": check_id, "description": description, "group": group,
            "row_key": row_key, "suggested_fix": suggested_fix, "target_ref": target_ref}


def summarize_findings(findings: list[dict]) -> dict:
    out = {"total": len(findings), "critical": 0, "major": 0, "minor": 0,
           "coverage": 0, "warnings": 0, "blocking": 0}
    for f in findings:
        g = f["group"]
        if g in out:
            out[g] += 1
        if g in ("critical", "major"):
            out["blocking"] += 1
    return out


async def run_tc_validation(document_id: uuid.UUID, doc: ArtifactDocument, db: AsyncSession) -> list[dict]:
    """Run test-case validation. Returns findings sorted by severity."""
    from app.models.test_cases import TestCase, TestPlan
    from app.services.context.tc_coverage import build_tc_coverage

    findings: list[dict] = []

    plans = (
        await db.execute(select(TestPlan).where(
            TestPlan.document_id == document_id, TestPlan.is_current.is_(True), TestPlan.status == "active",
        ))
    ).scalars().all()
    cases = (
        await db.execute(select(TestCase).where(
            TestCase.document_id == document_id, TestCase.is_current.is_(True), TestCase.status == "active",
        ))
    ).scalars().all()

    # ── CRITICAL ──────────────────────────────────────────────────────────────
    if not plans:
        findings.append(_finding("zero_plans", "No test plans exist. Generate test cases first.", "critical"))
        return _sort(findings)

    cases_by_plan: dict[str, list] = {}
    for c in cases:
        cases_by_plan.setdefault(c.plan_row_key, []).append(c)

    project_id = (
        await db.execute(select(ArtifactDocument.project_id).where(ArtifactDocument.id == document_id))
    ).scalar_one()
    coverage = await build_tc_coverage(project_id, db)

    spec_pct = {}
    spec_negok = {}
    for m in coverage["modules"]:
        for s in m["specs"]:
            spec_pct[s["spec_row_key"]] = s["pct"]
            spec_negok[s["spec_row_key"]] = s["negative_ok"]

    # Build active FRS element row_key set for orphan detection
    active_frs_keys = await _active_frs_keys(project_id, db)

    # plan_zero_cases — critical only when the plan was authored elsewhere; we treat
    # any plan with 0 cases as authored-incomplete → critical for P0/P1, else coverage.
    for p in plans:
        n = len(cases_by_plan.get(p.row_key, []))
        if n == 0:
            grp = "critical" if p.priority in ("P0", "P1") else "coverage"
            findings.append(_finding("plan_zero_cases",
                f"Plan {p.row_key} ({p.priority}) has no test cases.", grp,
                row_key=p.row_key, suggested_fix="Author or regenerate this plan."))

    # must_br_untested (multi-hop chain)
    for entry in coverage["brd_chain"]:
        if not entry["tested"]:
            findings.append(_finding("must_br_untested",
                f"Must-priority {entry['br_row_key']} is not fully tested: {entry['reason']}.",
                "critical", row_key=entry["br_row_key"], target_ref=entry["br_row_key"]))

    # ── MAJOR / COVERAGE — uncovered FRS elements ─────────────────────────────
    for m in coverage["modules"]:
        for s in m["specs"]:
            low_priority = s["priority"] in ("P2", "P3")
            for el in s["elements"]:
                if el["covered_by"]:
                    continue
                kind = el["kind"]
                if kind == "acceptance_scenario":
                    grp = "coverage" if low_priority else "major"
                    findings.append(_finding("scenario_uncovered",
                        f"Acceptance scenario {el['frs_row_key']} has no test case.", grp,
                        row_key=s["spec_row_key"], target_ref=el["frs_row_key"]))
                elif kind == "functional_requirement":
                    grp = "coverage" if low_priority else "major"
                    findings.append(_finding("fr_uncovered",
                        f"Functional requirement {el['frs_row_key']} has no test case.", grp,
                        row_key=s["spec_row_key"], target_ref=el["frs_row_key"]))
                elif kind == "business_rule":
                    findings.append(_finding("business_rule_uncovered",
                        f"Business rule {el['frs_row_key']} has no test case.", "minor",
                        row_key=s["spec_row_key"], target_ref=el["frs_row_key"]))
                elif kind == "screen":
                    findings.append(_finding("screen_no_responsive",
                        f"Screen {el['frs_row_key']} has no responsive test.", "warnings",
                        row_key=s["spec_row_key"], target_ref=el["frs_row_key"]))
                elif kind == "independent_test":
                    findings.append(_finding("independent_test_uncovered",
                        f"Spec {s['spec_row_key']} independent test has no e2e case.", "minor",
                        row_key=s["spec_row_key"]))
            # no_negative_test
            if not spec_negok.get(s["spec_row_key"], True):
                findings.append(_finding("no_negative_test",
                    f"Spec {s['spec_row_key']} has negative scenarios but no negative test case.",
                    "major", row_key=s["spec_row_key"]))

    # ── per-case checks ────────────────────────────────────────────────────────
    trace_sources = await _trace_source_keys(document_id, db)
    for c in cases:
        # case_no_trace
        refs = (c.scenario_refs or []) + (c.fr_refs or []) + (c.br_refs or [])
        if c.row_key not in trace_sources and not refs:
            findings.append(_finding("case_no_trace",
                f"Test case {c.row_key} has no traceability link to any FRS element.",
                "major", row_key=c.row_key))
        # orphan_case — refs point to a non-active FRS row
        for k in refs:
            if k not in active_frs_keys:
                findings.append(_finding("orphan_case",
                    f"Test case {c.row_key} references {k}, which no longer exists in the FRS.",
                    "major", row_key=c.row_key, target_ref=k))
                break
        # responsive_no_viewports
        if c.test_type == "responsive" and not (c.viewports or []):
            findings.append(_finding("responsive_no_viewports",
                f"Responsive test case {c.row_key} has no viewports.", "major", row_key=c.row_key))
        # case_not_rich — a case is "rich" when it has ≥2 concrete assertions AND a
        # specific expected_result. (We deliberately do NOT keyword-match negative
        # cases for words like "reject"/"error": real negative assertions phrase the
        # failure many ways — "denied/blocked", "does not crash", "alarm fires", a
        # specific error string — and a substring gate flags all of those as false
        # positives, which can never be cleared no matter how good the test is.)
        not_rich = (len(c.key_assertions or []) < 2) or not (c.expected_result or "").strip()
        if not_rich:
            findings.append(_finding("case_not_rich",
                f"Test case {c.row_key} is not rich enough (needs ≥2 concrete assertions "
                f"and a specific expected result).",
                "major", row_key=c.row_key))

    # plan completeness (minor)
    for p in plans:
        if (p.completeness or 0) < 90 and cases_by_plan.get(p.row_key):
            findings.append(_finding("plan_completeness",
                f"Plan {p.row_key} completeness is {p.completeness}% (<90%).", "minor", row_key=p.row_key))

    return _sort(findings)


def _sort(findings: list[dict]) -> list[dict]:
    return sorted(findings, key=lambda f: _GROUP_ORDER.get(f["group"], 9))


async def _active_frs_keys(project_id: uuid.UUID, db: AsyncSession) -> set[str]:
    from app.models.frs import (
        FrsAcceptanceScenario, FrsBusinessRule, FrsFunctionalRequirement, FrsScreen,
    )
    frs_doc = (
        await db.execute(select(ArtifactDocument).where(
            ArtifactDocument.project_id == project_id, ArtifactDocument.artifact_type == "frs",
        ))
    ).scalar_one_or_none()
    if frs_doc is None:
        return set()
    keys: set[str] = set()
    for model in (FrsAcceptanceScenario, FrsFunctionalRequirement, FrsBusinessRule, FrsScreen):
        rows = (
            await db.execute(select(model.row_key).where(
                model.document_id == frs_doc.id, model.is_current.is_(True), model.status == "active",
            ))
        ).scalars().all()
        keys.update(rows)
    return keys


async def _trace_source_keys(document_id: uuid.UUID, db: AsyncSession) -> set[str]:
    from app.models.test_cases import TestCaseTraceability
    rows = (
        await db.execute(select(TestCaseTraceability.source_row_key).where(
            TestCaseTraceability.document_id == document_id,
            TestCaseTraceability.source_table == "test_cases",
        ))
    ).scalars().all()
    return set(rows)
