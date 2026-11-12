"""Vision and Multimodal Capability.

Uses Qwen2-VL-2B for image understanding, screenshot diagnosis, and visual error extraction.
Supports combined Vision + Coding pipelines when a fix is requested from an image.
"""

from typing import Dict, Any, Optional
from loguru import logger

from backend.app.schemas.company_ai import StructuredRequest
from backend.app.schemas.capability import CapabilityResult, CapabilityEnum, TaskTypeEnum
from backend.app.services.capabilities.base_capability import BaseCapability
from backend.app.services.llm.vision_model import vision_model
from backend.app.services.document_manager import document_manager


class VisionCapability(BaseCapability):
    """Visual Understanding and Image Intelligence Specialist."""

    def __init__(self, capability_name: str = CapabilityEnum.VISION.value):
        super().__init__(capability_name)

    def can_handle(self, request: StructuredRequest, context: Optional[Any] = None) -> bool:
        cap = (request.capability or "").upper()
        if cap in ("VISION", "IMAGE", "MULTI_MODAL"):
            return True
        if request.task_type in (TaskTypeEnum.IMAGE_INSPECTION.value, TaskTypeEnum.VISION_CODING.value):
            return True

        # Check for image attachments
        active_doc = request.active_document or (context.active_document if context else None)
        if isinstance(active_doc, dict):
            ext = active_doc.get("extension", "").lower()
            if ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"):
                return True

        return False

    def execute(self, request: StructuredRequest, context: Optional[Any] = None) -> CapabilityResult:
        query = (request.user_request or request.normalized_message or "").strip()
        logger.info(f"[VISION_CAPABILITY] Analyzing visual request: {query!r}")

        img_path, filename = self._resolve_image_path(request, context)
        if not img_path:
            return CapabilityResult(
                success=False,
                capability=self.capability_name,
                operation="NO_IMAGE",
                task_type=TaskTypeEnum.IMAGE_INSPECTION.value,
                answer="No image is currently attached. Please upload an image or screenshot to analyze.",
                answer_type="error",
                confidence=1.0
            )

        try:
            # Pure visual inspection
            ans = vision_model.analyze_image(
                image_path_or_bytes=img_path,
                prompt=query,
                task="image_understanding"
            )
            return CapabilityResult(
                success=True,
                capability=self.capability_name,
                operation="IMAGE_INSPECTION",
                task_type=TaskTypeEnum.IMAGE_INSPECTION.value,
                answer=ans,
                answer_type="text",
                sources=[filename] if filename else [],
                confidence=0.95
            )
        except Exception as e:
            logger.error(f"[VISION_CAPABILITY] Execution error: {e}")
            return CapabilityResult(
                success=False,
                capability=self.capability_name,
                operation="IMAGE_INSPECTION",
                task_type=TaskTypeEnum.IMAGE_INSPECTION.value,
                answer=f"Vision model error: {str(e)}",
                answer_type="error",
                confidence=0.5
            )

    def _resolve_image_path(self, request: StructuredRequest, context: Optional[Any]) -> tuple[Optional[str], Optional[str]]:
        doc_id = getattr(request, "active_document", None)
        if not doc_id and context:
            doc_id = getattr(context, "active_document_id", None) or getattr(context, "active_document", None)

        if isinstance(doc_id, dict):
            return doc_id.get("file_path") or doc_id.get("path"), doc_id.get("filename")

        if doc_id:
            doc_meta = document_manager.get_document(doc_id)
            if doc_meta:
                return doc_meta.get("file_path"), doc_meta.get("filename")

        return None, None
