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

    def _format_deterministic_answer(self, result: CompanyAIResult) -> str:
        """Deterministic formatter — always available, zero latency."""
        if result.permission_status == "DENIED":
            return (
                "Access to this department's privileged operations is restricted for your role. "
                "Your account does not possess the necessary RBAC permissions to execute this request."
            )

        paragraphs = []
        if result.summary and result.summary.strip():
            paragraphs.append(result.summary.strip())

        if result.findings:
            for f in result.findings:
                f_str = f.strip() if isinstance(f, str) else str(f).strip()
                if f_str and (not result.summary or f_str != result.summary.strip()):
                    paragraphs.append(f_str)

        if result.warnings:
            for w in result.warnings:
                paragraphs.append(f"Notice: {str(w).strip()}")

        answer = "\n\n".join(paragraphs).strip()
        if not answer:
            return "I couldn't find this information in the available company knowledge or documents."
        return answer
