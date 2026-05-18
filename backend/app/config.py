from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://spec_forge_user:PASSWORD@localhost:5432/spec_forge_db"

    # File uploads
    upload_dir: str = "./uploads"
    max_upload_mb: int = 20

    # LLM
    llm_provider: str = "mock"
    gemini_api_key: str = ""
    gemini_service_account_path: str = ""
    gemini_model: str = "gemini-2.0-flash-001"
    gemini_project_id: str = ""
    gemini_location: str = "us-central1"

    # CORS
    cors_origins: str = "http://localhost:3000"

    # Logging
    log_level: str = "INFO"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
