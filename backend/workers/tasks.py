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


# ── Project Wiki (E2 intelligent intake) ───────────────────────────────────────

@celery_app.task(name="workers.tasks.compile_project_wiki_for_doc")
def compile_project_wiki_for_doc(project_id: str, document_id: str) -> dict:
    return _run_async(_compile_project_wiki_for_doc(project_id, document_id))


@celery_app.task(name="workers.tasks.rebuild_project_wiki")
def rebuild_project_wiki(project_id: str) -> dict:
    return _run_async(_rebuild_project_wiki(project_id))


@celery_app.task(name="workers.tasks.check_project_wiki_health")
def check_project_wiki_health(project_id: str) -> dict:
    return _run_async(_check_project_wiki_health(project_id))


@celery_app.task(name="workers.tasks.run_project_clarification")
def run_project_clarification(project_id: str, trigger: str = "new_document") -> dict:
    return _run_async(_run_project_clarification(project_id, trigger))


async def _run_project_clarification(project_id: str, trigger: str) -> dict:
    from app.db import AsyncSessionLocal
    from app.services.understanding.clarifier import run_clarification

    async with AsyncSessionLocal() as db:
        try:
            items = await run_clarification(UUID(project_id), db, trigger=trigger)  # type: ignore[arg-type]
            return {"ok": True, "project_id": project_id, "items": len(items)}
        except Exception as exc:  # noqa: BLE001
            log.warning("run_project_clarification failed project_id=%s error=%s", project_id, exc)
            return {"ok": False, "error": str(exc)}


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
def generate_concept_brief(
    self, project_id: str, artifact_type: str,
    context: str | None = None, discover_context: str | None = None,
) -> dict:
    return _run_async(_generate_concept_brief(project_id, artifact_type, context, discover_context))


@celery_app.task(name="workers.tasks.incorporate_answer_task", bind=True, max_retries=1, default_retry_delay=5)
def incorporate_answer_task(
    self, project_id: str, artifact_type: str, question_seq: int | None = None,
) -> dict:
    return _run_async(_incorporate_answer_bg(project_id, artifact_type, question_seq))


@celery_app.task(name="workers.tasks.analyze_discover", bind=True, max_retries=2, default_retry_delay=10)
def analyze_discover(self, project_id: str, artifact_type: str, brief_text: str) -> dict:
    return _run_async(_analyze_discover_bg(project_id, artifact_type, brief_text))


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


# ── Project Wiki async implementations ──────────────────────────────────────────

def _project_wiki_scope():
    from app.models.project_wiki import ProjectWikiConcept, ProjectWikiSummary
    from app.services.wiki.compile_core import WikiScope
    return WikiScope(
        summary_model=ProjectWikiSummary,
        concept_model=ProjectWikiConcept,
        scope_col="project_id",
        summary_doc_col="document_id",
    )


async def _compile_one_project_doc(db, project, doc, settings) -> int:
    """Resolve a project document's tree + text and compile it into the project
    wiki via the shared compile core."""
    from sqlalchemy import select
    from app.models.project_source import DocumentTree
    from app.services.wiki.compile_core import compile_doc_into_wiki

    tree_row = (await db.execute(
        select(DocumentTree).where(DocumentTree.document_id == doc.id)
    )).scalar_one_or_none()
    tree_json = tree_row.tree_json if tree_row else None
    node_count = tree_row.node_count if tree_row else 0
    source_text = doc.extracted_text or ""

    return await compile_doc_into_wiki(
        db,
        scope_id=project.id,
        scope_name=project.name,
        doc_id=doc.id,
        doc_name=doc.filename,
        tree_json=tree_json,
        node_count=node_count,
        source_text=source_text,
        scope=_project_wiki_scope(),
        settings=settings,
    )


async def _compile_project_wiki_for_doc(project_id: str, document_id: str) -> dict:
    from sqlalchemy import select

    from app.config import get_settings
    from app.db import AsyncSessionLocal
    from app.models.document import Document
    from app.models.project import Project

    settings = get_settings()
    async with AsyncSessionLocal() as db:
        project = await db.get(Project, UUID(project_id))
        doc = await db.get(Document, UUID(document_id))
        if project is None or doc is None:
            log.error("compile_project_wiki_for_doc project=%s doc=%s not found", project_id, document_id)
            return {"ok": False, "error": "not_found"}

        project.wiki_status = "running"
        await db.commit()
        try:
            n = await _compile_one_project_doc(db, project, doc, settings)
            project.wiki_compiled_at = datetime.now(timezone.utc)
            project.wiki_status = "idle"
            await db.commit()
        except Exception as exc:
            await db.rollback()
            # Benign race: the project (or its document) can be deleted while we
            # compile — the LLM pass takes tens of seconds. Detect that and exit
            # quietly instead of emitting a scary FK-violation traceback. Use a
            # direct SELECT (not db.get, which is served from the identity map).
            still_exists = (await db.execute(
                select(Project.id).where(Project.id == UUID(project_id))
            )).scalar_one_or_none()
            if still_exists is None:
                log.info("compile_project_wiki_for_doc project_id=%s deleted mid-compile; skipping", project_id)
                return {"ok": False, "error": "project_deleted"}
            log.error("compile_project_wiki_for_doc project_id=%s error=%s", project_id, exc, exc_info=True)
            try:
                fresh = await db.get(Project, UUID(project_id))
                if fresh:
                    fresh.wiki_status = "idle"
                    await db.commit()
            except Exception:
                await db.rollback()
            return {"ok": False, "error": str(exc)}

    log.info("compile_project_wiki_for_doc project_id=%s document_id=%s concepts=%d", project_id, document_id, n)
    # Wiki is fresh → regenerate clarification questions (best-effort).
    try:
        from workers.dispatch import dispatch
        dispatch(run_project_clarification, project_id, "new_document")
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "project_id": project_id, "document_id": document_id, "concepts_touched": n}


async def _rebuild_project_wiki(project_id: str) -> dict:
    from sqlalchemy import delete as sa_delete, select

    from app.config import get_settings
    from app.db import AsyncSessionLocal
    from app.models.document import Document
    from app.models.project import Project
    from app.models.project_wiki import ProjectWikiConcept, ProjectWikiSummary

    settings = get_settings()
    async with AsyncSessionLocal() as db:
        project = await db.get(Project, UUID(project_id))
        if project is None:
            return {"ok": False, "error": "project_not_found"}

        project.wiki_status = "running"
        await db.commit()
        try:
            await db.execute(sa_delete(ProjectWikiConcept).where(ProjectWikiConcept.project_id == project.id))
            await db.execute(sa_delete(ProjectWikiSummary).where(ProjectWikiSummary.project_id == project.id))
            await db.flush()

            docs = (await db.execute(
                select(Document)
                .where(Document.project_id == project.id, Document.indexing_status == "done")
                .order_by(Document.created_at)
            )).scalars().all()

            total = 0
            for doc in docs:
                total += await _compile_one_project_doc(db, project, doc, settings)
                await db.flush()

            project.wiki_compiled_at = datetime.now(timezone.utc)
            project.wiki_status = "idle"
            await db.commit()
        except Exception as exc:
            await db.rollback()
            still_exists = (await db.execute(
                select(Project.id).where(Project.id == UUID(project_id))
            )).scalar_one_or_none()
            if still_exists is None:
                log.info("rebuild_project_wiki project_id=%s deleted mid-compile; skipping", project_id)
                return {"ok": False, "error": "project_deleted"}
            log.error("rebuild_project_wiki project_id=%s error=%s", project_id, exc, exc_info=True)
            try:
                fresh = await db.get(Project, UUID(project_id))
                if fresh:
                    fresh.wiki_status = "idle"
                    await db.commit()
            except Exception:
                await db.rollback()
            return {"ok": False, "error": str(exc)}

    log.info("rebuild_project_wiki project_id=%s docs=%d concepts=%d", project_id, len(docs), total)
    return {"ok": True, "project_id": project_id, "docs": len(docs), "concepts": total}


async def _check_project_wiki_health(project_id: str) -> dict:
    from sqlalchemy import select

    from app.db import AsyncSessionLocal
    from app.models.project import Project
    from app.models.project_wiki import ProjectWikiConcept
    from app.services.skills.wiki_compiler.dspy_wiki import ConceptForLint, run_wiki_lint

    async with AsyncSessionLocal() as db:
        project = await db.get(Project, UUID(project_id))
        if project is None:
            return {"ok": False, "error": "project_not_found"}

        concepts = (await db.execute(
            select(ProjectWikiConcept).where(ProjectWikiConcept.project_id == UUID(project_id))
        )).scalars().all()

        linked_to: set[str] = set()
        for c in concepts:
            linked_to.update(c.related_slugs or [])
        orphans = [
            {"slug": c.slug, "title": c.title}
            for c in concepts
            if not (c.related_slugs or []) and c.slug not in linked_to
        ]

        contradictions: list[dict] = []
        valid_slugs = {c.slug for c in concepts}
        if len(concepts) >= 2:
            try:
                payload = [
                    ConceptForLint(slug=c.slug, title=c.title, content_md=(c.content_md or "")[:4000])
                    for c in concepts
                ]
                result = await run_wiki_lint(project.name, payload)
                raw = result.get("contradictions", []) if isinstance(result, dict) else []
                contradictions = [
                    x for x in raw
                    if x.get("concept_a") in valid_slugs and x.get("concept_b") in valid_slugs
                ]
            except Exception as exc:  # noqa: BLE001
                log.warning("check_project_wiki_health lint failed project_id=%s error=%s", project_id, exc)

        project.wiki_health = {
            "contradictions": contradictions,
            "orphans": orphans,
            "concept_count": len(concepts),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.commit()

    log.info(
        "check_project_wiki_health project_id=%s concepts=%d contradictions=%d orphans=%d",
        project_id, len(concepts), len(contradictions), len(orphans),
    )
    return {"ok": True, "project_id": project_id, "contradictions": len(contradictions), "orphans": len(orphans)}


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


RICH_MIMES = frozenset({
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/png", "image/jpeg", "image/jpg",
    "image/gif", "image/webp", "image/tiff", "image/bmp",
})


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

            # For rich types (PDF, DOCX, images): convert to markdown via the
            # provider. Store in doc.extracted_text (project zone — never writes to
            # document_markdown which is the App Brain zone).
            # Commit conversion separately so a PageIndex failure can't roll it back —
            # this makes retries skip the expensive Azure call.
            if doc.mime_type in RICH_MIMES:
                if not doc.extracted_text:
                    from app.services.markdown_converter import get_markdown_provider
                    md_provider = get_markdown_provider()
                    markdown = await md_provider.convert(data, doc.mime_type, doc.filename)
                    doc.extracted_text = markdown
                    doc.parse_status = "done"
                    doc.parse_error = None
                    # Commit conversion before PageIndex so a tree-build failure
                    # can't roll back the (expensive) Azure result.
                    await db.commit()

                # For PDFs: feed raw bytes to page_index_main — it uses an LLM to
                # infer section structure directly from the PDF, which is more
                # intelligent than md_to_tree on headingless markdown (press releases,
                # flat reports). Azure markdown goes to extracted_text only.
                # For DOCX / images: no native PageIndex path, so use the markdown.
                if doc.mime_type == "application/pdf":
                    index_data = data
                    index_content_type = "application/pdf"
                else:
                    index_data = doc.extracted_text.encode("utf-8")
                    index_content_type = "text/markdown"
            else:
                # TXT/MD: extracted_text already set in sync upload phase
                index_data = (doc.extracted_text or "").encode("utf-8")
                index_content_type = "text/markdown"

            index_provider = get_corpus_index_provider()
            result = await index_provider.build_index(
                data=index_data,
                content_type=index_content_type,
                filename=doc.filename,
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
            doc.index_error = None
            project_id_str = str(doc.project_id)
            await db.commit()
            log.info("ingest_project_source document_id=%s nodes=%d", document_id, result.node_count)
            # Compile this doc into the Project Wiki (mirrors app-brain corpus ingest).
            compile_project_wiki_for_doc.delay(project_id_str, document_id)
            return {"ok": True, "document_id": document_id, "nodes": result.node_count}

        except Exception as exc:
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


async def _generate_concept_brief(
    project_id: str, artifact_type: str,
    context: str | None, discover_context: str | None = None,
) -> dict:
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
            await generate_all(project, artifact_type, db, context=context,
                               discover_context=discover_context)
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


async def _analyze_discover_bg(project_id: str, artifact_type: str, brief_text: str) -> dict:
    from uuid import UUID as _UUID
    from sqlalchemy import select
    from app.db import AsyncSessionLocal
    from app.models.artifact import ArtifactDocument
    from app.models.project import Project

    pid = _UUID(project_id)
    async with AsyncSessionLocal() as db:
        project = await db.get(Project, pid)
        if project is None:
            log.error("analyze_discover project_id=%s not found", project_id)
            return {"ok": False}
        try:
            from app.services.artifacts.discover import analyze_brief
            await analyze_brief(project, artifact_type, brief_text, db)
        except Exception:
            log.exception("analyze_discover failed project_id=%s", project_id)
            raise
        finally:
            doc = (await db.execute(
                select(ArtifactDocument).where(
                    ArtifactDocument.project_id == pid,
                    ArtifactDocument.artifact_type == artifact_type,
                )
            )).scalar_one_or_none()
            if doc is not None:
                doc.discover_analyzing = False
                await db.commit()
    return {"ok": True}


async def _incorporate_answer_bg(
    project_id: str, artifact_type: str, question_seq: int | None,
) -> dict:
    from uuid import UUID as _UUID
    from app.services.artifacts.orchestrator import run_regeneration

    try:
        await run_regeneration(_UUID(project_id), artifact_type, question_seq)
        return {"ok": True}
    except Exception:
        log.exception("incorporate_answer_task failed project_id=%s", project_id)
        raise


# ── BRD generation ────────────────────────────────────────────────────────────

@celery_app.task(name="workers.tasks.generate_brd", bind=True, max_retries=2, default_retry_delay=10)
def generate_brd(
    self, project_id: str, context: str | None = None, discover_context: str | None = None,
) -> dict:
    return _run_async(_generate_brd(project_id, context, discover_context))


@celery_app.task(name="workers.tasks.incorporate_brd_answer_task", bind=True, max_retries=1, default_retry_delay=5)
def incorporate_brd_answer_task(
    self, project_id: str, question_seq: int | None = None,
) -> dict:
    return _run_async(_incorporate_brd_answer_bg(project_id, question_seq))


async def _generate_brd(
    project_id: str, context: str | None, discover_context: str | None,
) -> dict:
    from uuid import UUID as _UUID
    from sqlalchemy import select as _select
    from app.db import AsyncSessionLocal
    from app.models.artifact import ArtifactDocument
    from app.models.project import Project
    from app.services.artifacts.brd_orchestrator import generate_brd_all

    async with AsyncSessionLocal() as db:
        project = await db.get(Project, _UUID(project_id))
        if project is None:
            log.error("generate_brd project_id=%s not found", project_id)
            return {"ok": False, "error": "project_not_found"}
        try:
            await generate_brd_all(project, db, context=context, discover_context=discover_context)
            return {"ok": True}
        except Exception:
            log.exception("generate_brd failed project_id=%s", project_id)
            async with AsyncSessionLocal() as db2:
                doc = (await db2.execute(
                    _select(ArtifactDocument).where(
                        ArtifactDocument.project_id == _UUID(project_id),
                        ArtifactDocument.artifact_type == "brd",
                    )
                )).scalar_one_or_none()
                if doc and doc.status == "generating":
                    doc.status = "in_interview"
                    await db2.commit()
            raise


async def _incorporate_brd_answer_bg(project_id: str, question_seq: int | None) -> dict:
    from uuid import UUID as _UUID
    from app.services.artifacts.brd_orchestrator import run_brd_regeneration
    try:
        await run_brd_regeneration(_UUID(project_id), question_seq)
        return {"ok": True}
    except Exception:
        log.exception("incorporate_brd_answer_task failed project_id=%s", project_id)
        raise


# ── FRS generation ────────────────────────────────────────────────────────────

@celery_app.task(name="workers.tasks.generate_frs", bind=True, max_retries=2, default_retry_delay=10)
def generate_frs(self, project_id: str, brief: str | None = None) -> dict:
    return _run_async(_generate_frs(project_id, brief))


async def _generate_frs(project_id: str, brief: str | None) -> dict:
    from uuid import UUID as _UUID
    from sqlalchemy import select as _select
    from app.db import AsyncSessionLocal
    from app.models.artifact import ArtifactDocument
    from app.models.project import Project
    from app.services.artifacts.frs_orchestrator import generate_frs_all

    async with AsyncSessionLocal() as db:
        project = await db.get(Project, _UUID(project_id))
        if project is None:
            log.error("generate_frs project_id=%s not found", project_id)
            return {"ok": False, "error": "project_not_found"}
        try:
            await generate_frs_all(project, db, brief=brief)
            return {"ok": True}
        except Exception:
            log.exception("generate_frs failed project_id=%s", project_id)
            # Reset stuck status so the user isn't trapped in 'generating'
            async with AsyncSessionLocal() as db2:
                doc = (await db2.execute(
                    _select(ArtifactDocument).where(
                        ArtifactDocument.project_id == _UUID(project_id),
                        ArtifactDocument.artifact_type == "frs",
                    )
                )).scalar_one_or_none()
                if doc and doc.status == "generating":
                    doc.status = "in_interview"
                    await db2.commit()
            raise


# ── NFR Celery tasks ─────────────────────────────────────────────────────────

@celery_app.task(name="workers.tasks.generate_nfr", bind=True, max_retries=2, default_retry_delay=10)
def generate_nfr(self, project_id: str, brief: str | None = None) -> dict:
    return _run_async(_generate_nfr(project_id, brief))


async def _generate_nfr(project_id: str, brief: str | None) -> dict:
    from uuid import UUID as _UUID
    from sqlalchemy import select as _select
    from app.db import AsyncSessionLocal
    from app.models.artifact import ArtifactDocument
    from app.services.artifacts.nfr_orchestrator import run_nfr_generation

    try:
        await run_nfr_generation(_UUID(project_id), brief)
        return {"ok": True}
    except Exception:
        log.exception("generate_nfr failed project_id=%s", project_id)
        async with AsyncSessionLocal() as db2:
            doc = (await db2.execute(
                _select(ArtifactDocument).where(
                    ArtifactDocument.project_id == _UUID(project_id),
                    ArtifactDocument.artifact_type == "nfr",
                )
            )).scalar_one_or_none()
            if doc and doc.status == "generating":
                doc.status = "in_interview"
                await db2.commit()
        raise


@celery_app.task(name="workers.tasks.regenerate_nfr_unit", bind=True, max_retries=2, default_retry_delay=10)
def regenerate_nfr_unit(self, project_id: str, unit_key: str) -> dict:
    return _run_async(_regenerate_nfr_unit(project_id, unit_key))


async def _regenerate_nfr_unit(project_id: str, unit_key: str) -> dict:
    from uuid import UUID as _UUID
    from app.services.artifacts.nfr_orchestrator import regenerate_nfr_unit as _regen
    try:
        await _regen(_UUID(project_id), unit_key)
        return {"ok": True}
    except Exception:
        log.exception("regenerate_nfr_unit failed project_id=%s unit=%s", project_id, unit_key)
        raise


# ── Stage B Celery tasks ─────────────────────────────────────────────────────


@celery_app.task(name="workers.tasks.regenerate_frs_module", bind=True, max_retries=2,
                 default_retry_delay=30, time_limit=1800, soft_time_limit=1740)
def regenerate_frs_module(self, project_id: str, module_row_key: str) -> dict:
    # A module designs its specs sequentially, each capped at ~120s on Vertex.
    # A large module (10-15 specs) can take 20-25 min; allow 30 min (1800s).
    return _run_async(_regenerate_frs_module(project_id, module_row_key))


async def _regenerate_frs_module(project_id: str, module_row_key: str) -> dict:
    from uuid import UUID as _UUID
    from sqlalchemy import select as _select
    from app.db import AsyncSessionLocal
    from app.models.artifact import ArtifactDocument
    from app.models.project import Project
    from app.services.artifacts.frs_orchestrator import generate_frs_design_module
    from app.services.context.project_context import gather_project_context

    async with AsyncSessionLocal() as db:
        project = await db.get(Project, _UUID(project_id))
        if project is None:
            log.error("regenerate_frs_module project_id=%s not found", project_id)
            return {"ok": False, "error": "project_not_found"}
        doc = (await db.execute(
            _select(ArtifactDocument).where(
                ArtifactDocument.project_id == _UUID(project_id),
                ArtifactDocument.artifact_type == "frs",
            )
        )).scalar_one_or_none()
        if doc is None:
            return {"ok": False, "error": "frs_doc_not_found"}
        try:
            bundle = await gather_project_context(
                project.id, db,
                artifact_document_id=doc.id, artifact_type="frs",
            )
            await generate_frs_design_module(
                project, module_row_key, doc, bundle, db,
            )
            await db.commit()
            return {"ok": True, "module_row_key": module_row_key}
        except Exception:
            log.exception("regenerate_frs_module failed project_id=%s module=%s",
                          project_id, module_row_key)
            # Self-heal so the user isn't trapped: clear the _current_unit pointer
            # (which pins the frontend overlay open) and reset a stuck status.
            from sqlalchemy import text as _text
            async with AsyncSessionLocal() as db2:
                rd = (await db2.execute(
                    _select(ArtifactDocument).where(
                        ArtifactDocument.project_id == _UUID(project_id),
                        ArtifactDocument.artifact_type == "frs",
                    )
                )).scalar_one_or_none()
                if rd:
                    await db2.execute(_text(
                        "UPDATE artifact_documents "
                        "SET unit_status = COALESCE(unit_status, '{}'::jsonb) || '{\"_current_unit\": null}'::jsonb, "
                        "    status = CASE WHEN status = 'generating' THEN 'in_interview' ELSE status END, "
                        "    updated_at = NOW() "
                        "WHERE id = :doc_id"
                    ), {"doc_id": str(rd.id)})
                    await db2.commit()
            raise


@celery_app.task(name="workers.tasks.regenerate_frs_spec", bind=True, max_retries=2,
                 default_retry_delay=30, time_limit=480, soft_time_limit=420)
def regenerate_frs_spec(self, project_id: str, spec_row_key: str, scope: str = "full") -> dict:
    return _run_async(_regenerate_frs_spec(project_id, spec_row_key, scope))


async def _regenerate_frs_spec(project_id: str, spec_row_key: str, scope: str) -> dict:
    from uuid import UUID as _UUID
    from sqlalchemy import select as _select
    from app.db import AsyncSessionLocal
    from app.models.artifact import ArtifactDocument
    from app.models.project import Project
    from app.services.artifacts.frs_orchestrator import (
        regenerate_frs_spec as orch_regen,
    )
    from app.services.context.project_context import gather_project_context

    async with AsyncSessionLocal() as db:
        project = await db.get(Project, _UUID(project_id))
        if project is None:
            return {"ok": False, "error": "project_not_found"}
        doc = (await db.execute(
            _select(ArtifactDocument).where(
                ArtifactDocument.project_id == _UUID(project_id),
                ArtifactDocument.artifact_type == "frs",
            )
        )).scalar_one_or_none()
        if doc is None:
            return {"ok": False, "error": "frs_doc_not_found"}
        try:
            bundle = await gather_project_context(
                project.id, db,
                artifact_document_id=doc.id, artifact_type="frs",
            )
            await orch_regen(project, spec_row_key, db, scope=scope, bundle=bundle)
            await db.commit()
            return {"ok": True, "spec_row_key": spec_row_key, "scope": scope}
        except Exception:
            log.exception(
                "regenerate_frs_spec failed project_id=%s spec=%s scope=%s",
                project_id, spec_row_key, scope,
            )
            async with AsyncSessionLocal() as db2:
                rd = (await db2.execute(
                    _select(ArtifactDocument).where(
                        ArtifactDocument.project_id == _UUID(project_id),
                        ArtifactDocument.artifact_type == "frs",
                    )
                )).scalar_one_or_none()
                if rd and rd.status == "generating":
                    rd.status = "in_interview"
                    await db2.commit()
            raise


@celery_app.task(name="workers.tasks.incorporate_frs_answer", bind=True, max_retries=2, default_retry_delay=10)
def incorporate_frs_answer(self, project_id: str, target_spec_row_key: str | None = None) -> dict:
    return _run_async(_incorporate_frs_answer(project_id, target_spec_row_key))


async def _incorporate_frs_answer(project_id: str, target_spec_row_key: str | None) -> dict:
    """User answered a free-text refinement question; re-run the affected spec(s).

    If target_spec_row_key is provided, regen that one spec. Otherwise we currently
    no-op (broader re-modularization is reserved for future work).
    """
    if target_spec_row_key is None:
        log.info("incorporate_frs_answer no target_spec_row_key — skipping regen")
        return {"ok": True, "noop": True}
    return await _regenerate_frs_spec(project_id, target_spec_row_key, "full")


@celery_app.task(
    name="workers.tasks.design_all_frs_modules",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
    time_limit=3600,
    soft_time_limit=3540,
)
def design_all_frs_modules(
    self, project_id: str, skip_designed: bool = True,
) -> dict:
    """Design all (or remaining) FRS modules in parallel (Semaphore=3).

    skip_designed=True: modules with completeness > 0 are skipped, making
    this safe to use as a "Design Remaining" action after partial completion.
    """
    return _run_async(_design_all_frs_modules(project_id, skip_designed))


async def _design_all_frs_modules(project_id: str, skip_designed: bool) -> dict:
    from uuid import UUID as _UUID
    from sqlalchemy import select as _select
    from app.db import AsyncSessionLocal
    from app.models.artifact import ArtifactDocument
    from app.models.project import Project
    from app.services.artifacts.frs_orchestrator import run_frs_stage_b

    async with AsyncSessionLocal() as db:
        project = await db.get(Project, _UUID(project_id))
        if project is None:
            log.error("design_all_frs_modules project_id=%s not found", project_id)
            return {"ok": False, "error": "project_not_found"}
        try:
            await run_frs_stage_b(project, db, skip_designed=skip_designed)
            return {"ok": True}
        except Exception:
            log.exception(
                "design_all_frs_modules failed project_id=%s", project_id,
            )
            async with AsyncSessionLocal() as db2:
                doc = (await db2.execute(
                    _select(ArtifactDocument).where(
                        ArtifactDocument.project_id == _UUID(project_id),
                        ArtifactDocument.artifact_type == "frs",
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


# ── Project Copilot (Ask the Project) ────────────────────────────────────────

@celery_app.task(
    name="workers.tasks.run_project_chat",
    bind=True,
    max_retries=0,
    time_limit=300,
    soft_time_limit=270,
)
def run_project_chat(
    self,
    project_id: str,
    project_name: str,
    question: str,
    history_json: list,
    stream_key: str,
) -> dict:
    """Run the ProjectChatAgent loop in the worker, publishing each SSE event to a
    Redis Stream. The /ask POST endpoint tails that stream and forwards events to
    the browser. Search is heavy (multiple Vertex calls) so it runs off the API."""
    return _run_async(
        _run_project_chat(project_id, project_name, question, history_json, stream_key)
    )


async def _run_project_chat(
    project_id: str,
    project_name: str,
    question: str,
    history_json: list,
    stream_key: str,
) -> dict:
    import json as _json
    from uuid import UUID

    from redis.asyncio import Redis

    from app.config import get_settings
    from app.db import AsyncSessionLocal
    from app.services.rag.project_agent import ProjectChatAgent

    # IMPORTANT: create a Redis client bound to THIS task's event loop. Celery prefork
    # runs each task in a fresh asyncio.run() loop, so the process-level get_redis()
    # singleton would be bound to a dead loop ("got Future attached to a different loop").
    redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    redis_key = f"ask:{stream_key}"
    status_key = f"ask_status:{stream_key}"
    _TTL = 1800  # 30 min

    async def _pub(event: dict) -> None:
        await redis.xadd(redis_key, {"e": _json.dumps(event)}, maxlen=1000)
        await redis.expire(redis_key, _TTL)

    n = 0
    log.info("run_project_chat START stream_key=%s q=%r", stream_key, question[:80])
    try:
        await redis.setex(status_key, _TTL, "running")
        async with AsyncSessionLocal() as db:
            async for event in ProjectChatAgent().stream_answer(
                project_id=UUID(project_id),
                project_name=project_name,
                question=question,
                db=db,
                history=history_json,
            ):
                await _pub(event)
                n += 1
                etype = event.get("type")
                if etype in ("step", "error"):
                    log.info("run_project_chat stream_key=%s [%s] %s",
                             stream_key, etype, (event.get("text") or event.get("message") or "")[:80])
                if etype in ("done", "error"):
                    await redis.setex(status_key, _TTL, etype)
                    log.info("run_project_chat END stream_key=%s events=%d status=%s", stream_key, n, etype)
                    return {"ok": True, "stream_key": stream_key, "events": n}
        await redis.setex(status_key, _TTL, "done")
        log.info("run_project_chat END stream_key=%s events=%d (no explicit done)", stream_key, n)
        return {"ok": True, "stream_key": stream_key, "events": n}
    except Exception as exc:
        log.error("run_project_chat FAILED stream_key=%s: %s", stream_key, exc, exc_info=True)
        try:
            await _pub({"type": "error", "message": "Agent task failed. Please try again."})
            await _pub({"type": "done"})
            await redis.setex(status_key, _TTL, "error")
        except Exception:
            pass
        return {"ok": False, "stream_key": stream_key, "events": n}
    finally:
        # Close this task's Redis connection so it isn't left bound to the loop we dispose.
        try:
            await redis.aclose()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# Test Cases (E3) — Stage A (plan_journeys) + Stage B (author_plan per spec)
# ═══════════════════════════════════════════════════════════════════════════════

import contextlib as _contextlib


@_contextlib.asynccontextmanager
async def _tc_project_lock(project_id: str):
    """Per-project Redis lock so only ONE test-case generation runs at a time.

    Celery prefork has multiple worker processes, so duplicate queued tasks could
    otherwise run concurrently on the same project — each resetting progress and
    re-authoring (the '16/34 → 0/34' stomp). Duplicates that can't acquire the
    lock skip. Degrades to no-lock if Redis is unreachable. TTL bounds a crashed
    holder; released in finally on the happy + error paths.
    """
    from redis.asyncio import Redis
    from app.config import get_settings
    import uuid as _uuid

    redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    key = f"tc_gen_lock:{project_id}"
    token = _uuid.uuid4().hex
    owned = False
    try:
        try:
            owned = bool(await redis.set(key, token, nx=True, ex=3600))
            acquired = owned
        except Exception:
            acquired = True  # Redis unavailable → don't block generation
        yield acquired
    finally:
        if owned:
            try:
                if (await redis.get(key)) == token:
                    await redis.delete(key)
            except Exception:
                pass
        try:
            await redis.aclose()
        except Exception:
            pass


async def _reset_tc_status_if_stuck(project_id: str) -> None:
    from uuid import UUID as _UUID
    from sqlalchemy import select as _select
    from app.db import AsyncSessionLocal
    from app.models.artifact import ArtifactDocument
    async with AsyncSessionLocal() as db2:
        doc = (await db2.execute(
            _select(ArtifactDocument).where(
                ArtifactDocument.project_id == _UUID(project_id),
                ArtifactDocument.artifact_type == "test_cases",
            )
        )).scalar_one_or_none()
        if doc and doc.status == "generating":
            doc.status = "in_interview"
            await db2.commit()


@celery_app.task(name="workers.tasks.generate_test_cases", bind=True, max_retries=0,
                 time_limit=5400, soft_time_limit=5340)
def generate_test_cases(self, project_id: str) -> dict:
    return _run_async(_generate_test_cases(project_id))


async def _generate_test_cases(project_id: str) -> dict:
    from uuid import UUID as _UUID
    from app.db import AsyncSessionLocal
    from app.models.project import Project
    from app.services.artifacts.tc_orchestrator import generate_tc_all

    async with _tc_project_lock(project_id) as acquired:
        if not acquired:
            log.warning("generate_test_cases skipped — generation already running for %s", project_id)
            return {"ok": True, "skipped": "already_running"}
        async with AsyncSessionLocal() as db:
            project = await db.get(Project, _UUID(project_id))
            if project is None:
                log.error("generate_test_cases project_id=%s not found", project_id)
                return {"ok": False, "error": "project_not_found"}
            try:
                await generate_tc_all(project, db, run_stage_b=True)
                return {"ok": True}
            except Exception:
                log.exception("generate_test_cases failed project_id=%s", project_id)
                await _reset_tc_status_if_stuck(project_id)
                raise


@celery_app.task(name="workers.tasks.design_all_test_plans", bind=True, max_retries=0,
                 time_limit=5400, soft_time_limit=5340)
def design_all_test_plans(self, project_id: str, skip_designed: bool = True,
                          module_row_key: str | None = None) -> dict:
    return _run_async(_design_all_test_plans(project_id, skip_designed, module_row_key))


async def _design_all_test_plans(project_id: str, skip_designed: bool,
                                 module_row_key: str | None = None) -> dict:
    from uuid import UUID as _UUID
    from app.db import AsyncSessionLocal
    from app.models.project import Project
    from app.services.artifacts.tc_orchestrator import run_tc_stage_b

    async with _tc_project_lock(project_id) as acquired:
        if not acquired:
            log.warning("design_all_test_plans skipped — generation already running for %s", project_id)
            return {"ok": True, "skipped": "already_running"}
        async with AsyncSessionLocal() as db:
            project = await db.get(Project, _UUID(project_id))
            if project is None:
                return {"ok": False, "error": "project_not_found"}
            try:
                await run_tc_stage_b(project, db, skip_designed=skip_designed, module_row_key=module_row_key)
                return {"ok": True}
            except Exception:
                log.exception("design_all_test_plans failed project_id=%s", project_id)
                await _reset_tc_status_if_stuck(project_id)
                raise


@celery_app.task(name="workers.tasks.regenerate_test_cases_plan", bind=True, max_retries=2,
                 default_retry_delay=30, time_limit=900, soft_time_limit=840)
def regenerate_test_cases_plan(self, project_id: str, spec_row_key: str) -> dict:
    return _run_async(_regenerate_test_cases_plan(project_id, spec_row_key))


async def _regenerate_test_cases_plan(project_id: str, spec_row_key: str) -> dict:
    from uuid import UUID as _UUID
    from app.db import AsyncSessionLocal
    from app.models.project import Project
    from app.services.artifacts.tc_orchestrator import regenerate_tc_plan

    async with AsyncSessionLocal() as db:
        project = await db.get(Project, _UUID(project_id))
        if project is None:
            return {"ok": False, "error": "project_not_found"}
        try:
            await regenerate_tc_plan(project, spec_row_key, db)
            return {"ok": True}
        except Exception:
            log.exception("regenerate_test_cases_plan failed project_id=%s spec=%s", project_id, spec_row_key)
            raise


@celery_app.task(name="workers.tasks.regen_thin_test_cases", bind=True, max_retries=0,
                 time_limit=5400, soft_time_limit=5340)
def regen_thin_test_cases(self, project_id: str) -> dict:
    """Re-author only the specs that still fail validation (the 'thin' ones).

    The API runs cleanup_tc_refs inline before dispatching this, so by the time
    we run, orphan_case is already cleared and the only remaining regen-fixable
    findings are richness/coverage gaps — exactly the specs we re-author here.
    """
    return _run_async(_regen_thin_test_cases(project_id))


async def _regen_thin_test_cases(project_id: str) -> dict:
    from uuid import UUID as _UUID
    from app.db import AsyncSessionLocal
    from app.models.project import Project
    from app.services.artifacts.tc_orchestrator import regen_thin_tc

    async with _tc_project_lock(project_id) as acquired:
        if not acquired:
            log.warning("regen_thin_test_cases skipped — generation already running for %s", project_id)
            return {"ok": True, "skipped": "already_running"}
        async with AsyncSessionLocal() as db:
            project = await db.get(Project, _UUID(project_id))
            if project is None:
                return {"ok": False, "error": "project_not_found"}
            try:
                await regen_thin_tc(project, db)
                return {"ok": True}
            except Exception:
                log.exception("regen_thin_test_cases failed project_id=%s", project_id)
                await _reset_tc_status_if_stuck(project_id)
                raise


@celery_app.task(name="workers.tasks.gap_fill_test_cases", bind=True, max_retries=0,
                 time_limit=5400, soft_time_limit=5340)
def gap_fill_test_cases(self, project_id: str, spec_row_key: str | None = None) -> dict:
    return _run_async(_gap_fill_test_cases(project_id, spec_row_key))


async def _gap_fill_test_cases(project_id: str, spec_row_key: str | None = None) -> dict:
    from uuid import UUID as _UUID
    from app.db import AsyncSessionLocal
    from app.models.project import Project
    from app.services.artifacts.tc_orchestrator import gap_fill_tc

    async with _tc_project_lock(project_id) as acquired:
        if not acquired:
            log.warning("gap_fill_test_cases skipped — generation already running for %s", project_id)
            return {"ok": True, "skipped": "already_running"}
        async with AsyncSessionLocal() as db:
            project = await db.get(Project, _UUID(project_id))
            if project is None:
                return {"ok": False, "error": "project_not_found"}
            try:
                await gap_fill_tc(project, db, spec_row_key=spec_row_key)
                return {"ok": True}
            except Exception:
                log.exception("gap_fill_test_cases failed project_id=%s", project_id)
                await _reset_tc_status_if_stuck(project_id)
                raise
