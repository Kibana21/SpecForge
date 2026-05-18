import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_project_or_404, get_provider_dep
from app.config import get_settings
from app.db import get_db
from app.limiter import limiter
from app.models.document import Document
from app.models.gap import GapQuestion
from app.models.project import Project
from app.models.requirement import ExtractedRequirement
from app.schemas.document import DocumentRead
from app.schemas.envelope import err, ok
from app.schemas.gap import GapQuestionRead
from app.schemas.requirement import ExtractedRequirementRead
from app.services.documents import parser, storage
from app.services.llm.base import LLMProvider
from app.services.skills.skill_engine import SkillEngine

log = logging.getLogger(__name__)
router = APIRouter(tags=["documents"])
_skill_engine = SkillEngine()

_REQUIREMENT_CATEGORY_MAP = {
    "functional_requirements": "functional",
    "non_functional_requirements": "non_functional",
    "constraints": "constraint",
    "assumptions": "assumption",
    "stakeholders": "stakeholder",
}


@router.post("/projects/{project_id}/documents", status_code=201)
async def upload_document(
    request: Request,
    project_id: UUID,
    file: UploadFile = File(...),
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    content = await file.read()

    if len(content) > settings.max_upload_bytes:
        err("file_too_large", f"File exceeds {settings.max_upload_mb} MB limit", 413)

    mime = storage.detect_mime(content)
    if mime not in storage.ALLOWED_MIME_TYPES:
        err("unsupported_file_type", "Unsupported file type. Allowed: PDF, DOCX, TXT", 422)

    safe_name = storage.sanitize_filename(file.filename or "upload")
    storage_path = await storage.save(str(project_id), safe_name, mime, content, settings.upload_dir)

    doc = Document(
        project_id=project_id,
        filename=safe_name,
        mime_type=mime,
        size_bytes=len(content),
        storage_path=storage_path,
        parse_status="pending",
    )
    db.add(doc)
    await db.flush()

    try:
        text = parser.parse(content, mime)
        doc.extracted_text = text
        doc.parse_status = "done"
    except Exception as exc:
        log.warning("doc_parse_failed doc_id=%s error=%s", doc.id, exc)
        doc.parse_error = str(exc)[:500]
        doc.parse_status = "error"

    await db.commit()
    await db.refresh(doc)
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

    result = await _skill_engine.run(
        "requirement_extractor",
        {"project_name": project.name, "document_text": document_text},
        provider,
    )

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

    result = await _skill_engine.run(
        "gap_detector",
        {"extracted_requirements": json.dumps(reqs_data, indent=2)},
        provider,
    )

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
