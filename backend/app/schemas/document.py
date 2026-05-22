from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    filename: str
    mime_type: str
    size_bytes: int
    parse_status: str
    parse_error: str | None
    indexing_status: str = "pending"
    index_error: str | None = None
    page_count: int | None = None
    created_at: datetime
    updated_at: datetime
