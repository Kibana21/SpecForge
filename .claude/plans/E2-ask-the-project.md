# E2 — Ask the Project (Agentic Vectorless Copilot) — Detailed Implementation Plan

> PRD: `.claude/prd/prd-e2-ask-the-project.md`. This plan is the self-contained build spec — every file, scaffold, schema, wireframe, and test. Read top-to-bottom; sections map to commits.

## Context

SpecForge can already *read* a project's knowledge (Wiki, Lineage, source peeks) and *generate* from it (CB/BRD/FRS), but you cannot **ask it questions**. We add a project-scoped chat **Copilot** that navigates the project's PageIndex reasoning trees (multiple `document_trees`), the Project Wiki concepts (`project_wiki_concepts`, which themselves carry cross-document `tree_node_refs`), and the linked App Brain facts (`AppFact` via `ProjectApp`) — answering with **layered, verified citations** (`S:` section · `C:` concept · `F:` fact) and showing **exactly which references across which indexes it touched**.

"Amazing" here means three concrete bars, taken from the project's UX/traceability standard:
1. **Distinctive, intuitive UX** — a two-pane "ask + live evidence" workspace, not a narrow chat box. You *watch* the agent navigate the trees.
2. **First-class traceability/provenance** — every claim links to a real source; a live **Evidence rail** shows the cross-document tree map of visited nodes, concepts, and facts; citations are *verified* (no broken chips, ever).
3. **Full-context grounding** — the agent is seeded by the **proven** project retrieval (`tree_search` over all trees + concept-select over the wiki) and then refines agentically, so quality ≥ existing Deep Search while adding multi-hop reach.

Decisions (confirmed): **true `dspy.ReAct` engine**, **full S:/C:/F: grounding**, **left-nav "Ask" tab**. This is the codebase's first tool-calling agent.

---

## The experience (what we're building)

```
┌─ Project workspace ▸ Ask ───────────────────────────────────────────────────────────┐
│  ◀ Back            Ask the Project · PayHub                    [History ▾] [+ New]     │
├──────────────────────────────────────────────┬───────────────────────────────────────┤
│  CONVERSATION (main, ~62%)                    │  EVIDENCE  (rail, ~38%, sticky)        │
│                                               │                                        │
│  ▸ Empty state: 3–4 starter chips derived     │  ┌ Grounding ──────────────────────┐   │
│    from top wiki concepts + RU objective      │  │ 4 sections · 2 docs · 1 concept │   │
│                                               │  │ ███████████░░  strong            │   │
│  ● You: How are refunds handled and what's    │  └─────────────────────────────────┘   │
│        the SLA?                               │                                        │
│                                               │  TREE MAP (visited nodes per index)    │
│  ◇ Copilot                                    │  ▸ PayHub-Spec.pdf                      │
│   ┌ Reasoning trail (live, collapsible) ──┐   │     0001 Overview                      │
│   │ ✓ Listed 4 documents                   │   │   ● 0007 Refund flow      ← read       │
│   │ ✓ Searched sections "refund SLA" (6)   │   │     0008 Disputes                      │
│   │ ✓ Read PayHub-Spec › Refund flow        │   │  ▸ Ops-Runbook.md                      │
│   │ ⟳ Reading concept refund-policy…        │   │   ● 0012 SLA targets      ← read       │
│   └────────────────────────────────────────┘   │                                        │
│                                               │  CONCEPTS                              │
│   Refunds are initiated from the agent        │   ◈ refund-policy — "How refunds…"     │
│   console S:‹PayHub-Spec›:0007 and must       │      └ grounded in 2 sections ▸         │
│   clear within **24h** per the SLA            │  FACTS                                  │
│   S:‹Ops-Runbook›:0012. This aligns with      │   ◷ PayHub/integration — "Stripe…"     │
│   the C:‹refund-policy› concept and the        │                                        │
│   F:‹…› Stripe webhook fact. [chips inline]   │  (each row clickable → source peek)    │
│                                               │                                        │
│   ▣ Grounded in 4 sources · View full trace ▸ │                                        │
│  ───────────────────────────────────────────  │                                        │
│  [ Ask a follow-up…                      ➤ ]  │                                        │
└──────────────────────────────────────────────┴───────────────────────────────────────┘
```

- **Reasoning trail**: each ReAct step animates in (tool + observation), spinner on the in-flight step, green check when done. Collapses to a one-line summary after completion.
- **Evidence rail** updates *live* as `trace`/step events arrive: grounding meter, a per-document **tree outline with visited nodes highlighted** (the cross-index references made visceral), concept cards (expandable to their grounded sections), and fact cards. Every row opens the existing source-peek popover.
- **Inline citations**: `S:/C:/F:` tokens in the answer render as `IntakeTraceChip` popovers (already supported by `renderInline`). Hovering a chip highlights the matching Evidence-rail row.
- **Starters**: empty state suggests questions built from the project's wiki concepts + RU objective.

---

## Architecture

```
Frontend  projects/[id]/page.tsx  ── view 'ask' ──▶  AskProjectView
                                                       ├─ ProjectChatPanel  (conversation + input + reasoning trail)
                                                       └─ EvidencePanel     (grounding + tree map + concepts + facts)
                                                          │ authedFetch SSE
                                                          ▼
Backend   POST /api/projects/{id}/ask   (project_ask.py, @limiter 20/min, audit emit)
            │
            ▼
          ProjectChatAgent.stream_answer()  (services/rag/project_agent.py)
            1. load ProjectKnowledge once          (trees + wiki + facts, in memory)
            2. PRE-FLIGHT SEED (async, proven):     ── reuse existing retrieval
                 • corpus_index.tree_search(question, all project trees, k)
                 • run_concept_select(question, concept/summary outlines)
               → seed_context string + pre-recorded seed refs
            3. build sync tools as closures over knowledge + TraceAccumulator
            4. dspy.streamify( dspy.ReAct(ProjectChatSignature, tools) )
                 │ StatusMessage  ─▶ SSE 'step'   (tool call/observation)
                 │ StreamResponse ─▶ SSE 'chunk'  (answer tokens w/ S:/C:/F:)
            5. VERIFY citations: drop tokens that don't resolve in loaded knowledge
            6. SSE 'trace'  (grounding + tree map + concepts + facts)
            7. SSE 'citations' (verified, layered)  → 'done'
            8. (client) auto-persist transcript to project_ask_sessions
            │
        MOCK (LLM_PROVIDER=mock): scripted trajectory over the *real* loaded
        knowledge (real ids) — deterministic, exercises full SSE+citation path.
```

**Why seed + agentic refine.** The pre-flight reuses the *proven* project retrieval (the same `tree_search` Deep Search and generation already rely on) so answer quality starts at parity; ReAct then adds multi-hop reach (read a section → notice a reference → pull the concept → check a fact). Tools stay **synchronous and in-memory** (a chat corpus is bounded), so the threaded ReAct loop never touches the async DB. The one async cost — the seed — runs once, before the loop.

---

## Backend

### B1. Knowledge loader + tools — `app/services/rag/project_tools.py` (NEW)

```python
"""Agent tools over a project's PageIndex trees, wiki concepts, and app facts.
Pre-loaded in memory so the (sync, threaded) ReAct loop never touches async DB.
Every tool records what it touched into TraceAccumulator for post-hoc trace+citations."""
from __future__ import annotations
import re
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.project_source import DocumentTree
from app.models.project_wiki import ProjectWikiConcept
from app.services.corpus_index.base import IndexedDoc, find_node, flatten_outline, iter_nodes, node_text
from app.services.projects.app_context import load_app_facts_for_project

_SECTION_CHARS = 1400   # per-observation budget (keeps agent token use bounded)
_STOP = {"the","and","for","with","that","this","what","how","are","was","does","from","into"}


@dataclass
class ProjectKnowledge:
    docs: list[IndexedDoc]
    page_texts: dict[str, dict]
    doc_names: dict[str, str]
    concepts: list[ProjectWikiConcept]
    facts: list[dict]               # {id, app, kind, text, confidence, source_ref}

    def has_any(self) -> bool:
        return bool(self.docs or self.concepts)


@dataclass
class TraceAccumulator:
    sections: dict[tuple[str, str], dict] = field(default_factory=dict)  # (doc_id,node_id)->section
    concepts: dict[str, dict] = field(default_factory=dict)              # slug->concept
    facts: dict[str, dict] = field(default_factory=dict)                 # id->fact
    visited: dict[str, set[str]] = field(default_factory=dict)           # doc_id-> {node_id} (tree map)
    steps: list[str] = field(default_factory=list)

    def note_visit(self, doc_id: str, node_id: str) -> None:
        self.visited.setdefault(doc_id, set()).add(node_id)


async def load_project_knowledge(project_id: uuid.UUID, db: AsyncSession) -> ProjectKnowledge:
    tree_rows = (await db.execute(
        select(DocumentTree, Document.filename)
        .join(Document, Document.id == DocumentTree.document_id)
        .where(DocumentTree.project_id == project_id)
    )).all()
    docs, page_texts, doc_names = [], {}, {}
    for t, name in tree_rows:
        did = str(t.document_id)
        docs.append(IndexedDoc(document_id=t.document_id, doc_name=name, tree=t.tree_json, page_texts=t.page_texts))
        page_texts[did], doc_names[did] = t.page_texts, name
    concepts = (await db.execute(
        select(ProjectWikiConcept).where(ProjectWikiConcept.project_id == project_id)
        .order_by(ProjectWikiConcept.title)
    )).scalars().all()
    facts = await load_app_facts_for_project(project_id, db)
    return ProjectKnowledge(docs, page_texts, doc_names, list(concepts), facts)


def _terms(q: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", q.lower()) if len(w) > 2 and w not in _STOP}


def _score(text: str, title: str, terms: set[str], phrase: str) -> float:
    """Title-weighted token overlap, length-normalized, with an exact-phrase bonus.
    Deterministic + dependency-free (works under mock); semantic quality comes from the
    pre-flight seed which reuses the proven tree_search/concept-select retrieval."""
    body = f"{title} {text}".lower()
    if not body.strip():
        return 0.0
    overlap = sum(body.count(t) for t in terms)
    title_hits = sum(title.lower().count(t) for t in terms) * 2
    phrase_bonus = 3.0 if phrase and phrase in body else 0.0
    return (overlap + title_hits + phrase_bonus) / (1 + len(body) / 4000)


def build_tools(k: ProjectKnowledge, trace: TraceAccumulator) -> list:
    """DSPy-compatible callables. ReAct reads name/__doc__/type-hints — keep docstrings crisp."""

    def list_documents() -> str:
        """List every project document with its section outline ('[Di] node_id · title — summary').
        Call this first to see what exists; then read_section to open the full text of a node."""
        trace.steps.append(f"Listed {len(k.docs)} documents")
        return flatten_outline(k.docs) or "(no indexed documents)"

    def search_sections(query: str) -> str:
        """Find the most relevant document sections for a query across ALL project documents.
        Returns 'S:<doc_id>:<node_id> · title — summary' lines. Open the best with read_section.
        Cite a section as S:<doc_id>:<node_id>."""
        terms, phrase = _terms(query), query.lower().strip()
        scored = []
        for d in k.docs:
            for n in iter_nodes(d.tree):
                if n.get("node_id") == "0000":          # synthetic root
                    continue
                s = _score(n.get("summary", ""), n.get("title", ""), terms, phrase)
                if s > 0:
                    scored.append((s, str(d.document_id), n))
        scored.sort(key=lambda x: -x[0])
        if not scored:
            return "(no matching sections — call list_documents to browse the outline)"
        trace.steps.append(f"Searched sections for “{query}” → {len(scored)} hits")
        return "\n".join(
            f"S:{did}:{n.get('node_id')} · {n.get('title','')} — {(n.get('summary') or '')[:120]}"
            for _, did, n in scored[:8])

    def read_section(doc_id: str, node_id: str) -> str:
        """Read one section's full source text. doc_id/node_id come from list_documents or
        search_sections. Cite it as S:<doc_id>:<node_id>."""
        for d in k.docs:
            if str(d.document_id) == doc_id:
                node = find_node(d.tree, node_id)
                if not node:
                    return "(section not found)"
                text = node_text(node, d.page_texts)
                trace.sections[(doc_id, node_id)] = {
                    "doc_id": doc_id, "doc_name": k.doc_names.get(doc_id, ""), "node_id": node_id,
                    "title": (node.get("title") or "").strip(),
                    "pages": (f"{node.get('start_index')}-{node.get('end_index')}"
                              if node.get("start_index") is not None else ""),
                    "text": text,
                }
                trace.note_visit(doc_id, node_id)
                trace.steps.append(f"Read {k.doc_names.get(doc_id,'?')} › {node.get('title','§'+node_id)}")
                return (text[:_SECTION_CHARS] + " …") if len(text) > _SECTION_CHARS else (text or "(empty section)")
        return "(document not found)"

    def search_wiki(query: str) -> str:
        """Search the Project Wiki concepts (cross-document synthesized knowledge).
        Returns 'C:<slug> · Title — brief' lines. Open one with read_concept. Cite as C:<slug>."""
        terms, phrase = _terms(query), query.lower().strip()
        scored = sorted(((_score(c.brief, c.title, terms, phrase), c) for c in k.concepts), key=lambda x: -x[0])
        hits = [c for s, c in scored if s > 0] or list(k.concepts[:3])
        if not hits:
            return "(no wiki concepts compiled yet)"
        trace.steps.append(f"Searched wiki for “{query}”")
        return "\n".join(f"C:{c.slug} · {c.title} — {c.brief}" for c in hits[:6])

    def read_concept(slug: str) -> str:
        """Read a Project Wiki concept's full content and the sections it's grounded in.
        Cite the concept as C:<slug>; you may also cite its underlying S: sections."""
        for c in k.concepts:
            if c.slug == slug:
                trace.concepts[slug] = {
                    "slug": slug, "title": c.title, "brief": c.brief,
                    "tree_node_refs": c.tree_node_refs or [],
                }
                for r in (c.tree_node_refs or []):       # concept → cross-index sections
                    if r.get("doc_id") and r.get("node_id"):
                        trace.note_visit(str(r["doc_id"]), str(r["node_id"]))
                trace.steps.append(f"Read concept “{c.title}”")
                refs = "; ".join(f"S:{r.get('doc_id')}:{r.get('node_id')} ({r.get('title','')})"
                                 for r in (c.tree_node_refs or [])[:6])
                return f"# {c.title}\n{c.content_md}\n\nGrounded in: {refs or '(none)'}"
        return "(concept not found)"

    def lookup_facts(query: str) -> str:
        """Look up App Brain facts about the systems/integrations involved.
        Returns 'F:<id> [app/kind] text' lines. Cite a fact as F:<id>."""
        terms, phrase = _terms(query), query.lower().strip()
        scored = sorted(((_score(f["text"], f.get("app",""), terms, phrase), f) for f in k.facts), key=lambda x: -x[0])
        hits = [f for s, f in scored if s > 0][:8] or k.facts[:5]
        for f in hits:
            trace.facts[f["id"]] = f
        if not hits:
            return "(no app facts in scope for this project)"
        trace.steps.append(f"Looked up facts for “{query}”")
        return "\n".join(f"F:{f['id']} [{f['app']}/{f['kind']}] {f['text'][:160]}" for f in hits)

    tools = [list_documents, search_sections, read_section, search_wiki, read_concept]
    if k.facts:
        tools.append(lookup_facts)
    return tools
```

### B2. Pre-flight seed — `app/services/rag/project_seed.py` (NEW)

Reuses the **proven** retrieval so the agent starts grounded. Both calls are already mock-safe.

```python
async def build_seed(project_id, question, k: ProjectKnowledge, trace: TraceAccumulator, db) -> str:
    """One async pass before the (sync) ReAct loop: proven tree_search over all project
    trees + wiki concept-select. Pre-records refs into trace so the Evidence rail is
    populated even before the agent's first tool call."""
    from app.config import get_settings
    from app.services.corpus_index import get_corpus_index_provider
    from app.services.skills.wiki_compiler.dspy_wiki import run_concept_select

    lines: list[str] = []
    # Sections — reuse CorpusIndexProvider.tree_search (LLM-reasoned in real mode, deterministic in mock)
    if k.docs:
        sections = await get_corpus_index_provider().tree_search(
            query=question, docs=k.docs, top_k=get_settings().tree_search_top_k)
        for s in sections:
            did, nid = str(s.document_id), s.node_id
            trace.sections[(did, nid)] = {
                "doc_id": did, "doc_name": s.doc_name, "node_id": nid, "title": s.title,
                "pages": f"{s.page_start}-{s.page_end}" if s.page_start else "", "text": s.text,
            }
            trace.note_visit(did, nid)
            lines.append(f"S:{did}:{nid} · {s.doc_name} › {s.title} — {s.text[:200]}")
    # Concepts — reuse the existing concept-select signature with project outlines
    if k.concepts:
        outline = "\n".join(f"{c.slug} · {c.title} — {c.brief}" for c in k.concepts)
        try:
            sel = await run_concept_select(question, outline, "(none)")
            for slug in (sel.get("concept_slugs", []) if isinstance(sel, dict) else []):
                c = next((x for x in k.concepts if x.slug == slug), None)
                if c:
                    trace.concepts[slug] = {"slug": slug, "title": c.title, "brief": c.brief,
                                            "tree_node_refs": c.tree_node_refs or []}
                    lines.append(f"C:{slug} · {c.title} — {c.brief}")
        except Exception:
            pass
    if lines:
        trace.steps.append(f"Pre-retrieved {len(lines)} candidate references")
    return "\n".join(lines) or "(no pre-retrieved candidates — explore with the tools)"
```

### B3. DSPy ReAct module — `app/services/skills/project_chat/dspy_chat.py` (NEW)

```python
"""Project Copilot — the codebase's first dspy.ReAct agent. Tools navigate the
project's PageIndex trees, wiki concepts, and app facts."""
import dspy

class ProjectChatSignature(dspy.Signature):
    """Answer the user's question about THIS project using ONLY the tools and the
    pre-retrieved seed_context. Verify and expand the seed: open sections with
    read_section, pull concepts with read_concept, check systems with lookup_facts.
    Prefer specific leaf sections over broad summaries. Ground EVERY claim with an
    inline citation token — S:<doc_id>:<node_id> (section), C:<slug> (concept),
    F:<id> (fact). Copy ids verbatim from tool output; never invent ids or tokens.
    If the knowledge base does not cover the question, say so plainly and do not guess."""
    project_name: str = dspy.InputField()
    seed_context: str = dspy.InputField(desc="Pre-retrieved candidate sections/concepts to verify+expand")
    conversation: str = dspy.InputField(desc="Prior chat turns, or empty")
    question: str = dspy.InputField()
    answer: str = dspy.OutputField(desc="Markdown answer with inline S:/C:/F: citation tokens")

def build_react(tools: list, max_iters: int = 6) -> dspy.ReAct:
    return dspy.ReAct(ProjectChatSignature, tools=tools, max_iters=max_iters)
```

DSPy LM config reused verbatim: `_configure_dspy()` from `app/services/skills/fact_extractor/dspy_extractor.py` (lru-cached Vertex Gemini).

### B4. Streaming orchestrator — `app/services/rag/project_agent.py` (NEW)

Emits the **existing SSE event model** (`step / chunk / trace / citations / done / error`) so the frontend reader mirrors `AskPanel`.

```python
class ProjectChatAgent:
    async def stream_answer(self, *, project_id, project_name, question, db, history=None):
        from app.config import get_settings
        k = await load_project_knowledge(project_id, db)
        if not k.has_any():
            yield {"type": "error", "message": "This project has no indexed documents or wiki yet. "
                                               "Upload sources or compile the wiki first."}; return
        trace = TraceAccumulator()
        yield {"type": "step", "text": "Gathering project knowledge…"}
        seed = await build_seed(project_id, question, k, trace, db)
        # stream the seed refs into the Evidence rail immediately (partial trace)
        yield {"type": "trace", "trace": _build_trace(k, trace, partial=True)}

        if get_settings().llm_provider == "mock":
            async for ev in _mock_trajectory(k, trace, question, seed): yield ev
        else:
            async for ev in _react_stream(k, trace, project_name, question, seed, history): yield ev

        _verify_and_prune(k, trace)            # drop refs no real id backs (no broken chips)
        yield {"type": "trace", "trace": _build_trace(k, trace, partial=False)}
        yield {"type": "citations", "citations": _build_citations(trace)}
        yield {"type": "done"}
```

```python
async def _react_stream(k, trace, project_name, question, seed, history):
    from app.services.skills.fact_extractor.dspy_extractor import _configure_dspy
    from app.services.rag.rag_service import format_conversation
    _configure_dspy()
    program = dspy.streamify(
        build_react(build_tools(k, trace)),
        stream_listeners=[dspy.streaming.StreamListener(signature_field_name="answer")],
        status_message_provider=_ProjectStatusProvider(),     # see below
    )
    streamed = False
    try:
        async for chunk in program(project_name=project_name, seed_context=seed,
                                   conversation=format_conversation(history), question=question):
            if isinstance(chunk, dspy.streaming.StatusMessage):
                yield {"type": "step", "text": chunk.message}
                yield {"type": "trace", "trace": _build_trace(k, trace, partial=True)}   # live rail
            elif isinstance(chunk, dspy.streaming.StreamResponse) and chunk.chunk:
                streamed = True
                yield {"type": "chunk", "text": chunk.chunk}
    except Exception as exc:
        log.warning("project ReAct stream failed (%s); one-shot fallback", exc)
    if not streamed:        # version-safe fallback: run once in a thread, replay steps, emit answer
        import asyncio
        loop = asyncio.get_running_loop()
        pred = await loop.run_in_executor(None, lambda: build_react(build_tools(k, trace))(
            project_name=project_name, seed_context=seed,
            conversation=format_conversation(history), question=question))
        for s in trace.steps: yield {"type": "step", "text": s}
        yield {"type": "chunk", "text": getattr(pred, "answer", "") or
               "I couldn't find enough in this project's knowledge to answer that."}
```

`_ProjectStatusProvider(dspy.streaming.StatusMessageProvider)` overrides `tool_start_status_message`/`tool_end_status_message` to humanize tool calls (e.g. `read_section(doc,0007)` → "Reading PayHub-Spec › Refund flow"). **Version guard:** if `dspy.streaming.StatusMessage`/`StatusMessageProvider` are absent in the installed DSPy, skip `status_message_provider`, rely on the non-streaming fallback for steps; the SSE contract is unchanged. Confirm the DSPy version's streaming API in commit 1.

### B5. Citation verification + grounding gate — in `project_agent.py`

```python
_TOKEN_RE = re.compile(r"\b(S:[0-9a-fA-F-]{8,}:[A-Za-z0-9._-]+|C:[a-z0-9][a-z0-9_-]+|F:[0-9a-fA-F-]{8,})\b")

def _verify_and_prune(k, trace):
    """Keep only refs that resolve in loaded knowledge (the agent occasionally fabricates an id).
    Guarantees every chip the UI renders will open."""
    valid_docs = {str(d.document_id) for d in k.docs}
    trace.sections = {(d, n): v for (d, n), v in trace.sections.items()
                      if d in valid_docs and find_node(next(x.tree for x in k.docs if str(x.document_id)==d), n)}
    slugs = {c.slug for c in k.concepts}
    trace.concepts = {s: v for s, v in trace.concepts.items() if s in slugs}
    fact_ids = {f["id"] for f in k.facts}
    trace.facts = {i: v for i, v in trace.facts.items() if i in fact_ids}
```

`_build_trace(k, trace, partial)` → a **`ProjectAskTrace`** dict (superset of `DeepTrace`, so `AskTraceDrawer` still renders, and the new `EvidencePanel` reads the extras):

```python
def _build_trace(k, trace, partial):
    docs_index = {str(d.document_id): d for d in k.docs}
    return {
        "mode": "agent",
        "selected_concepts": [{"slug": c["slug"], "title": c["title"], "brief": c["brief"]} for c in trace.concepts.values()],
        "selected_documents": [],                       # (kept for DeepTrace shape compat)
        "sections": [{"doc_id": s["doc_id"], "doc_name": s["doc_name"], "node_id": s["node_id"],
                      "title": s["title"], "pages": s["pages"], "excerpt": s["text"][:300]}
                     for s in trace.sections.values()],
        "chunks": [],
        "facts": [{"id": f["id"], "app": f["app"], "kind": f["kind"], "text": f["text"][:200]}
                  for f in trace.facts.values()],
        # tree map: per visited document, the outline + which node_ids were touched
        "tree_map": [{"doc_id": did, "doc_name": k.doc_names.get(did, ""),
                      "visited": sorted(nodes),
                      "outline": _outline_nodes(docs_index[did].tree) if did in docs_index else []}
                     for did, nodes in trace.visited.items()],
        "fallback_used": False,
        "context_chars": sum(len(s["text"]) for s in trace.sections.values()),
        "partial": partial,
    }
```

`_outline_nodes(tree)` → `[{node_id, title, depth}]` (flat, depth-tagged) for the rail's tree view.

`_build_citations(trace)` → layered, each carrying its raw token so inline chips reconcile with rail rows:

```python
def _build_citations(trace):
    out = [{"id": f"concept-{c['slug']}", "token": f"C:{c['slug']}", "kind": "concept",
            "doc_name": f"Concept · {c['title']}", "chunk_no": 0, "text_excerpt": c["brief"][:200]}
           for c in trace.concepts.values()]
    out += [{"id": f"sec-{s['node_id']}", "token": f"S:{s['doc_id']}:{s['node_id']}", "kind": "section",
             "doc_name": f"{s['doc_name']} › {s['title']}" if s["title"] else s["doc_name"],
             "chunk_no": 0, "text_excerpt": s["text"][:200]} for s in trace.sections.values()]
    out += [{"id": f"fact-{f['id']}", "token": f"F:{f['id']}", "kind": "fact",
             "doc_name": f"{f['app']} · {f['kind']}", "chunk_no": 0, "text_excerpt": f["text"][:200]}
            for f in trace.facts.values()]
    return out
```

### B6. Deterministic mock — `_mock_trajectory` (in `project_agent.py`)

No fixture file; scripted over the **real** loaded knowledge so ids resolve and tests assert real values.

```python
async def _mock_trajectory(k, trace, question, seed):
    import asyncio
    tools = build_tools(k, trace)
    for name, fn in (("list_documents", tools[0]),):
        yield {"type": "step", "text": "Listed project documents"}; fn()
    parts = []
    if k.docs:
        d = k.docs[0]; first = next((n for n in iter_nodes(d.tree) if n.get("node_id") != "0000"), None)
        if first:
            did, nid = str(d.document_id), str(first["node_id"])
            tools[2](did, nid)                       # read_section → records section + visit
            parts.append(f"Per the source, see S:{did}:{nid}.")
    if k.concepts:
        tools[4](k.concepts[0].slug)                 # read_concept → records concept + grounded visits
        parts.append(f"This relates to C:{k.concepts[0].slug}.")
    if k.facts:
        trace.facts[k.facts[0]["id"]] = k.facts[0]
        parts.append(f"A known fact is F:{k.facts[0]['id']}.")
    answer = "Mock project answer. " + " ".join(parts) if parts else \
             "Mock project answer. No specific sources were found for this question."
    for i in range(0, len(answer), 12):
        yield {"type": "chunk", "text": answer[i:i+12]}; await asyncio.sleep(0)
```

### B7. Endpoint + router — `app/api/project_ask.py` (NEW), mounted in `app/main.py`

```python
router = APIRouter(tags=["project-ask"])

@router.post("/projects/{project_id}/ask")
@limiter.limit("20/minute")
async def ask_project(request: Request, body: ProjectAskRequest,
                      project: Project = Depends(get_project_or_404),
                      user: User = Depends(get_current_user),
                      db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    await audit.emit(db, event="project.ask", actor_id=str(user.id),
                     metadata={"project_id": str(project.id),
                               "question_hash": hashlib.sha256(body.question.encode()).hexdigest()})
    await db.commit()
    async def gen():
        async for ev in ProjectChatAgent().stream_answer(
                project_id=project.id, project_name=project.name,
                question=body.question, db=db, history=body.history):
            yield f"data: {json.dumps(ev)}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Transfer-Encoding": "chunked"})
```

- Access: `get_project_or_404` (owner-or-member; admins all) — the dep used by `project_wiki.py`/provenance.
- SSE headers copied from `apps.py::ask_app_brain` (prevents proxy buffering).
- Mount in `app/main.py` next to the other project routers.

### B8. Sessions — mirror `AppAskSession` exactly

- **Model** `app/models/project_ask_session.py` (NEW): identical to `AppAskSession` (`TimestampMixin`, `id`, `project_id` FK→projects CASCADE, `user_id` FK→users CASCADE nullable, `title` Text, `messages` JSONB default list), index `ix_project_ask_sessions_project_user (project_id, user_id, updated_at)`. **Register in `app/models/__init__.py`.**
- **Migration** `alembic/versions/0022_project_ask_sessions.py` (NEW): hand-written raw SQL, `CREATE TABLE IF NOT EXISTS project_ask_sessions (...)` + index, `op.execute` style matching `0020`/`0021`; downgrade drops table.
- **Session endpoints** in `project_ask.py` — copy the four `apps.py` handlers verbatim, swap `AppAskSession`→`ProjectAskSession`, `app`/`require_app_access`→`project`/`get_project_or_404`, scope `user_id == user.id`:
  `GET /projects/{id}/ask/sessions`, `GET /…/sessions/{sid}`, `POST /…/sessions`, `DELETE /…/sessions/{sid}`.

### B9. Schemas — `app/schemas/project.py` (or a small `project_ask.py`)

Reuse `AskTurn`, `AskSessionMessage`, `AskSessionCitation`, `AskSessionSave`, `AskSessionListItem`, `AskSessionRead` from `app/schemas/app.py` (import them). Add only:

```python
class ProjectAskRequest(BaseModel):
    question: Annotated[str, Field(min_length=1, max_length=1000)]
    history: Annotated[list[AskTurn], Field(max_length=20)] = []
    # no `mode`/`top_k` — the agent decides its own depth
```

---

## Frontend

All tokens via `globals.css` `:root` (`--accent` emerald, `--bg-*`, `--text-*`, `--border-*`). `'use client'`, framer-motion honoring `useReducedMotion()`, sonner for errors. No new shadcn primitives needed.

### F1. Shared inline-token renderer — `lib/inlineTokens.tsx` (NEW)

Lift `renderInline` + `TOKEN_SPLIT` out of `BrainWiki.tsx` into a shared module and re-export from `BrainWiki.tsx` (no behavior change there). Add a thin `ProjectMarkdown` that renders answer markdown with project-scope `S:/C:/F:` chips:

```tsx
export const TOKEN_SPLIT = /(\[\[[^\]]+\]\]|\*\*[^*]+\*\*|\bF:[0-9a-fA-F-]{8,}\b|\bC:[a-z0-9][a-z0-9_-]+\b|\bS:[0-9a-fA-F-]{8,}:[A-Za-z0-9._-]+\b)/g
export function renderInline(text, onLink, projectId, onHoverToken?) { /* moved from BrainWiki, + optional onHoverToken to sync the Evidence rail */ }
export function ProjectMarkdown({ md, projectId, onHoverToken }: { md: string; projectId: string; onHoverToken?: (t: string|null)=>void }) {
  // line-based markdown (## / # / - / ---) reusing renderInline per line, like BrainWiki's MarkdownBody
}
```

### F2. View shell — `frontend/app/components/AskProjectView.tsx` (NEW)

Two-pane layout used by the workspace `'ask'` view; owns the shared `trace`/`citations`/`hoverToken` state so the conversation and Evidence rail stay in lock-step.

```tsx
interface Props { projectId: string }
export function AskProjectView({ projectId }: Props) {
  const [trace, setTrace] = useState<ProjectAskTrace | null>(null)     // latest (live) trace
  const [hoverToken, setHoverToken] = useState<string | null>(null)
  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_minmax(320px,38%)] gap-4 h-[calc(100vh-200px)]">
      <ProjectChatPanel projectId={projectId} onTrace={setTrace}
                        hoverToken={hoverToken} onHoverToken={setHoverToken} />
      <EvidencePanel projectId={projectId} trace={trace} hoverToken={hoverToken} />
    </div>
  )
}
```

### F3. `ProjectChatPanel.tsx` (NEW) — conversation + reasoning trail

Fork of `AskPanel.tsx` (same SSE reader, sessions dropdown, autosave, textarea, framer-motion), with these deltas:
- **No mode toggle** (the agent self-paces). Header: title + History + New chat (reuse AskPanel's bar minus modes).
- **Endpoint**: `authedFetch(`/api/projects/${projectId}/ask`, { method:'POST', body: JSON.stringify({ question, history }) })`; SSE event switch identical (`step/chunk/trace/citations/error/done`). On each `trace` event call `onTrace(event.trace)` to drive the rail.
- **Answer rendering**: `<ProjectMarkdown md={m.content} projectId={projectId} onHoverToken={onHoverToken} />` (inline `IntakeTraceChip`s), with the streaming caret from AskPanel.
- **Reasoning trail**: identical to AskPanel's `m.steps` block (spinner on in-flight step, green check done), labeled "Reasoning".
- **Grounded-in footer**: replace AskPanel's CitationChip row with a compact summary button — "▣ Grounded in N sources · View trace ▸" — opening `AskTraceDrawer` (works with `ProjectAskTrace`). Inline chips already carry the per-claim citations, so the chip-row is redundant; the summary keeps it clean.
- **Empty state**: `StarterChips` (F5).
- **Sessions** via `api.projects.listChatSessions/getChatSession/saveChatSession/deleteChatSession` (F7). Persist transcript on `done` (compact: role/content/citations/trace), same shape as AppAskSession.

State type:
```tsx
interface ChatMessage { role:'user'|'assistant'; content:string; streaming?:boolean
  steps?:string[]; citations?:CitationItem[]; trace?:ProjectAskTrace }
```

### F4. `EvidencePanel.tsx` (NEW) — live cross-index references

The distinctive surface. Sticky right rail; updates on every `trace` event (partial during streaming, final after `done`).

```tsx
export function EvidencePanel({ projectId, trace, hoverToken }: {
  projectId: string; trace: ProjectAskTrace | null; hoverToken: string | null }) {
  if (!trace) return <EvidenceEmpty />                       // hint: "References will appear here as the copilot works"
  return (
    <div className="rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] overflow-y-auto p-3 space-y-4">
      <GroundingMeter sections={trace.sections} docs={trace.tree_map} concepts={trace.selected_concepts} facts={trace.facts}/>
      <TreeMap map={trace.tree_map} projectId={projectId} hoverToken={hoverToken}/>     {/* per-doc outline, visited nodes ●-highlighted */}
      <ConceptList concepts={trace.selected_concepts} projectId={projectId} hoverToken={hoverToken}/>
      <FactList facts={trace.facts} projectId={projectId} hoverToken={hoverToken}/>
    </div>
  )
}
```

- **GroundingMeter**: "N sections · M docs · K concepts · J facts" + a strength bar (heuristic: clamp((sections + concepts*1.5 + facts*0.5)/6,0,1) → weak/medium/strong, colored via `--status-*`). Communicates answer confidence at a glance.
- **TreeMap**: for each `tree_map[doc]`, a collapsible document with its `outline` nodes indented by `depth`; visited node_ids get a filled `●` + accent text + a "read" tag; others muted. **This is the "references across pageindexes" made visible** — multiple documents, the exact nodes touched. Each visited node is a button → `api.projects.getSourceSection` peek (reuse the BrainWiki `GroundedIn` popover pattern, or open `IntakeTraceChip` with `S:doc:node`).
- **ConceptList**: concept cards; expand → its `tree_node_refs` rendered as `S:` chips (concept → grounded sections, the cross-index link). 
- **FactList**: fact cards (app · kind · text), click → `IntakeTraceChip` `F:` popover.
- **Hover sync**: when `hoverToken` matches a row's token, ring-highlight it (`ring-2 ring-[var(--accent)]`). Inline chip ↔ rail two-way affordance.

### F5. `StarterChips.tsx` (NEW) — smart empty state

On mount, `api.projects.getWiki(projectId)` → top 3 concept titles + RU objective (`api.projects.understanding`) → render clickable starter questions:
- "How does **{concept}** work in this project?"
- "What are the risks around **{concept}**?"
- "Summarize the objective and what we must deliver."
Falls back to generic starters if wiki/RU empty. Clicking fills the textarea and submits.

### F6. Trace drawer reuse — `AskTraceDrawer.tsx`

Works unchanged with `ProjectAskTrace` (superset of `DeepTrace`). Optional polish: add a `facts` `Section` and a "Tree map" `Section` so the full-trace drawer matches the rail. Low priority — the rail is the primary surface.

### F7. Workspace wiring — `frontend/app/projects/[id]/page.tsx`

- `type View = 'interview' | 'wiki' | 'ask' | 'concept-brief' | 'brd' | 'frs' | null` (add `'ask'`); include `'ask'` in the `useState` initializer guard.
- Add a `NavItem` after Project Wiki:
  ```tsx
  <NavItem label="Ask" sublabel="Chat with the project" icon={<MessageSquare size={14} />}
           active={view === 'ask'} onClick={() => setView('ask')} />
  ```
  (import `MessageSquare` from lucide-react).
- Render block, mirroring the wiki view's back-header:
  ```tsx
  if (view === 'ask') {
    return (
      <div className="space-y-4">
        <button onClick={() => setView(null)} className="text-xs text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] flex items-center gap-1"><ChevronLeft size={14}/> Back</button>
        <AskProjectView projectId={projectId} />
      </div>
    )
  }
  ```

### F8. API client — `frontend/lib/api.ts` (`api.projects`)

```ts
// ── Ask the Project (E2 copilot) ──────────────────────────────────────────
listChatSessions: (id: string) => apiFetch<AskSessionListItem[]>(`/api/projects/${id}/ask/sessions`),
getChatSession:   (id: string, sid: string) => apiFetch<AskSessionRead>(`/api/projects/${id}/ask/sessions/${sid}`),
saveChatSession:  (id: string, body: { id: string|null; title: string; messages: AskSessionMessage[] }) =>
                    apiFetch<{ id: string; updated_at: string }>(`/api/projects/${id}/ask/sessions`, { method:'POST', body: JSON.stringify(body) }),
deleteChatSession:(id: string, sid: string) => apiFetch<void>(`/api/projects/${id}/ask/sessions/${sid}`, { method:'DELETE' }),
// `ask` itself uses raw authedFetch in ProjectChatPanel (streaming) — no wrapper.
```

### F9. Types — `frontend/lib/types.ts`

```ts
export interface TreeMapNode { node_id: string; title: string; depth: number }
export interface TreeMapDoc { doc_id: string; doc_name: string; visited: string[]; outline: TreeMapNode[] }
export interface TraceFact { id: string; app: string; kind: string; text: string }
export interface ProjectAskTrace extends DeepTrace {       // DeepTrace stays the base
  mode: 'agent'
  facts: TraceFact[]
  tree_map: TreeMapDoc[]
  partial?: boolean
}
export interface CitationItem { /* existing */ token?: string; kind?: 'section'|'concept'|'fact' }  // additive
```
Reuse `AskSessionListItem/Message/Read`, `AskTurn`.

---

## SSE event contract

| event       | payload                                   | UI effect                                                        |
|-------------|-------------------------------------------|------------------------------------------------------------------|
| `step`      | `{text}`                                  | append to reasoning trail (spinner→check)                        |
| `trace`     | `{trace: ProjectAskTrace}` (partial/final)| refresh Evidence rail live; `partial:true` while streaming       |
| `chunk`     | `{text}`                                  | append answer tokens (inline `S:/C:/F:` chips via ProjectMarkdown)|
| `citations` | `{citations: CitationItem[]}` (verified)  | drive "Grounded in N" footer; reconcile inline chips             |
| `error`     | `{message}`                               | toast + inline error                                             |
| `done`      | `{}`                                      | stop caret; autosave transcript                                  |

---

## Files to create / modify

**Create — backend**
| File | Purpose |
|---|---|
| `backend/app/services/rag/project_tools.py` | `ProjectKnowledge`, `TraceAccumulator`, loader, 6 tools, ranker |
| `backend/app/services/rag/project_seed.py` | pre-flight `tree_search` + concept-select seed |
| `backend/app/services/skills/project_chat/dspy_chat.py` | ReAct signature + builder |
| `backend/app/services/rag/project_agent.py` | orchestrator, `_react_stream`, `_mock_trajectory`, verify, trace/citation builders, `_ProjectStatusProvider` |
| `backend/app/api/project_ask.py` | `/projects/{id}/ask` + 4 session endpoints |
| `backend/app/models/project_ask_session.py` | session model |
| `backend/alembic/versions/0022_project_ask_sessions.py` | migration |
| `backend/tests/test_project_chat.py` | mock tests |

**Create — frontend**
| File | Purpose |
|---|---|
| `frontend/lib/inlineTokens.tsx` | shared `renderInline`/`TOKEN_SPLIT` + `ProjectMarkdown` |
| `frontend/app/components/AskProjectView.tsx` | two-pane shell + shared state |
| `frontend/app/components/ProjectChatPanel.tsx` | conversation + trail + input |
| `frontend/app/components/EvidencePanel.tsx` | grounding meter, tree map, concepts, facts |
| `frontend/app/components/StarterChips.tsx` | smart empty-state starters |

**Modify**
| File | Change |
|---|---|
| `backend/app/main.py` | mount `project_ask` router |
| `backend/app/models/__init__.py` | register `ProjectAskSession` |
| `backend/app/schemas/project.py` | `ProjectAskRequest` (reuse `AskTurn`) |
| `frontend/app/projects/[id]/page.tsx` | `'ask'` in `View` + guard + `NavItem` + render block |
| `frontend/lib/api.ts` | 4 project chat-session methods |
| `frontend/lib/types.ts` | `ProjectAskTrace`, `TreeMapDoc/Node`, `TraceFact`, additive `CitationItem` fields |
| `frontend/app/components/BrainWiki.tsx` | import `renderInline`/`TOKEN_SPLIT` from `lib/inlineTokens` (no behavior change) |
| after backend lands | `graphify update .` |

**Reused unchanged**: `corpus_index/base.py` helpers + `get_corpus_index_provider().tree_search`, `wiki_compiler.run_concept_select`, `rag_service.format_conversation`, `app_context.load_app_facts_for_project`, `IntakeTraceChip.tsx`, `AskTraceDrawer.tsx`, `get_project_source_section` + `getWikiConcept`/`resolveFact` endpoints, `_configure_dspy`, `@limiter`, `audit.emit`.

---

## Verification

**1. Mock integration (`LLM_PROVIDER=mock`, real PG/Redis) — `backend/tests/test_project_chat.py`**
- Seed a project with ≥2 indexed `DocumentTree`s + ≥1 `ProjectWikiConcept` (with `tree_node_refs`) + an in-scope `ProjectApp`/`AppFact`. Unique ids (`f"prj{uuid4().hex[:8]}"`).
- POST `/projects/{id}/ask`; parse the SSE stream. Assert order `step+ → trace(partial) → chunk+ → trace(final) → citations → done`.
- Assert the answer contains a **real** `S:<doc_id>:<node_id>` token and that `citations[]` ids match loaded sections/concepts/facts.
- Assert `trace.tree_map` lists the visited doc(s) with `visited` node_ids ⊆ that doc's outline (proves cross-index reference tracking).
- **Verification gate**: inject a fabricated token path → assert `_verify_and_prune` drops it (no citation for a non-existent id).
- Empty project (no trees, no wiki) → `error` event, no crash.
- Session round-trip: POST → list → get → delete (scoped to user).

**2. Token resolution** — for each emitted `S:/C:/F:` token, call `get_project_source_section` / `getWikiConcept` / `resolveFact` → 200 (guarantees every chip opens).

**3. Live smoke (real Vertex)** — `make migrate && make dev-be dev-fe worker`; seed `PRJ-0001` (`backend/scripts/seed_projects.py`). Open project ▸ **Ask**. Ask *"How are refunds handled and what's the SLA?"*:
- reasoning trail streams tool calls (list/search/read/concept/fact);
- Evidence rail fills live — tree map highlights visited nodes across ≥2 documents, concept + fact cards appear;
- answer streams with inline chips; clicking `S:`/`C:`/`F:` opens the popover; hovering a chip ring-highlights its rail row;
- "View trace" drawer matches the rail; refresh → History replays the session.

**4. Gates** — `make typecheck lint test-be` green; frontend `make typecheck`/lint green; verify UI in dev-browser (login `admin@specforge.test`). Confirm DSPy streaming API (StatusMessage/StreamListener) in commit 1; else non-streaming fallback path covers tests 1–3.

---

## Build sequence (commits)

1. **DSPy spike** — confirm installed `dspy.ReAct` + `streamify` + `StatusMessageProvider` API; lock the streaming vs fallback path. *(de-risks everything)*
2. **Backend core** — `project_tools.py`, `project_seed.py`, `dspy_chat.py`, `project_agent.py` (with mock). Unit-test the tools + mock trajectory directly.
3. **Endpoint + sessions** — `project_ask.py`, model, migration `0022`, schema, `main.py`, `__init__.py`. Mock integration tests green.
4. **Frontend data plumbing** — `inlineTokens.tsx` lift, `api.ts`, `types.ts`, `ProjectChatPanel` (conversation works end-to-end with inline chips).
5. **Evidence experience** — `EvidencePanel` (tree map / concepts / facts / grounding meter), `AskProjectView`, `StarterChips`, hover-sync.
6. **Wire the tab** — `page.tsx` NavItem + view; live smoke on `PRJ-0001`; polish motion/empty states; `graphify update .`.

## Risks & mitigations
- **DSPy version drift** (streaming/ReAct API) → commit-1 spike + non-streaming fallback that satisfies all tests.
- **Agent fabricates ids** → `_verify_and_prune` + tool docstrings demanding verbatim ids; chips can't break.
- **Latency** (seed + multi-iter loop) → `max_iters=6`, per-section char budget, seed runs once; stream steps so the UI feels alive immediately.
- **Mock determinism for an agent** → no fixture; scripted trajectory over real loaded knowledge keeps CI green and asserts real ids.
- **Token budget** → observations truncated to `_SECTION_CHARS`; seed excerpts capped.
