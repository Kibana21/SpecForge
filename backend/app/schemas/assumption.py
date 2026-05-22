from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AssumptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    ext_id: str
    text: str
    confidence: str
    source_ref: str | None
    status: str  # open|confirmed|rejected
    created_at: datetime
    updated_at: datetime


class AssumptionPatch(BaseModel):
    status: str  # open|confirmed|rejected
