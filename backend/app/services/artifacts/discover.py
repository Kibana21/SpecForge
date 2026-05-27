"""Discover Phase service: context gathering, brief enhancement, question analysis."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import ArtifactDocument, CbDiscoverEnhancedBrief, CbDiscoverQuestion
from app.models.document import Document
from app.models.project import Project
from app.models.project_source import DocumentTree
from app.services.artifacts.app_context import gather_impacted_apps_context
from app.services.artifacts.discover_catalog import (
    DISCOVER_QUESTIONS, LLM_ANALYSIS_KEYS, PROJECT_PREFILL,
    QUESTION_BY_KEY, QUESTION_KEYS, UNIT_DISCOVER_MAP,
)
from app.services.corpus_index import IndexedDoc, get_corpus_index_provider
from app.services.skills.dspy_discover import run_discover_analysis, run_enhance_brief


# ── Context gathering ─────────────────────────────────────────────────────────

async def _gather_discover_context(
    project: Project,
    db: AsyncSession,
) -> tuple[str, str, list[dict], list[dict]]:
    """Return (project_doc_sections, app_brain_context, doc_sources, app_sources)."""
    from app.config import get_settings

    query = (
        f"{project.name} business problem customers value outcomes "
        f"scope milestones KPI assumptions strategic driver"
    )
    rows = (
        await db.execute(
            select(DocumentTree, Document.filename)
            .join(Document, Document.id == DocumentTree.document_id)
            .where(DocumentTree.project_id == project.id)
        )
    ).all()

    doc_sources: list[dict] = []
    if rows:
        docs = [
            IndexedDoc(
                document_id=t.document_id, doc_name=name,
                tree=t.tree_json, page_texts=t.page_texts,
            )
            for t, name in rows
        ]
        top_k = get_settings().tree_search_top_k
        sections = await get_corpus_index_provider().tree_search(
            query=query, docs=docs, top_k=top_k * 2,
        )
        if sections:
            project_doc_sections = "\n\n".join(
                f"[D{i}] {s.doc_name} › {s.title}\n{s.text[:1000]}"
                for i, s in enumerate(sections, 1)
            )
            doc_sources = [
                {"doc_id": str(s.document_id), "filename": s.doc_name, "section": s.title}
                for s in sections
            ]
        else:
            project_doc_sections = "(no project documents indexed)"
    else:
        project_doc_sections = "(no project documents indexed)"

    raw_app_context = await gather_impacted_apps_context(project.id, db)
    app_brain_context = raw_app_context or "(no linked apps)"

    # Resolve app sources for attribution
    from app.models.project_intake import ProjectApp
    from app.models.app import App
    app_rows = (
        await db.execute(
            select(ProjectApp, App.name)
            .join(App, App.id == ProjectApp.app_id)
            .where(ProjectApp.project_id == project.id, ProjectApp.included.is_(True))
        )
    ).all()
    app_sources = [{"app_id": str(pa.app_id), "app_name": name} for pa, name in app_rows]

    return project_doc_sections, app_brain_context, doc_sources, app_sources


# ── Ensure document ───────────────────────────────────────────────────────────

async def _ensure_discover_document(
    project_id: uuid.UUID, artifact_type: str, db: AsyncSession
) -> ArtifactDocument:
    """Get or create the artifact document, setting status to in_discover."""
    from app.models.artifact import ArtifactSource
    from sqlalchemy.exc import IntegrityError

    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == artifact_type,
            )
        )
    ).scalar_one_or_none()

    if doc is None:
        try:
            async with db.begin_nested():
                doc = ArtifactDocument(
                    project_id=project_id,
                    artifact_type=artifact_type,
                    status="in_discover",
                )
                db.add(doc)
                await db.flush()
                project_docs = (
                    await db.execute(
                        select(Document.id).where(Document.project_id == project_id)
                    )
                ).scalars().all()
                for doc_id in project_docs:
                    db.add(ArtifactSource(
                        artifact_document_id=doc.id,
                        source_document_id=doc_id,
                        included=True,
                    ))
                await db.flush()
        except IntegrityError:
            doc = (
                await db.execute(
                    select(ArtifactDocument).where(
                        ArtifactDocument.project_id == project_id,
                        ArtifactDocument.artifact_type == artifact_type,
                    )
                )
            ).scalar_one()
    else:
        doc.status = "in_discover"

    return doc


# ── Enhance brief ─────────────────────────────────────────────────────────────

async def enhance_brief(
    project: Project,
    artifact_type: str,
    brief_text: str,
    db: AsyncSession,
) -> dict:
    """Run BriefEnhancerModule; persist audit record; return result dict."""
    project_doc_sections, app_brain_context, doc_sources, app_sources = (
        await _gather_discover_context(project, db)
    )

    result = await run_enhance_brief(
        project_name=project.name,
        business_unit=project.business_unit or "—",
        user_brief=brief_text,
        project_doc_sections=project_doc_sections,
        app_brain_context=app_brain_context,
    )
    enhanced = result["enhanced_brief"]

    # Persist for audit — look up the document if it exists
    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project.id,
                ArtifactDocument.artifact_type == artifact_type,
            )
        )
    ).scalar_one_or_none()

    if doc:
        db.add(CbDiscoverEnhancedBrief(
            artifact_document_id=doc.id,
            original_brief=brief_text,
            enhanced_brief=enhanced,
            doc_sources=doc_sources,
            app_sources=app_sources,
        ))
        await db.flush()

    return {
        "enhanced_brief": enhanced,
        "doc_count": len({s["filename"] for s in doc_sources}),
        "app_count": len(app_sources),
        "doc_sources": doc_sources,
        "app_sources": app_sources,
    }


# ── Analyze brief → upsert questions ─────────────────────────────────────────

async def analyze_brief(
    project: Project,
    artifact_type: str,
    brief_text: str,
    db: AsyncSession,
) -> list[CbDiscoverQuestion]:
    """Analyze brief + context; upsert all 14 discover questions; return them."""
    doc = await _ensure_discover_document(project.id, artifact_type, db)
    await db.flush()

    project_doc_sections, app_brain_context, doc_sources, app_sources = (
        await _gather_discover_context(project, db)
    )

    # Build analysis rows for LLM questions
    llm_questions = [QUESTION_BY_KEY[k] for k in LLM_ANALYSIS_KEYS]
    analysis_rows = await run_discover_analysis(
        project_name=project.name,
        business_unit=project.business_unit or "—",
        brief_text=brief_text,
        project_doc_sections=project_doc_sections,
        app_brain_context=app_brain_context,
        questions=llm_questions,
    )
    analysis_by_key = {r["question_key"]: r for r in analysis_rows}

    # Upsert all 14 questions
    now = datetime.now(timezone.utc)
    for seq, q in enumerate(DISCOVER_QUESTIONS):
        key = q["key"]

        # Determine answer + source
        if key in PROJECT_PREFILL:
            prefill_val = PROJECT_PREFILL[key](project)
            answer = prefill_val if prefill_val else None
            inferred = prefill_val or None
            source = "project" if answer else None
        else:
            row = analysis_by_key.get(key, {})
            if row.get("answered"):
                answer = row.get("extracted_answer") or None
                inferred = answer
                source = row.get("source") or None
            else:
                answer = None
                extracted = row.get("extracted_answer", "")
                inferred = extracted if extracted else None
                source = row.get("source") or None

        # Load existing question for this doc+key
        existing = (
            await db.execute(
                select(CbDiscoverQuestion).where(
                    CbDiscoverQuestion.artifact_document_id == doc.id,
                    CbDiscoverQuestion.question_key == key,
                )
            )
        ).scalar_one_or_none()

        context_sources = {"docs": doc_sources, "apps": app_sources}

        if existing is None:
            db.add(CbDiscoverQuestion(
                artifact_document_id=doc.id,
                question_key=key,
                category=q["category"],
                question_text=q["text"],
                answer=answer,
                inferred_answer=inferred,
                source=source,
                context_sources=context_sources,
                seq=seq,
                updated_at=now,
            ))
        else:
            # Preserve user-supplied answers; refresh inference for non-user questions
            if existing.source != "user":
                existing.answer = answer
                existing.inferred_answer = inferred
                existing.source = source
                existing.context_sources = context_sources
                existing.updated_at = now

    await db.flush()

    # Store brief as initial context message (idempotent — skip if already present)
    from app.models.artifact import ArtifactMessage
    from sqlalchemy import func
    has_initial = await db.scalar(
        select(func.count(ArtifactMessage.id)).where(
            ArtifactMessage.document_id == doc.id,
            ArtifactMessage.role == "user",
        )
    )
    if not has_initial and brief_text.strip():
        seq_val = await db.scalar(
            select(func.coalesce(func.max(ArtifactMessage.seq), 0)).where(
                ArtifactMessage.document_id == doc.id
            )
        ) or 0
        db.add(ArtifactMessage(
            document_id=doc.id,
            project_id=project.id,
            role="user",
            content=brief_text.strip(),
            citations=[],
            meta={"is_initial_context": True},
            seq=seq_val + 1,
        ))

    await db.commit()
    return await _get_questions_for_doc(doc.id, db)


# ── Get questions ─────────────────────────────────────────────────────────────

async def get_questions(
    project_id: uuid.UUID, artifact_type: str, db: AsyncSession
) -> dict:
    """Return questions + most recent enhanced brief for the project."""
    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == artifact_type,
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        return {"questions": [], "enhanced_brief": None}

    questions = await _get_questions_for_doc(doc.id, db)

    # Latest enhanced brief (if any)
    latest_eb = (
        await db.execute(
            select(CbDiscoverEnhancedBrief)
            .where(CbDiscoverEnhancedBrief.artifact_document_id == doc.id)
            .order_by(CbDiscoverEnhancedBrief.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    return {
        "questions": questions,
        "enhanced_brief": latest_eb.enhanced_brief if latest_eb else None,
    }


async def _get_questions_for_doc(
    document_id: uuid.UUID, db: AsyncSession
) -> list[CbDiscoverQuestion]:
    return (
        await db.execute(
            select(CbDiscoverQuestion)
            .where(CbDiscoverQuestion.artifact_document_id == document_id)
            .order_by(CbDiscoverQuestion.seq)
        )
    ).scalars().all()


# ── Answer one question ───────────────────────────────────────────────────────

async def answer_question(
    question_id: uuid.UUID, answer: str, db: AsyncSession
) -> CbDiscoverQuestion:
    q = await db.get(CbDiscoverQuestion, question_id)
    if q is None:
        raise ValueError(f"Question {question_id} not found")
    q.answer = answer.strip() if answer.strip() else None
    q.source = "user" if answer.strip() else q.source
    q.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return q


# ── Complete discover → trigger generation ────────────────────────────────────

async def complete_discover(
    project: Project,
    artifact_type: str,
    db: AsyncSession,
) -> dict:
    """Validate all questions answered, build discover_context, dispatch generation."""
    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project.id,
                ArtifactDocument.artifact_type == artifact_type,
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        raise ValueError("Artifact document not found — run analyze first")

    questions = await _get_questions_for_doc(doc.id, db)
    unanswered = [
        q.question_key for q in questions
        if not (q.answer and q.answer.strip())
    ]
    if unanswered:
        raise ValueError(f"Unanswered questions: {', '.join(unanswered)}")

    # Build discover_context string (filtered per unit via UNIT_DISCOVER_MAP)
    discover_context = _build_discover_context(questions)

    # Transition to generating
    doc.status = "generating"
    await db.commit()

    from app.config import get_settings
    if get_settings().llm_provider == "mock":
        from app.services.artifacts.orchestrator import generate_all
        return await generate_all(project, artifact_type, db, discover_context=discover_context)

    from workers.dispatch import dispatch
    from workers.tasks import generate_concept_brief
    dispatch(generate_concept_brief, str(project.id), artifact_type, None, discover_context)

    from app.services.artifacts.orchestrator import get_artifact_detail
    return await get_artifact_detail(project.id, artifact_type, db)


def _build_discover_context(questions: list[CbDiscoverQuestion]) -> str:
    """Format all answered questions into a single context string for DSPy units."""
    CATEGORY_LABELS = {
        "initiative_context": "Initiative Context",
        "business_context": "Business Context",
        "value_outcomes": "Value & Outcomes",
        "scope_assumptions": "Scope & Assumptions",
        "delivery": "Delivery",
    }
    SOURCE_LABELS = {
        "project": "from: project",
        "brief": "from: your brief",
        "documents": "from: documents",
        "app_brain": "from: app brain",
        "combined": "from: multiple sources",
        "ai_enhanced": "from: AI enhanced",
        "user": "you answered",
    }

    lines = ["=== Pre-Generation Discovery ===\n"]
    current_category = None
    for q in sorted(questions, key=lambda x: x.seq):
        if q.category != current_category:
            current_category = q.category
            lines.append(f"\n[{CATEGORY_LABELS.get(q.category, q.category)}]")
        answer = q.answer or "(not answered)"
        source_label = SOURCE_LABELS.get(q.source or "", "")
        suffix = f"  [{source_label}]" if source_label else ""
        lines.append(f"Q: {q.question_text}")
        lines.append(f"A: {answer}{suffix}\n")

    return "\n".join(lines)


# ── Serialisation helper ──────────────────────────────────────────────────────

def question_to_dict(q: CbDiscoverQuestion) -> dict:
    return {
        "id": str(q.id),
        "question_key": q.question_key,
        "category": q.category,
        "question_text": q.question_text,
        "answer": q.answer,
        "inferred_answer": q.inferred_answer,
        "source": q.source,
        "context_sources": q.context_sources,
        "seq": q.seq,
        "created_at": q.created_at.isoformat(),
        "updated_at": q.updated_at.isoformat(),
    }
