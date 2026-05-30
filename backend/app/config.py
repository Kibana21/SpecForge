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
