"""Markdown export for SDLC artifact documents (Concept Brief)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import (
    ArtifactDocument, CbCapability, CbContextMap, CbGateCriterion,
    CbMetric, CbMilestone, CbOutcome, CbScopeItem, CbTextBlock,
)
from app.models.project import Project


async def export_concept_brief(project_id: uuid.UUID, db: AsyncSession) -> str:
    """Reconstruct the Concept Brief template exactly as markdown."""
    project = await db.get(Project, project_id)
    if project is None:
        raise ValueError("Project not found")

    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == "concept_brief",
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        raise ValueError("Concept Brief not found")

    slug = project.name.lower().replace(" ", "-")[:40]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    async def _text(field_key: str) -> str:
        row = (
            await db.execute(
                select(CbTextBlock).where(
                    CbTextBlock.document_id == doc.id,
                    CbTextBlock.row_key == field_key,
                    CbTextBlock.is_current.is_(True),
                    CbTextBlock.status == "active",
                )
            )
        ).scalar_one_or_none()
        return row.text if row else "—"

    async def _rows(model):
        return (
            await db.execute(
                select(model).where(
                    model.document_id == doc.id,
                    model.is_current.is_(True),
                    model.status == "active",
                ).order_by(model.row_key)
            )
        ).scalars().all()

    # ── Frontmatter ──────────────────────────────────────────────────────────
    lines = [
        "---",
        f"title: {project.name} – Concept Brief",
        f"artefactId: concept-{slug}",
        "artefactType: concept-brief",
        "generatorSkill: concept-brief-builder",
        f"generatedAt: {now}",
        "---",
        "",
        f"# {project.name} — Concept Brief",
        "",
    ]

    # ── Document Control ──────────────────────────────────────────────────────
    lines += [
        "## Document Control",
        "",
        "| Version | Date | Author | Summary | Approved By |",
        "|---------|------|--------|---------|-------------|",
    ]
    if doc.validated_at:
        validated_date = doc.validated_at.strftime("%Y-%m-%d")
        lines.append(f"| 1.0 | {validated_date} | System | Initial validated concept brief | — |")
    else:
        lines.append(f"| 0.1 | {now} | System | Draft | — |")
    lines.append("")

    # ── Section 1: Problem Statement & Context Map ────────────────────────────
    lines += [
        "## 1. Problem Statement & Context Map",
        "",
        "### Business Context",
        "",
        await _text("business_context"),
        "",
        "### Problem Statement",
        "",
        await _text("problem_statement"),
        "",
        "### Context Map",
        "",
        "| Dimension | Detail |",
        "|-----------|--------|",
    ]
    ctx_map = await _rows(CbContextMap)
    for r in ctx_map:
        lines.append(f"| {r.dimension} | {r.detail} |")
    lines.append("")

    # ── Section 2: Value Hypothesis & Expected Outcomes ───────────────────────
    lines += [
        "## 2. Value Hypothesis & Expected Outcomes",
        "",
        "### Value Hypothesis",
        "",
        f"**If** {await _text('value_hypothesis_if')}",
        "",
        f"**then** {await _text('value_hypothesis_then')}",
        "",
        "### Expected Outcomes",
        "",
        "| Outcome | Description |",
        "|---------|-------------|",
    ]
    for r in await _rows(CbOutcome):
        lines.append(f"| {r.outcome} | {r.description} |")
    lines.append("")

    # ── Section 3: Success Metrics ────────────────────────────────────────────
    lines += [
        "### Success Metrics",
        "",
        "| Metric | Description | Quantifiable |",
        "|--------|-------------|:------------:|",
    ]
    for r in await _rows(CbMetric):
        q = "✓" if r.quantifiable else ""
        lines.append(f"| {r.metric} | {r.description} | {q} |")
    lines.append("")

    # ── Section 4: Proposed Capabilities ─────────────────────────────────────
    lines += [
        "## 3. Proposed Capabilities",
        "",
        "| Capability | Description |",
        "|------------|-------------|",
    ]
    for r in await _rows(CbCapability):
        lines.append(f"| {r.capability} | {r.description} |")
    lines.append("")

    # ── Section 5: Scope Boundaries & Assumptions ─────────────────────────────
    scope_rows = await _rows(CbScopeItem)
    in_scope = [r for r in scope_rows if r.kind == "in_scope"]
    out_scope = [r for r in scope_rows if r.kind == "out_of_scope"]
    assumptions = [r for r in scope_rows if r.kind == "assumption"]

    lines += ["## 4. Scope Boundaries & Assumptions", "", "### In Scope", ""]
    for r in in_scope:
        lines.append(f"- {r.text}")
    lines += ["", "### Out of Scope", ""]
    for r in out_scope:
        lines.append(f"- {r.text}")
    lines += ["", "### Assumptions", ""]
    for r in assumptions:
        lines.append(f"- {r.text}")
    lines.append("")

    # ── Section 6: Delivery Approach ─────────────────────────────────────────
    lines += [
        "## 5. Delivery Approach",
        "",
        "| Milestone | Target | Description |",
        "|-----------|--------|-------------|",
    ]
    for r in await _rows(CbMilestone):
        lines.append(f"| {r.milestone} | {r.target} | {r.description} |")
    lines.append("")

    # ── Section 7: Approval Gate ─────────────────────────────────────────────
    lines += [
        "## 6. Approval Gate",
        "",
        "| Criterion | Status | Notes |",
        "|-----------|--------|-------|",
    ]
    for r in await _rows(CbGateCriterion):
        lines.append(f"| {r.criterion} | {r.gate_status} | {r.notes} |")
    lines.append("")

    return "\n".join(lines)
