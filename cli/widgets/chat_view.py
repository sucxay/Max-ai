from rich.markdown import Markdown
from rich.text import Text
from textual.widgets import RichLog


class ChatView(RichLog):
    """Conversation log rendered with Rich and Markdown."""

    def __init__(self, **kwargs):
        super().__init__(wrap=True, markup=False, highlight=False, **kwargs)

    def add_user(self, message: str) -> None:
        self.write(Text("YOU", style="bold white"))
        self.write(Text(message))

    def add_assistant(self, message: str) -> None:
        self.write(Text("MAX", style="bold cyan"))
        self.write(Markdown(message or "No response was returned."))

    def add_status(self, message: str, style: str = "dim") -> None:
        self.write(Text(message, style=style))
