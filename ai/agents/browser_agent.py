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
- For a web search, navigate to a search engine, enter the query, submit it, and
  inspect the results. Do not stop after opening the search engine.
- Click an input before typing into it.
- Two dedicated tabs are opened for you in the user's existing Chrome session.
  Use browser_tabs to select and reuse them. Leave the user's other tabs alone.
  Do not open additional tabs unless the task requires them.
- Dismiss popups like "Not Now" or "Save login info" first.
- Complete the whole task instead of stopping after opening a site.
- For a request that only asks to open a site, successful navigation completes
  the task. Reply immediately; do not search, inspect unrelated elements, or wait
  for the user to interact. For other tasks, stop once the requested result is verified.
- If blocked by login, CAPTCHA, or an error, tell the user.
- Never claim success without verifying it on the page.
- Keep the browser open after tasks so the user can interact with it and
  continue in later turns. Only use browser_close when the user asks to close it.
- Ask for confirmation before sending messages, purchases, or destructive actions.
- Understand short replies like "yes" or "go ahead" from the previous turn.
"""


import re

MAX_CHARS = 4000


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
_browser_close_tool = None
_lock = asyncio.Lock()
_tabs_lock = asyncio.Lock()
_session = None
_task_tab_count = 0

async def get_agent():
    """Create the session + agent once, then reuse it forever."""
    global _agent, _browser_close_tool, _session
    async with _lock:
        if _agent is None:
            session = await _stack.enter_async_context(client.session("playwright"))
            print(">>> MCP session OPENED", flush=True)
            log_browser_debug("MCP session OPENED")
            logger.info("Playwright MCP session opened")
            tools = await load_mcp_tools(session, tool_interceptors=[strip_images_interceptor])
            available_names = [tool.name for tool in tools]
            _browser_close_tool = next(
                (tool for tool in tools if tool.name == "browser_close"), None
            )
            log_browser_debug(
                f"Loaded all Playwright MCP tools: {available_names}"
            )
            _agent = create_agent(
                model=get_llm(),
                tools=tools,
                checkpointer=InMemorySaver(),
                system_prompt=SYSTEM_PROMPT,
            )
            _session = session
    return _agent


async def prepare_browser_tabs():
    """Create two task tabs once per connection, without replacing user tabs."""
    global _task_tab_count
    async with _tabs_lock:
        if _session is None:
            raise RuntimeError("Browser agent has not been initialized at startup.")
        while _task_tab_count < 2:
            result = await _session.call_tool("browser_tabs", {"action": "new"})
            if result.isError:
                raise RuntimeError(
                    "Could not open task tabs in Chrome. Open chrome://inspect/#remote-debugging "
                    "and enable 'Allow remote debugging for this browser instance', "
                    "then approve the connection in Chrome."
                )
            _task_tab_count += 1


def navigation_target(task: str):
    """Recognize navigation-only requests; leave interactive tasks to the agent."""
    match = re.fullmatch(
        r"\s*(?:please\s+)?(?:open|visit|navigate to|go to)\s+"
        r"(\S+?)(?:\s+(?:please|in (?:the )?browser))?[.!]?\s*",
        task, re.IGNORECASE,
    )
    if not match:
        return None
    target = match.group(1)
    sites = {
        "instagram": "https://www.instagram.com/",
        "youtube": "https://www.youtube.com/",
        "google": "https://www.google.com/",
        "gmail": "https://mail.google.com/",
        "facebook": "https://www.facebook.com/",
        "reddit": "https://www.reddit.com/",
    }
    if target.lower() in sites:
        return sites[target.lower()]
    if re.fullmatch(r"(?:https?://)?[\w-]+(?:\.[\w-]+)+(?:[/:?#][^\s]*)?", target):
        return target if target.startswith(("http://", "https://")) else f"https://{target}"
    return None


async def open_browser_url(url: str):
    """Return after navigation, without waiting for an unnecessary model turn."""
    result = await _session.call_tool("browser_navigate", {"url": url})
    details = "\n".join(
        item.text for item in result.content if getattr(item, "type", None) == "text"
    )
    if result.isError:
        raise RuntimeError(f"Could not open {url}: {details}")
    log_browser_debug(f"Navigation completed: {url}")
    return {"response": f"Opened {url} in Chrome."}


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


async def close_browser_tab():
    """Close the controlled browser after a task without another model turn."""
    if _browser_close_tool is None:
        return
    try:
        await asyncio.wait_for(_browser_close_tool.ainvoke({}), timeout=8)
        log_browser_debug("Browser closed after task")
    except Exception as exc:
        # Task results should still be returned when browser cleanup fails.
        log_browser_debug(f"Browser close failed: {type(exc).__name__}: {exc}")

async def close_browser_agent():
    """Close the shared Playwright session during application shutdown."""
    global _agent, _stack, _browser_close_tool, _session, _task_tab_count
    async with _lock:
        if _agent is not None:
            await _stack.aclose()
            print(">>> MCP session CLOSED", flush=True)
            log_browser_debug("MCP session CLOSED")
            logger.info("Playwright MCP session closed")
            _agent = None
            _browser_close_tool = None
            _session = None
            _task_tab_count = 0
            # AsyncExitStack is one-shot once closed; create a fresh stack for
            # the next request (or application restart in the same process).
            _stack = AsyncExitStack()
