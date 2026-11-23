import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

load_dotenv()


def get_llm(*, browser: bool = False):
    groq_options = {}
    gemini_options = {}
    if browser:
        # Browser tasks resend tool schemas and page context on each model turn.
        # Give them a separate Groq model budget and cap per-call latency.
        groq_options = {"reasoning_effort": "low", "max_tokens": 1024, "timeout": 15}
        gemini_options = {"timeout": 15, "max_retries": 0}
    def groq_model(model: str):
        return ChatGroq(
            model=model,
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0,
            max_retries=1 if browser and model == "openai/gpt-oss-20b" else 0,
            **groq_options,
        )

    primary = groq_model("openai/gpt-oss-120b")
    fallback = ChatGoogleGenerativeAI(
        model="gemini-3.8-flash",
        api_key=os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"),
        temperature=0,
        **gemini_options,
    )
    if browser:
        return groq_model("openai/gpt-oss-20b").with_fallbacks([primary, fallback])
    return primary.with_fallbacks([fallback])

