"""Base Capability Interface for MYGPT Modular Capability Architecture.

Every capability must implement:
- can_handle(request, context) -> bool
- execute(request, context) -> CapabilityResult
- validate(result, request) -> CapabilityResult
- format_result(result) -> str
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from loguru import logger

from backend.app.schemas.company_ai import StructuredRequest
from backend.app.schemas.capability import CapabilityResult, CapabilityEnum


class BaseCapability(ABC):
    """Abstract Base Class for modular MYGPT capabilities."""

    def __init__(self, capability_name: str):
        self.capability_name = capability_name.upper()

    @abstractmethod
    def can_handle(self, request: StructuredRequest, context: Optional[Any] = None) -> bool:
        """Determines if this capability can process the given structured request."""
        pass

    @abstractmethod
    def execute(self, request: StructuredRequest, context: Optional[Any] = None) -> CapabilityResult:
        """Executes the capability using specialist models or deterministic tools."""
        pass

    def validate(self, result: CapabilityResult, request: StructuredRequest) -> CapabilityResult:
        """Verifies findings to prevent hallucination, math errors, or invalid code.
        Default implementation ensures non-empty answer or structured data.
        """
        if not result.answer and not result.structured_data and not result.plan:
            result.success = False
            result.answer = "Verification failed: Capability produced empty output."
        return result

    def format_result(self, result: CapabilityResult) -> str:
        """Formats the validated result into human-ready presentation."""
        return result.answer
