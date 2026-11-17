"""General conversation agent for requests that do not need a specialist."""

from langchain.agents import create_agent

from ai.llm.llm import get_llm


def convo_agent():
    """Build the general purpose, tool-free conversation agent."""
    return create_agent(
        model=get_llm(),
        system_prompt=(
            "You are Max, a helpful general conversation assistant. "
            "Answer questions, explain ideas, brainstorm, and chat naturally. "
            "Use the conversation context included in the request when relevant. "
            "You have no tools: do not claim to have performed actions or accessed "
            "information you cannot verify. If a request needs a specialist capability, "
            "briefly explain what you can help with or ask a useful follow-up. "
            "Keep spoken responses concise and conversational."
        ),
    )
