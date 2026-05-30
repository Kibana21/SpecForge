"""FRS markdown export bundle.

Produces a zip with:
  README.md                                 — overview + counts + traceability summary
  modules/<NN>-<slug>.md                    — one file per module
  specs/<row_key_lower>-<slug>.md           — one file per FRS spec (12-section template)
  traceability/
    br-to-frs.md
    nfr-to-frs.md
    module-to-frs.md
    matrix.csv                              — flat dump of frs_traceability

Mirrors `reference_mds/skills/frs-builder/templates/frs-template.md`. JSONB blobs
(request_spec, response_spec, columns, etc.) are rendered as bulleted YAML-ish
trees for readability.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import re
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import ArtifactDocument
from app.models.brd import BrdBusinessRequirement
from app.models.frs import (
    FrsAcceptanceScenario, FrsBusinessRule, FrsDataEntity,
    FrsEndpoint, FrsFunctionalRequirement, FrsModule,
    FrsModuleActor, FrsModuleDataEntity, FrsModuleInterface,
    FrsModuleResponsibility, FrsScreen, FrsSpec, FrsSpecDecision,
    FrsTraceability, FrsUiComponent,
)

log = logging.getLogger(__name__)


# ─── Public entry point ──────────────────────────────────────────────────────


async def build_frs_export_zip(
    project_id: uuid.UUID,
    doc: ArtifactDocument,
    db: AsyncSession,
) -> bytes:
    """Build the FRS markdown bundle as a zip and return the raw bytes."""
    modules = await _active(FrsModule, doc.id, db)
    specs = await _active(FrsSpec, doc.id, db)
    actors = await _active(FrsModuleActor, doc.id, db)
    responsibilities = await _active(FrsModuleResponsibility, doc.id, db)
    interfaces = await _active(FrsModuleInterface, doc.id, db)
    module_entities = await _active(FrsModuleDataEntity, doc.id, db)
    screens = await _active(FrsScreen, doc.id, db)
    components = await _active(FrsUiComponent, doc.id, db)
    endpoints = await _active(FrsEndpoint, doc.id, db)
    entities = await _active(FrsDataEntity, doc.id, db)
    business_rules = await _active(FrsBusinessRule, doc.id, db)
    scenarios = await _active(FrsAcceptanceScenario, doc.id, db)
    frs_list = await _active(FrsFunctionalRequirement, doc.id, db)
    decisions = await _active(FrsSpecDecision, doc.id, db)
    traceability = (
        await db.execute(
            select(FrsTraceability).where(FrsTraceability.document_id == doc.id)
        )
    ).scalars().all()

    # BR titles (so traceability targets are human-readable)
    brd_doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == "brd",
            )
        )
    ).scalar_one_or_none()
    br_titles: dict[str, str] = {}
    if brd_doc is not None:
        br_rows = (
            await db.execute(
                select(BrdBusinessRequirement).where(
                    BrdBusinessRequirement.document_id == brd_doc.id,
                    BrdBusinessRequirement.is_current.is_(True),
                    BrdBusinessRequirement.status == "active",
                )
            )
        ).scalars().all()
        br_titles = {br.row_key: br.title for br in br_rows}

    # Index sub-rows per parent
    actors_by_mod = _group_by(actors, "module_row_key")
    resp_by_mod = _group_by(responsibilities, "module_row_key")
    iface_by_mod = _group_by(interfaces, "module_row_key")
    mod_entities_by_mod = _group_by(module_entities, "module_row_key")
    specs_by_mod = _group_by(specs, "module_row_key")

    screens_by_spec = _group_by(screens, "spec_row_key")
    components_by_spec = _group_by(components, "spec_row_key")
    endpoints_by_spec = _group_by(endpoints, "spec_row_key")
    entities_by_spec = _group_by(entities, "spec_row_key")
    rules_by_spec = _group_by(business_rules, "spec_row_key")
    scenarios_by_spec = _group_by(scenarios, "spec_row_key")
    frs_by_spec = _group_by(frs_list, "spec_row_key")
    decisions_by_spec = _group_by(
        [d for d in decisions if d.spec_row_key is not None],
        "spec_row_key",
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        # README
        z.writestr("README.md", _render_readme(
            modules, specs, traceability, br_titles,
        ))

        # Modules
        for i, m in enumerate(_sorted(modules), 1):
            md = _render_module(
                m,
                actors=actors_by_mod.get(m.row_key, []),
                responsibilities=resp_by_mod.get(m.row_key, []),
                interfaces=iface_by_mod.get(m.row_key, []),
                data_entities=mod_entities_by_mod.get(m.row_key, []),
                specs=specs_by_mod.get(m.row_key, []),
            )
            filename = f"modules/{i:03d}-{_slug(m.name)}.md"
            z.writestr(filename, md)

        # Specs
        for s in _sorted(specs):
            md = _render_spec(
                s,
                screens=screens_by_spec.get(s.row_key, []),
                components=components_by_spec.get(s.row_key, []),
                endpoints=endpoints_by_spec.get(s.row_key, []),
                entities=entities_by_spec.get(s.row_key, []),
                rules=rules_by_spec.get(s.row_key, []),
                scenarios=scenarios_by_spec.get(s.row_key, []),
                frs=frs_by_spec.get(s.row_key, []),
                decisions=decisions_by_spec.get(s.row_key, []),
                traceability=[t for t in traceability if t.source_row_key == s.row_key],
                br_titles=br_titles,
            )
            filename = f"specs/{s.row_key.lower()}-{_slug(s.title)}.md"
            z.writestr(filename, md)

        # Traceability files
        z.writestr("traceability/br-to-frs.md",
                   _render_br_to_frs(traceability, br_titles, specs))
        z.writestr("traceability/nfr-to-frs.md",
                   _render_nfr_to_frs(traceability, specs))
        z.writestr("traceability/module-to-frs.md",
                   _render_module_to_frs(modules, specs))
        z.writestr("traceability/matrix.csv",
                   _render_matrix_csv(traceability))

    return buf.getvalue()


# ─── Internal: data fetch + grouping ─────────────────────────────────────────


async def _active(model: type, document_id: uuid.UUID, db: AsyncSession) -> list[Any]:
    rows = (
        await db.execute(
            select(model).where(
                model.document_id == document_id,
                model.is_current.is_(True),
                model.status == "active",
            )
        )
    ).scalars().all()
    return list(rows)


def _group_by(rows: list[Any], key: str) -> dict[str, list[Any]]:
    out: dict[str, list[Any]] = {}
    for r in rows:
        out.setdefault(getattr(r, key), []).append(r)
    return out


def _sorted(rows: list[Any]) -> list[Any]:
    return sorted(rows, key=lambda r: getattr(r, "row_key", ""))


# ─── Renderers ───────────────────────────────────────────────────────────────


def _render_readme(modules, specs, traceability, br_titles) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    designed = sum(1 for s in specs if (s.completeness or 0) > 0)
    br_traced = {t.target_ref for t in traceability
                 if t.target_kind == "brd_business_requirement"}
    parts = [
        "# FRS Export Bundle",
        "",
        f"Generated: **{ts}**",
        "",
        "## Counts",
        "",
        f"- Modules: **{len(modules)}**",
        f"- FRS specs: **{len(specs)}** ({designed} designed, {len(specs) - designed} stubs)",
        f"- BRs traced: **{len(br_traced)}**",
        f"- Traceability rows: **{len(traceability)}**",
        "",
        "## Directory layout",
        "",
        "```",
        "README.md",
        "modules/                  one markdown file per module",
        "specs/                    one markdown file per FRS spec",
        "traceability/",
        "  br-to-frs.md            BR → FRS coverage",
        "  nfr-to-frs.md           NFR → FRS coverage",
        "  module-to-frs.md        module → FRS rollup",
        "  matrix.csv              flat dump of all traceability rows",
        "```",
        "",
    ]
    return "\n".join(parts) + "\n"


def _render_module(m, *, actors, responsibilities, interfaces,
                    data_entities, specs) -> str:
    p: list[str] = []
    p.append(f"# Module – {m.name}")
    p.append("")
    p.append(f"**Module ID:** `{m.row_key}` &middot; **Layer:** {m.layer}")
    p.append("")
    if m.summary:
        p.append(m.summary)
        p.append("")
    p.append("---")
    p.append("")
    p.append("## Scope")
    p.append("")
    p.append("### In scope")
    p.append("")
    p.append(_indent_or_bullet(m.scope_in))
    p.append("")
    p.append("### Out of scope")
    p.append("")
    p.append(_indent_or_bullet(m.scope_out))
    p.append("")
    p.append("---")
    p.append("")
    p.append("## Actors and Dependencies")
    p.append("")
    if actors:
        p.append("| Actor / System | Relationship | Notes |")
        p.append("|---|---|---|")
        for a in actors:
            p.append(f"| {a.actor_name} | {a.relationship} | {_md_cell(a.notes)} |")
    else:
        p.append("_(none defined)_")
    p.append("")
    p.append("---")
    p.append("")
    p.append("## Responsibilities")
    p.append("")
    if responsibilities:
        for r in responsibilities:
            refs = ", ".join(r.frs_refs or [])
            tail = f"  &nbsp;&middot; FRS: {refs}" if refs else ""
            p.append(f"- {r.responsibility}{tail}")
    else:
        p.append("_(none defined)_")
    p.append("")
    p.append("---")
    p.append("")
    p.append("## Interfaces")
    p.append("")
    ui_surfaces = [i for i in interfaces if i.interface_kind == "ui_surface"]
    apis = [i for i in interfaces if i.interface_kind == "api"]
    events = [i for i in interfaces if i.interface_kind == "event"]
    if ui_surfaces:
        p.append("### UI Surfaces")
        p.append("")
        p.append("| Surface | User Role | Purpose | FRS |")
        p.append("|---|---|---|---|")
        for i in ui_surfaces:
            p.append(f"| {i.name} | {i.user_role or '—'} | {_md_cell(i.purpose)} | {i.frs_ref or '—'} |")
        p.append("")
    if apis:
        p.append("### APIs")
        p.append("")
        p.append("| Direction | Transport | Counterpart | Name | Purpose | FRS |")
        p.append("|---|---|---|---|---|---|")
        for i in apis:
            p.append(f"| {i.direction or '—'} | {i.transport or '—'} | {i.counterpart or '—'} | {i.name} | {_md_cell(i.purpose)} | {i.frs_ref or '—'} |")
        p.append("")
    if events:
        p.append("### Events")
        p.append("")
        p.append("| Direction | Transport | Counterpart | Event Name | Purpose | FRS |")
        p.append("|---|---|---|---|---|---|")
        for i in events:
            p.append(f"| {i.direction or '—'} | {i.transport or '—'} | {i.counterpart or '—'} | {i.name} | {_md_cell(i.purpose)} | {i.frs_ref or '—'} |")
        p.append("")
    if not (ui_surfaces or apis or events):
        p.append("_(no interfaces yet)_")
        p.append("")
    p.append("---")
    p.append("")
    p.append("## Data")
    p.append("")
    if data_entities:
        p.append("| Entity | Business Purpose | Source of Truth |")
        p.append("|---|---|---|")
        for e in data_entities:
            p.append(f"| `{e.entity_name}` | {_md_cell(e.business_purpose)} | {_md_cell(e.source_of_truth)} |")
    else:
        p.append("_(no entities defined)_")
    p.append("")
    p.append("---")
    p.append("")
    p.append("## FRS Backlog")
    p.append("")
    if specs:
        p.append("| FRS ID | Title | Priority | Completeness | Confidence |")
        p.append("|---|---|---|---|---|")
        for s in sorted(specs, key=lambda x: x.row_key):
            p.append(f"| `{s.row_key}` | {_md_cell(s.title)} | {s.priority} | {s.completeness}% | {s.confidence} |")
    else:
        p.append("_(no backlog stubs)_")
    p.append("")
    return "\n".join(p) + "\n"


def _render_spec(s, *, screens, components, endpoints, entities, rules,
                  scenarios, frs, decisions, traceability, br_titles) -> str:
    p: list[str] = []
    p.append(f"# `{s.row_key}` – {s.title}")
    p.append("")
    p.append(
        f"**Priority:** {s.priority} &nbsp;&nbsp; **Layer:** {s.layer} "
        f"&nbsp;&nbsp; **Module:** `{s.module_row_key}` "
        f"&nbsp;&nbsp; **Completeness:** {s.completeness}% "
        f"&nbsp;&nbsp; **Confidence:** {s.confidence}"
    )
    p.append("")
    br_list = ", ".join(f"`{b}`" for b in (s.br_refs or [])) or "_(none)_"
    nfr_list = ", ".join(f"`{n}`" for n in (s.nfr_refs or [])) or "_(none)_"
    dep_list = ", ".join(f"`{d}`" for d in (s.depends_on or [])) or "N/A"
    p.append(f"**Business Requirements:** {br_list}")
    p.append(f"**NFR Drivers:** {nfr_list}")
    p.append(f"**Depends on:** {dep_list}")
    p.append("")
    p.append("---")
    p.append("")
    p.append("## Intent / Narrative")
    p.append("")
    p.append(s.narrative or "_(not yet authored)_")
    p.append("")
    p.append("---")
    p.append("")
    p.append("## Detailed Design")
    p.append("")

    # §1 UI Spec
    p.append("### 1. UI Specification")
    p.append("")
    if not screens:
        p.append("_N/A – no UI surfaces for this spec._")
        p.append("")
    else:
        for sc in screens:
            p.append(f"#### Screen: {sc.screen_name}")
            p.append("")
            p.append(f"- **Figma:** {sc.figma_link or '_pending_'}")
            roles = ", ".join(sc.user_roles or []) or "—"
            p.append(f"- **User roles:** {roles}")
            if sc.purpose:
                p.append("- **Purpose:**")
                p.append(_indent_block(sc.purpose, "    "))
            if sc.layout:
                p.append("- **Layout:**")
                p.append(_indent_block(sc.layout, "    "))
            if sc.navigation:
                p.append("- **Navigation:**")
                p.append(_indent_block(sc.navigation, "    "))
            if sc.interactive_behavior:
                p.append("- **Interactive behavior:**")
                p.append(_indent_block(sc.interactive_behavior, "    "))
            p.append("")
            # Components on this screen
            screen_cmps = [c for c in components if c.screen_row_key == sc.row_key]
            if screen_cmps:
                p.append(f"##### Components on `{sc.screen_name}`")
                p.append("")
                for c in screen_cmps:
                    p.append(f"###### {c.component_name} ({c.component_type})")
                    p.append("")
                    p.append(_render_json_block("Definition", c.definition))
                    p.append(_render_json_block("Behavior", c.behavior))
                    p.append(_render_json_block("Validation", c.validation))
                    if c.actions:
                        p.append(_render_json_block("Actions", c.actions))
                    if c.data_mapping:
                        p.append(_render_json_block("Data mapping", c.data_mapping))
                    p.append("")

    # §2 Backend
    p.append("### 2. Backend Service Specification")
    p.append("")
    if not endpoints:
        p.append("_N/A – no backend endpoints for this spec._")
        p.append("")
    else:
        for e in endpoints:
            p.append(f"#### Endpoint: {e.method} {e.url}")
            p.append("")
            p.append(f"- **Service:** {e.service_name}")
            p.append(f"- **Sync/Async:** {e.sync_async} &middot; **Idempotent:** {e.idempotent}")
            p.append(f"- **Protocol:** {e.protocol}")
            if e.integration_target:
                p.append(f"- **Integration target:** {e.integration_target}")
            p.append("")
            p.append(_render_json_block("Request", e.request_spec))
            p.append(_render_json_block("Response", e.response_spec))
            p.append(_render_json_block("Error handling", e.error_handling))
            p.append(_render_json_block("Security", e.security))
            p.append(_render_json_block("Operational", e.operational))
            p.append("")

    # §3 Data
    p.append("### 3. Data / Storage / Cache Specification")
    p.append("")
    if not entities:
        p.append("_N/A – no persistent data owned by this spec._")
        p.append("")
    else:
        for e in entities:
            p.append(f"#### Entity: `{e.entity_name}` ({e.data_store_type})")
            p.append("")
            p.append(f"- **Description:** {e.description}")
            p.append(f"- **Expected volume:** {e.expected_volume}")
            p.append(f"- **Retention:** {e.retention_policy}")
            p.append("")
            if e.columns:
                p.append(_render_json_block("Columns", e.columns))
            if e.keys_constraints:
                p.append(_render_json_block("Keys & constraints", e.keys_constraints))
            if e.indexes:
                p.append(_render_json_block("Indexes", e.indexes))
            if e.relationships:
                p.append(_render_json_block("Relationships", e.relationships))
            if e.access_logic:
                p.append("- **Access logic:**")
                p.append(_indent_block(e.access_logic, "    "))
            if e.cache_spec:
                p.append(_render_json_block("Cache spec", e.cache_spec))
            p.append("")

    # §4 Cross-Cutting
    p.append("### 4. Cross-Cutting Specifications")
    p.append("")
    if rules:
        p.append("#### 4.1 Business Rules")
        p.append("")
        p.append("| Rule ID | Description | Applies to | Logic / Decision |")
        p.append("|---|---|---|---|")
        for r in sorted(rules, key=lambda x: x.rule_id):
            p.append(f"| {r.rule_id} | {_md_cell(r.description)} | {_md_cell(r.applies_to)} | {_md_cell(r.logic_decision)} |")
        p.append("")
    else:
        p.append("_(no business rules)_")
        p.append("")

    # Independent Test
    p.append("## Independent Test")
    p.append("")
    p.append(s.independent_test or "_(not yet authored)_")
    p.append("")
    p.append("---")
    p.append("")

    # Scenarios
    p.append("## Acceptance Scenarios")
    p.append("")
    neg = sum(1 for sc in scenarios if sc.is_negative)
    p.append(f"_{len(scenarios)} scenarios &middot; {neg} negative_")
    p.append("")
    for sc in sorted(scenarios, key=lambda x: x.scenario_index):
        tag = " **(negative)**" if sc.is_negative else ""
        fr_refs = ", ".join(sc.fr_refs or [])
        tail = f" → {fr_refs}" if fr_refs else ""
        p.append(f"{sc.scenario_index}. **Given** {sc.given}{tag}")
        p.append(f"   **When** {sc.when}")
        p.append(f"   **Then** {sc.then}{tail}")
    p.append("")
    p.append("---")
    p.append("")

    # Functional Requirements
    p.append("## Functional Requirements")
    p.append("")
    for fr in sorted(frs, key=lambda x: x.fr_id):
        refs = ", ".join(fr.scenario_refs or [])
        tail = f" _(validated by {refs})_" if refs else ""
        p.append(f"- **{fr.fr_id}.** {fr.requirement_text}{tail}")
    p.append("")
    p.append("---")
    p.append("")

    p.append("## Data and Validation")
    p.append("")
    p.append(s.data_and_validation or "_(not yet authored)_")
    p.append("")
    p.append("---")
    p.append("")
    p.append("## Errors and Edge Cases")
    p.append("")
    p.append(s.errors_and_edge_cases or "_(not yet authored)_")
    p.append("")
    p.append("---")
    p.append("")
    p.append("## Observability")
    p.append("")
    p.append(s.observability or "_(not yet authored)_")
    p.append("")

    if s.implementation_tasks:
        p.append("---")
        p.append("")
        p.append("## Implementation Tasks (non-binding)")
        p.append("")
        for t in s.implementation_tasks:
            mark = "x" if t.get("done") else " "
            p.append(f"- [{mark}] {t.get('task', '')}")
        p.append("")

    if decisions:
        p.append("---")
        p.append("")
        p.append("## Spec Decisions")
        p.append("")
        for d in decisions:
            star = " ★" if d.recommended_index is not None else ""
            p.append(f"- **{d.row_key}** &nbsp;_({d.resolution_status})_  ")
            p.append(f"  {d.question}")
            for i, opt in enumerate(d.options or []):
                rec = star if i == d.recommended_index else ""
                p.append(f"    - **Option {i}:** {opt.get('label', '')}{rec} — {opt.get('description', '')}")
            if d.recommended_rationale:
                p.append(f"  _Rationale:_ {d.recommended_rationale}")
        p.append("")

    if traceability:
        p.append("---")
        p.append("")
        p.append("## Traceability")
        p.append("")
        p.append("| From | Kind | Target | Label | Confidence |")
        p.append("|---|---|---|---|---|")
        for t in sorted(traceability, key=lambda x: (x.source_table, x.source_row_key)):
            label = t.target_label or br_titles.get(t.target_ref, "")
            p.append(f"| `{t.source_table}/{t.source_row_key}` | {t.target_kind} | `{t.target_ref}` | {_md_cell(label)} | {t.confidence} |")
        p.append("")

    return "\n".join(p) + "\n"


def _render_br_to_frs(traceability, br_titles, specs) -> str:
    covers: dict[str, list[str]] = {}
    for t in traceability:
        if t.source_table == "frs_specs" and t.target_kind == "brd_business_requirement":
            covers.setdefault(t.target_ref, []).append(t.source_row_key)
    spec_titles = {s.row_key: s.title for s in specs}

    parts = ["# BR → FRS Coverage", ""]
    if not covers:
        parts.append("_(no BR traceability yet)_")
        return "\n".join(parts) + "\n"
    for br in sorted(covers):
        title = br_titles.get(br, "")
        parts.append(f"## {br}{' — ' + title if title else ''}")
        parts.append("")
        for sk in sorted(covers[br]):
            parts.append(f"- `{sk}` — {spec_titles.get(sk, '')}")
        parts.append("")
    return "\n".join(parts) + "\n"


def _render_nfr_to_frs(traceability, specs) -> str:
    covers: dict[str, list[str]] = {}
    for t in traceability:
        if t.target_kind == "nfr_driver":
            covers.setdefault(t.target_ref, []).append(t.source_row_key)
    spec_titles = {s.row_key: s.title for s in specs}

    parts = ["# NFR → FRS Coverage", ""]
    if not covers:
        parts.append("_(no NFR traceability yet — NFR builder ships in a later release)_")
        return "\n".join(parts) + "\n"
    for nfr in sorted(covers):
        parts.append(f"## {nfr}")
        parts.append("")
        for sk in sorted(covers[nfr]):
            parts.append(f"- `{sk}` — {spec_titles.get(sk, '')}")
        parts.append("")
    return "\n".join(parts) + "\n"


def _render_module_to_frs(modules, specs) -> str:
    by_mod: dict[str, list[Any]] = {}
    for s in specs:
        by_mod.setdefault(s.module_row_key, []).append(s)

    parts = ["# Module → FRS Rollup", ""]
    for m in sorted(modules, key=lambda x: x.row_key):
        parts.append(f"## `{m.row_key}` — {m.name}")
        parts.append("")
        mod_specs = sorted(by_mod.get(m.row_key, []), key=lambda x: x.row_key)
        if not mod_specs:
            parts.append("_(no specs)_")
        else:
            for s in mod_specs:
                parts.append(f"- `{s.row_key}` — {s.title} _(completeness {s.completeness}%)_")
        parts.append("")
    return "\n".join(parts) + "\n"


def _render_matrix_csv(traceability) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["source_table", "source_row_key", "target_kind", "target_ref",
                     "target_label", "confidence"])
    for t in sorted(traceability, key=lambda x: (x.source_table, x.source_row_key, x.target_ref)):
        writer.writerow([
            t.source_table, t.source_row_key, t.target_kind,
            t.target_ref, t.target_label or "", t.confidence,
        ])
    return out.getvalue()


# ─── Formatting helpers ──────────────────────────────────────────────────────


def _slug(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s or "").strip("-").lower()
    return s[:80] or "untitled"


def _md_cell(s: str | None) -> str:
    """Escape pipes and collapse newlines for markdown table cells."""
    if not s:
        return "—"
    return s.replace("|", "\\|").replace("\n", " ").replace("  ", " ").strip()


def _indent_or_bullet(text: str) -> str:
    """If text is already bullet-style, return as-is. Else wrap as a single bullet."""
    if not text:
        return "_(none)_"
    if text.lstrip().startswith(("-", "*", "+")):
        return text
    return "\n".join(f"- {line}" for line in text.splitlines() if line.strip())


def _indent_block(text: str, prefix: str) -> str:
    if not text:
        return f"{prefix}_(empty)_"
    return "\n".join(f"{prefix}{line}" for line in text.splitlines())


def _render_json_block(title: str, payload: Any, indent: str = "  ") -> str:
    """Render a JSONB-style payload as a readable bullet tree under a section."""
    if payload is None or (isinstance(payload, (list, dict)) and not payload):
        return f"- **{title}:** _(empty)_"
    rendered = _yaml_ish(payload, indent_level=1)
    return f"- **{title}:**\n{rendered}"


def _yaml_ish(payload: Any, indent_level: int = 0, indent: str = "  ") -> str:
    """Best-effort markdown-ish YAML for nested dict/list payloads.

    Stays portable + readable; not a parser-compatible YAML emitter.
    """
    prefix = indent * indent_level
    if isinstance(payload, dict):
        lines = []
        for k, v in payload.items():
            if isinstance(v, (dict, list)) and v:
                lines.append(f"{prefix}- **{k}:**")
                lines.append(_yaml_ish(v, indent_level + 1, indent))
            else:
                lines.append(f"{prefix}- **{k}:** {_inline(v)}")
        return "\n".join(lines)
    if isinstance(payload, list):
        lines = []
        for item in payload:
            if isinstance(item, (dict, list)) and item:
                lines.append(f"{prefix}- _(item)_")
                lines.append(_yaml_ish(item, indent_level + 1, indent))
            else:
                lines.append(f"{prefix}- {_inline(item)}")
        return "\n".join(lines)
    return f"{prefix}- {_inline(payload)}"


def _inline(v: Any) -> str:
    if v is None:
        return "_(null)_"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if len(s) > 200:
        s = s[:200] + "…"
    return s
