"""Tests for the DSPy skill wrappers in mock mode — no DB, no API keys.

Conftest sets LLM_PROVIDER=mock, so each run_* wrapper returns its fixture
deterministically. These assert the fixtures satisfy the PRD minimums and that
the SkillEngine fallback (still used for any future Jinja skill) behaves.
"""
import json

import pytest

from app.services.llm.mock_provider import MockProvider
from app.services.skills.dspy_intake import (
    run_gap_detector, run_requirement_extractor, run_requirement_understanding,
)
from app.services.skills.dspy_specs import (
    run_functional_spec, run_reviewer, run_technical_spec, run_user_stories,
)

_REQS_JSON = json.dumps({
    "functional_requirements": [], "non_functional_requirements": [],
    "constraints": [], "assumptions": [], "stakeholders": [],
})
_FUNC_JSON = json.dumps({"overview": "Test", "objectives": [], "scope": "test", "features": []})


@pytest.mark.asyncio
async def test_requirement_extractor_returns_expected_keys():
    result = await run_requirement_extractor("Test Project", "Users log in and upload docs.")
    for key in ("functional_requirements", "non_functional_requirements", "constraints",
                "assumptions", "stakeholders"):
        assert key in result
    assert len(result["functional_requirements"]) >= 5  # PRD requirement


@pytest.mark.asyncio
async def test_gap_detector_returns_gaps():
    result = await run_gap_detector(_REQS_JSON)
    assert "gaps" in result
    assert len(result["gaps"]) >= 3  # PRD requirement
    for gap in result["gaps"]:
        assert {"id", "question", "category", "severity"} <= gap.keys()


@pytest.mark.asyncio
async def test_requirement_understanding_returns_structure():
    result = await run_requirement_understanding(
        "Test Project", "BU", "desc", "(no source sections)", "(no app facts)", "(none yet)",
    )
    assert "objective" in result
    assert "field_confidence" in result


@pytest.mark.asyncio
async def test_functional_spec_returns_structure():
    result = await run_functional_spec("Test Project", _REQS_JSON, "[]")
    for key in ("overview", "objectives", "scope", "features"):
        assert key in result


@pytest.mark.asyncio
async def test_technical_spec_returns_structure():
    result = await run_technical_spec("Test Project", _FUNC_JSON, _REQS_JSON)
    for key in ("architecture_overview", "components", "data_models", "api_endpoints",
                "tech_stack", "risks"):
        assert key in result


@pytest.mark.asyncio
async def test_user_stories_returns_at_least_5():
    result = await run_user_stories("Test Project", _FUNC_JSON, _REQS_JSON)
    assert "stories" in result
    assert len(result["stories"]) >= 5  # PRD requirement


@pytest.mark.asyncio
async def test_reviewer_returns_at_least_4_comments():
    result = await run_reviewer("Test Project", _FUNC_JSON, "{}", "{}", _REQS_JSON)
    assert "comments" in result
    assert len(result["comments"]) >= 4  # PRD requirement


@pytest.mark.asyncio
async def test_mock_provider_unknown_skill_returns_empty():
    result = await MockProvider().complete(prompt="test", system="sys", skill_name="unknown_skill")
    assert result == "{}"


def test_all_fixtures_are_valid_json():
    """Every fixture referenced by the DSPy mock path must be valid JSON."""
    from app.services.skills.mock_fixtures import mock_fixture
    for name in (
        "requirement_extractor", "gap_detector", "requirement_understanding",
        "functional_spec", "technical_spec", "user_stories", "reviewer",
        "source_tree_search", "fact_extractor",
    ):
        assert isinstance(mock_fixture(name), dict), f"Fixture {name} should be a dict"
