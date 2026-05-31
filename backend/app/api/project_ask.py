"""Project Copilot API — agentic vectorless chat over the project's PageIndex trees,
wiki concepts, and app facts. Mirrors the App Brain Ask interface (same SSE model,
same session CRUD) but project-scoped and powered by dspy.ReAct.

See .claude/plans/E2-ask-the-project.md.
"""
import asyncio
import hashlib
import json
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

router = APIRouter(tags=["project-ask"])


# ── Ask (SSE stream) ──────────────────────────────────────────────────────────────

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
    from app.services.rag.project_agent import ProjectChatAgent

    question_hash = hashlib.sha256(body.question.encode()).hexdigest()
    await audit.emit(
        db,
        event="project.ask",
        actor_id=str(user.id),
        metadata={"project_id": str(project.id), "question_hash": question_hash},
    )
    await db.commit()

    async def event_generator():
        # Interleave heartbeat pings (SSE comments) every 8 seconds while the agent
        # is running. This prevents the Next.js dev proxy from closing the connection
        # (ECONNRESET) during long Vertex/LLM calls.
        agent = ProjectChatAgent()
        event_iter = agent.stream_answer(
            project_id=project.id,
            project_name=project.name,
            question=body.question,
            db=db,
            history=body.history,
        )
        while True:
            try:
                event = await asyncio.wait_for(event_iter.__anext__(), timeout=8.0)
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") == "done" or event.get("type") == "error":
                    break
            except StopAsyncIteration:
                break
            except asyncio.TimeoutError:
                # Send a keep-alive comment to prevent proxy timeout
                yield ": heartbeat\n\n"

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
