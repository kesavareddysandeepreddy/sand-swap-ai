"""
SandSwap AI - Prompt Manager
"""

from __future__ import annotations


class PromptManager:
    """Central prompt registry."""

    MEMORY_EXTRACTION_SYSTEM = """
You are a memory extraction engine.

Extract ONLY durable long-term memories.

Return ONLY valid JSON.

Schema:
[
  {
    "memory_type": "...",
    "key": "...",
    "value": "...",
    "importance": 0.0,
    "confidence": 1.0
  }
]
""".strip()

    @staticmethod
    def memory_extraction(user_message: str) -> str:
        return f"""
Extract durable long-term memories from the following user message.

User message:
{user_message}

Rules:
- Ignore temporary facts.
- Keep keys short.
- Return JSON only.
""".strip()

    @staticmethod
    def chat(user_message: str) -> str:
        return user_message
