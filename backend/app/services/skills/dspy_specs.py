"""DSPy modules for spec generation: functional, technical, user stories, review.
Replaces the Jinja SkillEngine skills; mock path returns existing fixtures.

`app_brain_context` is the compiled Brain Wiki grounding (may be empty).
"""
import asyncio
import logging
from typing import Literal

import dspy
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)


def _configure():
    from app.services.skills.fact_extractor.dspy_extractor import _configure_dspy
    _configure_dspy()


def _is_mock() -> bool:
    from app.config import get_settings
    return get_settings().llm_provider == "mock"


# ── Functional spec ─────────────────────────────────────────────────────────────

class Feature(BaseModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    acceptance_criteria: list[str] = Field(default_factory=list)


class FunctionalSpec(BaseModel):
    overview: str
    objectives: list[str] = Field(default_factory=list)
    scope: str
    features: list[Feature] = Field(default_factory=list)


class FunctionalSpecSignature(dspy.Signature):
    """Generate a structured Functional Specification as a senior Business Analyst.

    Base every statement on the provided requirements — do not add unmentioned
    features. Incorporate resolved gap answers. Features must have concrete,
    testable acceptance criteria. When Application Brain context is provided,
    ground features in it and respect documented capabilities/constraints. Write
    in clear, non-technical language.
    """

    project_name: str = dspy.InputField()
    extracted_requirements: str = dspy.InputField()
    resolved_gap_answers: str = dspy.InputField()
    app_brain_context: str = dspy.InputField(desc="Compiled app knowledge, or empty")
    spec: FunctionalSpec = dspy.OutputField()


class FunctionalSpecModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(FunctionalSpecSignature)

    def forward(self, project_name, extracted_requirements, resolved_gap_answers, app_brain_context) -> dict:
        return self.predict(
            project_name=project_name, extracted_requirements=extracted_requirements,
            resolved_gap_answers=resolved_gap_answers, app_brain_context=app_brain_context,
        ).spec.model_dump()


async def run_functional_spec(project_name, extracted_requirements, resolved_gap_answers, app_brain_context="") -> dict:
    if _is_mock():
        from app.services.skills.mock_fixtures import mock_fixture
        return mock_fixture("functional_spec")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, FunctionalSpecModule(),
        project_name, extracted_requirements, resolved_gap_answers, app_brain_context,
    )


# ── Technical spec ──────────────────────────────────────────────────────────────

class NamedItem(BaseModel):
    name: str
    description: str


class ApiEndpoint(BaseModel):
    method: str
    path: str
    description: str


class Risk(BaseModel):
    risk: str
    mitigation: str


class TechnicalSpec(BaseModel):
    architecture_overview: str
    components: list[NamedItem] = Field(default_factory=list)
    data_models: list[NamedItem] = Field(default_factory=list)
    api_endpoints: list[ApiEndpoint] = Field(default_factory=list)
    tech_stack: dict[str, str] = Field(default_factory=dict)
    risks: list[Risk] = Field(default_factory=list)


class TechnicalSpecSignature(dspy.Signature):
    """Generate a structured Technical Specification as a senior Software Architect.

    Every architectural decision must trace to a functional requirement. List
    specific technologies (no vague terms). Data models include key fields and
    relationships; API endpoints include method, path, and purpose; risks are
    specific and actionable. When Application Brain context is provided, align
    components, data models, endpoints, and tech stack with those documented
    systems and their constraints/integrations.
    """

    project_name: str = dspy.InputField()
    functional_spec: str = dspy.InputField()
    extracted_requirements: str = dspy.InputField()
    app_brain_context: str = dspy.InputField(desc="Compiled app knowledge, or empty")
    spec: TechnicalSpec = dspy.OutputField()


class TechnicalSpecModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(TechnicalSpecSignature)

    def forward(self, project_name, functional_spec, extracted_requirements, app_brain_context) -> dict:
        return self.predict(
            project_name=project_name, functional_spec=functional_spec,
            extracted_requirements=extracted_requirements, app_brain_context=app_brain_context,
        ).spec.model_dump()


async def run_technical_spec(project_name, functional_spec, extracted_requirements, app_brain_context="") -> dict:
    if _is_mock():
        from app.services.skills.mock_fixtures import mock_fixture
        return mock_fixture("technical_spec")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, TechnicalSpecModule(),
        project_name, functional_spec, extracted_requirements, app_brain_context,
    )


# ── User stories ────────────────────────────────────────────────────────────────

class UserStory(BaseModel):
    id: str
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    acceptance_criteria: list[str] = Field(default_factory=list)
    story_points: int = Field(ge=1, le=13)
    labels: list[str] = Field(default_factory=list)


class UserStories(BaseModel):
    stories: list[UserStory] = Field(default_factory=list)


class UserStoriesSignature(dspy.Signature):
    """Generate granular, Jira-ready User Stories as an Agile coach / Product Owner.

    Format: "As a [persona], I want [action] so that [benefit]." Each feature
    yields multiple granular stories — never merge features. Acceptance criteria
    are specific, testable, present tense. Story points are Fibonacci (1,2,3,5,8,13),
    max 13. Labels are lowercase hyphen-separated. When Application Brain context is
    provided, keep stories consistent with documented capabilities/constraints.
    """

    project_name: str = dspy.InputField()
    functional_spec: str = dspy.InputField()
    extracted_requirements: str = dspy.InputField()
    app_brain_context: str = dspy.InputField(desc="Compiled app knowledge, or empty")
    result: UserStories = dspy.OutputField()


class UserStoriesModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(UserStoriesSignature)

    def forward(self, project_name, functional_spec, extracted_requirements, app_brain_context) -> dict:
        return self.predict(
            project_name=project_name, functional_spec=functional_spec,
            extracted_requirements=extracted_requirements, app_brain_context=app_brain_context,
        ).result.model_dump()


async def run_user_stories(project_name, functional_spec, extracted_requirements, app_brain_context="") -> dict:
    if _is_mock():
        from app.services.skills.mock_fixtures import mock_fixture
        return mock_fixture("user_stories")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, UserStoriesModule(),
        project_name, functional_spec, extracted_requirements, app_brain_context,
    )


# ── Reviewer ────────────────────────────────────────────────────────────────────

class ReviewComment(BaseModel):
    id: str
    section: str = Field(min_length=1)
    comment: str = Field(min_length=1)
    severity: Literal["critical", "warning", "suggestion"]
    category: Literal["completeness", "ambiguity", "security", "data", "implementation"]


class ReviewResult(BaseModel):
    comments: list[ReviewComment] = Field(default_factory=list)


class ReviewerSignature(dspy.Signature):
    """Review generated specs for completeness, ambiguity, and risk as a senior QA.

    Comments reference a specific spec section. Only raise genuine issues — never
    fabricate. When Application Brain context is provided, treat it as authoritative:
    flag spec claims that CONTRADICT it (critical/warning) and material claims it
    does not support (completeness/ambiguity); don't penalise claims it simply
    doesn't cover. Severity: critical|warning|suggestion. Category: completeness|
    ambiguity|security|data|implementation.
    """

    project_name: str = dspy.InputField()
    functional_spec: str = dspy.InputField()
    technical_spec: str = dspy.InputField()
    user_stories: str = dspy.InputField()
    extracted_requirements: str = dspy.InputField()
    app_brain_context: str = dspy.InputField(desc="Compiled app knowledge, or empty")
    result: ReviewResult = dspy.OutputField()


class ReviewerModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(ReviewerSignature)

    def forward(self, project_name, functional_spec, technical_spec, user_stories, extracted_requirements, app_brain_context) -> dict:
        return self.predict(
            project_name=project_name, functional_spec=functional_spec,
            technical_spec=technical_spec, user_stories=user_stories,
            extracted_requirements=extracted_requirements, app_brain_context=app_brain_context,
        ).result.model_dump()


async def run_reviewer(project_name, functional_spec, technical_spec, user_stories, extracted_requirements, app_brain_context="") -> dict:
    if _is_mock():
        from app.services.skills.mock_fixtures import mock_fixture
        return mock_fixture("reviewer")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, ReviewerModule(),
        project_name, functional_spec, technical_spec, user_stories, extracted_requirements, app_brain_context,
    )
