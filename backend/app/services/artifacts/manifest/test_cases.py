"""Test Cases generation manifest: 2 phases, table maps, editable columns.

Stage A — plan_journeys (single DSPy call). Lays out a test_suite per validated
FRS module and a test_plan stub per FRS spec (with coverage_targets).

Stage B — author_plan (dynamic, one DSPy call per FRS spec). Authors the actual
test_cases + traceability for each plan. Orchestrated parallel-per-module,
sequential-per-spec.

Mirrors the FRS manifest pattern (manifest/frs.py) with test-cases tables.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class TcUnitSpec:
    unit_key: str
    phase: Literal["A", "B"]
    label: str
    writes: list[str]                       # table names this unit owns
    depends_on: list[str]                   # unit_keys that must run first
    unit_instruction: str
    discover_question_keys: list[str] = field(default_factory=list)
    timeout_seconds: int = 120


# ── Stage A unit: plan_journeys ────────────────────────────────────────────────

TC_STAGE_A_UNIT = TcUnitSpec(
    unit_key="plan_journeys",
    phase="A",
    label="Plan test journeys per module",
    writes=["test_suites", "test_plans"],   # plan stubs, completeness=0
    depends_on=[],
    unit_instruction=(
        "Lay out a test_suite per FRS module (user-journey overview + strategy + "
        "outcomes_summary) and a test_plan STUB per FRS spec (no cases yet). Each "
        "plan stub carries coverage_targets = the row_keys of every acceptance "
        "scenario, functional requirement, business rule, and screen it must cover. "
        "row_keys: suites TS-{module_row_key}; plans TP-{spec_row_key}. Preserve "
        "existing keys; reproduce locked rows verbatim."
    ),
    discover_question_keys=[],
    timeout_seconds=120,
)


# ── Stage B unit: author_plan (per-spec; dynamic) ──────────────────────────────

TC_STAGE_B_UNIT = TcUnitSpec(
    unit_key="author_plan",
    phase="B",
    label="Author test cases for one FRS spec",
    writes=["test_plans", "test_cases", "test_case_traceability"],
    depends_on=["plan_journeys"],
    unit_instruction=(
        "Author COMPREHENSIVE multi-level test cases for ONE FRS spec. Cover every "
        "acceptance scenario (negative type for is_negative), every functional "
        "requirement, every business rule, the independent test (e2e), and every "
        "screen (responsive). ≥1 negative case. Each case is rich: ≥2 outcome-level "
        "assertions in FRS language, a specific expected_result, test_data for "
        "data-dependent cases, expected_observability where the spec defines it. "
        "Set fr_refs/scenario_refs/br_refs + emit traceability to each FRS element; "
        "emit a plan→frs_spec trace and transitive plan→brd_business_requirement "
        "traces. Reproduce locked cases verbatim."
    ),
    discover_question_keys=[],
    timeout_seconds=360,
)


TC_MANIFEST: list[TcUnitSpec] = [TC_STAGE_A_UNIT, TC_STAGE_B_UNIT]
TC_MANIFEST_BY_KEY: dict[str, TcUnitSpec] = {u.unit_key: u for u in TC_MANIFEST}


# ── Table→model mapping (for upsert routing + queries) ────────────────────────

from app.models.test_cases import (  # noqa: E402
    TestSuite, TestPlan, TestCase, TestCaseTraceability,
)

TC_TABLE_MAP: dict[str, type] = {
    "test_suites": TestSuite,
    "test_plans":  TestPlan,
    "test_cases":  TestCase,
    # test_case_traceability has bespoke replace-all handling — not in upsert path
}


# ── Per-table editable column whitelist (for versioned upsert) ────────────────
#
# Excludes versioning columns (id, document_id, row_key, version, is_current,
# is_locked, status, source, created_by, created_at).

TC_TYPED_COLS: dict[str, list[str]] = {
    "test_suites": [
        "module_row_key", "title", "journey_overview", "test_strategy",
        "outcomes_summary", "completeness", "confidence",
    ],
    "test_plans": [
        "suite_row_key", "spec_row_key", "module_row_key", "title",
        "preconditions", "test_data_notes", "coverage_targets",
        "outcomes_summary", "priority", "summary", "completeness", "confidence",
    ],
    "test_cases": [
        "plan_row_key", "spec_row_key", "module_row_key", "title", "test_type",
        "source_kind", "source_ref", "given", "when", "then", "steps",
        "preconditions", "key_assertions", "test_data", "expected_result",
        "expected_observability", "viewports", "auth_required", "auth_role",
        "priority", "fr_refs", "scenario_refs", "br_refs",
    ],
}


# ── Integer-type columns (for type coercion on LLM string→int) ────────────────

TC_INT_COLS: dict[str, set[str]] = {
    "test_suites": {"completeness"},
    "test_plans":  {"completeness"},
}
