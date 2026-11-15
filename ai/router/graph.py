from langgraph.graph import StateGraph, START, END

from ai.router.state import VoiceState
from ai.router.router import router_node, route_task

from ai.agents.apple_agent import apple_agent
from ai.agents.browser_agent import get_existing_agent, log_browser_debug
from ai.agents.system_agent import system_agent
from ai.agents.file_agent import file_agent

_BROWSER_THREAD_ID = "nova-browser"



async def apple_node(state: VoiceState):
    agent = await apple_agent()
    result = await agent.ainvoke({
        "messages": [{"role": "user", "content": state["task"]}]
    })
    return {"response": result["messages"][-1].content}


async def browser_node(state: VoiceState):
    agent = get_existing_agent()
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": state["task"]}]},
        config={"configurable": {"thread_id": _BROWSER_THREAD_ID}},
    )
    for message in result.get("messages", []):
        for tool_call in getattr(message, "tool_calls", []) or []:
            if isinstance(tool_call, dict):
                name = tool_call.get("name")
            else:
                name = getattr(tool_call, "name", None)
            if name:
                print(f">>> Tool call: {name}", flush=True)
                log_browser_debug(f"Tool call: {name}")
    return {"response": result["messages"][-1].content}


async def file_node(state: VoiceState):
    agent = await file_agent()
    result = await agent.ainvoke({
        "messages": [{"role": "user", "content": state["task"]}]
    })
    return {"response": result["messages"][-1].content}


async def system_node(state: VoiceState):
    agent = system_agent()
    result = await agent.ainvoke({
        "messages": [{"role": "user", "content": state["task"]}]
    })
    return {"response": result["messages"][-1].content}


builder = StateGraph(VoiceState)

# Register nodes
builder.add_node("router", router_node)
builder.add_node("apple", apple_node)
builder.add_node("browser", browser_node)
builder.add_node("system", system_node)
builder.add_node("file", file_node)

# Start -> Router
builder.add_edge(START, "router")

# Router -> Selected agent
builder.add_conditional_edges(
    "router",
    route_task,
    {
        "apple": "apple",
        "browser": "browser",
        "system": "system",
        "file": "file",
    }
)

# Selected agent -> End
for node in ["apple", "browser", "system", "file"]:
    builder.add_edge(node, END)

voice_graph = builder.compile()
