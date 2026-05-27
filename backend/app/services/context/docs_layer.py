"""Documents layer: breadth (full outline inventory) + depth (per-unit tree_search)."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.context.project_context import DocInventoryEntry, DocsLayer


async def build_docs_layer(
    project_id: uuid.UUID,
    db: AsyncSession,
    *,
    artifact_document_id: uuid.UUID | None = None,
) -> DocsLayer:
    """Build the document layer for the bundle.

    Breadth: enumerate every included doc with its PageIndex outline summary.
    Depth: deferred to generation time via `depth_search()` so each unit gets
    its own targeted tree_search results.
    """
    from app.models.artifact import ArtifactSource
    from app.models.document import Document
    from app.models.project_source import DocumentTree

    # Which docs are in scope?
    if artifact_document_id is not None:
        included_ids = (
            await db.execute(
                select(ArtifactSource.source_document_id).where(
                    ArtifactSource.artifact_document_id == artifact_document_id,
                    ArtifactSource.included.is_(True),
                )
            )
        ).scalars().all()
        doc_filter = Document.id.in_(included_ids) if included_ids else Document.id.is_(None)
    else:
        doc_filter = Document.project_id == project_id

    # Load docs + their tree index status
    doc_rows = (
        await db.execute(
            select(Document)
            .where(doc_filter)
            .order_by(Document.filename)
        )
    ).scalars().all()

    if not doc_rows:
        return DocsLayer(
            inventory=[],
            ready_count=0,
            pending_count=0,
            failed_count=0,
            total_count=0,
            outline_text="(no project documents in scope)",
        )

    doc_ids = [d.id for d in doc_rows]
    tree_rows = (
        await db.execute(
            select(DocumentTree).where(DocumentTree.document_id.in_(doc_ids))
        )
    ).scalars().all()
    tree_by_doc: dict[uuid.UUID, DocumentTree] = {t.document_id: t for t in tree_rows}

    inventory: list[DocInventoryEntry] = []
    for doc in doc_rows:
        tree = tree_by_doc.get(doc.id)
        inventory.append(DocInventoryEntry(
            doc_id=str(doc.id),
            filename=doc.filename,
            parse_status=doc.parse_status,
            indexing_status=doc.indexing_status,
            node_count=tree.node_count if tree else 0,
            has_tree=tree is not None and tree.node_count > 0,
            included=True,
            page_count=doc.page_count,
        ))

    ready = [e for e in inventory if e.indexing_status == "done" and e.has_tree]
    pending = [e for e in inventory if e.indexing_status in ("pending", "running")]
    failed = [e for e in inventory if e.indexing_status == "error" or e.parse_status == "error"]

    outline_text = _build_outline_text(inventory, tree_by_doc, doc_rows)

    return DocsLayer(
        inventory=inventory,
        ready_count=len(ready),
        pending_count=len(pending),
        failed_count=len(failed),
        total_count=len(inventory),
        outline_text=outline_text,
    )


def _build_outline_text(
    inventory: list[DocInventoryEntry],
    tree_by_doc: dict[uuid.UUID, "DocumentTree"],
    doc_rows: list,
) -> str:
    """Build a breadth-first outline of all indexed documents (root nodes + summaries)."""
    import uuid as uuid_module
    lines = ["=== Project Document Inventory ===\n"]
    for entry in inventory:
        doc_id_obj = uuid_module.UUID(entry.doc_id)
        tree = tree_by_doc.get(doc_id_obj)
        status_tag = f"[{entry.indexing_status}]"
        lines.append(f"**{entry.filename}** {status_tag} — {entry.node_count} nodes")
        if tree and tree.node_count > 0:
            outline = _extract_outline(tree.tree_json)
            if outline:
                lines.append(outline)
        lines.append("")
    return "\n".join(lines)


def _extract_outline(tree_json: dict, max_nodes: int = 20) -> str:
    """Extract root-level section titles + first-level children as a compact outline."""
    if not tree_json:
        return ""
    nodes = tree_json.get("nodes", []) or tree_json.get("children", [])
    if not nodes:
        # Flat dict structure: try to get title + summary
        title = tree_json.get("title", "")
        summary = tree_json.get("summary", "")
        if title:
            return f"  - {title}" + (f": {summary[:100]}" if summary else "")
        return ""

    lines = []
    count = 0
    for node in nodes[:max_nodes]:
        if count >= max_nodes:
            break
        title = node.get("title", "")
        summary = node.get("summary", "")
        if title:
            lines.append(f"  - {title}" + (f": {summary[:100]}" if summary else ""))
            count += 1
        # One level of children
        for child in node.get("children", [])[:3]:
            if count >= max_nodes:
                break
            ct = child.get("title", "")
            if ct:
                lines.append(f"    · {ct}")
                count += 1
    return "\n".join(lines)


async def depth_search(
    project_id: uuid.UUID,
    db: AsyncSession,
    query: str,
    *,
    artifact_document_id: uuid.UUID | None = None,
    top_k: int | None = None,
) -> str:
    """Per-unit depth search: targeted tree_search for a specific query.

    Returns formatted section snippets ready for prompt injection.
    Called by the orchestrator for each generation unit.
    """
    from app.config import get_settings
    from app.models.artifact import ArtifactSource
    from app.models.document import Document
    from app.models.project_source import DocumentTree
    from app.services.corpus_index import IndexedDoc, get_corpus_index_provider

    if artifact_document_id is not None:
        included_ids = (
            await db.execute(
                select(ArtifactSource.source_document_id).where(
                    ArtifactSource.artifact_document_id == artifact_document_id,
                    ArtifactSource.included.is_(True),
                )
            )
        ).scalars().all()
        if not included_ids:
            return "(no source sections)"
        tree_filter = DocumentTree.document_id.in_(included_ids)
    else:
        tree_filter = DocumentTree.project_id == project_id

    rows = (
        await db.execute(
            select(DocumentTree, Document.filename)
            .join(Document, Document.id == DocumentTree.document_id)
            .where(tree_filter)
        )
    ).all()

    if not rows:
        return "(no source sections)"

    docs = [
        IndexedDoc(
            document_id=t.document_id,
            doc_name=name,
            tree=t.tree_json,
            page_texts=t.page_texts,
        )
        for t, name in rows
    ]

    settings = get_settings()
    k = top_k if top_k is not None else settings.tree_search_top_k
    sections = await get_corpus_index_provider().tree_search(query=query, docs=docs, top_k=k)
    if not sections:
        return "(no source sections)"

    return "\n\n".join(
        f"[S{i}] {s.doc_name} › {s.title}\n{s.text[:1200]}"
        for i, s in enumerate(sections, start=1)
    )
