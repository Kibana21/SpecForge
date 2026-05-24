"""DSPy modules for E2 intake skills: requirement extraction, gap detection,
and Requirement Understanding (RU). Replaces the Jinja SkillEngine skills.

Mock path (LLM_PROVIDER=mock) returns the existing fixtures so test assertions
on fixture content keep holding.
"""
import asyncio
import logging
from typing import Literal

import dspy
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

Confidence = Literal["high", "medium", "low"]


def _configure():
    from app.services.skills.fact_extractor.dspy_extractor import _configure_dspy
    _configure_dspy()


def _is_mock() -> bool:
    from app.config import get_settings
    return get_settings().llm_provider == "mock"


# ── Requirement extraction ──────────────────────────────────────────────────────

class RequirementItem(BaseModel):
    id: str
    text: str = Field(min_length=1)
    source_reference: str | None = None
    confidence: Confidence


class ExtractionResult(BaseModel):
    functional_requirements: list[RequirementItem] = Field(default_factory=list)
    non_functional_requirements: list[RequirementItem] = Field(default_factory=list)
    constraints: list[RequirementItem] = Field(default_factory=list)
    assumptions: list[RequirementItem] = Field(default_factory=list)
    stakeholders: list[RequirementItem] = Field(default_factory=list)


class RequirementExtractorSignature(dspy.Signature):
    """Extract structured requirements from raw document text as a Business Analyst.

    Extract ONLY information present in the document — never invent requirements.
    Categorise each as functional, non-functional, constraint, assumption, or
    stakeholder. Quote a short excerpt as source_reference (or null). Assign
    confidence: high (explicit), medium (implied), low (inferred). Give each a
    short unique id (FR-1, NFR-1, CON-1, ASM-1, STK-1). Empty arrays if none.
    """

    project_name: str = dspy.InputField()
    document_text: str = dspy.InputField()
    result: ExtractionResult = dspy.OutputField()


class RequirementExtractorModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(RequirementExtractorSignature)

    def forward(self, project_name: str, document_text: str) -> dict:
        try:
            return self.predict(project_name=project_name, document_text=document_text).result.model_dump()
        except Exception as exc:
            log.error("dspy requirement_extractor failed: %s", exc, exc_info=True)
            return ExtractionResult().model_dump()


async def run_requirement_extractor(project_name: str, document_text: str) -> dict:
    if _is_mock():
        from app.services.skills.mock_fixtures import mock_fixture
        return mock_fixture("requirement_extractor")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, RequirementExtractorModule(), project_name, document_text)


# ── Gap detection ───────────────────────────────────────────────────────────────

class Gap(BaseModel):
    id: str
    question: str = Field(min_length=1)
    category: Literal["scope", "data", "security", "integration", "ux"]
    severity: Literal["blocker", "major", "minor"]


class GapResult(BaseModel):
    gaps: list[Gap] = Field(default_factory=list)


class GapDetectorSignature(dspy.Signature):
    """Detect missing, ambiguous, or under-specified information in extracted
    requirements. Identify genuine gaps only — never fabricate. Categorise each
    (scope|data|security|integration|ux) and set severity (blocker|major|minor).
    Write plain-language questions a BA can answer. Unique ids (GAP-1, …). Empty
    list if no gaps.
    """

    extracted_requirements: str = dspy.InputField(desc="JSON of the extracted requirements")
    result: GapResult = dspy.OutputField()


class GapDetectorModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(GapDetectorSignature)

    def forward(self, extracted_requirements: str) -> dict:
        try:
            return self.predict(extracted_requirements=extracted_requirements).result.model_dump()
        except Exception as exc:
            log.error("dspy gap_detector failed: %s", exc, exc_info=True)
            return GapResult().model_dump()


async def run_gap_detector(extracted_requirements: str) -> dict:
    if _is_mock():
        from app.services.skills.mock_fixtures import mock_fixture
        return mock_fixture("gap_detector")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, GapDetectorModule(), extracted_requirements)


# ── Requirement Understanding (RU) ──────────────────────────────────────────────

class RUAssumption(BaseModel):
    text: str
    confidence: Confidence | None = None
    source_ref: str | None = None


class RUOpenQuestion(BaseModel):
    question: str
    field: str = ""
    why: str = ""


class RUFieldConfidence(BaseModel):
    confidence: Confidence | None = None
    completeness: int | None = Field(default=None, ge=0, le=100)


class RUCitation(BaseModel):
    marker: str
    kind: Literal["source", "fact"]
    ref: str
    excerpt: str = ""


class RUResult(BaseModel):
    objective: str | None = None
    stakeholders: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    target_process: str | None = None
    functional_areas: list[str] = Field(default_factory=list)
    systems: list[str] = Field(default_factory=list)
    integrations: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    assumptions: list[RUAssumption] = Field(default_factory=list)
    open_questions: list[RUOpenQuestion] = Field(default_factory=list)
    field_confidence: dict[str, RUFieldConfidence] = Field(default_factory=dict)
    citations: list[RUCitation] = Field(default_factory=list)


class RequirementUnderstandingSignature(dspy.Signature):
    """Build a structured Requirement Understanding (RU) from the inputs only —
    project identity, retrieved source sections, in-scope app-brain facts, and
    prior interview Q&A. Do NOT invent facts.

    For every field set field_confidence (high=explicit, medium=implied,
    low=inferred) with a completeness 0–100. Attach citation markers [S#] (source)
    or [F#] (fact) to grounded/inferred claims and list them in citations. Generate
    open_questions ONLY for fields you genuinely cannot infer — each names the
    field it resolves and a short why. Record assumptions you had to make.
    """

    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    description: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    app_facts: str = dspy.InputField()
    qa_pairs: str = dspy.InputField()
    result: RUResult = dspy.OutputField()


class RequirementUnderstandingModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(RequirementUnderstandingSignature)

    def forward(self, project_name, business_unit, description, source_sections, app_facts, qa_pairs) -> dict:
        try:
            return self.predict(
                project_name=project_name, business_unit=business_unit, description=description,
                source_sections=source_sections, app_facts=app_facts, qa_pairs=qa_pairs,
            ).result.model_dump()
        except Exception as exc:
            log.error("dspy requirement_understanding failed: %s", exc, exc_info=True)
            return RUResult().model_dump()


async def run_requirement_understanding(
    project_name: str, business_unit: str, description: str,
    source_sections: str, app_facts: str, qa_pairs: str,
) -> dict:
    if _is_mock():
        from app.services.skills.mock_fixtures import mock_fixture
        return mock_fixture("requirement_understanding")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, RequirementUnderstandingModule(),
        project_name, business_unit, description, source_sections, app_facts, qa_pairs,
    )
