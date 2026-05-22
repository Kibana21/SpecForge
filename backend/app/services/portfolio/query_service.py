"""RBAC-filtered portfolio query: search + saved views + grouping.

One place that builds the access-scoped project query so the list, the saved-view
counts, and grouping all share identical RBAC + view semantics.
"""
from __future__ import annotations

from sqlalchemy import and_, cast, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import UserDefinedType

from app.models.document import Document
from app.models.project import Project, ProjectMember
from app.models.review import ReviewComment
from app.models.spec import SpecVersion
from app.models.user import User

_ADMIN_ROLES = {"platform_admin", "compliance_reviewer"}

_STALE_JSONPATH = '$.* ? (@.status == "stale")'


class JsonPath(UserDefinedType):
    """Postgres `jsonpath` type so jsonb_path_exists receives the right arg type."""
    cache_ok = True

    def get_col_spec(self, **kw):
        return "jsonpath"


def is_stale_expr():
    """True when any stage in stage_progress has status == 'stale'."""
    return func.jsonb_path_exists(Project.stage_progress, cast(_STALE_JSONPATH, JsonPath()))

# 6 saved views (BR-M1-002)
SAVED_VIEWS = [
    ("all", "All projects"),
    ("mine", "My projects"),
    ("needs_review", "Needs review"),
    ("stale", "Stale"),
    ("high_priority", "High priority"),
    ("finalized", "Finalized"),
]

GROUP_COLUMNS = {
    "business_unit": Project.business_unit,
    "status": Project.status,
    "owner": Project.owner_id,
}


def _is_stale():
    return is_stale_expr()


def _has_open_review():
    return exists().where(
        ReviewComment.project_id == Project.id, ReviewComment.dismissed.is_(False)
    )


def _access_clause(user: User):
    if user.role in _ADMIN_ROLES:
        return None  # sees all
    member_sq = select(ProjectMember.project_id).where(ProjectMember.user_id == user.id)
    return or_(Project.owner_id == user.id, Project.id.in_(member_sq))


def _view_clause(view: str, user: User):
    if view == "mine":
        member_sq = select(ProjectMember.project_id).where(ProjectMember.user_id == user.id)
        return or_(Project.owner_id == user.id, Project.id.in_(member_sq))
    if view == "needs_review":
        return _has_open_review()
    if view == "stale":
        return _is_stale()
    if view == "high_priority":
        return Project.priority.in_(("high", "critical"))
    if view == "finalized":
        return Project.status == "finalized"
    return None  # "all" or unknown


def _base_conditions(user: User, q: str | None, view: str):
    conds = [Project.deleted_at.is_(None)]
    access = _access_clause(user)
    if access is not None:
        conds.append(access)
    if q:
        like = f"%{q.strip().lower()}%"
        conds.append(
            or_(
                func.lower(Project.name).like(like),
                func.lower(func.coalesce(Project.human_id, "")).like(like),
                func.lower(func.coalesce(Project.business_unit, "")).like(like),
            )
        )
    vclause = _view_clause(view, user)
    if vclause is not None:
        conds.append(vclause)
    return and_(*conds)


async def list_projects(
    *, db: AsyncSession, user: User, q: str | None = None, view: str = "all",
    group_by: str = "none", limit: int = 50, offset: int = 0,
) -> tuple[list, int, list | None]:
    """Returns (rows, total, groups). rows are (Project, doc_count, latest_spec_type,
    open_review_count, is_stale). groups is None unless group_by is set."""
    where = _base_conditions(user, q, view)

    if group_by in GROUP_COLUMNS:
        col = GROUP_COLUMNS[group_by]
        result = (
            await db.execute(
                select(
                    col.label("key"),
                    func.count(Project.id).label("count"),
                    func.count().filter(_is_stale()).label("stale"),
                    func.count().filter(_has_open_review()).label("review"),
                    func.count().filter(Project.status == "finalized").label("finalized"),
                )
                .where(where)
                .group_by(col)
                .order_by(func.count(Project.id).desc())
            )
        ).all()
        groups = [
            {
                "key": (r.key if r.key is not None else "—"),
                "count": r.count,
                "stale": r.stale,
                "review": r.review,
                "finalized": r.finalized,
            }
            for r in result
        ]
        total = sum(g["count"] for g in groups)
        return [], total, groups

    doc_count_sq = (
        select(func.count(Document.id)).where(Document.project_id == Project.id)
        .correlate(Project).scalar_subquery()
    )
    latest_spec_sq = (
        select(SpecVersion.spec_type).where(SpecVersion.project_id == Project.id)
        .order_by(SpecVersion.updated_at.desc()).limit(1).correlate(Project).scalar_subquery()
    )
    review_count_sq = (
        select(func.count(ReviewComment.id)).where(
            ReviewComment.project_id == Project.id, ReviewComment.dismissed.is_(False)
        ).correlate(Project).scalar_subquery()
    )

    rows = (
        await db.execute(
            select(
                Project,
                doc_count_sq.label("doc_count"),
                latest_spec_sq.label("latest_spec_type"),
                review_count_sq.label("open_review_count"),
                _is_stale().label("is_stale"),
            )
            .where(where)
            .order_by(Project.updated_at.desc())
            .limit(min(limit, 100))
            .offset(offset)
        )
    ).all()

    total = await db.scalar(select(func.count(Project.id)).where(where))
    return rows, (total or 0), None


async def view_counts(db: AsyncSession, user: User) -> list[dict]:
    """Count of accessible projects per saved view (BR-M1-002)."""
    out = []
    for view, label in SAVED_VIEWS:
        where = _base_conditions(user, None, view)
        count = await db.scalar(select(func.count(Project.id)).where(where))
        out.append({"view": view, "label": label, "count": count or 0})
    return out
