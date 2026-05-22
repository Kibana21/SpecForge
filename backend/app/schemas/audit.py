from datetime import datetime

from pydantic import BaseModel


class AuditEventRead(BaseModel):
    id: int
    ts: datetime
    event: str
    label: str
    category: str
    severity: str
    actor_id: str | None = None
    actor_name: str | None = None
    actor_email: str | None = None
    actor_role: str | None = None
    action: str | None = None
    project_id: str | None = None
    document_key: str | None = None
    app_key: str | None = None
    ip: str | None = None
    user_agent: str | None = None
    correlation_id: str | None = None
    metadata: dict | None = None
    affected_sections: dict | None = None


class AuditSummary(BaseModel):
    events_today: int
    failed_logins_24h: int
    lockouts_24h: int
    token_reuse_7d: int
    deletions_7d: int
    ai_actions_today: int
