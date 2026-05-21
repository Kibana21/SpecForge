import logging

from app.config import get_settings
from app.services.llm.base import LLMProvider

log = logging.getLogger(__name__)


def get_provider() -> LLMProvider:
    settings = get_settings()
    provider_name = settings.llm_provider.lower()

    if provider_name == "gemini":
        has_credentials = bool(settings.gemini_api_key or settings.google_service_account_path)
        if not has_credentials:
            log.warning("No Gemini credentials set — falling back to MockProvider")
            from app.services.llm.mock_provider import MockProvider
            return MockProvider()
        from app.services.llm.gemini_provider import GeminiProvider
        return GeminiProvider()

    if provider_name == "mock":
        from app.services.llm.mock_provider import MockProvider
        return MockProvider()

    raise ValueError(f"Unknown LLM_PROVIDER: {provider_name!r}. Valid values: gemini, mock")
