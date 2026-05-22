"""Corpus-index provider abstraction.

A reasoning-based (vectorless) document index: each document becomes a tree of
sections (PageIndex). Retrieval = an LLM navigates the tree to pick relevant
sections, then we fetch those sections' text. Isolated behind this interface so
the engine is swappable and mockable (mirrors EmbeddingProvider / LLMProvider).
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field


@dataclass
class DocTree:
    """Result of build_index. Canonical tree shape: {"nodes": [<node>, ...]}.

    Each node: {node_id, title, summary, start_index, end_index, nodes: [...]}.
    page_texts maps page-number (str) -> page text, for fetching node text.
    """
    tree: dict
    page_texts: dict
    node_count: int
    model: str


@dataclass
class IndexedDoc:
    """An already-indexed document, input to tree_search."""
    document_id: uuid.UUID
    doc_name: str
    tree: dict
    page_texts: dict


@dataclass
class RetrievedSection:
    document_id: uuid.UUID
    doc_name: str
    node_id: str
    title: str
    page_start: int
    page_end: int
    text: str
    reason: str = ""


class CorpusIndexProvider(ABC):
    @abstractmethod
    async def build_index(self, *, data: bytes, content_type: str, filename: str) -> DocTree:
        """Build a reasoning tree for one document."""

    @abstractmethod
    async def tree_search(
        self, *, query: str, docs: list[IndexedDoc], top_k: int
    ) -> list[RetrievedSection]:
        """Reason over the in-scope trees and return the most relevant sections."""


# ── Tree helpers (shared by providers + retrieval) ──────────────────────────────

def iter_nodes(tree: dict) -> Iterator[dict]:
    """Depth-first iterate every node in a canonical tree ({"nodes": [...]})."""
    stack = list(tree.get("nodes", []) or [])
    while stack:
        node = stack.pop()
        yield node
        children = node.get("nodes") or []
        stack.extend(children)


def count_nodes(tree: dict) -> int:
    return sum(1 for _ in iter_nodes(tree))


def find_node(tree: dict, node_id: str) -> dict | None:
    for node in iter_nodes(tree):
        if str(node.get("node_id")) == str(node_id):
            return node
    return None


def node_text(node: dict, page_texts: dict) -> str:
    """Concatenate page text for a node's page range (inclusive). Falls back to a
    node-level 'text' field if present and no page range resolves."""
    start = node.get("start_index")
    end = node.get("end_index")
    if start is not None and end is not None:
        parts = [page_texts.get(str(p), "") for p in range(int(start), int(end) + 1)]
        joined = "\n".join(p for p in parts if p).strip()
        if joined:
            return joined
    return (node.get("text") or "").strip()


def flatten_outline(docs: list[IndexedDoc]) -> str:
    """A compact, LLM-readable outline of all in-scope trees for tree-search.

    Lines: `[D{i}] {node_id} · {title} — {summary}` so the model can select node_ids.
    """
    lines: list[str] = []
    for i, doc in enumerate(docs):
        lines.append(f"=== [D{i}] {doc.doc_name} (document_id={doc.document_id}) ===")
        for node in iter_nodes(doc.tree):
            nid = node.get("node_id", "?")
            title = (node.get("title") or "").strip()
            summary = (node.get("summary") or "").strip()
            lines.append(f"[D{i}] {nid} · {title} — {summary}")
    return "\n".join(lines)
