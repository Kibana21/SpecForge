"""App Brain registry API — /api/apps"""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, delete as sa_delete, func, or_, select, text as sa_text, update
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
from app.models.wiki import AppWikiConcept, AppWikiSummary
from app.models.ask_session import AppAskSession
from app.schemas.app import AppCreate, AppDetail, AppFactRead, AppListItem, AppUpdate, AskRequest, BrainContextResponse, PipelineSummary, AppCorpusDocRead, FactCreate, FactUpdate, AppWikiConceptRead, AppWikiSummaryRead, AskSessionSave, AskSessionRead
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

    chunks_result = await db.execute(
        select(AppChunk).join(AppCorpusDoc, AppChunk.doc_id == AppCorpusDoc.id)
        .where(AppCorpusDoc.app_id == app.id)
    )
    chunks = chunks_result.scalars().all()

    return ok(_app_detail(app, corpus_docs, _pipeline_summary(corpus_docs, chunks)))


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
    chunks = (await db.execute(
        select(AppChunk).join(AppCorpusDoc, AppChunk.doc_id == AppCorpusDoc.id).where(AppCorpusDoc.app_id == app.id)
    )).scalars().all()
    return ok(_app_detail(app, corpus_docs, _pipeline_summary(corpus_docs, chunks)))


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


def _app_detail(app: App, corpus_docs: list, pipeline: PipelineSummary) -> dict:
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
        "pipeline_summary": pipeline.model_dump(),
        "brain_context_synthesized_at": app.brain_context_synthesized_at.isoformat() if app.brain_context_synthesized_at else None,
        "brain_context_status": app.brain_context_status or "idle",
        "wiki_compiled_at": app.wiki_compiled_at.isoformat() if app.wiki_compiled_at else None,
        "wiki_status": app.wiki_status or "idle",
        "wiki_health": app.wiki_health,
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


# ── Per-document: delete / markdown / reindex ─────────────────────────────────

@router.delete("/{app_id}/corpus/{doc_id}", status_code=204)
async def delete_corpus_doc(
    doc_id: uuid.UUID,
    app: App = Depends(require_app_write_access),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(AppCorpusDoc).where(AppCorpusDoc.id == doc_id, AppCorpusDoc.app_id == app.id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        err("not_found", "Corpus document not found", 404)

    # Delete AI-extracted facts that are traceable to this doc.
    # Two linkage paths (both set by _extract_app_facts since the per-doc fix):
    #   1. source_ref = doc.name  — explicit name attribution
    #   2. chunk_ids JSONB array contains any UUID belonging to this doc's chunks
    # We must do this BEFORE deleting the corpus doc so the app_chunks join still resolves.
    await db.execute(
        sa_text("""
            DELETE FROM app_facts
            WHERE app_id = :app_id
              AND source = 'ai'
              AND (
                source_ref = :doc_name
                OR EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements_text(COALESCE(chunk_ids, '[]'::jsonb)) AS t(cid)
                    JOIN app_chunks c ON c.id::text = t.cid
                    WHERE c.doc_id = :doc_id
                )
              )
        """),
        {"app_id": str(app.id), "doc_name": doc.name, "doc_id": str(doc.id)},
    )

    # Delete cached markdown conversion
    from app.models.document_markdown import DocumentMarkdown
    await db.execute(
        sa_delete(DocumentMarkdown).where(DocumentMarkdown.correlation_id == str(doc.id))
    )

    # Delete corpus doc — FK CASCADE removes AppChunk rows and AppDocTree
    await db.delete(doc)

    await audit.emit(
        db,
        event="corpus.doc.deleted",
        actor_id=str(user.id),
        metadata={"app_id": str(app.id), "doc_id": str(doc.id), "name": doc.name},
    )
    await db.commit()


@router.get("/{app_id}/corpus/{doc_id}/markdown")
async def get_corpus_doc_markdown(
    doc_id: uuid.UUID,
    app: App = Depends(require_app_access),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(AppCorpusDoc).where(AppCorpusDoc.id == doc_id, AppCorpusDoc.app_id == app.id)
    )
    if result.scalar_one_or_none() is None:
        err("not_found", "Corpus document not found", 404)

    from app.models.document_markdown import DocumentMarkdown
    md_result = await db.execute(
        select(DocumentMarkdown)
        .where(DocumentMarkdown.correlation_id == str(doc_id))
        .order_by(DocumentMarkdown.created_at.desc())
        .limit(1)
    )
    md = md_result.scalar_one_or_none()
    if md is None:
        err("not_found", "Markdown not yet available for this document", 404)

    return ok({
        "markdown_text": md.markdown_text,
        "provider": md.provider,
        "filename": md.filename,
        "created_at": md.created_at.isoformat(),
    })


@router.post("/{app_id}/corpus/{doc_id}/reindex", status_code=202)
async def reindex_corpus_doc(
    doc_id: uuid.UUID,
    app: App = Depends(require_app_write_access),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(AppCorpusDoc).where(AppCorpusDoc.id == doc_id, AppCorpusDoc.app_id == app.id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        err("not_found", "Corpus document not found", 404)

    await db.execute(
        update(AppCorpusDoc).where(AppCorpusDoc.id == doc_id).values(
            index_status="pending",
            index_error=None,
        )
    )

    await audit.emit(
        db,
        event="corpus.doc.reindex.triggered",
        actor_id=str(user.id),
        metadata={"app_id": str(app.id), "doc_id": str(doc.id), "name": doc.name},
    )
    await db.commit()

    from workers.dispatch import dispatch
    from workers.tasks import ingest_corpus_doc
    task = dispatch(ingest_corpus_doc, str(doc_id))

    return ok({"task_id": task.id if task else None})


# ── Re-extract facts ──────────────────────────────────────────────────────────

# ── Per-document facts ────────────────────────────────────────────────────────

@router.get("/{app_id}/corpus/{doc_id}/facts")
async def list_doc_facts(
    doc_id: uuid.UUID,
    app: App = Depends(require_app_access),
    db: AsyncSession = Depends(get_db),
) -> dict:
    doc_result = await db.execute(
        select(AppCorpusDoc).where(AppCorpusDoc.id == doc_id, AppCorpusDoc.app_id == app.id)
    )
    doc = doc_result.scalar_one_or_none()
    if doc is None:
        err("not_found", "Corpus document not found", 404)

    facts_result = await db.execute(
        select(AppFact).where(
            AppFact.app_id == app.id,
            AppFact.status != "dismissed",
            AppFact.source != "brain",
            or_(
                AppFact.doc_id == doc_id,
                and_(AppFact.doc_id.is_(None), AppFact.source_ref == doc.name),
            ),
        ).order_by(AppFact.created_at.desc())
    )
    facts = facts_result.scalars().all()
    return ok([AppFactRead.model_validate(f).model_dump() for f in facts])


@router.post("/{app_id}/corpus/{doc_id}/facts", status_code=201)
async def create_doc_fact(
    doc_id: uuid.UUID,
    body: FactCreate,
    app: App = Depends(require_app_write_access),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(AppCorpusDoc).where(AppCorpusDoc.id == doc_id, AppCorpusDoc.app_id == app.id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        err("not_found", "Corpus document not found", 404)

    fact = AppFact(
        app_id=app.id,
        doc_id=doc_id,
        kind=body.kind,
        text=body.text,
        confidence=body.confidence,
        source_ref=body.source_ref or doc.name,
        status="active",
        source="human",
        chunk_ids=[],
        source_fact_ids=[],
    )
    db.add(fact)
    await audit.emit(db, event="app.fact.created", actor_id=str(user.id),
                     metadata={"app_id": str(app.id), "doc_id": str(doc_id), "kind": body.kind})
    await db.commit()
    await db.refresh(fact)
    return ok(AppFactRead.model_validate(fact).model_dump())


# ── Brain Context ─────────────────────────────────────────────────────────────

@router.get("/{app_id}/brain-context")
async def get_brain_context(
    app: App = Depends(require_app_access),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return synthesized brain facts + synthesis metadata."""
    brain_facts_result = await db.execute(
        select(AppFact).where(
            AppFact.app_id == app.id,
            AppFact.source == "brain",
            AppFact.status == "active",
        ).order_by(AppFact.kind, AppFact.created_at)
    )
    brain_facts = brain_facts_result.scalars().all()

    source_count_result = await db.execute(
        select(func.count(AppCorpusDoc.id)).where(AppCorpusDoc.app_id == app.id)
    )
    source_doc_count = source_count_result.scalar_one()

    return ok({
        "facts": [AppFactRead.model_validate(f).model_dump() for f in brain_facts],
        "synthesized_at": app.brain_context_synthesized_at.isoformat() if app.brain_context_synthesized_at else None,
        "status": app.brain_context_status or "idle",
        "source_doc_count": source_doc_count,
    })


@router.post("/{app_id}/brain-context/synthesize", status_code=202)
async def trigger_brain_synthesis(
    app: App = Depends(require_app_write_access),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Dispatch brain context synthesis task."""
    if app.brain_context_status == "running":
        return ok({"status": "already_running"})

    from workers.dispatch import dispatch
    from workers.tasks import synthesize_brain_context

    task = dispatch(synthesize_brain_context, str(app.id))

    await audit.emit(db, event="app.brain_context.synthesize_triggered",
                     actor_id=str(user.id), metadata={"app_id": str(app.id)})
    await db.commit()
    return ok({"task_id": task.id if task else None, "status": "running"})


# ── Brain Wiki ──────────────────────────────────────────────────────────────────

@router.get("/{app_id}/wiki")
async def get_wiki_index(
    app: App = Depends(require_app_access),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Lightweight wiki index: concept + document-summary briefs (no bodies)."""
    concepts = (await db.execute(
        select(AppWikiConcept).where(AppWikiConcept.app_id == app.id).order_by(AppWikiConcept.title)
    )).scalars().all()

    summaries = (await db.execute(
        select(AppWikiSummary, AppCorpusDoc.name)
        .join(AppCorpusDoc, AppWikiSummary.doc_id == AppCorpusDoc.id)
        .where(AppWikiSummary.app_id == app.id)
        .order_by(AppCorpusDoc.name)
    )).all()

    return ok({
        "concepts": [
            {"slug": c.slug, "title": c.title, "brief": c.brief} for c in concepts
        ],
        "summaries": [
            {"doc_id": str(s.doc_id), "doc_name": name, "brief": s.brief, "doc_type": s.doc_type}
            for s, name in summaries
        ],
        "status": app.wiki_status or "idle",
        "compiled_at": app.wiki_compiled_at.isoformat() if app.wiki_compiled_at else None,
        "health": app.wiki_health,
    })


@router.get("/{app_id}/wiki/concepts/{slug}")
async def get_wiki_concept(
    slug: str,
    app: App = Depends(require_app_access),
    db: AsyncSession = Depends(get_db),
) -> dict:
    concept = (await db.execute(
        select(AppWikiConcept).where(AppWikiConcept.app_id == app.id, AppWikiConcept.slug == slug)
    )).scalar_one_or_none()
    if concept is None:
        err("not_found", "Wiki concept not found", 404)
    return ok(AppWikiConceptRead.model_validate(concept).model_dump(mode="json"))


@router.get("/{app_id}/wiki/summaries/{doc_id}")
async def get_wiki_summary(
    doc_id: uuid.UUID,
    app: App = Depends(require_app_access),
    db: AsyncSession = Depends(get_db),
) -> dict:
    summary = (await db.execute(
        select(AppWikiSummary).where(AppWikiSummary.app_id == app.id, AppWikiSummary.doc_id == doc_id)
    )).scalar_one_or_none()
    if summary is None:
        err("not_found", "Wiki summary not found", 404)
    return ok(AppWikiSummaryRead.model_validate(summary).model_dump(mode="json"))


@router.post("/{app_id}/wiki/rebuild", status_code=202)
async def rebuild_wiki(
    app: App = Depends(require_app_write_access),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Clear and recompile the entire Brain Wiki from all indexed corpus docs."""
    if app.wiki_status == "running":
        return ok({"status": "already_running"})

    from workers.dispatch import dispatch
    from workers.tasks import rebuild_app_wiki

    task = dispatch(rebuild_app_wiki, str(app.id))

    await audit.emit(db, event="app.wiki.rebuild_triggered",
                     actor_id=str(user.id), metadata={"app_id": str(app.id)})
    await db.commit()
    return ok({"task_id": task.id if task else None, "status": "running"})


@router.post("/{app_id}/wiki/health", status_code=202)
async def check_wiki_health_endpoint(
    app: App = Depends(require_app_write_access),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Lint the compiled wiki for contradictions + orphan concepts."""
    concept_count = (await db.execute(
        select(func.count(AppWikiConcept.id)).where(AppWikiConcept.app_id == app.id)
    )).scalar_one()
    if concept_count == 0:
        err("no_wiki", "Compile the wiki before checking its health.", 409)

    from workers.dispatch import dispatch
    from workers.tasks import check_wiki_health

    task = dispatch(check_wiki_health, str(app.id))
    await audit.emit(db, event="app.wiki.health_checked",
                     actor_id=str(user.id), metadata={"app_id": str(app.id)})
    await db.commit()
    return ok({"task_id": task.id if task else None, "status": "running"})


@router.get("/{app_id}/corpus/{doc_id}/section/{node_id}")
async def get_corpus_section(
    doc_id: uuid.UUID,
    node_id: str,
    app: App = Depends(require_app_access),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the source text of one PageIndex section — powers the wiki's
    'Grounded in' peek (click a section chip to see the exact grounding text)."""
    from app.models.corpus import AppDocTree
    from app.services.corpus_index.base import find_node, node_text

    row = (await db.execute(
        select(AppDocTree, AppCorpusDoc.name)
        .join(AppCorpusDoc, AppCorpusDoc.id == AppDocTree.corpus_doc_id)
        .where(AppDocTree.corpus_doc_id == doc_id, AppDocTree.app_id == app.id)
    )).first()
    if row is None:
        err("not_found", "Document tree not found", 404)
    tree, doc_name = row
    node = find_node(tree.tree_json, node_id)
    if node is None:
        err("not_found", "Section not found", 404)
    s, e = node.get("start_index"), node.get("end_index")
    return ok({
        "doc_id": str(doc_id),
        "doc_name": doc_name,
        "node_id": node_id,
        "title": (node.get("title") or "").strip(),
        "pages": f"{s}-{e}" if s is not None and e is not None else "",
        "summary": (node.get("summary") or "").strip(),
        "text": node_text(node, tree.page_texts),
    })


@router.post("/{app_id}/facts/extract", status_code=202)
async def extract_facts(
    app: App = Depends(require_app_write_access),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Dispatch a fact re-extraction on existing chunks (no corpus rebuild)."""
    from workers.dispatch import dispatch
    from workers.tasks import extract_app_facts

    task = dispatch(extract_app_facts, str(app.id))

    await audit.emit(
        db,
        event="app.facts.extract_triggered",
        actor_id=str(user.id),
        metadata={"app_id": str(app.id)},
    )
    await db.commit()

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


# ── Fact CRUD ────────────────────────────────────────────────────────────────

@router.post("/{app_id}/facts", status_code=201)
async def create_fact(
    body: FactCreate,
    app: App = Depends(require_app_write_access),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    fact = AppFact(
        app_id=app.id,
        kind=body.kind,
        text=body.text,
        confidence=body.confidence,
        source_ref=body.source_ref,
        status="active",
        source="human",
        chunk_ids=[],
    )
    db.add(fact)
    await audit.emit(db, event="app.fact.created", actor_id=str(user.id),
                     metadata={"app_id": str(app.id), "kind": body.kind, "text": body.text[:120]})
    await db.commit()
    await db.refresh(fact)
    return ok(AppFactRead.model_validate(fact).model_dump())


@router.patch("/{app_id}/facts/{fact_id}")
async def update_fact(
    fact_id: uuid.UUID,
    body: FactUpdate,
    app: App = Depends(require_app_write_access),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    fact = await db.get(AppFact, fact_id)
    if not fact or fact.app_id != app.id:
        err("fact_not_found", "Fact not found", 404)
    if body.kind is not None:
        fact.kind = body.kind
    if body.text is not None:
        fact.text = body.text
    if body.confidence is not None:
        fact.confidence = body.confidence
    if body.source_ref is not None:
        fact.source_ref = body.source_ref
    if body.status is not None:
        fact.status = body.status
    fact.source = "human"
    fact.updated_at = datetime.now(timezone.utc)
    await audit.emit(db, event="app.fact.updated", actor_id=str(user.id),
                     metadata={"app_id": str(app.id), "fact_id": str(fact_id),
                                "changes": body.model_dump(exclude_none=True)})
    await db.commit()
    await db.refresh(fact)
    return ok(AppFactRead.model_validate(fact).model_dump())


@router.delete("/{app_id}/facts/{fact_id}", status_code=204)
async def delete_fact(
    fact_id: uuid.UUID,
    app: App = Depends(require_app_write_access),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    fact = await db.get(AppFact, fact_id)
    if not fact or fact.app_id != app.id:
        err("fact_not_found", "Fact not found", 404)
    await audit.emit(db, event="app.fact.deleted", actor_id=str(user.id),
                     metadata={"app_id": str(app.id), "fact_id": str(fact_id),
                                "source": fact.source, "kind": fact.kind})
    await db.delete(fact)
    await db.commit()


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
    from app.services.rag.agent import AppBrainAgent
    from app.services.rag.rag_service import AppBrainRAGService

    provider = get_provider()
    question_hash = hashlib.sha256(body.question.encode()).hexdigest()

    # Deep mode requires a compiled wiki; otherwise transparently use Quick.
    use_deep = body.mode == "deep"
    if use_deep:
        concept_count = (await db.execute(
            select(func.count(AppWikiConcept.id)).where(AppWikiConcept.app_id == app.id)
        )).scalar_one()
        if concept_count == 0:
            use_deep = False

    await audit.emit(
        db,
        event="app.brain.ask",
        actor_id=str(user.id),
        metadata={
            "app_id": str(app.id),
            "question_hash": question_hash,
            "top_k": body.top_k,
            "mode": "deep" if use_deep else "quick",
        },
    )
    await db.commit()

    async def event_generator():
        if body.mode == "deep" and not use_deep:
            yield f"data: {json.dumps({'type': 'step', 'text': 'Deep search needs a compiled wiki — using Quick search.'})}\n\n"
        if use_deep:
            stream = AppBrainAgent().stream_answer(
                app_id=app.id, question=body.question, top_k=body.top_k,
                db=db, app_name=app.name, provider=provider, history=body.history,
            )
        else:
            stream = AppBrainRAGService().stream_answer(
                app_id=app.id, question=body.question, top_k=body.top_k,
                db=db, app_name=app.name, provider=provider, history=body.history,
            )
        async for event in stream:
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


# ── Ask Brain saved sessions (per-user chat history) ────────────────────────────

@router.get("/{app_id}/ask/sessions")
async def list_ask_sessions(
    app: App = Depends(require_app_access),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List the current user's saved chat sessions for this app (newest first, no bodies)."""
    rows = (await db.execute(
        select(
            AppAskSession.id, AppAskSession.title,
            func.jsonb_array_length(AppAskSession.messages),
            AppAskSession.created_at, AppAskSession.updated_at,
        )
        .where(AppAskSession.app_id == app.id, AppAskSession.user_id == user.id)
        .order_by(AppAskSession.updated_at.desc())
    )).all()
    return ok([
        {
            "id": str(sid), "title": title, "message_count": count or 0,
            "created_at": created.isoformat(), "updated_at": updated.isoformat(),
        }
        for sid, title, count, created, updated in rows
    ])


@router.get("/{app_id}/ask/sessions/{session_id}")
async def get_ask_session(
    session_id: uuid.UUID,
    app: App = Depends(require_app_access),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    sess = (await db.execute(
        select(AppAskSession).where(
            AppAskSession.id == session_id,
            AppAskSession.app_id == app.id,
            AppAskSession.user_id == user.id,
        )
    )).scalar_one_or_none()
    if sess is None:
        err("not_found", "Chat session not found", 404)
    return ok(AskSessionRead.model_validate(sess).model_dump(mode="json"))


@router.post("/{app_id}/ask/sessions")
async def save_ask_session(
    body: AskSessionSave,
    app: App = Depends(require_app_access),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Upsert a chat session: creates one when id is null, else updates the user's own."""
    messages = [m.model_dump() for m in body.messages]
    sess: AppAskSession | None = None
    if body.id is not None:
        sess = (await db.execute(
            select(AppAskSession).where(
                AppAskSession.id == body.id,
                AppAskSession.app_id == app.id,
                AppAskSession.user_id == user.id,
            )
        )).scalar_one_or_none()
    if sess is None:
        sess = AppAskSession(app_id=app.id, user_id=user.id, title=body.title[:200], messages=messages)
        db.add(sess)
    else:
        sess.title = body.title[:200]
        sess.messages = messages
    await db.commit()
    await db.refresh(sess)
    return ok({"id": str(sess.id), "updated_at": sess.updated_at.isoformat()})


@router.delete("/{app_id}/ask/sessions/{session_id}", status_code=204)
async def delete_ask_session(
    session_id: uuid.UUID,
    app: App = Depends(require_app_access),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    sess = (await db.execute(
        select(AppAskSession).where(
            AppAskSession.id == session_id,
            AppAskSession.app_id == app.id,
            AppAskSession.user_id == user.id,
        )
    )).scalar_one_or_none()
    if sess is not None:
        await db.delete(sess)
        await db.commit()
