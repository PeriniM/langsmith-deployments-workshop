"""
Calendar agent with long-term memory: read_calendar, write_calendar,
plus semantic search over memory and adding items to the store.
Uses ToolRuntime for store access; context_schema provides user_id for namespacing.
Pre-model middleware injects current user preferences from the store into the conversation.
"""

import uuid
from dataclasses import dataclass
from typing import List, Dict, Any
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import before_model, AgentState
from langchain.tools import tool, ToolRuntime
from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime
from agents.utils import model
from pydantic import Field

load_dotenv(override=True)

@dataclass
class Context:
    user_id: str = Field(default="default", description="User ID",
        json_schema_extra={
            "title": "User ID",
            "langgraph_nodes": ["inject_memory_preferences.before_model"],
            "langgraph_type": "text",
        })

# Mock calendar storage (in production, this would connect to Google Calendar API)
_calendar_events: List[Dict] = []


@tool
def read_calendar(date: str = None) -> str:
    """Read calendar events. If date is provided, filter events for that date.
    
    Args:
        date: Optional date string in format 'YYYY-MM-DD'. If None, returns all events.
    
    Returns:
        A string representation of calendar events.
    """
    if date:
        filtered = [e for e in _calendar_events if e.get("date") == date]
        if not filtered:
            return f"No events found for {date}"
        return "\n".join([f"- {e['title']} on {e['date']} at {e['time']} in {e.get('location', 'N/A')}" 
                         for e in filtered])
    
    if not _calendar_events:
        return "No events in calendar"
    
    return "\n".join([f"- {e['title']} on {e['date']} at {e['time']} in {e.get('location', 'N/A')}" 
                     for e in _calendar_events])


@tool
def write_calendar(title: str, date: str, time: str, location: str = "") -> str:
    """Create a new calendar event.
    
    Args:
        title: Event title
        date: Event date in format 'YYYY-MM-DD'
        time: Event time in format 'HH:MM'
        location: Optional location
    
    Returns:
        Confirmation message
    """
    # Check for conflicts
    for event in _calendar_events:
        if event["date"] == date and event["time"] == time:
            return f"Conflict: There's already an event '{event['title']}' scheduled for {date} at {time}"
    
    new_event = {
        "title": title,
        "date": date,
        "time": time,
        "location": location
    }
    _calendar_events.append(new_event)
    return f"Successfully created event '{title}' on {date} at {time} in {location}"


@tool
def search_memory(query: str, limit: int = 5, runtime: ToolRuntime[Context] = None) -> str:
    """Search documents by meaning (semantic search). Use for user documents added under the documents key.
    Args:
        query: Natural language question or topic to search for.
        limit: Max number of documents to return (default 5).
    """
    if runtime is None or not getattr(runtime, "store", None):
        return "Store is not available."
    user_id = getattr(runtime.context, "user_id", None) or "default"
    namespace = (user_id, "documents")
    results = runtime.store.search(namespace, query=query, limit=limit)
    if not results:
        return "No documents available."
    parts = []
    for item in results:
        val = item.value if hasattr(item, "value") else item
        doc = val.get("document", val.get("documents", val)) if isinstance(val, dict) else val
        if isinstance(doc, list):
            parts.extend(str(d) for d in doc)
        else:
            parts.append(str(doc))
    return "\n".join(parts)


@tool
def add_memory(content: str, runtime: ToolRuntime[Context] = None) -> str:
    """Add a fact or note to long-term memory. Use when the user shares something to remember (preferences, name, context).
    Args:
        content: The fact or memory to store (e.g. 'User prefers morning meetings').
    """
    if runtime is None or not getattr(runtime, "store", None):
        return "Memory store is not available."
    user_id = getattr(runtime.context, "user_id", None) or "default"
    namespace = (user_id, "memories")
    memory_id = str(uuid.uuid4())
    runtime.store.put(namespace, memory_id, {"memory": content})
    return f"Remembered: {content}"


# System prompt
SYSTEM_PROMPT = """You are a helpful calendar assistant. You can:
- Read calendar events using read_calendar
- Create new events using write_calendar
- Search user documents with search_memory (semantic search over the documents key)
- Save facts to long-term memory with add_memory when the user shares something to remember

When scheduling events, always check the calendar first for conflicts.
Use search_memory to find relevant documents; use add_memory to remember user preferences.
Be friendly and confirm when events are successfully created."""


@before_model(can_jump_to=["end"])
async def inject_memory_preferences(state: AgentState, runtime: Runtime[Context]) -> dict[str, Any] | None:
    """Pre-model: read long-term memory for this user and inject a human message with current preferences."""
    store = getattr(runtime, "store", None)
    if not store:
        return None
    ctx = getattr(runtime, "context", None)
    user_id = getattr(ctx, "user_id", None) if ctx else None
    user_id = user_id or "default"
    namespace = (user_id, "memories")
    try:
        results = await store.asearch(namespace, query="user preferences and remembered facts", limit=5)
    except Exception:
        return None
    if not results:
        return None
    parts = []
    for item in results:
        val = item.value if hasattr(item, "value") else item
        mem = val.get("memory", val) if isinstance(val, dict) else str(val)
        parts.append(str(mem))
    text = "Current user preferences:\n" + "\n".join(f"- {p}" for p in parts)
    return {"messages": [AIMessage(content=text)]}


# Create the agent (store is provided by the server when run via LangGraph deployment)
agent = create_agent(
    model=model,
    tools=[read_calendar, write_calendar, search_memory, add_memory],
    system_prompt=SYSTEM_PROMPT,
    context_schema=Context,
    middleware=[inject_memory_preferences],
)
