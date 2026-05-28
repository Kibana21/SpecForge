"""DSPy modules for FRS generation — 2 units: modularize (Stage A) + design_module (Stage B).

Stage A: one DSPy call decomposes the BRD into 5–12 modules + backlog stubs.
Stage B: per-module DSPy call (parallel) authors full FRS specs.

Pattern follows dspy_brd.py:
- Pydantic output model
- DSPy Signature with typed docstring
- DSPy Module (ChainOfThought)
- Async runner (mock path → fixture, real path → Gemini)
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Literal

import dspy
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

_FIXTURE_DIR = Path(__file__).parent.parent / "llm" / "fixtures"


def _configure() -> None:
    from app.services.skills.fact_extractor.dspy_extractor import _configure_dspy
    _configure_dspy()


def _is_mock() -> bool:
    from app.config import get_settings
    return get_settings().llm_provider == "mock"


def _load_fixture(name: str) -> dict:
    """Load a fixture JSON file. Name prefix is implied (frs_*)."""
    path = _FIXTURE_DIR / f"{name}.json"
    with open(path) as f:
        return json.load(f)


# ── Common output models ──────────────────────────────────────────────────────

class FrsOpenQuestion(BaseModel):
    question: str
    field: str
    why: str
    example: str = ""


class FrsSpecDecisionRow(BaseModel):
    """[SPEC-DECISION] MCQ raised during modularize or design_module."""
    row_key: str
    spec_row_key: str | None = None       # set in Stage B (spec-scoped)
    module_row_key: str | None = None     # set in Stage A (module-scoped)
    question: str
    options: list[dict[str, Any]] = Field(
        description="2–4 options: each {label, description, implications}"
    )
    recommended_index: int = Field(ge=0)
    recommended_rationale: str


# ── Stage A — Modularize output models ────────────────────────────────────────

class FrsActorRow(BaseModel):
    actor_name: str
    relationship: Literal["primary_user", "dependency", "external_system", "downstream_consumer"]
    notes: str = ""


class FrsResponsibilityRow(BaseModel):
    responsibility: str
    frs_refs: list[str] = Field(default_factory=list, description="Backlog stub row_keys this maps to")


class FrsInterfaceRow(BaseModel):
    interface_kind: Literal["ui_surface", "api", "event"]
    direction: Literal["inbound", "outbound"] | None = None      # None for ui_surface
    transport: Literal["rest", "grpc", "mq", "webhook", "event_bus"] | None = None
    name: str
    counterpart: str | None = None
    user_role: str | None = None
    purpose: str = ""
    frs_ref: str | None = None


class FrsModuleDataRow(BaseModel):
    entity_name: str
    business_purpose: str = ""
    source_of_truth: str = ""


class FrsBacklogStub(BaseModel):
    row_key: str = Field(description="M001-FRS001 format (zero-padded, module-prefixed)")
    title: str
    priority: Literal["P0", "P1", "P2", "P3"]
    br_refs: list[str] = Field(description="BR row_keys from the validated BRD this stub traces to")
    description: str = Field(description="1–2 sentence description; Stage B expands to full FRS")


class FrsModuleInventoryRow(BaseModel):
    row_key: str = Field(description="MOD-000 for Cross-cutting Standards, MOD-001+, …")
    name: str = Field(description="Capability-language name — NEVER tech-specific")
    slug: str = Field(description="URL-safe kebab-case")
    layer: Literal["foundation", "vertical", "cross_cutting"]
    scope_in: str = Field(description="Bullet narrative of what's in scope")
    scope_out: str = Field(description="Bullet narrative of what's out of scope (with module-owner notes)")
    summary: str = Field(description="2–3 sentences describing the module")
    actors: list[FrsActorRow] = Field(description="2–8 actors typical")
    responsibilities: list[FrsResponsibilityRow] = Field(description="Business-language responsibilities; each maps to ≥1 FRS")
    interfaces: list[FrsInterfaceRow] = Field(description="UI surfaces + APIs (inbound/outbound) + events")
    data_entities: list[FrsModuleDataRow] = Field(description="Conceptual entities only; NO schema")
    frs_backlog: list[FrsBacklogStub] = Field(description="3–15 stubs typical")


class FrsModularizeOutput(BaseModel):
    modules: list[FrsModuleInventoryRow] = Field(description="5–12 modules typical")
    spec_decisions: list[FrsSpecDecisionRow] = Field(
        default_factory=list,
        description="Module-scoped [SPEC-DECISION] MCQs; cap at 5",
    )
    open_questions: list[FrsOpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


# ── Stage A — Modularize signature ────────────────────────────────────────────

class FrsModularizeSignature(dspy.Signature):
    """Run Steps 1+2+3 of the FRS-Builder skill: decompose the validated BRD into
    business-capability modules using DDD bounded contexts.

    HARD RULES (non-negotiable):

    1. Module names MUST use capability/role language. NEVER use tech-specific names:
       no 'API', 'Service', 'DB', 'Lambda', 'Kafka', 'Postgres', 'Redis',
       'Microservice', 'Gateway', etc. Use 'Authentication' (not 'Auth API'),
       'Notifications' (not 'Notification Service'), 'Claims Triage' (not 'Triage Lambda').

    2. Modules do NOT integrate via shared internal data models or shared databases.
       Every cross-module dependency MUST appear in BOTH source and target modules'
       `interfaces` (source = outbound, target = inbound) with matching `name` and
       `transport`. Symmetry is enforced by the downstream validator.

    3. Do NOT create modules for deployment / CI/CD / infrastructure / environment
       setup — those are architecture concerns, not business capabilities.

    4. Apply DDD bounded-context signals: rules/invariants differ, language differs,
       data ownership differs, actors differ, change cadence differs.

    5. Apply sizing rules. Split if: multiple independent sub-capabilities, >3 major
       end-to-end flows, >5 aggregates, >2 unrelated external integrations, or would
       produce >15 FRS for one module. Merge if two candidate modules always change
       together or share core invariants.

    CROSS-CUTTING STANDARDS (Layer 0):
    If you detect ≥2 modules sharing common rules (error envelope, reference data,
    RBAC base, common audit pattern, shared date/timezone handling), hoist those
    rules into a Layer-0 module called 'Cross-cutting Standards' with
    row_key='MOD-000'. Feature modules will reference its FRS via `depends_on`
    during Stage B.

    BACKLOG STUBS:
    For each module produce 3–15 FRS slices. Each stub must:
    - Use row_key M001-FRS001, M001-FRS002, … (module-prefixed, zero-padded to 3 digits)
    - Have a 1–2 sentence description (Stage B expands to a full FRS spec)
    - Trace to ≥1 BR row_key from the validated BRD (br_refs)
    DO NOT write full FRS spec content here.

    AMBIGUITY ([SPEC-DECISION]):
    For any module-boundary decision where multiple reasonable decompositions exist,
    emit a SpecDecisionRow with 2–4 MCQ options, pick recommended_index (typically
    the simpler/lower-coupling option), and PROCEED. The user can override later.
    Cap at 5 module-scoped decisions per run.

    ROW_KEY CONVENTIONS:
    - Modules:        MOD-000 (Cross-cutting), MOD-001, MOD-002, …
    - Actors:         {module_row_key}-ACT-1, -ACT-2, …
    - Responsib.:     {module_row_key}-R-1, -R-2, …
    - Interfaces:     {module_row_key}-IF-1, -IF-2, …
    - Data entities:  {module_row_key}-E-1, -E-2, …
    - Backlog stubs:  M001-FRS001, M001-FRS002, …
    - Decisions:      MOD-001-DEC-1, MOD-001-DEC-2, …

    Preserve row_keys for any modules in current_modules JSON. Locked modules
    (in locked_modules JSON) must be reproduced verbatim.
    """
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    brief: str = dspy.InputField(desc="Optional user brief; may be empty")
    brd_context: str = dspy.InputField(desc="Full validated BRD: every row, formatted")
    cb_context: str = dspy.InputField(desc="Validated Concept Brief")
    app_brain: str = dspy.InputField(desc="In-scope application facts")
    source_sections: str = dspy.InputField(
        desc="Retrieved NFR / Architecture doc sections (if uploaded), else empty"
    )
    qa_pairs: str = dspy.InputField(desc="FRS discover Q&A answers")
    current_modules: str = dspy.InputField(
        desc="JSON of existing modules for idempotent regen; '[]' on first run"
    )
    locked_modules: str = dspy.InputField(
        desc="JSON of locked modules to preserve verbatim; '[]' if none locked"
    )
    result: FrsModularizeOutput = dspy.OutputField()


class FrsModularizeModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(FrsModularizeSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_modularize(**kwargs) -> dict:
    if _is_mock():
        return _load_fixture("frs_modularize")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: FrsModularizeModule()(**kwargs))


# ── Stage B — design_module (signatures defined in E4c-2 plan) ────────────────
# Stage B's FrsDesignModuleSignature + run_design_module live in this same file
# when Stage B ships; for now Stage A is self-contained.
