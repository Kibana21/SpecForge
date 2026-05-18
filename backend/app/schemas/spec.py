from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SpecVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    spec_type: str
    version_number: int
    content_json: Any
    content_markdown: str | None
    is_edited: bool
    created_at: datetime
    updated_at: datetime


class SpecPatch(BaseModel):
    content_markdown: str | None = None
    content_json: Any = None
