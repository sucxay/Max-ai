from typing import Literal

from pydantic import BaseModel, Field

from ai.llm.llm import get_llm
from ai.prompts.router_prompt import ROUTER_PROMPT
from ai.router.state import DesktopInput
llm = get_llm()


class RouterDecision(BaseModel):
    agent: Literal["apple", "browser", "system", "file", "convo"]
    task: str
    reason: str
    desktop_input: DesktopInput | None = Field(
        default=None,
        description="The named desktop app, exact text, and whether to submit it. Set only for an explicitly requested text-entry action.",
    )


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
        "reason":decision.reason,
        "desktop_input": decision.desktop_input,
    }


def route_task(state):
    return state["agent"]
