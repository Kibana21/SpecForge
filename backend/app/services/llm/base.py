from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, *, prompt: str, system: str, skill_name: str | None = None) -> str:
        """Call the LLM and return raw text. Skill engine handles JSON parsing/validation."""

    @abstractmethod
    async def astream(
        self, *, prompt: str, system: str, skill_name: str | None = None
    ) -> AsyncIterator[str]:
        """Stream tokens from LLM. Yields raw text token strings."""
