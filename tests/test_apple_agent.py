import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from ai.agents.apple_agent import apple_agent
from ai.tools.music import apple_music


class AppleAgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_discovered_tools_and_music_are_exposed(self):
        tools = [SimpleNamespace(name=name, description=f"{name} operations")
                 for name in ("calendar", "reminders", "maps", "future_apple_tool")]
        with (
            patch("ai.agents.apple_agent.get_apple_tools", AsyncMock(return_value=tools)),
            patch("ai.agents.apple_agent.get_llm"),
            patch("ai.agents.apple_agent.create_agent") as create,
        ):
            await apple_agent()
        self.assertEqual(create.call_args.kwargs["tools"], tools + [apple_music])
        prompt = create.call_args.kwargs["system_prompt"]
        for name in ("future_apple_tool", "maps", "apple_music", "Current local date/time"):
            self.assertIn(name, prompt)


class MusicTests(unittest.TestCase):
    @patch("ai.tools.music.subprocess.run")
    def test_query_is_data_and_playback_state_returned(self, run):
        run.return_value.stdout = "Player state: playing; Test — Artist\n"
        query = 'Song "name"\n$(whoami)'
        result = apple_music.invoke({"action": "play", "query": query})
        self.assertEqual(run.call_args.args[0], ["osascript", "-", "play", query, "50"])
        self.assertNotIn(query, run.call_args.kwargs["input"])
        self.assertIn("Player state: playing", result)

    @patch("ai.tools.music.subprocess.run")
    def test_invalid_inputs_do_not_invoke_music(self, run):
        self.assertIn("required", apple_music.invoke({"action": "play_playlist"}))
        self.assertIn("between", apple_music.invoke({"action": "set_volume", "volume": 101}))
        run.assert_not_called()

    @patch("ai.tools.music.subprocess.run")
    def test_failure_is_reported_without_retry(self, run):
        run.side_effect = subprocess.CalledProcessError(1, "osascript", stderr="Permission denied")
        result = apple_music.invoke({"action": "pause"})
        self.assertIn("Permission denied", result)
        run.assert_called_once()
