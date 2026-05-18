from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class GapQuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    ext_id: str
    question: str
    category: str
    severity: str
    resolved: bool
    resolution_text: str | None
    resolved_at: datetime | None
    created_at: datetime


class GapResolvePatch(BaseModel):
    resolved: bool
    resolution_text: str | None = None
