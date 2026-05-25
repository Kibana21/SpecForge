"""Pydantic schemas for artifact API."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel


class ArtifactDocumentRead(BaseModel):
    id: UUID
    project_id: UUID
    artifact_type: str
    status: str
    unit_status: dict[str, Any] = {}
    validated_at: str | None = None
    validated_by: str | None = None
    created_at: str
    updated_at: str


class ArtifactMessageRead(BaseModel):
    id: str
    document_id: str
    role: str
    content: str
    citations: list = []
    meta: dict = {}
    seq: int
    created_at: str


class ArtifactSourceRead(BaseModel):
    id: str
    source_document_id: str
    filename: str
    parse_status: str
    included: bool


class CbRowRead(BaseModel):
    id: str
    document_id: str
    row_key: str
    version: int
    is_current: bool
    is_locked: bool
    status: str
    source: str
    created_by: str | None = None
    created_at: str


class RowEditIn(BaseModel):
    fields: dict[str, Any]
    lock: bool = True


class RowRestoreIn(BaseModel):
    version: int


class UnitRegenerateIn(BaseModel):
    directive: str | None = None


class AnswerIn(BaseModel):
    answer: str
    seq: int | None = None


class SourceToggleIn(BaseModel):
    included: bool


class ArtifactDetailResponse(BaseModel):
    document: ArtifactDocumentRead | None
    sections: dict[str, list[dict]] = {}
    messages: list[ArtifactMessageRead] = []
    sources: list[ArtifactSourceRead] = []


class ValidationResponse(BaseModel):
    ok: bool
    failures: list[str] = []
