"""
Invoke the langchain_advanced agent via POST /api/v1/invoke.
Run first: uv run langgraph dev --config ./langgraph_advanced.json
Then: uv run python examples/invoke_advanced_agent.py
"""
import json
import urllib.request

url = "http://localhost:2024/api/v1/invoke"
body = json.dumps({
    "message": "What can you do? Do you have any documents or preferences for me?",
    "user_id": "user1",
}).encode("utf-8")
req = urllib.request.Request(
    url,
    data=body,
    method="POST",
    headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer user1-token",
        "x-user-id": "user1",
    },
)

print(f"POST {url} ...")
print()
try:
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)
        print("Assistant:", data.get("content", data))
except urllib.error.HTTPError as e:
    print(f"Error {e.code}: {e.reason}")
    if e.fp:
        print(e.fp.read().decode())
