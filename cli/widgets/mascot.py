from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Static

from cli.animation.sprites import render_sprite
from cli.animation.states import MascotState


class Mascot(Vertical):
    """A small timer-driven pixel mascot; only this widget refreshes per frame."""

    state: reactive[MascotState] = reactive(MascotState.IDLE)
    agent: reactive[str] = reactive("")
    gaze: int = 0
    frame: reactive[int] = reactive(0)
    hint: reactive[str] = reactive("Your curious cat companion.")

    def compose(self) -> ComposeResult:
        yield Static(id="sprite", classes="sprite")
        yield Static(id="mascot-state", classes="mascot-state")
        yield Static(id="mascot-hint", classes="mascot-hint")

    def on_mount(self) -> None:
        self.set_interval(0.18, self._animate)
        self._refresh_sprite()

    def set_state(self, state: MascotState, agent: str = "") -> None:
        if self.state == state and self.agent == agent:
            return
        self.state = state
        self.agent = agent
        self.frame = 0
        self._refresh_sprite()

    def _animate(self) -> None:
        self.frame += 1
        self._refresh_sprite()

    def _refresh_sprite(self) -> None:
        sprite = self.query_one("#sprite", Static)
        sprite.update(render_sprite(self.state, self.frame, self.gaze))
        self.query_one("#mascot-state", Static).update(self._state_label())
        self.query_one("#mascot-hint", Static).update(self._hint_label())

    def _state_label(self) -> str:
        if self.state == MascotState.EXECUTING and self.agent:
            return f"● {self.state.value} · {self.agent.upper()}"
        return f"● {self.state.value}"

    def _hint_label(self) -> str:
        hints = {
            MascotState.IDLE: "Your curious cat companion.",
            MascotState.WATCHING: "Watching you type…",
            MascotState.LISTENING: "I’m listening.",
            MascotState.THINKING: "Putting the pieces together…",
            MascotState.EXECUTING: f"Working with {self.agent or 'your specialist'}…",
            MascotState.SUCCESS: "All done. Nice and tidy.",
            MascotState.ERROR: "That didn’t go to plan.",
            MascotState.SLEEPING: "Resting until you need me.",
        }
        return hints[self.state]
