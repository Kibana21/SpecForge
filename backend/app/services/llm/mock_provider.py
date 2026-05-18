import json
import logging
from pathlib import Path

from app.services.llm.base import LLMProvider

log = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Map skill_name → fixture filename
_SKILL_FIXTURE_MAP: dict[str, str] = {
    "requirement_extractor": "requirement_extractor.json",
    "gap_detector": "gap_detector.json",
    "functional_spec": "functional_spec.json",
    "technical_spec": "technical_spec.json",
    "user_stories": "user_stories.json",
    "reviewer": "reviewer.json",
}


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
