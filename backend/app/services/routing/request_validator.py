"""Request Validation Layer for Enterprise Company AI.

Stage between Qwen Layer 1 Semantic Understanding (or Fast-Path Router) and MYGPT Execution.
Validates StructuredRequest against conversation context, document availability,
RBAC prerequisites, and entity completeness.

If validation fails or request is ambiguous, produces a precise clarification question.
NEVER silently converts invalid or unrecognized requests to GENERAL.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from loguru import logger

from backend.app.schemas.department import DepartmentEnum
from backend.app.schemas.company_ai import StructuredRequest, ConversationState


class ValidationResult(BaseModel):
    """Result returned by RequestValidator."""
    is_valid: bool = Field(default=True, description="Whether the request is valid for execution")
    needs_clarification: bool = Field(default=False, description="Whether the user must be asked a clarification question")
    clarification_message: Optional[str] = Field(default=None, description="Precise clarification question for user")
    failure_reason: Optional[str] = Field(default=None, description="Diagnostic reason for validation failure")
    normalized_capability: str = Field(default="GENERAL", description="Normalized capability domain")
    normalized_department: DepartmentEnum = Field(default=DepartmentEnum.GENERAL)
    normalized_intent: str = Field(default="unknown")
    normalized_operation: Optional[str] = Field(default=None)
    sanitized_entities: Dict[str, Any] = Field(default_factory=dict)


class RequestValidator:
    """Enterprise Request Validator ensuring safe, authorized, and unambiguous execution."""

    VALID_DEPARTMENTS = {DepartmentEnum.HR, DepartmentEnum.FINANCE, DepartmentEnum.TECH, DepartmentEnum.GENERAL}

    VALID_OPERATIONS = {
        "SUMMARY", "DOCUMENT_SUMMARY", "DOCUMENT_QUERY", "DOCUMENT_QA", "EXTRACT_INFORMATION",
        "DOCUMENT_TRANSFORMATION", "FLOWCHART", "WORKFLOW",
        "TOTAL", "COUNT", "AVERAGE", "MIN", "MAX", "FILTER", "SORT",
        "GROUP", "UNIQUE_VALUES", "COLUMN_LIST", "COLUMN_EXPORT", "FULL_EXPORT",
        "EXPORT_RESULT", "COMPARISON", "MULTI_DOCUMENT_COMPARISON", "MULTI_DOCUMENT_SUMMARY",
        "REPORT", "SPLIT", "READ_COLUMN", "FILTER_EXPORT", "FILTER_COLUMN", "GROUP_MAX", "GROUP_MIN",
        "CODE_GENERATION", "CODE_EXPLANATION", "CODE_DEBUG", "CODE_REVIEW"
    }

    VALID_CODING_OPERATIONS = {"CODE_GENERATION", "CODE_EXPLANATION", "CODE_DEBUG", "CODE_REVIEW"}

    def validate(
        self,
        req: StructuredRequest,
        raw_message: str,
        context_state: Optional[ConversationState] = None
    ) -> ValidationResult:
        """Validates a StructuredRequest before MYGPT Core execution.

        Returns ValidationResult with is_valid=True or is_valid=False + clarification_message.
        """
        # 1. Department Validation
        dept_str = (req.department or "").strip().upper()
        try:
            dept_enum = DepartmentEnum(dept_str)
        except ValueError:
            dept_enum = DepartmentEnum.GENERAL

        intent = (req.intent or "unknown").strip().lower()
        operation = (req.operation or "").strip().upper() if req.operation else None
        entities = dict(req.entities or {})
        confidence = float(req.confidence or 0.0)

        # 2. Check standalone general-purpose question (world facts, science, coding concepts)
        if intent == "general_question":
            return ValidationResult(
                is_valid=True,
                needs_clarification=False,
                normalized_department=DepartmentEnum.GENERAL,
                normalized_intent="general_question",
                normalized_operation="ANSWER",
                sanitized_entities=entities
            )

        # 3. Check for completely unrecognized / empty / unknown intent
        if intent in ("unknown", "unrecognized", "") and not operation:
            # Check if this is a genuine continuation of an ongoing task / topic / workflow
            if context_state and (getattr(req, "is_follow_up", False) or getattr(context_state, "conversation_mode", None) == "continuation"):
                logger.info(f"[VALIDATION] Request intent is empty/unknown but continuing active task context: '{raw_message}'")
                return ValidationResult(
                    is_valid=True,
                    needs_clarification=False,
                    normalized_department=DepartmentEnum(context_state.department) if context_state.department else dept_enum,
                    normalized_intent=context_state.last_intent or "task_continuation",
                    normalized_operation=operation or "CONTINUE",
                    sanitized_entities=entities
                )

            # Check if this is an underspecified request (e.g. "give me the thing from yesterday")
            logger.info(f"[VALIDATION] Request intent is unknown (conf={confidence:.2f}): '{raw_message}'")
            return ValidationResult(
                is_valid=False,
                needs_clarification=True,
                clarification_message=self._build_general_clarification(raw_message, context_state),
                failure_reason="intent_unknown",
                normalized_department=dept_enum,
                normalized_intent="clarification_needed"
            )

        # 4. Check for low confidence ambiguity
        if confidence < 0.40 and intent not in ("greeting", "department_declaration", "general_question"):
            if context_state and (getattr(req, "is_follow_up", False) or getattr(context_state, "conversation_mode", None) == "continuation"):
                logger.info(f"[VALIDATION] Low confidence ({confidence:.2f}) but preserved by active task continuation: '{raw_message}'")
                return ValidationResult(
                    is_valid=True,
                    needs_clarification=False,
                    normalized_department=DepartmentEnum(context_state.department) if context_state.department else dept_enum,
                    normalized_intent=context_state.last_intent or "task_continuation",
                    normalized_operation=operation or "CONTINUE",
                    sanitized_entities=entities
                )
            logger.info(f"[VALIDATION] Request confidence too low ({confidence:.2f}): '{raw_message}'")
            return ValidationResult(
                is_valid=False,
                needs_clarification=True,
                clarification_message=self._build_general_clarification(raw_message, context_state),
                failure_reason="low_confidence",
                normalized_department=dept_enum,
                normalized_intent="clarification_needed"
            )

        # 4. Multi-Document Operations Validation
        if operation in ("COMPARISON", "MULTI_DOCUMENT_COMPARISON", "MULTI_DOCUMENT_SUMMARY") or intent in ("file_comparison", "excel_comparison"):
            active_docs_count = len(context_state.active_document_ids) if (context_state and context_state.active_document_ids) else 0
            if not active_docs_count and context_state and context_state.active_document_id:
                active_docs_count = 1
            if context_state and context_state.previous_document:
                active_docs_count += 1
            source_docs = req.source_documents or []
            total_available_docs = max(active_docs_count, len(source_docs))

            if total_available_docs < 2:
                logger.info(f"[VALIDATION] Multi-document comparison requested but only {total_available_docs} document(s) available")
                return ValidationResult(
                    is_valid=False,
                    needs_clarification=True,
                    clarification_message="Document comparison requires two uploaded files. Please attach or upload the second file to compare.",
                    failure_reason="insufficient_documents_for_comparison",
                    normalized_department=dept_enum,
                    normalized_intent=intent,
                    normalized_operation=operation
                )

        # 5. Follow-up / Previous Result Reference Validation
        if req.is_follow_up or req.source == "PREVIOUS_RESULT" or operation == "EXPORT_RESULT":
            has_prev_result = bool(
                context_state and (
                    context_state.last_exportable_result or
                    context_state.last_excel_result or
                    context_state.last_exportable_rows or
                    context_state.last_verified_result
                )
            )
            if not has_prev_result and operation == "EXPORT_RESULT":
                logger.info("[VALIDATION] Export previous result requested but no exportable previous result found in session")
                return ValidationResult(
                    is_valid=False,
                    needs_clarification=True,
                    clarification_message="There is no recent query result or active dataset to export. What specific data would you like me to find and export for you?",
                    failure_reason="no_previous_result_to_export",
                    normalized_department=dept_enum,
                    normalized_intent=intent,
                    normalized_operation=operation
                )

        # 6. Active Document Requirement Validation for Excel / Document specific intents
        if intent.startswith("excel_") or (operation in self.VALID_OPERATIONS and operation not in self.VALID_CODING_OPERATIONS):
            if operation not in ("COMPARISON", "MULTI_DOCUMENT_COMPARISON", "MULTI_DOCUMENT_SUMMARY"):
                has_active_doc = bool(context_state and (context_state.active_document_id or context_state.active_document))
                is_task_cont = bool(context_state and (getattr(context_state, "task", None) or getattr(context_state, "project", None) or getattr(context_state, "conversation_mode", None) == "continuation"))
                if not has_active_doc and not req.is_follow_up and not is_task_cont and intent not in ("expense_calculation",):
                    # Check if document is attached or available
                    logger.info(f"[VALIDATION] Excel/Document operation '{operation or intent}' requested but no active document in context")
                    return ValidationResult(
                        is_valid=False,
                        needs_clarification=True,
                        clarification_message="Please upload or specify the document or spreadsheet you would like me to analyze.",
                        failure_reason="missing_active_document",
                        normalized_department=dept_enum,
                        normalized_intent=intent,
                        normalized_operation=operation
                    )

        # 7. Candidate / HR Document Validation
        if dept_enum == DepartmentEnum.HR and intent in ("candidate_experience", "candidate_skills", "candidate_education", "candidate_summary", "candidate_profile"):
            has_resume = bool(
                context_state and (
                    (context_state.active_document_type == "RESUME") or
                    (context_state.active_document and "resume" in str(context_state.active_document.get("filename", "")).lower()) or
                    context_state.active_document_id
                )
            )
            # If no resume attached and no candidate name in entities, verify
            if not has_resume and not entities.get("candidate_name"):
                logger.info("[VALIDATION] HR candidate query without attached resume or specified candidate name")
                return ValidationResult(
                    is_valid=False,
                    needs_clarification=True,
                    clarification_message="Please upload the candidate's resume or provide the candidate name to retrieve their details.",
                    failure_reason="missing_candidate_resume",
                    normalized_department=dept_enum,
                    normalized_intent=intent
                )

        cap = getattr(req, "capability", "GENERAL") or "GENERAL"

        # 8. Coding Request Validation: Only ask for clarification when essential information is genuinely missing or ambiguous
        if (cap == "CODING" or dept_enum == DepartmentEnum.TECH) and (intent == "code_generation" or operation == "CODE_GENERATION"):
            raw_lower = raw_message.lower()
            has_framework_or_lang = any(k in raw_lower for k in [
                "codeigniter", "ci3", "ci4", "laravel", "symfony", "php", "python",
                "react", "vue", "angular", "node", "express", "fastapi", "flask",
                "django", "sql", "javascript", "typescript", "c#", "c++", "java", "html", "css"
            ])
            has_component_or_task = any(k in raw_lower for k in [
                "controller", "function", "method", "class", "endpoint", "api",
                "component", "query", "script", "model", "user", "login", "register",
                "auth", "add", "insert", "crud"
            ])
            if not has_framework_or_lang and not has_component_or_task and len(raw_lower.split()) < 3:
                return ValidationResult(
                    is_valid=False,
                    needs_clarification=True,
                    clarification_message="What programming language or framework would you like me to use, and what should the code do?",
                    failure_reason="ambiguous_coding_request",
                    normalized_capability="CODING",
                    normalized_department=dept_enum,
                    normalized_intent=intent,
                    normalized_operation=operation
                )

        # All validation checks passed
        logger.info(f"[VALIDATION] status=VALIDATED cap={cap} dept={dept_enum.value} intent={intent} op={operation}")
        return ValidationResult(
            is_valid=True,
            needs_clarification=False,
            clarification_message=None,
            failure_reason=None,
            normalized_capability=cap,
            normalized_department=dept_enum,
            normalized_intent=intent,
            normalized_operation=operation,
            sanitized_entities=entities
        )

    def _build_general_clarification(self, raw_message: str, context_state: Optional[ConversationState] = None) -> str:
        """Constructs an intelligent, courteous clarification question based on user input."""
        msg_lower = raw_message.lower().strip()

        has_task_context = bool(context_state and (
            getattr(context_state, "task", None) or
            getattr(context_state, "project", None) or
            getattr(context_state, "workflow", None) or
            getattr(context_state, "current_module", None) or
            getattr(context_state, "current_stage", None) or
            context_state.last_topic or
            getattr(context_state, "conversation_mode", None) == "continuation"
        ))

        is_code_or_project_file = any(phrase in msg_lower for phrase in [
            "give me the file", "give me the files", "give files", "files one by one",
            "project files", "code files", "step by step", "next file", "previous file",
            "create file", "generate file", "one by one", "the files", "files"
        ])

        if "yesterday" in msg_lower or "previous" in msg_lower or "earlier" in msg_lower:
            return "What specific document, report, or information would you like me to retrieve?"

        # Only enter document clarification if explicitly about uploaded documents and NOT code/project continuation
        if ("doc" in msg_lower or "sheet" in msg_lower or ("file" in msg_lower and not is_code_or_project_file and not has_task_context)):
            return "Which file or document would you like me to work with, and what would you like me to do?"

        if "compare" in msg_lower:
            return "Which two documents or datasets would you like me to compare?"
        if "calculate" in msg_lower or "sum" in msg_lower or "total" in msg_lower:
            return "What values or columns would you like me to calculate?"
        return "Could you please provide more details or clarify what specific information or task you need assistance with?"


# Global singleton instance
request_validator = RequestValidator()
