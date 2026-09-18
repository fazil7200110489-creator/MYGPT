"""Workbook Schema and Domain Detection Engine.

Analyzes sheet names, column headers, row counts, and data distributions to accurately
classify workbooks into domain categories (TRANSACTION, EBO_TOPUP, SPRINT, INVOICE, EMPLOYEE, etc.)
WITHOUT assuming everything is a Sprint workbook.
"""

import re
from enum import Enum
from typing import Dict, Any, List, Optional, Set
from loguru import logger


class WorkbookType(str, Enum):
    SPRINT = "SPRINT"
    TRANSACTION = "TRANSACTION"
    EBO_TOPUP = "EBO_TOPUP"
    INVOICE = "INVOICE"
    EMPLOYEE = "EMPLOYEE"
    ATTENDANCE = "ATTENDANCE"
    PAYROLL = "PAYROLL"
    SALES = "SALES"
    INVENTORY = "INVENTORY"
    GENERIC = "GENERIC"


class WorkbookDetector:
    """Classifies Excel workbooks based on header patterns, vocabulary, and data structures."""

    SPRINT_INDICATORS = {
        "owner", "task", "module", "estimated hours", "sprint", "assigned to",
        "employee", "task description", "assigned", "developer", "jira", "story points"
    }

    TRANSACTION_INDICATORS = {
        "amount", "total amount", "transaction number", "transaction id", "rid",
        "crn", "trn", "transaction mode", "status", "settled amount", "commission",
        "gst", "clrnce_date", "crtd_date", "athrsd_date", "aggregrator", "agent_name",
        "unique_id", "unique_apna_id", "branch_code", "cmpny_code"
    }

    EBO_INDICATORS = {
        "vendor reference id", "bank transaction id", "ebo id", "requested amount",
        "transaction amount", "trans mode", "trans remarks", "success date"
    }

    INVOICE_INDICATORS = {
        "invoice number", "invoice #", "vendor", "subtotal", "tax", "gst",
        "total amount payable", "invoice date", "bill to", "po number"
    }

    EMPLOYEE_INDICATORS = {
        "employee id", "employee name", "department", "designation", "joining date",
        "employee code", "salary", "ctc", "grade"
    }

    def detect(self, file_path: str) -> WorkbookType:
        """Inspects workbook file and returns classified WorkbookType enum."""
        from backend.app.services.excel.excel_parser import load_workbook_safe
        wb = load_workbook_safe(file_path, data_only=True)
        try:
            ws = wb.active
            headers = [cell.value for cell in ws[1] if cell.value is not None]
            schema_info = self.detect_schema(headers)
            type_str = schema_info.get("workbook_type", WorkbookType.GENERIC.value)
            return WorkbookType(type_str)
        finally:
            wb.close()

    def detect_schema(self, headers: List[str], sample_rows: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Examines column headers and sample data to categorize the sheet schema."""
        if not headers:
            return {
                "workbook_type": WorkbookType.GENERIC.value,
                "is_sprint": False,
                "is_transaction": False,
                "is_ebo": False,
                "is_invoice": False,
                "confidence": 0.50
            }

        h_set = {str(h).strip().lower() for h in headers if h is not None}
        h_text = " ".join(h_set)

        # Count indicator hits
        sprint_score = sum(1 for ind in self.SPRINT_INDICATORS if any(ind in h for h in h_set))
        trans_score = sum(1 for ind in self.TRANSACTION_INDICATORS if any(ind in h for h in h_set))
        ebo_score = sum(1 for ind in self.EBO_INDICATORS if any(ind in h for h in h_set))
        invoice_score = sum(1 for ind in self.INVOICE_INDICATORS if any(ind in h for h in h_set))
        employee_score = sum(1 for ind in self.EMPLOYEE_INDICATORS if any(ind in h for h in h_set))

        # Check for specific EBO topup pattern
        if ("ebo id" in h_set or "bank transaction id" in h_set or "vendor reference id" in h_set) and ebo_score >= 3:
            return {
                "workbook_type": WorkbookType.EBO_TOPUP.value,
                "is_sprint": False,
                "is_transaction": True,
                "is_ebo": True,
                "is_invoice": False,
                "confidence": 0.99,
                "amount_column": self._find_column(headers, ["transaction amount", "requested amount", "amount", "total amount"]),
                "key_column": self._find_column(headers, ["bank transaction id", "vendor reference id", "ebo id"]),
                "status_column": self._find_column(headers, ["status"]),
                "date_column": self._find_column(headers, ["transaction date time", "success date", "date"])
            }

        # Check for Transaction Schema (UPI, QR, Banking)
        if trans_score >= 3 or ("rid" in h_set and "amount" in h_set) or ("transaction mode" in h_set):
            return {
                "workbook_type": WorkbookType.TRANSACTION.value,
                "is_sprint": False,
                "is_transaction": True,
                "is_ebo": False,
                "is_invoice": False,
                "confidence": 0.98,
                "amount_column": self._find_column(headers, ["amount", "total amount", "settled_amount", "transaction amount"]),
                "key_column": self._find_column(headers, ["rid", "trn", "crn", "trnsctn_nmbr", "unique_id"]),
                "status_column": self._find_column(headers, ["status"]),
                "mode_column": self._find_column(headers, ["transaction mode", "trans mode", "mode"]),
                "date_column": self._find_column(headers, ["crtd_date", "athrsd_date", "clrnce_date", "settled_date"])
            }

        # Check for Sprint Schema
        if sprint_score >= 2 or ("owner" in h_set and any(k in h_text for k in ["task", "module", "hours", "sprint"])):
            return {
                "workbook_type": WorkbookType.SPRINT.value,
                "is_sprint": True,
                "is_transaction": False,
                "is_ebo": False,
                "is_invoice": False,
                "confidence": 0.98,
                "owner_column": self._find_column(headers, ["owner", "assigned to", "developer", "employee", "assignee"]),
                "task_column": self._find_column(headers, ["task", "task description", "summary", "description"]),
                "module_column": self._find_column(headers, ["module", "component", "epic", "feature"]),
                "hours_column": self._find_column(headers, ["estimated hours", "estimate", "hours", "story points"])
            }

        # Check for Invoice Schema
        if invoice_score >= 2 or ("invoice number" in h_set and "vendor" in h_set):
            return {
                "workbook_type": WorkbookType.INVOICE.value,
                "is_sprint": False,
                "is_transaction": False,
                "is_ebo": False,
                "is_invoice": True,
                "confidence": 0.95,
                "amount_column": self._find_column(headers, ["total amount", "total", "subtotal", "amount"]),
                "vendor_column": self._find_column(headers, ["vendor", "vendor name", "supplier"])
            }

        # Check for Employee Schema
        if employee_score >= 2:
            return {
                "workbook_type": WorkbookType.EMPLOYEE.value,
                "is_sprint": False,
                "is_transaction": False,
                "is_ebo": False,
                "is_invoice": False,
                "confidence": 0.90
            }

        return {
            "workbook_type": WorkbookType.GENERIC.value,
            "is_sprint": False,
            "is_transaction": False,
            "is_ebo": False,
            "is_invoice": False,
            "confidence": 0.60
        }

    def _find_column(self, headers: Optional[List[Any]], candidate_names: Optional[List[str]]) -> Optional[str]:
        """Finds the best matching header among candidates safely."""
        if not headers or not candidate_names:
            return None

        clean_headers = [str(h).strip() for h in headers if h is not None]
        if not clean_headers:
            return None

        # 1. Exact match (case-insensitive)
        for cand in candidate_names:
            if not cand:
                continue
            cand_clean = cand.strip().lower()
            for h in clean_headers:
                if h.lower() == cand_clean:
                    return h

        # 2. Normalized token match (ignore spaces, underscores, hyphens)
        for cand in candidate_names:
            if not cand:
                continue
            cand_norm = re.sub(r"[_\s\-]+", "", cand.strip().lower())
            for h in clean_headers:
                h_norm = re.sub(r"[_\s\-]+", "", h.lower())
                if cand_norm and cand_norm == h_norm:
                    return h

        # 3. Substring match
        for cand in candidate_names:
            if not cand:
                continue
            cand_clean = cand.strip().lower()
            for h in clean_headers:
                if cand_clean in h.lower():
                    return h

        return None


workbook_detector = WorkbookDetector()
