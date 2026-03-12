"""
Step 1: Basic Calendar Agent
A simple agent with calendar tools (read_calendar, write_calendar)
Demonstrates the basic LangGraph pattern with tools.
"""

from langchain.tools import tool
from agents.utils import model
from typing import List, Dict
from dotenv import load_dotenv

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


# System prompt
SYSTEM_PROMPT = """You are a helpful calendar assistant. You can:
- Read calendar events using read_calendar
- Create new events using write_calendar

When scheduling events, always check the calendar first for conflicts.
Be friendly and confirm when events are successfully created."""

# Augment the LLM with tools
tools = [read_calendar, write_calendar]
tools_by_name = {t.name: t for t in tools}
model_with_tools = model.bind_tools(tools)

# Step 2: Define state

from langchain.messages import AnyMessage
from typing_extensions import TypedDict, Annotated
import operator


class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int

# Step 3: Define model node
from langchain.messages import SystemMessage


def llm_call(state: dict):
    """LLM decides whether to call a tool or not"""

    return {
        "messages": [
            model_with_tools.invoke(
                [
                    SystemMessage(content=SYSTEM_PROMPT)
                ]
                + state["messages"]
            )
        ],
        "llm_calls": state.get('llm_calls', 0) + 1
    }


# Step 4: Define tool node

from langchain.messages import ToolMessage


def tool_node(state: dict):
    """Performs the tool call"""

    result = []
    for tool_call in state["messages"][-1].tool_calls:
        tool = tools_by_name[tool_call["name"]]
        observation = tool.invoke(tool_call["args"])
        result.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
    return {"messages": result}

# Step 5: Define logic to determine whether to end

from typing import Literal
from langgraph.graph import StateGraph, START, END


# Conditional edge function to route to the tool node or end based upon whether the LLM made a tool call
def should_continue(state: MessagesState) -> Literal["tool_node", END]:
    """Decide if we should continue the loop or stop based upon whether the LLM made a tool call"""

    messages = state["messages"]
    last_message = messages[-1]

    # If the LLM makes a tool call, then perform an action
    if last_message.tool_calls:
        return "tool_node"

    # Otherwise, we stop (reply to the user)
    return END

# Step 6: Build agent

# Build workflow
agent_graph = StateGraph(MessagesState)

# Add nodes
agent_graph.add_node("llm_call", llm_call)
agent_graph.add_node("tool_node", tool_node)

# Add edges to connect nodes
agent_graph.add_edge(START, "llm_call")
agent_graph.add_conditional_edges(
    "llm_call",
    should_continue,
    ["tool_node", END]
)
agent_graph.add_edge("tool_node", "llm_call")

# Compile the agent
agent = agent_graph.compile()