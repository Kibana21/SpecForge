"""DSPy modules for the Concept Brief Discover Phase.

Two modules:
  BriefEnhancerModule   — ✨ Enhance button: enriches user brief using docs + app brain
  DiscoverAnalysisModule — Analyze: checks which of the 14 questions are already answered
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

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


# ── Brief Enhancer ────────────────────────────────────────────────────────────

class BriefEnhancerSignature(dspy.Signature):
    """Synthesise a comprehensive initiative brief from project metadata, source documents,
    and app brain context. Expand and enrich the user's text without contradicting it.
    Ground claims in [D#] excerpts. Solution-agnostic. Cover: business problem, strategic
    driver, customers, as-is state, value, outcomes, KPIs, scope, assumptions, milestones."""

    project_name: str = dspy.InputField(desc="Initiative / project name")
    business_unit: str = dspy.InputField(desc="Owning business unit; '—' if unknown")
    user_brief: str = dspy.InputField(desc="User's initiative description — authoritative, do not contradict")
    project_doc_sections: str = dspy.InputField(desc="[D#]-tagged excerpts from project documents; '(no project documents indexed)' if none")
    app_brain_context: str = dspy.InputField(desc="App brain context: capabilities, limits, KPIs, user segments; '(no linked apps)' if none")
    enhanced_brief: str = dspy.OutputField(desc="200–400 word prose initiative brief covering all 14 discovery areas; solution-agnostic")


# ── Discover Analysis ─────────────────────────────────────────────────────────

class DiscoverAnalysisRow(BaseModel):
    question_key: str = Field(description="Question key, e.g. '1a', '2c'")
    answered: bool = Field(description="True only if context explicitly and specifically answers this; when in doubt, false")
    extracted_answer: str = Field(description="Best excerpt or ≤2-sentence synthesis; specific answer if answered=true, partial hint or '' if false; no fabrication")
    source: str = Field(description="Source layer: 'brief', 'documents', 'app_brain', 'combined', or ''")


class DiscoverAnalysisSignature(dspy.Signature):
    """For each question in questions_json, produce one DiscoverAnalysisRow in the same order.
    Priority: brief > documents > app_brain. answered=true only when the context is explicit
    and the answer stands alone. Do not fabricate. Partial hints go in extracted_answer."""

    project_name: str = dspy.InputField(desc="Initiative / project name")
    business_unit: str = dspy.InputField(desc="Owning business unit; '—' if unknown")
    brief_text: str = dspy.InputField(desc="User's initiative description — highest-priority source")
    project_doc_sections: str = dspy.InputField(desc="[D#]-tagged project document excerpts; '(no project documents indexed)' if none")
    app_brain_context: str = dspy.InputField(desc="App brain context; '(no linked apps)' if none")
    questions_json: str = dspy.InputField(desc='JSON array: [{"key":"1b","text":"..."},...]. Return exactly one row per entry, same order.')
    analyses: list[DiscoverAnalysisRow] = dspy.OutputField(desc="One DiscoverAnalysisRow per question, same order as questions_json input")


# ── Public runners ────────────────────────────────────────────────────────────

async def run_enhance_brief(
    project_name: str,
    business_unit: str,
    user_brief: str,
    project_doc_sections: str,
    app_brain_context: str,
) -> dict:
    if _is_mock():
        return _load_fixture("discover_enhance_brief")

    _configure()
    import asyncio
    module = dspy.ChainOfThought(BriefEnhancerSignature)

    def _run() -> dict:
        pred = module(
            project_name=project_name,
            business_unit=business_unit,
            user_brief=user_brief,
            project_doc_sections=project_doc_sections,
            app_brain_context=app_brain_context,
        )
        return {"enhanced_brief": pred.enhanced_brief}

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _run)


async def run_discover_analysis(
    project_name: str,
    business_unit: str,
    brief_text: str,
    project_doc_sections: str,
    app_brain_context: str,
    questions: list[dict],
) -> list[dict]:
    """Returns list of analysis dicts in the same order as questions."""
    if _is_mock():
        fixture = _load_fixture("discover_analysis")
        rows = fixture.get("analyses", [])
        key_set = {q["key"] for q in questions}
        return [r for r in rows if r["question_key"] in key_set]

    _configure()
    import asyncio

    questions_json = json.dumps([{"key": q["key"], "text": q["text"]} for q in questions])
    module = dspy.ChainOfThought(DiscoverAnalysisSignature)

    def _run() -> list[dict]:
        pred = module(
            project_name=project_name,
            business_unit=business_unit,
            brief_text=brief_text,
            project_doc_sections=project_doc_sections,
            app_brain_context=app_brain_context,
            questions_json=questions_json,
        )
        return [r.model_dump() for r in pred.analyses]

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _run)
