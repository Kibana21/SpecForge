"""Render a validated NFR document to markdown following the nfr-template structure."""
from __future__ import annotations

from app.models.project import Project

_PRIORITY_LABEL = {"must": "Must", "should": "Should", "could": "Could", "wont": "Won't"}

_CATEGORY_SECTIONS = [
    ("performance", "Performance & Efficiency"),
    ("availability", "Availability, Reliability & Resilience"),
    ("security", "Security & Compliance"),
    ("usability", "Usability"),
    ("scalability", "Scalability & Capacity"),
    ("maintainability", "Maintainability & Supportability"),
    ("portability", "Portability & Compatibility"),
]

_CATEGORY_FRAMEWORK = [
    ("Performance & Efficiency", "Speed, latency, and throughput"),
    ("Security & Compliance", "Confidentiality, integrity, auditability, and adherence to legal or industry standards"),
    ("Availability & Reliability", "System uptime and robustness, often defined by SLAs"),
    ("Scalability & Capacity", "Ability to handle increasing user loads or data volumes"),
    ("Maintainability & Supportability", "Ease of updating, patching, and fixing the system"),
    ("Portability & Compatibility", "Ability to operate in different environments or with other systems"),
    ("Usability", "User experience and accessibility standards"),
]


def _esc(text) -> str:
    return str(text or "").replace("|", "\\|").replace("\n", " ").strip()


def _rows(sections: dict, table: str) -> list[dict]:
    return sections.get(table, []) or []


def _text_block(sections: dict, block_kind: str) -> str:
    for r in _rows(sections, "nfr_text_blocks"):
        if r.get("block_kind") == block_kind:
            return r.get("content", "")
    return ""


def export_nfr_markdown(detail: dict, project: Project) -> str:
    sections = detail.get("sections", {})
    trace_by_src = detail.get("traceability_by_source", {})
    out: list[str] = []

    out.append(f"# {project.name} — Non-Functional Requirements\n")

    # §1 Context & Objectives
    out.append("## 1. Context and Purpose\n")
    overview = _text_block(sections, "overview")
    objectives = _text_block(sections, "objectives")
    if overview:
        out.append("### 1.1 Overview\n")
        out.append(overview + "\n")
    if objectives:
        out.append("### 1.2 Objectives\n")
        out.append(objectives + "\n")

    out.append("### 1.3 NFR Category Framework\n")
    out.append("| Category | Description |")
    out.append("|----------|-------------|")
    for cat, desc in _CATEGORY_FRAMEWORK:
        out.append(f"| **{cat}** | {desc} |")
    out.append("")

    # §2–§8 category requirement tables
    reqs = _rows(sections, "nfr_requirements")
    by_cat: dict[str, list[dict]] = {}
    for r in reqs:
        by_cat.setdefault(r.get("category", ""), []).append(r)
    for i, (cat_key, cat_label) in enumerate(_CATEGORY_SECTIONS, start=2):
        out.append(f"## {i}. {cat_label}\n")
        rows = sorted(by_cat.get(cat_key, []), key=lambda r: r.get("row_key", ""))
        if not rows:
            out.append("_Not applicable._\n")
            continue
        out.append("| NFR Number | Attribute | Requirement | Priority |")
        out.append("|------------|-----------|-------------|----------|")
        for r in rows:
            if r.get("na"):
                out.append(f"| {r['row_key']} | — | _N/A — {_esc(r.get('rationale'))}_ | — |")
            else:
                pr = _PRIORITY_LABEL.get(r.get("priority", ""), r.get("priority", ""))
                req = _esc(r.get("requirement"))
                meas = _esc(r.get("measurement"))
                full = f"{req} (Measure: {meas})" if meas else req
                out.append(f"| {r['row_key']} | {_esc(r.get('attribute'))} | {full} | {pr} |")
        out.append("")

    # §9 Risks & Trade-offs
    out.append("## 9. Risks, Issues, and Trade-offs\n")
    risks = _rows(sections, "nfr_risks")
    out.append("### 9.1 NFR Risks\n")
    if risks:
        out.append("| Risk ID | Description | Affected Attribute | Impact | Likelihood | Mitigation | Owner | Status |")
        out.append("|---------|-------------|--------------------|--------|------------|-----------|-------|--------|")
        for r in risks:
            out.append(f"| {_esc(r.get('risk_id') or r['row_key'])} | {_esc(r.get('description'))} | {_esc(r.get('affected_attribute'))} | {_esc(r.get('impact'))} | {_esc(r.get('likelihood'))} | {_esc(r.get('mitigation'))} | {_esc(r.get('owner'))} | {_esc(r.get('risk_status'))} |")
        out.append("")
    else:
        out.append("_None recorded._\n")

    tradeoffs = _rows(sections, "nfr_tradeoffs")
    out.append("### 9.2 Trade-off Decisions\n")
    if tradeoffs:
        out.append("| Decision ID | Trade-off | Options Considered | Decision | Rationale | Decision Maker |")
        out.append("|-------------|-----------|--------------------|----------|-----------|----------------|")
        for t in tradeoffs:
            opts = ", ".join(t.get("options_considered") or [])
            out.append(f"| {t['row_key']} | {_esc(t.get('tradeoff'))} | {_esc(opts)} | {_esc(t.get('decision'))} | {_esc(t.get('rationale'))} | {_esc(t.get('decision_maker'))} |")
        out.append("")
    else:
        out.append("_None recorded._\n")

    # §10 Traceability to BRD
    out.append("## 10. Traceability to BRD\n")
    traced = [(r["row_key"], trace_by_src.get(r["row_key"], [])) for r in reqs if not r.get("na")]
    if any(tr for _, tr in traced):
        out.append("| NFR ID | Linked BRD Objective / Requirement | Notes |")
        out.append("|--------|-----------------------------------|-------|")
        for rk, trs in traced:
            refs = ", ".join(f"{t.get('target_ref')}" for t in trs) or "—"
            labels = "; ".join(t.get("target_label", "") for t in trs if t.get("target_label"))
            out.append(f"| {rk} | {_esc(refs)} | {_esc(labels)} |")
        out.append("")
    else:
        out.append("_No traceability recorded._\n")

    # §11 Open Questions & Pending Decisions
    out.append("## 11. Open Questions and Decisions\n")
    oqs = _rows(sections, "nfr_open_questions")
    out.append("### 11.1 Open Questions\n")
    if oqs:
        out.append("| Q ID | Question | Owner | Due Date | Status |")
        out.append("|------|----------|-------|----------|--------|")
        for q in oqs:
            out.append(f"| {q['row_key']} | {_esc(q.get('question'))} | {_esc(q.get('owner'))} | {_esc(q.get('due_date'))} | {_esc(q.get('oq_status'))} |")
        out.append("")
    else:
        out.append("_None._\n")

    decisions = _rows(sections, "nfr_decisions")
    out.append("### 11.2 Pending Decisions\n")
    if decisions:
        out.append("| Decision ID | Description | Owner | Target Date | Status |")
        out.append("|-------------|-------------|-------|-------------|--------|")
        for d in decisions:
            out.append(f"| {d['row_key']} | {_esc(d.get('description'))} | {_esc(d.get('owner'))} | {_esc(d.get('target_date'))} | {_esc(d.get('decision_status'))} |")
        out.append("")
    else:
        out.append("_None._\n")

    # §12 References & Glossary
    out.append("## 12. References and Appendices\n")
    refs = _rows(sections, "nfr_references")
    out.append("### 12.1 Reference Materials\n")
    if refs:
        out.append("| Ref ID | Type | Title / Description | Location | Notes |")
        out.append("|--------|------|---------------------|----------|-------|")
        for r in refs:
            out.append(f"| {r['row_key']} | {_esc(r.get('ref_type'))} | {_esc(r.get('title'))} | {_esc(r.get('location'))} | {_esc(r.get('notes'))} |")
        out.append("")
    else:
        out.append("_None._\n")

    glossary = _rows(sections, "nfr_glossary")
    out.append("### 12.2 Glossary\n")
    if glossary:
        out.append("| Term | Definition |")
        out.append("|------|-----------|")
        for g in glossary:
            out.append(f"| {_esc(g.get('term'))} | {_esc(g.get('definition'))} |")
        out.append("")
    else:
        out.append("_None._\n")

    return "\n".join(out)
