"""Native Music controls supplementing the Apple MCP server's app tools."""

import subprocess
from typing import Literal

from langchain.tools import tool


_MUSIC_SCRIPT = '''
on run argv
    set actionName to item 1 of argv
    set queryText to item 2 of argv
    tell application "Music"
        if actionName is "play" then
            if queryText is "" then
                play
            else
                set matches to search library playlist 1 for queryText
                if (count of matches) is 0 then return "No matching tracks in your Music library. Nothing was played."
                play item 1 of matches
            end if
        else if actionName is "play_playlist" then
            set matches to every user playlist whose name is queryText
            if (count of matches) is 0 then return "No playlist with that exact name. Nothing was played."
            play item 1 of matches
        else if actionName is "pause" then
            pause
        else if actionName is "stop" then
            stop
        else if actionName is "next" then
            next track
        else if actionName is "previous" then
            previous track
        else if actionName is "set_volume" then
            set sound volume to (item 3 of argv) as integer
            return "Music volume: " & (sound volume as text)
        else if actionName is "list_playlists" then
            set playlistNames to name of every user playlist
            set AppleScript's text item delimiters to linefeed
            return playlistNames as text
        else if actionName is "search" then
            set matches to search library playlist 1 for queryText
            set output to ""
            repeat with i from 1 to (count of matches)
                if i > 20 then exit repeat
                set t to item i of matches
                set output to output & name of t & " — " & artist of t & linefeed
            end repeat
            if output is "" then return "No matching tracks in your Music library."
            return output
        end if
        set statusText to "Player state: " & (player state as text)
        if player state is not stopped then
            try
                set statusText to statusText & "; " & name of current track & " — " & artist of current track
            end try
        end if
        return statusText
    end tell
end run
'''


@tool
def apple_music(
    action: Literal["play", "pause", "stop", "next", "previous", "now_playing",
                    "search", "list_playlists", "play_playlist", "set_volume"],
    query: str = "",
    volume: int = 50,
) -> str:
    """Control Apple Music on this Mac and return its playback state.

    play: resume, or search the user's library by query and play its first match.
    search: find up to 20 library tracks. play_playlist: exact playlist name in query.
    Other actions: pause, stop, next, previous, now_playing, list_playlists,
    set_volume (0–100, Music only). Search does not search the subscription catalog.
    Requires macOS Automation permission for Music. Do not invent matches or retries.
    """
    if action in {"search", "play_playlist"} and not query.strip():
        return f"A query is required for {action}."
    if not 0 <= volume <= 100:
        return "Music volume must be between 0 and 100."
    try:
        result = subprocess.run(
            ["osascript", "-", action, query, str(volume)], input=_MUSIC_SCRIPT,
            check=True, capture_output=True, text=True, timeout=30,
        )
        return result.stdout.strip() or "Music returned no status; the result could not be verified."
    except subprocess.CalledProcessError as exc:
        return f"Music action failed: {exc.stderr.strip()}. Check macOS Automation permission for Music."
    except subprocess.TimeoutExpired:
        return "Music did not respond in time. Check the app before retrying; the action may have completed."
    except OSError as exc:
        return f"Could not control Music: {exc}"
