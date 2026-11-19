"""Browser requests must preserve the shared session for follow-up use."""

import asyncio
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
            patch.object(graph, "prepare_browser_tabs", new_callable=AsyncMock),
            patch.object(graph, "log_browser_debug"),
            patch.object(browser_agent, "log_browser_debug"),
            patch.object(browser_agent, "_session", session),
        ):
            result = await graph.browser_node({"task": "Open Instagram."})
        self.assertEqual(result, {"response": "Opened https://www.instagram.com/ in Chrome."})
        session.call_tool.assert_awaited_once_with(
            "browser_navigate", {"url": "https://www.instagram.com/"}
        )
        agent.ainvoke.assert_not_awaited()

    def test_interactive_requests_still_use_agent(self):
        for task in ("Open Instagram and find my messages", "Search Google for cats"):
            self.assertIsNone(browser_agent.navigation_target(task))

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
            patch.object(graph, "prepare_browser_tabs", new_callable=AsyncMock),
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
            patch.object(graph, "prepare_browser_tabs", new_callable=AsyncMock),
            patch.object(graph, "log_browser_debug"),
        ):
            with self.assertRaisesRegex(TimeoutError, "Tool timeout"):
                await graph.browser_node({"task": "Open a page"})
        close_tool.ainvoke.assert_not_awaited()

    async def test_two_tabs_created_once_and_reused(self):
        session = SimpleNamespace(call_tool=AsyncMock(
            return_value=SimpleNamespace(isError=False)
        ))
        with (
            patch.object(browser_agent, "_session", session),
            patch.object(browser_agent, "_task_tab_count", 0),
        ):
            await browser_agent.prepare_browser_tabs()
            await browser_agent.prepare_browser_tabs()
        self.assertEqual(session.call_tool.await_count, 2)
        for call in session.call_tool.await_args_list:
            self.assertEqual(call.args, ("browser_tabs", {"action": "new"}))

    async def test_failed_tab_creation_can_be_retried(self):
        session = SimpleNamespace(call_tool=AsyncMock(side_effect=[
            SimpleNamespace(isError=False),
            SimpleNamespace(isError=True),
            SimpleNamespace(isError=False),
        ]))
        with (
            patch.object(browser_agent, "_session", session),
            patch.object(browser_agent, "_task_tab_count", 0),
        ):
            with self.assertRaisesRegex(RuntimeError, "Could not open task tabs"):
                await browser_agent.prepare_browser_tabs()
            await browser_agent.prepare_browser_tabs()
            self.assertEqual(browser_agent._task_tab_count, 2)
        self.assertEqual(session.call_tool.await_count, 3)


if __name__ == "__main__":
    unittest.main()
