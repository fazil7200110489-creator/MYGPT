"""Centralized Model Registry for MYGPT.

Manages all local AI models across all specialized capabilities:
- GENERAL_MODEL: Qwen3-4B (Layer 1 input understanding & Layer 2 response formatting)
- CODING_MODEL: Qwen2.5-Coder-3B (Software engineering, debugging, code refactoring)
- VISION_MODEL: Qwen2-VL-2B (Visual reasoning, screenshots, UI, OCR, charts)
- EMBEDDING_MODEL: PyTorch token/dense embeddings

Centralizes paths, runtimes, quantization, and status to prevent hardcoding model paths throughout the application.
"""

import os
import time
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from loguru import logger

from backend.app.core.config import settings


class ModelDescriptor(BaseModel):
    """Specification and live state descriptor for a model in the registry."""
    key: str = Field(..., description="Unique registry key: general | coding | vision | embedding")
    name: str = Field(..., description="Human-readable model name e.g. qwen2.5-coder-3b")
    path: str = Field(..., description="Absolute filesystem path to model weights")
    mmproj_path: Optional[str] = Field(default=None, description="Optional path to multimodal projector GGUF")
    type: str = Field(..., description="Model functional domain: general | coding | vision | embedding")
    runtime: str = Field(default="llama.cpp", description="Execution runtime: llama.cpp | pytorch")
    quantization: str = Field(default="Q4_K_M", description="Quantization scheme e.g. Q4_K_M, FP16")
    capabilities: List[str] = Field(default_factory=list, description="Supported operations/tasks")
    status: str = Field(default="unloaded", description="Current lifecycle state: unloaded | loaded | failed")
    loaded: bool = Field(default=False, description="Whether model is currently loaded in memory")
    load_time: Optional[float] = Field(default=None, description="Model load duration in seconds")
    memory_usage: Optional[str] = Field(default=None, description="Estimated memory footprint or parameter count")


class ModelRegistry:
    """Central singleton model registry orchestrating model locations and capabilities."""

    _instance: Optional['ModelRegistry'] = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ModelRegistry, cls).__new__(cls, *args, **kwargs)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        self._models: Dict[str, ModelDescriptor] = {}
        self._initialize_default_registry()
        self._initialized = True
        logger.info("ModelRegistry initialized with registered models: " + ", ".join(self._models.keys()))

    def _initialize_default_registry(self) -> None:
        """Configures default models with dynamic overrides from settings/environment."""
        base_dir = getattr(settings, "BASE_DIR", r"d:\MYGPT")
        models_dir = os.path.join(base_dir, "models")

        # 1. General Model (Gemma 4 E2B primary, with Qwen2.5 rollback fallback)
        general_path = getattr(settings, "GENERAL_MODEL_PATH", "")
        if not general_path or not os.path.exists(general_path) or "qwen3" in general_path.lower():
            gemma_cand = os.path.join(models_dir, "local_llm", "gemma-4-E2B-it-Q4_K_M.gguf")
            coding_cand = os.path.join(models_dir, "local_llm", "coding", "qwen2.5-coder-3b-instruct-q4_k_m.gguf")
            if os.path.exists(gemma_cand):
                general_path = gemma_cand
            elif os.path.exists(coding_cand):
                general_path = coding_cand
            else:
                general_path = os.path.join(models_dir, "local_llm", "qwen2.5-coder-3b-instruct-q4_k_m.gguf")

        is_gemma_general = "gemma" in os.path.basename(general_path).lower()
        self._models["general"] = ModelDescriptor(
            key="general",
            name="gemma-4-e2b-it" if is_gemma_general else "qwen2.5-3b-instruct",
            path=general_path,
            type="general",
            runtime="llama.cpp",
            quantization="Q4_K_M",
            capabilities=[
                "input_understanding",
                "output_generation",
                "conversational_reasoning",
                "general_knowledge",
                "document_qa"
            ],
            status="loaded" if os.path.exists(general_path) else "unloaded",
            loaded=False,
            memory_usage="E2B / 4.6B total (~2.35 GB RSS)" if is_gemma_general else "3B parameters (~2.7 GB RSS)"
        )

        # 2. Coding Model (Qwen2.5-Coder-3B)
        coding_path = getattr(settings, "CODING_MODEL_PATH", os.path.join(models_dir, "local_llm", "coding", "qwen2.5-coder-3b-instruct-q4_k_m.gguf"))
        self._models["coding"] = ModelDescriptor(
            key="coding",
            name="qwen2.5-coder-3b",
            path=coding_path,
            type="coding",
            runtime="llama.cpp",
            quantization="Q4_K_M",
            capabilities=[
                "coding_debug",
                "code_explanation",
                "code_generation",
                "code_refactoring",
                "error_analysis",
                "stack_trace_analysis",
                "sql_analysis",
                "api_debugging",
                "dependency_analysis",
                "code_comparison",
                "architecture_analysis"
            ],
            status="loaded" if os.path.exists(coding_path) else "unloaded",
            loaded=False,
            memory_usage="3B parameters (~1.9 GB)"
        )

        # 3. Vision Model (Qwen2-VL-2B)
        vision_path = getattr(settings, "VISION_MODEL_PATH", os.path.join(models_dir, "vision", "Qwen2-VL-2B-Instruct-Q4_K_M.gguf"))
        vision_mmproj = getattr(settings, "VISION_MMPROJ_PATH", os.path.join(models_dir, "vision", "mmproj-Qwen2-VL-2B-Instruct-f16.gguf"))
        self._models["vision"] = ModelDescriptor(
            key="vision",
            name="qwen2-vl-2b",
            path=vision_path,
            mmproj_path=vision_mmproj,
            type="vision",
            runtime="llama.cpp",
            quantization="Q4_K_M",
            capabilities=[
                "image_understanding",
                "screenshot_analysis",
                "ui_debugging",
                "chart_analysis",
                "diagram_analysis",
                "scanned_document_reading",
                "visual_error_detection",
                "mobile_screenshot_analysis",
                "website_screenshot_analysis",
                "ocr_visual"
            ],
            status="loaded" if os.path.exists(vision_path) else "unloaded",
            loaded=False,
            memory_usage="2B parameters (~2.2 GB with mmproj)"
        )

        # 4. Embedding Model
        self._models["embedding"] = ModelDescriptor(
            key="embedding",
            name="bpe-tokenizer-dense-embedding",
            path=os.path.join(models_dir, "tokenizer"),
            type="embedding",
            runtime="pytorch",
            quantization="FP32",
            capabilities=["token_embeddings", "dense_retrieval", "semantic_search"],
            status="loaded",
            loaded=True,
            memory_usage="~50 MB"
        )

    def register_model(self, descriptor: ModelDescriptor) -> None:
        """Registers or updates a model descriptor in the registry."""
        self._models[descriptor.key] = descriptor
        logger.info(f"Model registered: {descriptor.key} -> {descriptor.name} ({descriptor.path})")

    def get_model(self, key: str) -> Optional[ModelDescriptor]:
        """Retrieves a model descriptor by key (general, coding, vision, embedding)."""
        return self._models.get(key.lower())

    def get_model_path(self, key: str) -> Optional[str]:
        """Returns the configured model filepath for a given model key."""
        m = self.get_model(key)
        return m.path if m else None

    def is_available(self, key: str) -> bool:
        """Checks whether the model file physically exists on disk."""
        m = self.get_model(key)
        if not m:
            return False
        if m.runtime == "llama.cpp":
            exists = os.path.exists(m.path) and os.path.getsize(m.path) > 100_000
            if m.mmproj_path:
                exists = exists and os.path.exists(m.mmproj_path) and os.path.getsize(m.mmproj_path) > 100_000
            return exists
        return True

    def mark_loaded(self, key: str, load_time: float, memory_usage: Optional[str] = None) -> None:
        """Updates model runtime status when loaded into RAM."""
        if key in self._models:
            self._models[key].loaded = True
            self._models[key].status = "loaded"
            self._models[key].load_time = round(load_time, 2)
            if memory_usage:
                self._models[key].memory_usage = memory_usage
            logger.info(f"Model '{key}' marked as loaded (load_time={load_time:.2f}s)")

    def mark_unloaded(self, key: str) -> None:
        """Updates model runtime status when freed from RAM."""
        if key in self._models:
            self._models[key].loaded = False
            self._models[key].status = "unloaded"
            logger.info(f"Model '{key}' marked as unloaded")

    def mark_failed(self, key: str, reason: str) -> None:
        """Marks model as failed during load or inference."""
        if key in self._models:
            self._models[key].loaded = False
            self._models[key].status = f"failed: {reason}"
            logger.warning(f"Model '{key}' marked as failed: {reason}")

    def list_models(self) -> List[Dict[str, Any]]:
        """Returns a list of all registered models and their current metadata."""
        return [m.model_dump() for m in self._models.values()]

    def get_model_status(self) -> Dict[str, Any]:
        """Provides high-level operational status across all registered models."""
        return {
            key: {
                "name": m.name,
                "available": self.is_available(key),
                "loaded": m.loaded,
                "path": m.path,
                "runtime": m.runtime,
                "capabilities": m.capabilities,
                "quantization": m.quantization
            }
            for key, m in self._models.items()
        }

    def get_status(self) -> Dict[str, Any]:
        """Provides high-level summary and detailed model status."""
        statuses = self.get_model_status()
        return {
            "total_models": len(self._models),
            "models": statuses
        }


# Global centralized model registry singleton
model_registry = ModelRegistry()

GENERAL_MODEL = "general"
CODING_MODEL = "coding"
VISION_MODEL = "vision"
EMBEDDING_MODEL = "embedding"
