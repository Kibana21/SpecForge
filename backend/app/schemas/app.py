import re
import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


def _validate_short_name(v: str) -> str:
    v = v.strip()
    if not re.match(r"^[a-z0-9-]{1,50}$", v):
        raise ValueError("short_name must match ^[a-z0-9-]{1,50}$")
    return v


class AppCreate(BaseModel):
    name: Annotated[str, AfterValidator(lambda v: v.strip())] = Field(min_length=1)
    short_name: Annotated[str, AfterValidator(_validate_short_name)]
    description: str | None = None
    tier: Annotated[int, Field(ge=1, le=3)]
    domain_area: str | None = None
    version: str | None = None
    owner_team: str | None = None
    environments: list[str] = []


class AppUpdate(BaseModel):
    """Partial metadata update — only provided fields change. short_name is immutable."""
    name: str | None = None
    description: str | None = None
    tier: int | None = Field(default=None, ge=1, le=3)
    domain_area: str | None = None
    version: str | None = None
    owner_team: str | None = None
    environments: list[str] | None = None


class AppCorpusDocRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    app_id: uuid.UUID
    name: str
    page_count: int | None
    is_primary: bool
    index_status: str
    indexed_at: datetime | None
    created_at: datetime


class AppFactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    app_id: uuid.UUID
    doc_id: uuid.UUID | None = None
    kind: str
    text: str
    source_ref: str | None
    confidence: str
    status: str
    source: str
    chunk_ids: list
    source_fact_ids: list = []
    created_at: datetime
    updated_at: datetime


class FactCreate(BaseModel):
    kind: str
    text: str
    confidence: str = "high"
    source_ref: str | None = None


class FactUpdate(BaseModel):
    kind: str | None = None
    text: str | None = None
    confidence: str | None = None
    source_ref: str | None = None
    status: str | None = None


class PipelineSummary(BaseModel):
    total_docs: int
    indexed_docs: int
    pending_docs: int
    total_chunks: int
    total_facts: int
    last_indexed_at: datetime | None


class AppListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    short_name: str
    description: str | None
    tier: int
    domain_area: str | None
    is_onboarded: bool
    version: str | None
    owner_id: uuid.UUID | None
    owner_team: str | None = None
    environments: list[str] = []
    corpus_doc_count: int = 0
    indexed_doc_count: int = 0
    fact_count: int = 0
    live_project_count: int = 0
    open_qs: int = 0
    created_at: datetime
    updated_at: datetime


class AppDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    short_name: str
    description: str | None
    tier: int
    domain_area: str | None
    is_onboarded: bool
    version: str | None
    owner_id: uuid.UUID | None
    owner_team: str | None = None
    environments: list[str] = []
    corpus_docs: list[AppCorpusDocRead]
    pipeline_summary: PipelineSummary
    brain_context_synthesized_at: datetime | None = None
    brain_context_status: str = "idle"
    created_at: datetime
    updated_at: datetime


class BrainContextResponse(BaseModel):
    facts: list[AppFactRead]
    synthesized_at: datetime | None
    status: str
    source_doc_count: int


class AskRequest(BaseModel):
    question: Annotated[str, Field(min_length=1, max_length=1000)]
    top_k: Annotated[int, Field(default=8, ge=1, le=20)] = 8
