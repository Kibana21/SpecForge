import json
import logging
import re
import time
from pathlib import Path

import jsonschema
from jinja2 import Environment, StrictUndefined

from app.services.llm.base import LLMProvider

log = logging.getLogger(__name__)

SKILLS_ROOT = Path(__file__).parent
MAX_DOCUMENT_TEXT_CHARS = 60_000  # guard against prompt overflow


class SkillValidationError(Exception):
    """Raised when the LLM response fails JSON Schema validation after the retry."""


def _extract_json(raw: str) -> dict | list:
    """Strip markdown code fences and extract the first valid JSON object/array."""
    # Remove ```json ... ``` fences
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()

    # Try the whole string first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Find first { or [ and try from there
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        start = cleaned.find(start_char)
        if start == -1:
            continue
        end = cleaned.rfind(end_char)
        if end == -1:
            continue
        try:
            return json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            continue

    raise ValueError(f"No valid JSON found in LLM response. Raw (first 500 chars): {raw[:500]!r}")


class SkillEngine:
    def __init__(self, skills_root: Path | None = None) -> None:
        self._root = skills_root or SKILLS_ROOT

    async def run(
        self,
        skill_name: str,
        context: dict,
        provider: LLMProvider,
    ) -> dict | list:
        skill_dir = self._root / skill_name
        if not skill_dir.is_dir():
            raise FileNotFoundError(f"Skill directory not found: {skill_dir}")

        instruction = (skill_dir / "instruction.md").read_text(encoding="utf-8")
        template_src = (skill_dir / "template.md").read_text(encoding="utf-8")
        schema = json.loads((skill_dir / "schema.json").read_text(encoding="utf-8"))

        # Truncate large document text to avoid prompt overflow
        if "document_text" in context and len(context["document_text"]) > MAX_DOCUMENT_TEXT_CHARS:
            log.warning(
                "skill=%s truncating document_text from %d to %d chars",
                skill_name, len(context["document_text"]), MAX_DOCUMENT_TEXT_CHARS,
            )
            context = {**context, "document_text": context["document_text"][:MAX_DOCUMENT_TEXT_CHARS]}

        env = Environment(undefined=StrictUndefined, autoescape=False)
        prompt = env.from_string(template_src).render(**context)

        # Attempt 1
        raw = await self._call(provider, prompt, instruction, skill_name, attempt=1)
        first_error: Exception | None = None
        try:
            parsed = _extract_json(raw)
            jsonschema.validate(parsed, schema)
            return parsed
        except (ValueError, jsonschema.ValidationError) as exc:
            first_error = exc
            log.warning("skill=%s attempt=1 validation_error=%s", skill_name, str(exc)[:200])

        # Attempt 2 — error-correction prompt
        retry_prompt = (
            f"{prompt}\n\n"
            f"Your previous response was invalid. Error: {first_error}\n"
            f"Return ONLY valid JSON that strictly matches the required schema. No prose, no markdown fences."
        )
        raw2 = await self._call(provider, retry_prompt, instruction, skill_name, attempt=2)
        try:
            parsed2 = _extract_json(raw2)
            jsonschema.validate(parsed2, schema)
            return parsed2
        except (ValueError, jsonschema.ValidationError) as exc2:
            log.error("skill=%s attempt=2 validation_error=%s", skill_name, str(exc2)[:200])
            raise SkillValidationError(
                f"Skill '{skill_name}' failed schema validation after 2 attempts: {exc2}"
            ) from exc2

    async def _call(
        self,
        provider: LLMProvider,
        prompt: str,
        system: str,
        skill_name: str,
        attempt: int,
    ) -> str:
        start = time.monotonic()
        raw = await provider.complete(prompt=prompt, system=system, skill_name=skill_name)
        latency = round((time.monotonic() - start) * 1000)
        log.info("skill=%s attempt=%d latency_ms=%d", skill_name, attempt, latency)
        return raw
