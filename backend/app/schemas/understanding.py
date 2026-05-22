from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from typing import Annotated


class InterviewMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: str  # ai|user|question|understanding
    content: str
    citations: list = []
    seq: int
    created_at: datetime


class RequirementUnderstandingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    objective: str | None
    content_json: dict = {}
    field_confidence: dict = {}
    status: str
    version_number: int
    validated_at: datetime | None
    validated_by: UUID | None
    created_at: datetime
    updated_at: datetime


class UnderstandingDetail(BaseModel):
    """RU + interview transcript for the interview screen."""
    understanding: RequirementUnderstandingRead
    messages: list[InterviewMessageRead] = []


class AnswerIn(BaseModel):
    seq: int | None = None  # which question is being answered (optional)
    answer: Annotated[str, Field(min_length=1, max_length=4000)]


class ValidateResult(BaseModel):
    ru_validated: bool
    understanding: RequirementUnderstandingRead
