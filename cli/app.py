"""Textual application for Max's interactive assistant terminal."""

from __future__ import annotations

import os
import asyncio
import logging
import time
from pathlib import Path
from rich.markdown import Markdown
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.events import Resize
from textual.widgets import Input, Static

from ai.router.graph import voice_graph
from cli.animation.states import MascotState
from cli.widgets.chat_view import ChatView
from cli.widgets.mascot import Mascot
from ai.voice.voice_input import VoiceInput


try:
    SLEEP_AFTER_SECONDS = max(10, int(os.getenv("MAX_IDLE_SLEEP_SECONDS", "90")))
except ValueError:
    SLEEP_AFTER_SECONDS = 90
SPECIALISTS = {"apple", "browser", "system", "file", "convo"}


def _with_history(message: str, history: list[dict[str, str]]) -> str:
    if not history:
        return message
    previous = "\n\n".join(
        f"User: {turn['user']}\nMax: {turn['response']}" for turn in history
    )
    return (
        "Use conversation history only when it helps with the current request. The final "
        "section is the current request. Preserve relevant details in the task sent to "
        "the selected specialist.\n\n"
        f"Conversation history:\n{previous}\n\nCurrent user request:\n{message}"
    )


class MaxApp(App[None]):
    TITLE = "MAX"
    SUB_TITLE = "Personal AI assistant"
    CSS_PATH = Path(__file__).parent / "styles" / "app.tcss"
    BINDINGS = [("ctrl+c", "quit", "Quit")]

    def __init__(self) -> None:
        super().__init__()
        self.history: list[dict[str, str]] = []
        self.last_activity = time.monotonic()
        self.request_running = False
        self._request_tasks: set[asyncio.Task] = set()
        self._terminal_timer = None
        self._voice_input: VoiceInput | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="topbar"):
            yield Static("MAX  /  PERSONAL AI ASSISTANT", id="brand")
            yield Static("● READY", id="connection-status")
        with Horizontal(id="main"):
            yield Mascot(id="mascot")
            yield ChatView(id="conversation")
        with Horizontal(id="input-row"):
            yield Static("›", id="input-prompt")
            yield Input(placeholder="Ask Max anything…", id="request-input")
        yield Static("/help   /voice   /clear   /history   /reset   /exit", id="command-help")

    def on_mount(self) -> None:
        chat = self.query_one(ChatView)
        chat.add_status("MAX is here. What can I help with?", "cyan")
        self.query_one(Input).focus()
        self.set_interval(2.0, self._check_idle)
        self._adapt_layout(self.size.width, self.size.height)

    def on_unmount(self) -> None:
        if self._voice_input is not None:
            self._voice_input.stop()

    def _on_voice_transcript(self, transcript: str) -> None:
        self._voice_input = None
        if self.request_running:
            return
        self.query_one(ChatView).add_status(f"Heard: {transcript}", "dim")
        self._submit_message(transcript)

    def _on_voice_error(self, message: str) -> None:
        self._voice_input = None
        chat = self.query_one(ChatView)
        self._mascot().set_state(MascotState.IDLE)
        self._set_status("READY")
        chat.add_status(f"Voice input: {message}", "yellow")

    def _on_voice_transcribing(self) -> None:
        self._mascot().set_state(MascotState.THINKING)
        self._set_status("TRANSCRIBING")
        self.query_one(ChatView).add_status("Transcribing with Parakeet MLX…", "cyan")

    def on_resize(self, event: Resize) -> None:
        self._adapt_layout(event.size.width, event.size.height)

    def _adapt_layout(self, width: int, height: int) -> None:
        main = self.query_one("#main", Horizontal)
        mascot = self.query_one("#mascot", Mascot)
        sprite = self.query_one("#sprite", Static)
        hint = self.query_one("#mascot-hint", Static)
        conversation = self.query_one("#conversation", ChatView)
        if width < 58 and height >= 30:
            main.styles.layout = "vertical"
            mascot.styles.width = "1fr"
            mascot.styles.min_width = 1
            mascot.styles.height = 16
            mascot.styles.padding = (0, 0)
            sprite.styles.height = 11
            hint.styles.display = "block"
            conversation.styles.margin = (1, 0, 0, 0)
        elif width < 76:
            main.styles.layout = "horizontal"
            mascot.styles.width = 24
            mascot.styles.min_width = 20
            mascot.styles.height = "1fr"
            mascot.styles.padding = (0, 0)
            sprite.styles.height = "1fr"
            hint.styles.display = "none"
            conversation.styles.margin = (0, 0, 0, 1)
        else:
            main.styles.layout = "horizontal"
            mascot.styles.width = 30
            mascot.styles.min_width = 24
            mascot.styles.height = "1fr"
            mascot.styles.padding = (0, 1)
            sprite.styles.height = "1fr"
            hint.styles.display = "block"
            conversation.styles.margin = (0, 0, 0, 1)

    def _mascot(self) -> Mascot:
        return self.query_one(Mascot)

    def _set_status(self, label: str) -> None:
        self.query_one("#connection-status", Static).update(f"● {label}")

    def _touch(self) -> None:
        self.last_activity = time.monotonic()
        if self._mascot().state == MascotState.SLEEPING:
            self._mascot().set_state(MascotState.IDLE)
            self._set_status("READY")

    def _check_idle(self) -> None:
        if (
            not self.request_running
            and self._mascot().state == MascotState.IDLE
            and time.monotonic() - self.last_activity >= SLEEP_AFTER_SECONDS
        ):
            self._mascot().set_state(MascotState.SLEEPING)
            self._set_status("SLEEPING")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "request-input" or self.request_running or self._voice_input is not None:
            return
        self._touch()
        if event.value.strip():
            self._mascot().gaze = (len(event.value) // 4) % 3 - 1
            self._mascot().set_state(MascotState.WATCHING)
            self._set_status("WATCHING")
        else:
            self._mascot().set_state(MascotState.IDLE)
            self._set_status("READY")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        message = event.value.strip()
        event.input.value = ""
        self._touch()
        if not message:
            return
        if message.startswith("/"):
            self._handle_command(message.casefold())
            return
        self._submit_message(message)

    def _submit_message(self, message: str) -> None:
        if not message or self.request_running:
            return
        self._touch()
        self.query_one(ChatView).add_user(message)
        self._mascot().set_state(MascotState.THINKING)
        self._set_status("THINKING")
        task = asyncio.create_task(self.run_request(message))
        self._request_tasks.add(task)
        task.add_done_callback(self._request_tasks.discard)
        self.request_running = True

    def _handle_command(self, command: str) -> None:
        chat = self.query_one(ChatView)
        if command == "/exit":
            self.exit()
        elif command == "/help":
            chat.add_status("Commands: /help · /voice · /clear · /history · /reset · /exit", "cyan")
        elif command == "/voice":
            if self.request_running:
                chat.add_status("Wait for the current request to finish before using /voice.", "yellow")
                return
            if self._voice_input is not None and self._voice_input.is_running:
                chat.add_status("Voice capture is already active.", "yellow")
                return
            self._touch()
            self._mascot().set_state(MascotState.LISTENING)
            self._set_status("LISTENING")
            chat.add_status("Listening now. Speak your request; pause when you’re done.", "cyan")
            self._voice_input = VoiceInput(
                on_transcript=lambda transcript: self.call_from_thread(
                    self._on_voice_transcript, transcript
                ),
                on_transcribing=lambda: self.call_from_thread(self._on_voice_transcribing),
                on_error=lambda message: self.call_from_thread(self._on_voice_error, message),
                # MLX streams are thread-local. Run Parakeet on Textual's app
                # thread, where the MLX runtime was initialized.
                transcribe=lambda path: self.call_from_thread(
                    VoiceInput._transcribe, path
                ),
            )
            self._voice_input.start()
        elif command == "/history":
            if not self.history:
                chat.add_status("No completed requests in this session yet.")
            else:
                chat.add_status("Session history", "bold cyan")
                for turn in self.history:
                    chat.add_status(f"You: {turn['user']}")
                    chat.write(Markdown(turn["response"] or "No response."))
        elif command == "/reset":
            self.history.clear()
            chat.clear()
            chat.add_status("Conversation history cleared.", "cyan")
        elif command == "/clear":
            chat.clear()
            chat.add_status("Conversation view cleared. Session history is still available with /history.")
        else:
            chat.add_status(f"Unknown command: {command}. Use /help.", "bold red")

    async def run_request(self, message: str) -> None:
        chat = self.query_one(ChatView)
        input_box = self.query_one(Input)
        self.request_running = True
        if self._terminal_timer is not None:
            self._terminal_timer.stop()
            self._terminal_timer = None
        self._touch()
        initial_state = {
            "user_input": _with_history(message, self.history),
            "agent": "",
            "task": "",
            "reason": "",
            "response": "",
        }
        response = ""
        selected_agent = ""
        try:
            async for updates in voice_graph.astream(initial_state, stream_mode="updates"):
                router_update = updates.get("router")
                if router_update:
                    selected_agent = str(router_update.get("agent") or "")
                    if selected_agent in SPECIALISTS:
                        self._mascot().set_state(MascotState.EXECUTING, selected_agent)
                        self._set_status(f"EXECUTING · {selected_agent.upper()}")
                        chat.add_status(f"Router selected {selected_agent}. Specialist executing…", "cyan")

                for node_name, node_update in updates.items():
                    if node_name in SPECIALISTS and isinstance(node_update, dict):
                        response = str(node_update.get("response") or "")

            if not selected_agent:
                raise RuntimeError("The router did not select a specialist agent.")
            chat.add_assistant(response)
            self.history.append(
                {"user": message, "response": response, "agent": selected_agent}
            )
            self._mascot().set_state(MascotState.SUCCESS)
            self._set_status("SUCCESS")
            self._return_to_idle_after_animation(MascotState.SUCCESS)
        except Exception as exc:
            chat.add_status(f"Request failed: {exc}", "bold red")
            self._mascot().set_state(MascotState.ERROR)
            self._set_status("ERROR")
            self._return_to_idle_after_animation(MascotState.ERROR)
        finally:
            current_task = asyncio.current_task()
            self.request_running = any(
                task is not current_task and not task.done()
                for task in self._request_tasks
            )
            input_box.focus()
            self.last_activity = time.monotonic()

    def _return_to_idle_after_animation(self, expected_state: MascotState) -> None:
        def return_to_idle() -> None:
            if self._mascot().state == expected_state:
                self._mascot().set_state(MascotState.IDLE)
                self._set_status("READY")
            self._terminal_timer = None

        if self._terminal_timer is not None:
            self._terminal_timer.stop()
        self._terminal_timer = self.set_timer(1.5, return_to_idle)


async def main() -> None:
    """Open shared services and run the interface on one asyncio loop."""
    from ai.agents.browser_agent import close_browser_agent, get_agent, log_browser_debug

    logging.basicConfig(level=logging.INFO)
    app = None
    try:
        await get_agent()
        app = MaxApp()
        log_browser_debug("Textual app starting")
        await app.run_async()
        log_browser_debug("Textual app returned; entering shutdown")
    finally:
        if app is not None and app._request_tasks:
            await asyncio.gather(*tuple(app._request_tasks), return_exceptions=True)
        await close_browser_agent()


def run() -> None:
    """Launch the Textual interface with one event loop for its lifetime."""
    asyncio.run(main())
