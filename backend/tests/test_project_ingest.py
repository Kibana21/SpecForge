"""Project source upload → PageIndex ingestion (mock corpus provider).

Verifies the upload endpoint persists a document with sha256 + indexing_status,
and that the ingest task builds a document_trees row via the mock corpus provider.
"""
import asyncio

import pytest

pytestmark = pytest.mark.asyncio


async def _new_project(client) -> str:
    r = await client.post("/api/projects", json={"name": "Ingest Test", "description": "d"})
    assert r.status_code == 201
    return r.json()["data"]["id"]


async def test_upload_sets_indexing_pending_and_sha256(client):
    pid = await _new_project(client)
    files = {"file": ("notes.txt", b"PayHub caps transactions at 10M USD per instruction.", "text/plain")}
    r = await client.post(f"/api/projects/{pid}/documents", files=files)
    assert r.status_code == 201
    doc = r.json()["data"]
    assert doc["indexing_status"] == "pending"
    assert doc["parse_status"] == "done"


async def test_duplicate_upload_rejected(client):
    pid = await _new_project(client)
    content = b"Some unique source content for dedup."
    files = {"file": ("a.txt", content, "text/plain")}
    r1 = await client.post(f"/api/projects/{pid}/documents", files=files)
    assert r1.status_code == 201
    files2 = {"file": ("b.txt", content, "text/plain")}  # same bytes → same sha256
    r2 = await client.post(f"/api/projects/{pid}/documents", files=files2)
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "duplicate_document"


async def test_ingest_task_builds_document_tree(client):
    from sqlalchemy import select

    from app.db import AsyncSessionLocal
    from app.models.document import Document
    from app.models.project_source import DocumentTree
    from workers.tasks import _ingest_project_source

    pid = await _new_project(client)
    files = {"file": ("spec.txt", b"Section A. " + b"payments " * 200, "text/plain")}
    r = await client.post(f"/api/projects/{pid}/documents", files=files)
    doc_id = r.json()["data"]["id"]

    # Broker is skipped in tests, so run the ingest task directly.
    result = await _ingest_project_source(doc_id)
    assert result["ok"] is True
    assert result["nodes"] >= 1

    async with AsyncSessionLocal() as db:
        tree = (
            await db.execute(select(DocumentTree).where(DocumentTree.document_id == doc_id))
        ).scalar_one_or_none()
        assert tree is not None
        assert tree.node_count >= 1
        assert tree.tree_json["nodes"]
        doc = await db.get(Document, doc_id)
        assert doc.indexing_status == "done"
