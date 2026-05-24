import logging
import uuid
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services.corpus_index import RetrievedSection
from app.services.llm.base import LLMProvider
from app.services.rag.retrieval_service import RAGRetrievalService, RetrievedChunk
from app.services.rag.tree_retrieval import retrieve_app_sections

log = logging.getLogger(__name__)

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


def format_conversation(history, max_turns: int = 6) -> str:
    """Render recent chat turns into a compact transcript for the QA prompt."""
    if not history:
        return ""
    lines: list[str] = []
    for t in history[-max_turns:]:
        role = getattr(t, "role", None) or (t.get("role") if isinstance(t, dict) else "")
        content = getattr(t, "content", None) or (t.get("content") if isinstance(t, dict) else "")
        label = "User" if role == "user" else "Assistant"
        lines.append(f"{label}: {(content or '').strip()[:1500]}")
    return "\n\n".join(lines)


class AppBrainRAGService:
    async def stream_answer(
        self,
        app_id: uuid.UUID,
        question: str,
        top_k: int,
        db: AsyncSession,
        app_name: str,
        provider: LLMProvider,
        history: list | None = None,
    ) -> AsyncGenerator[dict, None]:
        settings = get_settings()
        sections: list[RetrievedSection] = []
        if settings.app_brain_use_pageindex:
            try:
                sections = await retrieve_app_sections(
                    app_id=app_id, question=question, top_k=top_k, db=db
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("app_brain tree-search failed app_id=%s error=%s", app_id, exc)

        # Fall back to vector chunks only when PageIndex is off or returned nothing.
        chunks: list[RetrievedChunk] = []
        if not settings.app_brain_use_pageindex or not sections:
            chunks = await _retrieval_service.retrieve(
                app_id=app_id,
                question=question,
                top_k=top_k,
                db=db,
            )

        if not chunks and not sections:
            yield {"type": "error", "message": "No indexed content found for this app."}
            return

        retrieved_text = _build_retrieved_text(sections, chunks)

        # --- Explainability trace: what fed this single-pass answer ---
        yield {
            "type": "trace",
            "trace": {
                "mode": "quick",
                "selected_concepts": [],
                "selected_documents": [],
                "sections": [
                    {
                        "doc_id": str(s.document_id), "doc_name": s.doc_name, "node_id": s.node_id,
                        "title": s.title, "pages": f"{s.page_start}-{s.page_end}" if s.page_start else "",
                        "excerpt": s.text[:300],
                    }
                    for s in sections
                ],
                "chunks": [
                    {
                        "doc_name": c.doc_name, "chunk_no": c.chunk_no,
                        "similarity": round(c.similarity, 3), "excerpt": c.text[:300],
                    }
                    for c in chunks
                ],
                "fallback_used": bool(chunks) and not sections,
                "context_chars": len(retrieved_text),
            },
        }

        from app.services.skills.app_brain_qa.dspy_qa import run_qa_stream
        async for token in run_qa_stream(
            app_name=app_name, retrieved_text=retrieved_text,
            conversation=format_conversation(history), question=question,
        ):
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
