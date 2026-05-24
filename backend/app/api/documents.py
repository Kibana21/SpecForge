import hashlib
import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_project_or_404, get_provider_dep
from app.config import get_settings
from app.core import audit
from app.db import get_db
from app.limiter import limiter
from app.models.document import Document
from app.models.gap import GapQuestion
from app.models.project import Project
from app.models.requirement import ExtractedRequirement
from app.models.user import User
from app.schemas.document import DocumentRead
from app.schemas.envelope import err, ok
from app.schemas.gap import GapQuestionRead
from app.schemas.requirement import ExtractedRequirementRead
from app.services.documents import parser, storage
from app.services.documents.malware_scanner import get_malware_scanner
from app.services.llm.base import LLMProvider

log = logging.getLogger(__name__)
router = APIRouter(tags=["documents"], dependencies=[Depends(get_current_user)])

_REQUIREMENT_CATEGORY_MAP = {
    "functional_requirements": "functional",
    "non_functional_requirements": "non_functional",
    "constraints": "constraint",
    "assumptions": "assumption",
    "stakeholders": "stakeholder",
}


@router.post("/projects/{project_id}/documents", status_code=201)
@limiter.limit("10/minute")
async def upload_document(
    request: Request,
    project_id: UUID,
    file: UploadFile = File(...),
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    settings = get_settings()
    content = await file.read()

    max_bytes = settings.corpus_max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        err("file_too_large", f"File exceeds {settings.corpus_max_upload_mb} MB limit", 413)

    # Malware scan before persisting (no-op stub today; blocks on a non-clean result).
    scan = await get_malware_scanner().scan(content, file.filename or "upload")
    if not scan.clean:
        await audit.emit(db, event="malware_detected", actor_id=str(user.id),
                         metadata={"project_id": str(project_id), "detail": scan.detail})
        await db.commit()
        err("malware_detected", "File failed the malware scan.", 422)

    mime = storage.detect_mime(content)
    if mime not in storage.ALLOWED_MIME_TYPES:
        err("unsupported_file_type", "Unsupported file type. Allowed: PDF, DOCX, XLSX, PPTX, MD, TXT", 422)

    # SHA-256 dedup within the project.
    sha = hashlib.sha256(content).hexdigest()
    dup = (
        await db.execute(
            select(Document.id).where(Document.project_id == project_id, Document.sha256 == sha)
        )
    ).first()
    if dup is not None:
        err("duplicate_document", "This file is already in the project.", 409)

    safe_name = storage.sanitize_filename(file.filename or "upload")
    storage_path = await storage.save(str(project_id), safe_name, mime, content, settings.upload_dir)

    doc = Document(
        project_id=project_id,
        filename=safe_name,
        mime_type=mime,
        size_bytes=len(content),
        storage_path=storage_path,
        sha256=sha,
        parse_status="pending",
        indexing_status="pending",
    )
    db.add(doc)
    await db.flush()

    # Synchronous text extraction (used by requirement_extractor); PageIndex tree
    # build is dispatched async below.
    try:
        text = parser.parse(content, mime)
        doc.extracted_text = text
        doc.parse_status = "done"
    except Exception as exc:
        log.warning("doc_parse_failed doc_id=%s error=%s", doc.id, exc)
        doc.parse_error = str(exc)[:500]
        doc.parse_status = "error"

    await audit.emit(db, event="source.uploaded", actor_id=str(user.id),
                     metadata={"project_id": str(project_id), "doc_id": str(doc.id), "name": safe_name})
    await db.commit()
    await db.refresh(doc)

    # Dispatch PageIndex ingestion (builds the reasoning tree → document_trees).
    # Best-effort: a broker outage must not fail the (already durable) upload.
    from workers.dispatch import dispatch
    from workers.tasks import ingest_project_source
    dispatch(ingest_project_source, str(doc.id))

    return ok(DocumentRead.model_validate(doc).model_dump(mode="json"))


@router.get("/projects/{project_id}/documents")
async def list_documents(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(Document)
            .where(Document.project_id == project_id)
            .order_by(Document.created_at.asc())
        )
    ).scalars().all()
    return ok([DocumentRead.model_validate(d).model_dump(mode="json") for d in rows])


@router.delete("/projects/{project_id}/documents/{doc_id}")
async def delete_document(
    project_id: UUID,
    doc_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
):
    doc = (
        await db.execute(
            select(Document).where(Document.id == doc_id, Document.project_id == project_id)
        )
    ).scalar_one_or_none()
    if doc is None:
        err("not_found", f"Document {doc_id} not found", 404)

    await storage.delete(doc.storage_path)
    await db.delete(doc)
    await db.commit()
    return ok({"id": str(doc_id)})


@router.post("/projects/{project_id}/extract")
@limiter.limit("30/minute")
async def extract_requirements(
    request: Request,
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    provider: LLMProvider = Depends(get_provider_dep),
):
    docs = (
        await db.execute(
            select(Document).where(
                Document.project_id == project_id,
                Document.parse_status == "done",
                Document.extracted_text.isnot(None),
            )
        )
    ).scalars().all()

    if not docs:
        err("no_documents", "No parsed documents found. Upload documents first.", 422)

    document_text = "\n\n---\n\n".join(
        f"[Document: {d.filename}]\n{d.extracted_text}" for d in docs
    )

    from app.services.skills.dspy_intake import run_requirement_extractor
    result = await run_requirement_extractor(project.name, document_text)

    await db.execute(
        delete(ExtractedRequirement).where(ExtractedRequirement.project_id == project_id)
    )

    new_reqs: list[ExtractedRequirement] = []
    for key, category in _REQUIREMENT_CATEGORY_MAP.items():
        for item in result.get(key, []):
            req = ExtractedRequirement(
                project_id=project_id,
                category=category,
                ext_id=item.get("id", ""),
                text=item.get("text", ""),
                source_reference=item.get("source_reference"),
                confidence=item.get("confidence", "medium"),
            )
            db.add(req)
            new_reqs.append(req)

    await db.commit()
    for req in new_reqs:
        await db.refresh(req)

    return ok([ExtractedRequirementRead.model_validate(r).model_dump(mode="json") for r in new_reqs])


@router.get("/projects/{project_id}/requirements")
async def list_requirements(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(ExtractedRequirement)
            .where(ExtractedRequirement.project_id == project_id)
            .order_by(ExtractedRequirement.category, ExtractedRequirement.ext_id)
        )
    ).scalars().all()
    return ok([ExtractedRequirementRead.model_validate(r).model_dump(mode="json") for r in rows])


@router.post("/projects/{project_id}/detect-gaps")
@limiter.limit("30/minute")
async def detect_gaps(
    request: Request,
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    provider: LLMProvider = Depends(get_provider_dep),
):
    reqs = (
        await db.execute(
            select(ExtractedRequirement).where(ExtractedRequirement.project_id == project_id)
        )
    ).scalars().all()

    if not reqs:
        err("no_requirements", "No requirements found. Run extraction first.", 422)

    reqs_data = [
        {
            "id": r.ext_id,
            "category": r.category,
            "text": r.text,
            "source_reference": r.source_reference,
            "confidence": r.confidence,
        }
        for r in reqs
    ]

    from app.services.skills.dspy_intake import run_gap_detector
    result = await run_gap_detector(json.dumps(reqs_data, indent=2))

    await db.execute(delete(GapQuestion).where(GapQuestion.project_id == project_id))

    new_gaps: list[GapQuestion] = []
    for item in result.get("gaps", []):
        gap = GapQuestion(
            project_id=project_id,
            ext_id=item.get("id", ""),
            question=item.get("question", ""),
            category=item.get("category", "scope"),
            severity=item.get("severity", "minor"),
        )
        db.add(gap)
        new_gaps.append(gap)

    await db.commit()
    for gap in new_gaps:
        await db.refresh(gap)

    return ok([GapQuestionRead.model_validate(g).model_dump(mode="json") for g in new_gaps])


@router.get("/projects/{project_id}/gaps")
async def list_gaps(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(GapQuestion)
            .where(GapQuestion.project_id == project_id)
            .order_by(GapQuestion.severity, GapQuestion.ext_id)
        )
    ).scalars().all()
    return ok([GapQuestionRead.model_validate(g).model_dump(mode="json") for g in rows])
