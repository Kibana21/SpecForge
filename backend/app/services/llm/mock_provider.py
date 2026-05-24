import asyncio
import json
import logging
from collections.abc import AsyncIterator
from pathlib import Path

from app.services.llm.base import LLMProvider

log = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# All skills now run through DSPy modules (which load fixtures directly in mock
# mode via app.services.skills.mock_fixtures), so the SkillEngine fixture map is
# empty. Kept for the legacy MockProvider.complete contract / unknown-skill test.
_SKILL_FIXTURE_MAP: dict[str, str] = {}


class MockProvider(LLMProvider):
    """Returns pre-written fixture JSON for each skill. No API calls made."""

    async def complete(self, *, prompt: str, system: str, skill_name: str | None = None) -> str:
        if skill_name is None:
            log.warning("MockProvider called with no skill_name — returning empty object")
            return "{}"

        filename = _SKILL_FIXTURE_MAP.get(skill_name)
        if filename is None:
            log.warning("MockProvider has no fixture for skill=%s — returning empty object", skill_name)
            return "{}"

        fixture_path = FIXTURES_DIR / filename
        if not fixture_path.exists():
            raise FileNotFoundError(f"Mock fixture missing: {fixture_path}")

        log.debug("mock_provider skill=%s fixture=%s", skill_name, filename)
        return fixture_path.read_text(encoding="utf-8")

    async def astream(
        self, *, prompt: str, system: str, skill_name: str | None = None
    ) -> AsyncIterator[str]:
        fixture_answer = (
            "This is a mock streaming answer from the App Brain. "
            "It references [Citation 1] and provides illustrative information."
        )
        chunk_size = 10
        for i in range(0, len(fixture_answer), chunk_size):
            yield fixture_answer[i: i + chunk_size]
            await asyncio.sleep(0)
