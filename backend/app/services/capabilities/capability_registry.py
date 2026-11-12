"""Modular Capability Registry for MYGPT.

Enables dynamic registration and resolution of capabilities.
New capabilities can be plugged in without modifying core orchestrator logic.
"""

from typing import Dict, Any, List, Optional
from loguru import logger

from backend.app.schemas.company_ai import StructuredRequest
from backend.app.schemas.capability import CapabilityEnum
from backend.app.services.capabilities.base_capability import BaseCapability


class CapabilityRegistry:
    """Registry managing all active MYGPT capabilities."""

    def __init__(self):
        self._capabilities: Dict[str, BaseCapability] = {}
        logger.info("Initializing CapabilityRegistry")

    def register(self, capability: BaseCapability) -> None:
        """Registers a capability instance under its uppercase canonical name."""
        name = capability.capability_name.upper()
        self._capabilities[name] = capability
        logger.info(f"[CAPABILITY_REGISTRY] Registered capability: {name}")

    def get(self, name: str) -> Optional[BaseCapability]:
        """Gets a capability by its exact name."""
        if not name:
            return None
        return self._capabilities.get(name.upper())

    def resolve(self, request: StructuredRequest, context: Optional[Any] = None) -> BaseCapability:
        """Resolves the best capability handler for a structured request:
        1. Check exact match by request.capability.
        2. Probe each capability via can_handle().
        3. Fall back safely to GENERAL capability if unknown.
        """
        req_cap = (request.capability or "").upper()
        aliases = {
            "EXCEL": "EXCEL_DATA",
            "SPREADSHEET": "EXCEL_DATA",
            "MATH": "REASONING_MATH",
            "ARITHMETIC": "REASONING_MATH",
            "CALCULATION": "REASONING_MATH",
            "CODE": "CODING",
            "MULTI_MODAL": "MULTIMODAL",
            "IMAGE": "VISION",
            "DOC": "DOCUMENT",
            "DOCS": "DOCUMENT",
            "TOOL": "TOOLS",
        }
        canonical = aliases.get(req_cap, req_cap)
        if canonical in self._capabilities:
            return self._capabilities[canonical]

        # Probe can_handle across registered capabilities
        for name, cap in self._capabilities.items():
            if name != CapabilityEnum.GENERAL.value and cap.can_handle(request, context):
                logger.info(f"[CAPABILITY_REGISTRY] Resolved capability via can_handle: {name}")
                return cap

        # Safe fallback to GENERAL
        logger.info("[CAPABILITY_REGISTRY] Delegating to default GENERAL capability")
        return self._capabilities.get(CapabilityEnum.GENERAL.value)

    def list_capabilities(self) -> List[str]:
        """Returns list of registered capability identifiers."""
        return list(self._capabilities.keys())

    def get_all(self) -> List[BaseCapability]:
        """Returns all registered capability instances."""
        return list(self._capabilities.values())
