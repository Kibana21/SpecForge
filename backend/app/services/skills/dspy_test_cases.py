"""DSPy modules for Test Cases generation — 2 units.

Stage A — plan_journeys: one DSPy call lays out a test_suite per FRS module and a
  test_plan stub per FRS spec (with coverage_targets).
Stage B — author_plan: one DSPy call PER FRS SPEC authors the actual test_cases +
  traceability (comprehensive multi-level: functional/integration/e2e/negative/
  edge_case/responsive).

Pattern follows dspy_frs.py: Pydantic output model + typed Signature +
ChainOfThought Module + async runner (mock → deterministic synthesis from the
real FRS row_keys so coverage is exercised; real → Gemini).
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Literal

import dspy
from pydantic import BaseModel, Field, model_validator

log = logging.getLogger(__name__)

_FIXTURE_DIR = Path(__file__).parent.parent / "llm" / "fixtures"


def _configure() -> None:
    from app.services.skills.fact_extractor.dspy_extractor import _configure_dspy
    _configure_dspy()


_TC_LM = None


def _get_tc_lm():
    """Dedicated LM for test-case generation with the model's 'thinking' pass
    disabled (≈half the per-spec latency; same output). Scoped via dspy.context so
    it never changes the global LM that BRD/FRS use. Built once per process."""
    global _TC_LM
    if _TC_LM is None:
        from app.config import get_settings
        from app.core.google_credentials import configure_google_genai_env
        configure_google_genai_env()
        s = get_settings()
        extra = {}
        if s.tc_reasoning_effort:
            extra["reasoning_effort"] = s.tc_reasoning_effort
        _TC_LM = dspy.LM(
            f"vertex_ai/{s.gemini_model}", max_tokens=s.tc_max_tokens, cache=False,
            vertex_location=s.gemini_location, vertex_project=s.gemini_project_id or None,
            **extra,
        )
    return _TC_LM


_TC_LM_HQ = None


def _get_tc_lm_hq():
    """High-quality LM for the repair pass: full reasoning budget + bigger output
    cap so re-authored cases come out rich. Built once per process, scoped via
    dspy.context so it never touches the fast bulk-generation LM."""
    global _TC_LM_HQ
    if _TC_LM_HQ is None:
        from app.config import get_settings
        from app.core.google_credentials import configure_google_genai_env
        configure_google_genai_env()
        s = get_settings()
        extra = {}
        if s.tc_reasoning_effort_high:
            extra["reasoning_effort"] = s.tc_reasoning_effort_high
        _TC_LM_HQ = dspy.LM(
            f"vertex_ai/{s.gemini_model}", max_tokens=s.tc_max_tokens_high, cache=False,
            vertex_location=s.gemini_location, vertex_project=s.gemini_project_id or None,
            **extra,
        )
    return _TC_LM_HQ


def _is_mock() -> bool:
    from app.config import get_settings
    return get_settings().llm_provider == "mock"


def _load_fixture(name: str) -> dict:
    path = _FIXTURE_DIR / f"{name}.json"
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


# ── Common output models ────────────────────────────────────────────────────────

class TcOpenQuestion(BaseModel):
    question: str
    context: str = ""


class TcTraceRow(BaseModel):
    source_table: Literal["test_cases", "test_plans", "test_suites"]
    source_row_key: str
    target_kind: Literal[
        "frs_spec", "frs_acceptance_scenario", "frs_functional_requirement",
        "frs_business_rule", "frs_screen", "brd_business_requirement",
        "within_test_cases",
    ]
    target_ref: str
    target_label: str = ""
    confidence: Literal["high", "medium", "low"] = "high"


class TcObservabilityItem(BaseModel):
    kind: Literal["log", "metric", "trace", "audit"]
    signal: str
    assertion: str


class TcStep(BaseModel):
    step: str
    expected: str = ""


class TcCaseRow(BaseModel):
    row_key: str = Field(description="{plan_row_key}-TC-NNN, zero-padded")
    title: str
    test_type: Literal["functional", "integration", "e2e", "negative", "edge_case", "responsive"]
    source_kind: Literal[
        "acceptance_scenario", "functional_requirement", "business_rule",
        "independent_test", "screen", "manual",
    ] = "acceptance_scenario"
    source_ref: str | None = None
    given: str = ""
    when: str = ""
    then: str = ""
    steps: list[TcStep] = Field(default_factory=list)
    preconditions: str = ""
    key_assertions: list[str] = Field(
        ..., min_length=2,
        description="≥2 concrete, outcome-level assertions in FRS language",
    )
    test_data: dict[str, Any] = Field(default_factory=dict)
    expected_result: str = Field(description="Specific observable outcome; never 'works correctly'")
    expected_observability: list[TcObservabilityItem] = Field(default_factory=list)
    viewports: list[str] = Field(default_factory=list)
    auth_required: bool = False
    auth_role: str | None = None
    priority: Literal["P0", "P1", "P2", "P3"] = "P1"
    fr_refs: list[str] = Field(default_factory=list)
    scenario_refs: list[str] = Field(default_factory=list)
    br_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_richness(self):
        if self.test_type == "responsive" and not self.viewports:
            raise ValueError("responsive test_type requires non-empty viewports")
        if not (self.expected_result or "").strip():
            raise ValueError("expected_result must be specific and non-empty")
        return self


class TcPlanFull(BaseModel):
    row_key: str = Field(description="TP-{spec_row_key}")
    suite_row_key: str
    spec_row_key: str
    module_row_key: str
    title: str
    preconditions: str = ""
    test_data_notes: str = ""
    outcomes_summary: str = Field(description="What this plan proves (1–3 sentences)")
    priority: Literal["P0", "P1", "P2", "P3"] = "P1"
    summary: str = ""
    completeness: int = Field(ge=0, le=100, default=100)
    confidence: Literal["high", "medium", "low"] = "medium"


class TcAuthorPlanOutput(BaseModel):
    plan: TcPlanFull
    test_cases: list[TcCaseRow] = Field(..., min_length=1)
    traceability: list[TcTraceRow] = Field(default_factory=list)
    open_questions: list[TcOpenQuestion] = Field(default_factory=list)


# ── Stage A output models ────────────────────────────────────────────────────────

class TcSuiteRow(BaseModel):
    row_key: str = Field(description="TS-{module_row_key}")
    module_row_key: str
    title: str
    journey_overview: str = Field(description="actor → goal → steps framing")
    test_strategy: str = ""
    outcomes_summary: str = ""
    completeness: int = Field(ge=0, le=100, default=100)
    confidence: Literal["high", "medium", "low"] = "medium"


class TcPlanStub(BaseModel):
    row_key: str = Field(description="TP-{spec_row_key}")
    suite_row_key: str
    spec_row_key: str
    module_row_key: str
    title: str
    preconditions: str = ""
    test_data_notes: str = ""
    coverage_targets: dict[str, Any] = Field(
        default_factory=dict,
        description="{scenarios:[...], frs:[...], business_rules:[...], screens:[...]}",
    )
    outcomes_summary: str = ""
    priority: Literal["P0", "P1", "P2", "P3"] = "P1"
    summary: str = ""
    completeness: int = Field(ge=0, le=100, default=0)
    confidence: Literal["high", "medium", "low"] = "medium"


class TcPlanJourneysOutput(BaseModel):
    suites: list[TcSuiteRow] = Field(default_factory=list)
    plans: list[TcPlanStub] = Field(default_factory=list)
    open_questions: list[TcOpenQuestion] = Field(default_factory=list)


# ── Stage A — plan_journeys signature ─────────────────────────────────────────

class TcPlanJourneysSignature(dspy.Signature):
    """Lay out the test SUITE per FRS module and a test PLAN stub per FRS spec.

    LANGUAGE: Write all text (titles, journey_overview, test_strategy, summaries)
    in clear professional ENGLISH. Never switch languages.

    You are a senior QA Architect. Read the validated FRS (all modules + specs) and
    produce, for each module, ONE test_suite with a user-journey overview (actor →
    goal → steps), a test_strategy (which test_types apply + why), and an
    outcomes_summary (what the journey proves). For each FRS spec, produce ONE
    test_plan STUB (no test cases yet — Stage B authors those) with:
    - row_key TP-{spec_row_key}, suite_row_key TS-{module_row_key}
    - priority carried from the spec's priority
    - coverage_targets: the row_keys of every acceptance_scenario, functional_
      requirement, business_rule and screen the plan must cover (use modules_json /
      specs_json verbatim — never invent keys)

    Preserve row_keys present in current_plans; reproduce locked rows verbatim.
    """
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    frs_context: str = dspy.InputField(desc="Validated FRS: every module + spec, formatted")
    brd_context: str = dspy.InputField(desc="Validated BRD for outcome framing")
    cb_context: str = dspy.InputField(desc="Validated Concept Brief")
    app_brain: str = dspy.InputField(desc="In-scope application facts")
    source_sections: str = dspy.InputField(desc="Depth-searched project doc sections")
    qa_pairs: str = dspy.InputField(desc="Discover Q&A; '' if none")
    modules_json: str = dspy.InputField(desc="JSON of FRS modules (row_key, name, layer)")
    specs_json: str = dspy.InputField(
        desc="JSON of FRS specs incl. each spec's scenario/fr/business_rule/screen row_keys"
    )
    current_plans: str = dspy.InputField(desc="JSON of existing suites+plans for idempotent regen; '{}'")
    locked_plans: str = dspy.InputField(desc="JSON of locked rows to reproduce verbatim; '[]'")
    result: TcPlanJourneysOutput = dspy.OutputField()


class TcPlanJourneysModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.Predict(TcPlanJourneysSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


# ── Stage B — author_plan signature ───────────────────────────────────────────

class TcAuthorPlanSignature(dspy.Signature):
    """Author COMPREHENSIVE multi-level test cases for ONE FRS spec.

    LANGUAGE: Write EVERY field — titles, given/when/then, steps, key_assertions,
    expected_result, expected_observability, summaries — in clear professional
    ENGLISH. Never switch to another language, regardless of any wording in the
    inputs.

    You are a senior QA Architect. For the single spec in `target_spec` (JSON: full
    spec text + its acceptance_scenarios, functional_requirements, business_rules,
    screens, endpoints, data_entities, actors, observability), author a FOCUSED,
    high-value set of test_cases. Be concise — do not pad. Coverage rules:
    - EVERY acceptance_scenario → exactly 1 case (negative test_type for
      is_negative=True). Set fr_refs to the FRs that scenario validates so those
      FRs are covered WITHOUT a separate per-FR case.
    - functional_requirements: only add a dedicated case for an FR that no
      scenario already references (otherwise it is already covered).
    - business_rules: add an edge_case ONLY for rules not already exercised by a
      scenario.
    - independent_test → exactly 1 e2e case.
    - screens → ONE representative responsive case for the primary screen (not one
      per screen).
    ≥1 negative case overall. Aim for roughly one case per acceptance_scenario
    plus the e2e + responsive — typically 6–12 cases, not dozens.

    Each case MUST be RICH:
    - ≥2 concrete key_assertions in FRS language (exact labels/messages/values),
      phrased as observable business outcomes (not just HTTP status)
    - a specific expected_result (never "works correctly")
    - test_data (setup + inputs + boundary values) for data-dependent cases
    - expected_observability tied to the spec's observability section where defined
    - set fr_refs / scenario_refs / br_refs to the FRS row_keys it validates, and
      emit a test_case_traceability row to each (target_kind frs_acceptance_scenario
      / frs_functional_requirement / frs_business_rule / frs_screen)

    Also: emit ONE plan→frs_spec trace and copy the spec's br_refs as
    plan→brd_business_requirement traces (transitive rollup). Write the plan's
    outcomes_summary ("what this plan proves").

    row_key conventions: cases {plan_row_key}-TC-NNN (zero-padded). Reproduce locked
    cases (in current_plan) verbatim. Use FRS language; do NOT invent behavior the
    FRS is silent on — emit an open_question instead.
    """
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    target_spec_row_key: str = dspy.InputField()
    plan_row_key: str = dspy.InputField()
    suite_row_key: str = dspy.InputField()
    module_row_key: str = dspy.InputField()
    target_spec: str = dspy.InputField(desc="JSON: full FRS spec + all its sub-rows")
    module_context: str = dspy.InputField(desc="JSON: module scope, actors, interfaces")
    sibling_plans_summary: str = dspy.InputField(desc="JSON list of other plans in this module")
    brd_context: str = dspy.InputField(desc="Validated BRD for outcome framing")
    cb_context: str = dspy.InputField(desc="Validated Concept Brief")
    app_brain: str = dspy.InputField(desc="In-scope application facts")
    nfr_context: str = dspy.InputField(desc="NFR drivers (perf/security thresholds); '' if none")
    source_sections: str = dspy.InputField(desc="Depth-searched project doc sections")
    qa_pairs: str = dspy.InputField(desc="Discover Q&A; '' if none")
    current_plan: str = dspy.InputField(desc="JSON of existing cases for idempotent regen; '{}'")
    result: TcAuthorPlanOutput = dspy.OutputField()


class TcAuthorPlanModule(dspy.Module):
    def __init__(self, quality: str = "fast") -> None:
        super().__init__()
        # fast  → Predict (no reasoning pass): the FRS spec is already fully
        #         specified, so extra reasoning tokens mostly add latency.
        # high  → ChainOfThought: reasons through each case before emitting, which
        #         is what produces rich assertions + a concrete expected_result.
        #         Used by the repair pass to fix thin cases.
        self.quality = quality
        self.predict = (
            dspy.ChainOfThought(TcAuthorPlanSignature) if quality == "high"
            else dspy.Predict(TcAuthorPlanSignature)
        )

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


# ── Runners ────────────────────────────────────────────────────────────────────

async def run_plan_journeys(**kwargs) -> dict:
    """Stage A. Mock synthesizes suites + plan stubs directly from the FRS rows."""
    if _is_mock():
        return _mock_plan_journeys(kwargs)
    _configure()
    lm = _get_tc_lm()
    loop = asyncio.get_running_loop()

    def _run():
        with dspy.context(lm=lm):
            return TcPlanJourneysModule()(**kwargs)
    fut = loop.run_in_executor(None, _run)
    try:
        return await asyncio.shield(fut)
    except asyncio.CancelledError:
        raise TimeoutError("DSPy TcPlanJourneys timed out")


async def run_author_plan(*, quality: str = "fast", **kwargs) -> dict:
    """Stage B (one spec). Mock synthesizes coverage-complete rich cases.

    quality='high' (repair pass) → full reasoning budget + ChainOfThought, for
    rich cases. quality='fast' (bulk) → thinking-light Predict, for speed.
    """
    if _is_mock():
        return _mock_author_plan(kwargs)
    _configure()
    lm = _get_tc_lm_hq() if quality == "high" else _get_tc_lm()
    loop = asyncio.get_running_loop()

    def _run():
        with dspy.context(lm=lm):
            return TcAuthorPlanModule(quality=quality)(**kwargs)
    fut = loop.run_in_executor(None, _run)
    try:
        return await asyncio.shield(fut)
    except asyncio.CancelledError:
        raise TimeoutError("DSPy TcAuthorPlan timed out")


# ── Mock synthesis (deterministic, coverage-complete) ─────────────────────────

def _mock_plan_journeys(kwargs: dict) -> dict:
    modules = json.loads(kwargs.get("modules_json") or "[]")
    specs = json.loads(kwargs.get("specs_json") or "[]")

    suites = []
    for m in modules:
        mkey = m["row_key"]
        suites.append({
            "row_key": f"TS-{mkey}",
            "module_row_key": mkey,
            "title": f"{m.get('name', mkey)} — test journey",
            "journey_overview": (
                f"As a user of {m.get('name', mkey)}, complete the module's core "
                f"flows end to end and verify each step's observable outcome."
            ),
            "test_strategy": (
                "Functional + negative coverage of every acceptance scenario and "
                "functional requirement; e2e for the independent test; responsive "
                "for each screen; edge cases for business rules."
            ),
            "outcomes_summary": f"Proves the {m.get('name', mkey)} capability behaves per its FRS.",
            "completeness": 100,
            "confidence": "high",
        })

    plans = []
    for s in specs:
        skey = s["row_key"]
        mkey = s.get("module_row_key", "")
        plans.append({
            "row_key": f"TP-{skey}",
            "suite_row_key": f"TS-{mkey}",
            "spec_row_key": skey,
            "module_row_key": mkey,
            "title": f"Test plan — {s.get('title', skey)}",
            "preconditions": "App running; test database seeded; authenticated session available.",
            "test_data_notes": s.get("data_and_validation", "")[:280],
            "coverage_targets": {
                "scenarios": [x["row_key"] for x in s.get("scenarios", [])],
                "frs": [x["row_key"] for x in s.get("functional_requirements", [])],
                "business_rules": [x["row_key"] for x in s.get("business_rules", [])],
                "screens": [x["row_key"] for x in s.get("screens", [])],
            },
            "outcomes_summary": f"Proves {s.get('title', skey)} satisfies its acceptance criteria.",
            "priority": s.get("priority", "P1"),
            "summary": s.get("narrative", "")[:280],
            "completeness": 0,
            "confidence": "high",
        })

    return {"suites": suites, "plans": plans, "open_questions": []}


def _mk_assertions(text: str, negative: bool) -> list[str]:
    base = (text or "the expected outcome").strip().rstrip(".")
    if negative:
        return [
            f"The action is rejected and {base[:120]}",
            "No state change is persisted (system left unchanged)",
        ]
    return [
        f"The system performs the action and {base[:120]}",
        "The resulting state is persisted and observable to the user",
    ]


def _mock_author_plan(kwargs: dict) -> dict:
    spec = json.loads(kwargs.get("target_spec") or "{}")
    plan_key = kwargs.get("plan_row_key", "")
    suite_key = kwargs.get("suite_row_key", "")
    spec_key = spec.get("row_key") or kwargs.get("target_spec_row_key", "")
    module_key = spec.get("module_row_key") or kwargs.get("module_row_key", "")
    priority = spec.get("priority", "P1")
    actors = spec.get("actors") or []
    auth_role = actors[0] if actors else None
    has_obs = bool((spec.get("observability") or "").strip())

    cases: list[dict] = []
    traces: list[dict] = []
    n = 0

    def _next_key() -> str:
        nonlocal n
        n += 1
        return f"{plan_key}-TC-{n:03d}"

    def _obs() -> list[dict]:
        if not has_obs:
            return []
        return [{"kind": "audit", "signal": f"{spec_key}.action", "assertion": "an audit event is recorded with the outcome"}]

    # 1. independent_test → e2e smoke (always TC-001 first)
    indep = (spec.get("independent_test") or "").strip()
    if indep:
        rk = _next_key()
        cases.append({
            "row_key": rk, "title": f"Smoke: {spec.get('title', spec_key)} end to end",
            "test_type": "e2e", "source_kind": "independent_test", "source_ref": spec_key,
            "given": "The system is running with seeded data",
            "when": "The primary user completes the core flow end to end",
            "then": indep[:200],
            "steps": [{"step": "Complete the core flow", "expected": indep[:160] or "the flow succeeds"}],
            "preconditions": "Authenticated session; seeded fixtures.",
            "key_assertions": _mk_assertions(indep, False),
            "test_data": {"setup": ["seeded baseline records"], "inputs": {}, "boundary": []},
            "expected_result": indep[:200] or "The end-to-end flow completes successfully.",
            "expected_observability": _obs(),
            "viewports": [], "auth_required": bool(auth_role), "auth_role": auth_role,
            "priority": priority, "fr_refs": [], "scenario_refs": [], "br_refs": [],
        })
        traces.append({"source_table": "test_cases", "source_row_key": rk,
                        "target_kind": "frs_spec", "target_ref": spec_key,
                        "target_label": spec.get("title", spec_key), "confidence": "high"})

    # 2. one case per acceptance scenario (negative for is_negative)
    for sc in spec.get("scenarios", []):
        rk = _next_key()
        neg = bool(sc.get("is_negative"))
        fr_refs = list(sc.get("fr_refs") or [])
        cases.append({
            "row_key": rk, "title": (("Reject: " if neg else "Verify: ") + (sc.get("when") or sc["row_key"]))[:90],
            "test_type": "negative" if neg else "functional",
            "source_kind": "acceptance_scenario", "source_ref": sc["row_key"],
            "given": sc.get("given", ""), "when": sc.get("when", ""), "then": sc.get("then", ""),
            "steps": [], "preconditions": "Authenticated session.",
            "key_assertions": _mk_assertions(sc.get("then", ""), neg),
            "test_data": {"setup": [], "inputs": {}, "boundary": (["min", "max", "empty"] if neg else [])},
            "expected_result": (sc.get("then") or "The scenario outcome holds.")[:200],
            "expected_observability": _obs(),
            "viewports": [], "auth_required": bool(auth_role), "auth_role": auth_role,
            "priority": priority, "fr_refs": fr_refs, "scenario_refs": [sc["row_key"]], "br_refs": [],
        })
        traces.append({"source_table": "test_cases", "source_row_key": rk,
                        "target_kind": "frs_acceptance_scenario", "target_ref": sc["row_key"],
                        "target_label": "", "confidence": "high"})
        for fr in fr_refs:
            traces.append({"source_table": "test_cases", "source_row_key": rk,
                            "target_kind": "frs_functional_requirement", "target_ref": fr,
                            "target_label": "", "confidence": "high"})

    # 3. one verification case per functional requirement
    for fr in spec.get("functional_requirements", []):
        rk = _next_key()
        cases.append({
            "row_key": rk, "title": f"Requirement {fr.get('fr_id', fr['row_key'])} verification"[:90],
            "test_type": "functional", "source_kind": "functional_requirement", "source_ref": fr["row_key"],
            "given": "A valid context for the requirement",
            "when": "The behavior described by the requirement is exercised",
            "then": (fr.get("requirement_text") or "")[:200],
            "steps": [], "preconditions": "Authenticated session.",
            "key_assertions": _mk_assertions(fr.get("requirement_text", ""), False),
            "test_data": {"setup": [], "inputs": {}, "boundary": []},
            "expected_result": (fr.get("requirement_text") or "The requirement holds.")[:200],
            "expected_observability": _obs(),
            "viewports": [], "auth_required": bool(auth_role), "auth_role": auth_role,
            "priority": priority, "fr_refs": [fr["row_key"]], "scenario_refs": [], "br_refs": [],
        })
        traces.append({"source_table": "test_cases", "source_row_key": rk,
                        "target_kind": "frs_functional_requirement", "target_ref": fr["row_key"],
                        "target_label": fr.get("fr_id", ""), "confidence": "high"})

    # 4. one edge case per business rule
    for br in spec.get("business_rules", []):
        rk = _next_key()
        cases.append({
            "row_key": rk, "title": f"Rule {br.get('rule_id', br['row_key'])} enforcement"[:90],
            "test_type": "edge_case", "source_kind": "business_rule", "source_ref": br["row_key"],
            "given": "Inputs at the rule's boundary",
            "when": "The rule is evaluated",
            "then": (br.get("description") or "")[:200],
            "steps": [], "preconditions": "Authenticated session.",
            "key_assertions": _mk_assertions(br.get("description", ""), True),
            "test_data": {"setup": [], "inputs": {}, "boundary": ["at-limit", "over-limit", "under-limit"]},
            "expected_result": (br.get("description") or "The rule is enforced.")[:200],
            "expected_observability": _obs(),
            "viewports": [], "auth_required": bool(auth_role), "auth_role": auth_role,
            "priority": priority, "fr_refs": [], "scenario_refs": [], "br_refs": [br["row_key"]],
        })
        traces.append({"source_table": "test_cases", "source_row_key": rk,
                        "target_kind": "frs_business_rule", "target_ref": br["row_key"],
                        "target_label": br.get("rule_id", ""), "confidence": "high"})

    # 5. one responsive case per screen
    for scr in spec.get("screens", []):
        rk = _next_key()
        cases.append({
            "row_key": rk, "title": f"{scr.get('screen_name', scr['row_key'])} responsive layout"[:90],
            "test_type": "responsive", "source_kind": "screen", "source_ref": scr["row_key"],
            "given": "The screen is opened on each target viewport",
            "when": "The layout renders",
            "then": "The layout adapts correctly at every breakpoint with no overflow or clipping",
            "steps": [], "preconditions": "Authenticated session.",
            "key_assertions": [
                "All primary controls are reachable and legible at each viewport",
                "No horizontal overflow or clipped content at mobile width",
            ],
            "test_data": {"setup": [], "inputs": {}, "boundary": []},
            "expected_result": "The screen renders correctly across mobile, tablet, and desktop.",
            "expected_observability": [],
            "viewports": ["mobile-360", "tablet-768", "desktop-1440"],
            "auth_required": bool(auth_role), "auth_role": auth_role,
            "priority": priority, "fr_refs": [], "scenario_refs": [], "br_refs": [],
        })
        traces.append({"source_table": "test_cases", "source_row_key": rk,
                        "target_kind": "frs_screen", "target_ref": scr["row_key"],
                        "target_label": scr.get("screen_name", ""), "confidence": "high"})

    # Ensure ≥1 negative case overall
    if not any(c["test_type"] == "negative" for c in cases):
        rk = _next_key()
        cases.append({
            "row_key": rk, "title": "Reject invalid input", "test_type": "negative",
            "source_kind": "manual", "source_ref": None,
            "given": "An invalid or out-of-range input", "when": "The user submits it",
            "then": "The system rejects the input with a clear validation message",
            "steps": [], "preconditions": "Authenticated session.",
            "key_assertions": [
                "A validation error is shown and the action is blocked",
                "No state change is persisted",
            ],
            "test_data": {"setup": [], "inputs": {"value": "<<invalid>>"}, "boundary": ["empty", "over-limit"]},
            "expected_result": "The invalid input is rejected and nothing is persisted.",
            "expected_observability": _obs(),
            "viewports": [], "auth_required": bool(auth_role), "auth_role": auth_role,
            "priority": priority, "fr_refs": [], "scenario_refs": [], "br_refs": [],
        })

    # Plan-level traces: frs_spec + transitive brd_business_requirement
    traces.append({"source_table": "test_plans", "source_row_key": plan_key,
                   "target_kind": "frs_spec", "target_ref": spec_key,
                   "target_label": spec.get("title", spec_key), "confidence": "high"})
    for br in spec.get("br_refs", []):
        traces.append({"source_table": "test_plans", "source_row_key": plan_key,
                       "target_kind": "brd_business_requirement", "target_ref": br,
                       "target_label": "", "confidence": "high"})

    plan = {
        "row_key": plan_key, "suite_row_key": suite_key, "spec_row_key": spec_key,
        "module_row_key": module_key, "title": f"Test plan — {spec.get('title', spec_key)}",
        "preconditions": "App running; test database seeded; authenticated session available.",
        "test_data_notes": (spec.get("data_and_validation") or "")[:280],
        "outcomes_summary": f"Proves {spec.get('title', spec_key)} satisfies its acceptance criteria, "
                            f"functional requirements, and business rules.",
        "priority": priority, "summary": (spec.get("narrative") or "")[:280],
        "completeness": 100, "confidence": "high",
    }

    return {"plan": plan, "test_cases": cases, "traceability": traces, "open_questions": []}


# ── Gap-fill unit: author cases ONLY for specific uncovered FRS elements ───────

class TcGapFillOutput(BaseModel):
    test_cases: list[TcCaseRow] = Field(..., min_length=1)
    traceability: list[TcTraceRow] = Field(default_factory=list)
    open_questions: list[TcOpenQuestion] = Field(default_factory=list)


class TcGapFillSignature(dspy.Signature):
    """Author test cases ONLY for the specific UNCOVERED FRS elements in `gaps`.

    LANGUAGE: Write every field in clear professional ENGLISH. Never switch languages.

    `gaps` is a JSON object listing the elements that currently have NO test case:
    scenarios (with given/when/then/is_negative/fr_refs), functional_requirements,
    business_rules, screens, and possibly independent_test. Author exactly enough
    cases to cover EACH listed element (>=1 case each; negative test_type for an
    is_negative scenario; responsive for a screen; e2e for independent_test).

    Do NOT author cases for anything not in `gaps` (the rest of the spec is already
    covered). Each case must be RICH: >=2 concrete outcome-level key_assertions in
    FRS language, a specific expected_result, test_data for data-dependent cases.
    Set fr_refs/scenario_refs/br_refs to the EXACT row_keys from `gaps` and emit a
    test_case_traceability row to each (frs_acceptance_scenario / frs_functional_
    requirement / frs_business_rule / frs_screen). Use `target_spec` only for
    context. row_key can be any unique placeholder; it will be renumbered on save.
    """
    project_name: str = dspy.InputField()
    spec_row_key: str = dspy.InputField()
    plan_row_key: str = dspy.InputField()
    module_row_key: str = dspy.InputField()
    target_spec: str = dspy.InputField(desc="JSON: full FRS spec, for context only")
    gaps: str = dspy.InputField(desc="JSON: the uncovered elements to author cases for")
    brd_context: str = dspy.InputField(desc="Linked business requirements")
    app_brain: str = dspy.InputField(desc="In-scope application facts; '' if none")
    result: TcGapFillOutput = dspy.OutputField()


class TcGapFillModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.Predict(TcGapFillSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_gap_fill(**kwargs) -> dict:
    """Author cases for only the uncovered elements. Mock synthesizes them."""
    if _is_mock():
        return _mock_gap_fill(kwargs)
    _configure()
    lm = _get_tc_lm()
    loop = asyncio.get_running_loop()

    def _run():
        with dspy.context(lm=lm):
            return TcGapFillModule()(**kwargs)
    fut = loop.run_in_executor(None, _run)
    try:
        return await asyncio.shield(fut)
    except asyncio.CancelledError:
        raise TimeoutError("DSPy TcGapFill timed out")


def _mock_gap_fill(kwargs: dict) -> dict:
    gaps = json.loads(kwargs.get("gaps") or "{}")
    plan = kwargs.get("plan_row_key", "")
    cases: list[dict] = []
    traces: list[dict] = []
    n = 0

    def _nk() -> str:
        nonlocal n
        n += 1
        return f"{plan}-GAP-{n:03d}"

    def _base(rk, title, ttype, sk, sref, then_txt, neg=False, viewports=None):
        cases.append({
            "row_key": rk, "title": title[:90], "test_type": ttype, "source_kind": sk,
            "source_ref": sref, "given": "A valid context", "when": "the behavior is exercised",
            "then": (then_txt or "")[:200], "steps": [], "preconditions": "Authenticated session.",
            "key_assertions": _mk_assertions(then_txt, neg),
            "test_data": {"setup": [], "inputs": {}, "boundary": (["min", "max"] if neg else [])},
            "expected_result": (then_txt or "The outcome holds.")[:200],
            "expected_observability": [], "viewports": viewports or [],
            "auth_required": False, "auth_role": None, "priority": "P1",
            "fr_refs": [], "scenario_refs": [], "br_refs": [],
        })

    for sc in gaps.get("scenarios", []):
        rk = _nk(); neg = bool(sc.get("is_negative"))
        _base(rk, ("Reject: " if neg else "Verify: ") + (sc.get("when") or sc["row_key"]),
              "negative" if neg else "functional", "acceptance_scenario", sc["row_key"], sc.get("then", ""), neg)
        cases[-1]["scenario_refs"] = [sc["row_key"]]; cases[-1]["fr_refs"] = list(sc.get("fr_refs") or [])
        traces.append({"source_table": "test_cases", "source_row_key": rk,
                       "target_kind": "frs_acceptance_scenario", "target_ref": sc["row_key"], "confidence": "high"})
    for fr in gaps.get("functional_requirements", []):
        rk = _nk()
        _base(rk, f"Requirement {fr.get('fr_id', fr['row_key'])} verification", "functional",
              "functional_requirement", fr["row_key"], fr.get("requirement_text", ""))
        cases[-1]["fr_refs"] = [fr["row_key"]]
        traces.append({"source_table": "test_cases", "source_row_key": rk,
                       "target_kind": "frs_functional_requirement", "target_ref": fr["row_key"], "confidence": "high"})
    for br in gaps.get("business_rules", []):
        rk = _nk()
        _base(rk, f"Rule {br.get('rule_id', br['row_key'])} enforcement", "edge_case",
              "business_rule", br["row_key"], br.get("description", ""), neg=True)
        cases[-1]["br_refs"] = [br["row_key"]]
        traces.append({"source_table": "test_cases", "source_row_key": rk,
                       "target_kind": "frs_business_rule", "target_ref": br["row_key"], "confidence": "high"})
    for scr in gaps.get("screens", []):
        rk = _nk()
        _base(rk, f"{scr.get('screen_name', scr['row_key'])} responsive layout", "responsive",
              "screen", scr["row_key"], "The layout adapts at every breakpoint",
              viewports=["mobile-360", "tablet-768", "desktop-1440"])
        cases[-1]["key_assertions"] = ["All controls reachable at each viewport", "No overflow at mobile width"]
        traces.append({"source_table": "test_cases", "source_row_key": rk,
                       "target_kind": "frs_screen", "target_ref": scr["row_key"], "confidence": "high"})
    if gaps.get("independent_test"):
        rk = _nk()
        _base(rk, "Smoke: end to end", "e2e", "independent_test", kwargs.get("spec_row_key"),
              gaps.get("independent_test", "")[:160] or "The flow succeeds end to end")
        traces.append({"source_table": "test_cases", "source_row_key": rk,
                       "target_kind": "frs_spec", "target_ref": kwargs.get("spec_row_key", ""), "confidence": "high"})

    if not cases:  # nothing to fill (shouldn't happen — caller checks first)
        _base(_nk(), "Placeholder", "functional", "manual", None, "Covered.")
    return {"test_cases": cases, "traceability": traces, "open_questions": []}
