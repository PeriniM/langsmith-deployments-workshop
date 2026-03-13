"""
Supervisor agent with a subagent-as-tool that calls the calendar graph in the same deployment.
RemoteGraph is defined at module level (no context manager). The calendar is invoked by name
via RemoteGraph with distributed_tracing=True so the subagent receives trace context.
"""

from langchain.agents import create_agent
from langchain.tools import tool
from langgraph_sdk import get_client, get_sync_client
from langgraph.pregel.remote import RemoteGraph
from dotenv import load_dotenv
from agents.utils import model

load_dotenv(override=True)

# General agent system prompt: can delegate to calendar for read/schedule.
GENERAL_SYSTEM_PROMPT = """You are a helpful general assistant. You can answer questions and help with tasks.
For reading or scheduling calendar events, use the calendar tool to delegate to the calendar assistant.
Use the calendar tool when the user asks about events, schedule, availability, or booking."""

# Module-level clients and RemoteGraph (no context manager).
# Note: In-process calls (url=None) from supervisor to subagent can deadlock with a single
# worker. Run with multiple workers if the run gets stuck in the tools step (e.g. langgraph dev --n-jobs-per-worker 2 or use a separate deployment URL for the subagent).
_client = get_client()
_sync_client = get_sync_client()

# Name of the calendar graph in this deployment (must match langgraph.json).
# Use the graph that has make_graph with tracing context (langchain_remote_subagent).
CALENDAR_GRAPH_ID = "langchain_remote_subagent"

# Remote calendar graph
remote_calendar = RemoteGraph(
    CALENDAR_GRAPH_ID,
    client=_client,
    sync_client=_sync_client,
    distributed_tracing=True,
)

# Calendar subagent tool that calls the calendar graph via RemoteGraph.ainvoke
@tool(
    "calendar_subagent",
    description="Subagent that can read or update the calendar. Use for: listing events, checking availability, scheduling or creating events. Pass the user's request as the query.",
)
async def calendar_subagent(query: str) -> str:
    """Call the calendar graph via RemoteGraph.ainvoke (closes over remote_calendar)."""
    result = await remote_calendar.ainvoke({
        "messages": [{"role": "human", "content": query}],
    })
    messages = result.get("messages") or []
    return (messages[-1].get("content", "") if isinstance(messages[-1], dict) else getattr(messages[-1], "content", "")) if messages else ""

# Create the general agent with the calendar subagent tool
agent = create_agent(
    model=model,
    tools=[calendar_subagent],
    system_prompt=GENERAL_SYSTEM_PROMPT,
)
