import csv
import io
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.api.deps import require_role
from app.core import audit
from app.db import get_db
from app.limiter import limiter
from app.models.audit import AuditEvent
from app.models.user import User
from app.schemas.audit import AuditSummary
from app.schemas.envelope import ok
from app.services.audit.catalog import classify, events_for_category

router = APIRouter(tags=["audit"])

# Audit is sensitive (IPs, security events) — only these two roles may read it.
require_audit = require_role("platform_admin", "compliance_reviewer")
_EXPORT_CAP = 10_000


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


async def _filtered(
    db: AsyncSession, *, q: str | None, event: str | None, category: str | None,
    actor_id: str | None, project_id: str | None, app_key: str | None,
    correlation_id: str | None, start: datetime | None, end: datetime | None,
) -> Select:
    stmt = select(AuditEvent)
    if event:
        stmt = stmt.where(AuditEvent.event == event)
    elif category:
        evs = events_for_category(category)
        if evs:
            stmt = stmt.where(AuditEvent.event.in_(evs))
    if actor_id:
        stmt = stmt.where(AuditEvent.actor_id == actor_id)
    if project_id:
        stmt = stmt.where(AuditEvent.project_id == project_id)
    if app_key:
        stmt = stmt.where(AuditEvent.app_key == app_key)
    if correlation_id:
        stmt = stmt.where(AuditEvent.correlation_id == correlation_id)
    if start:
        stmt = stmt.where(AuditEvent.ts >= start)
    if end:
        stmt = stmt.where(AuditEvent.ts <= end)
    if q:
        like = f"%{q}%"
        conds = [
            AuditEvent.event.ilike(like),
            AuditEvent.action.ilike(like),
            AuditEvent.document_key.ilike(like),
            cast(AuditEvent.ai_meta, String).ilike(like),
        ]
        # also match by actor name/email
        uids = (await db.execute(
            select(User.id).where(or_(User.display_name.ilike(like), User.email.ilike(like)))
        )).scalars().all()
        if uids:
            conds.append(AuditEvent.actor_id.in_([str(u) for u in uids]))
        stmt = stmt.where(or_(*conds))
    return stmt


async def _resolve_actors(db: AsyncSession, rows: list[AuditEvent]) -> dict[str, User]:
    uuids = []
    for r in rows:
        if r.actor_id:
            try:
                uuids.append(uuid.UUID(r.actor_id))
            except ValueError:
                pass
    if not uuids:
        return {}
    users = (await db.execute(select(User).where(User.id.in_(uuids)))).scalars().all()
    return {str(u.id): u for u in users}


def _actor_name(row: AuditEvent, u: User | None) -> str:
    if u:
        return u.display_name
    return "Unknown" if row.actor_id else "System"  # unresolvable id vs. automated/system action


def _serialize(row: AuditEvent, actors: dict[str, User]) -> dict:
    meta = classify(row.event)
    u = actors.get(row.actor_id) if row.actor_id else None
    return {
        "id": row.id,
        "ts": row.ts.isoformat(),
        "event": row.event,
        "label": meta.label,
        "category": meta.category,
        "severity": meta.severity,
        "actor_id": row.actor_id,
        "actor_name": _actor_name(row, u),
        "actor_email": (u.email if u else None),
        "actor_role": (u.role if u else None),
        "action": row.action,
        "project_id": row.project_id,
        "document_key": row.document_key,
        "app_key": row.app_key,
        "ip": row.ip,
        "user_agent": row.user_agent,
        "correlation_id": row.correlation_id,
        "metadata": row.ai_meta,
        "affected_sections": row.affected_sections,
    }


@router.get("/audit/summary")
async def audit_summary(
    user: User = Depends(require_audit),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    d24, d7 = now - timedelta(hours=24), now - timedelta(days=7)

    async def _count(*conds) -> int:
        return (await db.execute(select(func.count()).select_from(AuditEvent).where(*conds))).scalar_one()

    summary = AuditSummary(
        events_today=await _count(AuditEvent.ts >= today),
        failed_logins_24h=await _count(AuditEvent.event == "login_failed", AuditEvent.ts >= d24),
        lockouts_24h=await _count(AuditEvent.event == "login_blocked_lockout", AuditEvent.ts >= d24),
        token_reuse_7d=await _count(AuditEvent.event == "refresh_token_reuse_detected", AuditEvent.ts >= d7),
        deletions_7d=await _count(AuditEvent.event.in_(["app.deleted", "project.deleted"]), AuditEvent.ts >= d7),
        ai_actions_today=await _count(
            AuditEvent.event.in_(["understanding.generated", "app.brain.ask", "app.reindex.triggered"]),
            AuditEvent.ts >= today,
        ),
    )
    return ok(summary.model_dump())


@router.get("/audit/export.csv")
@limiter.limit("10/hour")
async def export_audit(
    request: Request,
    q: str | None = None,
    event: str | None = None,
    category: str | None = None,
    actor_id: str | None = None,
    project_id: str | None = None,
    app_key: str | None = None,
    correlation_id: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    user: User = Depends(require_audit),
    db: AsyncSession = Depends(get_db),
):
    stmt = await _filtered(db, q=q, event=event, category=category, actor_id=actor_id,
                           project_id=project_id, app_key=app_key, correlation_id=correlation_id,
                           start=start, end=end)
    rows = (await db.execute(
        stmt.order_by(AuditEvent.ts.desc(), AuditEvent.id.desc()).limit(_EXPORT_CAP)
    )).scalars().all()
    actors = await _resolve_actors(db, rows)

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["timestamp", "event", "label", "category", "severity", "actor", "actor_email",
                "action", "project_id", "document_key", "app_key", "ip", "correlation_id"])
    for r in rows:
        meta = classify(r.event)
        u = actors.get(r.actor_id) if r.actor_id else None
        w.writerow([
            r.ts.isoformat(), r.event, meta.label, meta.category, meta.severity,
            _actor_name(r, u),
            (u.email if u else ""), r.action or "", r.project_id or "",
            r.document_key or "", r.app_key or "", r.ip or "", r.correlation_id or "",
        ])

    applied = {k: v for k, v in {"q": q, "event": event, "category": category,
                                 "actor_id": actor_id, "project_id": project_id}.items() if v}
    await audit.emit(db, event="audit.exported", actor_id=str(user.id), email=user.email,
                     ip=_client_ip(request), user_agent=request.headers.get("user-agent"),
                     metadata={"rows": len(rows), "filters": applied})
    await db.commit()

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit-log.csv"},
    )


@router.get("/audit")
async def list_audit(
    q: str | None = None,
    event: str | None = None,
    category: str | None = None,
    actor_id: str | None = None,
    project_id: str | None = None,
    app_key: str | None = None,
    correlation_id: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(require_audit),
    db: AsyncSession = Depends(get_db),
):
    limit = min(max(limit, 1), 100)
    offset = max(offset, 0)
    stmt = await _filtered(db, q=q, event=event, category=category, actor_id=actor_id,
                           project_id=project_id, app_key=app_key, correlation_id=correlation_id,
                           start=start, end=end)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await db.execute(
        stmt.order_by(AuditEvent.ts.desc(), AuditEvent.id.desc()).limit(limit).offset(offset)
    )).scalars().all()
    actors = await _resolve_actors(db, rows)
    items = [_serialize(r, actors) for r in rows]
    return ok(items, meta={"total": total, "limit": limit, "offset": offset})
