"""
LangGraph Assistant with configurable model (OpenAI or Anthropic) and system prompt.
Uses assistant context so you can set per-assistant:
- model_name: "openai" | "anthropic" (dropdown, default "openai")
- system_prompt: optional override; when omitted, the default calendar assistant prompt is used.
"""

from langchain.tools import tool
from agents.utils import get_model
from typing import List, Dict
from dotenv import load_dotenv
from langchain.messages import SystemMessage, ToolMessage

load_dotenv(override=True)

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
    for event in _calendar_events:
        if event["date"] == date and event["time"] == time:
            return f"Conflict: There's already an event '{event['title']}' scheduled for {date} at {time}"

    new_event = {"title": title, "date": date, "time": time, "location": location}
    _calendar_events.append(new_event)
    return f"Successfully created event '{title}' on {date} at {time} in {location}"


SYSTEM_PROMPT = """You are a helpful calendar assistant. You can:
- Read calendar events using read_calendar
- Create new events using write_calendar

When scheduling events, always check the calendar first for conflicts.
Be friendly and confirm when events are successfully created."""

# Default context so the UI can show the default system prompt when editing.
# When creating an assistant, pass context=DEFAULT_CONTEXT to pre-fill the form.
DEFAULT_CONTEXT: dict = {
    "model_name": "openai",
    "system_prompt": SYSTEM_PROMPT,
}

tools = [read_calendar, write_calendar]
tools_by_name = {t.name: t for t in tools}

# State and context schemas
from langchain.messages import AnyMessage
from typing import Literal
from typing_extensions import TypedDict, Annotated
import operator
from langgraph.runtime import Runtime
from pydantic import BaseModel, Field


class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int


# Literal restricts to these values so Studio can render a dropdown
ModelName = Literal["openai", "anthropic"]


class ContextSchema(BaseModel):
    """Context for this assistant. Defaults are set so the UI shows the default prompt when editing."""
    model_name: ModelName = Field(
        default="openai",
        description="LLM provider",
        json_schema_extra={
            "title": "LLM Provider",
            "langgraph_nodes": ["llm_call"],
            "langgraph_type": "dropdown",
        })
    system_prompt: str = Field(
        default=SYSTEM_PROMPT,
        description="System prompt for the assistant",
        json_schema_extra={
            "title": "System Prompt",
            "langgraph_nodes": ["llm_call"],
            "langgraph_type": "prompt",
        })


def llm_call(state: dict, runtime: Runtime[ContextSchema]):
    """LLM node: model and system prompt from context, merged with DEFAULT_CONTEXT."""
    ctx = {**DEFAULT_CONTEXT, **(runtime.context or {})}
    raw = ctx.get("model_name", "openai")
    model_name: ModelName = raw if raw in ("openai", "anthropic") else "openai"
    system_prompt = ctx.get("system_prompt") or SYSTEM_PROMPT
    model = get_model(model_name)
    model_with_tools = model.bind_tools(tools)

    return {
        "messages": [
            model_with_tools.invoke(
                [SystemMessage(content=system_prompt)] + state["messages"]
            )
        ],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


def tool_node(state: dict):
    """Execute tool calls from the last message."""
    result = []
    for tool_call in state["messages"][-1].tool_calls:
        tool = tools_by_name[tool_call["name"]]
        observation = tool.invoke(tool_call["args"])
        result.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
    return {"messages": result}


from typing import Literal
from langgraph.graph import StateGraph, START, END


def should_continue(state: MessagesState) -> Literal["tool_node", END]:
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "tool_node"
    return END


# Build graph with context_schema so assistants can set model_name
agent_graph = StateGraph(MessagesState, context_schema=ContextSchema)
agent_graph.add_node("llm_call", llm_call)
agent_graph.add_node("tool_node", tool_node)
agent_graph.add_edge(START, "llm_call")
agent_graph.add_conditional_edges("llm_call", should_continue, ["tool_node", END])
agent_graph.add_edge("tool_node", "llm_call")

agent = agent_graph.compile()
