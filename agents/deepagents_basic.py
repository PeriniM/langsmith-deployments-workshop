"""
Step 10: Introduction to Deep Agents
Demonstrates the transition from create_agent to create_deep_agent.
Deep agents come with built-in capabilities: planning (todos), file system tools, and subagents.
"""

from deepagents import create_deep_agent
from langchain.tools import tool
from typing import List, Dict
from dotenv import load_dotenv
from agents.utils import model

load_dotenv(override=True)

# Mock calendar storage
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


# System prompt - deep agents benefit from detailed instructions
SYSTEM_PROMPT = """You are a helpful calendar assistant with advanced planning capabilities. You can:
- Read calendar events using read_calendar
- Create new events using write_calendar

Built-in Deep Agent Capabilities:
- write_todos: Break down complex tasks into steps (automatically available)
- File system tools: ls, read_file, write_file, edit_file (automatically available)
  * Use these to store notes, drafts, or large amounts of information
  * Files are stored in agent state and persist within the conversation thread
- Task delegation: Spawn subagents for complex subtasks (automatically available)

When handling multi-step requests:
1. Use write_todos to plan your approach
2. Check the calendar first for conflicts
3. Use file system tools to save notes or drafts if needed
4. Execute the plan step by step

Be friendly and confirm when events are successfully created."""

# Create a deep agent using create_deep_agent
# This automatically includes TodoListMiddleware, FilesystemMiddleware, and SubAgentMiddleware
agent = create_deep_agent(
    model=model,
    tools=[read_calendar, write_calendar],
    system_prompt=SYSTEM_PROMPT
)