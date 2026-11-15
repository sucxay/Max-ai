from contextlib import asynccontextmanager, AsyncExitStack
import asyncio
import logging
from datetime import datetime
from pathlib import Path

from langchain.agents import create_agent
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.checkpoint.memory import InMemorySaver
from mcp.types import TextContent

from ai.llm.llm import get_llm
from ai.mcp.client import client

logger = logging.getLogger(__name__)
_DEBUG_LOG = Path("/tmp/max-browser-lifecycle.log")


def log_browser_debug(message: str) -> None:
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    with _DEBUG_LOG.open("a", encoding="utf-8") as log_file:
        log_file.write(f"{timestamp} {message}\n")

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

_stack = AsyncExitStack()
_agent = None
_lock = asyncio.Lock()

async def get_agent():
    """Create the session + agent once, then reuse it forever."""
    global _agent
    async with _lock:
        if _agent is None:
            session = await _stack.enter_async_context(client.session("playwright"))
            print(">>> MCP session OPENED", flush=True)
            log_browser_debug("MCP session OPENED")
            logger.info("Playwright MCP session opened")
            tools = await load_mcp_tools(session, tool_interceptors=[strip_images_interceptor])
            tools = [t for t in tools if t.name in ALLOWED_TOOLS]
            log_browser_debug(f"Filtered browser tools: {[tool.name for tool in tools]}")
            _agent = create_agent(
                model=get_llm(),
                tools=tools,
                checkpointer=InMemorySaver(),
                system_prompt=SYSTEM_PROMPT,
            )
    return _agent


def get_existing_agent():
    """Return the startup-initialized agent without opening a session."""
    if _agent is None:
        raise RuntimeError("Browser agent has not been initialized at startup.")
    return _agent


@asynccontextmanager
async def browser_agent():
    # Same interface as before, so callers don't change.
    # Exiting this block no longer closes the browser.
    yield await get_agent()

async def close_browser_agent():
    """Close the shared Playwright session during application shutdown."""
    global _agent
    if _agent is not None:
        await _stack.aclose()
        print(">>> MCP session CLOSED", flush=True)
        log_browser_debug("MCP session CLOSED")
        logger.info("Playwright MCP session closed")
        _agent = None
