"""NFR validation checklist (SKILL Phase-6 gate): run_nfr_validation returns findings.

Severity groups mirror the BRD/FRS validators: critical & major BLOCK validation;
minor & warnings are informational.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import ArtifactDocument
from app.models.nfr import NfrRequirement, NfrTraceability
from app.services.artifacts.manifest.nfr import NFR_CATEGORY_UNITS

_GROUP_ORDER = {"critical": 0, "major": 1, "minor": 2, "warnings": 3}


def _finding(check_id: str, description: str, group: str,
             row_key: str | None = None, suggested_fix: str = "") -> dict:
    return {
        "check_id": check_id,
        "description": description,
        "group": group,
        "row_key": row_key,
        "suggested_fix": suggested_fix,
    }


async def _active(model: type, document_id: uuid.UUID, db: AsyncSession) -> list[Any]:
    return (
        await db.execute(
            select(model).where(
                model.document_id == document_id,
                model.is_current.is_(True),
                model.status == "active",
            )
        )
    ).scalars().all()


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())


async def run_nfr_validation(
    document_id: uuid.UUID, doc: ArtifactDocument, db: AsyncSession
) -> list[dict]:
    findings: list[dict] = []

    reqs = await _active(NfrRequirement, document_id, db)

    # ── 1. brd_prerequisite (critical) ──────────────────────────────────────────
    brd = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == doc.project_id,
                ArtifactDocument.artifact_type == "brd",
            )
        )
    ).scalar_one_or_none()
    if brd is None or brd.status != "validated":
        findings.append(_finding(
            "brd_prerequisite",
            "NFRs must be derived from a validated BRD; no validated BRD found.",
            "critical",
            suggested_fix="Validate the BRD before validating the NFR document.",
        ))

    # ── 2. valid_moscow (critical) ──────────────────────────────────────────────
    valid_pri = {"must", "should", "could", "wont"}
    for r in reqs:
        if r.priority not in valid_pri:
            findings.append(_finding(
                "valid_moscow",
                f"{r.row_key} has an invalid MoSCoW priority '{r.priority}'.",
                "critical", row_key=r.row_key,
                suggested_fix="Set priority to one of: Must / Should / Could / Won't.",
            ))

    # ── 3. all_categories_covered (major) ───────────────────────────────────────
    cats_present = {r.category for r in reqs}
    for cat in NFR_CATEGORY_UNITS:
        if cat not in cats_present:
            findings.append(_finding(
                "all_categories_covered",
                f"Category '{cat}' has no requirements and is not marked N/A.",
                "major",
                suggested_fix=f"Generate or add at least one {cat} NFR, or add an explicit N/A row.",
            ))

    # ── 4. sequential_numbering (major) ─────────────────────────────────────────
    nums = []
    for r in reqs:
        if r.row_key.startswith("NFR-"):
            tail = r.row_key[4:]
            if tail.isdigit():
                nums.append(int(tail))
    if nums:
        nums_sorted = sorted(nums)
        if len(nums_sorted) != len(set(nums_sorted)):
            findings.append(_finding(
                "sequential_numbering",
                "Duplicate NFR numbers detected.",
                "major", suggested_fix="Renumber so every NFR-nnn is unique.",
            ))
        expected = list(range(1, len(nums_sorted) + 1))
        if nums_sorted != expected:
            findings.append(_finding(
                "sequential_numbering",
                f"NFR numbering has gaps (found {nums_sorted}, expected 1..{len(nums_sorted)}).",
                "major", suggested_fix="Renumber NFRs to be sequential with no gaps.",
            ))

    # ── 5. traceability_present (major) ─────────────────────────────────────────
    traces = (
        await db.execute(
            select(NfrTraceability.source_row_key).where(NfrTraceability.document_id == document_id)
        )
    ).scalars().all()
    traced_keys = set(traces)
    for r in reqs:
        if not r.na and r.row_key not in traced_keys:
            findings.append(_finding(
                "traceability_present",
                f"{r.row_key} does not trace to any BRD objective/requirement.",
                "major", row_key=r.row_key,
                suggested_fix="Link this NFR to ≥1 BRD objective or business requirement.",
            ))

    # ── 6. testable_statements (minor) ──────────────────────────────────────────
    for r in reqs:
        if not r.na and not (r.measurement or "").strip():
            findings.append(_finding(
                "testable_statements",
                f"{r.row_key} has no measurement — it may not be testable.",
                "minor", row_key=r.row_key,
                suggested_fix="Add a metric + threshold (e.g. 'p95 < 300ms @ 200 users').",
            ))

    # ── 7. no_duplicate_overlap (minor) ─────────────────────────────────────────
    seen: dict[str, str] = {}
    for r in reqs:
        key = _norm(r.requirement)
        if key and key in seen:
            findings.append(_finding(
                "no_duplicate_overlap",
                f"{r.row_key} duplicates/overlaps {seen[key]} (near-identical requirement text).",
                "minor", row_key=r.row_key,
                suggested_fix="Merge the overlapping NFRs or differentiate them.",
            ))
        elif key:
            seen[key] = r.row_key

    findings.sort(key=lambda f: _GROUP_ORDER.get(f["group"], 99))
    return findings
