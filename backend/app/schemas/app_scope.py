from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AppSuggestion(BaseModel):
    """An onboarded app offered for apps-in-scope, with an AI-suggestion flag."""
    id: UUID
    name: str
    short_name: str
    description: str | None = None
    tier: int
    domain_area: str | None = None
    version: str | None = None
    owner_id: UUID | None = None
    fact_count: int = 0
    corpus_doc_count: int = 0
    suggested: bool = False
    match_pct: int = 0


class SimilarProject(BaseModel):
    source_project_id: UUID
    name: str
    business_unit: str | None = None
    match_pct: int
    finalized_at: datetime | None = None
    asset_tags: list[str] = []


class ProjectAppRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    app_id: UUID
    suggested: bool
    included: bool
    app_brain_version: str | None = None
