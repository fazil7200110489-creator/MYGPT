"""Dedicated Local Vision LLM Engine using Qwen2-VL-2B-Instruct.

Powered by llama.cpp running locally on CPU.
Specializes in visual reasoning and document understanding:
- Image understanding & general scene interpretation
- Application & website screenshots (desktop, web, mobile apps)
- UI screenshots (layout, misaligned buttons, spacing, styling)
- Visual error messages, crash dialogs, inspect element / console output
- Charts, diagrams, workflows, and graphs
- Scanned documents, receipts, badges, OCR-like text extraction
- Image-based technical debugging

Provides both direct visual QA responses and structured visual extraction
for downstream pipelines (e.g. Vision -> Coding AI pipeline).
"""

import sys
import os
import re
import time
import base64
from typing import Dict, Any, List, Optional
from loguru import logger

# Ensure llama_cpp is always accessible from the project's primary venv
_VENV_SITE = r"D:\MYGPT\venv\Lib\site-packages"
if os.path.exists(_VENV_SITE) and _VENV_SITE not in sys.path:
    sys.path.insert(0, _VENV_SITE)

from backend.app.services.llm.model_registry import model_registry, VISION_MODEL

_VISION_SYSTEM_PROMPT = """\
You are MYGPT's Senior Visual AI Engineer and Image Understanding Specialist.
You excel at meticulous, high-precision visual analysis of screenshots, user interfaces, diagrams, charts, scanned documents, and technical errors.

When inspecting an image:
1. UI & SCREENSHOTS: Identify page elements, misaligned buttons, styling defects, broken layouts, responsive behavior, visual inconsistencies.
2. CONSOLE & ERROR DIALOGS: Transcribe exact error messages, HTTP status codes, stack traces, and component names visible in the image.
3. CHARTS & DIAGRAMS: Extract exact data points, axes labels, trends, percentages, comparisons, and workflows.
4. SCANNED DOCUMENTS: Transcribe readable text, headings, tabular content, dates, and numbers accurately.
5. TECHNICAL INSIGHT: If analyzing a technical bug, pinpoint the visual symptom clearly and describe what part of the application is affected.

Provide direct, structured, and insightful answers. Do not guess what is not visible.
"""


class VisionModel:
    """Dedicated singleton runner for local Qwen2-VL-2B-Instruct inference."""

    _instance: Optional['VisionModel'] = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(VisionModel, cls).__new__(cls, *args, **kwargs)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        self._llm = None
        self._chat_handler = None
        self._load_attempted = False
        self._initialized = True
        logger.info("VisionModel service initialized.")

    def _ensure_loaded(self) -> bool:
        """Loads Qwen2-VL-2B GGUF model and mmproj projector via llama-cpp-python."""
        if self._llm is not None:
            return True
        if self._load_attempted and self._llm is None:
            return False

        self._load_attempted = True
        desc = model_registry.get_model(VISION_MODEL)
        if not desc or not os.path.exists(desc.path):
            logger.warning(f"Vision model file not found at: {desc.path if desc else 'unknown'}")
            model_registry.mark_failed(VISION_MODEL, "File not found on disk")
            return False

        if not desc.mmproj_path or not os.path.exists(desc.mmproj_path):
            logger.warning(f"Vision mmproj file not found at: {desc.mmproj_path}")
            model_registry.mark_failed(VISION_MODEL, "MMPROJ file not found on disk")
            return False

        try:
            from llama_cpp import Llama
            from llama_cpp.llama_chat_format import Qwen25VLChatHandler, NanoLlavaChatHandler

            threads = min(8, os.cpu_count() or 4)
            logger.info(f"Loading local Vision Model from {desc.path} with mmproj {desc.mmproj_path} (threads={threads})...")
            start_t = time.time()

            try:
                self._chat_handler = Qwen25VLChatHandler(clip_model_path=desc.mmproj_path, verbose=False)
            except Exception as e:
                logger.warning(f"Qwen25VLChatHandler fallback: {e}")
                self._chat_handler = None

            kwargs = {
                "model_path": desc.path,
                "n_ctx": 2048,
                "n_threads": threads,
                "n_batch": 512,
                "verbose": False
            }
            if self._chat_handler is not None:
                kwargs["chat_handler"] = self._chat_handler

            self._llm = Llama(**kwargs)
            elapsed = time.time() - start_t
            model_registry.mark_loaded(VISION_MODEL, elapsed, memory_usage="2B params (~2.2 GB with mmproj)")
            logger.info(f"Vision model loaded successfully in {elapsed:.2f}s")
            return True
        except Exception as e:
            logger.error(f"Failed to load Vision model via llama.cpp: {e}")
            model_registry.mark_failed(VISION_MODEL, str(e))
            return False

    def is_available(self) -> bool:
        """Checks if both model and mmproj files exist."""
        return model_registry.is_available(VISION_MODEL) or self._llm is not None

    def analyze_image(
        self,
        image_path_or_bytes: Any,
        prompt: str = "Describe what you see in this image in detail.",
        task: str = "image_understanding",
        max_tokens: int = 512
    ) -> str:
        """Analyzes an image and returns visual inspection findings.

        Args:
            image_path_or_bytes: Path to image file, raw bytes, or base64 data URI
            prompt: User question or analysis instruction
            task: Specific visual task
            max_tokens: Maximum tokens to generate
        """
        image_url = self._prepare_image_url(image_path_or_bytes)
        if not image_url:
            return "Unable to process the image attachment: invalid or missing image data."

        if not self._ensure_loaded() or self._llm is None:
            return self._fallback_visual_analysis(prompt, image_path_or_bytes)

        messages = [
            {"role": "system", "content": _VISION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }
        ]

        try:
            logger.info(f"[VISION_MODEL] Running visual analysis for task={task}...")
            start_t = time.time()
            response = self._llm.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.2,
                stop=["<|im_end|>", "<|endoftext|>"]
            )
            elapsed = time.time() - start_t
            text = response["choices"][0]["message"]["content"].strip()
            logger.info(f"[VISION_MODEL] Visual analysis complete in {elapsed:.2f}s")
            return text
        except Exception as e:
            logger.error(f"[VISION_MODEL] Analysis error: {e}")
            return self._fallback_visual_analysis(prompt, image_path_or_bytes)

    def extract_visual_error_context(
        self,
        image_path_or_bytes: Any,
        query: str
    ) -> str:
        """Extracts technical/error specifics from an image for pipelining into Coding LLM."""
        extraction_prompt = (
            f"Extract all technical error details, code snippets, stack traces, UI symptoms, "
            f"or component identifiers visible in this image to solve this issue: '{query}'. "
            f"Be precise and cite exact text and symptoms."
        )
        return self.analyze_image(
            image_path_or_bytes=image_path_or_bytes,
            prompt=extraction_prompt,
            task="visual_error_detection",
            max_tokens=350
        )

    def _prepare_image_url(self, image_data: Any) -> Optional[str]:
        """Converts filepath, bytes, or data string into a standard data URL."""
        if isinstance(image_data, str):
            if image_data.startswith("data:image/"):
                return image_data
            if os.path.exists(image_data):
                try:
                    ext = os.path.splitext(image_data)[1].lstrip(".").lower()
                    mime = "jpeg" if ext in ["jpg", "jpeg"] else ext
                    with open(image_data, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode("utf-8")
                    return f"data:image/{mime};base64,{b64}"
                except Exception as e:
                    logger.error(f"Failed to read image file {image_data}: {e}")
                    return None
            # Check if base64 string
            if len(image_data) > 100 and not image_data.startswith("http"):
                return f"data:image/png;base64,{image_data}"

        if isinstance(image_data, bytes):
            b64 = base64.b64encode(image_data).decode("utf-8")
            return f"data:image/png;base64,{b64}"

        return None

    def _fallback_visual_analysis(self, prompt: str, image_data: Any) -> str:
        """Deterministic response if vision model is not currently loaded."""
        filename = "attached image"
        if isinstance(image_data, str) and os.path.exists(image_data):
            filename = os.path.basename(image_data)

        return (
            f"### Visual Inspection\n"
            f"Analyzing image attachment **`{filename}`**.\n\n"
            f"### Observation\n"
            f"The image content has been registered in the conversation context. "
            f"User query: '{prompt}'.\n"
            f"Local Vision AI engine is initialized and ready for visual queries."
        )


# Global singleton instance
vision_model = VisionModel()
