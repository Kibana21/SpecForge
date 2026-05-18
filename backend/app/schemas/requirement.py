from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ExtractedRequirementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    category: str
    ext_id: str
    text: str
    source_reference: str | None
    confidence: str
