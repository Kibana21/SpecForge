"""DSPy modules for NFR generation — single-phase, 9 units.

Mirrors dspy_brd.py:
- Pydantic output models (1:1 with the typed columns)
- DSPy Signature with a typed docstring (instruction comes from the manifest)
- DSPy Module (ChainOfThought)
- Async runner (mock path → fixture, real path → Gemini)

The 7 category units share NfrCategorySignature (the manifest supplies a per-category
instruction via the `unit_instruction` input + a pinned `category`); overview and
governance have their own signatures. run_nfr_unit is the dispatcher.
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

MoSCoW = Literal["must", "should", "could", "wont"]
Confidence = Literal["high", "medium", "low"]


def _configure() -> None:
    from app.services.skills.fact_extractor.dspy_extractor import _configure_dspy
    _configure_dspy()


def _is_mock() -> bool:
    from app.config import get_settings
    return get_settings().llm_provider == "mock"


def _load_fixture(name: str) -> dict:
    path = _FIXTURE_DIR / f"nfr_{name}.json"
    with open(path) as f:
        return json.load(f)


# ── Common row / output models ──────────────────────────────────────────────────

class NfrOpenQuestion(BaseModel):
    question: str
    field: str
    why: str
    example: str = ""


class NfrTraceabilityRow(BaseModel):
    source_row_key: str
    target_kind: Literal[
        "brd_objective", "brd_business_requirement", "brd_kpi", "brd_risk",
        "brd_text_block", "app_fact", "doc_section", "discover_qa", "within_nfr",
    ]
    target_ref: str
    target_label: str = ""
    confidence: Confidence = "high"


class NfrRequirementRow(BaseModel):
    row_key: str = Field(description="Global sequential NFR-001, NFR-002, … (no gaps)")
    category: Literal[
        "performance", "security", "availability", "usability",
        "scalability", "maintainability", "portability",
    ]
    attribute: str = Field(description="Short quality-attribute label")
    requirement: str = Field(description="Testable, unambiguous, SOLUTION-AGNOSTIC statement")
    priority: MoSCoW
    rationale: str = ""
    measurement: str = Field(description="Metric + threshold making it verifiable")
    brd_refs: list[str] = Field(default_factory=list)
    na: bool = False


class NfrTextBlockRow(BaseModel):
    row_key: str
    block_kind: Literal["overview", "objectives"]
    content: str


class NfrRiskRow(BaseModel):
    row_key: str
    risk_id: str = ""
    description: str = ""
    affected_attribute: str = ""
    impact: str = ""
    likelihood: str = ""
    mitigation: str = ""
    owner: str = ""
    risk_status: str = "open"


class NfrTradeoffRow(BaseModel):
    row_key: str
    tradeoff: str = ""
    options_considered: list[str] = Field(default_factory=list)
    decision: str = ""
    rationale: str = ""
    decided_on: str = ""
    decision_maker: str = ""


class NfrOpenQuestionRow(BaseModel):
    row_key: str
    question: str = ""
    owner: str = ""
    due_date: str = ""
    oq_status: str = "open"


class NfrDecisionRow(BaseModel):
    row_key: str
    description: str = ""
    owner: str = ""
    target_date: str = ""
    decision_status: str = "pending"


class NfrReferenceRow(BaseModel):
    row_key: str
    ref_type: str = ""
    title: str = ""
    location: str = ""
    notes: str = ""


class NfrGlossaryRow(BaseModel):
    row_key: str
    term: str = ""
    definition: str = ""


class NfrCategoryOutput(BaseModel):
    requirements: list[NfrRequirementRow] = Field(default_factory=list)
    traceability: list[NfrTraceabilityRow] = Field(default_factory=list)
    open_questions: list[NfrOpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Confidence


class NfrOverviewOutput(BaseModel):
    text_blocks: list[NfrTextBlockRow] = Field(default_factory=list)
    open_questions: list[NfrOpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Confidence


class NfrGovernanceOutput(BaseModel):
    risks: list[NfrRiskRow] = Field(default_factory=list)
    tradeoffs: list[NfrTradeoffRow] = Field(default_factory=list)
    open_questions_list: list[NfrOpenQuestionRow] = Field(default_factory=list)
    decisions: list[NfrDecisionRow] = Field(default_factory=list)
    references: list[NfrReferenceRow] = Field(default_factory=list)
    glossary: list[NfrGlossaryRow] = Field(default_factory=list)
    open_questions: list[NfrOpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Confidence


# ── Signatures ────────────────────────────────────────────────────────────────

class NfrCategorySignature(dspy.Signature):
    """Author the non-functional requirements for ONE quality category.

    Follow `unit_instruction` exactly. Requirements MUST be testable, unambiguous,
    SOLUTION-AGNOSTIC (no technology/product names), each carrying a MoSCoW priority
    and a `measurement` (metric + threshold). Continue GLOBAL NFR-nnn numbering using
    `existing_nfr_keys` so keys never collide across categories; reproduce `locked_rows`
    verbatim. Set `category` on every requirement. Emit a traceability row for every
    requirement linking it to ≥1 BRD objective/business requirement.
    """
    unit_instruction: str = dspy.InputField(desc="Per-category authoring guidance")
    category: str = dspy.InputField(desc="The NFR category to author")
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    brief: str = dspy.InputField(desc="Optional ad-hoc requirements supplied by the user")
    cb_context: str = dspy.InputField(desc="Validated Concept Brief context")
    brd_context: str = dspy.InputField(desc="Validated BRD context (objectives, BRs, KPIs, …)")
    source_sections: str = dspy.InputField(desc="Retrieved project document sections [S#]")
    app_brain: str = dspy.InputField(desc="In-scope application facts")
    qa_pairs: str = dspy.InputField(desc="Discover Q&A relevant to this unit")
    existing_nfr_keys: str = dspy.InputField(desc="JSON list of all NFR row_keys already in use (continue numbering)")
    current_rows: str = dspy.InputField(desc="This category's current rows for idempotent regen")
    locked_rows: str = dspy.InputField(desc="Locked rows to reproduce verbatim")
    result: NfrCategoryOutput = dspy.OutputField()


class NfrOverviewSignature(dspy.Signature):
    """Write the NFR document's Context overview and Objectives.

    Follow `unit_instruction`. Ground in the validated BRD + Concept Brief + any ad-hoc
    brief. Emit exactly two text blocks: 'NFR-TB-overview' (block_kind='overview') and
    'NFR-TB-objectives' (block_kind='objectives').
    """
    unit_instruction: str = dspy.InputField()
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    brief: str = dspy.InputField()
    cb_context: str = dspy.InputField()
    brd_context: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    app_brain: str = dspy.InputField()
    qa_pairs: str = dspy.InputField()
    current_rows: str = dspy.InputField()
    locked_rows: str = dspy.InputField()
    result: NfrOverviewOutput = dspy.OutputField()


class NfrGovernanceSignature(dspy.Signature):
    """Author the NFR governance sections (risks, trade-offs, open questions, pending
    decisions, references, glossary), informed by the requirements already produced
    across all categories (provided in `upstream`). Follow `unit_instruction`.
    """
    unit_instruction: str = dspy.InputField()
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    brief: str = dspy.InputField()
    cb_context: str = dspy.InputField()
    brd_context: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    app_brain: str = dspy.InputField()
    qa_pairs: str = dspy.InputField()
    upstream: str = dspy.InputField(desc="JSON of all NFR requirements produced so far")
    current_rows: str = dspy.InputField()
    locked_rows: str = dspy.InputField()
    result: NfrGovernanceOutput = dspy.OutputField()


class NfrCategoryModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(NfrCategorySignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


class NfrOverviewModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(NfrOverviewSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


class NfrGovernanceModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(NfrGovernanceSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


# ── Dispatcher ──────────────────────────────────────────────────────────────────

_CATEGORY_KEYS = {
    "performance", "security", "availability", "usability",
    "scalability", "maintainability", "portability",
}


async def run_nfr_unit(unit_key: str, **kwargs) -> dict:
    """Run one NFR DSPy unit. Mock path loads nfr_<unit_key>.json verbatim."""
    if _is_mock():
        return _load_fixture(unit_key)
    _configure()
    loop = asyncio.get_running_loop()
    if unit_key == "overview":
        module = NfrOverviewModule()
    elif unit_key == "governance":
        module = NfrGovernanceModule()
    elif unit_key in _CATEGORY_KEYS:
        module = NfrCategoryModule()
    else:
        raise ValueError(f"Unknown NFR unit_key: {unit_key}")
    return await loop.run_in_executor(None, lambda: module(**kwargs))
