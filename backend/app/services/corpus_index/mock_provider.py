"""Deterministic, dependency-free corpus index for dev/CI/seed.

build_index splits the document text into pseudo-pages and produces a small
canonical tree; tree_search returns the first top_k sections. No LLM/network.
"""
from __future__ import annotations

from app.services.corpus_index.base import (
    CorpusIndexProvider,
    DocTree,
    IndexedDoc,
    RetrievedSection,
    count_nodes,
    iter_nodes,
    node_text,
)

_PAGE_CHARS = 1500


def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""


class MockCorpusIndexProvider(CorpusIndexProvider):
    async def build_index(self, *, data: bytes, content_type: str, filename: str) -> DocTree:
        text = _decode(data) or "(no extractable text)"
        pages = [text[i : i + _PAGE_CHARS] for i in range(0, len(text), _PAGE_CHARS)] or [text]
        page_texts = {str(i + 1): p for i, p in enumerate(pages)}

        # One section per page (capped), under a single root node.
        children = [
            {
                "node_id": f"{i + 1:04d}",
                "title": f"Section {i + 1}",
                "summary": p[:160].replace("\n", " ").strip(),
                "start_index": i + 1,
                "end_index": i + 1,
                "nodes": [],
            }
            for i, p in enumerate(pages[:20])
        ]
        tree = {
            "nodes": [
                {
                    "node_id": "0000",
                    "title": filename or "Document",
                    "summary": text[:200].replace("\n", " ").strip(),
                    "start_index": 1,
                    "end_index": len(pages),
                    "nodes": children,
                }
            ]
        }
        return DocTree(tree=tree, page_texts=page_texts, node_count=count_nodes(tree), model="mock")

    async def tree_search(
        self, *, query: str, docs: list[IndexedDoc], top_k: int
    ) -> list[RetrievedSection]:
        out: list[RetrievedSection] = []
        for doc in docs:
            for node in iter_nodes(doc.tree):
                if node.get("node_id") == "0000":
                    continue  # skip the synthetic root
                out.append(
                    RetrievedSection(
                        document_id=doc.document_id,
                        doc_name=doc.doc_name,
                        node_id=str(node.get("node_id")),
                        title=node.get("title", ""),
                        page_start=int(node.get("start_index", 1)),
                        page_end=int(node.get("end_index", 1)),
                        text=node_text(node, doc.page_texts),
                        reason="mock: first sections",
                    )
                )
                if len(out) >= top_k:
                    return out
        return out
