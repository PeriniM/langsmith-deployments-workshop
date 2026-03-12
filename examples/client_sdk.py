from langgraph_sdk import get_sync_client # or get_client for async
from dotenv import load_dotenv
import os

load_dotenv(override=True)

client = get_sync_client(url="http://localhost:2024", api_key=os.getenv("LANGSMITH_API_KEY"))

for chunk in client.runs.stream(
    None,    # Threadless run
    "langchain_basic", # Name of agent. Defined in langgraph.json.
    input={
        "messages": [{
            "role": "human",
            "content": "What can you do?",
        }],
    },
    stream_mode="updates",
):
    print(f"Receiving new event of type: {chunk.event}...")
    print(chunk.data)
    print("\n\n")