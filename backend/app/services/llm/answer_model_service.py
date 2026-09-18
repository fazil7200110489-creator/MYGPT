"""Answer Model Service Coordinator for Local Two-Layer Language Processing.

Coordinates the two Qwen layers:
  Layer 1: understand_input()  — raw user message → StructuredRequest
  Layer 2: generate_answer()   — verified MYGPT result → natural language

Both layers use the SAME persistent llama.cpp model instance.
"""

from typing import Dict, Any, List, Optional
from loguru import logger

from backend.app.schemas.company_ai import CompanyAIResult, StructuredRequest
from backend.app.services.llm.base_answer_model import BaseAnswerModel
from backend.app.services.llm.qwen_answer_model import QwenAnswerModel


class AnswerModelService:
    """Central service coordinator for the local two-layer answer model."""

    def __init__(self):
        self._provider: BaseAnswerModel = QwenAnswerModel()

    def set_provider(self, provider: BaseAnswerModel) -> None:
        self._provider = provider
        logger.info(f"Swapped local answer model provider to {type(provider).__name__}")

    # ------------------------------------------------------------------
    # Layer 1 — Input Understanding
    # ------------------------------------------------------------------

    def understand_input(
        self,
        raw_message: str,
        history: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[StructuredRequest]:
        """Layer 1: Parse informal/complex user message → StructuredRequest.
        Returns None if model unavailable or message is trivially handled.
        """
        if hasattr(self._provider, "understand_input"):
            return self._provider.understand_input(raw_message, history, context=context)
        return None

    # ------------------------------------------------------------------
    # Layer 2 — Output Generation
    # ------------------------------------------------------------------

    def generate_answer(
        self,
        verified_result: CompanyAIResult,
        original_message: Optional[str] = None,
        conversation_context: Optional[List[Dict[str, Any]]] = None,
        response_format: str = "natural"
    ) -> str:
        """Layer 2: Generate natural language answer strictly from verified result."""
        return self._provider.generate_answer(
            verified_result=verified_result,
            original_message=original_message,
            conversation_context=conversation_context,
            response_format=response_format
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def pre_load(self) -> bool:
        """Pre-loads the underlying local model into persistent memory at startup."""
        if hasattr(self._provider, "load_model"):
            return self._provider.load_model()
        return False

    def is_available(self) -> bool:
        return self._provider.is_available()

    def get_status(self) -> Dict[str, Any]:
        return self._provider.get_model_info()


# Global singleton instance
answer_model_service = AnswerModelService()
