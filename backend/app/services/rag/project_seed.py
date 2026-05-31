"""Pre-flight seed for the Project Copilot.

One async pass before the (sync) dspy.ReAct loop — reuses the *proven* project
retrieval so the agent starts grounded at Deep-Search quality, then refines
agentically. Both calls are mock-safe (corpus_index uses MockCorpusIndexProvider
and run_concept_select returns a fixture under LLM_PROVIDER=mock).
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.rag.project_tools import ProjectKnowledge, TraceAccumulator

log = logging.getLogger(__name__)


async def build_seed(
    project_id: uuid.UUID,
    question: str,
    k: ProjectKnowledge,
    trace: TraceAccumulator,
    db: AsyncSession,
) -> str:
    """Run tree_search + concept-select, pre-record refs into trace, return seed string.

    The seed string is injected into the agent's seed_context input so the LLM starts
    with proven candidates it can verify/expand with its tools rather than navigating
    from scratch.
    """
    from app.config import get_settings
    from app.services.corpus_index import get_corpus_index_provider
    from app.services.skills.wiki_compiler.dspy_wiki import run_concept_select

    lines: list[str] = []

    # --- Section seed: LLM-reasoned tree_search (deterministic mock) ---
    if k.docs:
        try:
            settings = get_settings()
            sections = await get_corpus_index_provider().tree_search(
                query=question, docs=k.docs, top_k=settings.tree_search_top_k
            )
            for s in sections:
                did, nid = str(s.document_id), s.node_id
                trace.sections[(did, nid)] = {
                    "doc_id": did,
                    "doc_name": s.doc_name,
                    "node_id": nid,
                    "title": s.title,
                    "pages": f"{s.page_start}-{s.page_end}" if s.page_start else "",
                    "text": s.text,
                }
                trace.note_visit(did, nid)
                lines.append(
                    f"S:{did}:{nid} · {s.doc_name} › {s.title} — {s.text[:200]}"
                )
        except Exception as exc:
            log.warning("project_seed tree_search failed: %s", exc)

    # --- Concept seed: reuse existing concept-select signature ---
    if k.concepts:
        try:
            outline = "\n".join(f"{c.slug} · {c.title} — {c.brief}" for c in k.concepts)
            sel = await run_concept_select(question, outline, "(none)")
            for slug in (sel.get("concept_slugs", []) if isinstance(sel, dict) else []):
                c = next((x for x in k.concepts if x.slug == slug), None)
                if c:
                    trace.concepts[slug] = {
                        "slug": slug,
                        "title": c.title,
                        "brief": c.brief,
                        "tree_node_refs": c.tree_node_refs or [],
                    }
                    lines.append(f"C:{slug} · {c.title} — {c.brief}")
        except Exception as exc:
            log.warning("project_seed concept_select failed: %s", exc)

    if lines:
        trace.steps.append(f"Pre-retrieved {len(lines)} candidate reference(s)")

    return "\n".join(lines) or "(no pre-retrieved candidates — explore with the tools)"
