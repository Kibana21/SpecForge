"""Document upload and extraction API tests. Requires PostgreSQL with schema applied."""
from pathlib import Path

import pytest

pytestmark = pytest.mark.asyncio

FIXTURES = Path(__file__).parent / "fixtures"


async def _create_project(client, name: str = "DocTest") -> str:
    r = await client.post("/api/projects", json={"name": name})
    assert r.status_code == 201
    return r.json()["data"]["id"]


async def test_upload_txt(client):
    project_id = await _create_project(client, "TxtUpload")
    content = (FIXTURES / "sample.txt").read_bytes()
    r = await client.post(
        f"/api/projects/{project_id}/documents",
        files={"file": ("sample.txt", content, "text/plain")},
    )
    assert r.status_code == 201
    data = r.json()["data"]
    assert data["filename"] == "sample.txt"
    assert data["parse_status"] == "done"
    assert data["project_id"] == project_id


async def test_upload_pdf(client):
    project_id = await _create_project(client, "PdfUpload")
    content = (FIXTURES / "sample.pdf").read_bytes()
    r = await client.post(
        f"/api/projects/{project_id}/documents",
        files={"file": ("sample.pdf", content, "application/pdf")},
    )
    assert r.status_code == 201
    assert r.json()["data"]["parse_status"] == "done"


async def test_upload_docx(client):
    project_id = await _create_project(client, "DocxUpload")
    content = (FIXTURES / "sample.docx").read_bytes()
    r = await client.post(
        f"/api/projects/{project_id}/documents",
        files={"file": ("sample.docx", content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert r.status_code == 201
    assert r.json()["data"]["parse_status"] == "done"


async def test_upload_unsupported_type_rejected(client):
    project_id = await _create_project(client, "UnsupportedUpload")
    # Binary content that's not a PDF/DOCX and can't be decoded as UTF-8 → application/octet-stream
    binary_junk = bytes([0x00, 0x01, 0x02, 0xFE, 0xFF, 0xAA, 0xBB] * 100)
    r = await client.post(
        f"/api/projects/{project_id}/documents",
        files={"file": ("data.bin", binary_junk, "application/octet-stream")},
    )
    assert r.status_code == 422


async def test_list_documents(client):
    project_id = await _create_project(client, "ListDocs")
    content = (FIXTURES / "sample.txt").read_bytes()
    await client.post(
        f"/api/projects/{project_id}/documents",
        files={"file": ("a.txt", content, "text/plain")},
    )
    r = await client.get(f"/api/projects/{project_id}/documents")
    assert r.status_code == 200
    assert len(r.json()["data"]) == 1


async def test_delete_document(client):
    project_id = await _create_project(client, "DeleteDoc")
    content = (FIXTURES / "sample.txt").read_bytes()
    r = await client.post(
        f"/api/projects/{project_id}/documents",
        files={"file": ("del.txt", content, "text/plain")},
    )
    doc_id = r.json()["data"]["id"]

    r = await client.delete(f"/api/projects/{project_id}/documents/{doc_id}")
    assert r.status_code == 200

    r = await client.get(f"/api/projects/{project_id}/documents")
    assert r.json()["data"] == []


async def test_extract_requirements(client):
    project_id = await _create_project(client, "ExtractReqs")
    content = (FIXTURES / "sample.txt").read_bytes()
    await client.post(
        f"/api/projects/{project_id}/documents",
        files={"file": ("sample.txt", content, "text/plain")},
    )

    r = await client.post(f"/api/projects/{project_id}/extract")
    assert r.status_code == 200
    reqs = r.json()["data"]
    assert isinstance(reqs, list)
    assert len(reqs) >= 1


async def test_detect_gaps(client):
    project_id = await _create_project(client, "DetectGaps")
    content = (FIXTURES / "sample.txt").read_bytes()
    await client.post(
        f"/api/projects/{project_id}/documents",
        files={"file": ("sample.txt", content, "text/plain")},
    )
    await client.post(f"/api/projects/{project_id}/extract")

    r = await client.post(f"/api/projects/{project_id}/detect-gaps")
    assert r.status_code == 200
    gaps = r.json()["data"]
    assert isinstance(gaps, list)


async def test_extract_without_documents_returns_422(client):
    project_id = await _create_project(client, "NoDocsExtract")
    r = await client.post(f"/api/projects/{project_id}/extract")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "no_documents"
