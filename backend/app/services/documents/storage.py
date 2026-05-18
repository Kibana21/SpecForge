"""File storage abstraction — local filesystem today, swappable to Azure Blob later."""
import logging
import re
import uuid
from pathlib import Path

import aiofiles

log = logging.getLogger(__name__)

# Map MIME type → canonical extension
_MIME_TO_EXT = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
}

# Allowed MIME types (magic-byte validated)
ALLOWED_MIME_TYPES = set(_MIME_TO_EXT.keys())


def detect_mime(content: bytes) -> str:
    """Detect MIME type from magic bytes. Falls back to text/plain for non-binary content."""
    import filetype

    kind = filetype.guess(content[:2048])
    if kind is not None:
        return kind.mime

    # filetype returns None for plain text — verify it decodes as UTF-8
    try:
        content[:1024].decode("utf-8")
        return "text/plain"
    except UnicodeDecodeError:
        return "application/octet-stream"


def sanitize_filename(filename: str) -> str:
    """Remove path traversal, null bytes, and non-safe characters. Keep basename only."""
    # Strip directory components
    name = Path(filename).name
    # Remove null bytes
    name = name.replace("\x00", "")
    # Allow only safe characters (alphanumeric, dots, dashes, underscores, spaces)
    name = re.sub(r"[^\w.\- ]", "_", name)
    # Collapse multiple dots to prevent extension spoofing
    name = re.sub(r"\.{2,}", ".", name)
    return name.strip() or "upload"


async def save(project_id: str, original_filename: str, mime_type: str, content: bytes, upload_dir: str) -> str:
    """Save file content to disk. Returns the storage path (relative to upload_dir parent)."""
    ext = _MIME_TO_EXT.get(mime_type, ".bin")
    stored_name = f"{uuid.uuid4()}{ext}"

    project_dir = Path(upload_dir) / str(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)

    dest = project_dir / stored_name
    async with aiofiles.open(dest, "wb") as f:
        await f.write(content)

    log.debug("stored file original=%s stored=%s", original_filename, dest)
    return str(dest)


async def delete(storage_path: str) -> None:
    """Delete a stored file. Silently ignores missing files."""
    path = Path(storage_path)
    if path.exists():
        path.unlink()
        log.debug("deleted file %s", storage_path)
