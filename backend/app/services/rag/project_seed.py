"""Pre-flight seed for the Project Copilot.

One async pass before the (sync) dspy.ReAct loop — reuses the *proven* project
retrieval so the agent starts grounded at Deep-Search quality, then refines
agentically. Both calls are mock-safe (corpus_index uses MockCorpusIndexProvider
and run_concept_select returns a fixture under LLM_PROVIDER=mock).

tree_search and concept_select run in parallel to avoid a sequential LLM roundtrip.
"""
from __future__ import annotations

import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.rag.project_tools import ProjectKnowledge, TraceAccumulator

log = logging.getLogger(__name__)

# How many chars of section text to include in seed_context.
# Enough to orient the LLM; full text is available via read_section.
_SEED_EXCERPT_CHARS = 120


async def build_seed(
    project_id: uuid.UUID,
    question: str,
    k: ProjectKnowledge,
    trace: TraceAccumulator,
    db: AsyncSession,
) -> str:
    """Run tree_search + concept-select in parallel, pre-record refs into trace.

    Seed text is injected into seed_context so the LLM starts with proven
    candidates. Short excerpts only — read_section gives full text when needed.
    """
    from app.config import get_settings
    from app.services.corpus_index import get_corpus_index_provider
    from app.services.skills.wiki_compiler.dspy_wiki import run_concept_select

    settings = get_settings()
    section_lines: list[str] = []
    concept_lines: list[str] = []

    async def _section_seed() -> None:
        if not k.docs:
            return
        try:
            sections = await get_corpus_index_provider().tree_search(
                query=question,
                docs=k.docs,
                # Cap at 5 — more sections = larger seed context = slower LLM
                top_k=min(settings.tree_search_top_k, 5),
            )
            for s in sections:
                did, nid = str(s.document_id), s.node_id
                trace.sections[(did, nid)] = {
                    "doc_id": did, "doc_name": s.doc_name, "node_id": nid,
                    "title": s.title,
                    "pages": f"{s.page_start}-{s.page_end}" if s.page_start else "",
                    "text": s.text,
                }
                trace.note_visit(did, nid)
                section_lines.append(
                    f"S:{did}:{nid} · {s.doc_name} › {s.title} — {s.text[:_SEED_EXCERPT_CHARS]}"
                )
        except Exception as exc:
            log.warning("project_seed tree_search failed: %s", exc)

    async def _concept_seed() -> None:
        if not k.concepts:
            return
        try:
            outline = "\n".join(f"{c.slug} · {c.title} — {c.brief}" for c in k.concepts)
            sel = await run_concept_select(question, outline, "(none)")
            for slug in (sel.get("concept_slugs", []) if isinstance(sel, dict) else []):
                c = next((x for x in k.concepts if x.slug == slug), None)
                if c:
                    trace.concepts[slug] = {
                        "slug": slug, "title": c.title, "brief": c.brief,
                        "tree_node_refs": c.tree_node_refs or [],
                    }
                    concept_lines.append(f"C:{slug} · {c.title} — {c.brief}")
        except Exception as exc:
            log.warning("project_seed concept_select failed: %s", exc)

    # Run both in parallel — saves one sequential LLM roundtrip (~3-8s)
    await asyncio.gather(_section_seed(), _concept_seed())

    lines = section_lines + concept_lines
    if lines:
        trace.steps.append(f"Pre-retrieved {len(lines)} candidate reference(s)")

    return "\n".join(lines) or "(no pre-retrieved candidates — explore with the tools)"
