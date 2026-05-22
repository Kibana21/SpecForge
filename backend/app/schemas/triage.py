from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TriageItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID | None
    kind: str  # stale_impact|review|approval|low_confidence|open_assumption
    priority: int
    title: str
    link: str
    computed_at: datetime
    next_at: datetime | None
