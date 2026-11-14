from langgraph.graph import StateGraph, START, END

from ai.router.state import VoiceState
from ai.router.router import router_node, route_task

from ai.agents.apple_agent import apple_agent
from ai.agents.browser_agent import browser_agent
from ai.agents.system_agent import system_agent
from ai.agents.file_agent import file_agent



async def apple_node(state: VoiceState):
    agent = await apple_agent()
    result = await agent.ainvoke({
        "messages": [{"role": "user", "content": state["task"]}]
    })
    return {"response": result["messages"][-1].content}


async def browser_node(state: VoiceState):
    async with browser_agent() as agent:
        result = await agent.ainvoke({
            "messages": [{"role": "user", "content": state["task"]}]
        })
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
