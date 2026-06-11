"""LLM setup for the QA Bug Triage Crew."""

import os

from crewai import LLM
from dotenv import load_dotenv

load_dotenv()


# Workaround: CrewAI 1.14.6 attaches a `cache_breakpoint` field to chat
# messages that Groq's OpenAI-compatible endpoint rejects. Strip it before
# every call.
class GroqLLM(LLM):
    def call(self, messages, *args, **kwargs):
        if isinstance(messages, list):
            cleaned = []
            for m in messages:
                if isinstance(m, dict):
                    m = {k: v for k, v in m.items() if k != "cache_breakpoint"}
                cleaned.append(m)
            messages = cleaned
        return super().call(messages, *args, **kwargs)


# Step 0 - Setup the Brain (GPT-OSS 120B via Groq)
# max_tokens caps each agent's response so the cumulative context passed to
# later tasks stays within Groq's tokens-per-minute limit (8000 TPM).
groq_llm = GroqLLM(
    model="openai/openai/gpt-oss-120b",
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_KEY"),
    max_tokens=1024,
)
