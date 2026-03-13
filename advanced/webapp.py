# ./advanced/webapp.py
"""
Custom FastAPI app mounted by the LangGraph server (see langgraph_advanced.json http.app).
Routes are: GET /hello, POST /invoke.
"""
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel
from langgraph_sdk import get_client

app = FastAPI(title="Advanced API", description="Custom routes + graph invoke")

# Must match langgraph_advanced.json graph id
GRAPH_ID = "langchain_advanced"

class InvokeRequest(BaseModel):
    """Body for POST /invoke."""
    message: str
    user_id: str | None = None  # optional; overridden by x-user-id header if present


class InvokeResponse(BaseModel):
    """Response from POST /invoke."""
    content: str
    graph_id: str = GRAPH_ID


@app.get("/hello")
async def read_root():
    return {"Hello": "World"}


@app.post("/invoke", response_model=InvokeResponse)
async def invoke_graph(
    request: Request,
    body: InvokeRequest,
    x_user_id: str | None = Header(None, alias="x-user-id"),
) -> InvokeResponse:
    """
    Invoke the langchain_advanced graph with one user message.
    Client is built with url=request base (scheme+host+port) so it hits this server's graph API.
    """
    user_id = x_user_id or body.user_id or "default"
    client = get_client()
    # Forward auth and configurable headers so the internal /runs/wait call is allowed
    headers = {}
    if request.headers.get("authorization"):
        headers["authorization"] = request.headers["authorization"]
    if x_user_id:
        headers["x-user-id"] = x_user_id
    try:
        result = await client.runs.wait(
            None,
            GRAPH_ID,
            input={
                "messages": [{"role": "human", "content": body.message}],
            },
            context={"user_id": user_id},
            headers=headers or None,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Graph run failed: {e!s}") from e

    messages = result.get("messages") if isinstance(result, dict) else []
    if not messages:
        return InvokeResponse(content="(No response from graph.)")
    last = messages[-1]
    content = last.get("content", "") if isinstance(last, dict) else getattr(last, "content", str(last))
    return InvokeResponse(content=content if isinstance(content, str) else str(content))
