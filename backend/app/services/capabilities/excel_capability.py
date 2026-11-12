"""Excel and Tabular Data Analysis Capability.

The uploaded spreadsheet/CSV file is the DATA SOURCE.
The user's QUESTION determines the analytical operation:
- "How many differences are there?" -> COMPARISON
- "What is the total amount?" -> CALCULATION
- "Summarize this Excel" -> OVERVIEW
- "Filter records" -> FILTER
- "Export mismatches" -> EXPORT
"""

import re
from typing import Dict, Any, List, Optional
from loguru import logger

from backend.app.schemas.company_ai import StructuredRequest
from backend.app.schemas.capability import CapabilityResult, CapabilityEnum, TaskTypeEnum
from backend.app.services.capabilities.base_capability import BaseCapability
from backend.app.services.excel.excel_service import excel_service
from backend.app.services.excel.semantic_excel_resolver import semantic_excel_resolver
from backend.app.services.excel.excel_aggregator import excel_aggregator
from backend.app.services.document_manager import document_manager


class ExcelCapability(BaseCapability):
    """Spreadsheet, CSV, and Tabular Data Intelligence Specialist."""

    def __init__(self):
        super().__init__(CapabilityEnum.EXCEL_DATA.value)

    def can_handle(self, request: StructuredRequest, context: Optional[Any] = None) -> bool:
        cap = (request.capability or "").upper()
        if cap in ("EXCEL_DATA", "EXCEL"):
            return True
        if request.operation in ("EXCEL_COMPARISON", "EXCEL_CALCULATION", "EXCEL_FILTER", "EXCEL_OVERVIEW", "COMPARISON", "AGGREGATION"):
            return True
        if request.task_type in (
            TaskTypeEnum.EXCEL_COMPARISON.value,
            TaskTypeEnum.EXCEL_CALCULATION.value,
            TaskTypeEnum.EXCEL_FILTER.value,
            TaskTypeEnum.EXCEL_OVERVIEW.value
        ):
            return True

        # Check if active file is a spreadsheet
        active_doc = request.active_document or (context.active_document if context else None)
        if isinstance(active_doc, dict):
            ext = active_doc.get("extension", "").lower()
            if ext in (".xlsx", ".xls", ".csv", ".xlsm"):
                return True
        elif isinstance(active_doc, str) and any(active_doc.lower().endswith(ext) for ext in (".xlsx", ".xls", ".csv", ".xlsm")):
            return True

        return False

    def execute(self, request: StructuredRequest, context: Optional[Any] = None) -> CapabilityResult:
        query = (request.user_request or request.normalized_message or "").strip()
        logger.info(f"[EXCEL_CAPABILITY] Executing analytical query: {query!r}")

        # 1. Resolve active spreadsheet file
        file_path, active_name = self._resolve_file_path(request, context)
        if not file_path:
            return CapabilityResult(
                success=False,
                capability=self.capability_name,
                operation="NO_FILE",
                task_type=TaskTypeEnum.EXCEL_OVERVIEW.value,
                answer="No spreadsheet or CSV file is currently active. Please attach or upload an Excel file to analyze.",
                answer_type="error",
                confidence=1.0
            )

        # 2. Derive analytical operation strictly from user question
        op = self._resolve_operation(query, request)

        # 3. Extract actual headers and available sheets from workbook
        actual_headers: List[str] = []
        available_sheets: List[str] = []
        try:
            insp = excel_aggregator.inspect_workbook(file_path)
            actual_headers = insp.get("headers", [])
            available_sheets = insp.get("sheet_names", [])
        except Exception as e:
            logger.warning(f"[EXCEL_CAPABILITY] Workbook inspection warning: {e}")

        # 4. Prepare parameters and delegate to excel_service
        entities = dict(request.entities or {})
        entities["raw_query"] = query
        entities["message"] = query
        entities["operation"] = op

        # Resolve semantic schema for structured request
        resolved_schema = semantic_excel_resolver.resolve_schema_for_structured_request(
            request, actual_headers, available_sheets=available_sheets
        )
        entities.update(resolved_schema)

        # Context inheritance for follow-ups
        if context:
            if getattr(context, "last_excel_result", None):
                entities["last_excel_result"] = context.last_excel_result
            if getattr(context, "last_result", None):
                entities["last_result"] = context.last_result
            if getattr(context, "last_operation", None):
                entities["last_operation"] = context.last_operation

        try:
            excel_res = excel_service.process_excel_operation(
                intent=self._map_operation_to_intent(op),
                file_path=file_path,
                entities=entities
            )

            answer = excel_res.summary or "\n".join(str(f) for f in excel_res.findings)
            ans_type = "comparison" if op == "EXCEL_COMPARISON" else ("calculation" if op == "EXCEL_CALCULATION" else "text")

            return CapabilityResult(
                success=excel_res.success,
                capability=self.capability_name,
                operation=op,
                task_type=TaskTypeEnum.EXCEL_COMPARISON.value if op == "EXCEL_COMPARISON" else TaskTypeEnum.EXCEL_CALCULATION.value,
                answer=answer,
                answer_type=ans_type,
                structured_data=excel_res.internal_metadata.get("structured_data") or excel_res.tool_results,
                sources=[active_name] if active_name else [],
                files=excel_res.files,
                confidence=excel_res.confidence
            )
        except Exception as e:
            logger.error(f"[EXCEL_CAPABILITY] Execution error: {e}")
            return CapabilityResult(
                success=False,
                capability=self.capability_name,
                operation=op,
                task_type=TaskTypeEnum.EXCEL_OVERVIEW.value,
                answer=f"Spreadsheet analysis error: {str(e)}",
                answer_type="error",
                confidence=0.5
            )

    def _resolve_operation(self, query: str, request: Optional[StructuredRequest] = None) -> str:
        """User's question determines the analytical operation."""
        q_lower = query.lower()

        # Comparison / Difference
        if any(w in q_lower for w in ("difference", "differences", "compare", "comparison", "mismatch", "variance", "matched")):
            return "EXCEL_COMPARISON"

        # Calculation / Aggregation (use regex with word boundaries to avoid 'sum' matching in 'summarize')
        calc_patterns = [r"\btotal\b", r"\bsum\b", r"\baverage\b", r"\bavg\b", r"\bcount\b", r"\bmaximum\b", r"\bmax\b", r"\bminimum\b", r"\bmin\b", r"\bcalculate\b", r"\bcalculation\b"]
        if any(re.search(pat, q_lower) for pat in calc_patterns):
            return "EXCEL_CALCULATION"

        # Filtering
        if any(w in q_lower for w in ("filter", "where", "only", "show records where", "which records")):
            return "EXCEL_FILTER"

        # Overview / Metadata Summary
        return "EXCEL_OVERVIEW"

    def _map_operation_to_intent(self, op: str) -> str:
        mapping = {
            "EXCEL_COMPARISON": "excel_compare",
            "EXCEL_CALCULATION": "excel_total",
            "EXCEL_FILTER": "excel_filter",
            "EXCEL_OVERVIEW": "excel_summary"
        }
        return mapping.get(op, "excel_summary")

    def _resolve_file_path(self, request: StructuredRequest, context: Optional[Any]) -> tuple[Optional[str], Optional[str]]:
        """Resolves absolute file path and display filename."""
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
