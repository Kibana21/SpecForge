"""Project Copilot mock integration tests.

Runs against real Postgres with mock LLM / corpus index (LLM_PROVIDER=mock).
Every test seeds its own project with unique ids so no cross-test collisions.

Covers:
  - SSE event ordering and content (step+ → trace(partial) → chunk+ → trace(final) → citations → done)
  - Real S:/C:/F: citation tokens appear in answer and trace
  - tree_map lists visited doc(s) with valid node_ids
  - _verify_and_prune gate: fabricated token never appears in citations
  - Empty project → error event, no crash
  - Session CRUD round-trip (create, list, get, delete)
"""
from __future__ import annotations

import json
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.models.app import App
from app.models.document import Document
from app.models.fact import AppFact
from app.models.project import Project
from app.models.project_ask_session import ProjectAskSession
from app.models.project_intake import ProjectApp
from app.models.project_source import DocumentTree
from app.models.project_wiki import ProjectWikiConcept


def _s() -> str:
    return uuid.uuid4().hex[:8]


async def _seed_project_with_knowledge(db, owner_id) -> tuple[Project, Document, str, str]:
    """Create a project with one indexed DocumentTree + one wiki concept + one app fact.
    Returns (project, document, node_id_of_first_section, concept_slug).
    """
    project = Project(name=f"ChatTest-{_s()}", description="test", owner_id=owner_id)
    db.add(project)
    await db.flush()

    # Document + DocumentTree (mock provider builds a real tree)
    doc = Document(
        project_id=project.id, filename=f"spec-{_s()}.md",
        mime_type="text/markdown", size_bytes=1024,
        storage_path=f"/tmp/{_s()}.md",
        extracted_text="# Refund Policy\n\nRefunds must clear within 24 hours of request.",
        parse_status="done", indexing_status="done",
    )
    db.add(doc)
    await db.flush()

    # Build a mock tree for this doc
    from app.services.corpus_index import get_corpus_index_provider
    doc_tree = await get_corpus_index_provider().build_index(
        data=doc.extracted_text.encode(),
        content_type="text/markdown",
        filename=doc.filename,
    )
    first_section_node_id = None
    from app.services.corpus_index.base import iter_nodes
    for n in iter_nodes(doc_tree.tree):
        if n.get("node_id") != "0000":
            first_section_node_id = str(n["node_id"])
            break
    assert first_section_node_id, "mock tree must produce at least one non-root node"

    db.add(DocumentTree(
        document_id=doc.id, project_id=project.id,
        tree_json=doc_tree.tree, page_texts=doc_tree.page_texts,
        node_count=doc_tree.node_count, model=doc_tree.model,
    ))

    # Wiki concept with tree_node_refs pointing to the real doc/node
    slug = f"refund-policy-{_s()}"
    db.add(ProjectWikiConcept(
        project_id=project.id, slug=slug,
        title="Refund Policy", brief="How refunds are processed",
        content_md="Refunds are processed within 24h.",
        source_doc_ids=[str(doc.id)],
        related_slugs=[],
        tree_node_refs=[{"doc_id": str(doc.id), "node_id": first_section_node_id,
                         "title": "Section 1", "pages": "1-1"}],
    ))

    # App in scope with a fact
    sfx = _s()
    app_obj = App(name=f"PayHub-{sfx}", short_name=f"ph{sfx[:6]}", tier=1, description="payment app")
    db.add(app_obj)
    await db.flush()
    db.add(ProjectApp(project_id=project.id, app_id=app_obj.id, included=True))
    db.add(AppFact(app_id=app_obj.id, kind="integration", text="Stripe webhook triggers refund.",
                   status="active", confidence="high"))

    await db.commit()
    await db.refresh(project)
    return project, doc, first_section_node_id, slug


def _parse_sse(body: str) -> list[dict]:
    events = []
    for line in body.splitlines():
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events


# ── Core SSE test ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ask_project_sse_ordering_and_citations(client):
    from app.models.user import User
    async with AsyncSessionLocal() as db:
        user_row = (await db.execute(
            select(User.id).where(User.role == "platform_admin").limit(1)
        )).first()
        owner_id = user_row[0] if user_row else None
        project, doc, first_node_id, slug = await _seed_project_with_knowledge(db, owner_id)

    resp = await client.post(
        f"/api/projects/{project.id}/ask",
        json={"question": "How are refunds handled?"},
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    events = _parse_sse(resp.text)
    types = [e["type"] for e in events]

    # Must end with done
    assert types[-1] == "done", f"last event was {types[-1]}"

    # trace must appear before done
    trace_idxs = [i for i, t in enumerate(types) if t == "trace"]
    done_idx = types.index("done")
    assert trace_idxs, "must emit at least one trace event"
    assert trace_idxs[-1] < done_idx

    # chunk events must appear
    assert "chunk" in types, "must emit chunk events"

    # citations event must appear before done
    assert "citations" in types
    assert types.index("citations") < done_idx

    # step event(s) must appear
    assert "step" in types

    # The final non-partial trace
    final_traces = [e for e in events if e["type"] == "trace" and not e.get("trace", {}).get("partial")]
    assert final_traces, "must emit a final (non-partial) trace"
    final_trace = final_traces[-1]["trace"]

    # tree_map must list our document with at least one visited node
    tree_map = final_trace.get("tree_map", [])
    doc_ids_visited = {tm["doc_id"] for tm in tree_map}
    assert str(doc.id) in doc_ids_visited, "document must appear in tree_map"
    for tm in tree_map:
        if tm["doc_id"] == str(doc.id):
            assert tm["visited"], "visited list must not be empty"
            # All visited node_ids must be in the outline
            outline_ids = {n["node_id"] for n in tm["outline"]}
            for nid in tm["visited"]:
                assert nid in outline_ids, f"visited node {nid} not in outline"

    # The answer must contain at least one real S: token
    chunks = [e for e in events if e["type"] == "chunk"]
    answer = "".join(c["text"] for c in chunks)
    assert "S:" in answer, f"answer must contain S: citation token; got: {answer[:200]}"

    # citations array must have entries with real ids
    cit_event = next(e for e in events if e["type"] == "citations")
    citations = cit_event["citations"]
    assert citations, "citations must not be empty"
    citation_tokens = {c.get("token") for c in citations}
    # At least one S: token resolves
    assert any(t and t.startswith("S:") for t in citation_tokens)


@pytest.mark.asyncio
async def test_verify_and_prune_drops_fabricated_tokens(client):
    """_verify_and_prune must drop a citation whose node_id doesn't exist."""
    from app.services.rag.project_tools import ProjectKnowledge, TraceAccumulator
    from app.services.rag.project_agent import _verify_and_prune
    from app.services.corpus_index.base import IndexedDoc
    import uuid as _uuid

    fake_doc_id = str(_uuid.uuid4())
    fake_node_id = "ffff"
    k = ProjectKnowledge(docs=[], page_texts={}, doc_names={}, concepts=[], facts=[])
    trace = TraceAccumulator()
    trace.sections[(fake_doc_id, fake_node_id)] = {
        "doc_id": fake_doc_id, "doc_name": "ghost.pdf", "node_id": fake_node_id,
        "title": "Ghost", "pages": "", "text": "fabricated",
    }
    trace.concepts["fake-slug"] = {"slug": "fake-slug", "title": "Ghost", "brief": ""}
    trace.facts["fake-fact-id"] = {"id": "fake-fact-id", "app": "Ghost", "kind": "misc", "text": "x"}

    _verify_and_prune(k, trace)

    assert len(trace.sections) == 0, "fabricated section must be pruned"
    assert len(trace.concepts) == 0, "fabricated concept must be pruned"
    assert len(trace.facts) == 0, "fabricated fact must be pruned"


@pytest.mark.asyncio
async def test_ask_empty_project_returns_error(client):
    async with AsyncSessionLocal() as db:
        project = Project(name=f"EmptyChat-{_s()}", description="empty")
        db.add(project)
        await db.commit()
        await db.refresh(project)
        project_id = project.id

    resp = await client.post(
        f"/api/projects/{project_id}/ask",
        json={"question": "What is this?"},
    )
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    types = [e["type"] for e in events]
    assert "error" in types, f"expected error event for empty project, got: {types}"


# ── Session CRUD ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_session_crud(client):
    async with AsyncSessionLocal() as db:
        project = Project(name=f"SessionTest-{_s()}", description="x")
        db.add(project)
        await db.commit()
        await db.refresh(project)
        pid = project.id

    # Create
    create_resp = await client.post(f"/api/projects/{pid}/ask/sessions", json={
        "id": None,
        "title": "Test chat",
        "messages": [
            {"role": "user", "content": "hello", "citations": [], "mode": None, "trace": None},
            {"role": "assistant", "content": "world", "citations": [], "mode": None, "trace": None},
        ],
    })
    assert create_resp.status_code == 200
    session_id = create_resp.json()["data"]["id"]
    assert session_id

    # List
    list_resp = await client.get(f"/api/projects/{pid}/ask/sessions")
    assert list_resp.status_code == 200
    sessions = list_resp.json()["data"]
    assert any(s["id"] == session_id for s in sessions)

    # Get
    get_resp = await client.get(f"/api/projects/{pid}/ask/sessions/{session_id}")
    assert get_resp.status_code == 200
    sess = get_resp.json()["data"]
    assert sess["title"] == "Test chat"
    assert len(sess["messages"]) == 2

    # Update (upsert)
    update_resp = await client.post(f"/api/projects/{pid}/ask/sessions", json={
        "id": session_id,
        "title": "Updated chat",
        "messages": [
            {"role": "user", "content": "hello", "citations": [], "mode": None, "trace": None},
            {"role": "assistant", "content": "world v2", "citations": [], "mode": None, "trace": None},
            {"role": "user", "content": "follow up", "citations": [], "mode": None, "trace": None},
        ],
    })
    assert update_resp.status_code == 200

    # Delete
    del_resp = await client.delete(f"/api/projects/{pid}/ask/sessions/{session_id}")
    assert del_resp.status_code == 200

    # Confirm gone
    list_after = await client.get(f"/api/projects/{pid}/ask/sessions")
    after_ids = [s["id"] for s in list_after.json()["data"]]
    assert session_id not in after_ids
