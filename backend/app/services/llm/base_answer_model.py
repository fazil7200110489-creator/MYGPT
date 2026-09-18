"""Base interface for Local Answer Model Services.
Defines the two-layer Qwen contract:
  Layer 1: understand_input()  — parse raw user language → StructuredRequest
  Layer 2: generate_answer()   — convert verified MYGPT result → natural language
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from backend.app.schemas.company_ai import CompanyAIResult, StructuredRequest


class BaseAnswerModel(ABC):
    """Abstract base class for the two-layer local language model service."""

    @abstractmethod
    def understand_input(
        self,
        raw_message: str,
        history: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[StructuredRequest]:
        """Layer 1 — Input Understanding.
        Parses an informal/complex/ambiguous/contextual user message into a StructuredRequest.
        Receives raw_message, turn history, and structured conversation context.
        Must NOT perform RBAC, access company data, or execute tools.
        Returns None if the model is unavailable or parsing fails.
        """
        pass

    @abstractmethod
    def generate_answer(
        self,
        verified_result: CompanyAIResult,
        original_message: Optional[str] = None,
        conversation_context: Optional[List[Dict[str, str]]] = None,
        response_format: str = "natural"
    ) -> str:
        """Layer 2 — Output Generation.
        Converts a verified MYGPT CompanyAIResult into natural language for the user.
        Must ONLY use the verified result — must NOT invent company information.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if local model weights are loaded and ready."""
        pass

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """Returns non-sensitive model metadata."""
        pass
