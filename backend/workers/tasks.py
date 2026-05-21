import asyncio
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from workers.celery_app import celery_app

log = logging.getLogger(__name__)


# ── Utility tasks ─────────────────────────────────────────────────────────────

@celery_app.task(name="workers.tasks.ping", bind=True)
def ping(self) -> dict:
    log.info("ping task executed task_id=%s", self.request.id)
    return {"ok": True, "ts": datetime.now(timezone.utc).isoformat()}


@celery_app.task(name="workers.tasks.purge_expired_refresh_tokens")
def purge_expired_refresh_tokens() -> dict:
    return asyncio.run(_purge_expired_tokens())


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
    return asyncio.run(_ingest_corpus_doc(doc_id))


@celery_app.task(name="workers.tasks.extract_app_facts")
def extract_app_facts(app_id: str) -> dict:
    return asyncio.run(_extract_app_facts(app_id))


@celery_app.task(name="workers.tasks.rebuild_app_brain")
def rebuild_app_brain(app_id: str) -> dict:
    return asyncio.run(_rebuild_app_brain(app_id))


@celery_app.task(name="workers.tasks.reset_stale_rebuild_status")
def reset_stale_rebuild_status() -> dict:
    return asyncio.run(_reset_stale_rebuild_status())


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

            # Parse text
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

            doc.index_status = "done"
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

    return {"ok": True, "doc_id": doc_id, "chunks": len(chunks)}


async def _extract_app_facts(app_id: str) -> dict:
    from sqlalchemy import select

    from app.config import get_settings
    from app.db import AsyncSessionLocal
    from app.models.app import App
    from app.models.corpus import AppChunk, AppCorpusDoc
    from app.models.fact import AppFact
    from app.services.llm import get_provider as get_llm_provider
    from app.services.skills.skill_engine import SkillEngine

    settings = get_settings()
    max_chunks = settings.fact_extract_max_chunks

    async with AsyncSessionLocal() as db:
        app = await db.get(App, UUID(app_id))
        if app is None:
            log.error("extract_app_facts app_id=%s not found", app_id)
            return {"ok": False, "error": "app_not_found"}

        # Load chunks across all docs for this app
        result = await db.execute(
            select(AppChunk)
            .join(AppCorpusDoc, AppChunk.doc_id == AppCorpusDoc.id)
            .where(AppCorpusDoc.app_id == UUID(app_id))
            .order_by(AppCorpusDoc.id, AppChunk.chunk_no)
            .limit(max_chunks)
        )
        chunks = result.scalars().all()

        if not chunks:
            log.info("extract_app_facts app_id=%s no chunks found", app_id)
            return {"ok": True, "facts_created": 0, "app_id": app_id}

        # Build context text (truncate to 50k chars)
        doc_names: dict[str, str] = {}
        for chunk in chunks:
            doc_result = await db.get(AppCorpusDoc, chunk.doc_id)
            if doc_result:
                doc_names[str(chunk.doc_id)] = doc_result.name

        parts = []
        for chunk in chunks:
            doc_name = doc_names.get(str(chunk.doc_id), "Unknown")
            parts.append(f"--- [doc: {doc_name}, chunk {chunk.chunk_no}] ---\n{chunk.text}")
        chunk_text = "\n\n".join(parts)[:50_000]

        # Run fact_extractor skill
        provider = get_llm_provider()
        engine = SkillEngine()
        try:
            result_data = await engine.run(
                "fact_extractor",
                {"app_name": app.name, "chunk_text": chunk_text},
                provider,
            )
        except Exception as exc:
            log.error("extract_app_facts skill_error app_id=%s error=%s", app_id, exc)
            return {"ok": False, "error": str(exc)}

        facts_list = result_data.get("facts", []) if isinstance(result_data, dict) else []

        # Upsert facts — skip duplicates by normalized kind+text
        existing_result = await db.execute(
            select(AppFact).where(AppFact.app_id == UUID(app_id), AppFact.status == "active")
        )
        existing_facts = existing_result.scalars().all()
        existing_keys = {(f.kind, f.text.strip().lower()) for f in existing_facts}

        facts_created = 0
        for fact_data in facts_list:
            key = (fact_data["kind"], fact_data["text"].strip().lower())
            if key in existing_keys:
                continue
            db.add(AppFact(
                app_id=UUID(app_id),
                kind=fact_data["kind"],
                text=fact_data["text"],
                source_ref=fact_data.get("source_ref"),
                confidence=fact_data["confidence"],
                status="active",
                chunk_ids=[],
            ))
            existing_keys.add(key)
            facts_created += 1

        from datetime import timezone
        app.updated_at = datetime.now(timezone.utc)
        await db.commit()

    log.info("extract_app_facts app_id=%s facts_created=%d", app_id, facts_created)
    return {"ok": True, "facts_created": facts_created, "app_id": app_id}


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

    await _extract_app_facts(app_id)

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
