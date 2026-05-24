"""Deterministic fixtures for the DSPy skills' mock path.

When settings.llm_provider == 'mock' (CI/tests), each DSPy `run_*` wrapper returns
the canned JSON here instead of calling Vertex — zero network, deterministic, and
identical to the data the old SkillEngine fixtures returned (so existing test
assertions keep holding).
"""
import functools
import json
from pathlib import Path

_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "llm" / "fixtures"


@functools.lru_cache(maxsize=None)
def mock_fixture(name: str) -> dict:
    """Load llm/fixtures/<name>.json as a dict (cached)."""
    path = _FIXTURES_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Mock fixture missing: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Fixture {name} must be a JSON object")
    return data
