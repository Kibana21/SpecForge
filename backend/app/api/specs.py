import json
import logging
import re
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_project_or_404, get_provider_dep, require_ru_validated
from app.db import get_db
from app.limiter import limiter
from app.models.gap import GapQuestion
from app.models.project import Project
from app.models.requirement import ExtractedRequirement
from app.models.review import ReviewComment
from app.models.spec import SpecVersion
from app.schemas.envelope import err, ok
from app.schemas.spec import SpecPatch, SpecVersionRead
from app.services.export import markdown_exporter
from app.services.llm.base import LLMProvider
from app.services.skills.skill_engine import SkillEngine

log = logging.getLogger(__name__)
router = APIRouter(tags=["specs"], dependencies=[Depends(get_current_user)])
_skill_engine = SkillEngine()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _slugify(name: str) -> str:
    return re.sub(r"[^\w-]", "-", name.lower()).strip("-") or "project"


async def _get_requirements(db: AsyncSession, project_id: UUID) -> list[ExtractedRequirement]:
    return (
        await db.execute(
            select(ExtractedRequirement).where(ExtractedRequirement.project_id == project_id)
        )
    ).scalars().all()


async def _get_latest_spec(
    db: AsyncSession, project_id: UUID, spec_type: str
) -> SpecVersion | None:
    return (
        await db.execute(
            select(SpecVersion)
            .where(SpecVersion.project_id == project_id, SpecVersion.spec_type == spec_type)
            .order_by(SpecVersion.version_number.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


def _format_reqs_json(reqs: list[ExtractedRequirement]) -> str:
    return json.dumps(
        [
            {
                "id": r.ext_id,
                "category": r.category,
                "text": r.text,
                "source_reference": r.source_reference,
                "confidence": r.confidence,
            }
            for r in reqs
        ],
        indent=2,
    )


async def _allocate_and_create_spec(
    db: AsyncSession,
    project_id: UUID,
    spec_type: str,
    content_json: dict,
    project_name: str,
) -> SpecVersion:
    """Allocate next version_number under a row-level lock and create the SpecVersion."""
    await db.execute(select(Project).where(Project.id == project_id).with_for_update())
    max_ver = (
        await db.scalar(
            select(func.coalesce(func.max(SpecVersion.version_number), 0)).where(
                SpecVersion.project_id == project_id
            )
        )
    ) or 0
    version_number = max_ver + 1
    md = markdown_exporter.render(content_json, spec_type, project_name, version_number)
    spec = SpecVersion(
        project_id=project_id,
        spec_type=spec_type,
        version_number=version_number,
        content_json=content_json,
        content_markdown=md,
    )
    db.add(spec)
    return spec


# ── Generation endpoints ───────────────────────────────────────────────────────

@router.post("/projects/{project_id}/specs/functional")
@limiter.limit("30/minute")
async def generate_functional(
    request: Request,
    project_id: UUID,
    project: Project = Depends(require_ru_validated),
    db: AsyncSession = Depends(get_db),
    provider: LLMProvider = Depends(get_provider_dep),
):
    reqs = await _get_requirements(db, project_id)
    if not reqs:
        err("no_requirements", "Extract requirements first.", 422)

    resolved_gaps = (
        await db.execute(
            select(GapQuestion).where(
                GapQuestion.project_id == project_id, GapQuestion.resolved.is_(True)
            )
        )
    ).scalars().all()

    resolved_answers = (
        "\n".join(
            f"- {g.question}: {g.resolution_text or '(no answer provided)'}"
            for g in resolved_gaps
        )
        or "None"
    )

    result = await _skill_engine.run(
        "functional_spec",
        {
            "project_name": project.name,
            "extracted_requirements": _format_reqs_json(reqs),
            "resolved_gap_answers": resolved_answers,
        },
        provider,
    )

    spec = await _allocate_and_create_spec(db, project_id, "functional", result, project.name)
    await db.commit()
    await db.refresh(spec)
    return ok(SpecVersionRead.model_validate(spec).model_dump(mode="json"))


@router.post("/projects/{project_id}/specs/technical")
@limiter.limit("30/minute")
async def generate_technical(
    request: Request,
    project_id: UUID,
    project: Project = Depends(require_ru_validated),
    db: AsyncSession = Depends(get_db),
    provider: LLMProvider = Depends(get_provider_dep),
):
    reqs = await _get_requirements(db, project_id)
    func_spec = await _get_latest_spec(db, project_id, "functional")
    if not func_spec:
        err("no_functional_spec", "Generate functional spec first.", 422)

    result = await _skill_engine.run(
        "technical_spec",
        {
            "project_name": project.name,
            "functional_spec": json.dumps(func_spec.content_json, indent=2),
            "extracted_requirements": _format_reqs_json(reqs),
        },
        provider,
    )

    spec = await _allocate_and_create_spec(db, project_id, "technical", result, project.name)
    await db.commit()
    await db.refresh(spec)
    return ok(SpecVersionRead.model_validate(spec).model_dump(mode="json"))


@router.post("/projects/{project_id}/specs/user-stories")
@limiter.limit("30/minute")
async def generate_user_stories(
    request: Request,
    project_id: UUID,
    project: Project = Depends(require_ru_validated),
    db: AsyncSession = Depends(get_db),
    provider: LLMProvider = Depends(get_provider_dep),
):
    reqs = await _get_requirements(db, project_id)
    func_spec = await _get_latest_spec(db, project_id, "functional")
    if not func_spec:
        err("no_functional_spec", "Generate functional spec first.", 422)

    result = await _skill_engine.run(
        "user_stories",
        {
            "project_name": project.name,
            "functional_spec": json.dumps(func_spec.content_json, indent=2),
            "extracted_requirements": _format_reqs_json(reqs),
        },
        provider,
    )

    spec = await _allocate_and_create_spec(db, project_id, "user_stories", result, project.name)
    await db.commit()
    await db.refresh(spec)
    return ok(SpecVersionRead.model_validate(spec).model_dump(mode="json"))


@router.post("/projects/{project_id}/review")
@limiter.limit("30/minute")
async def run_review(
    request: Request,
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    provider: LLMProvider = Depends(get_provider_dep),
):
    reqs = await _get_requirements(db, project_id)
    func_spec = await _get_latest_spec(db, project_id, "functional")
    if not func_spec:
        err("no_functional_spec", "Generate at least the functional spec before reviewing.", 422)

    tech_spec = await _get_latest_spec(db, project_id, "technical")
    stories_spec = await _get_latest_spec(db, project_id, "user_stories")

    result = await _skill_engine.run(
        "reviewer",
        {
            "project_name": project.name,
            "functional_spec": json.dumps(func_spec.content_json, indent=2),
            "technical_spec": json.dumps(tech_spec.content_json, indent=2) if tech_spec else "Not generated yet",
            "user_stories": json.dumps(stories_spec.content_json, indent=2) if stories_spec else "Not generated yet",
            "extracted_requirements": _format_reqs_json(reqs),
        },
        provider,
    )

    spec = await _allocate_and_create_spec(db, project_id, "review", result, project.name)
    await db.flush()

    await db.execute(delete(ReviewComment).where(ReviewComment.project_id == project_id))

    for item in result.get("comments", []):
        db.add(
            ReviewComment(
                project_id=project_id,
                spec_version_id=spec.id,
                section=item.get("section", ""),
                comment=item.get("comment", ""),
                severity=item.get("severity", "suggestion"),
                category=item.get("category", "completeness"),
            )
        )

    await db.commit()
    await db.refresh(spec)
    return ok(SpecVersionRead.model_validate(spec).model_dump(mode="json"))


# ── Retrieval endpoints ────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/specs")
async def list_specs(
    project_id: UUID,
    all: bool = False,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(SpecVersion).where(SpecVersion.project_id == project_id)
    if not all:
        # Subquery: latest version per spec_type
        latest_sq = (
            select(func.max(SpecVersion.version_number).label("max_ver"), SpecVersion.spec_type)
            .where(SpecVersion.project_id == project_id)
            .group_by(SpecVersion.spec_type)
            .subquery()
        )
        stmt = stmt.join(
            latest_sq,
            (SpecVersion.spec_type == latest_sq.c.spec_type)
            & (SpecVersion.version_number == latest_sq.c.max_ver),
        )
    stmt = stmt.order_by(SpecVersion.spec_type, SpecVersion.version_number.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return ok([SpecVersionRead.model_validate(s).model_dump(mode="json") for s in rows])


@router.get("/projects/{project_id}/specs/{version_id}")
async def get_spec(
    project_id: UUID,
    version_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
):
    spec = (
        await db.execute(
            select(SpecVersion).where(
                SpecVersion.id == version_id, SpecVersion.project_id == project_id
            )
        )
    ).scalar_one_or_none()
    if spec is None:
        err("not_found", f"Spec version {version_id} not found", 404)
    return ok(SpecVersionRead.model_validate(spec).model_dump(mode="json"))


@router.patch("/projects/{project_id}/specs/{version_id}")
async def patch_spec(
    project_id: UUID,
    version_id: UUID,
    body: SpecPatch,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
):
    spec = (
        await db.execute(
            select(SpecVersion).where(
                SpecVersion.id == version_id, SpecVersion.project_id == project_id
            )
        )
    ).scalar_one_or_none()
    if spec is None:
        err("not_found", f"Spec version {version_id} not found", 404)

    if body.content_markdown is not None:
        spec.content_markdown = body.content_markdown
        spec.is_edited = True
    if body.content_json is not None:
        spec.content_json = body.content_json
        spec.is_edited = True

    await db.commit()
    await db.refresh(spec)
    return ok(SpecVersionRead.model_validate(spec).model_dump(mode="json"))


# ── Export endpoint ────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/export/markdown")
async def export_markdown(
    project_id: UUID,
    spec_type: str = "all",
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
):
    valid_types = {"functional", "technical", "user_stories", "review", "all"}
    if spec_type not in valid_types:
        err("invalid_spec_type", f"spec_type must be one of: {', '.join(sorted(valid_types))}", 400)

    slug = _slugify(project.name)

    if spec_type == "all":
        rendered: list[dict] = []
        for stype in ("functional", "technical", "user_stories", "review"):
            spec = await _get_latest_spec(db, project_id, stype)
            if spec:
                md = spec.content_markdown or markdown_exporter.render(
                    spec.content_json, stype, project.name, spec.version_number
                )
                rendered.append({"markdown": md})
        if not rendered:
            err("no_specs", "No specs generated yet.", 404)
        content = markdown_exporter.render_combined(rendered)
        filename = f"{slug}-all-specs.md"
    else:
        spec = await _get_latest_spec(db, project_id, spec_type)
        if spec is None:
            err("not_found", f"No {spec_type} spec generated yet.", 404)
        content = spec.content_markdown or markdown_exporter.render(
            spec.content_json, spec_type, project.name, spec.version_number
        )
        filename = f"{slug}-{spec_type.replace('_', '-')}-v{spec.version_number}.md"

    return Response(
        content=content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
