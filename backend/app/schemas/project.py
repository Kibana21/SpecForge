from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class ReuseSelectionIn(BaseModel):
    source_project_id: UUID
    asset_category: str  # template|requirements|nfr|glossary


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    # E2 wizard fields (optional here; the wizard endpoint enforces required ones)
    business_unit: str | None = None
    app_scope: str | None = None
    app_ids: list[UUID] = []
    reuse: list[ReuseSelectionIn] = []
    document_ids: list[UUID] = []

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Project name cannot be empty")
        return v.strip()


class AppScopeEntry(BaseModel):
    app_id: UUID
    impact_note: str | None = None


class ProjectUpdate(BaseModel):
    """Partial project-metadata update — only provided fields change."""
    name: str | None = None
    description: str | None = None
    business_unit: str | None = None
    app_scope: str | None = None
    priority: str | None = None
    status: str | None = None
    go_live_date: date | None = None
    app_scope_entries: list[AppScopeEntry] | None = None  # replaces ProjectApp rows when provided


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    owner_id: UUID | None = None
    human_id: str | None = None
    business_unit: str | None = None
    app_scope: str | None = None
    status: str = "draft"
    priority: str = "medium"
    completion_pct: int = 0
    go_live_date: date | None = None
    stage_progress: dict = {}
    ru_validated: bool = False
    created_at: datetime
    updated_at: datetime


class ProjectListItem(ProjectRead):
    doc_count: int = 0
    latest_spec_type: str | None = None
    open_review_count: int = 0
    is_stale: bool = False


class SavedViewCount(BaseModel):
    view: str
    label: str
    count: int


class ProjectDetail(ProjectRead):
    documents: list = []
    apps_in_scope: list = []
    gap_count: int = 0
    unresolved_gap_count: int = 0
    latest_specs: dict = {}
    # E2 workspace panels (populated in Phase 6)
    quality: dict = {}
    open_questions: list = []
    assumptions: list = []
    recent_activity: list = []
    skill_versions: list = []
    ru_status: str | None = None
    docs_stale_for_ru: bool = False
