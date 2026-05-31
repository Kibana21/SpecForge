"""Project Copilot API — agentic vectorless chat over the project's PageIndex trees,
wiki concepts, and app facts.

Transport: ONE streaming SSE POST (the proven pattern that flushes through the dev
proxy). Compute: the heavy agent search runs in a Celery worker; the POST tails the
worker's Redis Stream and forwards each event. Mock/test mode runs the agent inline
(no worker needed). Heartbeat comments keep the proxy alive during slow Vertex calls.

See .claude/plans/E2-ask-the-project.md.
"""
import asyncio
import hashlib
import json
import logging
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_project_or_404
from app.core import audit
from app.db import get_db
from app.limiter import limiter
from app.models.project import Project
from app.models.project_ask_session import ProjectAskSession
from app.models.user import User
from app.schemas.app import AskSessionRead, AskSessionSave
from app.schemas.envelope import err, ok
from app.schemas.project import ProjectAskRequest

log = logging.getLogger(__name__)

router = APIRouter(tags=["project-ask"])

_HEARTBEAT_INTERVAL = 8.0   # seconds between keep-alive pings (prevents proxy ECONNRESET)
_POLL_BLOCK_MS = 2000       # Redis XREAD block window when tailing the worker stream
_MAX_WAIT_S = 300           # hard cap on a single answer (matches the task time_limit)


# ── Ask (single streaming SSE POST) ───────────────────────────────────────────

@router.post("/projects/{project_id}/ask")
@limiter.limit("20/minute")
async def ask_project(
    request: Request,
    body: ProjectAskRequest,
    project: Project = Depends(get_project_or_404),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream an agentic answer over the project's knowledge base.

    The agent navigates PageIndex reasoning trees (S: section tokens), the Project
    Wiki (C: concept tokens), and linked App Brain facts (F: fact tokens). Each
    S:/C:/F: token in the answer resolves via the existing IntakeTraceChip popovers.
    """
    from app.config import get_settings

    question_hash = hashlib.sha256(body.question.encode()).hexdigest()
    await audit.emit(
        db,
        event="project.ask",
        actor_id=str(user.id),
        metadata={"project_id": str(project.id), "question_hash": question_hash},
    )
    await db.commit()

    project_id = project.id
    project_name = project.name
    history_json = [t.model_dump() for t in body.history]
    question = body.question
    is_mock = get_settings().llm_provider == "mock"

    # ── inline path (mock/tests, or worker unavailable) ──────────────────────
    async def _inline():
        from app.services.rag.project_agent import ProjectChatAgent
        agent = ProjectChatAgent()
        event_iter = agent.stream_answer(
            project_id=project_id, project_name=project_name,
            question=question, db=db, history=history_json,
        )
        while True:
            try:
                event = await asyncio.wait_for(event_iter.__anext__(), timeout=_HEARTBEAT_INTERVAL)
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") in ("done", "error"):
                    break
            except StopAsyncIteration:
                break
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"

    # ── worker path (real): dispatch to Celery, tail the Redis stream ────────
    async def _tail_worker(stream_key: str):
        from app.core.redis_client import get_redis
        redis = get_redis()
        redis_key = f"ask:{stream_key}"
        status_key = f"ask_status:{stream_key}"
        last_id = "0"
        loop = asyncio.get_running_loop()
        start = loop.time()
        forwarded = 0
        log.info("ask tail START stream_key=%s", stream_key)

        while True:
            if loop.time() - start > _MAX_WAIT_S:
                log.warning("ask tail TIMEOUT stream_key=%s after %ss", stream_key, _MAX_WAIT_S)
                yield f"data: {json.dumps({'type': 'error', 'message': 'The request timed out. Please try again.'})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return

            # Natural block (no wait_for wrapper → no cancelled-command corruption).
            results = await redis.xread({redis_key: last_id}, block=_POLL_BLOCK_MS, count=50)
            if not results:
                # No new events this window — verify the task hasn't died silently.
                status = await redis.get(status_key)
                if status in ("done", "error") and last_id != "0":
                    log.info("ask tail END stream_key=%s forwarded=%d (status=%s)", stream_key, forwarded, status)
                    return
                yield ": heartbeat\n\n"
                continue

            for _, messages in results:
                for msg_id, fields in messages:
                    last_id = msg_id if isinstance(msg_id, str) else msg_id.decode()
                    raw = fields.get("e") or fields.get(b"e") or "{}"
                    yield f"data: {raw}\n\n"
                    forwarded += 1
                    try:
                        if json.loads(raw).get("type") in ("done", "error"):
                            log.info("ask tail END stream_key=%s forwarded=%d", stream_key, forwarded)
                            return
                    except Exception:
                        pass

    async def event_generator():
        # Prime the stream with a padding comment so buffering proxies (the Next.js
        # dev rewrite in particular) flush immediately and keep flushing each event,
        # instead of holding the whole SSE response until the connection closes.
        yield ":" + (" " * 2048) + "\n\n"

        if is_mock:
            async for chunk in _inline():
                yield chunk
            return
        # Real mode: try to offload to the worker
        from workers.dispatch import dispatch
        from workers.tasks import run_project_chat
        stream_key = uuid.uuid4().hex
        result = dispatch(
            run_project_chat, str(project_id), project_name, question, history_json, stream_key,
        )
        if result is None:
            # Broker/worker unavailable → don't hang; run inline as a fallback.
            log.warning("ask broker unavailable — running inline (stream_key=%s)", stream_key)
            async for chunk in _inline():
                yield chunk
            return
        async for chunk in _tail_worker(stream_key):
            yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Transfer-Encoding": "chunked",
        },
    )


# ── Sessions (chat history, per-user) ─────────────────────────────────────────────

@router.get("/projects/{project_id}/ask/sessions")
async def list_ask_sessions(
    project: Project = Depends(get_project_or_404),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List the current user's saved copilot sessions for this project (newest first)."""
    rows = (await db.execute(
        select(
            ProjectAskSession.id,
            ProjectAskSession.title,
            func.jsonb_array_length(ProjectAskSession.messages),
            ProjectAskSession.created_at,
            ProjectAskSession.updated_at,
        )
        .where(
            ProjectAskSession.project_id == project.id,
            ProjectAskSession.user_id == user.id,
        )
        .order_by(ProjectAskSession.updated_at.desc())
    )).all()
    return ok([
        {
            "id": str(sid),
            "title": title,
            "message_count": count or 0,
            "created_at": created.isoformat(),
            "updated_at": updated.isoformat(),
        }
        for sid, title, count, created, updated in rows
    ])


@router.get("/projects/{project_id}/ask/sessions/{session_id}")
async def get_ask_session(
    session_id: uuid.UUID,
    project: Project = Depends(get_project_or_404),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    sess = (await db.execute(
        select(ProjectAskSession).where(
            ProjectAskSession.id == session_id,
            ProjectAskSession.project_id == project.id,
            ProjectAskSession.user_id == user.id,
        )
    )).scalar_one_or_none()
    if sess is None:
        err("not_found", "Chat session not found", 404)
    return ok(AskSessionRead.model_validate(sess).model_dump(mode="json"))


@router.post("/projects/{project_id}/ask/sessions")
async def save_ask_session(
    body: AskSessionSave,
    project: Project = Depends(get_project_or_404),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Upsert a session: creates when id is null, else updates the user's own."""
    messages = [m.model_dump() for m in body.messages]
    sess: ProjectAskSession | None = None
    if body.id is not None:
        sess = (await db.execute(
            select(ProjectAskSession).where(
                ProjectAskSession.id == body.id,
                ProjectAskSession.project_id == project.id,
                ProjectAskSession.user_id == user.id,
            )
        )).scalar_one_or_none()
    if sess is None:
        sess = ProjectAskSession(
            project_id=project.id,
            user_id=user.id,
            title=body.title[:200],
            messages=messages,
        )
        db.add(sess)
    else:
        sess.title = body.title[:200]
        sess.messages = messages
    await db.commit()
    await db.refresh(sess)
    return ok({"id": str(sess.id), "updated_at": sess.updated_at.isoformat()})


@router.delete("/projects/{project_id}/ask/sessions/{session_id}")
async def delete_ask_session(
    session_id: uuid.UUID,
    project: Project = Depends(get_project_or_404),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    sess = (await db.execute(
        select(ProjectAskSession).where(
            ProjectAskSession.id == session_id,
            ProjectAskSession.project_id == project.id,
            ProjectAskSession.user_id == user.id,
        )
    )).scalar_one_or_none()
    if sess is not None:
        await db.delete(sess)
        await db.commit()
    return ok(None)
