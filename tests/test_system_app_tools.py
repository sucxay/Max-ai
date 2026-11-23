import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from ai.router import graph, router
from ai.tools.system import send_app_prompt, type_in_app


class AppToolTests(unittest.TestCase):
    @patch("ai.tools.system.subprocess.run")
    def test_prompt_is_passed_as_data_and_submitted_once(self, run):
        text = 'Explain "hello"\nUnicode: नमस्ते 🐱; $(whoami)'
        result = send_app_prompt.invoke({"app_name": "chatgpt", "text": text})
        run.assert_called_once()
        args, kwargs = run.call_args
        self.assertEqual(args[0], ["osascript", "-", "ChatGPT", text, "true"])
        self.assertNotIn(text, kwargs["input"])
        self.assertNotIn("shell", kwargs)
        self.assertIn("Delivery has not been verified", result)

    @patch("ai.tools.system.subprocess.run")
    def test_draft_does_not_submit(self, run):
        type_in_app.invoke({"app_name": "Claude Desktop", "text": "Draft"})
        self.assertEqual(run.call_args.args[0][2], "Claude")
        self.assertEqual(run.call_args.args[0][-1], "false")

    @patch("ai.tools.system.subprocess.run")
    def test_accessibility_failure_is_reported(self, run):
        run.side_effect = subprocess.CalledProcessError(
            1, "osascript", stderr="osascript is not allowed assistive access. (-25211)"
        )
        result = send_app_prompt.invoke({"app_name": "claude", "text": "Hello"})
        self.assertIn("Accessibility", result)
        self.assertIn("assistive access", result)
        run.assert_called_once()

    @patch("ai.tools.system.subprocess.run")
    def test_automation_failure_names_system_events(self, run):
        run.side_effect = subprocess.CalledProcessError(
            1, "osascript", stderr="Not authorized to send Apple events. (-1743)"
        )
        result = send_app_prompt.invoke({"app_name": "claude", "text": "Hello"})
        self.assertIn("Privacy & Security → Automation", result)
        self.assertIn("System Events", result)
        run.assert_called_once()

    @patch("ai.tools.system.subprocess.run")
    def test_empty_text_does_not_send(self, run):
        send_app_prompt.invoke({"app_name": "claude", "text": " "})
        run.assert_not_called()

    @patch("ai.tools.system.subprocess.run")
    def test_timeout_does_not_retry(self, run):
        run.side_effect = subprocess.TimeoutExpired("osascript", 20)
        result = send_app_prompt.invoke({"app_name": "claude", "text": "Hello"})
        self.assertIn("may already have been entered", result)
        run.assert_called_once()


class DesktopInputRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_open_and_ask_calls_submission_tool_directly(self):
        text = 'Explain "hello" in two lines.'
        decision = router.RouterDecision(
            agent="system",
            task=f"Open Claude Desktop and ask it: {text}",
            reason="Desktop prompt",
            desktop_input={"app_name": "Claude Desktop", "text": text, "submit": True},
        )
        send = SimpleNamespace(ainvoke=AsyncMock(return_value="Pressed Return."))
        with (
            patch.object(router, "router_llm", SimpleNamespace(
                ainvoke=AsyncMock(return_value=decision)
            )),
            patch.object(graph, "send_app_prompt", send),
            patch.object(graph, "system_agent") as agent,
        ):
            result = await graph.voice_graph.ainvoke({"user_input": decision.task})
        send.ainvoke.assert_awaited_once_with({"app_name": "Claude Desktop", "text": text})
        agent.assert_not_called()
        self.assertEqual(result["response"], "Pressed Return.")

    async def test_draft_returns_the_typing_error_without_submitting(self):
        error = "Claude's message input lost focus."
        draft = SimpleNamespace(ainvoke=AsyncMock(return_value=error))
        with (
            patch.object(graph, "type_in_app", draft),
            patch.object(graph, "send_app_prompt") as send,
        ):
            result = await graph.system_node({
                "desktop_input": {"app_name": "Claude", "text": "Draft", "submit": False}
            })
        draft.ainvoke.assert_awaited_once_with({"app_name": "Claude", "text": "Draft"})
        send.assert_not_called()
        self.assertEqual(result["response"], error)
