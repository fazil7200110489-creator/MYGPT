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

    def generate_general_response(
        self,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Answers general knowledge, explanations, reasoning, and conversational queries directly using local model."""
        if hasattr(self._provider, "generate_general_response"):
            if max_tokens is not None:
                try:
                    return self._provider.generate_general_response(
                        prompt=prompt,
                        history=history,
                        system_instruction=system_instruction,
                        max_tokens=max_tokens,
                    )
                except TypeError:
                    pass
            return self._provider.generate_general_response(
                prompt=prompt,
                history=history,
                system_instruction=system_instruction,
            )
        return "General answer capability is not supported by the current provider."

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

    def check_primary_health(self):
        """Runs a lightweight health check on the primary Gemma 4 model."""
        if hasattr(self._provider, "check_primary_health"):
            return self._provider.check_primary_health()
        return self._provider.is_available(), "provider_default"

    def attempt_primary_recovery(self, force: bool = False) -> bool:
        """Attempts cooldown-gated recovery back to the primary Gemma 4 model."""
        if hasattr(self._provider, "attempt_primary_recovery"):
            return self._provider.attempt_primary_recovery(force=force)
        return False

    def reset_turn_trace(self) -> None:
        """Reset trace records for a new chat request turn."""
        if hasattr(self._provider, "reset_turn_trace"):
            self._provider.reset_turn_trace()

    def get_turn_trace(self) -> Dict[str, Any]:
        """Returns captured prompts and raw outputs from the latest request turn."""
        if hasattr(self._provider, "get_turn_trace"):
            return self._provider.get_turn_trace()
        return {}


# Global singleton instance
answer_model_service = AnswerModelService()
