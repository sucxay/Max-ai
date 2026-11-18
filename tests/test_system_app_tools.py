import subprocess
import unittest
from unittest.mock import patch

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
        type_in_app.invoke({"app_name": "claude", "text": "Draft"})
        self.assertEqual(run.call_args.args[0][-1], "false")

    @patch("ai.tools.system.subprocess.run")
    def test_accessibility_failure_is_reported(self, run):
        run.side_effect = subprocess.CalledProcessError(1, "osascript", stderr="Not authorized")
        result = send_app_prompt.invoke({"app_name": "claude", "text": "Hello"})
        self.assertIn("Accessibility", result)
        self.assertIn("Not authorized", result)
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
