"""Qwen Local Two-Layer Model using GGUF format and llama.cpp runtime.

Layer 1 — Input Understanding:
    understand_input(raw_message) → StructuredRequest
    Parses informal/complex/ambiguous user language into a structured request.
    Uses a JSON-only constrained prompt.
    Does NOT perform RBAC, access company data, or execute tools.

Layer 2 — Output Generation:
    generate_answer(verified_result) → str
    Converts verified MYGPT results into clear natural language for the user.
    Strictly bounded to verified findings only — no invented information.

Both layers share the SAME persistent llama.cpp model instance (self._llm).
The model is loaded ONCE at application startup via load_model().
"""

import gc
import os
import re
import json
import time
import threading
from typing import Dict, Any, List, Optional, Tuple
from loguru import logger

from backend.app.schemas.company_ai import CompanyAIResult, StructuredRequest
from backend.app.services.llm.base_answer_model import BaseAnswerModel

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_INPUT_UNDERSTANDING_SYSTEM = """\
You are MYGPT's semantic intent parser. Output ONLY a compact JSON object. No explanation, no markdown.

Supported capabilities:
- EXCEL_DATA (spreadsheets, columns, filters, totals, formulas)
- DOCUMENT (PDF, Word, resumes, policies, document Q&A, summaries)
- CODING (writing code, debugging, architecture, SQL)
- VISION (images, screenshots)
- REASONING_MATH (mathematical calculations)
- GENERAL (general conversation or knowledge)

Format (output compact JSON only):
{"capability":"<CAPABILITY>","operation":"<OPERATION>","target_columns":[],"filters":{}}
"""



_OUTPUT_GENERATION_SYSTEM = """\
You are the private response writer for a company AI system.
You do not perform company operations.
You do not make authorization decisions.
You do not invent company information.
You receive verified results produced by the company AI engine.
Your job is to explain those verified results clearly, professionally, and naturally to the user.
Use only the supplied verified information.
If the verified result says information is unavailable, missing, or could not be found, clearly say: "I couldn't find this information in the available company knowledge or documents."
Do not create facts that are not present in the verified result.
Do not claim that an action occurred unless the verified result explicitly says it occurred.
Do not output literal SVG tags, HTML placeholders, or strings like **svg** or [svg].
Do not output developer diagnostics, pipeline traces, or internal RAG identifiers.
Format key findings using clean Markdown bullet points, bold headers, or code blocks where appropriate."""


class QwenAnswerModel(BaseAnswerModel):
    """Local Qwen GGUF two-layer model runner powered by llama.cpp.

    Layer 1: understand_input()  — raw message → StructuredRequest
    Layer 2: generate_answer()   — verified result → natural language

    Both layers share the same persistent self._llm instance.
    """

    def __init__(self, model_dir: str = "models/local_llm"):
        self.model_dir = model_dir
        self.model_name = "Gemma-4-E2B-It-Q4_K_M"
        self._llm = None
        self._model_path: Optional[str] = None
        self._is_gemma: bool = True
        self._loaded_from_disk: bool = False
        self._load_attempted: bool = False
        self._lock = threading.RLock()

        # Primary / fallback / recovery state
        self._active_role: str = "unavailable"  # "primary" | "fallback" | "unavailable"
        self._primary_status: str = "uninitialized"  # "uninitialized" | "loaded" | "unavailable" | "failed" | "recovered"
        self._fallback_active: bool = False
        self._fallback_reason: Optional[str] = None
        self._fallback_activated_at: Optional[float] = None
        self._last_recovery_attempt_at: Optional[float] = None
        try:
            self._recovery_cooldown_seconds: float = float(
                os.environ.get("MYGPT_PRIMARY_RECOVERY_COOLDOWN_SEC", "120")
            )
        except ValueError:
            self._recovery_cooldown_seconds = 120.0
        self._recovery_status: str = "idle"
        self._consecutive_primary_failures: int = 0
        self._last_rss_mb: Optional[float] = None
        self._last_latency_seconds: float = 0.0

        self._last_execution_info: Dict[str, Any] = {
            "qwen_status": "uninitialized",
            "active_model": self.model_name,
            "active_role": self._active_role,
            "primary_status": self._primary_status,
            "fallback_used": False,
            "fallback_active": False,
            "fallback_reason": None,
            "retry_status": "not_needed",
            "recovery_status": self._recovery_status,
            "memory_rss_mb": None,
            "input_elapsed_seconds": 0.0,
            "output_elapsed_seconds": 0.0,
            "tokens_per_sec": 0.0,
        }
        # Trace diagnostics for debug logging
        self.last_layer1_prompt: Optional[str] = None
        self.last_layer1_raw_json: Optional[str] = None
        self.last_general_response_input: Optional[str] = None
        self.last_layer2_input: Optional[str] = None
        self._find_model_file()

    def reset_turn_trace(self) -> None:
        """Reset trace records for a new chat request turn."""
        self.last_layer1_prompt = None
        self.last_layer1_raw_json = None
        self.last_general_response_input = None
        self.last_layer2_input = None

    def get_turn_trace(self) -> Dict[str, Any]:
        """Returns captured prompts and raw outputs from the latest request turn."""
        return {
            "layer1_prompt": self.last_layer1_prompt,
            "layer1_raw_json": self.last_layer1_raw_json,
            "general_response_input": self.last_general_response_input,
            "layer2_input": self.last_layer2_input,
        }

    # ------------------------------------------------------------------
    # Model discovery, health check, switching & recovery lifecycle
    # ------------------------------------------------------------------

    def get_last_execution_info(self) -> Dict[str, Any]:
        """Returns diagnostic metrics from the most recent generation pass."""
        return dict(self._last_execution_info)

    @staticmethod
    def _is_rollback_mode() -> bool:
        return os.environ.get("MYGPT_GENERAL_MODEL_ROLLBACK", "").strip().lower() in (
            "qwen", "qwen2.5", "1", "true"
        )

    @staticmethod
    def _derive_model_identity(path: str) -> Tuple[str, bool]:
        """Returns (display_name, is_gemma) derived from a GGUF file path."""
        base = os.path.basename(path).lower()
        if "gemma" in base:
            return "Gemma-4-E2B-It-Q4_K_M", True
        if "coder" in base:
            return "Qwen2.5-Coder-3B-Instruct", False
        return "Qwen2.5-3B-Instruct", False

    @staticmethod
    def _is_valid_gguf(path: Optional[str]) -> bool:
        """Verifies file exists, meets minimum size, and carries the GGUF magic header."""
        if not path or not os.path.exists(path):
            return False
        try:
            if os.path.getsize(path) <= 100_000:
                return False
            with open(path, "rb") as f:
                return f.read(4) == b"GGUF"
        except OSError:
            return False

    @staticmethod
    def _get_rss_mb() -> Optional[float]:
        """Returns current process resident set size (RSS) in MB if psutil is available."""
        try:
            import psutil
            return round(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024), 1)
        except Exception:
            return None

    def _candidate_paths(self, family: str) -> List[str]:
        """Returns ordered GGUF candidate paths for 'primary' (Gemma 4) or 'fallback' (Qwen)."""
        default_dir = self.model_dir == "models/local_llm"
        repo_models = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "models", "local_llm")
        )
        if family == "primary":
            paths = [os.path.join(self.model_dir, "gemma-4-E2B-it-Q4_K_M.gguf")]
            if default_dir:
                paths.extend([
                    r"d:\MYGPT\models\local_llm\gemma-4-E2B-it-Q4_K_M.gguf",
                    os.path.join(repo_models, "gemma-4-E2B-it-Q4_K_M.gguf"),
                ])
            return paths

        paths = [
            os.path.join(self.model_dir, "coding", "qwen2.5-coder-3b-instruct-q4_k_m.gguf"),
            os.path.join(self.model_dir, "qwen2.5-coder-3b-instruct-q4_k_m.gguf"),
            os.path.join(self.model_dir, "qwen2.5-3b-instruct-q4_k_m.gguf"),
        ]
        if default_dir:
            paths.extend([
                r"d:\MYGPT\models\local_llm\coding\qwen2.5-coder-3b-instruct-q4_k_m.gguf",
                os.path.join(repo_models, "coding", "qwen2.5-coder-3b-instruct-q4_k_m.gguf"),
            ])
        return paths

    def _resolve_primary_path(self) -> Optional[str]:
        """Finds a valid primary GGUF path (respects explicit GENERAL_MODEL_PATH or rollback)."""
        env_override = os.environ.get("GENERAL_MODEL_PATH", "").strip()
        if env_override:
            return env_override if self._is_valid_gguf(env_override) else None
        if self._is_rollback_mode():
            for path in self._candidate_paths("fallback"):
                if "qwen3" not in path.lower() and self._is_valid_gguf(path):
                    return path
            return None
        for path in self._candidate_paths("primary"):
            if self._is_valid_gguf(path):
                return path
        return None

    def _resolve_fallback_path(self) -> Optional[str]:
        """Finds a valid Qwen2.5 fallback GGUF path."""
        for path in self._candidate_paths("fallback"):
            if "qwen3" not in path.lower() and self._is_valid_gguf(path):
                return path
        return None

    def _find_model_file(self) -> Optional[str]:
        """Identifies the best currently available GGUF path (primary preferred, else fallback)."""
        primary = self._resolve_primary_path()
        if primary:
            self._model_path = primary
            self.model_name, self._is_gemma = self._derive_model_identity(primary)
            logger.info(f"Located verified local primary GGUF model binary ({self.model_name}) at: {primary}")
            return primary

        if not self._is_rollback_mode() and not os.environ.get("GENERAL_MODEL_PATH", "").strip():
            fallback = self._resolve_fallback_path()
            if fallback:
                self._model_path = fallback
                self.model_name, self._is_gemma = self._derive_model_identity(fallback)
                logger.warning(
                    f"[FALLBACK] Primary Gemma 4 model unavailable during discovery; "
                    f"located fallback ({self.model_name}) at: {fallback}"
                )
                return fallback
        return None

    def _stop_tokens(self) -> List[str]:
        """Returns family-specific stop tokens for chat completions."""
        if self._is_gemma:
            return ["<turn|>", "<eos>"]
        return ["<|im_end|>", "<|endoftext|>", "<|im_start|>"]

    def _clean_model_output(self, text: str) -> str:
        """Strips any residual model control/thought tokens from generated text."""
        if not text:
            return ""
        cleaned = text
        if self._is_gemma:
            cleaned = re.sub(r"<\|channel>thought.*?<channel\|>", "", cleaned, flags=re.DOTALL)
            cleaned = cleaned.replace("<turn|>", "").replace("<eos>", "")
        return cleaned.strip()

    def _unload_current_model(self) -> None:
        """Releases the currently loaded Llama instance and forces GC before switching models."""
        llm = self._llm
        self._llm = None
        self._loaded_from_disk = False
        if llm is not None:
            prev_name = self.model_name
            try:
                if hasattr(llm, "close"):
                    llm.close()
            except Exception:
                pass
            del llm
            gc.collect()
            rss = self._get_rss_mb()
            logger.info(f"[MODEL_LIFECYCLE] Unloaded {prev_name} before switch (rss_mb={rss})")

    def _sync_registry(self, loaded: bool, load_time: Optional[float] = None, error: Optional[str] = None) -> None:
        """Keeps ModelRegistry synchronized with whichever general model is currently active."""
        try:
            from backend.app.services.llm.model_registry import model_registry, GENERAL_MODEL, ModelDescriptor
            registry_name = "gemma-4-e2b-it" if self._is_gemma else "qwen2.5-3b-instruct"
            existing = model_registry.get_model(GENERAL_MODEL)
            model_registry.register_model(
                ModelDescriptor(
                    name=registry_name,
                    capability=GENERAL_MODEL,
                    model_path=self._model_path or "",
                    provider=existing.provider if existing else "llama_cpp",
                    description=f"Active general model: {self.model_name}",
                )
            )
            if loaded and load_time is not None:
                model_registry.mark_loaded(GENERAL_MODEL, load_time, memory_usage=self._last_rss_mb)
            elif error:
                model_registry.mark_failed(GENERAL_MODEL, error)
        except Exception:
            pass

    def _update_execution_status(self, **extra: Any) -> None:
        """Synchronizes monitoring metadata fields in _last_execution_info."""
        rss = self._get_rss_mb()
        if rss is not None:
            self._last_rss_mb = rss
        self._last_execution_info.update({
            "active_model": self.model_name,
            "active_role": self._active_role,
            "primary_status": self._primary_status,
            "fallback_active": self._fallback_active,
            "fallback_used": self._fallback_active,
            "fallback_reason": self._fallback_reason,
            "recovery_status": self._recovery_status,
            "memory_rss_mb": self._last_rss_mb,
        })
        if extra:
            self._last_execution_info.update(extra)

    def _load_llama_instance(self, model_path: str, is_gemma: bool, display_name: str) -> Tuple[Any, float]:
        """Instantiates llama_cpp.Llama with family-specific chat_format and CPU settings."""
        from llama_cpp import Llama
        threads = min(4, os.cpu_count() or 4)
        logger.info(
            f"[MODEL_LOAD] Loading {display_name} from {model_path} "
            f"(threads={threads}, ctx=3072, batch=256, chat_format={'None(gguf_default)' if is_gemma else 'chatml'})..."
        )
        start_t = time.time()
        llama_kwargs: Dict[str, Any] = {
            "model_path": model_path,
            "n_ctx": 3072,
            "n_threads": threads,
            "n_threads_batch": threads,
            "n_batch": 256,
            "verbose": False,
            "chat_format": None if is_gemma else "chatml",
        }
        llm = Llama(**llama_kwargs)
        elapsed = time.time() - start_t
        return llm, elapsed

    def _activate_primary(self, reason: str = "startup") -> bool:
        """Loads Gemma 4 E2B (or explicit rollback primary) as the sole active model."""
        with self._lock:
            self._unload_current_model()
            path = self._resolve_primary_path()
            if not path:
                msg = "Primary Gemma 4 GGUF file missing or corrupted"
                self._primary_status = "unavailable"
                self._consecutive_primary_failures += 1
                self._sync_registry(loaded=False, error=msg)
                self._update_execution_status(qwen_status="unavailable")
                logger.error(f"[PRIMARY_FAIL] {msg} (reason={reason})")
                return False

            display_name, is_gemma = self._derive_model_identity(path)
            try:
                llm, elapsed = self._load_llama_instance(path, is_gemma, display_name)
                self._llm = llm
                self._model_path = path
                self._is_gemma = is_gemma
                self.model_name = display_name
                self._loaded_from_disk = True
                self._active_role = "primary"
                self._fallback_active = False
                self._fallback_reason = None
                self._consecutive_primary_failures = 0
                self._primary_status = "recovered" if reason == "health_check_recovery" else "loaded"
                rss = self._get_rss_mb()
                self._last_rss_mb = rss
                self._sync_registry(loaded=True, load_time=elapsed)
                self._update_execution_status(qwen_status="ready", retry_status="not_needed")
                logger.info(
                    f"[PRIMARY_ACTIVE] active_model={self.model_name} status={self._primary_status} "
                    f"load_time={elapsed:.2f}s rss_mb={rss} trigger={reason}"
                )
                return True
            except Exception as exc:
                self._llm = None
                self._loaded_from_disk = False
                self._primary_status = "failed"
                self._consecutive_primary_failures += 1
                self._sync_registry(loaded=False, error=str(exc))
                self._update_execution_status(qwen_status="failed")
                logger.error(f"[PRIMARY_FAIL] Failed loading {display_name} ({reason}): {exc}")
                return False

    def _activate_fallback(self, reason: str) -> bool:
        """Unloads any broken primary instance and activates Qwen2.5 fallback."""
        with self._lock:
            self._unload_current_model()
            if self._is_rollback_mode() or os.environ.get("GENERAL_MODEL_PATH", "").strip():
                self._active_role = "unavailable"
                self._update_execution_status(qwen_status="unavailable")
                return False

            fallback_path = self._resolve_fallback_path()
            if not fallback_path:
                self._active_role = "unavailable"
                self._fallback_active = True
                self._fallback_reason = reason
                self._fallback_activated_at = time.time()
                self._sync_registry(loaded=False, error=f"{reason}; fallback Qwen binary missing")
                self._update_execution_status(qwen_status="unavailable")
                logger.error(f"[FALLBACK_UNAVAILABLE] Cannot activate Qwen fallback ({reason}): file missing/invalid")
                return False

            display_name, is_gemma = self._derive_model_identity(fallback_path)
            logger.warning(f"[FALLBACK_ACTIVATED] reason={reason} -> activating {display_name}")
            try:
                llm, elapsed = self._load_llama_instance(fallback_path, is_gemma, display_name)
                self._llm = llm
                self._model_path = fallback_path
                self._is_gemma = False
                self.model_name = display_name
                self._loaded_from_disk = True
                self._active_role = "fallback"
                self._fallback_active = True
                self._fallback_reason = reason
                now = time.time()
                self._fallback_activated_at = now
                if self._last_recovery_attempt_at is None:
                    self._last_recovery_attempt_at = now
                rss = self._get_rss_mb()
                self._last_rss_mb = rss
                self._sync_registry(loaded=True, load_time=elapsed)
                self._update_execution_status(qwen_status="fallback_active")
                logger.info(
                    f"[FALLBACK_READY] active_model={self.model_name} load_time={elapsed:.2f}s "
                    f"rss_mb={rss} reason={reason}"
                )
                return True
            except Exception as exc:
                self._llm = None
                self._loaded_from_disk = False
                self._active_role = "unavailable"
                self._fallback_active = True
                self._fallback_reason = f"{reason}; fallback_load_error: {exc}"
                self._sync_registry(loaded=False, error=str(exc))
                self._update_execution_status(qwen_status="failed")
                logger.error(f"[FALLBACK_FAIL] Qwen fallback failed to load: {exc}")
                return False

    def check_primary_health(self) -> Tuple[bool, str]:
        """Lightweight health check for the primary Gemma 4 model (no duplicate RAM allocation)."""
        path = self._resolve_primary_path()
        if not path:
            return False, "Primary Gemma 4 model file missing or invalid GGUF header"
        return True, path

    def _effective_cooldown(self) -> float:
        """Applies exponential backoff on repeated primary failures to prevent flip-flopping."""
        base = max(0.0, self._recovery_cooldown_seconds)
        exponent = max(0, self._consecutive_primary_failures - 1)
        return min(base * (2 ** exponent), base * 8.0)

    def _should_attempt_recovery(self) -> bool:
        if not self._fallback_active or self._is_rollback_mode():
            return False
        anchor = max(self._fallback_activated_at or 0.0, self._last_recovery_attempt_at or 0.0)
        return (time.time() - anchor) >= self._effective_cooldown()

    def attempt_primary_recovery(self, force: bool = False) -> bool:
        """Attempts to restore Gemma 4 after cooldown and a passing health check."""
        with self._lock:
            if self._is_rollback_mode() or os.environ.get("GENERAL_MODEL_PATH", "").strip():
                return False
            if self._active_role == "primary" and self._llm is not None:
                return True
            if not force and not self._should_attempt_recovery():
                self._recovery_status = "cooldown_waiting"
                self._update_execution_status()
                return False

            self._last_recovery_attempt_at = time.time()
            healthy, detail = self.check_primary_health()
            if not healthy:
                self._recovery_status = "failed"
                self._consecutive_primary_failures += 1
                self._update_execution_status()
                logger.warning(f"[RECOVERY_SKIPPED] Health check failed: {detail}")
                return False

            self._recovery_status = "health_check_passed"
            logger.info(f"[RECOVERY_START] Primary health check passed ({detail}); restoring Gemma 4...")
            if self._activate_primary(reason="health_check_recovery"):
                self._recovery_status = "recovered"
                self._update_execution_status()
                logger.info(
                    f"[RECOVERY_COMPLETE] Restored active_model={self.model_name} "
                    f"rss_mb={self._last_rss_mb}"
                )
                return True

            # Recovery load failed — keep Qwen active and extend cooldown backoff
            self._recovery_status = "failed"
            self._activate_fallback(reason="primary_recovery_load_failed")
            return False

    def load_model(self) -> bool:
        """Explicitly loads local general LLM into persistent memory at startup."""
        return self._ensure_loaded()

    def _ensure_loaded(self) -> bool:
        """Ensures an active LLM is loaded (primary preferred, automatic Qwen fallback)."""
        with self._lock:
            # Verify primary loaded from disk has not disappeared or become corrupted at runtime
            if self._llm is not None and self._loaded_from_disk and self._active_role == "primary":
                if not self._is_valid_gguf(self._model_path):
                    logger.error(
                        f"[PRIMARY_FAIL] Active model file became unavailable during execution: {self._model_path}"
                    )
                    self._primary_status = "unavailable"
                    self._consecutive_primary_failures += 1
                    return self._activate_fallback(reason="primary_became_unavailable")

            # If currently in fallback mode, check cooldown recovery before serving request
            if self._fallback_active and self._should_attempt_recovery():
                self.attempt_primary_recovery(force=False)

            if self._llm is not None:
                return True

            if self._load_attempted and self._active_role == "unavailable":
                # Allow retry if primary became healthy again (e.g., recovered after both failed)
                healthy, _ = self.check_primary_health()
                if not healthy and not self._resolve_fallback_path():
                    return False

            self._load_attempted = True
            if self._activate_primary(reason="startup_load"):
                return True
            if self._activate_fallback(reason=f"primary_{self._primary_status}"):
                return True
            logger.warning("Neither Gemma 4 primary nor Qwen fallback could be loaded; using deterministic responses.")
            return False

    def is_available(self) -> bool:
        return self._llm is not None or self._resolve_primary_path() is not None or self._resolve_fallback_path() is not None

    def get_model_info(self) -> Dict[str, Any]:
        rss = self._get_rss_mb()
        if rss is not None:
            self._last_rss_mb = rss
        return {
            "model_name": self.model_name,
            "active_role": self._active_role,
            "primary_model": "Gemma-4-E2B-It-Q4_K_M",
            "fallback_model": "Qwen2.5-Coder-3B-Instruct",
            "primary_status": self._primary_status,
            "fallback_active": self._fallback_active,
            "fallback_reason": self._fallback_reason,
            "recovery_status": self._recovery_status,
            "recovery_cooldown_seconds": self._effective_cooldown() if self._fallback_active else self._recovery_cooldown_seconds,
            "consecutive_primary_failures": self._consecutive_primary_failures,
            "memory_rss_mb": self._last_rss_mb,
            "last_latency_seconds": self._last_latency_seconds,
            "quantization": "Q4_K_M",
            "format": "GGUF",
            "runtime": "llama.cpp",
            "local_only": True,
            "is_loaded": self._llm is not None,
            "model_path": self._model_path or "pending",
            "last_execution": dict(self._last_execution_info),
        }

    def _run_completion_with_fallback(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float,
        top_p: float = 0.9,
        stage: str = "general",
    ) -> Optional[Tuple[Dict[str, Any], float, str]]:
        """Thread-safe chat completion with automatic Qwen fallback & single safe retry."""
        with self._lock:
            if not self._ensure_loaded() or self._llm is None:
                self._update_execution_status(
                    qwen_status="unavailable",
                    retry_status="not_attempted_no_model",
                )
                return None

            attempt_role = self._active_role
            attempt_model = self.model_name
            t0 = time.time()
            try:
                response = self._llm.create_chat_completion(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    stop=self._stop_tokens(),
                )
                elapsed = time.time() - t0
                self._last_latency_seconds = round(elapsed, 3)
                retry_status = "served_by_fallback" if attempt_role == "fallback" else "not_needed"
                self._update_execution_status(retry_status=retry_status)
                logger.info(
                    f"[LLM_INFERENCE] stage={stage} active_model={attempt_model} role={attempt_role} "
                    f"latency={elapsed:.3f}s rss_mb={self._last_rss_mb}"
                )
                return response, elapsed, attempt_model
            except Exception as primary_err:
                elapsed = time.time() - t0
                logger.error(
                    f"[PRIMARY_FAIL] stage={stage} active_model={attempt_model} "
                    f"error={primary_err} after {elapsed:.3f}s"
                )
                if attempt_role == "primary" and not self._is_rollback_mode():
                    self._primary_status = "failed"
                    self._consecutive_primary_failures += 1
                    reason = f"inference_exception: {primary_err}"
                    if self._activate_fallback(reason=reason) and self._llm is not None:
                        t_retry = time.time()
                        try:
                            retry_resp = self._llm.create_chat_completion(
                                messages=messages,
                                max_tokens=max_tokens,
                                temperature=temperature,
                                top_p=top_p,
                                stop=self._stop_tokens(),
                            )
                            retry_elapsed = time.time() - t_retry
                            self._last_latency_seconds = round(retry_elapsed, 3)
                            self._update_execution_status(retry_status="succeeded")
                            logger.info(
                                f"[FALLBACK_RETRY] stage={stage} retry_status=succeeded "
                                f"active_model={self.model_name} latency={retry_elapsed:.3f}s "
                                f"rss_mb={self._last_rss_mb}"
                            )
                            return retry_resp, retry_elapsed, self.model_name
                        except Exception as fallback_err:
                            self._update_execution_status(
                                qwen_status="failed",
                                retry_status="failed",
                                fallback_reason=f"{reason}; fallback_retry_error: {fallback_err}",
                            )
                            logger.error(
                                f"[FALLBACK_FAIL] stage={stage} retry_status=failed "
                                f"fallback_model={self.model_name} error={fallback_err}"
                            )
                            return None

                    self._update_execution_status(
                        qwen_status="unavailable",
                        retry_status="failed_fallback_unavailable",
                    )
                    return None

                self._update_execution_status(
                    qwen_status="failed",
                    retry_status="failed",
                )
                return None

    # ------------------------------------------------------------------
    # Layer 1 — Input Understanding
    # ------------------------------------------------------------------

    def understand_input(
        self,
        raw_message: str,
        history: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[StructuredRequest]:
        """Layer 1: Parse raw/informal user message → StructuredRequest.

        Uses the same persistent llama.cpp instance with a JSON-only constrained prompt.
        Returns None if the model is unavailable or parsing fails.

        IMPORTANT: This method must NOT:
        - Perform RBAC checks
        - Access company databases or RAG
        - Execute any tools or workflows
        - Invent company policies
        """
        if not self.is_available():
            logger.info("[QWEN] understand_input: no local general model available — returning None")
            return None

        # Build context from session context or recent history
        context_parts = []
        if context:
            if context.get("department"):
                context_parts.append(f"active_department: {context['department']}")
            if context.get("active_document"):
                context_parts.append(f"active_document: {context['active_document']} (type: {context.get('active_document_type', 'GENERAL_DOCUMENT')})")
            if context.get("last_generated_file"):
                context_parts.append(f"last_generated_file: {context['last_generated_file']}")
            if context.get("last_topic"):
                context_parts.append(f"last_topic: {context['last_topic']}")
            if context.get("last_intent"):
                context_parts.append(f"last_intent: {context['last_intent']}")
            if context.get("last_action"):
                context_parts.append(f"last_action: {context['last_action']}")
            if context.get("pending_action"):
                context_parts.append(f"pending_action: {context['pending_action']}")
            if context.get("recent_history_summary"):
                context_parts.append(f"recent_history: {context['recent_history_summary']}")
        elif history and len(history) >= 1:
            last = history[-1]
            prev_dept = last.get("department", "")
            prev_intent = last.get("intent", "")
            if prev_dept and prev_dept != "GENERAL":
                context_parts.append(f"previous_department: {prev_dept}, previous_intent: {prev_intent}")

        context_note = ""
        if context_parts:
            context_note = "\nConversation Context:\n" + "\n".join(f"- {p}" for p in context_parts)

        user_prompt = f'Parse user request to compact JSON:{context_note}\n\nUser: "{raw_message}"'
        layer1_messages = [
            {"role": "system", "content": _INPUT_UNDERSTANDING_SYSTEM},
            {"role": "user",   "content": user_prompt}
        ]
        self.last_layer1_prompt = json.dumps(layer1_messages, indent=2)

        completion = self._run_completion_with_fallback(
            messages=layer1_messages,
            max_tokens=96,
            temperature=0.1,
            top_p=0.95,
            stage="layer1_understand",
        )
        if completion is None:
            logger.info("[QWEN_INPUT] triggered=true llama_cpp_called=false duration_ms=0 fallback_used=true")
            return None

        response, elapsed, used_model = completion
        try:
            raw_output = self._clean_model_output(response["choices"][0]["message"]["content"])
            self.last_layer1_raw_json = raw_output
            duration_ms = int(elapsed * 1000)
            logger.info(f"[PERF] qwen_input_understanding={elapsed:.3f}s model={used_model}")
            logger.info(f"[QWEN INPUT RAW] len={len(raw_output)}: {raw_output[:250]}")

            structured = self._parse_structured_request(raw_output, raw_message)
            if structured:
                self._update_execution_status(input_elapsed_seconds=round(elapsed, 3))
                logger.info(
                    f"[QWEN_INPUT] triggered=true llama_cpp_called=true model={used_model} "
                    f"duration_ms={duration_ms} fallback_used={self._fallback_active}"
                )
                return structured
            logger.warning("[QWEN] understand_input: JSON parse failed — returning None")
            logger.info(f"[QWEN_INPUT] triggered=true llama_cpp_called=true duration_ms={duration_ms} fallback_used=true")
            return None
        except Exception as e:
            logger.error(f"[QWEN] understand_input response parse error after {elapsed:.3f}s: {e}")
            logger.info(f"[QWEN_INPUT] triggered=true llama_cpp_called=true duration_ms={int(elapsed * 1000)} fallback_used=true")
            return None

    def _parse_structured_request(self, raw_output: str, original_message: str) -> Optional[StructuredRequest]:
        """Robustly parses Qwen's JSON output into a StructuredRequest.
        Handles markdown code fences, whitespace noise, and partial outputs.
        """
        # Strip markdown fences if present
        text = re.sub(r"```json\s*", "", raw_output, flags=re.I)
        text = re.sub(r"```\s*", "", text)
        text = text.strip()

        # Try to find the first {...} block
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None

        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            # Attempt to recover by fixing common issues
            try:
                # Replace single quotes with double quotes
                fixed = match.group().replace("'", '"')
                data = json.loads(fixed)
            except json.JSONDecodeError:
                return None

        # Validate required fields
        dept = str(data.get("department", "GENERAL")).strip().upper()
        intent = str(data.get("intent", "general_question")).strip().lower()
        action = str(data.get("action", "QUERY")).strip().upper()
        entities = data.get("entities", {}) or {}
        normalized = str(data.get("normalized_message", original_message)).strip()
        confidence = float(data.get("confidence", 0.75))

        # Validate department
        valid_depts = {"HR", "FINANCE", "TECH", "GENERAL"}
        if dept not in valid_depts:
            dept = "GENERAL"

        # Validate action
        valid_actions = {
            "QUERY", "CREATE", "EXPORT", "CALCULATE", "COMPARE", "DIAGNOSE",
            "SEARCH", "SUMMARIZE", "EXPAND", "MODIFY", "FILTER", "EVALUATE"
        }
        if action not in valid_actions:
            action = "QUERY"

        is_follow_up = bool(data.get("is_follow_up", False))
        ref_topic = data.get("referenced_previous_topic")
        if ref_topic is not None:
            ref_topic = str(ref_topic).strip() or None
        target_action = data.get("target_action")
        if target_action is not None:
            target_action = str(target_action).strip().upper() or None

        target_concept = data.get("target_concept")
        if target_concept is not None:
            target_concept = str(target_concept).strip().lower() or None

        filters = data.get("filters", {}) or {}
        if not isinstance(filters, dict):
            filters = {}

        operation = data.get("operation")
        if operation is not None:
            operation = str(operation).strip().upper() or None

        target_columns = data.get("target_columns", []) or []
        if not isinstance(target_columns, list):
            target_columns = [str(target_columns)]

        group_by = data.get("group_by")
        if group_by is not None:
            group_by = str(group_by).strip().lower() or None

        source_docs = data.get("source_documents", []) or []
        if not isinstance(source_docs, list):
            source_docs = [str(source_docs)]

        output_format = data.get("output_format")
        if output_format is not None:
            output_format = str(output_format).strip().upper() or None

        # Automatically align intent if operation is clear
        if operation == "COLUMN_LIST" and intent in ("general_question", "unknown"):
            intent = "excel_column_list"
        elif operation in ("COLUMN_READ", "COLUMN_EXPORT") and intent in ("general_question", "unknown"):
            intent = "excel_column_export"
        elif operation == "UNIQUE_VALUES" and intent in ("general_question", "unknown"):
            intent = "excel_unique_values"
        elif operation in ("GROUP", "DATE_GROUP") and intent in ("general_question", "unknown"):
            intent = "excel_group"
        elif operation == "GROUP_MAX" and intent in ("general_question", "unknown"):
            intent = "excel_group"
        elif operation == "GROUP_MIN" and intent in ("general_question", "unknown"):
            intent = "excel_group"
        elif operation in ("FILTER", "FILTER_COLUMN") and intent in ("general_question", "unknown"):
            intent = "excel_filter"
        elif operation == "FILTER_EXPORT" and intent in ("general_question", "unknown"):
            intent = "excel_filter_export"
        elif operation == "EXPORT_RESULT" and intent in ("general_question", "unknown"):
            intent = "excel_export_result"
        elif operation == "FULL_EXPORT" and intent in ("general_question", "unknown"):
            intent = "excel_full_export"
        elif operation in ("COMPARE", "COMPARISON", "MULTI_DOCUMENT_COMPARISON", "MULTI_DOCUMENT_SUMMARY") and intent in ("general_question", "unknown"):
            intent = "file_comparison" if dept == "FINANCE" else "excel_comparison"
        elif operation == "SUM" and intent in ("general_question", "unknown"):
            intent = "excel_total"
        elif operation == "COUNT" and intent in ("general_question", "unknown"):
            intent = "excel_count"
        elif operation == "AVERAGE" and intent in ("general_question", "unknown"):
            intent = "excel_average"
        elif operation == "MIN" and intent in ("general_question", "unknown"):
            intent = "excel_min"
        elif operation == "MAX" and intent in ("general_question", "unknown"):
            intent = "excel_max"
        elif operation in ("SUMMARY", "DOCUMENT_SUMMARY") and intent in ("general_question", "unknown"):
            intent = "document_summary"
        elif operation in ("DOCUMENT_TRANSFORMATION", "FLOWCHART", "WORKFLOW") and intent in ("general_question", "unknown"):
            intent = "document_transformation"
        elif operation in ("DOCUMENT_QUERY", "EXTRACT_INFORMATION", "DOCUMENT_QA") and intent in ("general_question", "unknown"):
            intent = "document_qa"

        # Validate capability
        cap = str(data.get("capability", "")).strip().upper()
        valid_caps = {"GENERAL", "REASONING_MATH", "CODING", "VISION", "EXCEL_DATA", "DOCUMENT", "RAG", "PROJECT", "MULTI_MODAL", "TOOL"}

        # Detect system building requests ("build a reconciliation web application")
        is_system_building = bool(re.search(
            r"\b(i\s+want\s+to\s+build|build\s+(?:me\s+)?a|create\s+(?:me\s+)?a|develop\s+(?:me\s+)?a)\s+(?:new\s+)?(?:web\s+)?(?:application|app|system|platform|portal|microservice)\b",
            original_message,
            re.I
        ))

        task_type = str(data.get("task_type", "")).strip().upper() or None
        requires_plan = bool(data.get("requires_plan", False)) or is_system_building
        if is_system_building:
            cap = "CODING"
            task_type = "PROJECT_PLANNING"
            operation = "PLANNING"
            requires_plan = True

        if not cap or cap not in valid_caps:
            if operation in ("CODE_GENERATION", "CODE_EXPLANATION", "CODE_DEBUG", "CODE_REVIEW", "PLANNING") or intent in ("code_generation", "code_explanation", "coding_debug", "code_review", "code_analysis"):
                cap = "CODING"
            elif operation in ("COLUMN_LIST", "COLUMN_READ", "COLUMN_EXPORT", "UNIQUE_VALUES", "FILTER", "FILTER_COLUMN", "GROUP", "SUM", "COUNT", "AVERAGE", "MIN", "MAX", "EXPORT_RESULT", "FULL_EXPORT", "COMPARE", "COMPARISON") or intent.startswith("excel_"):
                cap = "EXCEL_DATA"
            elif operation in ("SUMMARY", "DOCUMENT_TRANSFORMATION", "DOCUMENT_QUERY", "DOCUMENT_QA", "EXTRACT_INFORMATION") or intent.startswith("document_"):
                cap = "DOCUMENT"
            elif operation in ("IMAGE_UNDERSTANDING", "VISION") or intent in ("vision_analysis", "image_understanding"):
                cap = "VISION"
            elif operation in ("MATHEMATICS", "REASONING", "CALCULATION") or intent in ("math_solution", "reasoning_task"):
                cap = "REASONING_MATH"
            elif operation in ("PROJECT_INSPECTION", "INSPECT_PROJECT") or intent in ("project_inspection", "project_conventions"):
                cap = "PROJECT"
            elif operation in ("RAG", "RETRIEVAL"):
                cap = "RAG"
            else:
                cap = "GENERAL"

        parameters = data.get("parameters", {})
        if not isinstance(parameters, dict):
            parameters = {}
        files = data.get("files", [])
        if not isinstance(files, list):
            files = [str(files)]
        project_context_req = bool(data.get("project_context_required", False)) or (
            cap in ("CODING", "PROJECT") and any(w in original_message.lower() for w in ("project", "controller", "model", "convention", "route", "existing code"))
        )

        return StructuredRequest(
            capability=cap,
            operation=operation,
            task_type=task_type,
            user_request=original_message,
            department=dept,
            intent=intent,
            action=action,
            entities=entities if isinstance(entities, dict) else {},
            parameters=parameters,
            files=files,
            requires_plan=requires_plan,
            project_context_required=project_context_req,
            normalized_message=normalized or original_message,
            confidence=min(1.0, max(0.0, confidence)),
            source="qwen_nlp",
            is_follow_up=is_follow_up,
            referenced_previous_topic=ref_topic,
            target_action=target_action,
            target_concept=target_concept,
            filters=filters,
            target_columns=target_columns,
            group_by=group_by,
            source_documents=source_docs,
            output_format=output_format
        )

    # ------------------------------------------------------------------
    # Layer 2 — Output Generation
    # ------------------------------------------------------------------

    def generate_answer(
        self,
        verified_result: CompanyAIResult,
        original_message: Optional[str] = None,
        conversation_context: Optional[List[Dict[str, str]]] = None,
        response_format: str = "natural"
    ) -> str:
        """Layer 2: Convert verified MYGPT result into natural language.

        Uses the same persistent llama.cpp instance sequentially after Layer 1.
        Strictly bounded — only explains verified_result, never invents facts.
        """
        user_prompt = self._build_output_prompt(verified_result, original_message)

        if self.is_available():
            # Build message list with optional conversation context
            messages = [{"role": "system", "content": _OUTPUT_GENERATION_SYSTEM}]

            # Inject last 2 turns of conversation context for coherence
            if conversation_context:
                for turn in conversation_context[-2:]:
                    if turn.get("user_message"):
                        messages.append({"role": "user", "content": turn["user_message"]})
                    if turn.get("answer"):
                        messages.append({"role": "assistant", "content": str(turn["answer"])[:200]})

            messages.append({"role": "user", "content": user_prompt})
            self.last_layer2_input = json.dumps(messages, indent=2)

            completion = self._run_completion_with_fallback(
                messages=messages,
                max_tokens=220,
                temperature=0.2,
                top_p=0.9,
                stage="layer2_answer",
            )
            if completion is not None:
                response, elapsed, used_model = completion
                try:
                    generated_text = self._clean_model_output(response["choices"][0]["message"]["content"])
                    generated_text = re.sub(r"\*\*svg\*\*", "", generated_text, flags=re.I)
                    generated_text = re.sub(r"\[svg\]", "", generated_text, flags=re.I)
                    generated_text = re.sub(r"<svg.*?</svg>", "", generated_text, flags=re.DOTALL | re.I)
                    generated_text = generated_text.strip()
                    tokens_count = response.get("usage", {}).get("completion_tokens", len(generated_text.split()))
                    tps = round(tokens_count / max(elapsed, 0.001), 2)

                    logger.info(
                        f"[PERF] qwen_output_generation={elapsed:.3f}s model={used_model} "
                        f"({len(generated_text.split())} words, {tps} tok/s)"
                    )
                    logger.info(f"[QWEN OUTPUT RAW] len={len(generated_text)}: {repr(generated_text[:250])}")

                    if self._is_valid_natural_language(generated_text):
                        self._update_execution_status(
                            qwen_status="success",
                            output_elapsed_seconds=round(elapsed, 3),
                            tokens_per_sec=tps,
                        )
                        return generated_text
                    logger.warning("[QWEN] Output coherence check failed — using deterministic fallback.")
                    self._update_execution_status(
                        qwen_status="failed",
                        fallback_used=True,
                        fallback_reason="coherence_check",
                    )
                except Exception as e:
                    logger.error(f"[QWEN] generate_answer post-process error: {e}. Using deterministic fallback.")
                    self._update_execution_status(
                        qwen_status="failed",
                        fallback_used=True,
                        fallback_reason=str(e),
                        output_elapsed_seconds=0.0,
                        tokens_per_sec=0.0,
                    )
            else:
                self._update_execution_status(
                    qwen_status="failed",
                    fallback_used=True,
                    output_elapsed_seconds=0.0,
                    tokens_per_sec=0.0,
                )
        else:
            self._update_execution_status(
                qwen_status="unavailable",
                fallback_used=True,
                fallback_reason="Primary and fallback local models unavailable",
                output_elapsed_seconds=0.0,
                tokens_per_sec=0.0,
            )

        return self._format_deterministic_answer(verified_result)

    def generate_general_response(
        self,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Answers general knowledge, explanations, reasoning, and conversational queries using Gemma 4 (with automatic Qwen fallback)."""
        system_prompt = system_instruction or (
            "You are MYGPT, an intelligent, helpful, and versatile local AI assistant. "
            "Provide accurate, well-structured, and concise answers in clean Markdown. "
            "Explain concepts clearly, solve problems step-by-step, and keep responses focused so the complete answer finishes cleanly."
        )

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            for turn in history[-4:]:
                if turn.get("user_message"):
                    messages.append({"role": "user", "content": turn["user_message"]})
                if turn.get("answer"):
                    messages.append({"role": "assistant", "content": str(turn["answer"])[:400]})

        messages.append({"role": "user", "content": prompt})
        self.last_general_response_input = json.dumps(messages, indent=2)

        completion = self._run_completion_with_fallback(
            messages=messages,
            max_tokens=int(max_tokens) if max_tokens and max_tokens > 0 else 320,
            temperature=0.3,
            top_p=0.9,
            stage="general_response",
        )
        if completion is None:
            logger.error("[GENERAL_RESPONSE] Primary Gemma 4 and fallback Qwen are both unavailable; returning controlled message.")
            return (
                "Local AI models (primary Gemma 4 and fallback Qwen) are currently unavailable. "
                "Please verify the local GGUF model files or try again shortly."
            )

        response, elapsed, used_model = completion
        try:
            output = self._clean_model_output(response["choices"][0]["message"]["content"])
            tokens_count = response.get("usage", {}).get("completion_tokens", len(output.split()))
            tps = round(tokens_count / max(elapsed, 0.001), 2)
            self._update_execution_status(
                qwen_status="success",
                output_elapsed_seconds=round(elapsed, 3),
                tokens_per_sec=tps,
            )
            logger.info(
                f"[QWEN_GENERAL] active_model={used_model} words={len(output.split())} "
                f"latency={elapsed:.2f}s tps={tps} rss_mb={self._last_rss_mb}"
            )

            # Strict guard against token corruption, repetition or symbol spam
            if not self._is_valid_natural_language(output):
                logger.warning(f"[QWEN_GENERAL] Model returned invalid characters/gibberish: {repr(output[:80])}. Using safe fallback response.")
                return self._generate_fallback_general_response(prompt)

            return output
        except Exception as e:
            logger.error(f"[QWEN_GENERAL] Error formatting answer: {e}")
            return self._generate_fallback_general_response(prompt)

    def _is_valid_natural_language(self, text: str) -> bool:
        """Validates that model output is genuine readable language, rejecting gibberish/symbol noise."""
        if not text or len(text.strip()) < 3:
            return False
        clean = text.strip()
        # Strip standard Markdown horizontal rules (---, -----, ===) before checking symbol spam
        no_hr = re.sub(r"^\s*[-=*_]{3,}\s*$", "", clean, flags=re.MULTILINE).strip()
        if not no_hr:
            return False
        # Reject symbol/punctuation spam loops e.g. "!!!!!!" or "BD%+;D%!..."
        if re.search(r'[!@#$%^&*()_+=\[\]{}|\\;:\'",.<>/?`~-]{5,}', no_hr):
            return False
        alphanumeric = sum(c.isalnum() or c.isspace() for c in no_hr)
        # Output must be at least 65% alphanumeric/spaces
        return (alphanumeric / len(no_hr)) >= 0.65

    def _generate_fallback_general_response(self, prompt: str) -> str:
        """Deterministic, clean general response when local model outputs invalid tokens or errors."""
        p_lower = prompt.lower().strip()
        if any(g in p_lower for g in ["hello", "hi", "hey", "greetings"]):
            return "Hello! I am MYGPT, your local AI assistant. How can I assist you with your projects, coding, documents, spreadsheets, or questions today?"
        if "who are you" in p_lower or "what are you" in p_lower:
            return "I am MYGPT, a general-purpose local AI assistant. I run entirely on your local machine and can assist you with general knowledge, code development, data analysis, spreadsheets, and document understanding."
        if "capital of france" in p_lower:
            return "The capital of France is Paris."
        return (
            f"I have received your request: '{prompt.strip()}'. "
            "How can I assist you further with this?"
        )

    def _build_output_prompt(self, result: CompanyAIResult, original_message: Optional[str] = None) -> str:
        """Builds the strictly bounded user-facing output generation prompt."""
        lines = []

        if original_message:
            lines.append(f"USER'S ORIGINAL QUESTION: {original_message}")
            lines.append("")

        lines += [
            f"DEPARTMENT: {result.department.value}",
            f"TASK: {result.task or result.intent}",
            f"SUMMARY: {result.summary}"
        ]

        if result.findings:
            lines.append("VERIFIED FINDINGS:")
            for f in result.findings:
                lines.append(f"- {f}")

        if result.evidence:
            lines.append("SUPPORTING EVIDENCE:")
            for ev in result.evidence:
                lines.append(f"- {ev}")

        if result.tool_results:
            # Only include user-facing calculation results
            user_tool_results = {k: v for k, v in result.tool_results.items() if not str(k).startswith("_")}
            if user_tool_results:
                lines.append(f"CALCULATION RESULTS: {user_tool_results}")

        if result.warnings:
            lines.append("NOTICES / WARNINGS:")
            for w in result.warnings:
                lines.append(f"- {w}")

        if result.files:
            lines.append(f"GENERATED DOCUMENTS: {[f.get('filename') for f in result.files]}")

        lines.append("\nPlease provide a clear, professional, natural response explaining the above verified results to the user. Do not include internal trace IDs, internal RAG IDs, or raw developer diagnostics in your response.")
        return "\n".join(lines)

    def _format_deterministic_answer(self, result: CompanyAIResult) -> str:
        """Deterministic fallback formatter — always available, zero latency."""
        if result.permission_status == "DENIED":
            return (
                "Access to this department's privileged operations is restricted for your role. "
                "Your account does not possess the necessary RBAC permissions to execute this request."
            )

        paragraphs = []
        has_headline_finding = False
        if result.findings:
            first_f = str(result.findings[0]).strip()
            if first_f.startswith("🔴") or first_f.startswith("#") or first_f.startswith("|") or first_f.startswith("✓"):
                has_headline_finding = True

        if not has_headline_finding and result.summary and result.summary.strip():
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
