"""Standalone Project Context Bundle subsystem.

Used by every AI-generation module (BRD, FRS, …) to guarantee full corpus
coverage before generation: App Brain, project document PageIndex outlines,
and the validated Concept Brief — assembled once, projected per-unit.
"""
from app.services.context.project_context import (
    AppFactEntry,
    AppLayer,
    BundleReadiness,
    CbLayer,
    DocInventoryEntry,
    DocsLayer,
    ProjectContextBundle,
    gather_project_context,
)
from app.services.context.projection import UnitContext, project_for_unit
from app.services.context.coverage import (
    BRD_CONTEXT_PROJECTION,
    CoverageReport,
    compute_coverage,
)

__all__ = [
    "AppFactEntry",
    "AppLayer",
    "BundleReadiness",
    "CbLayer",
    "DocInventoryEntry",
    "DocsLayer",
    "ProjectContextBundle",
    "gather_project_context",
    "UnitContext",
    "project_for_unit",
    "BRD_CONTEXT_PROJECTION",
    "CoverageReport",
    "compute_coverage",
]
