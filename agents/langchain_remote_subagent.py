"""
Calendar agent (subagent) with distributed tracing.
Same as langchain_basic (read_calendar, write_calendar) but exposed via make_graph
so the server runs it inside ls.tracing_context, linking to the parent trace when
called by the supervisor via RemoteGraph with distributed_tracing=True.
"""

import contextlib
from typing import List, Dict
from dotenv import load_dotenv
import langsmith as ls
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from agents.utils import model

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

# Compiled calendar agent (used inside make_graph for tracing).
agent = create_agent(
    model=model,
    tools=[read_calendar, write_calendar],
    system_prompt=SYSTEM_PROMPT,
)

@contextlib.asynccontextmanager
async def make_graph(config: RunnableConfig):
    """Context manager that enables distributed tracing when a parent trace is present (execution)."""
    configurable = config.get("configurable", {})
    parent_trace = configurable.get("langsmith-trace")
    parent_project = configurable.get("langsmith-project")
    metadata = configurable.get("langsmith-metadata")
    tags = configurable.get("langsmith-tags")

    with ls.tracing_context(
        parent=parent_trace,
        project_name=parent_project,
        metadata=metadata,
        tags=tags,
    ):
        yield agent
