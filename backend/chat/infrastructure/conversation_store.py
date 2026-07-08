"""Conversation persistence store."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from backend.chat.domain.conversation import Conversation


class ConversationStore:
    """Persistence layer for chat conversations."""

    def __init__(self, db_path: str = "data/chat/conversations.db") -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.initialize()

    def initialize(self) -> None:
        """Create the conversation table if it does not exist."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """)
        self.conn.commit()

    def create_conversation(
        self, user_id: str, conversation_id: str | None = None
    ) -> Conversation:
        """Create a new conversation for a user."""
        conversation = Conversation(
            user_id=user_id, id=conversation_id or Conversation().id
        )
        self.save_conversation(conversation)
        return conversation

    def save_conversation(self, conversation: Conversation) -> Conversation:
        """Persist a conversation and its messages."""
        self.conn.execute(
            """
            INSERT OR REPLACE INTO conversations (id, user_id, created_at, updated_at, payload)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                conversation.id,
                conversation.user_id,
                conversation.created_at.isoformat(),
                conversation.updated_at.isoformat(),
                json.dumps(conversation.to_dict()),
            ),
        )
        self.conn.commit()
        return conversation

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        """Load one conversation by identifier."""
        row = self.conn.execute(
            "SELECT payload FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        if row is None:
            return None
        return Conversation.from_dict(json.loads(row["payload"]))

    def append_message(
        self, conversation_id: str, role: str, content: str
    ) -> Conversation:
        """Append a message to a conversation and save it."""
        conversation = self.get_conversation(conversation_id)
        if conversation is None:
            raise KeyError(f"Conversation '{conversation_id}' does not exist.")
        conversation.add_message(role, content)
        return self.save_conversation(conversation)

    def list_conversations(self, user_id: str | None = None) -> list[Conversation]:
        """List conversations optionally filtered by user."""
        if user_id is None:
            rows = self.conn.execute("SELECT payload FROM conversations").fetchall()
        else:
            rows = self.conn.execute(
                "SELECT payload FROM conversations WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        return [Conversation.from_dict(json.loads(row["payload"])) for row in rows]

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation by identifier."""
        cursor = self.conn.execute(
            "DELETE FROM conversations WHERE id = ?",
            (conversation_id,),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def close(self) -> None:
        """Close the underlying sqlite connection."""
        self.conn.close()

    def __del__(self) -> None:
        """Ensure the sqlite connection is closed when the store is discarded."""
        try:
            self.conn.close()
        except Exception:
            pass
