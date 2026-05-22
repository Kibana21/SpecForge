import json
import logging
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services.corpus_index import RetrievedSection
from app.services.llm.base import LLMProvider
from app.services.rag.retrieval_service import RAGRetrievalService, RetrievedChunk
from app.services.rag.tree_retrieval import retrieve_app_sections

log = logging.getLogger(__name__)

_SKILLS_ROOT = Path(__file__).parent.parent / "skills"
_retrieval_service = RAGRetrievalService()


def _build_retrieved_text(sections: list[RetrievedSection], chunks: list[RetrievedChunk]) -> str:
    """Combine reasoning-selected sections (PageIndex) + vector chunks for the QA prompt."""
    parts = []
    for i, s in enumerate(sections, start=1):
        loc = f" (p{s.page_start}-{s.page_end})" if s.page_start else ""
        parts.append(f"[Section {i} | {s.doc_name} › {s.title}{loc}]\n{s.text}")
    for i, c in enumerate(chunks, start=1):
        parts.append(f"[Citation {i} | {c.doc_name} chunk {c.chunk_no}]\n{c.text}")
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

        # Hybrid: reasoning tree-search alongside vector chunks (best-effort —
        # a tree-search failure must not break /ask).
        sections: list[RetrievedSection] = []
        if get_settings().app_brain_use_pageindex:
            try:
                sections = await retrieve_app_sections(
                    app_id=app_id, question=question, top_k=top_k, db=db
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("app_brain tree-search failed app_id=%s error=%s", app_id, exc)

        if not chunks and not sections:
            yield {"type": "error", "message": "No indexed content found for this app."}
            return

        retrieved_text = _build_retrieved_text(sections, chunks)
        prompt, instruction = _render_prompt(
            "app_brain_qa",
            {"app_name": app_name, "retrieved_text": retrieved_text, "question": question},
        )

        async for token in provider.astream(prompt=prompt, system=instruction, skill_name="app_brain_qa"):
            yield {"type": "chunk", "text": token}

        # Citations: reasoning sections first (doc › section, page), then vector chunks.
        citations = [
            {
                "id": f"sec-{s.node_id}",
                "doc_name": f"{s.doc_name} › {s.title}" if s.title else s.doc_name,
                "chunk_no": s.page_start,
                "text_excerpt": s.text[:200],
            }
            for s in sections
        ] + [
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
