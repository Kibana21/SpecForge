"""DSPy-based brain context synthesizer — production path (non-mock only).

Merges per-document facts of one kind into deduplicated app-level insights
with full source traceability (source_fact_ids).
"""
import asyncio
import logging
from typing import Literal, Optional

import dspy
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)


class SourceFact(BaseModel):
    id: str
    text: str
    source_ref: Optional[str] = None
    confidence: Literal["high", "medium", "low"]


class SynthesizedFact(BaseModel):
    text: str = Field(min_length=5)
    confidence: Literal["high", "medium", "low"]
    source_fact_ids: list[str] = Field(
        description="IDs of input facts this synthesized fact is derived from"
    )


class FactSynthesisSignature(dspy.Signature):
    """Synthesize a deduplicated set of facts from multiple per-document facts about the same software system.

    Rules:
    - Merge facts that express the same thing in different words into one
    - Preserve nuance: keep facts distinct when they add different information even if similar
    - Each output fact MUST list the input fact IDs it was derived from in source_fact_ids
    - source_fact_ids must only reference IDs that appear in the input — never invent IDs
    - Never invent new facts not grounded in the input
    - Output an empty list only when the input is empty
    """

    app_name: str = dspy.InputField(desc="Name of the application being synthesized")
    kind: str = dspy.InputField(
        desc="Fact category: capability | constraint | limitation | integration | gotcha"
    )
    source_facts: list[SourceFact] = dspy.InputField(
        desc="Per-document facts to synthesize, each with an id for traceability"
    )
    synthesized_facts: list[SynthesizedFact] = dspy.OutputField(
        desc="Deduplicated synthesized facts, each with full source attribution"
    )


class FactSynthesisModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(FactSynthesisSignature)

    def forward(self, app_name: str, kind: str, source_facts: list[SourceFact]) -> list[dict]:
        if not source_facts:
            return []
        try:
            result = self.predict(app_name=app_name, kind=kind, source_facts=source_facts)
            return [f.model_dump() for f in result.synthesized_facts]
        except Exception as exc:
            log.error("dspy fact_synthesis predict failed kind=%s: %s", kind, exc, exc_info=True)
            return []


async def run_dspy_fact_synthesis(
    app_name: str, kind: str, source_facts: list[SourceFact]
) -> list[dict]:
    """Run brain context synthesis via DSPy (Vertex AI). Runs in thread executor."""
    from app.services.skills.fact_extractor.dspy_extractor import _configure_dspy
    _configure_dspy()
    module = FactSynthesisModule()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, module, app_name, kind, source_facts)
