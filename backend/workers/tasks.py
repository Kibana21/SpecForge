import asyncio
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from workers.celery_app import celery_app

log = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async task body, disposing the DB engine afterward.

    Celery prefork executes each task in a NEW asyncio loop. The async engine's
    pooled asyncpg connections are bound to the loop that created them, so reusing
    the pool across tasks raises 'got Future attached to a different loop'.
    Disposing after each task forces fresh connections on the next task's loop.
    """
    async def _wrapped():
        try:
            return await coro
        finally:
            from app.db import engine
            await engine.dispose()

    return asyncio.run(_wrapped())


# ── Utility tasks ─────────────────────────────────────────────────────────────

@celery_app.task(name="workers.tasks.ping", bind=True)
def ping(self) -> dict:
    log.info("ping task executed task_id=%s", self.request.id)
    return {"ok": True, "ts": datetime.now(timezone.utc).isoformat()}


@celery_app.task(name="workers.tasks.purge_expired_refresh_tokens")
def purge_expired_refresh_tokens() -> dict:
    return _run_async(_purge_expired_tokens())


async def _purge_expired_tokens() -> dict:
    from sqlalchemy import delete

    from app.db import AsyncSessionLocal
    from app.models.auth import RefreshToken

    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            delete(RefreshToken).where(RefreshToken.expires_at < now)
        )
        await db.commit()
        count = result.rowcount

    log.info("purged_expired_refresh_tokens count=%d", count)
    return {"ok": True, "purged": count}


# ── App Brain ingestion ───────────────────────────────────────────────────────

@celery_app.task(
    name="workers.tasks.ingest_corpus_doc",
    max_retries=3,
    default_retry_delay=30,
)
def ingest_corpus_doc(doc_id: str) -> dict:
    return _run_async(_ingest_corpus_doc(doc_id))


@celery_app.task(name="workers.tasks.extract_app_facts")
def extract_app_facts(app_id: str) -> dict:
    return _run_async(_extract_app_facts(app_id))


@celery_app.task(name="workers.tasks.synthesize_brain_context")
def synthesize_brain_context(app_id: str) -> dict:
    return _run_async(_synthesize_brain_context(app_id))


@celery_app.task(name="workers.tasks.rebuild_app_brain")
def rebuild_app_brain(app_id: str) -> dict:
    return _run_async(_rebuild_app_brain(app_id))


@celery_app.task(name="workers.tasks.compile_wiki_for_doc")
def compile_wiki_for_doc(app_id: str, doc_id: str) -> dict:
    return _run_async(_compile_wiki_for_doc(app_id, doc_id))


@celery_app.task(name="workers.tasks.rebuild_app_wiki")
def rebuild_app_wiki(app_id: str) -> dict:
    return _run_async(_rebuild_app_wiki(app_id))


@celery_app.task(name="workers.tasks.check_wiki_health")
def check_wiki_health(app_id: str) -> dict:
    return _run_async(_check_wiki_health(app_id))


@celery_app.task(name="workers.tasks.reset_stale_rebuild_status")
def reset_stale_rebuild_status() -> dict:
    return _run_async(_reset_stale_rebuild_status())


# ── E2 project-source ingestion (PageIndex reasoning tree) ──────────────────────

@celery_app.task(
    name="workers.tasks.ingest_project_source",
    max_retries=3,
    default_retry_delay=30,
    time_limit=1800,  # PageIndex builds are LLM-heavy
)
def ingest_project_source(document_id: str) -> dict:
    return _run_async(_ingest_project_source(document_id))


@celery_app.task(name="workers.tasks.recompute_triage")
def recompute_triage() -> dict:
    return _run_async(_recompute_triage())


@celery_app.task(
    name="workers.tasks.generate_requirement_understanding",
    bind=True,
    max_retries=6,
    default_retry_delay=10,
)
def generate_requirement_understanding(self, project_id: str) -> dict:
    return _run_async(_generate_ru(self, project_id))


# ── Artifact generation ───────────────────────────────────────────────────────

@celery_app.task(name="workers.tasks.generate_concept_brief", bind=True, max_retries=2, default_retry_delay=5)
def generate_concept_brief(self, project_id: str, artifact_type: str, context: str | None = None) -> dict:
    return _run_async(_generate_concept_brief(project_id, artifact_type, context))


# ── Async implementations ─────────────────────────────────────────────────────

async def _ingest_corpus_doc(doc_id: str) -> dict:
    try:
        UUID(doc_id)
    except (ValueError, AttributeError):
        log.error("ingest_corpus_doc invalid doc_id=%s — skipping", doc_id)
        return {"ok": False, "error": "invalid_doc_id"}

    from sqlalchemy import delete, select, text

    from app.db import AsyncSessionLocal
    from app.models.corpus import AppChunk, AppCorpusDoc
    from app.models.storage import StorageFile, StorageFileBlob
    from app.services.corpus.chunker import chunk_text
    from app.services.documents.parser import parse
    from app.services.embeddings import get_embedding_provider
    from app.services.markdown_converter import MarkdownConverterService, get_markdown_provider

    async with AsyncSessionLocal() as db:
        doc = await db.get(AppCorpusDoc, UUID(doc_id))
        if doc is None:
            log.error("ingest_corpus_doc doc_id=%s not found", doc_id)
            return {"ok": False, "error": "doc_not_found"}

        doc.index_status = "running"
        await db.commit()

        try:
            # Load file bytes from StorageFile/StorageFileBlob
            file_row = await db.get(StorageFile, doc.file_id)
            if file_row is None:
                raise RuntimeError(f"StorageFile {doc.file_id} not found")

            blob_result = await db.execute(
                select(StorageFileBlob)
                .where(StorageFileBlob.file_id == doc.file_id)
                .order_by(StorageFileBlob.chunk_no)
            )
            blobs = blob_result.scalars().all()
            content = b"".join(b.data for b in blobs)

            # Convert document to text — Azure markdown converter in production,
            # plain parser in mock/CI mode (zero external calls, matches all other providers).
            from app.config import get_settings
            if get_settings().llm_provider != "mock":
                svc = MarkdownConverterService(db, get_markdown_provider())
                raw_text = await svc.convert(
                    content, file_row.content_type, doc.name,
                    correlation_id=str(doc.id),
                )
            else:
                raw_text = parse(content, file_row.content_type)

            # Count pages for PDF
            if file_row.content_type == "application/pdf":
                try:
                    import fitz
                    pdf_doc = fitz.open(stream=content, filetype="pdf")
                    doc.page_count = len(pdf_doc)
                    pdf_doc.close()
                except Exception:
                    doc.page_count = 1
            else:
                doc.page_count = 1

            # Chunk text
            chunks = chunk_text(raw_text)
            if not chunks:
                log.warning("ingest_corpus_doc doc_id=%s produced 0 chunks", doc_id)
                chunks = [raw_text[:1000]] if raw_text else []

            # Embed chunks
            provider = get_embedding_provider()
            embeddings = await provider.embed_batch(chunks)

            # Delete existing chunks then bulk insert
            await db.execute(delete(AppChunk).where(AppChunk.doc_id == doc.id))

            chunk_objs = [
                AppChunk(
                    doc_id=doc.id,
                    chunk_no=i,
                    text=chunks[i],
                    embedding=embeddings[i],
                )
                for i in range(len(chunks))
            ]
            db.add_all(chunk_objs)
            await db.flush()

            # Run ANALYZE on app_chunks for IVFFlat recall
            await db.execute(text("ANALYZE app_chunks"))

            # Hybrid: also build a PageIndex reasoning tree (best-effort — vector
            # chunks remain the baseline if tree building fails or is disabled).
            from app.config import get_settings
            if get_settings().app_brain_use_pageindex:
                try:
                    from app.models.corpus import AppDocTree
                    from app.services.corpus_index import get_corpus_index_provider

                    tree = await get_corpus_index_provider().build_index(
                        data=content, content_type=file_row.content_type, filename=doc.name
                    )
                    await db.execute(delete(AppDocTree).where(AppDocTree.corpus_doc_id == doc.id))
                    db.add(AppDocTree(
                        corpus_doc_id=doc.id, app_id=doc.app_id,
                        tree_json=tree.tree, page_texts=tree.page_texts,
                        node_count=tree.node_count, model=tree.model,
                    ))
                    log.info("ingest_corpus_doc doc_id=%s tree_nodes=%d", doc_id, tree.node_count)
                except Exception as exc:  # noqa: BLE001
                    log.warning("ingest_corpus_doc tree build failed doc_id=%s error=%s", doc_id, exc)

            doc.index_status = "done"
            doc.index_error = None  # clear any stale error from a prior failed run
            doc.indexed_at = datetime.now(timezone.utc)
            await db.commit()

            log.info("ingest_corpus_doc doc_id=%s chunks=%d", doc_id, len(chunks))

        except Exception as exc:
            doc.index_status = "error"
            doc.index_error = str(exc)[:1000]
            await db.commit()
            log.error("ingest_corpus_doc doc_id=%s error=%s", doc_id, exc)
            raise

    # Dispatch fact extraction on success
    extract_app_facts.delay(str(doc.app_id))
    # Incrementally compile this doc into the Brain Wiki (accumulate model)
    compile_wiki_for_doc.delay(str(doc.app_id), doc_id)

    return {"ok": True, "doc_id": doc_id, "chunks": len(chunks)}


async def _extract_app_facts(app_id: str) -> dict:
    from sqlalchemy import select

    from app.config import get_settings
    from app.db import AsyncSessionLocal
    from app.models.app import App
    from app.models.corpus import AppChunk, AppCorpusDoc
    from app.models.fact import AppFact

    settings = get_settings()
    max_chunks = settings.fact_extract_max_chunks

    async with AsyncSessionLocal() as db:
        app = await db.get(App, UUID(app_id))
        if app is None:
            log.error("extract_app_facts app_id=%s not found", app_id)
            return {"ok": False, "error": "app_not_found"}

        # Load corpus docs ordered by creation so extraction is deterministic
        docs_result = await db.execute(
            select(AppCorpusDoc)
            .where(AppCorpusDoc.app_id == UUID(app_id))
            .order_by(AppCorpusDoc.created_at)
        )
        corpus_docs = docs_result.scalars().all()

        if not corpus_docs:
            log.info("extract_app_facts app_id=%s no docs found", app_id)
            return {"ok": True, "facts_created": 0, "app_id": app_id}

        # Pre-load existing active facts once for cross-doc dedup
        existing_result = await db.execute(
            select(AppFact).where(AppFact.app_id == UUID(app_id), AppFact.status == "active")
        )
        existing_keys = {(f.kind, f.text.strip().lower()) for f in existing_result.scalars().all()}

        facts_created = 0

        if settings.llm_provider == "mock":
            # Mock/CI: single fixture call over all chunks — no LLM, no cost.
            # source_ref and chunk_ids are set to the sole doc when there is only one,
            # so cascade-delete still works in single-doc test scenarios.
            all_chunks_result = await db.execute(
                select(AppChunk)
                .join(AppCorpusDoc, AppChunk.doc_id == AppCorpusDoc.id)
                .where(AppCorpusDoc.app_id == UUID(app_id))
                .order_by(AppCorpusDoc.id, AppChunk.chunk_no)
                .limit(max_chunks)
            )
            all_chunks = all_chunks_result.scalars().all()

            if not all_chunks:
                return {"ok": True, "facts_created": 0, "app_id": app_id}

            from app.services.skills.mock_fixtures import mock_fixture
            result_data = mock_fixture("fact_extractor")
            facts_list = result_data.get("facts", []) if isinstance(result_data, dict) else []

            # Attribute to a single doc when possible so delete cascade can trace back
            sole_doc = corpus_docs[0] if len(corpus_docs) == 1 else None
            sole_chunk_ids = (
                [str(c.id) for c in all_chunks if c.doc_id == sole_doc.id]
                if sole_doc else []
            )

            for fact_data in facts_list:
                key = (fact_data["kind"], fact_data["text"].strip().lower())
                if key in existing_keys:
                    continue
                db.add(AppFact(
                    app_id=UUID(app_id),
                    doc_id=sole_doc.id if sole_doc else None,
                    kind=fact_data["kind"],
                    text=fact_data["text"],
                    source_ref=sole_doc.name if sole_doc else fact_data.get("source_ref"),
                    confidence=fact_data["confidence"],
                    status="active",
                    source="ai",
                    chunk_ids=sole_chunk_ids,
                    source_fact_ids=[],
                ))
                existing_keys.add(key)
                facts_created += 1

        else:
            # Production: extract per-doc so every fact carries explicit source traceability.
            # source_ref = doc.name (set here, not left to the LLM)
            # chunk_ids  = UUIDs of every chunk from that doc (enables cascade delete)
            from app.services.skills.fact_extractor.dspy_extractor import run_dspy_fact_extraction

            chunks_budget = max_chunks
            for doc in corpus_docs:
                if chunks_budget <= 0:
                    break

                doc_chunks_result = await db.execute(
                    select(AppChunk)
                    .where(AppChunk.doc_id == doc.id)
                    .order_by(AppChunk.chunk_no)
                    .limit(chunks_budget)
                )
                doc_chunks = doc_chunks_result.scalars().all()
                if not doc_chunks:
                    continue

                chunks_budget -= len(doc_chunks)
                doc_chunk_ids = [str(c.id) for c in doc_chunks]
                chunk_text = "\n\n".join(
                    f"--- [chunk {c.chunk_no}] ---\n{c.text}" for c in doc_chunks
                )[:50_000]

                try:
                    facts_list = await run_dspy_fact_extraction(chunk_text)
                except Exception as exc:
                    log.error("extract_app_facts skill_error app_id=%s doc_id=%s error=%s",
                              app_id, doc.id, exc)
                    continue

                log.info("extract_app_facts app_id=%s doc=%s chunks=%d facts_returned=%d",
                         app_id, doc.name, len(doc_chunks), len(facts_list))

                for fact_data in facts_list:
                    key = (fact_data["kind"], fact_data["text"].strip().lower())
                    if key in existing_keys:
                        continue
                    db.add(AppFact(
                        app_id=UUID(app_id),
                        doc_id=doc.id,            # explicit doc link for traceability
                        kind=fact_data["kind"],
                        text=fact_data["text"],
                        source_ref=doc.name,      # explicit — never left to LLM
                        confidence=fact_data["confidence"],
                        status="active",
                        source="ai",
                        chunk_ids=doc_chunk_ids,  # all chunks from this doc
                        source_fact_ids=[],
                    ))
                    existing_keys.add(key)
                    facts_created += 1

        from datetime import timezone
        app.updated_at = datetime.now(timezone.utc)
        await db.commit()

    log.info("extract_app_facts app_id=%s facts_created=%d", app_id, facts_created)
    return {"ok": True, "facts_created": facts_created, "app_id": app_id}


async def _synthesize_brain_context(app_id: str) -> dict:
    """Synthesize all per-doc facts for an app into deduplicated brain context facts.

    Per-doc facts (source='ai'|'human', doc_id IS NOT NULL) are grouped by kind and
    fed to the fact_synthesis skill. The output replaces all existing brain facts
    (source='brain') for this app.
    """
    from sqlalchemy import delete as sa_delete, select

    from app.config import get_settings
    from app.db import AsyncSessionLocal
    from app.models.app import App
    from app.models.corpus import AppCorpusDoc
    from app.models.fact import AppFact
    from app.services.skills.fact_synthesis.dspy_synthesizer import run_dspy_fact_synthesis, SourceFact

    FACT_KINDS = ["capability", "constraint", "limitation", "integration", "gotcha"]

    async with AsyncSessionLocal() as db:
        app = await db.get(App, UUID(app_id))
        if app is None:
            log.error("synthesize_brain_context app_id=%s not found", app_id)
            return {"ok": False, "error": "app_not_found"}

        app.brain_context_status = "running"
        await db.commit()

        try:
            # Fetch all active per-doc facts (excludes existing brain facts)
            source_facts_result = await db.execute(
                select(AppFact).where(
                    AppFact.app_id == UUID(app_id),
                    AppFact.source.in_(["ai", "human"]),
                    AppFact.doc_id.isnot(None),
                    AppFact.status == "active",
                )
            )
            source_facts = source_facts_result.scalars().all()

            if not source_facts:
                log.info("synthesize_brain_context app_id=%s no source facts", app_id)
                app.brain_context_status = "idle"
                app.brain_context_synthesized_at = datetime.now(timezone.utc)
                await db.commit()
                return {"ok": True, "facts_created": 0}

            # Load doc names for source attribution
            docs_result = await db.execute(
                select(AppCorpusDoc).where(AppCorpusDoc.app_id == UUID(app_id))
            )
            doc_name_map = {str(d.id): d.name for d in docs_result.scalars().all()}

            settings = get_settings()

            # Delete existing brain facts before re-synthesizing
            await db.execute(
                sa_delete(AppFact).where(
                    AppFact.app_id == UUID(app_id),
                    AppFact.source == "brain",
                )
            )

            facts_created = 0
            for kind in FACT_KINDS:
                kind_facts = [f for f in source_facts if f.kind == kind]
                if not kind_facts:
                    continue

                source_fact_objects = [
                    SourceFact(
                        id=str(f.id),
                        text=f.text,
                        source_ref=f.source_ref or doc_name_map.get(str(f.doc_id), ""),
                        confidence=f.confidence,
                    )
                    for f in kind_facts
                ]

                if settings.llm_provider == "mock":
                    all_ids = [str(f.id) for f in kind_facts]
                    synth_facts = [
                        {
                            "text": f"[{kind}] Synthesized: {kind_facts[0].text}",
                            "confidence": "high",
                            "source_fact_ids": all_ids[:2],
                        }
                    ]
                else:
                    try:
                        synth_facts = await run_dspy_fact_synthesis(
                            app_name=app.name,
                            kind=kind,
                            source_facts=source_fact_objects,
                        )
                    except Exception as exc:
                        log.error("synthesize_brain_context dspy_error kind=%s error=%s", kind, exc)
                        continue

                for sf in synth_facts:
                    # Validate source_fact_ids references real facts
                    valid_source_ids = [
                        sid for sid in sf.get("source_fact_ids", [])
                        if any(str(f.id) == sid for f in kind_facts)
                    ]
                    db.add(AppFact(
                        app_id=UUID(app_id),
                        doc_id=None,
                        kind=kind,
                        text=sf["text"],
                        confidence=sf.get("confidence", "medium"),
                        status="active",
                        source="brain",
                        source_ref=None,
                        chunk_ids=[],
                        source_fact_ids=valid_source_ids,
                    ))
                    facts_created += 1

            app.brain_context_synthesized_at = datetime.now(timezone.utc)
            app.brain_context_status = "idle"
            await db.commit()

        except Exception as exc:
            log.error("synthesize_brain_context app_id=%s error=%s", app_id, exc)
            try:
                await db.rollback()
                fresh = await db.get(App, UUID(app_id))
                if fresh:
                    fresh.brain_context_status = "idle"
                    await db.commit()
            except Exception:
                pass
            return {"ok": False, "error": str(exc)}

    log.info("synthesize_brain_context app_id=%s facts_created=%d", app_id, facts_created)
    return {"ok": True, "facts_created": facts_created, "app_id": app_id}


# ── Brain Wiki compilation (OpenKB-style: summaries + emergent concepts) ─────────

import re as _re


def _slugify(name: str) -> str:
    """snake_case, URL-safe slug for a concept name."""
    s = _re.sub(r"[^\w]+", "_", (name or "").strip().lower()).strip("_")
    return s[:120] or "concept"


# Strip internal section identifiers the LLM sometimes inlines into prose, e.g.
# "(node_id: 0007, 0006)" or "(node 0013)" — these belong only in tree_node_refs.
_NODE_REF_RE = _re.compile(r"\s*\(\s*node(?:[_ ]?id)?s?\s*:?[\s0-9,]*\)", _re.IGNORECASE)


def _strip_node_refs(text: str) -> str:
    if not text:
        return text
    cleaned = _NODE_REF_RE.sub("", text)
    # tidy any doubled spaces left before punctuation
    return _re.sub(r" +([.,;:])", r"\1", cleaned)


def _build_tree_context(tree_json: dict) -> tuple[str, dict[str, tuple[str, str]]]:
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


async def _compile_one_doc(db, app, doc, settings) -> int:
    """Compile a single corpus doc into wiki summary + concept rows (within an
    existing session/transaction). Returns the number of concept rows touched.

    Mirrors OpenKB's per-doc pipeline: summary → {create,update,related} plan →
    concept generation (with PageIndex node-ref grounding) → upsert + backlinks.
    """
    from sqlalchemy import delete as sa_delete, select

    from app.models.corpus import AppDocTree
    from app.models.document_markdown import DocumentMarkdown
    from app.models.wiki import AppWikiConcept, AppWikiSummary
    from app.services.skills.wiki_compiler.dspy_wiki import (
        run_concept_page, run_concept_plan, run_doc_summary,
    )

    app_id = app.id

    # --- Source: PageIndex tree (for outline + node refs) + markdown (full text) ---
    tree_row = (await db.execute(
        select(AppDocTree).where(AppDocTree.corpus_doc_id == doc.id)
    )).scalar_one_or_none()
    doc_type = "pageindex" if (tree_row and tree_row.node_count > 0) else "short"
    tree_outline, node_meta = _build_tree_context(tree_row.tree_json) if tree_row else ("", {})

    md_row = (await db.execute(
        select(DocumentMarkdown).where(DocumentMarkdown.correlation_id == str(doc.id))
    )).scalar_one_or_none()
    source_text = (md_row.markdown_text if md_row else "") or tree_outline
    source_text = source_text[:50_000]

    # --- Existing concepts for this app (accumulate model) ---
    existing = (await db.execute(
        select(AppWikiConcept).where(AppWikiConcept.app_id == app_id)
    )).scalars().all()
    existing_by_slug = {c.slug: c for c in existing}

    # --- Summary + plan + concept pages (mock vs production) ---
    if settings.llm_provider == "mock":
        summary = {
            "brief": f"Summary of {doc.name}",
            "content_md": f"## {doc.name}\n\n{source_text[:500]}",
            "candidate_concepts": ["overview", "capabilities"],
        }
        plan = {
            "create": (
                [] if "overview" in existing_by_slug
                else [{"slug": "overview", "title": "Overview"}]
            ),
            "update": (
                [{"slug": "overview", "title": "Overview"}]
                if "overview" in existing_by_slug else []
            ),
            "related": [],
        }
    else:
        summary = await run_doc_summary(app.name, doc.name, source_text)
        existing_briefs = "\n".join(
            f"- {c.slug}: {c.brief}" for c in existing
        ) or "(none yet)"
        plan = await run_concept_plan(app.name, summary.get("content_md", ""), existing_briefs)

    create_items = plan.get("create", []) or []
    update_items = plan.get("update", []) or []
    related_items = plan.get("related", []) or []

    # Whitelist of valid slugs the concept pages may cross-link to
    planned_slugs = {_slugify(a.get("slug", a.get("title", ""))) for a in create_items + update_items}
    valid_slugs = set(existing_by_slug) | planned_slugs
    valid_slugs_str = ", ".join(sorted(valid_slugs)) or "(none)"
    valid_node_ids = set(node_meta)

    async def _gen(action: dict, is_update: bool):
        slug = _slugify(action.get("slug", action.get("title", "")))
        title = action.get("title") or slug
        if settings.llm_provider == "mock":
            page = {
                "brief": f"{title} of {app.name}",
                "content_md": f"## {title}\n\nSynthesised from [[summaries/{doc.name}]].\n\n{source_text[:300]}",
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
                app.name, title, "", doc.name, source_text,
                tree_outline, valid_slugs_str, existing_content,
            )
        return slug, title, page, is_update

    tasks = [_gen(a, False) for a in create_items] + [_gen(a, True) for a in update_items]
    results = await asyncio.gather(*tasks, return_exceptions=True) if tasks else []

    # --- Upsert summary (replace any existing for this doc) ---
    touched_slugs: list[str] = []
    await db.execute(sa_delete(AppWikiSummary).where(AppWikiSummary.doc_id == doc.id))
    db.add(AppWikiSummary(
        app_id=app_id, doc_id=doc.id,
        brief=summary.get("brief", "")[:1000] or doc.name,
        content_md=_strip_node_refs(summary.get("content_md", "")) or f"## {doc.name}",
        related_slugs=[], doc_type=doc_type,
    ))

    # --- Upsert concept rows ---
    concepts_touched = 0
    for r in results:
        if isinstance(r, Exception):
            log.warning("compile_wiki concept gen failed app_id=%s: %s", app_id, r)
            continue
        slug, title, page, is_update = r
        # Validate node refs against the real tree; enrich with title + pages
        refs = []
        for ref in page.get("tree_node_refs", []) or []:
            nid = str(ref.get("node_id", "")).strip()
            if nid and nid in valid_node_ids:
                t, pages = node_meta[nid]
                refs.append({"doc_id": str(doc.id), "node_id": nid, "title": t, "pages": pages})
        related = [s for s in (page.get("related_slugs") or []) if s in valid_slugs and s != slug]
        brief = page.get("brief", "")[:1000] or title
        content_md = _strip_node_refs(page.get("content_md", "")) or f"## {title}"

        if slug in existing_by_slug:
            c = existing_by_slug[slug]
            c.title, c.brief, c.content_md = title, brief, content_md
            c.related_slugs = sorted(set(c.related_slugs) | set(related))
            c.source_doc_ids = sorted(set(c.source_doc_ids) | {str(doc.id)})
            # keep other docs' refs, replace this doc's
            other_refs = [x for x in c.tree_node_refs if x.get("doc_id") != str(doc.id)]
            c.tree_node_refs = other_refs + refs
            c.compiled_at = datetime.now(timezone.utc)
        else:
            c = AppWikiConcept(
                app_id=app_id, slug=slug, title=title, brief=brief, content_md=content_md,
                source_doc_ids=[str(doc.id)], related_slugs=related, tree_node_refs=refs,
            )
            db.add(c)
            existing_by_slug[slug] = c
        touched_slugs.append(slug)
        concepts_touched += 1

    # --- related: cross-link only (attribute the doc, no rewrite) ---
    for s in related_items:
        slug = _slugify(s)
        if slug in existing_by_slug:
            c = existing_by_slug[slug]
            c.source_doc_ids = sorted(set(c.source_doc_ids) | {str(doc.id)})
            touched_slugs.append(slug)

    # --- backlink: summary lists the concepts this doc touched ---
    summary_row = (await db.execute(
        select(AppWikiSummary).where(AppWikiSummary.doc_id == doc.id)
    )).scalar_one_or_none()
    if summary_row is not None:
        summary_row.related_slugs = sorted(set(touched_slugs))

    return concepts_touched


async def _compile_wiki_for_doc(app_id: str, doc_id: str) -> dict:
    from app.config import get_settings
    from app.db import AsyncSessionLocal
    from app.models.app import App
    from app.models.corpus import AppCorpusDoc

    settings = get_settings()
    async with AsyncSessionLocal() as db:
        app = await db.get(App, UUID(app_id))
        doc = await db.get(AppCorpusDoc, UUID(doc_id))
        if app is None or doc is None:
            log.error("compile_wiki_for_doc app=%s doc=%s not found", app_id, doc_id)
            return {"ok": False, "error": "not_found"}

        app.wiki_status = "running"
        await db.commit()
        try:
            n = await _compile_one_doc(db, app, doc, settings)
            app.wiki_compiled_at = datetime.now(timezone.utc)
            app.wiki_status = "idle"
            await db.commit()
        except Exception as exc:
            log.error("compile_wiki_for_doc app_id=%s error=%s", app_id, exc, exc_info=True)
            try:
                await db.rollback()
                fresh = await db.get(App, UUID(app_id))
                if fresh:
                    fresh.wiki_status = "idle"
                    await db.commit()
            except Exception:
                pass
            return {"ok": False, "error": str(exc)}

    log.info("compile_wiki_for_doc app_id=%s doc_id=%s concepts=%d", app_id, doc_id, n)
    return {"ok": True, "app_id": app_id, "doc_id": doc_id, "concepts_touched": n}


async def _rebuild_app_wiki(app_id: str) -> dict:
    from sqlalchemy import delete as sa_delete, select

    from app.config import get_settings
    from app.db import AsyncSessionLocal
    from app.models.app import App
    from app.models.corpus import AppCorpusDoc
    from app.models.wiki import AppWikiConcept, AppWikiSummary

    settings = get_settings()
    async with AsyncSessionLocal() as db:
        app = await db.get(App, UUID(app_id))
        if app is None:
            return {"ok": False, "error": "app_not_found"}

        app.wiki_status = "running"
        await db.commit()
        try:
            # Clear all wiki rows, then recompile docs in creation order so
            # concepts accumulate deterministically (each doc sees prior concepts).
            await db.execute(sa_delete(AppWikiConcept).where(AppWikiConcept.app_id == app.id))
            await db.execute(sa_delete(AppWikiSummary).where(AppWikiSummary.app_id == app.id))
            await db.flush()

            docs = (await db.execute(
                select(AppCorpusDoc)
                .where(
                    AppCorpusDoc.app_id == app.id,
                    AppCorpusDoc.index_status == "done",
                )
                .order_by(AppCorpusDoc.created_at)
            )).scalars().all()

            total = 0
            for doc in docs:
                total += await _compile_one_doc(db, app, doc, settings)
                await db.flush()

            app.wiki_compiled_at = datetime.now(timezone.utc)
            app.wiki_status = "idle"
            await db.commit()
        except Exception as exc:
            log.error("rebuild_app_wiki app_id=%s error=%s", app_id, exc, exc_info=True)
            try:
                await db.rollback()
                fresh = await db.get(App, UUID(app_id))
                if fresh:
                    fresh.wiki_status = "idle"
                    await db.commit()
            except Exception:
                pass
            return {"ok": False, "error": str(exc)}

    log.info("rebuild_app_wiki app_id=%s docs=%d concepts=%d", app_id, len(docs), total)
    return {"ok": True, "app_id": app_id, "docs": len(docs), "concepts": total}


async def _check_wiki_health(app_id: str) -> dict:
    """Lint the compiled wiki: orphan concepts (code) + contradictions (LLM).

    Stores a report on app.wiki_health = {contradictions, orphans, concept_count,
    checked_at}. Orphans are computed locally; contradictions via DSPy wiki_lint.
    """
    from sqlalchemy import select

    from app.db import AsyncSessionLocal
    from app.models.app import App
    from app.models.wiki import AppWikiConcept
    from app.services.skills.wiki_compiler.dspy_wiki import ConceptForLint, run_wiki_lint

    async with AsyncSessionLocal() as db:
        app = await db.get(App, UUID(app_id))
        if app is None:
            return {"ok": False, "error": "app_not_found"}

        concepts = (await db.execute(
            select(AppWikiConcept).where(AppWikiConcept.app_id == UUID(app_id))
        )).scalars().all()

        # Orphans (code): a concept nothing links to and which links to nothing.
        linked_to: set[str] = set()
        for c in concepts:
            linked_to.update(c.related_slugs or [])
        orphans = [
            {"slug": c.slug, "title": c.title}
            for c in concepts
            if not (c.related_slugs or []) and c.slug not in linked_to
        ]

        # Contradictions (LLM, skip when too few concepts to conflict).
        contradictions: list[dict] = []
        valid_slugs = {c.slug for c in concepts}
        if len(concepts) >= 2:
            try:
                concepts_payload = [
                    ConceptForLint(slug=c.slug, title=c.title, content_md=(c.content_md or "")[:4000])
                    for c in concepts
                ]
                result = await run_wiki_lint(app.name, concepts_payload)
                raw = result.get("contradictions", []) if isinstance(result, dict) else []
                contradictions = [
                    x for x in raw
                    if x.get("concept_a") in valid_slugs and x.get("concept_b") in valid_slugs
                ]
            except Exception as exc:  # noqa: BLE001
                log.warning("check_wiki_health lint failed app_id=%s error=%s", app_id, exc)

        app.wiki_health = {
            "contradictions": contradictions,
            "orphans": orphans,
            "concept_count": len(concepts),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.commit()

    log.info(
        "check_wiki_health app_id=%s concepts=%d contradictions=%d orphans=%d",
        app_id, len(concepts), len(contradictions), len(orphans),
    )
    return {"ok": True, "app_id": app_id, "contradictions": len(contradictions), "orphans": len(orphans)}


async def _rebuild_app_brain(app_id: str) -> dict:
    from sqlalchemy import select

    from app.db import AsyncSessionLocal
    from app.models.app import App
    from app.models.corpus import AppCorpusDoc

    async with AsyncSessionLocal() as db:
        app = await db.get(App, UUID(app_id))
        if app is None:
            return {"ok": False, "error": "app_not_found"}

        result = await db.execute(
            select(AppCorpusDoc)
            .where(
                AppCorpusDoc.app_id == UUID(app_id),
                AppCorpusDoc.index_status != "running",
            )
        )
        docs = result.scalars().all()

        for doc in docs:
            doc.index_status = "pending"
        await db.commit()

    # Ingest each doc sequentially
    docs_reindexed = 0
    for doc in docs:
        try:
            await _ingest_corpus_doc(str(doc.id))
            docs_reindexed += 1
        except Exception as exc:
            log.error("rebuild_app_brain doc_id=%s error=%s", doc.id, exc)

    fact_result = await _extract_app_facts(app_id)
    if not fact_result.get("ok"):
        log.error("rebuild_app_brain fact_extraction_failed app_id=%s error=%s", app_id, fact_result.get("error"))
    else:
        log.info("rebuild_app_brain fact_extraction app_id=%s facts_created=%d", app_id, fact_result.get("facts_created", 0))

    async with AsyncSessionLocal() as db:
        app = await db.get(App, UUID(app_id))
        if app:
            app.rebuild_status = None
            app.updated_at = datetime.now(timezone.utc)
            await db.commit()

    log.info("rebuild_app_brain app_id=%s docs_reindexed=%d", app_id, docs_reindexed)
    return {"ok": True, "app_id": app_id, "docs_reindexed": docs_reindexed}


async def _reset_stale_rebuild_status() -> dict:
    from sqlalchemy import select, update

    from app.db import AsyncSessionLocal
    from app.models.app import App

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=60)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            update(App)
            .where(App.rebuild_status == "rebuilding", App.updated_at < cutoff)
            .values(rebuild_status=None)
            .returning(App.id)
        )
        reset_ids = [str(r[0]) for r in result.all()]
        await db.commit()

    if reset_ids:
        log.warning("reset_stale_rebuild_status reset app_ids=%s", reset_ids)

    return {"ok": True, "reset_count": len(reset_ids)}


async def _ingest_project_source(document_id: str) -> dict:
    """Build a PageIndex reasoning tree for a project source document and store it."""
    try:
        UUID(document_id)
    except (ValueError, AttributeError):
        log.error("ingest_project_source invalid document_id=%s — skipping", document_id)
        return {"ok": False, "error": "invalid_document_id"}

    from sqlalchemy import delete

    from app.db import AsyncSessionLocal
    from app.models.document import Document
    from app.models.project_source import DocumentTree
    from app.services.corpus_index import get_corpus_index_provider
    from app.services.documents import storage

    async with AsyncSessionLocal() as db:
        doc = await db.get(Document, UUID(document_id))
        if doc is None:
            log.error("ingest_project_source document_id=%s not found", document_id)
            return {"ok": False, "error": "doc_not_found"}

        doc.indexing_status = "running"
        await db.commit()

        try:
            data = await storage.load(doc.storage_path)

            # PDF page count via fitz; non-PDF treated as a single logical page span.
            if doc.mime_type == "application/pdf":
                try:
                    import fitz
                    pdf = fitz.open(stream=data, filetype="pdf")
                    doc.page_count = len(pdf)
                    pdf.close()
                except Exception:
                    doc.page_count = 1

            provider = get_corpus_index_provider()
            result = await provider.build_index(
                data=data, content_type=doc.mime_type, filename=doc.filename
            )
            if doc.page_count is None:
                doc.page_count = len(result.page_texts) or 1

            await db.execute(delete(DocumentTree).where(DocumentTree.document_id == doc.id))
            db.add(DocumentTree(
                document_id=doc.id,
                project_id=doc.project_id,
                tree_json=result.tree,
                page_texts=result.page_texts,
                node_count=result.node_count,
                model=result.model,
            ))
            doc.indexing_status = "done"
            doc.index_error = None  # clear any stale error from a prior failed run
            await db.commit()
            log.info("ingest_project_source document_id=%s nodes=%d", document_id, result.node_count)
            return {"ok": True, "document_id": document_id, "nodes": result.node_count}

        except Exception as exc:
            # The session may be poisoned (e.g. the doc row was deleted mid-flight by
            # a concurrent cleanup → "0 rows matched"). Roll back, then best-effort
            # mark the doc errored in a fresh transaction; skip if it's gone.
            await db.rollback()
            log.error("ingest_project_source document_id=%s error=%s", document_id, exc)
            d2 = await db.get(Document, UUID(document_id))
            if d2 is None:
                return {"ok": False, "error": "doc_deleted_during_ingest"}
            d2.indexing_status = "error"
            d2.index_error = str(exc)[:1000]
            await db.commit()
            return {"ok": False, "error": str(exc)[:200]}


async def _recompute_triage() -> dict:
    from sqlalchemy import select

    from app.db import AsyncSessionLocal
    from app.models.user import User
    from app.services.portfolio.triage_service import compute_for_user

    async with AsyncSessionLocal() as db:
        user_ids = (
            await db.execute(select(User.id).where(User.status == "active"))
        ).scalars().all()
        for uid in user_ids:
            await compute_for_user(uid, db)

    log.info("recompute_triage users=%d", len(user_ids))
    return {"ok": True, "users": len(user_ids)}


async def _generate_concept_brief(project_id: str, artifact_type: str, context: str | None) -> dict:
    from uuid import UUID as _UUID
    from sqlalchemy import select as _select
    from app.db import AsyncSessionLocal
    from app.models.artifact import ArtifactDocument
    from app.models.project import Project
    from app.services.artifacts.orchestrator import generate_all

    async with AsyncSessionLocal() as db:
        project = await db.get(Project, _UUID(project_id))
        if project is None:
            log.error("generate_concept_brief project_id=%s not found", project_id)
            return {"ok": False, "error": "project_not_found"}
        try:
            await generate_all(project, artifact_type, db, context=context)
            return {"ok": True}
        except Exception:
            log.exception("generate_concept_brief failed project_id=%s", project_id)
            # Reset status so the user can retry
            async with AsyncSessionLocal() as db2:
                doc = (await db2.execute(
                    _select(ArtifactDocument).where(
                        ArtifactDocument.project_id == _UUID(project_id),
                        ArtifactDocument.artifact_type == artifact_type,
                    )
                )).scalar_one_or_none()
                if doc and doc.status == "generating":
                    doc.status = "in_interview"
                    await db2.commit()
            raise


async def _generate_ru(task, project_id: str) -> dict:
    try:
        UUID(project_id)
    except (ValueError, AttributeError):
        log.error("generate_requirement_understanding invalid project_id=%s", project_id)
        return {"ok": False, "error": "invalid_project_id"}

    from sqlalchemy import func, select

    from app.db import AsyncSessionLocal
    from app.models.document import Document
    from app.models.project import Project
    from app.services.llm import get_provider
    from app.services.understanding.orchestrator import generate

    async with AsyncSessionLocal() as db:
        if await db.get(Project, UUID(project_id)) is None:
            log.warning("generate_requirement_understanding project_not_found project_id=%s — skipping", project_id)
            return {"ok": False, "error": "project_not_found"}

        # Wait-free: if any source is still indexing, retry shortly so the RU sees
        # finished trees — but never block the wizard route.
        pending = await db.scalar(
            select(func.count(Document.id)).where(
                Document.project_id == UUID(project_id),
                Document.indexing_status.in_(("pending", "running")),
            )
        )
        if pending and task.request.retries < task.max_retries:
            raise task.retry(countdown=10)

        from sqlalchemy.exc import IntegrityError
        try:
            result = await generate(UUID(project_id), db, get_provider())
        except IntegrityError:
            # The project was deleted while this task ran (e.g. a queued backlog
            # for a since-purged project). Roll back and skip cleanly rather than
            # raising — a backlog of these must not produce a stack-trace storm.
            await db.rollback()
            log.warning("generate_requirement_understanding project_vanished project_id=%s — skipping", project_id)
            return {"ok": False, "error": "project_not_found"}

    log.info("generate_requirement_understanding project_id=%s ok=%s", project_id, result is not None)
    return {"ok": result is not None, "project_id": project_id}
