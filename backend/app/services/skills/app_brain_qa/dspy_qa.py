"""DSPy streaming QA for Ask Brain — the one free-text (non-structured) skill.

Uses dspy.streamify so the answer streams token-by-token like the rest of the
app is now DSPy-native. Citations are computed by the caller (from the retrieved
sections/chunks), so this module only generates the prose answer.

Falls back to a single non-streaming prediction if live streaming errors, so the
answer always renders.
"""
import asyncio
import logging

import dspy
from dspy.streaming import StreamListener, StreamResponse

log = logging.getLogger(__name__)

_MOCK_ANSWER = (
    "This is a mock streaming answer from the App Brain. "
    "It references [Citation 1] and provides illustrative information."
)


class AppBrainQASignature(dspy.Signature):
    """Answer a Business Analyst's question about an enterprise application using
    ONLY the provided documentation context.

    Ground every claim in the context; if it is insufficient, say so plainly —
    never guess or fabricate. Reference [Citation N] markers inline where they
    support a claim, matching the numbers in the context. Use the conversation so
    far to resolve follow-up references. Write a clear, well-structured answer in
    Markdown prose for a BA/SA audience.
    """

    app_name: str = dspy.InputField()
    retrieved_text: str = dspy.InputField(desc="Documentation context with [Citation N]/[Section N] markers")
    conversation: str = dspy.InputField(desc="Prior chat turns, or empty")
    question: str = dspy.InputField()
    answer: str = dspy.OutputField(desc="Markdown prose answer with inline [Citation N] markers")


async def run_qa_stream(app_name: str, retrieved_text: str, conversation: str, question: str):
    """Async generator yielding answer text deltas (strings)."""
    from app.config import get_settings
    if get_settings().llm_provider == "mock":
        for i in range(0, len(_MOCK_ANSWER), 12):
            yield _MOCK_ANSWER[i:i + 12]
            await asyncio.sleep(0)
        return

    from app.services.skills.fact_extractor.dspy_extractor import _configure_dspy
    _configure_dspy()
    inputs = dict(app_name=app_name, retrieved_text=retrieved_text,
                  conversation=conversation, question=question)

    streamed = False
    try:
        program = dspy.streamify(
            dspy.Predict(AppBrainQASignature),
            stream_listeners=[StreamListener(signature_field_name="answer")],
        )
        async for chunk in program(**inputs):
            if isinstance(chunk, StreamResponse) and chunk.chunk:
                streamed = True
                yield chunk.chunk
    except Exception as exc:  # noqa: BLE001
        log.warning("dspy qa streaming failed (%s); falling back to non-streaming", exc)

    if not streamed:
        # Fallback: one-shot prediction in a thread, yield the whole answer.
        def _predict() -> str:
            try:
                return dspy.Predict(AppBrainQASignature)(**inputs).answer or ""
            except Exception as exc:  # noqa: BLE001
                log.error("dspy qa non-streaming fallback failed: %s", exc, exc_info=True)
                return ""
        loop = asyncio.get_running_loop()
        answer = await loop.run_in_executor(None, _predict)
        if answer:
            yield answer
