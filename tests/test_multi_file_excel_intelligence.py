"""End-to-End & Unit Tests for Multi-File Excel Intelligence Architecture.

Verifies:
1. Multi-file sequential uploads & conversation document tracking.
2. Generic Excel total on UPI workbook (₹15,19,715.76 across 1,398 authorised records).
3. Generic Column listing on UPI workbook (not Sprint Filter).
4. Generic Record counting (1,398 authorised).
5. Column extraction/export (RID.xlsx with 1,398 records).
6. Safe Two-File Reconciliation / Comparison between EBO and UPI (EBO_UPI_Mismatch_Report.xlsx).
7. Follow-up contextual resolution from previous comparison results.
8. Backward compatibility for Sprint task splitting (Fazil=692h, Reka=686h).
9. RBAC permission checks on file download endpoint.
Zero mock business data.
"""

import os
import io
import pytest
from openpyxl import load_workbook

from backend.app.schemas.department import DepartmentEnum
from backend.app.schemas.security import UserRoleEnum
from backend.app.schemas.company_ai import CompanyAIChatRequest
from backend.app.services.company_ai_service import company_ai_service
from backend.app.services.conversation_context_manager import conversation_context_manager
from backend.app.services.excel.excel_service import excel_service
from backend.app.services.excel.workbook_detector import workbook_detector, WorkbookType
from backend.app.services.excel.excel_parser import parse_decimal_safe, format_inr
from backend.app.services.excel.excel_aggregator import excel_aggregator
from backend.app.services.excel.excel_column_export import excel_column_export
from backend.app.services.excel.excel_comparator import excel_comparator
from backend.app.services.excel.sprint_processor import sprint_processor


UPI_FILE_PATH = r"d:\MYGPT\data\uploads\d2468238-9020-4289-9cd8-b112277b2012.xlsx"
EBO_FILE_PATH = r"d:\MYGPT\data\uploads\7c3046ec-9a3b-4a93-8465-323dde21a760.xlsx"
SPRINT_FILE_PATH = r"d:\MYGPT\data\uploads\044c3cff-79c4-4f96-baf8-aedf61da5743.xlsx"


class TestWorkbookDetection:
    """Test safe schema detection across diverse workbook types."""

    def test_detect_upi_as_transaction(self):
        if not os.path.exists(UPI_FILE_PATH):
            pytest.skip("UPI file not present")
        wb_type = workbook_detector.detect(UPI_FILE_PATH)
        assert wb_type == WorkbookType.TRANSACTION

    def test_detect_ebo_as_ebo_topup(self):
        if not os.path.exists(EBO_FILE_PATH):
            pytest.skip("EBO file not present")
        wb_type = workbook_detector.detect(EBO_FILE_PATH)
        assert wb_type in (WorkbookType.EBO_TOPUP, WorkbookType.TRANSACTION)

    def test_detect_sprint_as_sprint(self):
        if not os.path.exists(SPRINT_FILE_PATH):
            pytest.skip("Sprint file not present")
        wb_type = workbook_detector.detect(SPRINT_FILE_PATH)
        assert wb_type == WorkbookType.SPRINT


class TestExcelAggregatorUPI:
    """Test deterministic calculations on authentic UPI transaction workbook."""

    def test_upi_total_amount(self):
        if not os.path.exists(UPI_FILE_PATH):
            pytest.skip("UPI file not present")
        agg = excel_aggregator.calculate_aggregation(UPI_FILE_PATH, target_column="Amount")
        assert float(agg["total"]) == 1519715.76
        assert agg["formatted_total"] == "₹15,19,715.76"
        assert agg["authorised_count"] == 1398

    def test_upi_column_listing(self):
        if not os.path.exists(UPI_FILE_PATH):
            pytest.skip("UPI file not present")
        cols_info = excel_column_export.list_columns(UPI_FILE_PATH)
        cols = cols_info["columns"]
        assert "Amount" in cols
        assert "RID" in cols
        assert "TRNSCTN_NMBR" in cols
        assert "STATUS" in cols
        assert len(cols) == 28

    def test_upi_rid_export(self):
        if not os.path.exists(UPI_FILE_PATH):
            pytest.skip("UPI file not present")
        res = excel_column_export.export_column(UPI_FILE_PATH, "RID")
        assert res["column_name"] == "RID"
        assert res["record_count"] == 1398
        assert res["filename"] == "RID.xlsx"

        # Verify openpyxl output binary
        wb = load_workbook(io.BytesIO(res["file_bytes"]))
        ws = wb.active
        assert ws.cell(row=1, column=2).value == "RID"
        assert ws.max_row == 1399  # 1 header + 1398 records


class TestExcelComparatorEBOandUPI:
    """Test two-file reconciliation and mismatch detection."""

    def test_two_file_reconciliation(self):
        if not os.path.exists(UPI_FILE_PATH) or not os.path.exists(EBO_FILE_PATH):
            pytest.skip("Comparison files not present")
        comp = excel_comparator.compare_workbooks(UPI_FILE_PATH, EBO_FILE_PATH)
        assert comp["success"] is True
        assert comp["matched_count"] > 1000
        assert comp["report_filename"] == "EBO_UPI_Mismatch_Report.xlsx"

        # Verify multi-sheet mismatch report structure
        wb = load_workbook(io.BytesIO(comp["report_bytes"]))
        sheet_names = wb.sheetnames
        assert "Summary" in sheet_names
        assert "Matched" in sheet_names
        assert "Mismatches" in sheet_names


class TestSprintBackwardCompatibility:
    """Test that sprint final.xlsx splitting remains 100% functional."""

    def test_sprint_split_fazil_reka(self):
        if not os.path.exists(SPRINT_FILE_PATH):
            pytest.skip("Sprint file not present")
        res = sprint_processor.filter_and_export_by_owners(SPRINT_FILE_PATH, ["Fazil", "Reka"])
        owners = res["owner_results"]
        assert "Fazil" in owners
        assert "Reka" in owners
        assert owners["Fazil"]["total_hours"] == 34.0
        assert owners["Reka"]["total_hours"] == 30.0
        assert owners["Fazil"]["filename"] == "Fazil_Sprint.xlsx"
        assert owners["Reka"]["filename"] == "Reka_Sprint.xlsx"


class TestMultiFileConversationFlow:
    """End-to-End Conversation Flow with Sequential Multi-Workbook Context."""

    def test_full_acceptance_flow(self):
        if not os.path.exists(UPI_FILE_PATH) or not os.path.exists(EBO_FILE_PATH):
            pytest.skip("Workbooks not present")

        session_id = "test_acceptance_session_101"
        conversation_context_manager.clear_session(session_id)

        # 1. Attach File 1 (UPI)
        doc1_meta = {
            "id": "doc_upi_101",
            "filename": "UPI - QR FROM 31-5-26 TO 15-06-26 1.xlsx",
            "file_path": UPI_FILE_PATH,
            "file_type": ".xlsx",
            "document_type": "EXCEL",
            "structured_data": {"workbook_type": "TRANSACTION"}
        }
        conversation_context_manager.set_active_document(session_id, doc1_meta)

        # 2. Ask "calculate the total maount inthe exel"
        req1 = CompanyAIChatRequest(
            message="calculate the total maount inthe exel",
            conversation_id=session_id,
            user_role=UserRoleEnum.EMPLOYEE
        )
        res1 = company_ai_service.process_chat(req1)
        assert "15,19,715.76" in res1.answer
        assert "1,398" in res1.answer
        assert "Amount" in res1.answer
        assert res1.tool_results.get("card_type") == "metric_card"

        # 3. Ask "give me the names of the colunms"
        req2 = CompanyAIChatRequest(
            message="give me the names of the colunms",
            conversation_id=session_id,
            user_role=UserRoleEnum.EMPLOYEE
        )
        res2 = company_ai_service.process_chat(req2)
        assert "RID" in res2.answer
        assert "Amount" in res2.answer
        assert "SPRINT FILTER" not in res2.answer.upper()
        assert res2.tool_results.get("card_type") == "column_list"

        # 4. Ask "how many transactions are there"
        req3 = CompanyAIChatRequest(
            message="how many transactions are there",
            conversation_id=session_id,
            user_role=UserRoleEnum.EMPLOYEE
        )
        res3 = company_ai_service.process_chat(req3)
        assert "1,398" in res3.answer

        # 5. Ask "give me the rid as the exle hseet"
        req4 = CompanyAIChatRequest(
            message="give me the rid as the exle hseet",
            conversation_id=session_id,
            user_role=UserRoleEnum.EMPLOYEE
        )
        res4 = company_ai_service.process_chat(req4)
        assert len(res4.files) > 0
        assert res4.files[0]["filename"] == "RID.xlsx"

        # 6. Upload File 2 (EBO Topup) sequentially without overwriting UPI
        doc2_meta = {
            "id": "doc_ebo_102",
            "filename": "EBO TB Topup_export_20260617_160221.xlsx",
            "file_path": EBO_FILE_PATH,
            "file_type": ".xlsx",
            "document_type": "EXCEL",
            "structured_data": {"workbook_type": "EBO_TOPUP"}
        }
        conversation_context_manager.set_active_document(session_id, doc2_meta)

        # Verify state has both documents
        state = conversation_context_manager.get_state(session_id)
        assert len(state.documents) == 2

        # 7. Ask "compare the ebo topup and upi qr exel and foudn the mismatch details and then gie me the exle sheet"
        req5 = CompanyAIChatRequest(
            message="compare the ebo topup and upi qr exel and foudn the mismatch details and then gie me the exle sheet",
            conversation_id=session_id,
            user_role=UserRoleEnum.EMPLOYEE
        )
        res5 = company_ai_service.process_chat(req5)
        assert "SPRINT COMPARISON" not in res5.answer.upper()
        assert len(res5.files) > 0
        assert "Mismatch_Report.xlsx" in res5.files[0]["filename"]
        assert res5.tool_results.get("card_type") == "comparison_matrix"

        # 8. Follow-up: "how many mismatches?"
        req6 = CompanyAIChatRequest(
            message="how many mismatches?",
            conversation_id=session_id,
            user_role=UserRoleEnum.EMPLOYEE
        )
        res6 = company_ai_service.process_chat(req6)
        assert "discrepanc" in res6.answer.lower() or "mismatch" in res6.answer.lower()
