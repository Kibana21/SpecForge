"""Mock markdown provider — deterministic, zero external calls. Used when markdown_provider=mock."""
import os

from .base import MarkdownProvider

_TEXT_TYPES = {"text/plain", "text/markdown", "text/html", "text/csv"}


class MockMarkdownProvider(MarkdownProvider):
    name = "mock"

    async def convert(self, content: bytes, mime_type: str, filename: str) -> str:
        if mime_type in _TEXT_TYPES:
            for enc in ("utf-8", "utf-8-sig", "latin-1"):
                try:
                    return content.decode(enc).strip()
                except UnicodeDecodeError:
                    continue
            return content.decode("latin-1", errors="replace").strip()

        stem = os.path.splitext(filename)[0]
        return (
            f"# {stem}\n\n"
            f"> _Mock markdown — real conversion requires the azure provider_\n\n"
            f"File: `{filename}` ({mime_type}, {len(content):,} bytes)"
        )
