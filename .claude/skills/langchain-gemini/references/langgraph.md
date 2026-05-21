# LangGraph — Agents and Workflows with Gemini

## Installation

`langgraph` is already in `requirements.txt`. Import from `langgraph`.

## Core concepts

| Concept | Description |
|---|---|
| `StateGraph` | Graph where nodes read/write a shared state dict |
| Node | Async function `(state) -> dict` that returns partial state updates |
| Edge | Directed connection between nodes; can be conditional |
| `END` | Terminal sentinel — graph finishes when a node routes to `END` |
| `MemorySaver` | In-memory checkpointer for multi-turn conversation threads |

## Minimal ReAct agent

```python
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from app.core.google_credentials import get_google_credentials
from app.config import get_settings

settings = get_settings()
llm = ChatGoogleGenerativeAI(
    model=settings.gemini_model,
    temperature=0.3,
    credentials=get_google_credentials(),
    project=settings.gemini_project_id,
)

@tool
def search_docs(query: str) -> str:
    """Search the corpus for relevant chunks."""
    ...

agent = create_react_agent(llm, tools=[search_docs])
result = await agent.ainvoke({"messages": [("user", "What is the refund policy?")]})
```

## Custom StateGraph (for multi-step pipelines)

```python
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    facts: list[str]
    done: bool

async def retrieve_node(state: AgentState) -> dict:
    # retrieve relevant facts from DB
    return {"facts": [...]}

async def answer_node(state: AgentState) -> dict:
    # call LLM with context
    response = await llm.ainvoke(state["messages"])
    return {"messages": [response], "done": True}

def should_continue(state: AgentState) -> str:
    return END if state["done"] else "answer"

builder = StateGraph(AgentState)
builder.add_node("retrieve", retrieve_node)
builder.add_node("answer", answer_node)
builder.set_entry_point("retrieve")
builder.add_edge("retrieve", "answer")
builder.add_conditional_edges("answer", should_continue)

graph = builder.compile()
result = await graph.ainvoke({"messages": [("user", "query")], "facts": [], "done": False})
```

## Streaming from a graph

```python
async for event in graph.astream_events(input_state, version="v2"):
    kind = event["event"]
    if kind == "on_chat_model_stream":
        chunk = event["data"]["chunk"]
        print(chunk.content, end="", flush=True)
```

## Persistent multi-turn memory

```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer)

config = {"configurable": {"thread_id": "user-session-abc"}}
result = await graph.ainvoke(input_state, config=config)
# next call with same thread_id resumes conversation
```

## Integrating with SpecForge async patterns

LangGraph nodes must be async when the graph is invoked with `ainvoke` / `astream`. Use `AsyncSessionLocal` normally inside nodes — LangGraph does not interfere with SQLAlchemy async sessions.

```python
async def db_node(state: AgentState) -> dict:
    from app.db import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        ...
    return {"facts": [...]}
```

## When to use LangGraph vs SkillEngine

| Use `SkillEngine` | Use `LangGraph` |
|---|---|
| Single LLM call with structured output | Multi-step agent with tool loops |
| Prompt template → parse → return | Conditional branching between nodes |
| Batch processing, Celery tasks | Stateful multi-turn conversations |
| Fast, simple, testable skills | Complex reasoning pipelines |
