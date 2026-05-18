from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Project name cannot be empty")
        return v.strip()


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class ProjectListItem(ProjectRead):
    doc_count: int = 0
    latest_spec_type: str | None = None


class ProjectDetail(ProjectRead):
    documents: list = []
    gap_count: int = 0
    unresolved_gap_count: int = 0
    latest_specs: dict = {}
