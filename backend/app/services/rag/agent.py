"""Deep Search — Brain Wiki-grounded answer orchestration.

A structured, transparent pipeline (the streamable form of OpenKB's query agent):
  1. SELECT   — LLM picks relevant wiki concepts/doc-summaries from the index
  2. GATHER   — pull concept bodies + drill into their PageIndex tree_node_refs
  3. FALLBACK — vector search only to fill gaps the wiki doesn't cover
  4. SYNTHESISE — stream a cited answer over the gathered, cross-document context

Emits SSE events: step (research trail) → chunk (answer tokens) → citations → done.
Starts from compiled cross-document concepts and drills to exact sections, so
multi-document questions resolve from pre-synthesised knowledge rather than a
single flat retrieval pass.
"""
import logging
import uuid
from collections.abc import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.corpus import AppCorpusDoc
from app.models.wiki import AppWikiConcept, AppWikiSummary
from app.services.corpus_index import RetrievedSection
from app.services.llm.base import LLMProvider
from app.services.rag.rag_service import format_conversation
from app.services.rag.retrieval_service import RAGRetrievalService, RetrievedChunk
from app.services.rag.tree_retrieval import get_sections_by_refs
from app.services.skills.wiki_compiler.dspy_wiki import run_concept_select

log = logging.getLogger(__name__)

_retrieval_service = RAGRetrievalService()


def _build_deep_context(
    concepts: list[AppWikiConcept],
    sections: list[RetrievedSection],
    chunks: list[RetrievedChunk],
) -> str:
    parts: list[str] = []
    for c in concepts:
        parts.append(f"[Concept: {c.title}]\n{c.content_md}")
    for i, s in enumerate(sections, start=1):
        loc = f" (p{s.page_start}-{s.page_end})" if s.page_start else ""
        parts.append(f"[Section {i} | {s.doc_name} › {s.title}{loc}]\n{s.text}")
    for i, c in enumerate(chunks, start=1):
        parts.append(f"[Citation {i} | {c.doc_name} chunk {c.chunk_no}]\n{c.text}")
    return "\n\n".join(parts)


class AppBrainAgent:
    """Deep Search over the compiled Brain Wiki."""

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
        # --- Load the wiki index ---
        concepts = (await db.execute(
            select(AppWikiConcept).where(AppWikiConcept.app_id == app_id)
        )).scalars().all()
        summary_rows = (await db.execute(
            select(AppWikiSummary, AppCorpusDoc.name)
            .join(AppCorpusDoc, AppCorpusDoc.id == AppWikiSummary.doc_id)
            .where(AppWikiSummary.app_id == app_id)
        )).all()

        if not concepts and not summary_rows:
            yield {"type": "error", "message": "No Brain Wiki compiled for this app yet."}
            return

        by_slug = {c.slug: c for c in concepts}
        summaries = {str(s.doc_id): (s, name) for s, name in summary_rows}

        yield {"type": "step", "text": f"Scanning {len(concepts)} concepts across the knowledge base…"}

        # --- 1. SELECT relevant concepts / doc summaries ---
        concepts_outline = "\n".join(f"{c.slug} · {c.title} — {c.brief}" for c in concepts) or "(none)"
        summaries_outline = "\n".join(
            f"{did} · {name} — {s.brief}" for did, (s, name) in summaries.items()
        ) or "(none)"

        chosen_concepts: list[AppWikiConcept] = []
        chosen_summaries: list[tuple[AppWikiSummary, str]] = []
        try:
            sel = await run_concept_select(question, concepts_outline, summaries_outline)
            slugs = sel.get("concept_slugs", []) if isinstance(sel, dict) else []
            doc_ids = sel.get("doc_ids", []) if isinstance(sel, dict) else []
            chosen_concepts = [by_slug[s] for s in slugs if s in by_slug]
            chosen_summaries = [summaries[d] for d in doc_ids if d in summaries]
        except Exception as exc:  # noqa: BLE001
            log.warning("deep_search select failed app_id=%s error=%s", app_id, exc)

        # Fallback: nothing selected → use the top few concepts so we still answer
        if not chosen_concepts and not chosen_summaries:
            chosen_concepts = list(concepts[:3])

        if chosen_concepts:
            yield {"type": "step", "text": "Selected concepts: " + ", ".join(c.title for c in chosen_concepts)}
        if chosen_summaries:
            yield {"type": "step", "text": "Including documents: " + ", ".join(name for _, name in chosen_summaries)}

        # --- 2. GATHER: drill into the concepts' PageIndex sections ---
        refs: list[dict] = []
        for c in chosen_concepts:
            for r in (c.tree_node_refs or []):
                refs.append({"doc_id": r.get("doc_id"), "node_id": r.get("node_id")})

        sections: list[RetrievedSection] = []
        if refs:
            sections = await get_sections_by_refs(app_id, refs, db)
            doc_count = len({s.document_id for s in sections})
            yield {"type": "step", "text": f"Drilling into {len(sections)} source sections across {doc_count} document(s)…"}

        # --- 3. FALLBACK: vector search to fill gaps ---
        chunks: list[RetrievedChunk] = []
        if not chosen_concepts or (not sections and not chosen_summaries):
            yield {"type": "step", "text": "Searching raw passages for additional detail…"}
            chunks = await _retrieval_service.retrieve(
                app_id=app_id, question=question, top_k=top_k, db=db
            )

        if not chosen_concepts and not chosen_summaries and not sections and not chunks:
            yield {"type": "error", "message": "Couldn't find relevant content for this question."}
            return

        # --- 4. SYNTHESISE: stream a cited answer ---
        # Doc-summary bodies join the concept context block.
        context_concepts = list(chosen_concepts)
        summary_context = "\n\n".join(
            f"[Document: {name}]\n{s.content_md}" for s, name in chosen_summaries
        )
        retrieved_text = _build_deep_context(context_concepts, sections, chunks)
        if summary_context:
            retrieved_text = summary_context + "\n\n" + retrieved_text

        # --- Explainability trace: exactly what fed the synthesis ---
        yield {
            "type": "trace",
            "trace": {
                "mode": "deep",
                "selected_concepts": [
                    {"slug": c.slug, "title": c.title, "brief": c.brief} for c in chosen_concepts
                ],
                "selected_documents": [
                    {"doc_id": str(s.doc_id), "name": name, "brief": s.brief}
                    for s, name in chosen_summaries
                ],
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
                "fallback_used": bool(chunks),
                "context_chars": len(retrieved_text),
            },
        }

        yield {"type": "step", "text": "Synthesizing answer…"}
        from app.services.skills.app_brain_qa.dspy_qa import run_qa_stream
        async for token in run_qa_stream(
            app_name=app_name, retrieved_text=retrieved_text,
            conversation=format_conversation(history), question=question,
        ):
            yield {"type": "chunk", "text": token}

        # --- Layered citations: concept → section → chunk ---
        citations = [
            {
                "id": f"concept-{c.slug}",
                "doc_name": f"Concept · {c.title}",
                "chunk_no": 0,
                "text_excerpt": c.brief[:200],
            }
            for c in chosen_concepts
        ] + [
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
