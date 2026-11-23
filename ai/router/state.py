from typing_extensions import NotRequired, TypedDict


class DesktopInput(TypedDict):
    app_name: str
    text: str
    submit: bool


class VoiceState(TypedDict):
    """State shared by the voice assistant graph nodes."""

    user_input: str
    agent: str
    task: str
    reason: str
    response: str
    desktop_input: NotRequired[DesktopInput | None]
