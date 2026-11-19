from langgraph.graph import StateGraph, START, END

from ai.router.state import VoiceState
from ai.router.router import router_node, route_task

from ai.agents.apple_agent import apple_agent
from ai.agents.browser_agent import (
    get_agent, log_browser_debug, prepare_browser_tabs,
    navigation_target, open_browser_url,
)
from ai.agents.system_agent import system_agent
from ai.agents.file_agent import file_agent
from ai.agents.convo_agent import convo_agent

_BROWSER_THREAD_ID = "nova-browser"



async def apple_node(state: VoiceState):
    agent = await apple_agent()
    result = await agent.ainvoke({
        "messages": [{"role": "user", "content": state["task"]}]
    })
    return {"response": result["messages"][-1].content}


async def browser_node(state: VoiceState):
    # Connect to Chrome only when a browser task is requested. Max should still
    # launch when Chrome is closed or remote debugging has not been enabled.
    agent = await get_agent()
    await prepare_browser_tabs()
    log_browser_debug("Browser task started")
    url = navigation_target(state["task"])
    if url:
        return await open_browser_url(url)
    # Browser tasks can include logins and other user interaction. Keep the
    # shared session alive across requests and close it only at app shutdown.
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": state["task"]}]},
        config={
            "configurable": {"thread_id": _BROWSER_THREAD_ID},
            "recursion_limit": 16,
        },
    )
    log_browser_debug("Browser task returned")
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


async def convo_node(state: VoiceState):
    agent = convo_agent()
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
builder.add_node("convo", convo_node)

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
        "convo": "convo",
    }
)

# Selected agent -> End
for node in ["apple", "browser", "system", "file", "convo"]:
    builder.add_edge(node, END)

voice_graph = builder.compile()
