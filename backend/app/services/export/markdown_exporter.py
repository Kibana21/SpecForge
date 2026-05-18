"""Convert structured spec JSON to well-formatted Markdown."""
from __future__ import annotations


def render(content_json: dict, spec_type: str, project_name: str, version: int) -> str:
    renderers = {
        "functional": render_functional,
        "technical": render_technical,
        "user_stories": render_user_stories,
        "review": render_review,
    }
    fn = renderers.get(spec_type)
    if fn is None:
        return f"# {project_name}\n\n```json\n{content_json}\n```"
    return fn(content_json, project_name, version)


def render_combined(specs: list[dict]) -> str:
    """Combine multiple rendered specs into one file."""
    return "\n\n---\n\n".join(s["markdown"] for s in specs if s.get("markdown"))


def render_functional(spec: dict, project_name: str, version: int) -> str:
    lines = [f"# Functional Specification — {project_name} (v{version})\n"]

    if overview := spec.get("overview"):
        lines += ["## Overview\n", overview, ""]

    if objectives := spec.get("objectives"):
        lines.append("## Objectives\n")
        for obj in objectives:
            lines.append(f"- {obj}")
        lines.append("")

    if scope := spec.get("scope"):
        lines += ["## Scope\n", scope, ""]

    if features := spec.get("features"):
        lines.append("## Features\n")
        for f in features:
            lines.append(f"### {f.get('name', 'Unnamed Feature')}\n")
            if desc := f.get("description"):
                lines += [desc, ""]
            if acs := f.get("acceptance_criteria"):
                lines.append("**Acceptance Criteria:**\n")
                for ac in acs:
                    lines.append(f"- {ac}")
                lines.append("")

    return "\n".join(lines)


def render_technical(spec: dict, project_name: str, version: int) -> str:
    lines = [f"# Technical Specification — {project_name} (v{version})\n"]

    if arch := spec.get("architecture_overview"):
        lines += ["## Architecture Overview\n", arch, ""]

    if components := spec.get("components"):
        lines.append("## Components\n")
        for c in components:
            lines.append(f"### {c.get('name', '')}\n")
            lines += [c.get("description", ""), ""]

    if models := spec.get("data_models"):
        lines.append("## Data Models\n")
        for m in models:
            lines.append(f"### {m.get('name', '')}\n")
            lines += [m.get("description", ""), ""]

    if endpoints := spec.get("api_endpoints"):
        lines.append("## API Endpoints\n")
        lines.append("| Method | Path | Description |")
        lines.append("|--------|------|-------------|")
        for e in endpoints:
            lines.append(f"| {e.get('method','')} | `{e.get('path','')}` | {e.get('description','')} |")
        lines.append("")

    if stack := spec.get("tech_stack"):
        lines.append("## Tech Stack\n")
        for k, v in stack.items():
            lines.append(f"- **{k.replace('_', ' ').title()}:** {v}")
        lines.append("")

    if risks := spec.get("risks"):
        lines.append("## Risks\n")
        for r in risks:
            lines.append(f"- **{r.get('risk', '')}** — {r.get('mitigation', '')}")
        lines.append("")

    return "\n".join(lines)


def render_user_stories(spec: dict, project_name: str, version: int) -> str:
    stories = spec.get("stories", [])
    lines = [f"# User Stories — {project_name} (v{version})\n"]

    if stories:
        lines.append("| ID | Title | Points | Labels |")
        lines.append("|----|-------|--------|--------|")
        for s in stories:
            labels = ", ".join(s.get("labels", []))
            lines.append(f"| {s.get('id','')} | {s.get('title','')} | {s.get('story_points','')} | {labels} |")
        lines.append("")

    for s in stories:
        lines.append(f"## {s.get('id','')} — {s.get('title','')}\n")
        if desc := s.get("description"):
            lines += [f"> {desc}", ""]
        if acs := s.get("acceptance_criteria"):
            lines.append("**Acceptance Criteria:**\n")
            for ac in acs:
                lines.append(f"- {ac}")
            lines.append("")
        lines.append("---\n")

    return "\n".join(lines)


def render_review(spec: dict, project_name: str, version: int) -> str:
    comments = spec.get("comments", [])
    lines = [f"# Review Comments — {project_name} (v{version})\n"]

    severity_order = ["critical", "warning", "suggestion"]
    grouped: dict[str, list] = {s: [] for s in severity_order}
    for c in comments:
        grouped.setdefault(c.get("severity", "suggestion"), []).append(c)

    for severity in severity_order:
        bucket = grouped.get(severity, [])
        if not bucket:
            continue
        lines.append(f"## {severity.title()}\n")
        for c in bucket:
            lines.append(f"### {c.get('id','')} — {c.get('section','')}\n")
            lines += [c.get("comment", ""), ""]
            lines.append(f"**Category:** {c.get('category', '')}\n")
            lines.append("---\n")

    return "\n".join(lines)
