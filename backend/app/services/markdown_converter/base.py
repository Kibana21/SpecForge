from abc import ABC, abstractmethod


class MarkdownProvider(ABC):
    name: str  # identifier stored in document_markdown.provider

    @abstractmethod
    async def convert(self, content: bytes, mime_type: str, filename: str) -> str:
        """Convert document bytes to markdown text."""
