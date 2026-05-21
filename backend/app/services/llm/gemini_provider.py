import asyncio
import logging
import time
import warnings
from collections.abc import AsyncIterator

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import get_settings
from app.core.google_credentials import get_google_credentials
from app.services.llm.base import LLMProvider

log = logging.getLogger(__name__)

warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain_google_genai")


class LLMProviderError(Exception):
    pass


def _build_llm(settings) -> ChatGoogleGenerativeAI:
    creds = get_google_credentials()
    log.info(
        "GeminiProvider via Vertex AI service account model=%s project=%s location=%s",
        settings.gemini_model, settings.gemini_project_id, settings.gemini_location,
    )
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
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

    async def astream(
        self, *, prompt: str, system: str, skill_name: str | None = None
    ) -> AsyncIterator[str]:
        messages = [
            SystemMessage(content=system),
            HumanMessage(content=prompt),
        ]
        start = time.monotonic()
        try:
            async for chunk in self._llm.astream(messages):
                if chunk.content:
                    yield chunk.content
            latency = round((time.monotonic() - start) * 1000)
            log.info("llm_stream skill=%s provider=vertex latency_ms=%d", skill_name, latency)
        except Exception as exc:
            latency = round((time.monotonic() - start) * 1000)
            log.error("llm_stream_error skill=%s latency_ms=%d error=%s", skill_name, latency, exc)
            raise LLMProviderError(f"Vertex AI stream failed: {exc}") from exc
