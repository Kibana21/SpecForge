# ChatGoogleGenerativeAI — Invocation Patterns

## Instantiation (project pattern)

```python
from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.google_credentials import get_google_credentials
from app.config import get_settings

settings = get_settings()
llm = ChatGoogleGenerativeAI(
    model=settings.gemini_model,        # "gemini-2.5-flash"
    temperature=0.3,
    credentials=get_google_credentials(),
    project=settings.gemini_project_id,
    location=settings.gemini_location,
)
```

> **Temperature note**: Gemini 3.0+ defaults to `1.0` when temperature is omitted. For skills that need deterministic output, explicitly set `temperature=0.3` or lower.

## Basic invocation

```python
from langchain_core.messages import HumanMessage, SystemMessage

response = await llm.ainvoke([
    SystemMessage(content="You are a helpful assistant."),
    HumanMessage(content="Explain vector databases in one sentence."),
])
text = response.content  # str for gemini-2.5; list of blocks for gemini-3.x
```

## Streaming (SSE pattern used in SpecForge)

```python
async for chunk in llm.astream(messages):
    if chunk.content:
        yield chunk.content  # str fragment
```

The `GeminiProvider.astream()` in `app/services/llm/gemini_provider.py` wraps this pattern. New skills should go through `SkillEngine` + `provider.astream()` rather than calling LangChain directly.

## Structured output

```python
from pydantic import BaseModel
from typing import Literal

class Sentiment(BaseModel):
    sentiment: Literal["positive", "neutral", "negative"]
    summary: str

structured = llm.with_structured_output(
    schema=Sentiment.model_json_schema(),
    method="json_schema",
)
result = await structured.ainvoke(messages)  # dict matching schema
```

## Tool / function calling

```python
from langchain_core.tools import tool

@tool(description="Look up a document by ID")
def get_document(doc_id: str) -> str:
    ...

llm_with_tools = llm.bind_tools([get_document])
response = await llm_with_tools.ainvoke(messages)

# Execute tool calls and feed results back
for call in response.tool_calls:
    result = get_document.invoke(call)
    messages.append(result)

final = await llm_with_tools.ainvoke(messages)
```

> **Gemini 3 warning**: Pass the original `AIMessage` object back — do not reconstruct it. Gemini 3 attaches thought signatures to messages; reconstructing loses them and causes 4xx errors.

## Built-in Gemini tools

```python
# Google Search grounding
llm_search = llm.bind_tools([{"google_search": {}}])

# Code execution
llm_code = llm.bind_tools([{"code_execution": {}}])
```

## Multimodal (image)

```python
import base64

image_bytes = open("image.jpg", "rb").read()
b64 = base64.b64encode(image_bytes).decode()

msg = HumanMessage(content=[
    {"type": "text", "text": "Describe this image."},
    {"type": "image", "base64": b64, "mime_type": "image/jpeg"},
])
response = await llm.ainvoke([msg])
```

## SpecForge skill pattern

New skills live in `app/services/skills/<skill_name>/` and are executed via `SkillEngine.run()`. The engine handles Jinja2 prompt rendering, schema validation of output, and mock fixture loading in tests. Only write raw LangChain calls when building something outside the skill system (e.g., a LangGraph agent).

```
app/services/skills/<skill_name>/
├── instruction.md   ← system prompt
├── template.md      ← Jinja2 user prompt (receives input_vars dict)
└── schema.json      ← JSON Schema for expected output
```
