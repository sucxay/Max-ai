import subprocess
from langchain.tools import tool 


APP_ALIAS= {
    'vscode': "Visual Code Studio", 
    "chrome" : "Google Chrome",
    "camera" : "Photo Booth",
    "brave": "Brave Browser"

}

def set_volume(level: int):
    """Set system volume 0-100"""
    level = max(0, min(100, level))
    subprocess.run(
        ['osascript', '-e', f'set volume output volume {level}'],
        check=True
    )

def get_volume():
    """Get current volume"""
    result = subprocess.run(
        ["osascript", "-e", "output volume of (get volume settings)"],
        capture_output=True,
        text=True,
        check=True
    )
    return int(result.stdout.strip())

def mute():
    """Mute system volume"""
    subprocess.run(
        ["osascript", "-e", "set volume output muted true"],
        check=True
    )   

def unmute():
    """Unmute system volume"""
    subprocess.run(
        ["osascript", "-e", "set volume output muted false"],
        check=True
    )

@tool
def system_volume(action: str, level: int = 50):
    """Control MacOS volume
    actions: mute, unmute, set, view, get"""
    try:
        normalized_action = action.lower().strip()
        if normalized_action == "set":
            clamped_level = max(0, min(100, level))
            set_volume(clamped_level)
            return f"Volume set to {clamped_level}"
        elif normalized_action == "mute":
            mute()
            return "Volume muted"
        elif normalized_action == "unmute":
            unmute()
            return "Volume unmuted"
        elif normalized_action in ["view", "get"]:
            return f"Current volume is {get_volume()}"
        return f"Unknown action: {action}"
    except subprocess.CalledProcessError as e:
        return f"Failed to execute volume command: {e}"
    except Exception as e:
        return f"Error controlling volume: {e}" 


@tool 
def system_brightness(action :str , level  : int =30):
    """control MacOS brightness
    actions : set , get
    """ 

    try : 
        normalized_action = action.lower().strip()
        if normalized_action=="set":
            level = max(0 , min(100 , level))
            subprocess.run(
                ['brightness', str(level/100)] , 
                check = True , 
                capture_output=True,  
                text = True 

            )
            return f"Brightness set to {level}"
        elif normalized_action =='get':
            result = subprocess.run(
            ["brightness", "-l"],
            capture_output=True,
            text=True,
            check=True
        )
            return result.stdout 
        return f"Unknown action: {action}"
    except subprocess.CalledProcessError as e:
        return f"Failed to execute brightness command: {e}"
    except Exception as e:
        return f"Error controlling brightness: {e}" 


import subprocess
from langchain.tools import tool

APP_ALIASES = {
    "vscode": "Visual Studio Code",
    "vs code": "Visual Studio Code",
    "code": "Visual Studio Code",
    "chrome": "Google Chrome",
    "browser": "Google Chrome",
    "safari": "Safari",
    "terminal": "Terminal",
    "spotify": "Spotify",
    "discord": "Discord",
    "whatsapp": "WhatsApp",
    "telegram": "Telegram",
    "finder": "Finder",
    "settings": "System Settings",
    "calculator": "Calculator",
    "notes": "Notes",
    "camera": "Photo Booth",
    "claude": "Claude",
    "chatgpt": "ChatGPT",
    "chat gpt": "ChatGPT",
}


# Pass application names and user text as argv, never as AppleScript source.
_TYPE_IN_APP_SCRIPT = '''
on run argv
    set appName to item 1 of argv
    set promptText to item 2 of argv
    set shouldSubmit to item 3 of argv
    tell application appName
        activate
        set appID to id
    end tell
    tell application "System Events"
        set targetProcess to first application process whose bundle identifier is appID
        repeat 40 times
            if frontmost of targetProcess then exit repeat
            delay 0.1
        end repeat
        if not (frontmost of targetProcess) then error "Could not focus the requested app."
        tell targetProcess
            set focusedElement to value of attribute "AXFocusedUIElement"
            set focusedRole to role of focusedElement
            if focusedRole is not in {"AXTextArea", "AXTextField", "AXComboBox"} then
                error "Click the message input in the requested app, then try again."
            end if
        end tell
    end tell
    set savedClipboard to the clipboard as record
    try
        set the clipboard to promptText
        tell application "System Events"
            if not (frontmost of targetProcess) then error "App focus changed; text was not pasted."
            keystroke "v" using command down
            delay 0.3
            if shouldSubmit is "true" then
                if not (frontmost of targetProcess) then error "App focus changed; prompt was not submitted."
                key code 36
            end if
        end tell
    on error errorMessage
        set the clipboard to savedClipboard
        error errorMessage
    end try
    set the clipboard to savedClipboard
end run
'''


def _type_in_app(app_name: str, text: str, submit: bool) -> str:
    app = APP_ALIASES.get(app_name.strip().lower(), app_name.strip())
    if not app or not text.strip():
        return "Application name and text are required."
    try:
        subprocess.run(
            ["osascript", "-", app, text, str(submit).lower()],
            input=_TYPE_IN_APP_SCRIPT,
            check=True, capture_output=True, text=True, timeout=20,
        )
    except subprocess.TimeoutExpired:
        return "App interaction timed out. Check the app before retrying; text may already have been entered."
    except subprocess.CalledProcessError as exc:
        return (
            f"Could not complete typing in {app}: {exc.stderr.strip()}. "
            "If macOS denied access, allow your terminal or Max in System Settings > "
            "Privacy & Security > Accessibility and Automation. Do not retry submission "
            "without checking whether it already went through."
        )
    except OSError as exc:
        return f"Could not control {app}: {exc}"
    if submit:
        return f"Pasted text into {app} and pressed Return. Delivery has not been verified."
    return f"Pasted text into the focused input in {app}."


@tool
def type_in_app(app_name: str, text: str) -> str:
    """Open/focus a macOS app and paste exact text into its focused text input without sending.

    The user must have the desired input selected in the app. Preserves the clipboard.
    Requires macOS Accessibility and Automation permissions.
    """
    return _type_in_app(app_name, text, submit=False)


@tool
def send_app_prompt(app_name: str, text: str) -> str:
    """Open/focus an app, paste exact text in its focused input and press Return once.

    Use when the user explicitly asks to send/submit a prompt, e.g. to Claude or ChatGPT.
    The desired message input must be selected; Return must submit in that app.
    This reports keyboard actions, not verified delivery. Never blindly retry.
    """
    return _type_in_app(app_name, text, submit=True)


@tool
def open_app(app_name: str) -> str:
    """Open a macOS application by its common name or alias."""

    try:
        name = app_name.strip().lower()
        app = APP_ALIASES.get(name, app_name.strip())

        subprocess.run(
            ["open", "-a", app],
            check=True,
            capture_output=True,
            text=True
        )

        return f"Opened {app} successfully."

    except subprocess.CalledProcessError as e:
        return f"Could not open {app_name}: {e.stderr.strip()}"

    except Exception as e:
        return f"Error opening application: {e}"

@tool 
def close_app(app_name: str) -> str:
    """Close a macOS application by its common name or alias."""
    try:
        name = app_name.strip().lower()
        app = APP_ALIASES.get(name, app_name.strip())

        subprocess.run(
            ["killall", app],
            check=True,
            capture_output=True,
            text=True
        )

        return f"Closed {app} successfully."

    except subprocess.CalledProcessError as e:
        return f"Could not close {app_name}: {e.stderr.strip()}"

    except Exception as e:
        return f"Error closing application: {e}"
