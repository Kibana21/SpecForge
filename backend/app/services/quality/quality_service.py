"""Heuristic quality subscores + stage-progress for the workspace (BR-M1-010/011).

These are deliberately simple signals — the full consistency/traceability engine
lands in E4. Each subscore is 0–100; `overall` is their average.
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gap import GapQuestion
from app.models.requirement import ExtractedRequirement
from app.models.spec import SpecVersion
from app.models.understanding import RequirementUnderstanding

# 10-stage workspace map. Only RU + the three generated specs have real signals in
# E2; the rest render "not_started" until their modules ship (E3/E4).
STAGES: list[tuple[str, str]] = [
    ("requirement_understanding", "Requirement Understanding"),
    ("brd", "Business Requirements"),
    ("functional_spec", "Functional Spec"),
    ("nfr", "Non-Functional Requirements"),
    ("technical_spec", "Technical Spec"),
    ("user_stories", "User Stories"),
    ("data_model", "Data Model"),
    ("api_design", "API Design"),
    ("test_plan", "Test Plan"),
    ("operations", "Operations Guide"),
]

_SPEC_STAGE = {"functional": "functional_spec", "technical": "technical_spec", "user_stories": "user_stories"}


async def compute_stage_progress(project_id: uuid.UUID, db: AsyncSession) -> dict:
    progress = {key: {"label": label, "progress": 0, "status": "not_started"} for key, label in STAGES}

    ru = (
        await db.execute(
            select(RequirementUnderstanding.status).where(RequirementUnderstanding.project_id == project_id)
        )
    ).scalar_one_or_none()
    if ru == "validated":
        progress["requirement_understanding"] = {**progress["requirement_understanding"], "progress": 100, "status": "done"}
    elif ru in ("in_interview", "draft"):
        progress["requirement_understanding"] = {**progress["requirement_understanding"], "progress": 50, "status": "in_progress"}

    spec_types = set(
        (await db.execute(select(SpecVersion.spec_type).where(SpecVersion.project_id == project_id))).scalars().all()
    )
    for spec_type, stage_key in _SPEC_STAGE.items():
        if spec_type in spec_types:
            progress[stage_key] = {**progress[stage_key], "progress": 100, "status": "done"}

    return progress


async def subscores(project_id: uuid.UUID, db: AsyncSession) -> dict:
    ru = (
        await db.execute(
            select(RequirementUnderstanding).where(RequirementUnderstanding.project_id == project_id)
        )
    ).scalar_one_or_none()

    # completeness — avg of RU per-field completeness
    completeness = 0
    if ru and isinstance(ru.field_confidence, dict) and ru.field_confidence:
        vals = [v.get("completeness", 0) for v in ru.field_confidence.values() if isinstance(v, dict)]
        completeness = round(sum(vals) / len(vals)) if vals else 0

    # clarity — fewer open interview questions = clearer
    open_q = await db.scalar(
        select(func.count(GapQuestion.id)).where(
            GapQuestion.project_id == project_id,
            GapQuestion.source == "interview",
            GapQuestion.resolved.is_(False),
        )
    ) or 0
    clarity = max(0, 100 - 12 * open_q)

    # traceability — % of extracted requirements with a source reference
    total_reqs = await db.scalar(
        select(func.count(ExtractedRequirement.id)).where(ExtractedRequirement.project_id == project_id)
    ) or 0
    with_ref = await db.scalar(
        select(func.count(ExtractedRequirement.id)).where(
            ExtractedRequirement.project_id == project_id,
            ExtractedRequirement.source_reference.isnot(None),
        )
    ) or 0
    traceability = round(100 * with_ref / total_reqs) if total_reqs else 0

    # nfr_coverage — non-functional requirement signal
    nfr_count = await db.scalar(
        select(func.count(ExtractedRequirement.id)).where(
            ExtractedRequirement.project_id == project_id,
            ExtractedRequirement.category == "non_functional",
        )
    ) or 0
    nfr_coverage = min(100, nfr_count * 25)

    # risk_coverage — RU records risks?
    risks = (ru.content_json.get("risks") if ru and isinstance(ru.content_json, dict) else None) or []
    risk_coverage = 100 if risks else 0

    consistency = 100  # placeholder — real engine lands in E4

    scores = {
        "completeness": completeness,
        "clarity": clarity,
        "traceability": traceability,
        "nfr_coverage": nfr_coverage,
        "risk_coverage": risk_coverage,
        "consistency": consistency,
    }
    scores["overall"] = round(sum(scores.values()) / len(scores))
    scores["heuristic"] = True  # flag for the UI: these are preliminary signals
    return scores
