from langchain.agents import create_agent 
from ai.tools.system import system_volume , system_brightness
from ai.llm.llm import get_llm 



def system_agent():
    agent = create_agent(
        model = get_llm(), 
        tools = [system_volume ,system_brightness],
        system_prompt="""
        You are Max, a macOS system assistant.

        Your responsibilities:
        - Control system volume.
        - Get current volume.
        - Mute and unmute the system.
        - Control display brightness.
        - Get current display brightness.

        Rules:
        - Use system_volume for all volume operations.
        - Use system_brightness for all brightness operations.
        - Never claim an action succeeded unless the tool confirms it.
        - If the requested level is unclear, ask the user.
        - Keep responses short and conversational.
        """
    )

    return agent

