"""General Conversational Capability.

Default fallback capability powered by Gemma 4 (with automatic Qwen fallback)
via answer_model_service.
"""

from typing import Dict, Any, Optional
from loguru import logger

from backend.app.schemas.company_ai import StructuredRequest
from backend.app.schemas.capability import CapabilityResult, CapabilityEnum, TaskTypeEnum
from backend.app.services.capabilities.base_capability import BaseCapability
from backend.app.services.llm.answer_model_service import answer_model_service


class GeneralCapability(BaseCapability):
    """Handles general conversational queries and fallback requests."""

    def __init__(self):
        super().__init__(CapabilityEnum.GENERAL.value)

    def can_handle(self, request: StructuredRequest, context: Optional[Any] = None) -> bool:
        return (request.capability or "").upper() in ("GENERAL", "")

    def execute(
        self,
        request: StructuredRequest,
        context: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> CapabilityResult:
        query = request.user_request
        logger.info(f"[GENERAL_CAPABILITY] Answering general query: '{query[:80]}'")
        try:
            answer = answer_model_service.generate_general_response(query)
            return CapabilityResult(
                success=True,
                capability=self.capability_name,
                operation="GENERAL_CHAT",
                task_type=TaskTypeEnum.GENERAL_QA.value,
                answer=answer,
                answer_type="text",
                confidence=0.9,
            )
        except Exception as e:
            logger.error(f"[GENERAL_CAPABILITY] Failed: {e}")
            return CapabilityResult(
                success=False,
                capability=self.capability_name,
                operation="GENERAL_CHAT",
                task_type=TaskTypeEnum.GENERAL_QA.value,
                answer="I encountered an error while generating a response.",
                answer_type="text",
                confidence=0.0,
            )

