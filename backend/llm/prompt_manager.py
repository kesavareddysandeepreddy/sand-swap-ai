"""
SandSwap AI - Prompt Manager
"""

from __future__ import annotations


class PromptManager:
    """Central prompt registry."""

    MEMORY_EXTRACTION_SYSTEM = """
You are a memory extraction engine.

Extract ALL durable long-term facts from user messages.

Return ONLY valid JSON.

Schema:
[
  {
    "memory_type": "...",
    "category": "...",
    "key": "...",
    "value": "...",
    "importance": 0.0,
    "confidence": 1.0
  }
]

Allowed categories:
identity, preference, project, goal, work, location, relationship, skill, fact, other

Rules:
- Emit one object per durable fact.
- Split compound messages into multiple facts when appropriate.
- Prefer concise, specific keys like name, role, favorite_ide, favorite_language, project_name, learning_goal.
- Map profile facts to identity.
- Map "favorite", "prefer", "work on", "building", "want to learn", "live in", and similar durable statements to the appropriate category.
- Ignore temporary, transient, or purely conversational details.

Examples:
- "My name is Sandeep." -> {"category": "identity", "key": "name", "value": "Sandeep"}
- "My favorite IDE is Cursor." -> {"category": "preference", "key": "favorite_ide", "value": "Cursor"}
- "My favorite language is Python." -> {"category": "preference", "key": "favorite_language", "value": "Python"}
- "I work on SandSwap AI." -> {"category": "project", "key": "project_name", "value": "SandSwap AI"}
- "I want to learn Kubernetes." -> {"category": "goal", "key": "learning_goal", "value": "Kubernetes"}
""".strip()

    @staticmethod
    def memory_extraction(user_message: str) -> str:
        return f"""
Extract durable long-term facts from the following user message.

Return every fact that should survive future conversations, not just the most obvious one.

User message:
{user_message}

Rules:
- Return JSON only.
- Include category, key, value, importance, and confidence for each fact.
- Prefer multiple objects when the message contains multiple durable facts.
- Keep keys short but specific.
- If the message contains no durable facts, return an empty array.
""".strip()

    @staticmethod
    def chat(user_message: str) -> str:
        return user_message
