"""DSPy-based fact extractor — production path (non-mock only).

Uses dspy.Predict with typed Pydantic output for reliable structured extraction.
Mock path (llm_provider=mock) is handled upstream by the caller via mock_fixture.
"""
import asyncio
import functools
import logging
from typing import Literal, Optional

import dspy
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)


class Fact(BaseModel):
    kind: Literal["capability", "constraint", "limitation", "integration", "gotcha"]
    text: str = Field(min_length=5)
    confidence: Literal["high", "medium", "low"]
    source_ref: Optional[str] = None


class FactExtractionSignature(dspy.Signature):
    """Extract structured facts about a software application from its documentation.

    Fact kinds:
    - capability: something the app CAN do (features, operations, APIs it exposes)
    - constraint: a rule, limit, or requirement the app must operate within
    - limitation: something the app cannot do, does not support, or handles poorly
    - integration: a connection with another system, protocol, service, or standard
    - gotcha: non-obvious behaviour that would surprise a developer or operator

    The text contains sections prefixed with "--- [doc: <filename>, chunk <N>] ---".
    For each extracted fact, set source_ref to the filename where the fact was found.
    Be generous: extract every meaningful fact, including those strongly implied by the text.
    An empty list is only valid if the text is completely unrelated to any software system.
    """

    chunk_text: str = dspy.InputField(desc="Documentation text with doc/chunk headers to extract facts from")
    facts: list[Fact] = dspy.OutputField(desc="All extracted facts, each with source_ref set to the source filename")


class FactExtractorModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(FactExtractionSignature)

    def forward(self, chunk_text: str) -> list[dict]:
        if not chunk_text or not chunk_text.strip():
            return []
        try:
            result = self.predict(chunk_text=chunk_text)
            return [f.model_dump() for f in result.facts]
        except Exception as exc:
            log.error("dspy fact_extractor predict failed: %s", exc, exc_info=True)
            return []


@functools.lru_cache(maxsize=1)
def _configure_dspy() -> None:
    """Configure DSPy with Vertex AI LM once per process (Celery worker-safe)."""
    from app.config import get_settings
    from app.core.google_credentials import configure_google_genai_env

    configure_google_genai_env()
    settings = get_settings()
    lm = dspy.LM(
        f"vertex_ai/{settings.gemini_model}",
        max_tokens=65536,
        cache=False,
        vertex_location=settings.gemini_location,
        vertex_project=settings.gemini_project_id or None,
    )
    dspy.configure(lm=lm)
    log.info(
        "dspy configured lm=vertex_ai/%s location=%s",
        settings.gemini_model, settings.gemini_location,
    )


async def run_dspy_fact_extraction(chunk_text: str) -> list[dict]:
    """Run fact extraction via DSPy ChainOfThought (Vertex AI). Runs in thread executor."""
    _configure_dspy()
    module = FactExtractorModule()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, module, chunk_text)
