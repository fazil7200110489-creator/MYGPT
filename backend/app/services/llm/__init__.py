"""Local LLM, Specialized Models, and Model Registry Services for MYGPT.
"""

from backend.app.services.llm.base_answer_model import BaseAnswerModel
from backend.app.services.llm.qwen_answer_model import QwenAnswerModel
from backend.app.services.llm.answer_model_service import answer_model_service, AnswerModelService
from backend.app.services.llm.model_registry import (
    model_registry, ModelRegistry, ModelDescriptor,
    GENERAL_MODEL, CODING_MODEL, VISION_MODEL, EMBEDDING_MODEL
)
from backend.app.services.llm.vision_model import vision_model, VisionModel

__all__ = [
    "BaseAnswerModel",
    "QwenAnswerModel",
    "answer_model_service",
    "AnswerModelService",
    "model_registry",
    "ModelRegistry",
    "ModelDescriptor",
    "GENERAL_MODEL",
    "CODING_MODEL",
    "VISION_MODEL",
    "EMBEDDING_MODEL",
    "vision_model",
    "VisionModel",
]
