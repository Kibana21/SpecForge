import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.limiter import limiter

settings = get_settings()

logging.basicConfig(level=settings.log_level.upper())
log = logging.getLogger(__name__)

app = FastAPI(
    title="SpecForge AI",
    description="Requirements-to-Spec guided workflow portal",
    version="0.1.0",
)

# ── Rate limiting ─────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Security headers ──────────────────────────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


# ── Exception handlers ────────────────────────────────────────────────────────
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        return JSONResponse(status_code=exc.status_code, content=detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "data": None,
            "error": {"code": "http_error", "message": str(detail)},
            "meta": {},
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    from app.services.skills.skill_engine import SkillValidationError

    if isinstance(exc, SkillValidationError):
        log.error("skill_validation_error path=%s error=%s", request.url.path, exc)
        return JSONResponse(
            status_code=502,
            content={
                "data": None,
                "error": {"code": "skill_validation_error", "message": str(exc)},
                "meta": {},
            },
        )
    log.exception("unhandled_error method=%s path=%s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "data": None,
            "error": {"code": "internal_error", "message": "An unexpected error occurred."},
            "meta": {},
        },
    )


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/healthz", tags=["infra"])
async def healthz():
    return {"ok": True}


# ── Routers ───────────────────────────────────────────────────────────────────
from app.api import documents, gaps, projects, reviews, specs  # noqa: E402

app.include_router(projects.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(specs.router, prefix="/api")
app.include_router(gaps.router, prefix="/api")
app.include_router(reviews.router, prefix="/api")
