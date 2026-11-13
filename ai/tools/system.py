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
    "camera":"Photo Booth"
}


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