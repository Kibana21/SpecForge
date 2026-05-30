"""Project Wiki API (E2) — mirrors the App Brain wiki routes, scoped to a
project. Powers the navigable ProjectWiki view and the "Grounded in" section
drill-down. See .claude/plans/E2-intelligent-intake.md.
"""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_project_or_404
from app.core import audit
from app.db import get_db
from app.models.app import App
from app.models.document import Document
from app.models.fact import AppFact
from app.models.project import Project
from app.models.project_intake import ProjectApp
from app.models.project_source import DocumentTree
from app.models.project_wiki import ProjectWikiConcept, ProjectWikiSummary
from app.models.user import User
from app.schemas.envelope import err, ok

router = APIRouter(tags=["project-wiki"])


def _concept_dict(c: ProjectWikiConcept) -> dict:
    return {
        "id": str(c.id), "slug": c.slug, "title": c.title, "brief": c.brief,
        "content_md": c.content_md, "source_doc_ids": c.source_doc_ids,
        "related_slugs": c.related_slugs, "tree_node_refs": c.tree_node_refs,
        "compiled_at": c.compiled_at.isoformat() if c.compiled_at else None,
    }


def _summary_dict(s: ProjectWikiSummary) -> dict:
    return {
        "id": str(s.id), "doc_id": str(s.document_id), "brief": s.brief,
        "content_md": s.content_md, "related_slugs": s.related_slugs,
        "doc_type": s.doc_type,
        "compiled_at": s.compiled_at.isoformat() if s.compiled_at else None,
    }


@router.get("/projects/{project_id}/wiki")
async def get_project_wiki_index(
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Lightweight index: concept + document-summary briefs (no bodies)."""
    concepts = (await db.execute(
        select(ProjectWikiConcept)
        .where(ProjectWikiConcept.project_id == project.id)
        .order_by(ProjectWikiConcept.title)
    )).scalars().all()

    summaries = (await db.execute(
        select(ProjectWikiSummary, Document.filename)
        .join(Document, ProjectWikiSummary.document_id == Document.id)
        .where(ProjectWikiSummary.project_id == project.id)
        .order_by(Document.filename)
    )).all()

    return ok({
        "concepts": [{"slug": c.slug, "title": c.title, "brief": c.brief} for c in concepts],
        "summaries": [
            {"doc_id": str(s.document_id), "doc_name": name, "brief": s.brief, "doc_type": s.doc_type}
            for s, name in summaries
        ],
        "status": project.wiki_status or "idle",
        "compiled_at": project.wiki_compiled_at.isoformat() if project.wiki_compiled_at else None,
        "health": project.wiki_health,
    })


@router.get("/projects/{project_id}/wiki/concepts/{slug}")
async def get_project_wiki_concept(
    slug: str,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    concept = (await db.execute(
        select(ProjectWikiConcept).where(
            ProjectWikiConcept.project_id == project.id, ProjectWikiConcept.slug == slug
        )
    )).scalar_one_or_none()
    if concept is None:
        err("not_found", "Wiki concept not found", 404)
    return ok(_concept_dict(concept))


@router.get("/projects/{project_id}/wiki/summaries/{doc_id}")
async def get_project_wiki_summary(
    doc_id: uuid.UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    summary = (await db.execute(
        select(ProjectWikiSummary).where(
            ProjectWikiSummary.project_id == project.id, ProjectWikiSummary.document_id == doc_id
        )
    )).scalar_one_or_none()
    if summary is None:
        err("not_found", "Wiki summary not found", 404)
    return ok(_summary_dict(summary))


@router.post("/projects/{project_id}/wiki/rebuild", status_code=202)
async def rebuild_project_wiki_endpoint(
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Clear and recompile the entire Project Wiki from all indexed documents."""
    from app.config import get_settings

    if project.wiki_status == "running":
        return ok({"status": "already_running"})

    settings = get_settings()
    if settings.llm_provider == "mock":
        from workers.tasks import _rebuild_project_wiki
        await _rebuild_project_wiki(str(project.id))
        return ok({"task_id": None, "status": "done"})

    from workers.dispatch import dispatch
    from workers.tasks import rebuild_project_wiki
    task = dispatch(rebuild_project_wiki, str(project.id))
    await audit.emit(db, event="project.wiki.rebuild_triggered",
                     actor_id=str(current_user.id), metadata={"project_id": str(project.id)})
    await db.commit()
    return ok({"task_id": task.id if task else None, "status": "running"})


@router.post("/projects/{project_id}/wiki/health", status_code=202)
async def check_project_wiki_health_endpoint(
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Lint the compiled wiki for contradictions + orphan concepts."""
    from app.config import get_settings

    concept_count = (await db.execute(
        select(func.count(ProjectWikiConcept.id)).where(ProjectWikiConcept.project_id == project.id)
    )).scalar_one()
    if concept_count == 0:
        err("no_wiki", "Compile the wiki before checking its health.", 409)

    settings = get_settings()
    if settings.llm_provider == "mock":
        from workers.tasks import _check_project_wiki_health
        await _check_project_wiki_health(str(project.id))
        return ok({"task_id": None, "status": "done"})

    from workers.dispatch import dispatch
    from workers.tasks import check_project_wiki_health
    task = dispatch(check_project_wiki_health, str(project.id))
    await audit.emit(db, event="project.wiki.health_checked",
                     actor_id=str(current_user.id), metadata={"project_id": str(project.id)})
    await db.commit()
    return ok({"task_id": task.id if task else None, "status": "running"})


@router.get("/projects/{project_id}/provenance")
async def get_project_provenance(
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Intake provenance spine: Documents → Concepts → Clarifications. Powers the
    LineageMap (forward impact / backward provenance)."""
    from app.services.provenance.lineage import build_lineage
    return ok(await build_lineage(project.id, db))


@router.get("/projects/{project_id}/facts/{fact_id}")
async def resolve_project_fact(
    fact_id: uuid.UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Resolve an App Brain fact cited in intake grounding / clarifications
    (the canonical `F:<app_fact_id>` token) to its text + provenance. Scoped to
    the project's in-scope apps so a fact can't be read across projects."""
    row = (await db.execute(
        select(AppFact, App.name)
        .join(App, App.id == AppFact.app_id)
        .join(ProjectApp, ProjectApp.app_id == AppFact.app_id)
        .where(
            AppFact.id == fact_id,
            ProjectApp.project_id == project.id,
            ProjectApp.included.is_(True),
        )
    )).first()
    if row is None:
        err("not_found", "Fact not found for this project", 404)
    fact, app_name = row
    return ok({
        "id": str(fact.id),
        "app": app_name,
        "kind": fact.kind,
        "text": fact.text,
        "confidence": fact.confidence,
        "source_ref": fact.source_ref,
    })


@router.get("/projects/{project_id}/facts/by-index/{index}")
async def resolve_project_fact_by_index(
    index: int,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Resolve a positional fact marker (the `F#` the RU/clarifier writes inline)
    to its App Brain fact. `index` is 1-based into the SAME ordered in-scope fact
    list the grounding enumerates, so `F117` → the 117th fact. Positional refs can
    drift if the fact set changes after generation — accurate for freshly
    generated understanding, best-effort thereafter."""
    from app.services.projects.app_context import load_app_facts_for_project

    facts = await load_app_facts_for_project(project.id, db)
    if index < 1 or index > len(facts):
        err("not_found", "Fact index out of range for this project", 404)
    f = facts[index - 1]
    return ok({
        "index": index,
        "id": f["id"],
        "app": f["app"],
        "kind": f["kind"],
        "text": f["text"],
        "confidence": f["confidence"],
        "source_ref": f["source_ref"],
    })


@router.get("/projects/{project_id}/sources/{doc_id}/section/{node_id}")
async def get_project_source_section(
    doc_id: uuid.UUID,
    node_id: str,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return one PageIndex section's source text — powers the wiki 'Grounded in'
    drill-down and the Understanding Studio source peek."""
    from app.services.corpus_index.base import find_node, node_text

    row = (await db.execute(
        select(DocumentTree, Document.filename)
        .join(Document, Document.id == DocumentTree.document_id)
        .where(DocumentTree.document_id == doc_id, DocumentTree.project_id == project.id)
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
        "text": node_text(node, tree.page_texts),
    })
