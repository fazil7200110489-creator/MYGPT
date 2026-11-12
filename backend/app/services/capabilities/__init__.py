"""Capability Module Initialization.

Instantiates and populates the global CapabilityRegistry.
"""

from backend.app.services.capabilities.base_capability import BaseCapability
from backend.app.services.capabilities.capability_registry import CapabilityRegistry
from backend.app.services.capabilities.general_capability import GeneralCapability
from backend.app.services.capabilities.vision_capability import VisionCapability
from backend.app.services.capabilities.excel_capability import ExcelCapability
from backend.app.services.capabilities.document_capability import DocumentCapability

# Global singleton registry
capability_registry = CapabilityRegistry()

# Register core capabilities
capability_registry.register(GeneralCapability())
capability_registry.register(VisionCapability())
capability_registry.register(VisionCapability("MULTIMODAL"))
capability_registry.register(ExcelCapability())
capability_registry.register(DocumentCapability())

__all__ = [
    "BaseCapability",
    "CapabilityRegistry",
    "capability_registry",
    "GeneralCapability",
    "VisionCapability",
    "ExcelCapability",
    "DocumentCapability",
]
