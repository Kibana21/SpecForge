from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://spec_forge_user:PASSWORD@localhost:5432/spec_forge_db"

    # Auth — fail loudly at startup if JWT_SECRET is missing or is the placeholder
    jwt_secret: str = ""
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    bcrypt_rounds: int = 12

    # Redis (rate-limit counters + JTI blocklist)
    redis_url: str = "redis://localhost:6379"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # File uploads
    upload_dir: str = "./uploads"
    max_upload_mb: int = 20

    # LLM
    llm_provider: str = "mock"
    gemini_api_key: str = ""
    google_service_account_path: str = ""  # path to service account JSON key (e.g. video-key.json)
    gemini_model: str = "gemini-3.5-flash"
    gemini_project_id: str = ""
    gemini_location: str = "global"  # Gemini 3.x text models are served only from `global`

    # Test Cases (E3): FRS specs authored concurrently in Stage B (spec-level
    # parallelism). Higher = faster wall-clock; lower if Vertex returns 429s.
    tc_parallel_specs: int = 6
    # Test Cases use a dedicated LM with a SMALL "thinking" budget ("low") — fast
    # like "disable" but with enough reasoning to keep instruction-following tight
    # (e.g. no accidental language drift). Options: "disable" | "low" | "medium" |
    # "" (full). Scoped to test-case generation only; BRD/FRS keep their default LM.
    tc_reasoning_effort: str = "low"
    # Output budget for the test-cases LM. With a thinking budget (reasoning_effort
    # != "disable") the model's thinking tokens count toward this cap, so it must
    # be generous or the structured case payload gets truncated mid-JSON.
    tc_max_tokens: int = 40000
    # Quality for the repair / "Clean up & fix" pass: ChainOfThought (an explicit
    # reasoning pass) so re-authored cases are rich (≥2 assertions, concrete
    # expected_result) instead of thin. "medium" reasoning is the sweet spot —
    # markedly richer than the fast bulk path (low + Predict) yet far fewer
    # tokens/call than "high", so it won't blow Vertex's tokens-per-minute quota
    # at concurrency. Bump to "high" only if your quota is generous.
    tc_reasoning_effort_high: str = "medium"
    tc_max_tokens_high: int = 48000
    # Concurrency for the repair pass. It runs alone (no bulk gen competing for
    # Vertex), but ChainOfThought calls are token-heavy, so going too wide trips
    # Vertex's per-minute quota → calls hang behind retries (looks "stuck"), which
    # is SLOWER, not faster. 8 is a stable-fast default. Capped at the thin-spec
    # count at run time. Tunable via TC_REPAIR_PARALLEL_SPECS (raise if quota allows).
    tc_repair_parallel_specs: int = 8

    # Embedding (kept for project/app similarity only)
    embedding_model: str = "text-embedding-004"
    embedding_dimensions: int = 768
    corpus_max_upload_mb: int = 50
    fact_extract_max_chunks: int = 100

    # Corpus index engine (PageIndex — reasoning tree). "auto" = mock when llm_provider==mock,
    # else pageindex. Override with "mock" or "pageindex".
    corpus_index_provider: str = "auto"
    pageindex_model: str = "vertex_ai/gemini-3.5-flash"  # LiteLLM Vertex model id for PageIndex
    tree_search_top_k: int = 8
    # Hybrid App Brain: also build + retrieve a PageIndex reasoning tree alongside
    # the pgvector chunks for /ask. Set false to fall back to pure vector RAG.
    app_brain_use_pageindex: bool = True

    # Markdown conversion ("auto" = mock when llm_provider==mock, else azure)
    markdown_provider: str = "auto"
    azure_content_understanding_endpoint: str = ""
    azure_content_understanding_key: str = ""

    # Malware scanning (no-op stub today; real engine slots in later)
    malware_scanner: str = "noop"

    # CORS
    cors_origins: str = "http://localhost:3000"

    # Logging
    log_level: str = "INFO"
    environment: str = "development"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
