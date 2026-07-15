"""Knowledge context composition for prompt consumption."""

from __future__ import annotations

from backend.knowledge.knowledge_models import KnowledgeContext, KnowledgeObject


class KnowledgeContextBuilder:
    """Render reusable natural-language context from knowledge objects."""

    def build(self, knowledge_objects: list[KnowledgeObject]) -> KnowledgeContext:
        if not knowledge_objects:
            return KnowledgeContext(knowledge_ids=[], rendered_text="", metadata={})

        enriched = [
            item
            for item in knowledge_objects
            if item.semantic_summary.strip()
            or item.description.strip()
            or bool(item.objects)
            or item.ocr_text.strip()
        ]
        if not enriched:
            return KnowledgeContext(
                knowledge_ids=[item.id for item in knowledge_objects],
                rendered_text="",
                metadata={"count": 0, "reason": "no_semantic_content"},
            )

        blocks: list[str] = []
        for item in enriched:
            objects_text = ", ".join(item.objects) if item.objects else "none"
            visible_text = item.ocr_text.strip() or "none"
            blocks.append(
                "\n".join(
                    [
                        "Attached Image",
                        f"Filename: {item.filename}",
                        f"Summary: {item.semantic_summary or 'none'}",
                        f"Description: {item.description or 'none'}",
                        f"Objects: {objects_text}",
                        f"Visible Text: {visible_text}",
                        f"Provider: {item.provider or 'unknown'}",
                        f"Confidence: {item.confidence:.2f}",
                    ]
                )
            )

        return KnowledgeContext(
            knowledge_ids=[item.id for item in enriched],
            rendered_text="\n\n".join(blocks),
            metadata={"count": len(enriched)},
        )
