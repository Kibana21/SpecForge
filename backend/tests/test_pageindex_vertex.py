"""Opt-in live spike: PageIndex builds a real tree via Vertex Gemini.

Skipped by default (makes real, billable Vertex calls). Run explicitly with:
    RUN_PAGEINDEX_LIVE=1 LLM_PROVIDER=gemini python -m pytest tests/test_pageindex_vertex.py -s

Validated 2026-05-22: build_index → 3-node tree; tree_search → reasoning-selected
the relevant section. Documents the corpus engine works end-to-end against Vertex.
"""
import asyncio
import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_PAGEINDEX_LIVE") != "1",
    reason="live PageIndex+Vertex spike; set RUN_PAGEINDEX_LIVE=1 to run (billable).",
)


def _sample_pdf() -> bytes:
    import fitz

    doc = fitz.open()
    sections = [
        ("1. Overview", "PayHub processes card and bank transfers with ISO 20022 and real-time settlement."),
        ("2. Integrations", "PayHub integrates with SWIFT MT103 and exposes a REST API with webhooks."),
        ("3. Constraints", "Transactions are capped at 10 million USD per instruction; idempotency keys expire after 24h."),
    ]
    for title, body in sections:
        p = doc.new_page()
        p.insert_text((72, 90), title, fontsize=18)
        p.insert_text((72, 130), body, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


def test_pageindex_vertex_build_and_search():
    from app.services.corpus_index.base import IndexedDoc
    from app.services.corpus_index.pageindex_provider import PageIndexProvider

    prov = PageIndexProvider()
    data = _sample_pdf()

    async def run():
        tree = await prov.build_index(data=data, content_type="application/pdf", filename="payhub.pdf")
        assert tree.node_count >= 1
        assert tree.tree["nodes"]
        assert tree.page_texts

        doc = IndexedDoc(
            document_id=uuid.uuid4(), doc_name="payhub.pdf",
            tree=tree.tree, page_texts=tree.page_texts,
        )
        secs = await prov.tree_search(
            query="What are PayHub's transaction limits and constraints?", docs=[doc], top_k=3
        )
        assert secs, "expected at least one reasoning-selected section"
        assert any("constraint" in s.title.lower() or "10 million" in s.text for s in secs)

    asyncio.run(run())
