"""Bounded local computer controls for the system specialist."""

import json
import os
from pathlib import Path
import subprocess
from typing import Literal

from langchain.tools import tool

from ai.tools.system import APP_ALIASES

ROOTS = [Path.home() / name for name in ("Desktop", "Documents", "Downloads")]
COMMAND_APPROVALS = Path.home() / ".config" / "max" / "approved_commands.json"
_SKIP = {"node_modules", ".git", ".venv", "venv", "build", "dist", "Library", "__pycache__"}


def _local_path(path: str) -> Path:
    resolved = Path(path).expanduser().resolve()
    if not any(resolved.is_relative_to(root.resolve()) for root in ROOTS):
        raise ValueError("Path must be inside Desktop, Documents, or Downloads.")
    return resolved


def _run(argv: list[str], *, cwd=None, script=None, timeout=20) -> str:
    try:
        result = subprocess.run(
            argv, cwd=cwd, input=script, capture_output=True, text=True,
            check=True, timeout=timeout,
        )
        return result.stdout.strip()[:8000] or "Command completed successfully."
    except subprocess.CalledProcessError as exc:
        return f"Action failed: {(exc.stderr or str(exc)).strip()[:2000]}"
    except subprocess.TimeoutExpired:
        return "Action timed out. Check its state before retrying."
    except OSError as exc:
        return f"Action failed: {exc}"


@tool
def find_local_items(name: str, kind: Literal["any", "file", "directory"] = "any") -> str:
    """Find up to 20 files or project folders by name under Desktop/Documents/Downloads.

    Searches at most six folder levels and 10,000 folders; excludes hidden paths,
    symlink directories, dependencies and build output. Returns paths, not file contents.
    """
    if not name.strip():
        return "Provide a file or project name to find."
    matches = []
    visited = 0
    for root in ROOTS:
        if not root.is_dir():
            continue
        for base, dirs, files in os.walk(root, followlinks=False):
            visited += 1
            if visited > 10000:
                return "\n".join(matches) + "\nSearch limit reached; narrow the folder/name."
            base = Path(base)
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in _SKIP
                             and not (base / d).is_symlink())
            candidates = (dirs if kind == "directory" else files if kind == "file" else dirs + files)
            for item in sorted(candidates):
                if not item.startswith(".") and name.casefold() in item.casefold():
                    candidate = base / item
                    if candidate.is_symlink():
                        continue
                    matches.append(str(candidate))
                    if len(matches) == 20:
                        return "\n".join(matches) + "\nShowing first 20 matches."
            if len(base.relative_to(root).parts) >= 5:
                dirs.clear()
    return "\n".join(matches) or "No matching items found in Desktop, Documents, or Downloads."


@tool
def organize_local_file(source: str, destination: str) -> str:
    """Move/rename one regular file within Desktop/Documents/Downloads, without overwriting.

    Destination is the full new filename, not just a folder. Creates its parent folders.
    No directory moves, symlink moves, hidden-file moves, deletion or overwriting.
    """
    try:
        src, dst = _local_path(source), _local_path(destination)
        if Path(source).expanduser().is_symlink() or not src.is_file():
            return "Source must be a regular file, not a directory or symlink."
        if any(part.startswith(".") for path in (src, dst) for part in path.parts):
            return "Hidden files and folders cannot be organized with this tool."
        if dst.exists() or dst.is_symlink():
            return "Destination already exists; nothing was moved."
        dst.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation prevents overwriting if another process creates dst
        # between the existence check and the move. Works across local volumes.
        import shutil
        with src.open("rb") as incoming, dst.open("xb") as outgoing:
            shutil.copyfileobj(incoming, outgoing)
        shutil.copystat(src, dst)
        src.unlink()
        return f"Moved {src} to {dst}."
    except (OSError, ValueError) as exc:
        return f"Could not move file: {exc}. Check both paths before retrying."


@tool
def open_project(path: str, app_name: str = "vscode") -> str:
    """Open an existing project directory in VS Code or another named app.

    Use find_local_items to resolve names like SPEC2RTL first. Do not guess between
    multiple matches. Opening the folder does not start builds, servers or scripts.
    """
    try:
        project = _local_path(path)
        if not project.is_dir():
            return "Project path must be an existing directory."
        app = APP_ALIASES.get(app_name.strip().lower(), app_name.strip())
        if not app:
            return "An application name is required."
        result = _run(["open", "-a", app, str(project)])
        return f"Opened {project} in {app}." if result == "Command completed successfully." else result
    except ValueError as exc:
        return str(exc)


@tool
def run_approved_command(argv: list[str], working_directory: str) -> str:
    """Run an exact approved command as argv (no shell) in a local project folder.

    Built-in approvals: pwd, git status --short, git diff --stat. Other commands must
    match an exact argv AND cwd entry in ~/.config/max/approved_commands.json.
    Never invent approval or retry a rejected command via a different tool.
    """
    try:
        cwd = _local_path(working_directory)
        if not cwd.is_dir():
            return "Working directory must exist."
        if not argv or any(not isinstance(arg, str) or "\0" in arg for arg in argv):
            return "Provide a nonempty argv list with valid strings."
        approved = argv in (["pwd"], ["git", "status", "--short"], ["git", "diff", "--stat"])
        if not approved and COMMAND_APPROVALS.exists():
            entries = json.loads(COMMAND_APPROVALS.read_text())
            if not isinstance(entries, list):
                raise ValueError("Approved commands config must be a JSON list.")
            approved = any(
                isinstance(entry, dict) and entry.get("argv") == argv
                and Path(entry.get("cwd", "")).expanduser().resolve() == cwd
                for entry in entries
            )
        if not approved:
            return (
                "Command not approved. Add its exact argv and project cwd to "
                "~/.config/max/approved_commands.json, then retry. No command was executed."
            )
        return _run(argv, cwd=str(cwd), timeout=60)
    except (OSError, ValueError, TypeError) as exc:
        return f"Could not run command: {exc}"


_WINDOW_SCRIPT = '''
on run argv
    set appName to item 1 of argv
    set actionName to item 2 of argv
    tell application appName
        activate
        set appID to id
    end tell
    tell application "System Events"
        set p to first application process whose bundle identifier is appID
        repeat 40 times
            if frontmost of p then exit repeat
            delay 0.1
        end repeat
        if not (frontmost of p) then error "Could not focus the app."
        tell p
            if actionName is "list" then return name of every window
            if (count of windows) is 0 then error "This app has no windows."
            set w to front window
            if actionName is "focus" then return "App window focused."
            if actionName is "minimize" then
                set value of attribute "AXMinimized" of w to true
                return "Window minimized."
            end if
            set value of attribute "AXMinimized" of w to false
            if actionName is "resize" then
                set position of w to {(item 3 of argv) as integer, (item 4 of argv) as integer}
                set size of w to {(item 5 of argv) as integer, (item 6 of argv) as integer}
            else
                tell application "Finder" to set desktopBounds to bounds of window of desktop
                set screenWidth to item 3 of desktopBounds
                set screenHeight to item 4 of desktopBounds
                set xPosition to 0
                if actionName is "left" or actionName is "right" then
                    set screenWidth to screenWidth div 2
                    if actionName is "right" then set xPosition to screenWidth
                end if
                set position of w to {xPosition, 25}
                set size of w to {screenWidth, screenHeight - 25}
            end if
            return "Window position: " & (position of w as text) & "; size: " & (size of w as text)
        end tell
    end tell
end run
'''


@tool
def manage_app_window(
    app_name: str,
    action: Literal["list", "focus", "minimize", "maximize", "left", "right", "resize"],
    x: int = 0, y: int = 25, width: int = 1200, height: int = 800,
) -> str:
    """List/focus/minimize/resize an app's front window; tile left/right or maximize.

    Tiling uses the primary display. resize uses x/y/width/height in screen points.
    Requires macOS Accessibility and Automation permissions. Does not close windows.
    """
    if not app_name.strip() or width < 100 or height < 100:
        return "Provide an app name and window dimensions of at least 100 points."
    app = APP_ALIASES.get(app_name.strip().lower(), app_name.strip())
    return _run(["osascript", "-", app, action, str(x), str(y), str(width), str(height)],
                script=_WINDOW_SCRIPT)


@tool
def open_system_settings(section: Literal[
    "general", "sound", "display", "keyboard", "mouse", "trackpad", "wifi",
    "bluetooth", "accessibility", "privacy",
]) -> str:
    """Open a specific macOS System Settings pane for the user to adjust.

    This opens the pane; it does not change permissions, Wi-Fi or Bluetooth itself.
    Use system_volume/system_brightness to change volume/brightness directly.
    """
    panes = {
        "general": "com.apple.systempreferences.GeneralSettings",
        "sound": "com.apple.Sound-Settings.extension",
        "display": "com.apple.Displays-Settings.extension",
        "keyboard": "com.apple.Keyboard-Settings.extension",
        "mouse": "com.apple.Mouse-Settings.extension",
        "trackpad": "com.apple.Trackpad-Settings.extension",
        "wifi": "com.apple.wifi-settings-extension",
        "bluetooth": "com.apple.BluetoothSettings",
        "accessibility": "com.apple.Accessibility-Settings.extension",
        "privacy": "com.apple.settings.PrivacySecurity.extension",
    }
    return _run(["open", f"x-apple.systempreferences:{panes[section]}"])
