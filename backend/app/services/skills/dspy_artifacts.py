"""DSPy modules for Concept Brief generation units.

Six units + shared row Pydantic models. Mock path returns fixtures.
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Literal

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
    path = _FIXTURE_DIR / f"artifact_{name}.json"
    with open(path) as f:
        return json.load(f)


# ── Row Pydantic models (1:1 with table typed columns) ────────────────────────

class ContextMapRow(BaseModel):
    row_key: str
    dimension: str
    detail: str


class OutcomeRow(BaseModel):
    row_key: str
    outcome: str
    description: str


class MetricRow(BaseModel):
    row_key: str
    metric: str
    description: str
    quantifiable: bool


class CapabilityRow(BaseModel):
    row_key: str
    capability: str
    description: str


class ScopeItemRow(BaseModel):
    row_key: str
    kind: Literal["in_scope", "out_of_scope", "assumption"]
    text: str


class MilestoneRow(BaseModel):
    row_key: str
    milestone: str
    target: str
    description: str


class OpenQuestion(BaseModel):
    question: str
    field: str
    why: str


# ── Shared signature inputs (all units receive these) ─────────────────────────

_COMMON_INPUTS = dict(
    project_name=dspy.InputField(desc="Project name"),
    business_unit=dspy.InputField(desc="Owning business unit"),
    description=dspy.InputField(desc="Project description"),
    source_sections=dspy.InputField(desc="Retrieved source document sections [S#], or empty"),
    impacted_apps=dspy.InputField(desc="Formatted impacted applications context, or empty"),
    qa_pairs=dspy.InputField(desc="Q&A interview transcript relevant to this unit, or empty"),
    upstream=dspy.InputField(desc="JSON of upstream dependency units' current rows"),
    current_rows=dspy.InputField(desc="This unit's current rows with row_keys (may be empty)"),
    locked_rows=dspy.InputField(desc="Locked rows that must be reproduced verbatim"),
)


# ── Unit 1: problem_context ───────────────────────────────────────────────────

class ProblemContextOutput(BaseModel):
    business_context: str = Field(description="Business context paragraph")
    problem_statement: str = Field(description="Problem statement paragraph")
    context_map: list[ContextMapRow] = Field(description="Exactly 6 context map rows")
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


class ProblemContextSignature(dspy.Signature):
    """Generate the Problem Statement & Context Map for a Concept Brief.

    Write a clear Business Context paragraph and a Problem Statement paragraph. For the
    Context Map produce exactly 6 rows with fixed dimensions: business_unit, new_channel,
    customer_segments, current_gap, strategic_driver, engagement_goal. Ground every
    statement in source sections [S#] and impacted applications. Reflect the apps'
    impact notes in current_gap, strategic_driver, and new_channel. Reproduce locked
    rows verbatim. Keep existing row_keys stable; mint new keys only for new rows.
    """

    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    impacted_apps: str = dspy.InputField()
    qa_pairs: str = dspy.InputField()
    upstream: str = dspy.InputField()
    current_rows: str = dspy.InputField()
    locked_rows: str = dspy.InputField()
    result: ProblemContextOutput = dspy.OutputField()


class ProblemContextModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(ProblemContextSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_problem_context(**kwargs) -> dict:
    if _is_mock():
        return _load_fixture("problem_context")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: ProblemContextModule()(**kwargs))


# ── Unit 2: value_hypothesis ──────────────────────────────────────────────────

class ValueHypothesisOutput(BaseModel):
    value_hypothesis_if: str = Field(description="The 'If [action]' part of the hypothesis")
    value_hypothesis_then: str = Field(description="The 'then [measurable result] for [who]' part")
    outcomes: list[OutcomeRow] = Field(description="3–6 expected outcomes")
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


class ValueHypothesisSignature(dspy.Signature):
    """Generate the Value Hypothesis & Expected Outcomes for a Concept Brief.

    Write a testable 'If [action] then [measurable result] for [who]' hypothesis split
    across value_hypothesis_if and value_hypothesis_then. List 3–6 concrete outcomes
    grounded in problem context and impacted applications. Keep row_keys stable.
    """

    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    impacted_apps: str = dspy.InputField()
    qa_pairs: str = dspy.InputField()
    upstream: str = dspy.InputField()
    current_rows: str = dspy.InputField()
    locked_rows: str = dspy.InputField()
    result: ValueHypothesisOutput = dspy.OutputField()


class ValueHypothesisModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(ValueHypothesisSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_value_hypothesis(**kwargs) -> dict:
    if _is_mock():
        return _load_fixture("value_hypothesis")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: ValueHypothesisModule()(**kwargs))


# ── Unit 3: metrics ───────────────────────────────────────────────────────────

class MetricsOutput(BaseModel):
    metrics: list[MetricRow] = Field(description="Success metrics; at least one must be quantifiable=true")
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


class MetricsSignature(dspy.Signature):
    """Generate Success Metrics for a Concept Brief.

    Produce at least one quantifiable metric (quantifiable=true) with a specific numeric
    target. Ground metrics in outcomes and any KPIs from source documents or impacted
    applications. Keep row_keys stable.
    """

    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    impacted_apps: str = dspy.InputField()
    qa_pairs: str = dspy.InputField()
    upstream: str = dspy.InputField()
    current_rows: str = dspy.InputField()
    locked_rows: str = dspy.InputField()
    result: MetricsOutput = dspy.OutputField()


class MetricsModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(MetricsSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_metrics(**kwargs) -> dict:
    if _is_mock():
        return _load_fixture("metrics")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: MetricsModule()(**kwargs))


# ── Unit 4: capabilities ──────────────────────────────────────────────────────

class CapabilitiesOutput(BaseModel):
    capabilities: list[CapabilityRow]
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


class CapabilitiesSignature(dspy.Signature):
    """Generate Proposed Capabilities for a Concept Brief.

    List solution-agnostic capabilities traceable to problems and outcomes. Ground in
    impacted applications — call out where an app supports, enables, or limits a
    capability. Keep row_keys stable.
    """

    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    impacted_apps: str = dspy.InputField()
    qa_pairs: str = dspy.InputField()
    upstream: str = dspy.InputField()
    current_rows: str = dspy.InputField()
    locked_rows: str = dspy.InputField()
    result: CapabilitiesOutput = dspy.OutputField()


class CapabilitiesModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(CapabilitiesSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_capabilities(**kwargs) -> dict:
    if _is_mock():
        return _load_fixture("capabilities")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: CapabilitiesModule()(**kwargs))


# ── Unit 5: scope ─────────────────────────────────────────────────────────────

class ScopeOutput(BaseModel):
    scope_items: list[ScopeItemRow] = Field(description="At least 1 of each kind: in_scope, out_of_scope, assumption")
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


class ScopeSignature(dspy.Signature):
    """Generate Scope Boundaries & Assumptions for a Concept Brief.

    Produce in_scope items aligned to capabilities, out_of_scope explicit exclusions,
    and assumption items. Reflect impacted applications' documented limitations and
    integration constraints. At least 1 of each kind. Keep row_keys stable.
    """

    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    impacted_apps: str = dspy.InputField()
    qa_pairs: str = dspy.InputField()
    upstream: str = dspy.InputField()
    current_rows: str = dspy.InputField()
    locked_rows: str = dspy.InputField()
    result: ScopeOutput = dspy.OutputField()


class ScopeModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(ScopeSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_scope(**kwargs) -> dict:
    if _is_mock():
        return _load_fixture("scope")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: ScopeModule()(**kwargs))


# ── Unit 6: milestones ────────────────────────────────────────────────────────

class MilestonesOutput(BaseModel):
    milestones: list[MilestoneRow]
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


class MilestonesSignature(dspy.Signature):
    """Generate the Delivery Approach milestones for a Concept Brief.

    Produce a realistic milestone table with target dates or relative timeframes.
    Ground in scope and impacted applications' integration complexity. Keep row_keys stable.
    """

    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    impacted_apps: str = dspy.InputField()
    qa_pairs: str = dspy.InputField()
    upstream: str = dspy.InputField()
    current_rows: str = dspy.InputField()
    locked_rows: str = dspy.InputField()
    result: MilestonesOutput = dspy.OutputField()


class MilestonesModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(MilestonesSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_milestones(**kwargs) -> dict:
    if _is_mock():
        return _load_fixture("milestones")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: MilestonesModule()(**kwargs))


# ── Dispatcher ────────────────────────────────────────────────────────────────

_RUNNERS = {
    "problem_context":  run_problem_context,
    "value_hypothesis": run_value_hypothesis,
    "metrics":          run_metrics,
    "capabilities":     run_capabilities,
    "scope":            run_scope,
    "milestones":       run_milestones,
}


async def run_unit(unit_key: str, **kwargs) -> dict:
    runner = _RUNNERS.get(unit_key)
    if runner is None:
        raise ValueError(f"Unknown unit_key: {unit_key}")
    return await runner(**kwargs)
