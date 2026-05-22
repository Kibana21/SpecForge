"""App Brain registry API — /api/apps"""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.core import audit
from app.db import get_db
from app.limiter import limiter
from app.models.app import App, AppMember
from app.models.corpus import AppChunk, AppCorpusDoc
from app.models.fact import AppFact
from app.models.project import Project
from app.models.project_intake import ProjectApp
from app.models.storage import StorageFile, StorageFileBlob
from app.models.user import User
from app.schemas.app import AppCreate, AppDetail, AppFactRead, AppListItem, AppUpdate, AskRequest, PipelineSummary, AppCorpusDocRead
from app.schemas.envelope import err, ok
from app.services.documents.storage import detect_mime, sanitize_filename

router = APIRouter(prefix="/api/apps", tags=["apps"])

# ── Access dependencies ───────────────────────────────────────────────────────

async def _get_app_or_404(app_id: uuid.UUID, db: AsyncSession) -> App:
    result = await db.execute(select(App).where(App.id == app_id))
    app = result.scalar_one_or_none()
    if app is None:
        err("not_found", "App not found", 404)
    return app  # type: ignore[return-value]


async def require_app_access(
    app_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> App:
    """Returns app if accessible; 404 for non-onboarded apps the user has no membership in."""
    result = await db.execute(select(App).where(App.id == app_id))
    app = result.scalar_one_or_none()

    if app is None:
        err("not_found", "App not found", 404)

    if user.role == "platform_admin":
        return app  # type: ignore[return-value]

    # Check membership
    member_result = await db.execute(
        select(AppMember).where(AppMember.app_id == app_id, AppMember.user_id == user.id)
    )
    is_member = member_result.scalar_one_or_none() is not None

    if not app.is_onboarded and not is_member:  # type: ignore[union-attr]
        err("not_found", "App not found", 404)

    return app  # type: ignore[return-value]


async def require_app_write_access(
    app_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> App:
    """platform_admin OR app owner/delegate."""
    app = await require_app_access(app_id=app_id, user=user, db=db)

    if user.role == "platform_admin":
        return app

    member_result = await db.execute(
        select(AppMember).where(AppMember.app_id == app_id, AppMember.user_id == user.id)
    )
    member = member_result.scalar_one_or_none()
    if member is None:
        err("forbidden", "Write access required", 403)

    return app  # type: ignore[return-value]


# ── List apps ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_apps(
    q: str | None = None,
    tier: int | None = None,
    mine: bool = False,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    limit = min(limit, 100)

    # Base query
    stmt = select(App)

    # Access filter
    if user.role != "platform_admin":
        member_subq = select(AppMember.app_id).where(AppMember.user_id == user.id)
        stmt = stmt.where(
            (App.is_onboarded == True) | App.id.in_(member_subq)  # noqa: E712
        )

    if q:
        stmt = stmt.where(
            App.name.ilike(f"%{q}%") | App.short_name.ilike(f"%{q}%")
        )
    if tier is not None:
        stmt = stmt.where(App.tier == tier)
    if mine:
        member_sq = select(AppMember.app_id).where(AppMember.user_id == user.id)
        stmt = stmt.where(App.id.in_(member_sq))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.offset(offset).limit(limit).order_by(App.name)
    result = await db.execute(stmt)
    apps = result.scalars().all()

    items = []
    for app in apps:
        doc_result = await db.execute(
            select(func.count()).where(AppCorpusDoc.app_id == app.id)
        )
        corpus_doc_count = doc_result.scalar_one()

        indexed_result = await db.execute(
            select(func.count()).where(
                AppCorpusDoc.app_id == app.id,
                AppCorpusDoc.index_status == "done",
            )
        )
        indexed_doc_count = indexed_result.scalar_one()

        fact_count = (await db.execute(
            select(func.count()).where(AppFact.app_id == app.id, AppFact.status == "active")
        )).scalar_one()

        # LIVE PROJECTS — distinct projects with this app in scope
        live_project_count = (await db.execute(
            select(func.count(func.distinct(ProjectApp.project_id)))
            .where(ProjectApp.app_id == app.id, ProjectApp.included.is_(True))
        )).scalar_one()

        # OPEN QS — proposed facts awaiting owner review
        open_qs = (await db.execute(
            select(func.count()).where(AppFact.app_id == app.id, AppFact.status == "proposed")
        )).scalar_one()

        items.append(AppListItem.model_validate({
            **{c.name: getattr(app, c.name) for c in app.__table__.columns},
            "corpus_doc_count": corpus_doc_count,
            "indexed_doc_count": indexed_doc_count,
            "fact_count": fact_count,
            "live_project_count": live_project_count,
            "open_qs": open_qs,
        }))

    return ok([item.model_dump() for item in items], meta={"total": total, "limit": limit, "offset": offset})


# ── Create app ────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_app(
    body: AppCreate,
    user: User = Depends(require_role("platform_admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    # Check short_name uniqueness (case-insensitive)
    result = await db.execute(
        select(App).where(func.lower(App.short_name) == body.short_name.lower())
    )
    if result.scalar_one_or_none() is not None:
        err("short_name_conflict", f"short_name '{body.short_name}' is already taken", 409)

    app = App(
        name=body.name,
        short_name=body.short_name,
        description=body.description,
        tier=body.tier,
        domain_area=body.domain_area,
        version=body.version,
        owner_team=body.owner_team,
        environments=body.environments,
        owner_id=user.id,
        is_onboarded=False,
    )
    db.add(app)
    await db.flush()

    await audit.emit(db, event="app.created", actor_id=str(user.id),
                     metadata={"app_id": str(app.id), "short_name": app.short_name})
    await db.commit()

    return ok(_app_detail(app, [], [], _pipeline_summary([], [])))


# ── App suggestion (apps-in-scope, BR-M1-008) ──────────────────────────────────
# NOTE: must be declared before the "/{app_id}" routes so "suggest" isn't captured.

@router.get("/suggest")
async def suggest_apps_for_project(
    project_id: uuid.UUID | None = None,
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Onboarded apps ranked by relevance to a project (or free-text) for the
    wizard's apps-in-scope step. Pass `project_id` (uses its stored text) or `q`."""
    from app.services.projects.discovery_service import suggest_apps

    query_text = (q or "").strip()
    if project_id is not None and not query_text:
        proj = await db.get(Project, project_id)
        if proj is None:
            err("not_found", f"Project {project_id} not found", 404)
        parts = [proj.name, proj.description or "", proj.business_unit or "", proj.app_scope or ""]
        query_text = "\n".join(p for p in parts if p).strip()
    if not query_text:
        err("missing_query", "Provide project_id or q to suggest apps.", 422)

    suggestions = await suggest_apps(query_text, db)
    return ok([s.model_dump(mode="json") for s in suggestions])


# ── Get app detail ────────────────────────────────────────────────────────────

@router.get("/{app_id}")
async def get_app(
    app: App = Depends(require_app_access),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    corpus_result = await db.execute(
        select(AppCorpusDoc).where(AppCorpusDoc.app_id == app.id)
    )
    corpus_docs = corpus_result.scalars().all()

    facts_result = await db.execute(select(AppFact).where(AppFact.app_id == app.id))
    facts = facts_result.scalars().all()

    chunks_result = await db.execute(
        select(AppChunk).join(AppCorpusDoc, AppChunk.doc_id == AppCorpusDoc.id)
        .where(AppCorpusDoc.app_id == app.id)
    )
    chunks = chunks_result.scalars().all()

    return ok(_app_detail(app, corpus_docs, facts, _pipeline_summary(corpus_docs, chunks)))


@router.patch("/{app_id}")
async def update_app(
    body: AppUpdate,
    app: App = Depends(require_app_write_access),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Edit app metadata (name, tier, owner team, environments, version, …)."""
    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(app, field, value)
    await audit.emit(db, event="app.updated", actor_id=str(user.id),
                     metadata={"app_id": str(app.id), "fields": list(changes.keys())})
    await db.commit()
    await db.refresh(app)

    corpus_docs = (await db.execute(select(AppCorpusDoc).where(AppCorpusDoc.app_id == app.id))).scalars().all()
    facts = (await db.execute(select(AppFact).where(AppFact.app_id == app.id))).scalars().all()
    chunks = (await db.execute(
        select(AppChunk).join(AppCorpusDoc, AppChunk.doc_id == AppCorpusDoc.id).where(AppCorpusDoc.app_id == app.id)
    )).scalars().all()
    return ok(_app_detail(app, corpus_docs, facts, _pipeline_summary(corpus_docs, chunks)))


@router.delete("/{app_id}")
async def delete_app(
    app: App = Depends(require_app_write_access),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete an app and its App Brain (corpus, chunks, trees, facts, members).
    Owner or platform_admin only; cascades remove project_apps references too."""
    app_id, name = app.id, app.name
    await db.delete(app)  # FK ON DELETE CASCADE removes corpus/chunks/trees/facts/members/project_apps
    await audit.emit(db, event="app.deleted", actor_id=str(user.id),
                     metadata={"app_id": str(app_id), "name": name})
    await db.commit()
    return ok({"id": str(app_id)})


def _pipeline_summary(corpus_docs: list, chunks: list) -> PipelineSummary:
    total_docs = len(corpus_docs)
    indexed_docs = sum(1 for d in corpus_docs if d.index_status == "done")
    pending_docs = sum(1 for d in corpus_docs if d.index_status in ("pending", "running"))
    last_indexed = max((d.indexed_at for d in corpus_docs if d.indexed_at), default=None)
    return PipelineSummary(
        total_docs=total_docs,
        indexed_docs=indexed_docs,
        pending_docs=pending_docs,
        total_chunks=len(chunks),
        total_facts=0,
        last_indexed_at=last_indexed,
    )


def _app_detail(app: App, corpus_docs: list, facts: list, pipeline: PipelineSummary) -> dict:
    return {
        "id": str(app.id),
        "name": app.name,
        "short_name": app.short_name,
        "description": app.description,
        "tier": app.tier,
        "domain_area": app.domain_area,
        "is_onboarded": app.is_onboarded,
        "version": app.version,
        "owner_id": str(app.owner_id) if app.owner_id else None,
        "owner_team": app.owner_team,
        "environments": app.environments or [],
        "corpus_docs": [
            {
                "id": str(d.id), "app_id": str(d.app_id), "name": d.name,
                "page_count": d.page_count, "is_primary": d.is_primary,
                "index_status": d.index_status, "indexed_at": d.indexed_at.isoformat() if d.indexed_at else None,
                "created_at": d.created_at.isoformat(),
            }
            for d in corpus_docs
        ],
        "facts": [
            {
                "id": str(f.id), "app_id": str(f.app_id), "kind": f.kind,
                "text": f.text, "source_ref": f.source_ref, "confidence": f.confidence,
                "status": f.status, "chunk_ids": f.chunk_ids,
                "created_at": f.created_at.isoformat(), "updated_at": f.updated_at.isoformat(),
            }
            for f in facts
        ],
        "pipeline_summary": pipeline.model_dump(),
        "created_at": app.created_at.isoformat(),
        "updated_at": app.updated_at.isoformat(),
    }


# ── Upload corpus document ────────────────────────────────────────────────────

ALLOWED_CORPUS_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}


@router.post("/{app_id}/corpus", status_code=202)
@limiter.limit("10/minute")
async def upload_corpus_doc(
    request: Request,
    file: UploadFile,
    is_primary: bool = False,
    app: App = Depends(require_app_write_access),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.config import get_settings
    settings = get_settings()
    max_bytes = settings.corpus_max_upload_mb * 1024 * 1024

    content = await file.read()
    if len(content) > max_bytes:
        err("file_too_large", f"File exceeds {settings.corpus_max_upload_mb}MB limit", 413)

    mime = detect_mime(content)
    if mime not in ALLOWED_CORPUS_MIME:
        err("invalid_mime_type", f"Unsupported file type: {mime}. Allowed: PDF, DOCX, TXT.", 422)

    # SHA-256 dedup
    import hashlib as _hashlib
    sha = _hashlib.sha256(content).hexdigest()

    existing = await db.execute(
        select(StorageFile).where(StorageFile.sha256 == sha)
    )
    existing_file = existing.scalar_one_or_none()
    if existing_file:
        # Check if already in this app's corpus
        dup = await db.execute(
            select(AppCorpusDoc).where(
                AppCorpusDoc.app_id == app.id,
                AppCorpusDoc.file_id == existing_file.id,
            )
        )
        if dup.scalar_one_or_none():
            err("duplicate_document", "This file is already in the corpus", 409)

    safe_name = sanitize_filename(file.filename or "upload")

    # Persist to StorageFile + StorageFileBlob
    storage_file = StorageFile(
        name=safe_name,
        content_type=mime,
        size=len(content),
        sha256=sha,
        created_by=user.id,
    )
    db.add(storage_file)
    await db.flush()

    blob = StorageFileBlob(file_id=storage_file.id, chunk_no=0, data=content)
    db.add(blob)
    await db.flush()

    corpus_doc = AppCorpusDoc(
        app_id=app.id,
        file_id=storage_file.id,
        name=safe_name,
        is_primary=is_primary,
        index_status="pending",
    )
    db.add(corpus_doc)
    await db.flush()

    await audit.emit(
        db,
        event="corpus.doc.uploaded",
        actor_id=str(user.id),
        metadata={"app_id": str(app.id), "doc_id": str(corpus_doc.id), "name": safe_name},
    )
    await db.commit()

    # Dispatch ingestion task (best-effort; never hangs if broker is down)
    from workers.dispatch import dispatch
    from workers.tasks import ingest_corpus_doc
    dispatch(ingest_corpus_doc, str(corpus_doc.id))

    return ok({
        "id": str(corpus_doc.id),
        "app_id": str(app.id),
        "name": corpus_doc.name,
        "page_count": corpus_doc.page_count,
        "is_primary": corpus_doc.is_primary,
        "index_status": corpus_doc.index_status,
        "indexed_at": None,
        "created_at": corpus_doc.created_at.isoformat(),
    })


# ── Re-index app ──────────────────────────────────────────────────────────────

@router.post("/{app_id}/reindex", status_code=202)
@limiter.limit("2/minute")
async def reindex_app(
    request: Request,
    app: App = Depends(require_app_write_access),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if app.rebuild_status == "rebuilding":
        err("rebuild_in_progress", "A rebuild is already in progress for this app", 409)

    await db.execute(
        update(App).where(App.id == app.id).values(
            rebuild_status="rebuilding",
            updated_at=datetime.now(timezone.utc),
        )
    )

    await audit.emit(
        db,
        event="app.reindex.triggered",
        actor_id=str(user.id),
        metadata={"app_id": str(app.id)},
    )
    await db.commit()

    from workers.dispatch import dispatch
    from workers.tasks import rebuild_app_brain
    task = dispatch(rebuild_app_brain, str(app.id))

    return ok({"task_id": task.id if task else None})


# ── List facts ────────────────────────────────────────────────────────────────

@router.get("/{app_id}/facts")
async def list_facts(
    kind: str | None = None,
    status: str | None = "active",
    confidence: str | None = None,
    limit: int = 50,
    offset: int = 0,
    app: App = Depends(require_app_access),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(AppFact).where(AppFact.app_id == app.id)

    if kind:
        stmt = stmt.where(AppFact.kind == kind)
    if status:
        stmt = stmt.where(AppFact.status == status)
    if confidence:
        stmt = stmt.where(AppFact.confidence == confidence)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.offset(offset).limit(min(limit, 100)).order_by(AppFact.created_at.desc())
    result = await db.execute(stmt)
    facts = result.scalars().all()

    return ok(
        [AppFactRead.model_validate(f).model_dump() for f in facts],
        meta={"total": total, "limit": limit, "offset": offset},
    )


# ── Ask the app brain (SSE) ───────────────────────────────────────────────────

@router.post("/{app_id}/ask")
@limiter.limit("20/minute")
async def ask_app_brain(
    request: Request,
    body: AskRequest,
    app: App = Depends(require_app_access),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    from app.services.llm import get_provider
    from app.services.rag.rag_service import AppBrainRAGService

    provider = get_provider()
    rag_service = AppBrainRAGService()
    question_hash = hashlib.sha256(body.question.encode()).hexdigest()

    await audit.emit(
        db,
        event="app.brain.ask",
        actor_id=str(user.id),
        metadata={
            "app_id": str(app.id),
            "question_hash": question_hash,
            "top_k": body.top_k,
        },
    )
    await db.commit()

    async def event_generator():
        async for event in rag_service.stream_answer(
            app_id=app.id,
            question=body.question,
            top_k=body.top_k,
            db=db,
            app_name=app.name,
            provider=provider,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Transfer-Encoding": "chunked",
        },
    )
