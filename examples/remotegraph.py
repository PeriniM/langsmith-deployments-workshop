
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.pregel.remote import RemoteGraph

url = "http://localhost:2024"
graph_name = "langchain_basic"
remote_graph = RemoteGraph(graph_name, url=url)

# define parent graph
builder = StateGraph(MessagesState)
# add remote graph directly as a node
builder.add_node("child", remote_graph)
builder.add_edge(START, "child")
graph = builder.compile()

# stream outputs from both the parent graph and subgraph
for chunk in graph.stream({
    "messages": [{"role": "user", "content": "What can you do?"}]
}, subgraphs=True):
    print(chunk)