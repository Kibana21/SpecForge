from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ReviewCommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    spec_version_id: UUID | None
    section: str
    comment: str
    severity: str
    category: str
    dismissed: bool
    dismissed_at: datetime | None
    created_at: datetime


class ReviewDismissPatch(BaseModel):
    dismissed: bool
