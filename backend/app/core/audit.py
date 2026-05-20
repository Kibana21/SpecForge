import hashlib

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent


async def emit(
    db: AsyncSession,
    *,
    event: str,
    actor_id: str | None = None,
    email: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    correlation_id: str | None = None,
    project_id: str | None = None,
    document_key: str | None = None,
    action: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Append an audit event. Caller is responsible for committing the session."""
    entry = AuditEvent(
        event=event,
        actor_id=actor_id,
        email_hash=hashlib.sha256(email.encode()).hexdigest() if email else None,
        project_id=project_id,
        document_key=document_key,
        action=action,
        ip=ip,
        user_agent=user_agent[:255] if user_agent else None,
        correlation_id=correlation_id,
        ai_meta=metadata,
    )
    db.add(entry)
