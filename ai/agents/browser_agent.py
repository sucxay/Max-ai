from contextlib import asynccontextmanager
import asyncio
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

from langchain.agents import create_agent
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.checkpoint.memory import InMemorySaver
from mcp.types import TextContent

from ai.llm.llm import get_llm
from ai.mcp.client import client

_DEBUG_LOG = Path("/tmp/max-browser-lifecycle.log")


def log_browser_debug(message: str) -> None:
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    with _DEBUG_LOG.open("a", encoding="utf-8") as log_file:
        log_file.write(f"{timestamp} {message}\n")

SYSTEM_PROMPT = """
You are Nova, an autonomous browser automation agent. Execute the user's
instructions with the Playwright browser tools.

- Use the snapshot included in browser_navigate results to read the page and get
  element refs. Call browser_snapshot if you need a newer or fuller snapshot.
- When the snapshot already contains the information requested, answer directly.
- For a web search, navigate to a search engine, enter the query, submit it, and
  inspect the results. Do not stop after opening the search engine.
- Click an input before typing into it.
- Use the current tab in Max's separate Chrome session.
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
        body = re.sub(r"\s*\[box=[^\]]*\]", "", body)
        text = head + "### Snapshot" + body
    return text[:MAX_CHARS]


async def strip_images_interceptor(request, handler):
    log_browser_debug(f"Calling browser tool: {request.name}")
    result = await handler(request)
    log_browser_debug(f"Browser tool returned: {request.name} (error={result.isError})")
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

_agent = None
_browser_close_tool = None
_lock = asyncio.Lock()
_session = None
_session_task = None
_stop_session = None


async def _run_browser_session(ready, stop):
    """Keep the MCP context open and close it from the task that entered it."""
    try:
        async with client.session("playwright") as session:
            tools = await load_mcp_tools(session, tool_interceptors=[strip_images_interceptor])
            # The browser model resends these schemas on every turn. Keep the
            # validation rules and the guidance for non-obvious arguments.
            for tool in tools:
                schema = tool.args_schema
                if isinstance(schema, dict):
                    schema.pop("$schema", None)
                    for name, argument in schema.get("properties", {}).items():
                        if name not in {"ref", "key", "function", "code"} and argument.get("type") in {
                            "string", "boolean", "integer", "number",
                        }:
                            argument.pop("description", None)
            agent = create_agent(
                model=get_llm(browser=True),
                tools=tools,
                checkpointer=InMemorySaver(),
                system_prompt=SYSTEM_PROMPT,
            )
            close_tool = next((tool for tool in tools if tool.name == "browser_close"), None)
            log_browser_debug("MCP session OPENED")
            ready.set_result((session, agent, close_tool))
            await stop.wait()
    except Exception as exc:
        if not ready.done():
            ready.set_exception(exc)
            return
        raise
    log_browser_debug("MCP session CLOSED")

async def get_agent():
    """Create the shared session on first use."""
    global _agent, _browser_close_tool, _session, _session_task, _stop_session
    async with _lock:
        if _agent is None:
            ready = asyncio.get_running_loop().create_future()
            stop = asyncio.Event()
            owner = asyncio.create_task(_run_browser_session(ready, stop))
            try:
                _session, _agent, _browser_close_tool = await asyncio.shield(ready)
            except BaseException:
                if not ready.done():
                    ready.cancel()
                owner.cancel()
                await asyncio.gather(owner, return_exceptions=True)
                raise
            _session_task, _stop_session = owner, stop
    return _agent


async def open_chrome():
    """Start Chrome or reuse the existing session without changing its pages."""
    result = await _session.call_tool("browser_tabs", {"action": "list"})
    if result.isError:
        details = "\n".join(
            item.text for item in result.content if getattr(item, "type", None) == "text"
        )
        raise RuntimeError(f"Could not open Max's Chrome session: {details}")
    return {"response": "Max's Chrome session is open."}


def is_open_chrome_request(task: str) -> bool:
    return bool(re.fullmatch(
        r"\s*(?:please\s+)?(?:open|launch|start)\s+"
        r"(?:(?:google\s+)?chrome|(?:the\s+)?browser)(?:\s+please)?[.!]?\s*",
        task,
        re.IGNORECASE,
    ))


def navigation_target(task: str):
    """Recognize navigation-only requests; leave interactive tasks to the agent."""
    match = re.fullmatch(
        r"\s*(?:please\s+)?(?:open (?:google )?chrome and\s+)?"
        r"(?:open|visit|navigate to|go to)\s+"
        r"(\S+?)(?:\s+(?:please|in (?:the browser|browser|(?:google )?chrome)))*[.!]?\s*",
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


def search_target(task: str) -> str | None:
    """Extract a standalone web search, leaving follow-up actions to the agent."""
    match = re.fullmatch(
        r"\s*(?:please\s+)?(?:search(?:\s+(?:the web|google|online))?\s+for|"
        r"(?:google|look up))\s+(.+?)\s*",
        task,
        re.IGNORECASE,
    )
    if not match:
        return None
    query = match.group(1).removesuffix(".")
    if not query.strip() or re.search(
        r"\b(?:and|then)\s+(?:open|click|read|summarize|tell|give|find|compare|show|report)\b",
        query,
        re.IGNORECASE,
    ):
        return None
    return query


async def open_web_search(query: str):
    url = "https://www.google.com/search?" + urlencode({"q": query})
    details = await _navigate(url)
    if "/sorry/" in details or "unusual traffic" in details.lower():
        return {"response": "Google blocked the search with a traffic check. Complete the check in Chrome to see the results."}
    return {"response": f"Opened Google search results for **{query}** in Chrome."}


async def open_browser_url(url: str):
    """Return after navigation, without waiting for an unnecessary model turn."""
    await _navigate(url)
    return {"response": f"Opened {url} in Chrome."}


async def _navigate(url: str) -> str:
    result = await _session.call_tool("browser_navigate", {"url": url})
    details = "\n".join(
        item.text for item in result.content if getattr(item, "type", None) == "text"
    )
    if result.isError:
        raise RuntimeError(f"Could not open {url}: {details}")
    log_browser_debug("Browser navigation completed")
    return details


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
    global _agent, _browser_close_tool, _session, _session_task, _stop_session
    async with _lock:
        if _session_task is not None:
            _stop_session.set()
            try:
                await _session_task
            finally:
                _agent = _browser_close_tool = _session = None
                _session_task = _stop_session = None
