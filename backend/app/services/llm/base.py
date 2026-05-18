from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, *, prompt: str, system: str, skill_name: str | None = None) -> str:
        """Call the LLM and return raw text. Skill engine handles JSON parsing/validation."""
