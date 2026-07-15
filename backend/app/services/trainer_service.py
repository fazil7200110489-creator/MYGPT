"""Trainer service wrapper for MyGPT Studio training management.
"""

import os
import json
from loguru import logger
from backend.app.core.config import settings
from backend.app.model.trainer import TrainingManager


class CustomTrainingManager(TrainingManager):
    """Extends TrainingManager with dynamic training sample persistence slots."""

    def save_training_sample(
        self,
        doc_id: str,
        question: str,
        answer: str,
        confidence: float,
        retrieved_context: str = "",
        intent: str = "",
        knowledge_used: bool = False,
        supporting_chunks: list = None
    ) -> None:
        """Saves a QA turn context sample to a local JSONL file for future training."""
        try:
            import datetime
            from backend.app.services.knowledge_service import knowledge_store
            knowledge = knowledge_store.get_knowledge(doc_id) if doc_id else None
            doc_type = knowledge.get("document_type", "Generic") if knowledge else "Generic"

            clean_supporting = []
            if supporting_chunks:
                for c in supporting_chunks:
                    clean_supporting.append({
                        "chunk_id": c.get("chunk_id"),
                        "text": c.get("text"),
                        "page_number": c.get("page_number"),
                        "similarity": c.get("similarity", c.get("score", 0.0))
                    })

            sample = {
                "document_type": doc_type,
                "document_id": doc_id,
                "question": question,
                "answer": answer,
                "knowledge_used": knowledge_used,
                "supporting_chunks": clean_supporting,
                "confidence": confidence,
                "timestamp": datetime.datetime.now().isoformat()
            }

            os.makedirs(settings.DATA_DIR, exist_ok=True)
            jsonl_path = os.path.join(settings.DATA_DIR, "training_samples.jsonl")

            with open(jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(sample) + "\n")
                
            logger.info(f"Saved training sample for doc_id {doc_id} to {jsonl_path}")
        except Exception as e:
            logger.error(f"Failed to save training sample: {e}")


# Instantiated as a global singleton service for router access
trainer_service = CustomTrainingManager()

