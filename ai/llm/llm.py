from dotenv import load_dotenv
from langchain_groq import ChatGroq 
import os 
import dotenv 
load_dotenv()


def get_llm():
    llm = ChatGroq(
        model="openai/gpt-oss-120b",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0,
    )
    return llm 

