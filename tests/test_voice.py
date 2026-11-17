"""Manual integration check for microphone -> Parakeet MLX -> LangGraph.

Run with: uv run python tests/test_voice.py
Use a harmless general question so the router selects the conversation agent.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai.router.graph import voice_graph
from ai.voice.voice_input import VoiceInput


async def main() -> None:
    loop = asyncio.get_running_loop()
    transcript_future: asyncio.Future[str] = loop.create_future()

    def receive_transcript(transcript: str) -> None:
        if not transcript_future.done():
            loop.call_soon_threadsafe(transcript_future.set_result, transcript)

    def receive_error(message: str) -> None:
        if not transcript_future.done():
            loop.call_soon_threadsafe(
                transcript_future.set_exception,
                RuntimeError(message),
            )

    voice_input = VoiceInput(
        on_transcript=receive_transcript,
        on_transcribing=lambda: print("Transcribing with Parakeet MLX…"),
        on_error=receive_error,
    )

    print("Listening. Say a harmless general question, then pause.")
    voice_input.start()
    try:
        transcript = await transcript_future
        print(f"Transcript: {transcript}")

        result = await voice_graph.ainvoke(
            {
                "user_input": transcript,
                "agent": "",
                "task": "",
                "reason": "",
                "response": "",
            }
        )
        print(f"Selected agent: {result['agent']}")
        print(f"MAX: {result['response']}")
    finally:
        voice_input.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Voice test cancelled.")
