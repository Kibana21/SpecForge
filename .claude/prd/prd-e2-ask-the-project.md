# Ask the Project — Agentic Vectorless Chat (E2)

## Context

SpecForge already turns a project's corpus into PageIndex **reasoning trees** (`document_trees`), a **Project Wiki** of cross-document concepts (`project_wiki_concepts`), and links each project to **App Brain facts** (`ProjectApp` → `AppFact`). Today you can *read* this knowledge (wiki, lineage map, source peeks) and *generate* artifacts from it (CB/BRD/FRS), but you cannot **ask it questions**.

We will add a chat interface to the project workspace, powered by a **DSPy ReAct agent** that navigates the project's PageIndex trees the way VectifyAI's `agentic_vectorless_rag_demo.py` does — outline-first, then selectively reading sections — but orchestrated as a DSPy tool-calling loop (like the `dspy.ai` customer-service agent). The agent grounds every answer in three citation layers (`S:` source sections, `C:` wiki concepts, `F:` app facts) and streams its full reasoning trajectory so the user *sees it think*.

This is the first `dspy.ReAct` / tool-calling agent in the codebase. The decisions taken (confirmed with the user): **true ReAct engine**, **full S:/C:/F: grounding**, **left-nav "Ask" tab**.

Outcome: a transparent, traceable project copilot that reuses ~80% of the existing Ask/citation/streaming infrastructure and introduces a clean, mockable agentic-retrieval primitive.

---

## Architecture overview

```
Frontend  projects/[id]/page.tsx  ── View 'ask' ──▶  ProjectChatPanel.tsx
                                                       │ authedFetch SSE
                                                       ▼
Backend   POST /api/projects/{id}/ask  (project_ask.py router, @limiter 20/min)
                                                       │
                                                       ▼
          ProjectChatAgent.stream_answer()  (services/rag/project_agent.py)
            1. load ProjectKnowledge once  (trees + wiki + app facts)  ── in memory
            2. build tools as closures over that knowledge  (project_tools.py)
            3. dspy.streamify( dspy.ReAct(ProjectChatSignature, tools) )
                 │  StatusMessage  ─▶ SSE 'step'   (tool call / observation)
                 │  StreamResponse ─▶ SSE 'chunk'  (answer tokens, with S:/C:/F:)
            4. emit 'trace'  (everything the tools touched)
            5. emit 'citations' (structured refs accumulated by tools)
            6. emit 'done'  ; persist transcript to project_ask_sessions
                                                       │
        MOCK path (LLM_PROVIDER=mock): skip dspy, run a scripted mini-trajectory
        over the *real* loaded knowledge so citations are real → CI deterministic.
```

The agent's tools are thin, **synchronous, in-memory** wrappers — we pre-load all project knowledge once (a chat corpus is bounded), so the ReAct loop (running in a thread via `run_in_executor`) never touches the async DB. Tools reuse the existing pure-Python tree helpers (`iter_nodes`, `find_node`, `node_text`, `flatten_outline` in `corpus_index/base.py`).

---

## Backend

### 1. Knowledge loader + tools — `app/services/rag/project_tools.py` (NEW)

Load everything once, then expose closures the agent can call. Each tool **records what it returned** into a shared `TraceAccumulator` so the orchestrator can build the trace + citations after the loop.

```python
"""Agent tools over a project's PageIndex trees, wiki concepts, and app facts.
Pre-loaded in memory so the (sync, threaded) ReAct loop never touches async DB."""
from __future__ import annotations
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.project_source import DocumentTree
from app.models.project_wiki import ProjectWikiConcept
from app.services.corpus_index.base import find_node, flatten_outline, iter_nodes, node_text, IndexedDoc
from app.services.projects.app_context import load_app_facts_for_project


@dataclass
class ProjectKnowledge:
    docs: list[IndexedDoc]                  # one per indexed DocumentTree
    page_texts: dict[str, dict]             # doc_id(str) -> page_texts
    doc_names: dict[str, str]               # doc_id(str) -> filename
    concepts: list[ProjectWikiConcept]
    facts: list[dict]                       # {id, app, kind, text, confidence, source_ref}


@dataclass
class TraceAccumulator:
    sections: dict[tuple[str, str], dict] = field(default_factory=dict)  # (doc_id,node_id)->section
    concepts: dict[str, dict] = field(default_factory=dict)              # slug->concept
    facts: dict[str, dict] = field(default_factory=dict)                 # id->fact
    steps: list[str] = field(default_factory=list)                       # human-readable trail


async def load_project_knowledge(project_id: uuid.UUID, db: AsyncSession) -> ProjectKnowledge:
    tree_rows = (await db.execute(
        select(DocumentTree, Document.filename)
        .join(Document, Document.id == DocumentTree.document_id)
        .where(DocumentTree.project_id == project_id)
    )).all()
    docs, page_texts, doc_names = [], {}, {}
    for t, name in tree_rows:
        did = str(t.document_id)
        docs.append(IndexedDoc(document_id=t.document_id, doc_name=name,
                               tree=t.tree_json, page_texts=t.page_texts))
        page_texts[did] = t.page_texts
        doc_names[did] = name
    concepts = (await db.execute(
        select(ProjectWikiConcept).where(ProjectWikiConcept.project_id == project_id)
        .order_by(ProjectWikiConcept.title)
    )).scalars().all()
    facts = await load_app_facts_for_project(project_id, db)
    return ProjectKnowledge(docs, page_texts, doc_names, concepts, facts)


def build_tools(k: ProjectKnowledge, trace: TraceAccumulator) -> list:
    """Return DSPy-compatible callables (name, __doc__, type hints all matter to ReAct)."""

    def list_documents() -> str:
        """List every project document with its section outline (node_id · title — summary).
        Call this FIRST to see what exists, then read_section to pull full text."""
        trace.steps.append("Listed project documents")
        return flatten_outline(k.docs) or "(no indexed documents)"

    def read_section(doc_id: str, node_id: str) -> str:
        """Read the full source text of one section. doc_id and node_id come from list_documents
        or search_sections. Cite it in your answer as S:<doc_id>:<node_id>."""
        for d in k.docs:
            if str(d.document_id) == doc_id:
                node = find_node(d.tree, node_id)
                if node:
                    text = node_text(node, d.page_texts)
                    trace.sections[(doc_id, node_id)] = {
                        "doc_id": doc_id, "doc_name": k.doc_names.get(doc_id, ""),
                        "node_id": node_id, "title": (node.get("title") or "").strip(),
                        "pages": f"{node.get('start_index')}-{node.get('end_index')}",
                        "text": text,
                    }
                    trace.steps.append(f"Read {k.doc_names.get(doc_id,'?')} › {node.get('title','')}")
                    return text or "(empty section)"
        return "(section not found)"

    def search_sections(query: str) -> str:
        """Keyword-rank project sections by relevance to a query. Returns lines of
        'S:<doc_id>:<node_id> · title — summary'. Use read_section to open the best ones."""
        terms = {w for w in query.lower().split() if len(w) > 2}
        scored = []
        for d in k.docs:
            for n in iter_nodes(d.tree):
                if n.get("node_id") == "0000":  # synthetic root
                    continue
                hay = f"{n.get('title','')} {n.get('summary','')}".lower()
                score = sum(hay.count(t) for t in terms)
                if score:
                    scored.append((score, str(d.document_id), n))
        scored.sort(key=lambda x: -x[0])
        if not scored:
            return "(no matching sections — try list_documents to browse)"
        trace.steps.append(f"Searched sections for '{query}' → {len(scored)} hits")
        return "\n".join(
            f"S:{did}:{n.get('node_id')} · {n.get('title','')} — {(n.get('summary') or '')[:120]}"
            for _, did, n in scored[:8]
        )

    def search_wiki(query: str) -> str:
        """Search the Project Wiki concepts. Returns 'C:<slug> · Title — brief' lines.
        Use read_concept to open one. Cite concepts as C:<slug>."""
        terms = {w for w in query.lower().split() if len(w) > 2}
        scored = sorted(
            ((sum(f"{c.title} {c.brief}".lower().count(t) for t in terms), c) for c in k.concepts),
            key=lambda x: -x[0])
        hits = [c for s, c in scored if s] or list(k.concepts[:3])
        if not hits:
            return "(no wiki concepts)"
        trace.steps.append(f"Searched wiki for '{query}'")
        return "\n".join(f"C:{c.slug} · {c.title} — {c.brief}" for c in hits[:6])

    def read_concept(slug: str) -> str:
        """Read a Project Wiki concept's full content. Cite it as C:<slug>."""
        for c in k.concepts:
            if c.slug == slug:
                trace.concepts[slug] = {"slug": slug, "title": c.title, "brief": c.brief}
                trace.steps.append(f"Read concept {c.title}")
                return f"# {c.title}\n{c.content_md}"
        return "(concept not found)"

    def lookup_facts(query: str) -> str:
        """Look up App Brain facts about the systems involved. Returns 'F:<id> [app/kind] text'
        lines. Cite a fact as F:<id>."""
        terms = {w for w in query.lower().split() if len(w) > 2}
        scored = sorted(
            ((sum(f["text"].lower().count(t) for t in terms), f) for f in k.facts),
            key=lambda x: -x[0])
        hits = [f for s, f in scored if s][:8] or k.facts[:5]
        for f in hits:
            trace.facts[f["id"]] = f
        if not hits:
            return "(no app facts in scope)"
        trace.steps.append(f"Looked up facts for '{query}'")
        return "\n".join(f"F:{f['id']} [{f['app']}/{f['kind']}] {f['text'][:160]}" for f in hits)

    tools = [list_documents, search_sections, read_section, search_wiki, read_concept]
    if k.facts:
        tools.append(lookup_facts)
    return tools
```

Notes:
- `search_sections`/`search_wiki`/`lookup_facts` use **deterministic keyword ranking**, not an embedding/LLM call. The *agent* is the intelligence — these tools just surface candidates, mirroring the vectorless demo where the LLM does the selecting. This keeps tools fast, sync, and mock-free.
- All section/concept/fact ids the tools emit are **real**, so the `S:/C:/F:` tokens the agent writes resolve through the existing `IntakeTraceChip` endpoints (`get_project_source_section`, `getWikiConcept`, `resolveFact`).

### 2. DSPy ReAct module — `app/services/skills/project_chat/dspy_chat.py` (NEW)

```python
"""Project Copilot — a dspy.ReAct agent over the project's knowledge tools.
First tool-calling agent in the codebase."""
import dspy
from pydantic import BaseModel

class ProjectChatSignature(dspy.Signature):
    """Answer the user's question about THIS project using ONLY the tools provided.
    Navigate documents outline-first (list_documents / search_sections), then read the
    most relevant sections. Consult the wiki and app facts when useful. Ground every
    claim with an inline citation token: S:<doc_id>:<node_id> for a source section,
    C:<slug> for a wiki concept, F:<id> for an app fact. Never invent ids or tokens.
    If the knowledge base does not cover the question, say so plainly."""
    project_name: str = dspy.InputField()
    conversation: str = dspy.InputField(desc="Prior chat turns, or empty")
    question: str = dspy.InputField()
    answer: str = dspy.OutputField(desc="Markdown answer with inline S:/C:/F: citation tokens")

def build_react(tools: list, max_iters: int = 6) -> dspy.ReAct:
    return dspy.ReAct(ProjectChatSignature, tools=tools, max_iters=max_iters)
```

DSPy config is reused verbatim: call `_configure_dspy()` from `app/services/skills/fact_extractor/dspy_extractor.py` (lru-cached Vertex LM).

### 3. Streaming orchestrator — `app/services/rag/project_agent.py` (NEW)

Emits the **same SSE event model** the App Brain Ask already uses (`step / chunk / trace / citations / done / error`), so the frontend reader is a near-copy of `AskPanel`.

```python
class ProjectChatAgent:
    async def stream_answer(self, *, project_id, project_name, question, db,
                            history=None) -> AsyncGenerator[dict, None]:
        from app.config import get_settings
        k = await load_project_knowledge(project_id, db)
        if not k.docs and not k.concepts:
            yield {"type": "error", "message": "This project has no indexed documents or wiki yet."}
            return
        trace = TraceAccumulator()
        tools = build_tools(k, trace)

        if get_settings().llm_provider == "mock":
            async for ev in _mock_trajectory(k, trace, question): yield ev
        else:
            async for ev in _react_stream(k, trace, project_name, question, history): yield ev

        # trace + citations built from what the tools actually touched
        yield {"type": "trace", "trace": _build_trace(trace)}
        yield {"type": "citations", "citations": _build_citations(trace)}
        yield {"type": "done"}
```

**Live streaming of the ReAct trajectory** (`_react_stream`) uses `dspy.streamify` with a `StatusMessageProvider` (maps each tool call/observation to a `step` event) and a `StreamListener(signature_field_name="answer")` (maps answer deltas to `chunk` events):

```python
async def _react_stream(k, trace, project_name, question, history):
    from app.services.skills.fact_extractor.dspy_extractor import _configure_dspy
    _configure_dspy()
    react = build_react(build_tools(k, trace))
    program = dspy.streamify(
        react,
        stream_listeners=[dspy.streaming.StreamListener(signature_field_name="answer")],
        status_message_provider=_ProjectStatusProvider(),   # tool start/finish -> step text
    )
    streamed = False
    try:
        async for chunk in program(project_name=project_name,
                                   conversation=format_conversation(history), question=question):
            if isinstance(chunk, dspy.streaming.StatusMessage):
                yield {"type": "step", "text": chunk.message}
            elif isinstance(chunk, dspy.streaming.StreamResponse) and chunk.chunk:
                streamed = True
                yield {"type": "chunk", "text": chunk.chunk}
    except Exception as exc:
        log.warning("project ReAct stream failed (%s); one-shot fallback", exc)
    if not streamed:   # fallback: run once in a thread, emit recorded steps + whole answer
        loop = asyncio.get_running_loop()
        pred = await loop.run_in_executor(None, lambda: build_react(build_tools(k, trace))(
            project_name=project_name, conversation=format_conversation(history), question=question))
        for s in trace.steps: yield {"type": "step", "text": s}
        yield {"type": "chunk", "text": getattr(pred, "answer", "") or ""}
```

> If `StatusMessageProvider`/`StatusMessage` are unavailable in the installed DSPy version, fall back to the non-streaming branch unconditionally (run ReAct in executor, replay `trace.steps`, then emit the answer). Either way the SSE contract to the frontend is identical. Verify the DSPy version's streaming API during step 1 of implementation.

`format_conversation` is imported from `app/services/rag/rag_service.py` (reused).

`_build_trace` / `_build_citations` reshape `TraceAccumulator` into the existing `DeepTrace` shape (so `AskTraceDrawer` renders unchanged) and the citation array `{id, doc_name, chunk_no, text_excerpt}`, with ids `sec-…/concept-…/fact-…`.

### 4. Deterministic mock — `_mock_trajectory` (in `project_agent.py`)

No fixture file needed; it runs a scripted loop over the **real** loaded knowledge so citations resolve and tests assert real ids:

```python
async def _mock_trajectory(k, trace, question):
    yield {"type": "step", "text": "Listed project documents"}
    build_tools(k, trace)[0]()  # list_documents (records nothing; just trail)
    parts = []
    if k.docs:  # read first real section
        d = k.docs[0]; first = next((n for n in iter_nodes(d.tree) if n.get("node_id") != "0000"), None)
        if first:
            did, nid = str(d.document_id), str(first["node_id"])
            build_tools(k, trace)[2](did, nid)  # read_section -> records trace.sections
            parts.append(f"Per the source, see S:{did}:{nid}.")
    if k.concepts:
        c = k.concepts[0]; trace.concepts[c.slug] = {"slug": c.slug, "title": c.title, "brief": c.brief}
        parts.append(f"This relates to C:{c.slug}.")
    if k.facts:
        f = k.facts[0]; trace.facts[f["id"]] = f
        parts.append(f"Known fact F:{f['id']}.")
    answer = "Mock project answer. " + " ".join(parts)
    for i in range(0, len(answer), 12):   # stream in chunks like dspy_qa mock
        yield {"type": "chunk", "text": answer[i:i+12]}; await asyncio.sleep(0)
```

### 5. Endpoint + router — `app/api/project_ask.py` (NEW), mounted in `app/main.py`

```python
@router.post("/projects/{project_id}/ask")
@limiter.limit("20/minute")
async def ask_project(request: Request, body: ProjectAskRequest,
                      project: Project = Depends(get_project_or_404),
                      user: User = Depends(get_current_user),
                      db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    agent = ProjectChatAgent()
    async def gen():
        async for ev in agent.stream_answer(project_id=project.id, project_name=project.name,
                                             question=body.question, db=db, history=body.history):
            yield f"data: {json.dumps(ev)}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")
```

- `ProjectAskRequest` (in `app/schemas/`): `question: str (1-1000)`, `history: list[AskTurn] = []` — **reuse the existing `AskTurn`** schema from `app/schemas/app.py`.
- Access control: `get_project_or_404` (owner-or-member; admins see all) — same dep the wiki/provenance routes use.
- Mount the router in `app/main.py` alongside the other project routers.

### 6. Sessions (persistence) — mirror `AppAskSession`

- **Model** `app/models/project_ask_session.py` (NEW): `ProjectAskSession(project_id FK, user_id FK, title, messages JSONB)` — identical shape to `AppAskSession`. **Register it in `app/models/__init__.py`.**
- **Migration** `alembic/versions/0022_project_ask_sessions.py` (NEW): hand-written raw SQL, `CREATE TABLE IF NOT EXISTS project_ask_sessions …` + index on `(project_id, user_id, updated_at)`, following the `0020`/`0021` style.
- **Session endpoints** in the same router: `GET/POST /projects/{id}/ask/sessions`, `GET/DELETE /projects/{id}/ask/sessions/{sid}` — copy the four App Brain session handlers, swap the model/scope. Reuse the `AskSessionMessage`/`AskSessionCitation` schemas.

---

## Frontend

### 7. `frontend/app/components/ProjectChatPanel.tsx` (NEW)

Modeled directly on `AskPanel.tsx` (copy its SSE reader, session dropdown, auto-save, input box, streaming state machine), with three project-specific changes:

1. **Endpoint**: `authedFetch(`/api/projects/${projectId}/ask`, …)` and `api.projects.*` session methods.
2. **Citation rendering**: render the assistant answer through the existing `renderInline(text, onLink, projectId)` from `BrainWiki.tsx` (exported/lifted into a shared helper) so inline `S:/C:/F:` tokens become live **`IntakeTraceChip`** popovers — richer than App Brain's flat `CitationChip`. Pass `projectId` so the chips resolve.
3. **Research trail**: render the streamed `step` events as a collapsible "thinking" trail above each answer (the ReAct trajectory), and reuse **`AskTraceDrawer`** for the final trace (its `DeepTrace` shape is unchanged).

Scaffold (state mirrors AskPanel's `ChatMessage`):

```tsx
interface Props { projectId: string }
interface ChatMessage {
  role: 'user' | 'assistant'; content: string; streaming?: boolean
  steps?: string[]; citations?: CitationItem[]; trace?: DeepTrace
}
// handleAsk(): POST SSE → on 'step' push to steps[]; 'chunk' append content;
//   'trace' set trace; 'citations' set citations; 'done' streaming=false → persist()
// History dropdown via api.projects.listChatSessions; replay via getChatSession.
// Render: <MarkdownAnswer md={m.content} projectId={projectId}/> using renderInline.
```

No new shadcn primitives needed (Button, ScrollArea, Textarea, DropdownMenu, Collapsible, Tooltip all exist).

### 8. Workspace wiring — `frontend/app/projects/[id]/page.tsx`

- Add `'ask'` to the `View` union.
- Add a left-rail `NavItem` ("Ask", `MessageSquare` icon from lucide-react) between Wiki and Concept Brief.
- In the main-content switch: `view === 'ask' && <ProjectChatPanel projectId={project.id} />`.

### 9. API client — `frontend/lib/api.ts`

Add under `api.projects`:
- `ask` is called via raw `authedFetch` (streaming) inside the panel — no wrapper needed, matching how AskPanel hits `/ask` directly.
- `listChatSessions(projectId)`, `getChatSession(projectId, sid)`, `saveChatSession(projectId, body)`, `deleteChatSession(projectId, sid)` — mirror the `api.apps.*AskSession*` methods.

### 10. Types — `frontend/lib/types.ts`

Reuse `CitationItem`, `DeepTrace`, `AskTurn`, `AskSessionMessage`. Add optional `steps?: string[]` to the chat message type (the ReAct trail) if not already covered by the App Brain `ChatMessage`.

---

## Files to create / modify

**Create**
- `backend/app/services/rag/project_tools.py` — knowledge loader + agent tools + trace accumulator
- `backend/app/services/skills/project_chat/dspy_chat.py` — ReAct signature + builder
- `backend/app/services/rag/project_agent.py` — streaming orchestrator + mock trajectory + trace/citation builders
- `backend/app/api/project_ask.py` — `/projects/{id}/ask` + session endpoints
- `backend/app/models/project_ask_session.py` — session model
- `backend/alembic/versions/0022_project_ask_sessions.py` — migration
- `frontend/app/components/ProjectChatPanel.tsx`

**Modify**
- `backend/app/main.py` — mount `project_ask` router
- `backend/app/models/__init__.py` — register `ProjectAskSession`
- `backend/app/schemas/` (e.g. `project.py`) — `ProjectAskRequest` (reuse `AskTurn`)
- `frontend/app/projects/[id]/page.tsx` — `'ask'` view + NavItem
- `frontend/lib/api.ts` — project chat-session methods
- `frontend/lib/types.ts` — optional `steps` on chat message
- `frontend/app/components/BrainWiki.tsx` — export `renderInline` (or lift to a shared `lib/inlineTokens.tsx`) for reuse by the chat panel
- after backend changes land: run `graphify update .`

**Reused unchanged** (no edits): `corpus_index/base.py` helpers, `tree_retrieval.py`, `rag_service.format_conversation`, `app_context.load_app_facts_for_project`, `IntakeTraceChip.tsx`, `AskTraceDrawer.tsx`, `get_project_source_section` + wiki/fact resolve endpoints, `_configure_dspy`, `@limiter`.

---

## Verification

1. **Mock unit/integration (CI, `LLM_PROVIDER=mock`)** — `backend/tests/test_project_chat.py`:
   - Seed a project with ≥1 indexed `DocumentTree` (+ a wiki concept + an in-scope app fact). Use unique ids (`f"prj{uuid4().hex[:8]}"`).
   - POST `/projects/{id}/ask`, read the SSE stream; assert events arrive in order `step* → chunk* → trace → citations → done`.
   - Assert the answer contains a **real** `S:<doc_id>:<node_id>` token and that `citations[]` ids match loaded sections/concepts/facts (proves tools touched real data).
   - Hit the empty-project case → `error` event.
   - Session round-trip: POST a session, GET list, GET by id, DELETE.
2. **Token resolution** — for a citation token emitted by the mock, call `get_project_source_section` / `getWikiConcept` / `resolveFact` and confirm 200 (the chips will work).
3. **Live smoke (manual, real Vertex)** — run `make dev-be dev-fe worker`, open a real project (`PRJ-0001` via `seed_projects.py`), click the **Ask** tab, ask "What does this project need to deliver?" Watch the research-trail steps stream (list/search/read tool calls), the answer stream with inline chips, and the trace drawer populate. Click an `S:`/`C:`/`F:` chip → popover resolves.
4. `make typecheck lint test-be` green; frontend `tsc`/lint green.
5. Confirm `_react_stream`'s DSPy streaming API matches the installed `dspy` version (StatusMessage/StreamListener); if not, the non-streaming fallback path still satisfies tests 1–3.
