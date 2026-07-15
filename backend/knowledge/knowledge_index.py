"""In-memory semantic index for knowledge-object retrieval."""

from __future__ import annotations

from collections import defaultdict

from backend.knowledge.knowledge_models import KnowledgeObject


class KnowledgeIndex:
    """Simple token index over knowledge object semantic fields."""

    def __init__(self) -> None:
        self._token_to_ids: dict[str, set[str]] = defaultdict(set)

    def _tokens(self, knowledge_object: KnowledgeObject) -> set[str]:
        text = " ".join(
            [
                knowledge_object.filename,
                knowledge_object.semantic_summary,
                knowledge_object.description,
                " ".join(knowledge_object.objects),
                " ".join(knowledge_object.tags),
                knowledge_object.ocr_text,
            ]
        )
        return {
            token.strip().lower()
            for token in text.replace("\n", " ").split(" ")
            if token.strip()
        }

    def index(self, knowledge_object: KnowledgeObject) -> None:
        for token in self._tokens(knowledge_object):
            self._token_to_ids[token].add(knowledge_object.id)

    def remove(self, knowledge_id: str) -> None:
        for ids in self._token_to_ids.values():
            ids.discard(knowledge_id)

    def search_ids(self, query: str) -> list[str]:
        tokens = [part.strip().lower() for part in query.split(" ") if part.strip()]
        if not tokens:
            return []

        score: dict[str, int] = defaultdict(int)
        for token in tokens:
            for knowledge_id in self._token_to_ids.get(token, set()):
                score[knowledge_id] += 1
        return [item[0] for item in sorted(score.items(), key=lambda item: -item[1])]
