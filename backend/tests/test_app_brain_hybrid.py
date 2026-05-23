"""Hybrid App Brain — PageIndex reasoning tree alongside pgvector chunks."""
import hashlib
import uuid

import pytest

pytestmark = pytest.mark.asyncio


async def test_retrieve_app_sections_from_tree():
    from app.db import AsyncSessionLocal
    from app.models.app import App
    from app.models.corpus import AppCorpusDoc, AppDocTree
    from app.models.storage import StorageFile
    from app.services.rag.tree_retrieval import retrieve_app_sections

    _app_pk = None
    async with AsyncSessionLocal() as db:
        app = App(name="PricingApp", short_name=f"prc{uuid.uuid4().hex[:8]}", tier=1, is_onboarded=True)
        db.add(app)
        await db.flush()
        sf = StorageFile(name="pricing.pdf", content_type="application/pdf", size=10,
                         sha256=hashlib.sha256(b"x").hexdigest())
        db.add(sf)
        await db.flush()
        cdoc = AppCorpusDoc(app_id=app.id, file_id=sf.id, name="pricing.pdf",
                            index_status="done")
        db.add(cdoc)
        await db.flush()
        db.add(AppDocTree(
            corpus_doc_id=cdoc.id, app_id=app.id,
            tree_json={"nodes": [
                {"node_id": "0001", "title": "Pricing", "summary": "price caps",
                 "start_index": 1, "end_index": 1, "nodes": []},
            ]},
            page_texts={"1": "Pricing is capped at 1,000,000 USD per transaction."},
            node_count=1, model="mock",
        ))
        await db.commit()
        _app_pk = app.id

    try:
        async with AsyncSessionLocal() as db:
            sections = await retrieve_app_sections(_app_pk, "what is the price cap?", top_k=5, db=db)
        assert len(sections) >= 1
        s = sections[0]
        assert s.node_id == "0001"
        assert "1,000,000" in s.text
        assert s.doc_name == "pricing.pdf"
    finally:
        async with AsyncSessionLocal() as db:
            a = await db.get(App, _app_pk)
            if a:
                await db.delete(a)  # cascades corpus docs + trees
                await db.commit()


async def test_retrieve_app_sections_empty_when_no_tree():
    from app.db import AsyncSessionLocal
    from app.services.rag.tree_retrieval import retrieve_app_sections

    async with AsyncSessionLocal() as db:
        sections = await retrieve_app_sections(uuid.uuid4(), "anything", top_k=5, db=db)
    assert sections == []


async def test_ingest_corpus_doc_builds_tree_and_chunks():
    """Full app ingestion writes BOTH app_chunks (vector) and an app_doc_trees row."""
    from sqlalchemy import select

    from app.db import AsyncSessionLocal
    from app.models.app import App
    from app.models.corpus import AppChunk, AppCorpusDoc, AppDocTree
    from app.models.storage import StorageFile, StorageFileBlob
    from workers.tasks import _ingest_corpus_doc

    _app_pk = None
    content = b"Pricing section. " + b"the platform caps transactions at one million usd. " * 30
    async with AsyncSessionLocal() as db:
        app = App(name="HybridApp", short_name=f"hyb{uuid.uuid4().hex[:8]}", tier=1, is_onboarded=True)
        db.add(app)
        await db.flush()
        sf = StorageFile(name="doc.txt", content_type="text/plain", size=len(content),
                         sha256=hashlib.sha256(content).hexdigest())
        db.add(sf)
        await db.flush()
        db.add(StorageFileBlob(file_id=sf.id, chunk_no=0, data=content))
        cdoc = AppCorpusDoc(app_id=app.id, file_id=sf.id, name="doc.txt", index_status="pending")
        db.add(cdoc)
        await db.commit()
        doc_id = str(cdoc.id)
        _app_pk = app.id

    try:
        result = await _ingest_corpus_doc(doc_id)
        assert result["ok"] is True

        async with AsyncSessionLocal() as db:
            chunks = (await db.execute(select(AppChunk).where(AppChunk.doc_id == uuid.UUID(doc_id)))).scalars().all()
            tree = (await db.execute(select(AppDocTree).where(AppDocTree.app_id == _app_pk))).scalar_one_or_none()
        assert len(chunks) >= 1, "vector chunks still produced"
        assert tree is not None, "PageIndex tree also produced (hybrid)"
        assert tree.node_count >= 1
    finally:
        async with AsyncSessionLocal() as db:
            a = await db.get(App, _app_pk)
            if a:
                await db.delete(a)  # cascades corpus docs, chunks, trees, facts
                await db.commit()
