"""Project Copilot streaming orchestrator.

Emits the same SSE event model as the App Brain Ask (step/chunk/trace/citations/done/error)
so the frontend reader mirrors AskPanel. New events: partial trace events during streaming
so the Evidence rail updates live.

Pipeline:
  1. load ProjectKnowledge  (async, once)
  2. pre-flight seed         (async, reuses proven tree_search + concept-select)
  3. dspy.streamify(ReAct)   (async-wrapped sync loop running in a thread)
  4. verify & prune citations (no broken chips, ever)
  5. emit final trace + citations + done
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import uuid
from collections.abc import AsyncGenerator
from typing import Any

log = logging.getLogger(__name__)

_TOKEN_RE = re.compile(
    r"\b(S:[0-9a-fA-F-]{8,}:[A-Za-z0-9._-]+|C:[a-z0-9][a-z0-9_-]+|F:[0-9a-fA-F-]{8,})\b"
)


# ── Status message provider ──────────────────────────────────────────────────────

class _ProjectStatusProvider:
    """Humanises dspy.ReAct tool calls into readable step text for the UI trail."""

    def __init__(self, doc_names: dict[str, str]) -> None:
        self._doc_names = doc_names

    def tool_start_status_message(self, instance: Any, inputs: dict[str, Any]) -> str:
        name = getattr(instance, "name", "") or ""
        if name == "list_documents":
            return "Listing project documents…"
        if name == "search_sections":
            q = inputs.get("query", "")[:60]
            return f'Searching sections for "{q}"…'
        if name == "read_section":
            doc_id = inputs.get("doc_id", "")
            node_id = inputs.get("node_id", "")
            doc = self._doc_names.get(str(doc_id), doc_id[:8] + "…" if doc_id else "?")
            return f"Reading {doc} § {node_id}…"
        if name == "search_wiki":
            q = inputs.get("query", "")[:60]
            return f'Searching wiki for "{q}"…'
        if name == "read_concept":
            slug = inputs.get("slug", "")
            return f'Reading concept "{slug}"...'
        if name == "lookup_facts":
            q = inputs.get("query", "")[:60]
            return f'Looking up facts for "{q}"…'
        return f"Calling {name}…"

    def tool_end_status_message(self, outputs: Any) -> str | None:
        return None  # step is logged on start; no duplicate on end

    def module_start_status_message(self, instance: Any, inputs: dict[str, Any]) -> str | None:
        return None

    def module_end_status_message(self, outputs: Any) -> str | None:
        return None

    def lm_start_status_message(self, instance: Any, inputs: dict[str, Any]) -> str | None:
        return None

    def lm_end_status_message(self, outputs: Any) -> str | None:
        return None


# ── Helpers ──────────────────────────────────────────────────────────────────────

def _outline_nodes(tree: dict, _depth: int = 0) -> list[dict]:
    """Flatten tree into [{node_id, title, depth}] for the Evidence rail."""
    out: list[dict] = []
    for node in (tree.get("nodes") or []):
        nid = node.get("node_id")
        if nid and nid != "0000":
            out.append({"node_id": str(nid), "title": (node.get("title") or "").strip(), "depth": _depth})
        out.extend(_outline_nodes(node, _depth + 1))
    return out


def _build_trace(k: Any, trace: Any, partial: bool) -> dict:
    from app.services.corpus_index.base import find_node
    docs_index = {str(d.document_id): d for d in k.docs}
    return {
        "mode": "agent",
        "selected_concepts": [
            {"slug": c["slug"], "title": c["title"], "brief": c["brief"]}
            for c in trace.concepts.values()
        ],
        "selected_documents": [],       # kept for DeepTrace shape compat
        "sections": [
            {
                "doc_id": s["doc_id"], "doc_name": s["doc_name"], "node_id": s["node_id"],
                "title": s["title"], "pages": s["pages"], "excerpt": s["text"][:300],
            }
            for s in trace.sections.values()
        ],
        "chunks": [],
        "facts": [
            {"id": f["id"], "app": f["app"], "kind": f["kind"], "text": f["text"][:200]}
            for f in trace.facts.values()
        ],
        "tree_map": [
            {
                "doc_id": did,
                "doc_name": k.doc_names.get(did, ""),
                "visited": sorted(nodes),
                "outline": _outline_nodes(docs_index[did].tree) if did in docs_index else [],
            }
            for did, nodes in trace.visited.items()
        ],
        "fallback_used": False,
        "context_chars": sum(len(s["text"]) for s in trace.sections.values()),
        "partial": partial,
    }


def _build_citations(trace: Any) -> list[dict]:
    out: list[dict] = []
    for c in trace.concepts.values():
        out.append({
            "id": f"concept-{c['slug']}", "token": f"C:{c['slug']}", "kind": "concept",
            "doc_name": f"Concept · {c['title']}", "chunk_no": 0,
            "text_excerpt": c["brief"][:200],
        })
    for s in trace.sections.values():
        name = f"{s['doc_name']} › {s['title']}" if s["title"] else s["doc_name"]
        out.append({
            "id": f"sec-{s['node_id']}", "token": f"S:{s['doc_id']}:{s['node_id']}", "kind": "section",
            "doc_name": name, "chunk_no": 0, "text_excerpt": s["text"][:200],
        })
    for f in trace.facts.values():
        out.append({
            "id": f"fact-{f['id']}", "token": f"F:{f['id']}", "kind": "fact",
            "doc_name": f"{f['app']} · {f['kind']}", "chunk_no": 0, "text_excerpt": f["text"][:200],
        })
    return out


def _verify_and_prune(k: Any, trace: Any) -> None:
    """Drop refs whose ids don't resolve in loaded knowledge.
    Guarantees every chip the UI renders will resolve — no broken popovers."""
    from app.services.corpus_index.base import find_node
    valid_docs = {str(d.document_id): d for d in k.docs}
    trace.sections = {
        (d, n): v for (d, n), v in trace.sections.items()
        if d in valid_docs and find_node(valid_docs[d].tree, n) is not None
    }
    slugs = {c.slug for c in k.concepts}
    trace.concepts = {s: v for s, v in trace.concepts.items() if s in slugs}
    fact_ids = {f["id"] for f in k.facts}
    trace.facts = {i: v for i, v in trace.facts.items() if i in fact_ids}


# ── Mock trajectory ───────────────────────────────────────────────────────────────

async def _mock_trajectory(
    k: Any, trace: Any, question: str, seed: str
) -> AsyncGenerator[dict, None]:
    """Scripted trajectory over the *real* loaded knowledge — deterministic, exercises
    the full SSE + citation path under LLM_PROVIDER=mock."""
    from app.services.corpus_index.base import iter_nodes
    tools = _build_tools_ref(k, trace)
    yield {"type": "step", "text": "Listed project documents"}
    tools["list_documents"]()

    parts: list[str] = []
    if k.docs:
        d = k.docs[0]
        first = next((n for n in iter_nodes(d.tree) if n.get("node_id") != "0000"), None)
        if first:
            did, nid = str(d.document_id), str(first["node_id"])
            yield {"type": "step", "text": f"Reading {k.doc_names.get(did, '?')} › {first.get('title', '')}"}
            tools["read_section"](did, nid)
            parts.append(f"Per the source, see S:{did}:{nid}.")
    if k.concepts:
        c = k.concepts[0]
        yield {"type": "step", "text": f'Reading concept "{c.title}"'}
        tools["read_concept"](c.slug)
        parts.append(f"This relates to C:{c.slug}.")
    if k.facts:
        f = k.facts[0]
        trace.facts[f["id"]] = f
        parts.append(f"A known fact is F:{f['id']}.")

    answer = ("Mock project answer. " + " ".join(parts)) if parts else \
             "Mock project answer. No specific sources were found for this question."
    for i in range(0, len(answer), 12):
        yield {"type": "chunk", "text": answer[i : i + 12]}
        await asyncio.sleep(0)


def _build_tools_ref(k: Any, trace: Any) -> dict:
    from app.services.rag.project_tools import build_tools
    tools_list = build_tools(k, trace)
    names = ["list_documents", "search_sections", "read_section", "search_wiki",
             "read_concept", "lookup_facts"]
    return {names[i]: t for i, t in enumerate(tools_list)}


# ── Live ReAct stream ─────────────────────────────────────────────────────────────

async def _react_stream(
    k: Any, trace: Any, project_name: str, question: str, seed: str, history: list | None
) -> AsyncGenerator[dict, None]:
    from app.services.skills.fact_extractor.dspy_extractor import _configure_dspy
    from app.services.skills.project_chat.dspy_chat import build_react
    from app.services.rag.project_tools import build_tools
    from app.services.rag.rag_service import format_conversation
    import dspy
    from dspy.streaming import StatusMessage, StreamResponse, StreamListener

    _configure_dspy()
    tools = build_tools(k, trace)
    react = build_react(tools)
    provider = _ProjectStatusProvider(k.doc_names)

    program = dspy.streamify(
        react,
        stream_listeners=[StreamListener(signature_field_name="answer")],
        status_message_provider=provider,
    )
    streamed = False
    try:
        async for chunk in program(
            project_name=project_name,
            seed_context=seed,
            conversation=format_conversation(history),
            question=question,
        ):
            if isinstance(chunk, StatusMessage) and chunk.message:
                yield {"type": "step", "text": chunk.message}
                yield {"type": "trace", "trace": _build_trace(k, trace, partial=True)}
            elif isinstance(chunk, StreamResponse) and chunk.chunk:
                streamed = True
                yield {"type": "chunk", "text": chunk.chunk}
    except Exception as exc:
        log.warning("project ReAct stream failed (%s); falling back to one-shot", exc)

    if not streamed:
        # One-shot fallback: run the full ReAct in a thread, replay recorded steps
        loop = asyncio.get_running_loop()
        tools_fallback = build_tools(k, trace)
        react_fallback = build_react(tools_fallback)
        try:
            pred = await loop.run_in_executor(
                None,
                lambda: react_fallback(
                    project_name=project_name,
                    seed_context=seed,
                    conversation=format_conversation(history),
                    question=question,
                ),
            )
        except Exception as exc:
            log.error("project ReAct one-shot fallback failed: %s", exc, exc_info=True)
            yield {"type": "error", "message": "The agent could not complete its research. Please try again."}
            return
        for s in trace.steps:
            yield {"type": "step", "text": s}
        answer = getattr(pred, "answer", "") or \
                 "I couldn't find enough in this project's knowledge to answer that."
        yield {"type": "chunk", "text": answer}


# ── Public agent ─────────────────────────────────────────────────────────────────

class ProjectChatAgent:
    async def stream_answer(
        self,
        *,
        project_id: uuid.UUID,
        project_name: str,
        question: str,
        db: Any,
        history: list | None = None,
    ) -> AsyncGenerator[dict, None]:
        from app.config import get_settings
        from app.services.rag.project_tools import load_project_knowledge, TraceAccumulator
        from app.services.rag.project_seed import build_seed

        # Emit immediately so the SSE connection is confirmed live to the browser/proxy
        yield {"type": "step", "text": "Connecting to project knowledge…"}

        k = await load_project_knowledge(project_id, db)
        if not k.has_any():
            yield {
                "type": "error",
                "message": (
                    "This project has no indexed documents or wiki yet. "
                    "Upload source documents and compile the wiki first."
                ),
            }
            return

        trace = TraceAccumulator()
        yield {"type": "step", "text": "Gathering project knowledge…"}

        seed = await build_seed(project_id, question, k, trace, db)
        # Emit partial trace immediately so the Evidence rail populates before the loop
        yield {"type": "trace", "trace": _build_trace(k, trace, partial=True)}

        settings = get_settings()
        try:
            if settings.llm_provider == "mock":
                async for ev in _mock_trajectory(k, trace, question, seed):
                    yield ev
            else:
                async for ev in _react_stream(k, trace, project_name, question, seed, history):
                    yield ev
        except Exception as exc:
            log.error("project_agent stream_answer failed: %s", exc, exc_info=True)
            yield {"type": "error", "message": "Something went wrong while generating the answer."}
            return

        _verify_and_prune(k, trace)
        yield {"type": "trace", "trace": _build_trace(k, trace, partial=False)}
        yield {"type": "citations", "citations": _build_citations(trace)}
        yield {"type": "done"}
