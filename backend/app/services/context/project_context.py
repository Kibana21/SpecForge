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


# ── BRD layer (populated when artifact_type=='frs') ───────────────────────────

@dataclass
class BrdLayer:
    """All validated BRD rows + discover Q&A; ready for FRS prompt injection."""
    brd_document_id: str | None
    brd_status: str | None           # in_interview | validated | None
    brd_validated_at: str | None
    brd_snapshot_key: str | None
    # All current, active rows keyed by table
    text_blocks: list[dict]          # brd_text_blocks (business_context, problem_statement, …)
    objectives: list[dict]           # brd_objectives
    stakeholders: list[dict]
    actors: list[dict]
    scope_items: list[dict]
    process_steps: list[dict]        # asis + tobe combined
    business_requirements: list[dict]  # KEYSTONE
    data_entities: list[dict]
    report_requirements: list[dict]
    assumptions: list[dict]
    constraints: list[dict]
    dependencies: list[dict]
    risks: list[dict]
    phases: list[dict]
    milestones: list[dict]
    kpis: list[dict]
    open_questions: list[dict]
    decisions: list[dict]
    references: list[dict]
    glossary_entries: list[dict]
    traceability: list[dict]         # all BrdTraceability rows for outward refs
    formatted_context: str           # full BRD projection block for prompts


# ── FRS layer (populated when artifact_type=='test_cases') ────────────────────

@dataclass
class FrsLayer:
    """All validated FRS rows + traceability; ready for Test-Case prompt injection.

    Loaded for test-case generation. Test cases trace into FRS specs / acceptance
    scenarios / functional requirements / business rules / screens, and roll up
    transitively to BRD business requirements via the FRS→BR traceability rows.
    """
    frs_document_id: str | None
    frs_status: str | None           # in_interview | validated | None
    frs_validated_at: str | None
    frs_snapshot_key: str | None
    # All current, active rows keyed by table
    modules: list[dict]
    specs: list[dict]                # KEYSTONE — full spec text + sub-section prose
    acceptance_scenarios: list[dict]
    functional_requirements: list[dict]
    business_rules: list[dict]
    screens: list[dict]
    ui_components: list[dict]
    endpoints: list[dict]
    data_entities: list[dict]
    module_actors: list[dict]
    traceability: list[dict]         # all FrsTraceability rows (incl. FRS→BR)
    formatted_context: str           # full FRS projection block for prompts


# ── NFR layer (loaded for FRS/test_cases so validated NFRs can feed FRS) ──────

@dataclass
class NfrLayer:
    """All validated NFR rows + traceability; ready for FRS prompt injection.

    Loaded (optionally, may be empty) for FRS + test_cases generation so validated
    NFRs can softly drive FRS design. NFR is NEVER a hard gate on FRS.
    """
    nfr_document_id: str | None
    nfr_status: str | None           # in_interview | validated | None
    nfr_validated_at: str | None
    nfr_snapshot_key: str | None
    requirements: list[dict]
    risks: list[dict]
    tradeoffs: list[dict]
    open_questions: list[dict]
    decisions: list[dict]
    references: list[dict]
    glossary: list[dict]
    text_blocks: list[dict]
    traceability: list[dict]
    formatted_context: str


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
    brd_ready: bool         # True for non-FRS artifacts; or when brd_status == "validated"
    brd_status: str | None
    frs_ready: bool         # True unless artifact_type=='test_cases'; else frs_status=='validated'
    frs_status: str | None
    nfr_ready: bool         # tracked for frs/test_cases (informational — NEVER blocks)
    nfr_status: str | None
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
    brd: BrdLayer | None            # populated when artifact_type in ('frs', 'test_cases', 'nfr')
    frs: "FrsLayer | None"          # populated only when artifact_type == 'test_cases'
    nfr: "NfrLayer | None"          # populated for frs/test_cases (soft NFR-driver feed)
    intake: "IntakeLayer"           # validated RU + resolved clarifications + wiki concepts
    readiness: BundleReadiness
    snapshot_timestamp: str     # ISO-8601 when the bundle was assembled


# ── Main entry point ──────────────────────────────────────────────────────────

async def gather_project_context(
    project_id: uuid.UUID,
    db: AsyncSession,
    *,
    artifact_document_id: uuid.UUID | None = None,
    artifact_type: str = "brd",
) -> ProjectContextBundle:
    """Assemble the full corpus context for a project.

    Gathers the three core layers in parallel (app facts, doc inventory + outlines,
    validated CB rows + discover Q&A) and — when artifact_type=='frs' — also loads
    the BRD layer. Computes overall readiness.

    artifact_document_id: when provided, uses this ArtifactDocument's source list
    to determine which docs are included. Falls back to all project docs when None.
    artifact_type: 'brd' (default) or 'frs'. FRS additionally requires the BRD to
    be validated; the readiness check enforces this.
    """
    from app.models.project import Project

    project = await db.get(Project, project_id)
    if project is None:
        raise ValueError(f"Project {project_id} not found")

    from app.services.context.app_layer import build_app_layer
    from app.services.context.docs_layer import build_docs_layer
    from app.services.context.cb_layer import build_cb_layer

    # Layers are built sequentially on a single session. asyncio.gather on the
    # same session can trip async-SQLAlchemy's "concurrent operations not
    # permitted" guard when the session has prior uncommitted/lazy state. The
    # cost is small (each layer is a handful of queries) and correctness wins.
    from app.services.context.intake_layer import build_intake_layer

    apps_layer = await build_app_layer(project_id, db)
    docs_layer = await build_docs_layer(project_id, db, artifact_document_id=artifact_document_id)
    cb_layer = await build_cb_layer(project_id, db)
    intake_layer = await build_intake_layer(project_id, db)

    brd_layer: BrdLayer | None = None
    # NFR is generated from the same corpus as FRS (apps + docs + validated CB + BRD),
    # so it also loads the BRD layer (and gates on a validated BRD via readiness).
    if artifact_type in ("frs", "test_cases", "nfr"):
        from app.services.context.brd_layer import build_brd_layer
        brd_layer = await build_brd_layer(project_id, db)

    frs_layer: "FrsLayer | None" = None
    if artifact_type == "test_cases":
        from app.services.context.frs_layer import build_frs_layer
        frs_layer = await build_frs_layer(project_id, db)

    # FRS/test_cases additionally load the (possibly empty) NFR layer so validated
    # NFRs can softly drive FRS design. This is purely additive — see projection.py.
    nfr_layer: "NfrLayer | None" = None
    if artifact_type in ("frs", "test_cases"):
        from app.services.context.nfr_layer import build_nfr_layer
        nfr_layer = await build_nfr_layer(project_id, db)

    readiness = _compute_readiness(
        apps_layer, docs_layer, cb_layer, brd_layer, frs_layer, nfr_layer,
        artifact_type=artifact_type,
    )

    return ProjectContextBundle(
        project_id=str(project_id),
        project_name=project.name,
        business_unit=project.business_unit or "—",
        apps=apps_layer,
        docs=docs_layer,
        cb=cb_layer,
        brd=brd_layer,
        frs=frs_layer,
        nfr=nfr_layer,
        intake=intake_layer,
        readiness=readiness,
        snapshot_timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _compute_readiness(
    apps: AppLayer,
    docs: DocsLayer,
    cb: CbLayer,
    brd: BrdLayer | None,
    frs: "FrsLayer | None" = None,
    nfr: "NfrLayer | None" = None,
    *,
    artifact_type: str = "brd",
) -> BundleReadiness:
    docs_all_ready = docs.pending_count == 0 and docs.failed_count == 0
    cb_ready = cb.cb_status == "validated"
    # The BRD gate applies to FRS + test_cases + nfr (all need a validated BRD).
    brd_ready = (artifact_type not in ("frs", "test_cases", "nfr")) or (brd is not None and brd.brd_status == "validated")
    # The FRS gate applies only to test_cases (needs a validated FRS).
    frs_ready = (artifact_type != "test_cases") or (frs is not None and frs.frs_status == "validated")
    # NFR is a SOFT input to FRS — tracked but NEVER part of the blocking gate.
    nfr_ready = (artifact_type not in ("frs", "test_cases")) or (nfr is not None and nfr.nfr_status == "validated")

    blocking: str | None = None
    if docs.pending_count > 0:
        blocking = f"{docs.pending_count} document(s) still indexing"
    elif docs.failed_count > 0:
        blocking = f"{docs.failed_count} document(s) failed indexing"
    elif not cb_ready:
        blocking = f"Concept Brief not yet validated (status: {cb.cb_status or 'not started'})"
    elif not brd_ready:
        brd_status_str = brd.brd_status if brd else "not started"
        blocking = f"BRD not yet validated (status: {brd_status_str})"
    elif not frs_ready:
        frs_status_str = frs.frs_status if frs else "not started"
        blocking = f"FRS not yet validated (status: {frs_status_str})"

    return BundleReadiness(
        apps_ready=True,  # App Brain is always available (may be empty)
        docs_all_ready=docs_all_ready,
        docs_ready_count=docs.ready_count,
        docs_total_count=docs.total_count,
        docs_pending_names=[e.filename for e in docs.inventory if e.indexing_status in ("pending", "running")],
        docs_failed_names=[e.filename for e in docs.inventory if e.indexing_status == "error"],
        cb_ready=cb_ready,
        cb_status=cb.cb_status,
        brd_ready=brd_ready,
        brd_status=brd.brd_status if brd else None,
        frs_ready=frs_ready,
        frs_status=frs.frs_status if frs else None,
        nfr_ready=nfr_ready,
        nfr_status=nfr.nfr_status if nfr else None,
        can_generate=(docs_all_ready and cb_ready and brd_ready and frs_ready),
        blocking_reason=blocking,
    )
