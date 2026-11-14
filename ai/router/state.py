from typing import TypedDict


class VoiceState(TypedDict):
    """State shared by the voice assistant graph nodes."""

    user_input: str
    agent: str
    task: str
    reason: str
    response: str
