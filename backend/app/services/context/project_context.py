"""Project Context Bundle: the full corpus snapshot fed to every generation module."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


# ── App layer ──────────────────────────────────────────────────────────────────

@dataclass
class AppFactEntry:
    app_id: str
    app_name: str
    tier: int
    domain_area: str | None
    impact_note: str | None
    facts_by_kind: dict[str, list[str]]
    wiki_concepts: list[str]


@dataclass
class AppLayer:
    entries: list[AppFactEntry]
    total_facts: int
    formatted_context: str  # ready-to-inject block for prompts


# ── Docs layer ─────────────────────────────────────────────────────────────────

@dataclass
class DocInventoryEntry:
    doc_id: str
    filename: str
    parse_status: str           # pending | done | error
    indexing_status: str        # pending | running | done | error
    node_count: int
    has_tree: bool
    included: bool
    page_count: int | None = None


@dataclass
class DocsLayer:
    inventory: list[DocInventoryEntry]
    ready_count: int
    pending_count: int
    failed_count: int
    total_count: int
    outline_text: str           # breadth: per-doc PageIndex outline for prompts
    # depth search (tree_search) is done per-unit at generation time


# ── CB layer ───────────────────────────────────────────────────────────────────

@dataclass
class CbLayer:
    cb_document_id: str | None
    cb_status: str | None           # in_interview | validated | …
    cb_validated_at: str | None
    cb_snapshot_key: str | None
    # All current, active rows keyed by table name
    text_blocks: list[dict]         # cb_text_blocks rows
    context_map: list[dict]         # cb_context_map rows
    outcomes: list[dict]            # cb_outcomes rows
    metrics: list[dict]             # cb_metrics rows
    capabilities: list[dict]        # cb_capabilities rows
    scope_items: list[dict]         # cb_scope_items rows
    milestones: list[dict]          # cb_milestones rows
    enhanced_brief: str | None      # latest CbDiscoverEnhancedBrief.enhanced_brief
    discover_qa: str                # formatted Q&A context string
    formatted_context: str          # full CB projection block for prompts


# ── Readiness ─────────────────────────────────────────────────────────────────

@dataclass
class BundleReadiness:
    apps_ready: bool
    docs_all_ready: bool
    docs_ready_count: int
    docs_total_count: int
    docs_pending_names: list[str]
    docs_failed_names: list[str]
    cb_ready: bool          # True when cb_status == "validated"
    cb_status: str | None
    can_generate: bool
    blocking_reason: str | None


# ── The Bundle ────────────────────────────────────────────────────────────────

@dataclass
class ProjectContextBundle:
    project_id: str
    project_name: str
    business_unit: str
    apps: AppLayer
    docs: DocsLayer
    cb: CbLayer
    readiness: BundleReadiness
    snapshot_timestamp: str     # ISO-8601 when the bundle was assembled


# ── Main entry point ──────────────────────────────────────────────────────────

async def gather_project_context(
    project_id: uuid.UUID,
    db: AsyncSession,
    *,
    artifact_document_id: uuid.UUID | None = None,
) -> ProjectContextBundle:
    """Assemble the full corpus context for a project.

    Gathers the three layers in parallel (app facts, doc inventory + outlines,
    validated CB rows + discover Q&A) and computes overall readiness.

    artifact_document_id: when provided, uses this ArtifactDocument's source list
    to determine which docs are included. Falls back to all project docs when None.
    """
    from app.models.project import Project
    from sqlalchemy import select

    project = await db.get(Project, project_id)
    if project is None:
        raise ValueError(f"Project {project_id} not found")

    import asyncio
    from app.services.context.app_layer import build_app_layer
    from app.services.context.docs_layer import build_docs_layer
    from app.services.context.cb_layer import build_cb_layer

    apps_layer, docs_layer, cb_layer = await asyncio.gather(
        build_app_layer(project_id, db),
        build_docs_layer(project_id, db, artifact_document_id=artifact_document_id),
        build_cb_layer(project_id, db),
    )

    readiness = _compute_readiness(apps_layer, docs_layer, cb_layer)

    return ProjectContextBundle(
        project_id=str(project_id),
        project_name=project.name,
        business_unit=project.business_unit or "—",
        apps=apps_layer,
        docs=docs_layer,
        cb=cb_layer,
        readiness=readiness,
        snapshot_timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _compute_readiness(
    apps: AppLayer,
    docs: DocsLayer,
    cb: CbLayer,
) -> BundleReadiness:
    docs_all_ready = docs.pending_count == 0 and docs.failed_count == 0
    cb_ready = cb.cb_status == "validated"

    blocking: str | None = None
    if docs.pending_count > 0:
        blocking = f"{docs.pending_count} document(s) still indexing"
    elif docs.failed_count > 0:
        blocking = f"{docs.failed_count} document(s) failed indexing"
    elif not cb_ready:
        blocking = f"Concept Brief not yet validated (status: {cb.cb_status or 'not started'})"

    return BundleReadiness(
        apps_ready=True,  # App Brain is always available (may be empty)
        docs_all_ready=docs_all_ready,
        docs_ready_count=docs.ready_count,
        docs_total_count=docs.total_count,
        docs_pending_names=[e.filename for e in docs.inventory if e.indexing_status in ("pending", "running")],
        docs_failed_names=[e.filename for e in docs.inventory if e.indexing_status == "error"],
        cb_ready=cb_ready,
        cb_status=cb.cb_status,
        can_generate=(docs_all_ready and cb_ready),
        blocking_reason=blocking,
    )
