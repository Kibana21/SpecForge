"""DSPy reasoning-retrieval over a PageIndex outline (replaces the
source_tree_search Jinja skill). Picks the most relevant sections for a query."""
import asyncio
import logging

import dspy
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)


class TreeSelection(BaseModel):
    doc: str = Field(description="Document alias from the outline, e.g. 'D0'")
    node_id: str = Field(description="A node_id that appears in the outline")
    reason: str = ""


class TreeSearchResult(BaseModel):
    selections: list[TreeSelection] = Field(default_factory=list)


class TreeSearchSignature(dspy.Signature):
    """Pick the document sections whose content best answers the query.

    Each outline line is `[D{i}] {node_id} · {title} — {summary}`; use the `[D{i}]`
    alias as `doc` and a `node_id` from the outline. Reason about meaning and
    relevance, not keyword overlap; prefer specific leaf sections over broad
    parents. Select the 3–6 most relevant; return an empty list only when nothing
    is even loosely related. Never invent node_ids.
    """

    query: str = dspy.InputField()
    outline: str = dspy.InputField(desc="lines of '[D{i}] node_id · title — summary'")
    top_k: int = dspy.InputField()
    result: TreeSearchResult = dspy.OutputField()


class TreeSearchModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(TreeSearchSignature)

    def forward(self, query: str, outline: str, top_k: int) -> dict:
        try:
            result = self.predict(query=query, outline=outline, top_k=top_k)
            return result.result.model_dump()
        except Exception as exc:
            log.error("dspy tree_search failed: %s", exc, exc_info=True)
            return {"selections": []}


async def run_tree_search(query: str, outline: str, top_k: int) -> dict:
    from app.config import get_settings
    if get_settings().llm_provider == "mock":
        from app.services.skills.mock_fixtures import mock_fixture
        return mock_fixture("source_tree_search")
    from app.services.skills.fact_extractor.dspy_extractor import _configure_dspy
    _configure_dspy()
    module = TreeSearchModule()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, module, query, outline, top_k)
