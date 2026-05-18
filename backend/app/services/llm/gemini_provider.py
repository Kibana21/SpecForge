import asyncio
import logging
import time
import warnings

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_vertexai import ChatVertexAI

from app.config import get_settings
from app.services.llm.base import LLMProvider

log = logging.getLogger(__name__)

warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain_google_vertexai")


class LLMProviderError(Exception):
    pass


def _build_llm(settings) -> ChatVertexAI:
    from google.oauth2 import service_account

    creds = service_account.Credentials.from_service_account_file(
        settings.gemini_service_account_path,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    log.info(
        "GeminiProvider via Vertex AI service account model=%s project=%s location=%s",
        settings.gemini_model, settings.gemini_project_id, settings.gemini_location,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return ChatVertexAI(
            model_name=settings.gemini_model,
            temperature=0.3,
            credentials=creds,
            project=settings.gemini_project_id,
            location=settings.gemini_location,
        )


class GeminiProvider(LLMProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self._llm = _build_llm(settings)

    async def complete(self, *, prompt: str, system: str, skill_name: str | None = None) -> str:
        messages = [
            SystemMessage(content=system),
            HumanMessage(content=prompt),
        ]

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            start = time.monotonic()
            try:
                response = await self._llm.ainvoke(messages)
                latency = round((time.monotonic() - start) * 1000)
                log.info(
                    "llm_call skill=%s provider=vertex attempt=%d latency_ms=%d",
                    skill_name, attempt, latency,
                )
                return response.content
            except Exception as exc:
                latency = round((time.monotonic() - start) * 1000)
                log.warning(
                    "llm_error skill=%s provider=vertex attempt=%d latency_ms=%d error=%s",
                    skill_name, attempt, latency, str(exc),
                )
                if attempt == max_retries:
                    raise LLMProviderError(
                        f"Vertex AI call failed after {max_retries} attempts: {exc}"
                    ) from exc
                await asyncio.sleep(2**attempt)

        raise LLMProviderError("Unreachable")
