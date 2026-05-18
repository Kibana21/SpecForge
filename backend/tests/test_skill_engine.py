"""Tests for SkillEngine with MockProvider — no DB, no API keys required."""
import json
from pathlib import Path

import pytest

from app.services.llm.mock_provider import MockProvider
from app.services.skills.skill_engine import SkillEngine, SkillValidationError

SKILL_NAMES = [
    "requirement_extractor",
    "gap_detector",
    "functional_spec",
    "technical_spec",
    "user_stories",
    "reviewer",
]

# Minimal context satisfying all skill templates (real values used in Phase C)
SAMPLE_CONTEXT = {
    "project_name": "Test Project",
    "document_text": "Users should be able to log in and upload documents.",
    "extracted_requirements": json.dumps({"functional_requirements": [], "non_functional_requirements": [], "constraints": [], "assumptions": [], "stakeholders": []}),
    "resolved_gap_answers": "[]",
    "functional_spec": json.dumps({"overview": "Test", "objectives": [], "scope": "test", "features": []}),
    "technical_spec": json.dumps({"architecture_overview": "Test", "components": [], "data_models": [], "api_endpoints": [], "tech_stack": {}, "risks": []}),
    "user_stories": json.dumps({"stories": []}),
}


@pytest.fixture
def engine() -> SkillEngine:
    return SkillEngine()


@pytest.fixture
def mock_provider() -> MockProvider:
    return MockProvider()


@pytest.mark.asyncio
@pytest.mark.parametrize("skill_name", SKILL_NAMES)
async def test_skill_runs_successfully(engine: SkillEngine, mock_provider: MockProvider, skill_name: str):
    result = await engine.run(skill_name, SAMPLE_CONTEXT, mock_provider)
    assert isinstance(result, (dict, list)), f"Expected dict or list, got {type(result)}"


@pytest.mark.asyncio
async def test_requirement_extractor_returns_expected_keys(engine: SkillEngine, mock_provider: MockProvider):
    result = await engine.run("requirement_extractor", SAMPLE_CONTEXT, mock_provider)
    assert "functional_requirements" in result
    assert "non_functional_requirements" in result
    assert "constraints" in result
    assert "assumptions" in result
    assert "stakeholders" in result
    assert len(result["functional_requirements"]) >= 5  # PRD requirement


@pytest.mark.asyncio
async def test_gap_detector_returns_gaps(engine: SkillEngine, mock_provider: MockProvider):
    result = await engine.run("gap_detector", SAMPLE_CONTEXT, mock_provider)
    assert "gaps" in result
    assert len(result["gaps"]) >= 3  # PRD requirement
    for gap in result["gaps"]:
        assert "id" in gap
        assert "question" in gap
        assert "category" in gap
        assert "severity" in gap


@pytest.mark.asyncio
async def test_user_stories_returns_at_least_5(engine: SkillEngine, mock_provider: MockProvider):
    result = await engine.run("user_stories", SAMPLE_CONTEXT, mock_provider)
    assert "stories" in result
    assert len(result["stories"]) >= 5  # PRD requirement


@pytest.mark.asyncio
async def test_reviewer_returns_at_least_4_comments(engine: SkillEngine, mock_provider: MockProvider):
    result = await engine.run("reviewer", SAMPLE_CONTEXT, mock_provider)
    assert "comments" in result
    assert len(result["comments"]) >= 4  # PRD requirement


@pytest.mark.asyncio
async def test_skill_engine_raises_on_unknown_skill(engine: SkillEngine, mock_provider: MockProvider):
    with pytest.raises(FileNotFoundError):
        await engine.run("nonexistent_skill", SAMPLE_CONTEXT, mock_provider)


@pytest.mark.asyncio
async def test_mock_provider_returns_string(mock_provider: MockProvider):
    result = await mock_provider.complete(
        prompt="test", system="test system", skill_name="requirement_extractor"
    )
    assert isinstance(result, str)
    parsed = json.loads(result)
    assert isinstance(parsed, dict)


@pytest.mark.asyncio
async def test_mock_provider_unknown_skill_returns_empty(mock_provider: MockProvider):
    result = await mock_provider.complete(
        prompt="test", system="test system", skill_name="unknown_skill"
    )
    assert result == "{}"


def test_all_fixtures_are_valid_json():
    """Ensure every fixture file is valid JSON before any runtime call."""
    from app.services.llm.mock_provider import FIXTURES_DIR, _SKILL_FIXTURE_MAP
    for skill, fname in _SKILL_FIXTURE_MAP.items():
        path = FIXTURES_DIR / fname
        assert path.exists(), f"Fixture missing for skill={skill}: {path}"
        data = json.loads(path.read_text())
        assert isinstance(data, dict), f"Fixture for {skill} should be a dict"
