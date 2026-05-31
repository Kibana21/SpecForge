"""Agent tools over a project's PageIndex trees, wiki concepts, and app facts.
Pre-loaded in memory so the (sync, threaded) dspy.ReAct loop never touches async DB.
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

_SECTION_CHARS = 1400   # per-observation budget — keeps agent token use bounded
_STOP = {"the", "and", "for", "with", "that", "this", "what", "how", "are",
         "was", "does", "from", "into", "about", "will", "can", "has", "have"}


@dataclass
class ProjectKnowledge:
    docs: list[IndexedDoc]
    page_texts: dict[str, dict]   # doc_id(str) -> page_texts
    doc_names: dict[str, str]     # doc_id(str) -> filename
    concepts: list[ProjectWikiConcept]
    facts: list[dict]             # {id, app, kind, text, confidence, source_ref}

    def has_any(self) -> bool:
        return bool(self.docs or self.concepts)


@dataclass
class TraceAccumulator:
    sections: dict[tuple[str, str], dict] = field(default_factory=dict)  # (doc_id,node_id)->section
    concepts: dict[str, dict] = field(default_factory=dict)              # slug->concept
    facts: dict[str, dict] = field(default_factory=dict)                 # id->fact
    visited: dict[str, set[str]] = field(default_factory=dict)           # doc_id->{node_ids}
    steps: list[str] = field(default_factory=list)

    def note_visit(self, doc_id: str, node_id: str) -> None:
        self.visited.setdefault(doc_id, set()).add(node_id)


async def load_project_knowledge(project_id: uuid.UUID, db: AsyncSession) -> ProjectKnowledge:
    tree_rows = (await db.execute(
        select(DocumentTree, Document.filename)
        .join(Document, Document.id == DocumentTree.document_id)
        .where(DocumentTree.project_id == project_id)
    )).all()
    docs: list[IndexedDoc] = []
    page_texts: dict[str, dict] = {}
    doc_names: dict[str, str] = {}
    for t, name in tree_rows:
        did = str(t.document_id)
        docs.append(IndexedDoc(document_id=t.document_id, doc_name=name,
                               tree=t.tree_json, page_texts=t.page_texts))
        page_texts[did] = t.page_texts
        doc_names[did] = name
    concepts = (await db.execute(
        select(ProjectWikiConcept)
        .where(ProjectWikiConcept.project_id == project_id)
        .order_by(ProjectWikiConcept.title)
    )).scalars().all()
    facts = await load_app_facts_for_project(project_id, db)
    return ProjectKnowledge(docs, page_texts, doc_names, list(concepts), facts)


def _terms(q: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", q.lower()) if len(w) > 2 and w not in _STOP}


def _score(text: str, title: str, terms: set[str], phrase: str) -> float:
    """Title-weighted token overlap, length-normalised, with an exact-phrase bonus.
    Deterministic + dependency-free — semantic quality comes from the pre-flight seed
    which calls the proven tree_search/concept-select retrieval."""
    body = f"{title} {text}".lower()
    if not body.strip():
        return 0.0
    overlap = sum(body.count(t) for t in terms)
    title_hits = sum(title.lower().count(t) for t in terms) * 2
    phrase_bonus = 3.0 if phrase and phrase in body else 0.0
    return (overlap + title_hits + phrase_bonus) / (1 + len(body) / 4000)


def build_tools(k: ProjectKnowledge, trace: TraceAccumulator) -> list:
    """Return DSPy-compatible callables. dspy.ReAct reads name/__doc__/type-hints."""

    def list_documents() -> str:
        """List every project document with its section outline ('[Di] node_id · title — summary').
        Call this first to see what exists; then use read_section to open a node's full text."""
        trace.steps.append(f"Listed {len(k.docs)} document(s)")
        return flatten_outline(k.docs) or "(no indexed documents)"

    def search_sections(query: str) -> str:
        """Find the most relevant document sections across ALL project documents for a query.
        Returns 'S:<doc_id>:<node_id> · title — summary' lines; open the best with read_section.
        Cite a section in the answer as S:<doc_id>:<node_id>."""
        terms, phrase = _terms(query), query.lower().strip()
        scored: list[tuple[float, str, dict]] = []
        for d in k.docs:
            for n in iter_nodes(d.tree):
                if n.get("node_id") == "0000":
                    continue
                s = _score(n.get("summary", ""), n.get("title", ""), terms, phrase)
                if s > 0:
                    scored.append((s, str(d.document_id), n))
        scored.sort(key=lambda x: -x[0])
        if not scored:
            return "(no matching sections — call list_documents to browse the outline)"
        trace.steps.append(f'Searched sections for "{query}" → {len(scored)} hits')
        return "\n".join(
            f"S:{did}:{n.get('node_id')} · {n.get('title', '')} — {(n.get('summary') or '')[:120]}"
            for _, did, n in scored[:8]
        )

    def read_section(doc_id: str, node_id: str) -> str:
        """Read one section's full source text. doc_id and node_id come from list_documents
        or search_sections. Cite it in the answer as S:<doc_id>:<node_id>."""
        for d in k.docs:
            if str(d.document_id) == doc_id:
                node = find_node(d.tree, node_id)
                if not node:
                    return "(section not found — verify node_id from list_documents or search_sections)"
                text = node_text(node, d.page_texts)
                trace.sections[(doc_id, node_id)] = {
                    "doc_id": doc_id,
                    "doc_name": k.doc_names.get(doc_id, ""),
                    "node_id": node_id,
                    "title": (node.get("title") or "").strip(),
                    "pages": (f"{node.get('start_index')}-{node.get('end_index')}"
                              if node.get("start_index") is not None else ""),
                    "text": text,
                }
                trace.note_visit(doc_id, node_id)
                title = node.get("title", "§" + node_id)
                trace.steps.append(f"Read {k.doc_names.get(doc_id, '?')} › {title}")
                if len(text) > _SECTION_CHARS:
                    return text[:_SECTION_CHARS] + " ..."
                return text or "(empty section)"
        return "(document not found — verify doc_id from list_documents)"

    def search_wiki(query: str) -> str:
        """Search the Project Wiki concepts (cross-document synthesised knowledge).
        Returns 'C:<slug> · Title — brief' lines. Open one with read_concept.
        Cite a concept in the answer as C:<slug>."""
        terms, phrase = _terms(query), query.lower().strip()
        scored = sorted(
            ((_score(c.brief, c.title, terms, phrase), c) for c in k.concepts),
            key=lambda x: -x[0],
        )
        hits = [c for s, c in scored if s > 0] or list(k.concepts[:3])
        if not hits:
            return "(no wiki concepts compiled yet — try search_sections instead)"
        trace.steps.append(f'Searched wiki for "{query}"')
        return "\n".join(f"C:{c.slug} · {c.title} — {c.brief}" for c in hits[:6])

    def read_concept(slug: str) -> str:
        """Read a Project Wiki concept's full content and the source sections it is grounded in.
        Cite the concept in the answer as C:<slug>; you may also cite its S: sections."""
        for c in k.concepts:
            if c.slug == slug:
                trace.concepts[slug] = {
                    "slug": slug,
                    "title": c.title,
                    "brief": c.brief,
                    "tree_node_refs": c.tree_node_refs or [],
                }
                for r in (c.tree_node_refs or []):
                    if r.get("doc_id") and r.get("node_id"):
                        trace.note_visit(str(r["doc_id"]), str(r["node_id"]))
                trace.steps.append(f'Read concept "{c.title}"')
                refs = "; ".join(
                    f"S:{r.get('doc_id')}:{r.get('node_id')} ({r.get('title', '')})"
                    for r in (c.tree_node_refs or [])[:6]
                )
                return f"# {c.title}\n{c.content_md}\n\nGrounded in: {refs or '(none)'}"
        return "(concept not found — verify slug from search_wiki)"

    def lookup_facts(query: str) -> str:
        """Look up App Brain facts about the systems and integrations in scope.
        Returns 'F:<id> [app/kind] text' lines. Cite a fact in the answer as F:<id>."""
        terms, phrase = _terms(query), query.lower().strip()
        scored = sorted(
            ((_score(f["text"], f.get("app", ""), terms, phrase), f) for f in k.facts),
            key=lambda x: -x[0],
        )
        hits = [f for s, f in scored if s > 0][:8] or k.facts[:5]
        for f in hits:
            trace.facts[f["id"]] = f
        if not hits:
            return "(no app facts in scope for this project)"
        trace.steps.append(f'Looked up facts for "{query}"')
        return "\n".join(
            f"F:{f['id']} [{f['app']}/{f['kind']}] {f['text'][:160]}" for f in hits
        )

    tools = [list_documents, search_sections, read_section, search_wiki, read_concept]
    if k.facts:
        tools.append(lookup_facts)
    return tools
