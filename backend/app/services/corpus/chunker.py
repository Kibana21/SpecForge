import logging

log = logging.getLogger(__name__)

_MAX_TOKENS = 512
_OVERLAP_TOKENS = 64
_MIN_TRAILING_TOKENS = 20


def chunk_text(
    text: str,
    max_tokens: int = _MAX_TOKENS,
    overlap_tokens: int = _OVERLAP_TOKENS,
) -> list[str]:
    """Split text into overlapping token-window chunks using tiktoken cl100k_base."""
    if not text or not text.strip():
        return []

    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)

    if not tokens:
        return []

    step = max_tokens - overlap_tokens  # 448
    chunks: list[str] = []
    start = 0

    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        window = tokens[start:end]
        chunks.append(enc.decode(window))
        if end == len(tokens):
            break
        start += step

    # Merge sub-minimal trailing chunk into previous
    if len(chunks) > 1:
        last_tokens = enc.encode(chunks[-1])
        if len(last_tokens) < _MIN_TRAILING_TOKENS:
            prev = chunks[-2] + " " + chunks[-1]
            chunks[-2] = prev
            chunks.pop()

    return chunks
