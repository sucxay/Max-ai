from contextlib import asynccontextmanager

from langchain.agents import create_agent
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.checkpoint.memory import InMemorySaver
from mcp.types import TextContent

from ai.llm.llm import get_llm
from ai.mcp.client import client

SYSTEM_PROMPT = """
You are Nova, an autonomous browser automation agent. Execute the user's
instructions with the Playwright browser tools.

- After browser_navigate, call browser_snapshot to see the page and get element refs.
- Click an input before typing into it.
- Dismiss popups like "Not Now" or "Save login info" first.
- Complete the whole task instead of stopping after opening a site.
- If blocked by login, CAPTCHA, or an error, tell the user.
- Never claim success without verifying it on the page.
- Ask for confirmation before sending messages, purchases, or destructive actions.
- Understand short replies like "yes" or "go ahead" from the previous turn.
"""


import re

MAX_CHARS = 4000
ALLOWED_TOOLS = {
    "browser_navigate", "browser_snapshot", "browser_click",
    "browser_type", "browser_press_key", "browser_wait_for",
    "browser_navigate_back",
}


def shrink(text: str) -> str:
    if "### Snapshot" in text:
        head, _, body = text.partition("### Snapshot")
        # keep only interactive lines (they carry the refs) and drop bounding boxes
        lines = [re.sub(r"\s*\[box=[^\]]*\]", "", l) for l in body.splitlines() if "[ref=" in l]
        text = head + "### Snapshot\n" + "\n".join(lines)
    return text[:MAX_CHARS]


async def strip_images_interceptor(request, handler):
    result = await handler(request)
    if hasattr(result, "content") and isinstance(result.content, list):
        cleaned = []
        for item in result.content:
            t = getattr(item, "type", None)
            if t == "image":
                cleaned.append(TextContent(type="text", text="[Screenshot captured]"))
            elif t == "text":
                cleaned.append(TextContent(type="text", text=shrink(item.text)))
            else:
                cleaned.append(item)
        result.content = cleaned or [TextContent(type="text", text="Action completed.")]
    return result

@asynccontextmanager
async def browser_agent():
    async with client.session("playwright") as session:
        tools = await load_mcp_tools(session, tool_interceptors=[strip_images_interceptor])
        tools = [t for t in tools if t.name in ALLOWED_TOOLS]
        agent = create_agent(
            model=get_llm(),
            tools=tools,
            checkpointer=InMemorySaver(),
            system_prompt=SYSTEM_PROMPT,
        )
        yield agent   # nothing after this line