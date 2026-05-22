"""Materialized per-user triage (BR-M1-005).

Recomputes a prioritized, personalized worklist from the user's accessible
projects: open reviews, pending RU validations, stale specs, low-confidence
assumptions. Used by the Beat recompute and an on-demand fallback.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, delete, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.project import Project, ProjectMember
from app.models.project_intake import Assumption, TriageItem
from app.models.review import ReviewComment
from app.models.understanding import RequirementUnderstanding
from app.models.user import User
from app.services.portfolio.query_service import is_stale_expr

_ADMIN_ROLES = {"platform_admin", "compliance_reviewer"}
_RECOMPUTE_INTERVAL_MIN = 15

# kind → priority (lower = more urgent)
_PRIORITY = {"review": 1, "approval": 2, "stale_impact": 3, "low_confidence": 4}


def _accessible(user: User):
    if user.role in _ADMIN_ROLES:
        return Project.deleted_at.is_(None)
    member_sq = select(ProjectMember.project_id).where(ProjectMember.user_id == user.id)
    return and_(
        Project.deleted_at.is_(None),
        or_(Project.owner_id == user.id, Project.id.in_(member_sq)),
    )


async def compute_for_user(user_id: uuid.UUID, db: AsyncSession) -> list[TriageItem]:
    user = await db.get(User, user_id)
    if user is None:
        return []

    now = datetime.now(timezone.utc)
    next_at = now + timedelta(minutes=_RECOMPUTE_INTERVAL_MIN)
    access = _accessible(user)
    items: list[TriageItem] = []

    def add(project_id, kind, title, link):
        items.append(TriageItem(
            user_id=user_id, project_id=project_id, kind=kind,
            priority=_PRIORITY[kind], title=title, link=link,
            computed_at=now, next_at=next_at,
        ))

    # 1. Open review comments
    review_rows = (
        await db.execute(
            select(Project.id, Project.name, func.count(ReviewComment.id).label("n"))
            .join(ReviewComment, ReviewComment.project_id == Project.id)
            .where(access, ReviewComment.dismissed.is_(False))
            .group_by(Project.id, Project.name)
        )
    ).all()
    for pid, name, n in review_rows:
        add(pid, "review", f"{n} open review comment{'s' if n != 1 else ''} — {name}", f"/projects/{pid}")

    # 2. Pending RU validation (sources indexed but RU not validated)
    approval_rows = (
        await db.execute(
            select(Project.id, Project.name)
            .join(RequirementUnderstanding, RequirementUnderstanding.project_id == Project.id)
            .where(
                access,
                Project.ru_validated.is_(False),
                exists().where(Document.project_id == Project.id, Document.indexing_status == "done"),
            )
        )
    ).all()
    for pid, name in approval_rows:
        add(pid, "approval", f"Validate Requirement Understanding — {name}", f"/projects/{pid}/interview")

    # 3. Stale specs
    stale_rows = (
        await db.execute(
            select(Project.id, Project.name).where(access, is_stale_expr())
        )
    ).all()
    for pid, name in stale_rows:
        add(pid, "stale_impact", f"Stale specs need refresh — {name}", f"/projects/{pid}")

    # 4. Open low-confidence assumptions
    lowconf_rows = (
        await db.execute(
            select(Project.id, Project.name, func.count(Assumption.id).label("n"))
            .join(Assumption, Assumption.project_id == Project.id)
            .where(access, Assumption.status == "open", Assumption.confidence == "low")
            .group_by(Project.id, Project.name)
        )
    ).all()
    for pid, name, n in lowconf_rows:
        add(pid, "low_confidence", f"{n} low-confidence assumption{'s' if n != 1 else ''} — {name}", f"/projects/{pid}")

    # Replace this user's triage items wholesale
    await db.execute(delete(TriageItem).where(TriageItem.user_id == user_id))
    if items:
        db.add_all(items)
    await db.commit()
    for it in items:
        await db.refresh(it)
    return sorted(items, key=lambda i: i.priority)
