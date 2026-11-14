from typing import Literal

from pydantic import BaseModel

from ai.llm.llm import get_llm
from ai.prompts.router_prompt import ROUTER_PROMPT
llm = get_llm()


class RouterDecision(BaseModel):
    agent: Literal["apple", "browser", "system", "file"]
    task: str
    reason: str


router_llm = llm.with_structured_output(RouterDecision)



async def router_node(state):
    decision = await router_llm.ainvoke([
        {
            "role":"system",
            "content":ROUTER_PROMPT
        },
        {
            "role":"user",
            "content":state['user_input']

        }
        
    ])
    return {
        "agent" : decision.agent,
        "task":decision.task,
        "reason":decision.reason
    }


def route_task(state):
    return state["agent"]
