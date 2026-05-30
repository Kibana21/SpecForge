"""Model-agnostic wiki compilation core.

This is a parameterized copy of the App Brain pipeline in
`workers/tasks.py::_compile_one_doc`, lifted here so the Project Wiki (E2) can
reuse it without touching the E1 App Brain path (which keeps its own private
copy — see .claude/plans/E2-intelligent-intake.md, "copy not refactor").

A single `compile_doc_into_wiki()` drives both wikis via a `WikiScope`: summary →
concept-plan → parallel concept-page (PageIndex node-ref grounding) → whitelist
validation → upsert + backlinks. Mock-first: deterministic output under
`LLM_PROVIDER=mock`, zero network.
"""
import asyncio
import logging
import re as _re
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import delete as sa_delete, select
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

# Strip internal section identifiers the LLM sometimes inlines into prose, e.g.
# "(node_id: 0007, 0006)" or "(node 0013)" — these belong only in tree_node_refs.
_NODE_REF_RE = _re.compile(r"\s*\(\s*node(?:[_ ]?id)?s?\s*:?[\s0-9,]*\)", _re.IGNORECASE)


def slugify(name: str) -> str:
    """snake_case, URL-safe slug for a concept name."""
    s = _re.sub(r"[^\w]+", "_", (name or "").strip().lower()).strip("_")
    return s[:120] or "concept"


def strip_node_refs(text: str) -> str:
    if not text:
        return text
    cleaned = _NODE_REF_RE.sub("", text)
    return _re.sub(r" +([.,;:])", r"\1", cleaned)


def build_tree_context(tree_json: dict) -> tuple[str, dict[str, tuple[str, str]]]:
    """Return (outline_text, node_meta) from a PageIndex tree.

    outline_text: 'node_id · title (pp s-e) — summary' lines for the LLM to cite.
    node_meta: node_id -> (title, pages) for validating + enriching tree_node_refs.
    """
    from app.services.corpus_index.base import iter_nodes

    lines: list[str] = []
    meta: dict[str, tuple[str, str]] = {}
    for node in iter_nodes(tree_json or {}):
        nid = str(node.get("node_id", "")).strip()
        if not nid:
            continue
        title = (node.get("title") or "").strip()
        summary = (node.get("summary") or "").strip()
        s, e = node.get("start_index"), node.get("end_index")
        pages = f"{s}-{e}" if s is not None and e is not None else ""
        meta[nid] = (title, pages)
        lines.append(f"{nid} · {title} (pp {pages}) — {summary}")
    return "\n".join(lines), meta


@dataclass(frozen=True)
class WikiScope:
    """Binds the compile core to a concrete wiki (App Brain or Project)."""
    summary_model: type   # AppWikiSummary | ProjectWikiSummary
    concept_model: type   # AppWikiConcept | ProjectWikiConcept
    scope_col: str        # "app_id" | "project_id"
    summary_doc_col: str  # "doc_id" | "document_id"


async def compile_doc_into_wiki(
    db: AsyncSession,
    *,
    scope_id,
    scope_name: str,
    doc_id,
    doc_name: str,
    tree_json: dict | None,
    node_count: int,
    source_text: str,
    scope: WikiScope,
    settings,
) -> int:
    """Compile a single document into wiki summary + concept rows for `scope`
    (within an existing session/transaction). Returns concepts_touched.

    Caller resolves `source_text` (full text) and `tree_json`/`node_count`
    (PageIndex tree) from whatever document store the scope uses.
    """
    from app.services.skills.wiki_compiler.dspy_wiki import (
        run_concept_page, run_concept_plan, run_doc_summary,
    )

    Summary = scope.summary_model
    Concept = scope.concept_model
    scol = scope.scope_col
    dcol = scope.summary_doc_col

    doc_type = "pageindex" if (tree_json and node_count > 0) else "short"
    tree_outline, node_meta = build_tree_context(tree_json) if tree_json else ("", {})
    source_text = (source_text or tree_outline)[:50_000]

    existing = (await db.execute(
        select(Concept).where(getattr(Concept, scol) == scope_id)
    )).scalars().all()
    existing_by_slug = {c.slug: c for c in existing}

    # --- Summary + plan (mock vs production) ---
    if settings.llm_provider == "mock":
        summary = {
            "brief": f"Summary of {doc_name}",
            "content_md": f"## {doc_name}\n\n{source_text[:500]}",
            "candidate_concepts": ["overview", "capabilities"],
        }
        plan = {
            "create": ([] if "overview" in existing_by_slug
                       else [{"slug": "overview", "title": "Overview"}]),
            "update": ([{"slug": "overview", "title": "Overview"}]
                       if "overview" in existing_by_slug else []),
            "related": [],
        }
    else:
        summary = await run_doc_summary(scope_name, doc_name, source_text)
        existing_briefs = "\n".join(f"- {c.slug}: {c.brief}" for c in existing) or "(none yet)"
        plan = await run_concept_plan(scope_name, summary.get("content_md", ""), existing_briefs)

    create_items = plan.get("create", []) or []
    update_items = plan.get("update", []) or []
    related_items = plan.get("related", []) or []

    planned_slugs = {slugify(a.get("slug", a.get("title", ""))) for a in create_items + update_items}
    valid_slugs = set(existing_by_slug) | planned_slugs
    valid_slugs_str = ", ".join(sorted(valid_slugs)) or "(none)"
    valid_node_ids = set(node_meta)

    async def _gen(action: dict, is_update: bool):
        slug = slugify(action.get("slug", action.get("title", "")))
        title = action.get("title") or slug
        if settings.llm_provider == "mock":
            page = {
                "brief": f"{title} of {scope_name}",
                "content_md": f"## {title}\n\nSynthesised from [[summaries/{doc_name}]].\n\n{source_text[:300]}",
                "related_slugs": [],
                "tree_node_refs": (
                    [{"node_id": next(iter(valid_node_ids))}] if valid_node_ids else []
                ),
            }
        else:
            existing_content = (
                existing_by_slug[slug].content_md
                if (is_update and slug in existing_by_slug) else "(new page)"
            )
            page = await run_concept_page(
                scope_name, title, "", doc_name, source_text,
                tree_outline, valid_slugs_str, existing_content,
            )
        return slug, title, page, is_update

    tasks = [_gen(a, False) for a in create_items] + [_gen(a, True) for a in update_items]
    results = await asyncio.gather(*tasks, return_exceptions=True) if tasks else []

    # --- Upsert summary (replace any existing for this doc) ---
    touched_slugs: list[str] = []
    await db.execute(sa_delete(Summary).where(getattr(Summary, dcol) == doc_id))
    db.add(Summary(**{
        scol: scope_id, dcol: doc_id,
        "brief": summary.get("brief", "")[:1000] or doc_name,
        "content_md": strip_node_refs(summary.get("content_md", "")) or f"## {doc_name}",
        "related_slugs": [], "doc_type": doc_type,
    }))

    # --- Upsert concept rows ---
    concepts_touched = 0
    for r in results:
        if isinstance(r, Exception):
            log.warning("compile_wiki concept gen failed scope=%s: %s", scope_id, r)
            continue
        slug, title, page, is_update = r
        refs = []
        for ref in page.get("tree_node_refs", []) or []:
            nid = str(ref.get("node_id", "")).strip()
            if nid and nid in valid_node_ids:
                t, pages = node_meta[nid]
                refs.append({"doc_id": str(doc_id), "node_id": nid, "title": t, "pages": pages})
        related = [s for s in (page.get("related_slugs") or []) if s in valid_slugs and s != slug]
        brief = page.get("brief", "")[:1000] or title
        content_md = strip_node_refs(page.get("content_md", "")) or f"## {title}"

        if slug in existing_by_slug:
            c = existing_by_slug[slug]
            c.title, c.brief, c.content_md = title, brief, content_md
            c.related_slugs = sorted(set(c.related_slugs) | set(related))
            c.source_doc_ids = sorted(set(c.source_doc_ids) | {str(doc_id)})
            other_refs = [x for x in c.tree_node_refs if x.get("doc_id") != str(doc_id)]
            c.tree_node_refs = other_refs + refs
            c.compiled_at = datetime.now(timezone.utc)
        else:
            c = Concept(**{
                scol: scope_id, "slug": slug, "title": title, "brief": brief,
                "content_md": content_md, "source_doc_ids": [str(doc_id)],
                "related_slugs": related, "tree_node_refs": refs,
            })
            db.add(c)
            existing_by_slug[slug] = c
        touched_slugs.append(slug)
        concepts_touched += 1

    # --- related: cross-link only (attribute the doc, no rewrite) ---
    for s in related_items:
        slug = slugify(s)
        if slug in existing_by_slug:
            c = existing_by_slug[slug]
            c.source_doc_ids = sorted(set(c.source_doc_ids) | {str(doc_id)})
            touched_slugs.append(slug)

    # --- backlink: summary lists the concepts this doc touched ---
    summary_row = (await db.execute(
        select(Summary).where(getattr(Summary, dcol) == doc_id)
    )).scalar_one_or_none()
    if summary_row is not None:
        summary_row.related_slugs = sorted(set(touched_slugs))

    return concepts_touched
