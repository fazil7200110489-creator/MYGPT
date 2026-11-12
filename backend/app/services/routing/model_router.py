"""Local Model Router for MYGPT Phase 1 Architecture.

Inspects:
1. Explicit user request & intent
2. Attachment type (images, code files, spreadsheets, documents)
3. Active document type & metadata
4. Conversation context & multi-turn history
5. Presence of code, syntax tokens, stack traces, compiler errors, or API logs

Strict Routing Priority:
EXPLICIT USER REQUEST
    ↓
ATTACHMENT TYPE
    ↓
ACTIVE DOCUMENT TYPE
    ↓
CONVERSATION CONTEXT
    ↓
TASK INTENT
    ↓
MODEL SELECTION

Models:
- CODING: Qwen2.5-Coder-3B (software engineering, debugging, code generation, refactoring)
- VISION: Qwen2-VL-2B (visual understanding, screenshots, UI, charts, diagrams, OCR)
- VISION -> CODING: Combined pipeline (visual error/UI screenshot + code fix)
- EXCEL: Excel Engine (authoritative calculations, aggregations, formulas)
- DOCUMENT: Document/RAG processor (policies, manuals, resumes, narrative reports)
- GENERAL: Qwen3-4B (general knowledge, conversational logic)

Returns a structured ModelRoutingDecision without exposing routing internals to normal users.
"""

import os
import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from loguru import logger

from backend.app.services.llm.model_registry import (
    model_registry, GENERAL_MODEL, CODING_MODEL, VISION_MODEL
)

# Supported coding file extensions
CODE_EXTENSIONS = {
    ".php", ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".cs",
    ".cpp", ".c", ".sql", ".html", ".css", ".json", ".xml", ".yaml",
    ".yml", ".md", ".txt"
}

# Supported image file extensions
IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".svg"
}

# Supported spreadsheet extensions
EXCEL_EXTENSIONS = {
    ".xlsx", ".xls", ".csv", ".xlsm"
}

# Supported document extensions
DOCUMENT_EXTENSIONS = {
    ".docx", ".doc", ".pdf", ".pptx", ".ppt", ".odt"
}


class ModelRoutingDecision(BaseModel):
    """Structured decision returned by the Local Model Router."""
    capability: str = Field(..., description="Target capability: coding | vision | vision_coding | excel | document | general")
    model: str = Field(..., description="Selected model identifier or subsystem name")
    task: str = Field(..., description="Specific task classified e.g. coding_debug, image_understanding")
    confidence: float = Field(..., description="Routing confidence score 0.0 - 1.0")
    reason: str = Field(..., description="Deterministic or contextual rationale for routing")
    is_combined_pipeline: bool = Field(default=False, description="Whether request chains multiple models (e.g. Vision -> Coding)")
    pipeline_stages: List[str] = Field(default_factory=list, description="Ordered execution pipeline stages")
    entities: Dict[str, Any] = Field(default_factory=dict, description="Extracted routing entities and metadata")


class ModelRouter:
    """Capability-based local router directing inputs to the appropriate model/engine."""

    def __init__(self):
        logger.info("Local ModelRouter initialized.")

    # ----------------------------------------------------------------------
    # Core Routing Entry Point
    # ----------------------------------------------------------------------

    def route(
        self,
        query: str,
        attachment: Optional[Dict[str, Any]] = None,
        active_document: Optional[Dict[str, Any]] = None,
        context_state: Optional[Any] = None,
        history: Optional[List[Dict[str, Any]]] = None
    ) -> ModelRoutingDecision:
        """Determines target capability and model based on strict 6-stage priority."""
        q_clean = query.strip()
        q_lower = q_clean.lower()

        # ------------------------------------------------------------------
        # STAGE 1: Explicit User Request Directives
        # ------------------------------------------------------------------
        explicit_decision = self._check_explicit_request(q_clean, q_lower)
        if explicit_decision:
            # If explicit coding request with an attached image, promote to combined pipeline
            if explicit_decision.capability == "coding" and attachment and self._is_image_attachment(attachment):
                return ModelRoutingDecision(
                    capability="vision_coding",
                    model="vision_and_coding_pipeline",
                    task="image_assisted_code_fix",
                    confidence=0.98,
                    reason="Explicit coding request provided with visual error/UI screenshot",
                    is_combined_pipeline=True,
                    pipeline_stages=["vision_extraction", "coding_generation"]
                )
            return explicit_decision

        # ------------------------------------------------------------------
        # STAGE 2: Attachment Type Detection
        # ------------------------------------------------------------------
        if attachment:
            att_decision = self._route_by_attachment(attachment, q_clean, q_lower)
            if att_decision:
                return att_decision

        # ------------------------------------------------------------------
        # STAGE 3: Active Document Type Continuity
        # ------------------------------------------------------------------
        if active_document:
            active_decision = self._route_by_active_document(active_document, q_clean, q_lower, context_state)
            if active_decision:
                return active_decision

        # ------------------------------------------------------------------
        # STAGE 4: Presence of Code, Errors, Stack Traces, or SQL in Message
        # ------------------------------------------------------------------
        code_signal_decision = self._detect_code_or_error_content(q_clean, q_lower)
        if code_signal_decision:
            return code_signal_decision

        # ------------------------------------------------------------------
        # STAGE 5: Conversation Context & Prior Topic Continuity
        # ------------------------------------------------------------------
        context_decision = self._route_by_conversation_context(q_clean, q_lower, context_state, history)
        if context_decision:
            return context_decision

        # ------------------------------------------------------------------
        # STAGE 6: General Model Fallback
        # ------------------------------------------------------------------
        general_desc = model_registry.get_model(GENERAL_MODEL)
        general_model_id = general_desc.name if general_desc else "gemma-4-e2b-it"
        return ModelRoutingDecision(
            capability="general",
            model=general_model_id,
            task="general_knowledge",
            confidence=0.85,
            reason="No specialized attachment, active code document, or technical error detected",
            is_combined_pipeline=False,
            pipeline_stages=["general_llm"]
        )

    # ----------------------------------------------------------------------
    # Stage 1: Explicit Directives
    # ----------------------------------------------------------------------

    def _check_explicit_request(self, text: str, lower: str) -> Optional[ModelRoutingDecision]:
        # Explicit Vision requests
        if any(lower.startswith(k) or f" {k}" in lower for k in [
            "inspect this screenshot", "read this screenshot", "analyze this image",
            "what is in this image", "look at this image", "what does this screenshot show",
            "explain this chart", "read this chart", "explain this diagram", "read this scanned page"
        ]):
            return ModelRoutingDecision(
                capability="vision",
                model="qwen2-vl-2b",
                task="image_understanding",
                confidence=0.96,
                reason="Explicit user directive requesting visual/image understanding",
                is_combined_pipeline=False,
                pipeline_stages=["vision_llm"]
            )

        # Shell, terminal, system command execution requests
        if re.search(r'\b(execute|run|exec|bash|powershell|cmd|terminal)\b', lower) and (
            re.search(r'\b(rm\s+-rf|del\s+/[sfq]|chmod|chown|kill|pkill|shutdown|reboot|curl.*?\|\s*bash|wget.*?\|\s*sh|drop\s+table|truncate)\b', lower)
            or any(k in lower for k in ["command", "script", "terminal", "server cache", "shell"])
        ):
            return ModelRoutingDecision(
                capability="coding",
                model="qwen2.5-coder-3b",
                task="code_execution",
                confidence=0.98,
                reason="Direct system command or shell execution request directed to coding sandbox guardrails",
                is_combined_pipeline=False,
                pipeline_stages=["coding_llm"]
            )

        # Explicit Coding requests:
        # 1. Technical framework/language + code construct combination (e.g. CodeIgniter 3 controller, CI3 function, PHP function, React component)
        framework_keywords = [
            "codeigniter", "ci3", "ci4", "laravel", "symfony", "yii", "flask", "fastapi",
            "django", "express", "react", "vue", "angular", "nextjs", "node", "nodejs",
            "php", "python", "javascript", "typescript", "sql", "mysql", "postgres",
            "css", "html", "jquery", "c#", "c++", "java", "golang", "rust"
        ]
        construct_keywords = [
            "controller", "function", "method", "class", "endpoint", "api", "query",
            "script", "component", "middleware", "model", "migration", "code", "crud"
        ]
        has_framework_and_construct = (
            any(f in lower for f in framework_keywords) and
            any(c in lower for c in construct_keywords)
        )

        # 2. Direct coding action / verb requests (e.g. write code, debug this, explain function, I need a controller method, give me a function)
        has_action_request = bool(
            re.search(r'\b(give\s+me|i\s+need|need\s+a|show\s+me|create|write|generate|implement|build|make|debug|fix|explain|refactor|solve|optimize)\b.*\b(code|function|method|class|controller|api|endpoint|query|script|component|algorithm)\b', lower)
        )

        has_coding_intent = has_framework_and_construct or has_action_request or any(k in lower for k in [
            "write code", "generate code", "fix the code", "debug this", "refactor this",
            "500 error", "stack trace", "syntax error", "runtime error", "typeerror", "referenceerror", "indexerror", "keyerror"
        ])

        if has_coding_intent:
            task = self._classify_coding_task(text, lower)
            return ModelRoutingDecision(
                capability="coding",
                model="qwen2.5-coder-3b",
                task=task,
                confidence=0.95,
                reason=f"Explicit user request for code implementation, debugging, or explanation ({task})",
                is_combined_pipeline=False,
                pipeline_stages=["coding_llm"]
            )

        return None

    # ----------------------------------------------------------------------
    # Stage 2: Attachment Routing
    # ----------------------------------------------------------------------

    def _route_by_attachment(
        self,
        att: Dict[str, Any],
        query: str,
        lower: str
    ) -> Optional[ModelRoutingDecision]:
        fname = (att.get("filename") or att.get("name") or "").lower()
        ext = os.path.splitext(fname)[1].lower() or att.get("extension", "").lower()
        mime = (att.get("mime_type") or att.get("content_type") or "").lower()

        # 1. Image Attachment
        if ext in IMAGE_EXTENSIONS or mime.startswith("image/"):
            # Check if query requests technical/code fixes based on image
            is_coding_intent = any(k in lower for k in [
                "fix", "code", "react", "css", "html", "javascript", "python",
                "error", "bug", "why is this", "misaligned", "solve", "change",
                "button", "component", "screen error", "api", "crash"
            ])
            if is_coding_intent and any(k in lower for k in ["code", "react", "css", "fix this", "changes required"]):
                return ModelRoutingDecision(
                    capability="vision_coding",
                    model="vision_and_coding_pipeline",
                    task="image_to_code_solution",
                    confidence=0.97,
                    reason=f"Image attachment '{fname}' paired with request for technical code solution",
                    is_combined_pipeline=True,
                    pipeline_stages=["vision_extraction", "coding_generation"]
                )
            return ModelRoutingDecision(
                capability="vision",
                model="qwen2-vl-2b",
                task="screenshot_analysis" if "screen" in lower or "ui" in lower else "image_understanding",
                confidence=0.98,
                reason=f"Image attachment '{fname}' requires local visual reasoning",
                is_combined_pipeline=False,
                pipeline_stages=["vision_llm"]
            )

        # 2. Code Attachment
        if ext in CODE_EXTENSIONS or att.get("document_type") == "CODE":
            task = self._classify_coding_task(query, lower)
            return ModelRoutingDecision(
                capability="coding",
                model="qwen2.5-coder-3b",
                task=task,
                confidence=0.98,
                reason=f"Code file attachment '{fname}' (extension: {ext}) routed to Coding LLM",
                is_combined_pipeline=False,
                pipeline_stages=["coding_llm"],
                entities={"file": fname, "extension": ext}
            )

        # 3. Excel Spreadsheet Attachment -> EXCEL ENGINE (Never Vision)
        if ext in EXCEL_EXTENSIONS or "spreadsheet" in fname or att.get("document_type") == "EXCEL":
            return ModelRoutingDecision(
                capability="excel",
                model="excel_processor",
                task="spreadsheet_analytics",
                confidence=0.99,
                reason=f"Spreadsheet attachment '{fname}' routed strictly to Excel calculation engine",
                is_combined_pipeline=False,
                pipeline_stages=["excel_processor"]
            )

        # 4. Standard Text PDF or Document -> DOCUMENT ENGINE (Never Vision unless image-only)
        if ext in DOCUMENT_EXTENSIONS or att.get("document_type") in ["PDF", "DOCX", "RESUME", "INVOICE"]:
            is_scanned = att.get("is_scanned", False) or "scanned" in fname
            if is_scanned:
                return ModelRoutingDecision(
                    capability="vision",
                    model="qwen2-vl-2b",
                    task="scanned_document_reading",
                    confidence=0.94,
                    reason=f"Scanned document '{fname}' routed to Vision AI for OCR reading",
                    is_combined_pipeline=False,
                    pipeline_stages=["vision_llm"]
                )
            return ModelRoutingDecision(
                capability="document",
                model="rag_engine",
                task="document_qa",
                confidence=0.96,
                reason=f"Text document attachment '{fname}' routed to Document/RAG processor",
                is_combined_pipeline=False,
                pipeline_stages=["document_rag"]
            )

        return None

    # ----------------------------------------------------------------------
    # Stage 3: Active Document Continuity
    # ----------------------------------------------------------------------

    def _route_by_active_document(
        self,
        active_doc: Dict[str, Any],
        query: str,
        lower: str,
        context_state: Optional[Any]
    ) -> Optional[ModelRoutingDecision]:
        fname = (active_doc.get("filename") or active_doc.get("active_document_name") or "").lower()
        ext = os.path.splitext(fname)[1].lower() or active_doc.get("extension", "").lower()
        doc_type = active_doc.get("document_type") or getattr(context_state, "active_document_type", None) or ""

        # Active Code Document
        if ext in CODE_EXTENSIONS or doc_type == "CODE":
            # Questions referencing active code document (e.g. "where exactly?", "find the error", "give me the corrected function")
            task = self._classify_coding_task(query, lower)
            return ModelRoutingDecision(
                capability="coding",
                model="qwen2.5-coder-3b",
                task=task,
                confidence=0.96,
                reason=f"Active code document '{fname}' governs conversation context for coding inquiry",
                is_combined_pipeline=False,
                pipeline_stages=["coding_llm"],
                entities={"active_code_document": fname}
            )

        # Active Excel Document -> Excel processor for analytical queries
        if ext in EXCEL_EXTENSIONS or doc_type == "EXCEL":
            if any(k in lower for k in ["total", "sum", "count", "average", "column", "rows", "calculate", "sheet", "split", "export"]):
                return ModelRoutingDecision(
                    capability="excel",
                    model="excel_processor",
                    task="spreadsheet_analytics",
                    confidence=0.98,
                    reason=f"Active Excel document '{fname}' receives analytical calculation request",
                    is_combined_pipeline=False,
                    pipeline_stages=["excel_processor"]
                )

        # Active Image Document -> Vision
        if ext in IMAGE_EXTENSIONS or doc_type == "IMAGE":
            if any(k in lower for k in ["write react", "give me css", "generate code", "fix in code"]):
                return ModelRoutingDecision(
                    capability="vision_coding",
                    model="vision_and_coding_pipeline",
                    task="image_to_code_solution",
                    confidence=0.96,
                    reason=f"Active image '{fname}' combined with code fix request",
                    is_combined_pipeline=True,
                    pipeline_stages=["vision_extraction", "coding_generation"]
                )
            return ModelRoutingDecision(
                capability="vision",
                model="qwen2-vl-2b",
                task="image_understanding",
                confidence=0.95,
                reason=f"Active image '{fname}' continues visual inspection thread",
                is_combined_pipeline=False,
                pipeline_stages=["vision_llm"]
            )

        return None

    # ----------------------------------------------------------------------
    # Stage 4: Text Content Inspection (Code, Traces, APIs, SQL)
    # ----------------------------------------------------------------------

    def _detect_code_or_error_content(self, text: str, lower: str) -> Optional[ModelRoutingDecision]:
        # 1. Stack Traces & Exceptions
        if any(sig in text for sig in [
            "Traceback (most recent call last):",
            "Fatal error: Uncaught",
            "Exception in thread",
            "NullPointerException",
            "TypeError: Cannot read properties",
            "SyntaxError:",
            "ReferenceError:",
            "ZeroDivisionError",
            "IndexError: list index out of range",
            "KeyError",
            "ValueError"
        ]) or re.search(r'\b(KeyError|TypeError|ValueError|IndexError|SyntaxError|ReferenceError|NullPointerException|AttributeError|ZeroDivisionError|FileNotFoundError)\b', text) \
           or re.search(r'File ".*?", line \d+', text) or re.search(r'at .*? \(\S+:\d+:\d+\)', text):
            return ModelRoutingDecision(
                capability="coding",
                model="qwen2.5-coder-3b",
                task="stack_trace_analysis",
                confidence=0.99,
                reason="Presence of software runtime stack trace / exception log",
                is_combined_pipeline=False,
                pipeline_stages=["coding_llm"]
            )

        # 2. HTTP API 500 / 4xx errors
        if re.search(r'\b(?:500|502|503|504|400|401|403|404)\s+(?:error|internal server error|bad request|unauthorized|forbidden)\b', lower) or \
           "500 error from this api" in lower or "api returning 500" in lower or "cors error" in lower or "jwt expired" in lower:
            return ModelRoutingDecision(
                capability="coding",
                model="qwen2.5-coder-3b",
                task="api_debugging",
                confidence=0.96,
                reason="API runtime / HTTP status code error debugging inquiry",
                is_combined_pipeline=False,
                pipeline_stages=["coding_llm"]
            )

        # 3. SQL Queries & Database Schema
        if re.search(r'\b(?:SELECT\s+.*?\s+FROM|INSERT\s+INTO|UPDATE\s+.*?\s+SET|DELETE\s+FROM|CREATE\s+TABLE|ALTER\s+TABLE)\b', text, re.IGNORECASE):
            return ModelRoutingDecision(
                capability="coding",
                model="qwen2.5-coder-3b",
                task="sql_analysis",
                confidence=0.97,
                reason="SQL query structure detected in message",
                is_combined_pipeline=False,
                pipeline_stages=["coding_llm"]
            )

        # 4. Code Blocks, Snippets, or Syntax Constructs (PHP, Python, JS, TS, React, HTML, CSS, SQL)
        is_code_syntax = (
            "```" in text or
            bool(re.search(r'(?:def\s+[a-zA-Z_]\w*\s*\(|function\s+[a-zA-Z_]\w*\s*\(|class\s+[A-Z]\w*[\s:]|const\s+\w+\s*=|const\s+\[|let\s+\w+|var\s+\w+)', text)) or
            bool(re.search(r'(?:<\?php|\$\w+\s*=|->\w+\(|=>|console\.log|var_dump|public\s+function|echo\s+["\']|import\s+.*?from|export\s+(?:default|const|function)|<\w+.*?>.*?</\w+>)', text)) or
            bool(re.search(r'(?:foreach\s*\(|for\s*\(|while\s*\(|return\s+\$\w+|;\s*\n|\bCI_Controller\b|\bCI_Model\b)', text))
        )
        if is_code_syntax:
            has_debug_kw = any(k in lower for k in ["error", "bug", "fix", "why", "issue", "vulnerabilit", "flaw", "problem"])
            return ModelRoutingDecision(
                capability="coding",
                model="qwen2.5-coder-3b",
                task="coding_debug" if has_debug_kw else "code_explanation",
                confidence=0.96,
                reason="Syntactic code definition (PHP/Python/JS/React/TS construct or code fence) detected",
                is_combined_pipeline=False,
                pipeline_stages=["coding_llm"]
            )

        # 5. Git & Version Control Issues
        if any(k in lower for k in ["merge conflict", "git rebase", "git checkout", "git cherry-pick", "git push rejected", "detached head"]):
            return ModelRoutingDecision(
                capability="coding",
                model="qwen2.5-coder-3b",
                task="dependency_analysis",
                confidence=0.95,
                reason="Git version control troubleshooting request",
                is_combined_pipeline=False,
                pipeline_stages=["coding_llm"]
            )

        return None

    # ----------------------------------------------------------------------
    # Stage 5: Conversation Context Continuity
    # ----------------------------------------------------------------------

    def _route_by_conversation_context(
        self,
        query: str,
        lower: str,
        context_state: Optional[Any],
        history: Optional[List[Dict[str, Any]]]
    ) -> Optional[ModelRoutingDecision]:
        last_intent = getattr(context_state, "last_intent", "") or ""
        last_topic = getattr(context_state, "last_topic", "") or ""

        # Follow-up in coding context (e.g. "where exactly?", "show me the fix", "can you rewrite it?")
        if "coding" in last_intent or "code" in last_topic or "debug" in last_intent:
            if any(k in lower for k in [
                "where exactly", "show me", "corrected function", "give me the fix",
                "rewrite", "change that", "how to use it", "what about the query",
                "explain more", "give the function", "the controller"
            ]):
                return ModelRoutingDecision(
                    capability="coding",
                    model="qwen2.5-coder-3b",
                    task="code_refactoring" if "rewrite" in lower or "corrected" in lower else "code_explanation",
                    confidence=0.94,
                    reason="Conversation context continuity in established coding thread",
                    is_combined_pipeline=False,
                    pipeline_stages=["coding_llm"]
                )

        # Follow-up in vision context (e.g. "what else is on that screen?", "zoom into the header")
        if "vision" in last_intent or "image" in last_topic:
            if any(k in lower for k in ["that screen", "in the image", "the header", "the button", "what else is there"]):
                return ModelRoutingDecision(
                    capability="vision",
                    model="qwen2-vl-2b",
                    task="image_understanding",
                    confidence=0.93,
                    reason="Conversation context continuity in visual inspection thread",
                    is_combined_pipeline=False,
                    pipeline_stages=["vision_llm"]
                )

        return None

    # ----------------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------------

    def _is_image_attachment(self, att: Dict[str, Any]) -> bool:
        fname = (att.get("filename") or att.get("name") or "").lower()
        ext = os.path.splitext(fname)[1].lower()
        mime = (att.get("mime_type") or "").lower()
        return ext in IMAGE_EXTENSIONS or mime.startswith("image/")

    def _classify_coding_task(self, text: str, lower: str) -> str:
        if "stack trace" in lower or "traceback" in lower:
            return "stack_trace_analysis"
        if "500 error" in lower or "api" in lower or "endpoint" in lower:
            return "api_debugging"
        if "sql" in lower or "select " in lower or "insert into " in lower or "update " in lower:
            return "sql_analysis"
        if "review" in lower:
            return "code_review"
        if "refactor" in lower or "clean up" in lower or "restructure" in lower:
            return "code_refactoring"
        if "compare" in lower or "difference between" in lower:
            return "code_comparison"
        if "architecture" in lower or "design pattern" in lower or "system design" in lower:
            return "architecture_analysis"
        if "dependency" in lower or "npm" in lower or "composer" in lower or "pip" in lower or "package" in lower:
            return "dependency_analysis"
        if "analyze" in lower or "analysis" in lower:
            return "code_analysis"
        if "fix" in lower or "error" in lower or "bug" in lower or "issue" in lower or "vulnerabilit" in lower or "flaw" in lower or "security" in lower:
            return "coding_debug"
        if any(k in lower for k in [
            "generate", "write", "create", "give me", "i need", "need a", "build",
            "implement", "make a", "provide a", "function for", "function to",
            "method to", "method for", "controller to", "controller for",
            "registration", "add user", "insert user", "adding user", "adding users",
            "to add a", "to insert a"
        ]):
            return "code_generation"
        if "explain" in lower or "understand" in lower or "what does this do" in lower:
            return "code_explanation"
        return "code_generation" if any(k in lower for k in ["controller", "function", "method", "class", "endpoint", "component", "script"]) else "coding_debug"


# Global singleton router instance
model_router = ModelRouter()

