"""Azure AI Content Understanding provider — converts documents to markdown via prebuilt-layout.

Uses the synchronous SDK wrapped in run_in_executor so the async caller never blocks.
The client is cached per (endpoint, key) pair via lru_cache — safe across threads.
"""
import asyncio
import functools
import logging
import re
from typing import Optional

from .base import MarkdownProvider

log = logging.getLogger(__name__)

_HEADER_RE = re.compile(r"^<!-- PageHeader:\s*(.+?)\s*-->$")
_FOOTER_RE = re.compile(r"^<!-- PageFooter:\s*(.+?)\s*-->$")
_BREAK_RE  = re.compile(r"^<!-- PageBreak -->$")
_NUM_RE    = re.compile(r"^<!-- PageNumber:\s*(.+?)\s*-->$")
_FIG_RE    = re.compile(r"!\[([^\]]*)\]\(figures/[^)]+\)")
_BLANK_RE  = re.compile(r"\n{3,}")


@functools.lru_cache(maxsize=4)
def _make_client(endpoint: str, key: str):
    from azure.ai.contentunderstanding import ContentUnderstandingClient
    from azure.core.credentials import AzureKeyCredential

    return ContentUnderstandingClient(endpoint, AzureKeyCredential(key))


def _postprocess(raw_md: str, page_count: int, table_count: int, figure_count: int) -> str:
    """Clean and enrich the raw prebuilt-layout markdown for LLM / RAG consumption.

    What this does:
    - Extracts PageHeader comments → deduplicated metadata block at the top
    - Extracts PageFooter footnotes → appended at the bottom; strips repeated branding
    - Replaces <!-- PageBreak --> with a --- horizontal rule
    - Replaces <!-- PageNumber: Page N --> with a subtle **— Page N —** marker
    - Replaces broken figure image refs with readable [Figure: caption] text
    - Collapses 3+ blank lines to 2
    """
    lines = raw_md.split("\n")

    seen_headers: list[str] = []
    seen_header_set: set[str] = set()
    footnotes: list[str] = []
    body_lines: list[str] = []

    for line in lines:
        # --- PageHeader --------------------------------------------------
        m = _HEADER_RE.match(line)
        if m:
            text = m.group(1).strip()
            # Strip figure image refs inside headers — logo images are useless as text
            text = _FIG_RE.sub(lambda x: x.group(1) if x.group(1) else "", text).strip()
            if text and text not in seen_header_set:
                seen_headers.append(text)
                seen_header_set.add(text)
            continue

        # --- PageFooter --------------------------------------------------
        m = _FOOTER_RE.match(line)
        if m:
            text = m.group(1).strip()
            # Skip pure company branding lines (e.g. "AIA Singapore Private Limited (Reg. No. 201106386R)")
            # Keep numbered footnote refs so citations aren't lost
            if re.match(r"^\d+\s", text) or text.startswith("http"):
                footnotes.append(text)
            continue

        # --- PageBreak ---------------------------------------------------
        if _BREAK_RE.match(line):
            body_lines.append("\n---\n")
            continue

        # --- PageNumber --------------------------------------------------
        m = _NUM_RE.match(line)
        if m:
            body_lines.append(f"\n**— {m.group(1)} —**\n")
            continue

        # --- Figure refs in body -----------------------------------------
        line = _FIG_RE.sub(lambda x: f"**[Figure: {x.group(1)}]**" if x.group(1) else "", line)

        body_lines.append(line)

    # Build the final document
    parts: list[str] = []

    # Metadata block at top
    meta_items = []
    if page_count:
        meta_items.append(f"{page_count} page{'s' if page_count != 1 else ''}")
    if table_count:
        meta_items.append(f"{table_count} table{'s' if table_count != 1 else ''}")
    if figure_count:
        meta_items.append(f"{figure_count} figure{'s' if figure_count != 1 else ''}")

    if seen_headers or meta_items:
        meta_lines = []
        if meta_items:
            meta_lines.append(f"<!-- doc: {' · '.join(meta_items)} -->")
        for h in seen_headers:
            meta_lines.append(f"<!-- header: {h} -->")
        parts.append("\n".join(meta_lines))

    # Body
    body = "\n".join(body_lines).strip()
    # Collapse 3+ consecutive blank lines
    body = _BLANK_RE.sub("\n\n", body)
    parts.append(body)

    # Footnotes at the bottom
    if footnotes:
        seen_fn: set[str] = set()
        unique_fn = [f for f in footnotes if not (f in seen_fn or seen_fn.add(f))]  # type: ignore[func-returns-value]
        parts.append("---\n**References**\n\n" + "\n\n".join(unique_fn))

    return "\n\n".join(parts).strip()


class AzureMarkdownProvider(MarkdownProvider):
    name = "azure"

    def __init__(
        self,
        endpoint: str,
        key: str,
        analyzer_id: str = "prebuilt-layout",
    ) -> None:
        self._endpoint = endpoint
        self._key = key
        self._analyzer_id = analyzer_id

    def _convert_sync(self, content: bytes, mime_type: str, filename: str) -> str:
        from azure.ai.contentunderstanding.models import DocumentContent

        client = _make_client(self._endpoint, self._key)
        poller = client.begin_analyze_binary(
            analyzer_id=self._analyzer_id,
            binary_input=content,
            content_type=mime_type,
        )
        result = poller.result()

        if not result.contents:
            log.warning("azure_markdown: empty result for filename=%s", filename)
            return ""

        parts = []
        for item in result.contents:
            raw_md = item.markdown or ""
            if isinstance(item, DocumentContent):
                cleaned = _postprocess(
                    raw_md,
                    page_count=len(item.pages) if item.pages else 0,
                    table_count=len(item.tables) if item.tables else 0,
                    figure_count=len(item.figures) if item.figures else 0,
                )
            else:
                cleaned = raw_md
            parts.append(cleaned)

        return "\n\n".join(parts)

    async def convert(self, content: bytes, mime_type: str, filename: str) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._convert_sync, content, mime_type, filename
        )
