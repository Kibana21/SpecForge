import json
import logging
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm.base import LLMProvider
from app.services.rag.retrieval_service import RAGRetrievalService, RetrievedChunk

log = logging.getLogger(__name__)

_SKILLS_ROOT = Path(__file__).parent.parent / "skills"
_retrieval_service = RAGRetrievalService()


def _build_retrieved_text(chunks: list[RetrievedChunk]) -> str:
    parts = []
    for i, c in enumerate(chunks, start=1):
        parts.append(
            f"[Citation {i} | {c.doc_name} chunk {c.chunk_no}]\n{c.text}"
        )
    return "\n\n".join(parts)


def _render_prompt(skill_name: str, context: dict) -> tuple[str, str]:
    """Return (prompt, system_instruction) for a skill."""
    from jinja2 import Environment, StrictUndefined

    skill_dir = _SKILLS_ROOT / skill_name
    instruction = (skill_dir / "instruction.md").read_text(encoding="utf-8")
    template_src = (skill_dir / "template.md").read_text(encoding="utf-8")
    env = Environment(undefined=StrictUndefined, autoescape=False)
    prompt = env.from_string(template_src).render(**context)
    return prompt, instruction


class AppBrainRAGService:
    async def stream_answer(
        self,
        app_id: uuid.UUID,
        question: str,
        top_k: int,
        db: AsyncSession,
        app_name: str,
        provider: LLMProvider,
    ) -> AsyncGenerator[dict, None]:
        chunks = await _retrieval_service.retrieve(
            app_id=app_id,
            question=question,
            top_k=top_k,
            db=db,
        )

        if not chunks:
            yield {"type": "error", "message": "No indexed content found for this app."}
            return

        retrieved_text = _build_retrieved_text(chunks)
        prompt, instruction = _render_prompt(
            "app_brain_qa",
            {"app_name": app_name, "retrieved_text": retrieved_text, "question": question},
        )

        async for token in provider.astream(prompt=prompt, system=instruction, skill_name="app_brain_qa"):
            yield {"type": "chunk", "text": token}

        citations = [
            {
                "id": str(c.chunk_id),
                "doc_name": c.doc_name,
                "chunk_no": c.chunk_no,
                "text_excerpt": c.text[:200],
            }
            for c in chunks
        ]
        yield {"type": "citations", "citations": citations}
        yield {"type": "done"}
