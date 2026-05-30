import os
from functools import lru_cache

from google.oauth2 import service_account

_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def configure_google_genai_env() -> None:
    """Route the google-genai SDK (used by langchain-google-genai) to Vertex with
    our service account.

    langchain-google-genai 4.x ignores the `credentials=` kwarg for embeddings and
    authenticates via the SDK's env-based ADC + Vertex routing. Setting these makes
    both the LLM and embedding providers use our service account on Vertex.
    Idempotent; safe to call from API and worker startup.
    """
    from app.config import get_settings
    settings = get_settings()
    if not settings.google_service_account_path:
        return
    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", settings.google_service_account_path)
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
    if settings.gemini_project_id:
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", settings.gemini_project_id)
    if settings.gemini_location:
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", settings.gemini_location)
        # LiteLLM (used by DSPy + PageIndex) ignores GOOGLE_CLOUD_LOCATION and
        # defaults Vertex to us-central1 unless VERTEXAI_LOCATION / VERTEXAI_PROJECT
        # are set. Gemini 3.x text models are served only from `global`, so this
        # is required or every DSPy call 404s against us-central1.
        os.environ.setdefault("VERTEXAI_LOCATION", settings.gemini_location)
        if settings.gemini_project_id:
            os.environ.setdefault("VERTEXAI_PROJECT", settings.gemini_project_id)


@lru_cache(maxsize=1)
def get_google_credentials() -> service_account.Credentials:
    from app.config import get_settings
    settings = get_settings()
    configure_google_genai_env()
    return service_account.Credentials.from_service_account_file(
        settings.google_service_account_path,
        scopes=_SCOPES,
    )
