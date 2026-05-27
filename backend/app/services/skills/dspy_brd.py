"""DSPy modules for BRD generation — 22 units.

Each unit follows the same pattern as dspy_artifacts.py:
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
    path = _FIXTURE_DIR / f"brd_{name}.json"
    with open(path) as f:
        return json.load(f)


# ── Common output models ──────────────────────────────────────────────────────

class BrdOpenQuestion(BaseModel):
    question: str
    field: str
    why: str
    example: str = ""


class TraceabilityRow(BaseModel):
    source_row_key: str
    target_kind: Literal[
        "cb_text_block", "cb_outcome", "cb_metric", "cb_capability",
        "cb_scope_item", "cb_milestone", "app_fact", "doc_section", "discover_qa"
    ]
    target_ref: str
    target_label: str
    confidence: Literal["high", "medium", "low"] = "high"


# ── §1: business_context ──────────────────────────────────────────────────────

class BusinessContextOutput(BaseModel):
    business_context: str = Field(description="Business context narrative (2–4 paragraphs)")
    open_questions: list[BrdOpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


class BusinessContextSignature(dspy.Signature):
    """Write §1 Business Context for a Business Requirements Document.

    Draw on the validated Concept Brief business_context, App Brain grounding (include
    specific app names and tiers), and project documents [S#]. Cover: industry/regulatory
    backdrop, strategic imperatives, the owning business unit, and how in-scope apps sit
    in the ecosystem. Be specific — reference app names, doc sections by [S#], and CB rows.
    For every open_question populate `example` with a concrete sample answer.
    """
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    cb_context: str = dspy.InputField(desc="Validated Concept Brief context")
    source_sections: str = dspy.InputField(desc="Retrieved project document sections [S#]")
    app_brain: str = dspy.InputField(desc="In-scope application facts")
    qa_pairs: str = dspy.InputField(desc="Discover Q&A relevant to this unit")
    upstream: str = dspy.InputField(desc="JSON of upstream unit rows")
    current_rows: str = dspy.InputField(desc="Current rows for idempotent generation")
    locked_rows: str = dspy.InputField(desc="Locked rows to reproduce verbatim")
    result: BusinessContextOutput = dspy.OutputField()


class BusinessContextModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(BusinessContextSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_business_context(**kwargs) -> dict:
    if _is_mock():
        return _load_fixture("business_context")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: BusinessContextModule()(**kwargs))


# ── §2: problem_statement ─────────────────────────────────────────────────────

class ProblemStatementOutput(BaseModel):
    problem_statement: str = Field(description="Crisp problem statement (1–2 paragraphs)")
    root_causes: list[str] = Field(description="2–5 enumerated root causes")
    open_questions: list[BrdOpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


class ProblemStatementSignature(dspy.Signature):
    """Write §2 Problem Statement for a BRD.

    Write a concise, evidence-grounded problem statement and enumerate root causes.
    Distinguish symptoms from root causes. Ground in CB problem_statement, App Brain
    pain points, and document sections [S#]. Reference source material explicitly.
    """
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    cb_context: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    app_brain: str = dspy.InputField()
    qa_pairs: str = dspy.InputField()
    upstream: str = dspy.InputField()
    current_rows: str = dspy.InputField()
    locked_rows: str = dspy.InputField()
    result: ProblemStatementOutput = dspy.OutputField()


class ProblemStatementModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(ProblemStatementSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_problem_statement(**kwargs) -> dict:
    if _is_mock():
        return _load_fixture("problem_statement")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: ProblemStatementModule()(**kwargs))


# ── §3: objectives ────────────────────────────────────────────────────────────

class ObjectiveRow(BaseModel):
    row_key: str
    statement: str
    category: str = "strategic"
    priority: Literal["must", "should", "could", "wont"]
    owner: str
    cb_outcome_ref: str | None = None


class ObjectivesOutput(BaseModel):
    objectives: list[ObjectiveRow] = Field(description="3–7 SMART objectives")
    traceability: list[TraceabilityRow] = Field(description="Outward traces for each objective; every objective must have ≥1 trace to a CB outcome or CB text block")
    open_questions: list[BrdOpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


class ObjectivesSignature(dspy.Signature):
    """Write §3 Strategic Objectives for a BRD.

    Derive 3–7 SMART objectives from CB outcomes and value hypothesis. Each objective
    must trace to a CB outcome (cb_outcome_ref). Assign MoSCoW priority reflecting
    CB value tier. Name an owner. Use OBJ-001, OBJ-002, … as row_keys.
    For each objective produce ≥1 traceability entry pointing to its CB outcome or
    text block source — source_row_key is the OBJ-xxx key, target_kind is cb_outcome
    or cb_text_block, target_ref is the CB row_key.
    """
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    cb_context: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    app_brain: str = dspy.InputField()
    qa_pairs: str = dspy.InputField()
    upstream: str = dspy.InputField()
    current_rows: str = dspy.InputField()
    locked_rows: str = dspy.InputField()
    result: ObjectivesOutput = dspy.OutputField()


class ObjectivesModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(ObjectivesSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_objectives(**kwargs) -> dict:
    if _is_mock():
        return _load_fixture("objectives")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: ObjectivesModule()(**kwargs))


# ── §4a: stakeholders ─────────────────────────────────────────────────────────

class StakeholderRow(BaseModel):
    row_key: str
    name: str
    stakeholder_type: Literal["sponsor", "owner", "user", "operations", "compliance", "technical", "external"]
    role: str
    interest: str
    influence: Literal["high", "medium", "low"]


class StakeholdersOutput(BaseModel):
    stakeholders: list[StakeholderRow]
    open_questions: list[BrdOpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


class StakeholdersSignature(dspy.Signature):
    """Write §4a Stakeholders for a BRD.

    Identify all stakeholder groups from CB context_map customer_segments and App Brain.
    For each: name, type, role, primary interest, and influence. Use STK-001 row_keys.
    """
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    cb_context: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    app_brain: str = dspy.InputField()
    qa_pairs: str = dspy.InputField()
    upstream: str = dspy.InputField()
    current_rows: str = dspy.InputField()
    locked_rows: str = dspy.InputField()
    result: StakeholdersOutput = dspy.OutputField()


class StakeholdersModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(StakeholdersSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_stakeholders(**kwargs) -> dict:
    if _is_mock():
        return _load_fixture("stakeholders")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: StakeholdersModule()(**kwargs))


# ── §4b: actors ───────────────────────────────────────────────────────────────

class ActorRow(BaseModel):
    row_key: str
    name: str
    actor_type: Literal["human", "system"]
    description: str
    interactions: str


class ActorsOutput(BaseModel):
    actors: list[ActorRow]
    open_questions: list[BrdOpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


class ActorsSignature(dspy.Signature):
    """Write §4b System Actors for a BRD.

    List every human role and system that interacts with the solution. Ground in
    App Brain capabilities — call out systems by app name. Use ACT-001 row_keys.
    """
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    cb_context: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    app_brain: str = dspy.InputField()
    qa_pairs: str = dspy.InputField()
    upstream: str = dspy.InputField()
    current_rows: str = dspy.InputField()
    locked_rows: str = dspy.InputField()
    result: ActorsOutput = dspy.OutputField()


class ActorsModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(ActorsSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_actors(**kwargs) -> dict:
    if _is_mock():
        return _load_fixture("actors")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: ActorsModule()(**kwargs))


# ── §5: scope ─────────────────────────────────────────────────────────────────

class BrdScopeItemRow(BaseModel):
    row_key: str
    kind: Literal["in_scope", "out_of_scope", "assumption"]
    text: str
    rationale: str = ""
    cb_scope_ref: str | None = None


class ScopeOutput(BaseModel):
    scope_items: list[BrdScopeItemRow] = Field(description="At least 2 of each kind")
    open_questions: list[BrdOpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


class ScopeSignature(dspy.Signature):
    """Write §5 Scope for a BRD.

    Produce in_scope (features/capabilities), out_of_scope (exclusions with rationale),
    and assumption items. Reference CB scope_items via cb_scope_ref.
    Minimum 2 of each kind. Use SCP-IN-001, SCP-OUT-001, SCP-ASM-001 formats.
    """
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    cb_context: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    app_brain: str = dspy.InputField()
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
        return _load_fixture("brd_scope")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: ScopeModule()(**kwargs))


# ── §6a: asis_process ─────────────────────────────────────────────────────────

class ProcessStepRow(BaseModel):
    row_key: str
    step_type: Literal["asis", "tobe"]
    step_number: int
    actor: str
    action: str
    pain_point: str | None = None
    improvement: str | None = None


class AsisProcessOutput(BaseModel):
    steps: list[ProcessStepRow] = Field(description="3–8 as-is process steps")
    open_questions: list[BrdOpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


class AsisProcessSignature(dspy.Signature):
    """Write §6a As-Is Process for a BRD.

    Map the current-state workflow step by step. Every step: step_number, actor,
    action, and pain_point. All steps must have step_type='asis'. Ground in [S#]
    and App Brain operational facts. Use ASIS-001 row_keys.
    """
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    cb_context: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    app_brain: str = dspy.InputField()
    qa_pairs: str = dspy.InputField()
    upstream: str = dspy.InputField()
    current_rows: str = dspy.InputField()
    locked_rows: str = dspy.InputField()
    result: AsisProcessOutput = dspy.OutputField()


class AsisProcessModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(AsisProcessSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_asis_process(**kwargs) -> dict:
    if _is_mock():
        return _load_fixture("asis_process")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: AsisProcessModule()(**kwargs))


# ── §6b: tobe_process ────────────────────────────────────────────────────────

class TobeProcessOutput(BaseModel):
    steps: list[ProcessStepRow] = Field(description="3–8 to-be process steps, all step_type='tobe'")
    open_questions: list[BrdOpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


class TobeProcessSignature(dspy.Signature):
    """Write §6b To-Be Process for a BRD.

    Map the future-state workflow enabled by the solution. Every step: step_number,
    actor, action, and improvement vs as-is. All steps must have step_type='tobe'.
    Ground in CB capabilities and App Brain. Use TOBE-001 row_keys.
    """
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    cb_context: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    app_brain: str = dspy.InputField()
    qa_pairs: str = dspy.InputField()
    upstream: str = dspy.InputField()
    current_rows: str = dspy.InputField()
    locked_rows: str = dspy.InputField()
    result: TobeProcessOutput = dspy.OutputField()


class TobeProcessModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(TobeProcessSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_tobe_process(**kwargs) -> dict:
    if _is_mock():
        return _load_fixture("tobe_process")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: TobeProcessModule()(**kwargs))


# ── §7: business_requirements (keystone) ─────────────────────────────────────

class AcceptanceCriterion(BaseModel):
    given: str
    when: str
    then: str


class BrRow(BaseModel):
    row_key: str
    title: str
    description: str
    priority: Literal["must", "should", "could", "wont"]
    category: Literal["functional", "non_functional", "data", "integration", "reporting", "compliance", "operational"]
    acceptance_criteria: list[AcceptanceCriterion] = Field(description="≥2 for 'must' BRs")
    objective_refs: list[str] = Field(description="row_keys of brd_objectives this BR satisfies")
    stakeholder_refs: list[str] = Field(description="row_keys of brd_stakeholders impacted")
    rationale: str


class BusinessRequirementsOutput(BaseModel):
    business_requirements: list[BrRow] = Field(description="All business requirements; must cover every in-scope item and CB capability")
    traceability: list[TraceabilityRow] = Field(description="Outward traces for each BR; every BR must have ≥1 trace")
    open_questions: list[BrdOpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


class BusinessRequirementsSignature(dspy.Signature):
    """Write §7 Business Requirements — the keystone section of the BRD.

    For each BR: title, description, MoSCoW priority, category, 2–4 Given-When-Then
    acceptance criteria (every 'must' BR must have ≥2), objective_refs (brd_objectives
    row_keys), stakeholder_refs (brd_stakeholders row_keys), and rationale citing
    CB/App Brain/doc sources. BRs must collectively cover every in-scope item and CB
    capability. For each BR produce ≥1 traceability entry pointing to a CB row, app
    fact, or doc section — never fabricate source refs not present in the context.
    Use BR-001 row_keys.
    """
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    cb_context: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    app_brain: str = dspy.InputField()
    qa_pairs: str = dspy.InputField()
    upstream: str = dspy.InputField()
    current_rows: str = dspy.InputField()
    locked_rows: str = dspy.InputField()
    result: BusinessRequirementsOutput = dspy.OutputField()


class BusinessRequirementsModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(BusinessRequirementsSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_business_requirements(**kwargs) -> dict:
    if _is_mock():
        return _load_fixture("business_requirements")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: BusinessRequirementsModule()(**kwargs))


# ── §8a: data_entities ────────────────────────────────────────────────────────

class DataEntityRow(BaseModel):
    row_key: str
    entity_name: str
    description: str
    owner_system: str
    data_sensitivity: Literal["standard", "confidential", "restricted"]
    key_attributes: list[str]


class DataEntitiesOutput(BaseModel):
    entities: list[DataEntityRow]
    open_questions: list[BrdOpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


class DataEntitiesSignature(dspy.Signature):
    """Write §8a Data Entities for a BRD.

    Identify all key data entities the solution creates, consumes, or transforms.
    Ground in App Brain integration facts. Sensitivity must reflect App Brain
    operational facts. Use DE-001 row_keys.
    """
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    cb_context: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    app_brain: str = dspy.InputField()
    qa_pairs: str = dspy.InputField()
    upstream: str = dspy.InputField()
    current_rows: str = dspy.InputField()
    locked_rows: str = dspy.InputField()
    result: DataEntitiesOutput = dspy.OutputField()


class DataEntitiesModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(DataEntitiesSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_data_entities(**kwargs) -> dict:
    if _is_mock():
        return _load_fixture("data_entities")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: DataEntitiesModule()(**kwargs))


# ── §8b: report_requirements ──────────────────────────────────────────────────

class ReportReqRow(BaseModel):
    row_key: str
    report_name: str
    description: str
    audience: str
    frequency: str
    key_metrics: list[str]


class ReportRequirementsOutput(BaseModel):
    report_requirements: list[ReportReqRow]
    open_questions: list[BrdOpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


class ReportRequirementsSignature(dspy.Signature):
    """Write §8b Reporting Requirements for a BRD.

    Identify all reports/dashboards the solution must produce. Ground in KPIs and
    CB metrics. Audience must map to a defined stakeholder group. Use RR-001 row_keys.
    """
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    cb_context: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    app_brain: str = dspy.InputField()
    qa_pairs: str = dspy.InputField()
    upstream: str = dspy.InputField()
    current_rows: str = dspy.InputField()
    locked_rows: str = dspy.InputField()
    result: ReportRequirementsOutput = dspy.OutputField()


class ReportRequirementsModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(ReportRequirementsSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_report_requirements(**kwargs) -> dict:
    if _is_mock():
        return _load_fixture("report_requirements")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: ReportRequirementsModule()(**kwargs))


# ── §9a: assumptions ──────────────────────────────────────────────────────────

class AssumptionRow(BaseModel):
    row_key: str
    assumption: str
    impact_if_wrong: str
    owner: str
    cb_scope_ref: str | None = None


class AssumptionsOutput(BaseModel):
    assumptions: list[AssumptionRow]
    open_questions: list[BrdOpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


class AssumptionsSignature(dspy.Signature):
    """Write §9a Assumptions for a BRD.

    Document every assumption the initiative makes. Reference CB scope_items of
    kind='assumption' via cb_scope_ref. Each must have impact_if_wrong. Use ASM-001.
    """
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    cb_context: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    app_brain: str = dspy.InputField()
    qa_pairs: str = dspy.InputField()
    upstream: str = dspy.InputField()
    current_rows: str = dspy.InputField()
    locked_rows: str = dspy.InputField()
    result: AssumptionsOutput = dspy.OutputField()


class AssumptionsModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(AssumptionsSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_assumptions(**kwargs) -> dict:
    if _is_mock():
        return _load_fixture("assumptions")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: AssumptionsModule()(**kwargs))


# ── §9b: constraints ──────────────────────────────────────────────────────────

class ConstraintRow(BaseModel):
    row_key: str
    constraint_text: str
    constraint_type: Literal["regulatory", "technical", "timeline", "budget", "organisational", "business"]
    source_ref: str


class ConstraintsOutput(BaseModel):
    constraints: list[ConstraintRow]
    open_questions: list[BrdOpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


class ConstraintsSignature(dspy.Signature):
    """Write §9b Constraints for a BRD.

    Document non-negotiable constraints: regulatory, technical, timeline, budget.
    Ground in App Brain limitations/gotchas and doc sections. Use CON-001 row_keys.
    """
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    cb_context: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    app_brain: str = dspy.InputField()
    qa_pairs: str = dspy.InputField()
    upstream: str = dspy.InputField()
    current_rows: str = dspy.InputField()
    locked_rows: str = dspy.InputField()
    result: ConstraintsOutput = dspy.OutputField()


class ConstraintsModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(ConstraintsSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_constraints(**kwargs) -> dict:
    if _is_mock():
        return _load_fixture("constraints")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: ConstraintsModule()(**kwargs))


# ── §9c: dependencies ─────────────────────────────────────────────────────────

class DependencyRow(BaseModel):
    row_key: str
    dependency: str
    dependency_type: Literal["external", "internal", "vendor", "regulatory"]
    owner: str
    due_date: str


class DependenciesOutput(BaseModel):
    dependencies: list[DependencyRow]
    open_questions: list[BrdOpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


class DependenciesSignature(dspy.Signature):
    """Write §9c External Dependencies for a BRD.

    List every external team, system, or vendor the initiative depends on.
    Ground in App Brain integration facts. Use DEP-001 row_keys.
    """
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    cb_context: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    app_brain: str = dspy.InputField()
    qa_pairs: str = dspy.InputField()
    upstream: str = dspy.InputField()
    current_rows: str = dspy.InputField()
    locked_rows: str = dspy.InputField()
    result: DependenciesOutput = dspy.OutputField()


class DependenciesModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(DependenciesSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_dependencies(**kwargs) -> dict:
    if _is_mock():
        return _load_fixture("dependencies")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: DependenciesModule()(**kwargs))


# ── §10: risks ────────────────────────────────────────────────────────────────

class RiskRow(BaseModel):
    row_key: str
    risk: str
    description: str
    severity: Literal["critical", "high", "medium", "low"]
    likelihood: Literal["high", "medium", "low"]
    mitigation: str = Field(description="Non-empty mitigation strategy required")
    owner: str


class RisksOutput(BaseModel):
    risks: list[RiskRow]
    traceability: list[TraceabilityRow] = Field(description="Outward traces for each risk; every risk must have ≥1 trace to a CB scope_item, context_map, or doc section")
    open_questions: list[BrdOpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


class RisksSignature(dspy.Signature):
    """Write §10 Risks & Issues for a BRD.

    Identify all business, delivery, and operational risks. Ground in App Brain
    gotchas, CB out_of_scope items, and document evidence. Every risk MUST have
    a non-empty mitigation. Use RSK-001 row_keys.
    For each risk produce ≥1 traceability entry: source_row_key is the RSK-xxx key,
    target_kind is cb_scope_item, cb_text_block, app_fact, or doc_section,
    target_ref is the source row_key or document reference.
    """
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    cb_context: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    app_brain: str = dspy.InputField()
    qa_pairs: str = dspy.InputField()
    upstream: str = dspy.InputField()
    current_rows: str = dspy.InputField()
    locked_rows: str = dspy.InputField()
    result: RisksOutput = dspy.OutputField()


class RisksModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(RisksSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_risks(**kwargs) -> dict:
    if _is_mock():
        return _load_fixture("risks")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: RisksModule()(**kwargs))


# ── §11a: implementation_phases ───────────────────────────────────────────────

class PhaseRow(BaseModel):
    row_key: str
    phase_name: str
    description: str
    target_date: str
    included_br_refs: list[str] = Field(description="BR row_keys in this phase")


class ImplementationPhasesOutput(BaseModel):
    phases: list[PhaseRow]
    open_questions: list[BrdOpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


class ImplementationPhasesSignature(dspy.Signature):
    """Write §11a Implementation Phases for a BRD.

    Group BRs into logical delivery phases (MVP → Phase 2 → …). Ground in CB
    milestones and stakeholder priorities. Use PH-001 row_keys.
    """
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    cb_context: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    app_brain: str = dspy.InputField()
    qa_pairs: str = dspy.InputField()
    upstream: str = dspy.InputField()
    current_rows: str = dspy.InputField()
    locked_rows: str = dspy.InputField()
    result: ImplementationPhasesOutput = dspy.OutputField()


class ImplementationPhasesModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(ImplementationPhasesSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_implementation_phases(**kwargs) -> dict:
    if _is_mock():
        return _load_fixture("implementation_phases")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: ImplementationPhasesModule()(**kwargs))


# ── §11b: milestones ──────────────────────────────────────────────────────────

class BrdMilestoneRow(BaseModel):
    row_key: str
    milestone: str
    target: str
    description: str
    phase_ref: str | None = None
    cb_milestone_ref: str | None = None


class BrdMilestonesOutput(BaseModel):
    milestones: list[BrdMilestoneRow]
    open_questions: list[BrdOpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


class BrdMilestonesSignature(dspy.Signature):
    """Write §11b Milestones for a BRD.

    Derive milestones from delivery phases and CB milestones. Reference phases via
    phase_ref and CB milestones via cb_milestone_ref. Use MS-001 row_keys.
    """
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    cb_context: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    app_brain: str = dspy.InputField()
    qa_pairs: str = dspy.InputField()
    upstream: str = dspy.InputField()
    current_rows: str = dspy.InputField()
    locked_rows: str = dspy.InputField()
    result: BrdMilestonesOutput = dspy.OutputField()


class BrdMilestonesModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(BrdMilestonesSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_milestones(**kwargs) -> dict:
    if _is_mock():
        return _load_fixture("milestones_brd")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: BrdMilestonesModule()(**kwargs))


# ── §12: kpis ─────────────────────────────────────────────────────────────────

class KpiRow(BaseModel):
    row_key: str
    kpi_name: str
    description: str
    baseline: str = Field(description="Current state value, or 'TBD'")
    target: str = Field(description="Specific numeric or qualitative target — never empty")
    timeframe: str = Field(description="When target must be achieved — never empty")
    data_source: str
    objective_ref: str | None = None
    cb_metric_ref: str | None = None


class KpisOutput(BaseModel):
    kpis: list[KpiRow] = Field(description="One KPI per objective, plus any from CB metrics")
    traceability: list[TraceabilityRow] = Field(description="Outward traces for each KPI; every KPI must have ≥1 trace to a CB metric or CB outcome")
    open_questions: list[BrdOpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


class KpisSignature(dspy.Signature):
    """Write §12 KPIs for a BRD.

    For every objective and CB metric derive a KPI with non-empty baseline, target,
    and timeframe. Link to objectives via objective_ref and CB metrics via cb_metric_ref.
    Use KPI-001 row_keys. For each KPI produce ≥1 traceability entry: source_row_key
    is the KPI-xxx key, target_kind is cb_metric or cb_outcome, target_ref is the
    CB metric/outcome row_key it measures.
    """
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    cb_context: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    app_brain: str = dspy.InputField()
    qa_pairs: str = dspy.InputField()
    upstream: str = dspy.InputField()
    current_rows: str = dspy.InputField()
    locked_rows: str = dspy.InputField()
    result: KpisOutput = dspy.OutputField()


class KpisModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(KpisSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_kpis(**kwargs) -> dict:
    if _is_mock():
        return _load_fixture("kpis")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: KpisModule()(**kwargs))


# ── §13a: open_questions ──────────────────────────────────────────────────────

class OpenQuestionRow(BaseModel):
    row_key: str
    question: str
    context: str
    owner: str
    due_date: str


class OpenQuestionsOutput(BaseModel):
    open_questions_list: list[OpenQuestionRow]
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


class OpenQuestionsSignature(dspy.Signature):
    """Write §13a Open Questions for a BRD.

    List unresolved questions from discover Q&A gaps and risks. Each must have
    context, owner, and due_date. Use OQ-001 row_keys.
    """
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    cb_context: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    app_brain: str = dspy.InputField()
    qa_pairs: str = dspy.InputField()
    upstream: str = dspy.InputField()
    current_rows: str = dspy.InputField()
    locked_rows: str = dspy.InputField()
    result: OpenQuestionsOutput = dspy.OutputField()


class OpenQuestionsModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(OpenQuestionsSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_open_questions(**kwargs) -> dict:
    if _is_mock():
        return _load_fixture("open_questions")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: OpenQuestionsModule()(**kwargs))


# ── §13b: decisions ───────────────────────────────────────────────────────────

class DecisionRow(BaseModel):
    row_key: str
    decision: str
    rationale: str
    owner: str
    decision_date: str
    alternatives_considered: str


class DecisionsOutput(BaseModel):
    decisions: list[DecisionRow]
    open_questions: list[BrdOpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


class DecisionsSignature(dspy.Signature):
    """Write §13b Key Decisions for a BRD.

    Document decisions already made that shaped this BRD. Include rationale and
    alternatives considered. Use DEC-001 row_keys.
    """
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    cb_context: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    app_brain: str = dspy.InputField()
    qa_pairs: str = dspy.InputField()
    upstream: str = dspy.InputField()
    current_rows: str = dspy.InputField()
    locked_rows: str = dspy.InputField()
    result: DecisionsOutput = dspy.OutputField()


class DecisionsModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(DecisionsSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_decisions(**kwargs) -> dict:
    if _is_mock():
        return _load_fixture("decisions")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: DecisionsModule()(**kwargs))


# ── §14a: references ──────────────────────────────────────────────────────────

class ReferenceRow(BaseModel):
    row_key: str
    title: str
    reference_type: Literal["document", "standard", "regulation", "system"]
    location: str
    description: str


class ReferencesOutput(BaseModel):
    references: list[ReferenceRow]
    open_questions: list[BrdOpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


class ReferencesSignature(dspy.Signature):
    """Write §14a References for a BRD.

    List all source documents, standards, and artefacts referenced. Ground in the
    document inventory provided. Use REF-001 row_keys.
    """
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    cb_context: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    app_brain: str = dspy.InputField()
    qa_pairs: str = dspy.InputField()
    upstream: str = dspy.InputField()
    current_rows: str = dspy.InputField()
    locked_rows: str = dspy.InputField()
    result: ReferencesOutput = dspy.OutputField()


class ReferencesModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(ReferencesSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_references(**kwargs) -> dict:
    if _is_mock():
        return _load_fixture("references")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: ReferencesModule()(**kwargs))


# ── §14b: glossary ────────────────────────────────────────────────────────────

class GlossaryEntryRow(BaseModel):
    row_key: str
    term: str
    definition: str
    source_ref: str


class GlossaryOutput(BaseModel):
    glossary: list[GlossaryEntryRow]
    open_questions: list[BrdOpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


class GlossarySignature(dspy.Signature):
    """Write §14b Glossary for a BRD.

    Define all acronyms, domain terms, and jargon. Definitions must be clear and
    non-circular. Ground in App Brain and document sections. Use GLO-001 row_keys.
    """
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    cb_context: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    app_brain: str = dspy.InputField()
    qa_pairs: str = dspy.InputField()
    upstream: str = dspy.InputField()
    current_rows: str = dspy.InputField()
    locked_rows: str = dspy.InputField()
    result: GlossaryOutput = dspy.OutputField()


class GlossaryModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(GlossarySignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_glossary(**kwargs) -> dict:
    if _is_mock():
        return _load_fixture("glossary")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: GlossaryModule()(**kwargs))


# ── Dispatcher ────────────────────────────────────────────────────────────────

_BRD_RUNNERS: dict[str, Any] = {
    "business_context":       run_business_context,
    "problem_statement":      run_problem_statement,
    "objectives":             run_objectives,
    "stakeholders":           run_stakeholders,
    "actors":                 run_actors,
    "scope":                  run_scope,
    "asis_process":           run_asis_process,
    "tobe_process":           run_tobe_process,
    "business_requirements":  run_business_requirements,
    "data_entities":          run_data_entities,
    "report_requirements":    run_report_requirements,
    "assumptions":            run_assumptions,
    "constraints":            run_constraints,
    "dependencies":           run_dependencies,
    "risks":                  run_risks,
    "implementation_phases":  run_implementation_phases,
    "milestones":             run_milestones,
    "kpis":                   run_kpis,
    "open_questions":         run_open_questions,
    "decisions":              run_decisions,
    "references":             run_references,
    "glossary":               run_glossary,
}


async def run_brd_unit(unit_key: str, **kwargs) -> dict:
    runner = _BRD_RUNNERS.get(unit_key)
    if runner is None:
        raise ValueError(f"Unknown BRD unit_key: {unit_key}")
    return await runner(**kwargs)
