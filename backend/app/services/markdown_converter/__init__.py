from .base import MarkdownProvider
from .mock_provider import MockMarkdownProvider
from .service import MarkdownConverterService


def get_markdown_provider() -> MarkdownProvider:
    """Return the configured markdown provider.

    markdown_provider setting:
      "auto"  → mock when llm_provider==mock, otherwise azure
      "mock"  → MockMarkdownProvider always
      "azure" → AzureMarkdownProvider always
    """
    from app.config import get_settings

    settings = get_settings()
    provider = settings.markdown_provider
    if provider == "auto":
        provider = "mock" if settings.llm_provider == "mock" else "azure"

    if provider == "mock":
        return MockMarkdownProvider()

    if provider == "azure":
        from .azure_provider import AzureMarkdownProvider

        return AzureMarkdownProvider(
            endpoint=settings.azure_content_understanding_endpoint,
            key=settings.azure_content_understanding_key,
        )

    raise ValueError(f"Unknown markdown_provider: {provider!r}")


__all__ = [
    "MarkdownProvider",
    "MockMarkdownProvider",
    "MarkdownConverterService",
    "get_markdown_provider",
]
