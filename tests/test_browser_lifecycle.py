"""Browser requests must preserve the shared session for follow-up use."""

import asyncio
from contextlib import asynccontextmanager
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from ai.agents import browser_agent
from ai.router import graph


class BrowserLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_open_instagram_finishes_without_model_loop(self):
        agent = SimpleNamespace(ainvoke=AsyncMock())
        session = SimpleNamespace(call_tool=AsyncMock(return_value=SimpleNamespace(
            isError=False, content=[]
        )))
        with (
            patch.object(graph, "get_agent", new_callable=AsyncMock, return_value=agent),
            patch.object(graph, "log_browser_debug"),
            patch.object(browser_agent, "log_browser_debug"),
            patch.object(browser_agent, "_session", session),
        ):
            result = await graph.browser_node({"task": "Open Instagram in Chrome."})
        self.assertEqual(result, {"response": "Opened https://www.instagram.com/ in Chrome."})
        session.call_tool.assert_awaited_once_with(
            "browser_navigate", {"url": "https://www.instagram.com/"}
        )
        agent.ainvoke.assert_not_awaited()

    def test_interactive_requests_still_use_agent(self):
        for task in ("Open Instagram and find my messages", "Search Google for cats and open the first result"):
            self.assertIsNone(browser_agent.navigation_target(task))
            self.assertIsNone(browser_agent.search_target(task))

    def test_navigation_accepts_router_rewrite(self):
        self.assertEqual(
            browser_agent.navigation_target("Open Chrome and navigate to https://example.com"),
            "https://example.com",
        )

    async def test_plain_web_search_opens_results_directly(self):
        agent = SimpleNamespace(ainvoke=AsyncMock())
        session = SimpleNamespace(call_tool=AsyncMock(
            return_value=SimpleNamespace(isError=False, content=[])
        ))
        with (
            patch.object(graph, "get_agent", new_callable=AsyncMock, return_value=agent),
            patch.object(browser_agent, "_session", session),
            patch.object(browser_agent, "log_browser_debug"),
        ):
            result = await graph.browser_node({"task": "Search the web for C++ & Python."})
        self.assertIn("C++ & Python", result["response"])
        session.call_tool.assert_awaited_once_with(
            "browser_navigate", {"url": "https://www.google.com/search?q=C%2B%2B+%26+Python"}
        )
        agent.ainvoke.assert_not_awaited()

    async def test_session_can_be_closed_from_a_different_request_task(self):
        tasks = []

        @asynccontextmanager
        async def session(_):
            tasks.append(asyncio.current_task())
            try:
                yield object()
            finally:
                tasks.append(asyncio.current_task())

        with (
            patch.object(browser_agent.client, "session", session),
            patch.object(browser_agent, "load_mcp_tools", new_callable=AsyncMock, return_value=[]),
            patch.object(browser_agent, "get_llm"),
            patch.object(browser_agent, "create_agent"),
            patch.object(browser_agent, "log_browser_debug"),
        ):
            await asyncio.create_task(browser_agent.get_agent())
            await browser_agent.close_browser_agent()
        self.assertEqual(len(tasks), 2)
        self.assertIs(tasks[0], tasks[1])

    async def test_navigation_failure_is_not_reported_as_success(self):
        session = SimpleNamespace(call_tool=AsyncMock(return_value=SimpleNamespace(
            isError=True, content=[]
        )))
        with patch.object(browser_agent, "_session", session):
            with self.assertRaisesRegex(RuntimeError, "Could not open"):
                await browser_agent.open_browser_url("https://www.instagram.com/")

    async def test_requests_reuse_session_without_deadline_or_close(self):
        agent = SimpleNamespace(
            ainvoke=AsyncMock(return_value={
                "messages": [SimpleNamespace(content="Ready", tool_calls=[])]
            })
        )
        close_tool = SimpleNamespace(ainvoke=AsyncMock())
        with (
            patch.object(browser_agent, "_browser_close_tool", close_tool),
            patch.object(graph, "get_agent", new_callable=AsyncMock, return_value=agent),
            patch.object(graph, "log_browser_debug"),
            patch.object(asyncio, "wait_for", side_effect=AssertionError("Unexpected deadline")),
        ):
            for task in ("Open the login page", "Continue after login"):
                self.assertEqual(
                    await graph.browser_node({"task": task}),
                    {"response": "Ready"},
                )
        close_tool.ainvoke.assert_not_awaited()
        self.assertEqual(agent.ainvoke.await_count, 2)
        configs = [call.kwargs["config"] for call in agent.ainvoke.await_args_list]
        self.assertEqual(configs[0], configs[1])

    async def test_tool_timeout_does_not_close_browser(self):
        agent = SimpleNamespace(ainvoke=AsyncMock(side_effect=TimeoutError("Tool timeout")))
        close_tool = SimpleNamespace(ainvoke=AsyncMock())
        with (
            patch.object(browser_agent, "_browser_close_tool", close_tool),
            patch.object(graph, "get_agent", new_callable=AsyncMock, return_value=agent),
            patch.object(graph, "log_browser_debug"),
        ):
            with self.assertRaisesRegex(TimeoutError, "Tool timeout"):
                await graph.browser_node({"task": "Open a page"})
        close_tool.ainvoke.assert_not_awaited()

    async def test_open_chrome_reuses_existing_tabs_without_model_loop(self):
        agent = SimpleNamespace(ainvoke=AsyncMock())
        session = SimpleNamespace(call_tool=AsyncMock(
            return_value=SimpleNamespace(isError=False, content=[])
        ))
        with (
            patch.object(graph, "get_agent", new_callable=AsyncMock, return_value=agent),
            patch.object(graph, "log_browser_debug"),
            patch.object(browser_agent, "_session", session),
        ):
            result = await graph.browser_node({"task": "Open Google Chrome."})
        self.assertEqual(result, {"response": "Max's Chrome session is open."})
        session.call_tool.assert_awaited_once_with("browser_tabs", {"action": "list"})
        agent.ainvoke.assert_not_awaited()

    async def test_chrome_launch_failure_is_reported(self):
        session = SimpleNamespace(call_tool=AsyncMock(return_value=SimpleNamespace(
            isError=True, content=[SimpleNamespace(type="text", text="Chrome not found")]
        )))
        with patch.object(browser_agent, "_session", session):
            with self.assertRaisesRegex(RuntimeError, "Chrome not found"):
                await browser_agent.open_chrome()


if __name__ == "__main__":
    unittest.main()
