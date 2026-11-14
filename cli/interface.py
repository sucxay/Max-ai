"""Rich terminal presentation and session handling for Max."""

from __future__ import annotations

import asyncio
from typing import Any

from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from ai.router.graph import voice_graph


THEME = Theme(
    {
        "accent": "bold cyan",
        "muted": "dim",
        "user": "bold white",
        "assistant": "cyan",
        "success": "bold green",
        "error": "bold red",
    }
)
console = Console(theme=THEME)
COMMANDS = "/help  /history  /reset  /clear  /exit"


def show_startup() -> None:
    """Draw the startup banner and command summary."""
    console.print()
    console.print(
        Panel(
            "[bold white]MAX[/bold white]\n[muted]Your personal AI assistant[/muted]",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(1, 3),
        ),
        justify="center",
    )
    console.print(f"[muted]Commands[/muted]  {COMMANDS}", justify="center")
    console.print("[success]●[/success] Ready", justify="center")
    console.print()


def show_help() -> None:
    console.print(
        Panel(
            "[accent]/help[/accent]      Show available commands\n"
            "[accent]/history[/accent]  Show this session's conversation\n"
            "[accent]/reset[/accent]    Clear conversation history\n"
            "[accent]/clear[/accent]    Clear the terminal and redraw Max\n"
            "[accent]/exit[/accent]     Exit Max\n\n"
            "Type any other message to talk to Max.",
            title="Commands",
            border_style="cyan",
            box=box.ROUNDED,
        )
    )


def show_history(history: list[dict[str, str]]) -> None:
    if not history:
        console.print(Panel("No conversation yet.", title="History", border_style="cyan"))
        return

    table = Table(box=box.SIMPLE, expand=True, border_style="bright_black")
    table.add_column("You", style="white", ratio=1)
    table.add_column("Max", style="cyan", ratio=2)
    for turn in history:
        table.add_row(turn["user"], turn["response"])
    console.print(Panel(table, title="Session history", border_style="cyan"))


def _graph_input(message: str, history: list[dict[str, str]]) -> str:
    if not history:
        return message

    prior_turns = "\n\n".join(
        f"User: {turn['user']}\nMax: {turn['response']}" for turn in history
    )
    return (
        "Use this conversation history only when it helps understand the current request. "
        "The final section is the user's new request. Preserve relevant details in the task "
        "you send to the selected specialist.\n\n"
        f"Conversation history:\n{prior_turns}\n\n"
        f"Current user request:\n{message}"
    )


async def execute_request(
    message: str, history: list[dict[str, str]]
) -> dict[str, Any]:
    """Invoke the existing graph with this session's transcript as context."""
    initial_state = {
        "user_input": _graph_input(message, history),
        "agent": "",
        "task": "",
        "reason": "",
        "response": "",
    }
    return await voice_graph.ainvoke(initial_state)


async def chat_loop() -> None:
    history: list[dict[str, str]] = []
    show_startup()

    while True:
        try:
            message = Prompt.ask("[accent]You[/accent]", console=console).strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[muted]Max session ended.[/muted]")
            return

        if not message:
            continue

        command = message.casefold()
        if command == "/exit":
            console.print("[muted]Goodbye.[/muted]")
            return
        if command == "/help":
            show_help()
            continue
        if command == "/history":
            show_history(history)
            continue
        if command == "/reset":
            history.clear()
            console.print("[success]Conversation history cleared.[/success]")
            continue
        if command == "/clear":
            console.clear()
            show_startup()
            continue
        if message.startswith("/"):
            console.print(f"[error]Unknown command:[/error] {message}. Use /help.")
            continue

        console.print(Panel(Text(message), title="You", border_style="bright_black"))
        try:
            with console.status("[accent]Thinking…[/accent]", spinner="dots", spinner_style="cyan"):
                result = await execute_request(message, history)
        except Exception as exc:  # Keep transient provider and agent failures in-session.
            console.print(Panel(str(exc), title="Request failed", border_style="red"))
            continue

        agent = str(result.get("agent") or "unknown")
        response = str(result.get("response") or "")
        console.print(
            f"[muted]Routed to[/muted] [accent]{agent}[/accent]",
            style="",
        )
        console.print(
            Panel(Markdown(response or "No response was returned."), title="Max", border_style="cyan")
        )
        history.append({"user": message, "response": response, "agent": agent})


def run() -> None:
    """Synchronous entry point used by ``max`` and ``python -m ai.main``."""
    try:
        asyncio.run(chat_loop())
    except KeyboardInterrupt:
        console.print("\n[muted]Max session ended.[/muted]")
