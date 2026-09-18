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

import os
import re
import json
import time
from typing import Dict, Any, List, Optional
from loguru import logger

from backend.app.schemas.company_ai import CompanyAIResult, StructuredRequest
from backend.app.services.llm.base_answer_model import BaseAnswerModel

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_INPUT_UNDERSTANDING_SYSTEM = """\
You are the primary semantic language parser for a private company AI system.
Understand the user's natural intent regardless of spelling mistakes, abbreviations, slang, synonyms, or indirect phrasing.
Parse the user request into structured JSON only. Output ONLY valid JSON. No prose. No markdown fences.

Departments: HR, FINANCE, TECH, GENERAL

Intents:
- HR: policy_question, candidate_search, candidate_comparison, candidate_skills, candidate_experience, candidate_role_fit_analysis, candidate_education, candidate_summary, offer_letter, recruitment, employee_information, document_creation, document_modification, document_export
- FINANCE: expense_calculation, expense_report, expense_report_summary, invoice, invoice_inquiry, invoice_export, excel_comparison, budget_analysis, financial_question
- TECH: troubleshooting, error_diagnosis, log_analysis, code_analysis, incident_report, technical_question
- GENERAL: document_summary, file_comparison, excel_summary, excel_total, excel_average, excel_count, excel_min, excel_max, excel_group_max, excel_group_min, excel_split, excel_filter, excel_export, excel_export_result, excel_full_export, excel_column_list, excel_column_export, excel_unique_values, excel_multi_document_summary, excel_report, what_happened, greeting, general_question

Actions: QUERY, CREATE, EXPORT, CALCULATE, COMPARE, DIAGNOSE, SEARCH, SUMMARIZE, EXPAND, MODIFY, FILTER, EVALUATE

Semantic Intent Guidelines:
- "what are the transaction modes" -> action="QUERY", intent="excel_unique_values", target_concept="transaction_mode", operation="UNIQUE_VALUES"
- "give me the total UPI amount" -> action="CALCULATE", intent="excel_total", filters={"mode": "UPI"}, operation="SUM"
- "give me UPI transaction details only as Excel" -> action="EXPORT", intent="excel_filter", filters={"mode": "UPI"}, operation="FILTER_EXPORT"
- "give me mobile numbers only as Excel" or "mobil enumbers only as exel sheet" -> action="EXPORT", intent="excel_column_export", target_concept="phone", operation="COLUMN_EXPORT"
- "give me the QR transaction mode as Excel" -> action="EXPORT", intent="excel_filter", filters={"mode": "QR"}, operation="FILTER_EXPORT"
- "give me this as Excel" or "Excel sheet" (referring to previous verified result) -> action="EXPORT", intent="excel_export_result", is_follow_up=true, operation="EXPORT_RESULT"
- "what are the mismatches in the 2 Excel files" -> action="COMPARE", intent="excel_comparison", operation="COMPARE"
- If the conversation context is about an HR policy and the user asks a follow-up ("what about casual leave?"), set department="HR", intent="policy_question", is_follow_up=true.
- If the conversation is comparing resumes/candidates and user asks "who is better?" or "which is best?", set department="HR", intent="candidate_comparison", is_follow_up=true.

Output exactly this JSON structure (no other text):
{
  "department": "GENERAL",
  "intent": "excel_total",
  "action": "CALCULATE",
  "operation": "SUM",
  "target_concept": "amount",
  "filters": {"mode": "UPI"},
  "target_columns": [],
  "entities": {
    "output_format": null,
    "leave_type": null,
    "amounts": null,
    "candidate_name": null,
    "period": null,
    "status_code": null,
    "file_operation": null,
    "referenced_file": null
  },
  "normalized_message": "Calculate the total amount for UPI transactions",
  "confidence": 0.95,
  "is_follow_up": false,
  "referenced_previous_topic": null,
  "target_action": null
}"""

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
        self.model_name = "Qwen3-4B-Q4_K_M"
        self._llm = None
        self._model_path = None
        self._load_attempted = False
        self._last_execution_info: Dict[str, Any] = {
            "qwen_status": "uninitialized",
            "fallback_used": False,
            "fallback_reason": None,
            "input_elapsed_seconds": 0.0,
            "output_elapsed_seconds": 0.0,
            "tokens_per_sec": 0.0
        }
        self._find_model_file()

    # ------------------------------------------------------------------
    # Model lifecycle
    # ------------------------------------------------------------------

    def get_last_execution_info(self) -> Dict[str, Any]:
        """Returns diagnostic metrics from the most recent generation pass."""
        return dict(self._last_execution_info)

    def _find_model_file(self) -> Optional[str]:
        """Locates the Qwen3-4B GGUF model file — cached after first discovery."""
        if self._model_path and os.path.exists(self._model_path):
            return self._model_path
        candidates = [
            os.path.join(self.model_dir, "Qwen3-4B-Q4_K_M.gguf"),
            r"d:\MYGPT\models\local_llm\Qwen3-4B-Q4_K_M.gguf",
            os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "models", "local_llm", "Qwen3-4B-Q4_K_M.gguf"))
        ]
        for path in candidates:
            if os.path.exists(path) and os.path.getsize(path) > 100_000:
                self._model_path = path
                logger.info(f"Located local Qwen3-4B GGUF model binary at: {path}")
                return path
        return None

    def load_model(self) -> bool:
        """Explicitly loads local Qwen model into persistent memory at startup."""
        return self._ensure_loaded()

    def _ensure_loaded(self) -> bool:
        """Initialises llama-cpp-python engine if not yet loaded. Never reloads."""
        if self._llm is not None:
            logger.info("[QWEN] reuse_existing_model")
            return True
        if self._load_attempted and self._llm is None:
            return False

        self._load_attempted = True
        model_path = self._find_model_file()
        if not model_path:
            logger.info("Local Qwen GGUF model binary not found. Using deterministic answer engine.")
            return False

        try:
            from llama_cpp import Llama
            threads = min(8, os.cpu_count() or 4)
            logger.info("[QWEN] initialization_start")
            logger.info(f"Loading local Qwen GGUF model into memory from {model_path} (threads={threads}, ctx=2048)...")
            start_t = time.time()
            self._llm = Llama(
                model_path=model_path,
                n_ctx=2048,
                n_threads=threads,
                n_batch=512,
                verbose=False
            )
            elapsed = time.time() - start_t
            logger.info(f"[QWEN] initialization_complete (loaded in {elapsed:.2f}s)")
            return True
        except Exception as e:
            logger.warning(f"llama-cpp model load warning: {e}. Falling back to deterministic answer formatter.")
            return False

    def is_available(self) -> bool:
        return self._model_path is not None or self._llm is not None

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "quantization": "Q4_K_M",
            "format": "GGUF",
            "runtime": "llama.cpp",
            "local_only": True,
            "is_loaded": self._llm is not None,
            "model_path": self._model_path or "pending",
            "last_execution": self._last_execution_info
        }

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
        if not self._ensure_loaded() or self._llm is None:
            logger.info("[QWEN] understand_input: model unavailable — returning None")
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

        user_prompt = f'Parse this user request into JSON:{context_note}\n\nUser: "{raw_message}"'

        t0 = time.time()
        try:
            response = self._llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": _INPUT_UNDERSTANDING_SYSTEM},
                    {"role": "user",   "content": user_prompt}
                ],
                max_tokens=256,
                temperature=0.1,   # Near-deterministic for structured output
                top_p=0.95,
                stop=["<|im_end|>", "<|endoftext|>", "<|im_start|>", "}\n", "\n\n"]
            )
            elapsed = time.time() - t0
            raw_output = response["choices"][0]["message"]["content"].strip()
            duration_ms = int(elapsed * 1000)
            logger.info(f"[PERF] qwen_input_understanding={elapsed:.3f}s")
            logger.info(f"[QWEN INPUT RAW] len={len(raw_output)}: {raw_output[:250]}")

            structured = self._parse_structured_request(raw_output, raw_message)
            if structured:
                self._last_execution_info["input_elapsed_seconds"] = round(elapsed, 3)
                logger.info(f"[QWEN_INPUT] triggered=true llama_cpp_called=true duration_ms={duration_ms} fallback_used=false")
                return structured
            else:
                logger.warning("[QWEN] understand_input: JSON parse failed — returning None")
                logger.info(f"[QWEN_INPUT] triggered=true llama_cpp_called=true duration_ms={duration_ms} fallback_used=true")
                return None

        except Exception as e:
            elapsed = time.time() - t0
            duration_ms = int(elapsed * 1000)
            logger.error(f"[QWEN] understand_input error after {elapsed:.3f}s: {e}")
            logger.info(f"[QWEN_INPUT] triggered=true llama_cpp_called=true duration_ms={duration_ms} fallback_used=true")
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

        return StructuredRequest(
            department=dept,
            intent=intent,
            action=action,
            entities=entities if isinstance(entities, dict) else {},
            normalized_message=normalized or original_message,
            confidence=min(1.0, max(0.0, confidence)),
            source="qwen_nlp",
            is_follow_up=is_follow_up,
            referenced_previous_topic=ref_topic,
            target_action=target_action,
            target_concept=target_concept,
            filters=filters,
            operation=operation,
            target_columns=target_columns
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

        if self._ensure_loaded() and self._llm is not None:
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

            try:
                t0 = time.time()
                response = self._llm.create_chat_completion(
                    messages=messages,
                    max_tokens=150,
                    temperature=0.2,
                    top_p=0.9,
                    stop=["<|im_end|>", "<|endoftext|>", "<|im_start|>"]
                )
                elapsed = time.time() - t0
                generated_text = response["choices"][0]["message"]["content"].strip()
                generated_text = re.sub(r"\*\*svg\*\*", "", generated_text, flags=re.I)
                generated_text = re.sub(r"\[svg\]", "", generated_text, flags=re.I)
                generated_text = re.sub(r"<svg.*?</svg>", "", generated_text, flags=re.DOTALL | re.I)
                generated_text = generated_text.strip()
                tokens_count = response.get("usage", {}).get("completion_tokens", len(generated_text.split()))
                tps = round(tokens_count / max(elapsed, 0.001), 2)

                logger.info(f"[PERF] qwen_output_generation={elapsed:.3f}s ({len(generated_text.split())} words, {tps} tok/s)")
                logger.info(f"[QWEN OUTPUT RAW] len={len(generated_text)}: {repr(generated_text[:250])}")
                self._last_execution_info.update({
                    "qwen_status": "success",
                    "fallback_used": False,
                    "fallback_reason": None,
                    "output_elapsed_seconds": round(elapsed, 3),
                    "tokens_per_sec": tps
                })

                if self._is_valid_natural_language(generated_text):
                    return generated_text
                else:
                    logger.warning("[QWEN] Output coherence check failed — using deterministic fallback.")
                    self._last_execution_info.update({"qwen_status": "failed", "fallback_used": True, "fallback_reason": "coherence_check"})

            except Exception as e:
                logger.error(f"[QWEN] generate_answer error: {e}. Using deterministic fallback.")
                self._last_execution_info.update({
                    "qwen_status": "failed",
                    "fallback_used": True,
                    "fallback_reason": str(e),
                    "output_elapsed_seconds": 0.0,
                    "tokens_per_sec": 0.0
                })
        else:
            self._last_execution_info.update({
                "qwen_status": "unavailable",
                "fallback_used": True,
                "fallback_reason": "Qwen runtime not loaded",
                "output_elapsed_seconds": 0.0,
                "tokens_per_sec": 0.0
            })

        return self._format_deterministic_answer(verified_result)

    def _is_valid_natural_language(self, text: str) -> bool:
        if not text or len(text.strip()) < 15:
            return False
        words = text.split()
        if len(words) < 4:
            return False
        alphanumeric = sum(c.isalnum() or c.isspace() for c in text)
        return (alphanumeric / len(text)) >= 0.70

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
        if result.findings:
            for f in result.findings:
                if f.strip():
                    paragraphs.append(f.strip())
        elif result.summary:
            paragraphs.append(result.summary.strip())

        if result.warnings:
            for w in result.warnings:
                paragraphs.append(f"Notice: {w.strip()}")

        answer = "\n\n".join(paragraphs).strip()
        if not answer:
            return "I couldn't find this information in the available company knowledge or documents."
        return answer
