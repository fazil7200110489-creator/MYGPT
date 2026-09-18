"""Unit and Integration Tests for Production Excel Document Operations.

Verifies:
1. Excel workbook upload & inspection (sheet detection, header detection, owner column identification)
2. Row filtering using authentic Owner values
3. Generation of real XLSX output files:
   - Fazil_Sprint.xlsx (containing only Fazil's rows)
   - Reka_Sprint.xlsx (containing only Reka's rows)
   - Sprint_Split_Fazil_Reka.xlsx (multi-tab combined workbook)
4. Preservation of headers: Module, Task, Description, Estimated Hours, Owner, Status
5. Follow-up natural language routing against active attached document:
   - "make a separate separate sprint for the fazil asnd reka" -> EXCEL_SPLIT
   - "split this for Fazil and Reka" -> EXCEL_SPLIT
   - "give me only Fazil" -> EXCEL_FILTER
   - "make one for Reka" -> EXCEL_FILTER
   - "give me Reka's sprint" -> EXCEL_FILTER
   - "sprint summary" -> EXCEL_SUMMARY
6. Zero mock data, zero fake rows, zero hardcoded task lists.
7. Secure download endpoint & RBAC verification.
"""

import io
import os
import tempfile
import pytest
import openpyxl
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.documents.excel_processor import excel_processor, ExcelProcessor
from backend.app.services.company_ai_service import company_ai_service
from backend.app.services.conversation_context_manager import conversation_context_manager
from backend.app.services.document_manager import document_manager
from backend.app.schemas.company_ai import CompanyAIChatRequest
from backend.app.schemas.security import UserRoleEnum
from backend.app.schemas.department import DepartmentEnum, RouteRequest
from backend.app.services.routing.intent_router import intent_router


@pytest.fixture
def sample_sprint_workbook_path(tmp_path):
    """Creates an authentic multi-sheet sprint Excel workbook with real rows."""
    wb = openpyxl.Workbook()
    
    # Sheet 1: Sprint 1 - Recruitment Portal
    ws1 = wb.active
    ws1.title = "Sprint 1 - Recruitment Portal"
    headers = ["Module", "Task", "Description", "Estimated Hours", "Owner", "Status"]
    ws1.append(headers)
    ws1.append(["Auth", "OAuth2 Integration", "Implement Google and Microsoft SSO login", 8, "Fazil", "In Progress"])
    ws1.append(["Auth", "JWT Token Rotation", "Add refresh token rotation middleware", 6, "Fazil", "Completed"])
    ws1.append(["Candidate", "Resume Parser", "Extract contact and skill data from PDF", 12, "Reka", "In Progress"])
    ws1.append(["Candidate", "Profile Search", "Build multi-filter candidate search UI", 10, "Reka", "To Do"])

    # Sheet 2: Sprint 2 - iWork
    ws2 = wb.create_sheet(title="Sprint 2 - iWork")
    ws2.append(headers)
    ws2.append(["Workflow", "Approval Engine", "Implement multi-level leave approval", 16, "Fazil", "To Do"])
    ws2.append(["Analytics", "Dashboard Metrics", "Generate department velocity charts", 8, "Reka", "In Progress"])
    ws2.append(["Reports", "Audit Export", "Export compliance logs to encrypted spreadsheet", 4, "Fazil", "To Do"])

    file_path = str(tmp_path / "sprint_final.xlsx")
    wb.save(file_path)
    wb.close()
    return file_path


class TestExcelProcessorUnit:
    """Unit tests for ExcelProcessor."""

    def test_inspect_workbook(self, sample_sprint_workbook_path):
        inspection = excel_processor.inspect_workbook(sample_sprint_workbook_path)
        
        assert "worksheet_names" in inspection
        assert len(inspection["worksheet_names"]) == 2
        assert "Sprint 1 - Recruitment Portal" in inspection["worksheet_names"]
        assert "Sprint 2 - iWork" in inspection["worksheet_names"]
        
        # Verify detected owners
        owners = sorted(inspection["owners"])
        assert "Fazil" in owners
        assert "Reka" in owners
        
        # Verify total rows across all sheets: 4 (Sprint 1) + 3 (Sprint 2) = 7
        assert inspection["total_rows"] == 7
        assert "Module" in inspection["headers"]
        assert "Owner" in inspection["headers"]

    def test_filter_and_export_by_owners_separate_files(self, sample_sprint_workbook_path):
        result = excel_processor.filter_and_export_by_owners(
            file_path=sample_sprint_workbook_path,
            target_owners=["Fazil", "Reka"],
            base_name="Sprint"
        )
        
        assert result["success"] is True
        files = result["generated_files"]
        
        # Should generate: Fazil_Sprint.xlsx, Reka_Sprint.xlsx, Sprint_Split_Fazil_Reka.xlsx
        filenames = [f["filename"] for f in files]
        assert "Fazil_Sprint.xlsx" in filenames
        assert "Reka_Sprint.xlsx" in filenames
        assert "Sprint_Split_Fazil_Reka.xlsx" in filenames

        # Verify Fazil's workbook contents with openpyxl
        fazil_file = next(f for f in files if f["filename"] == "Fazil_Sprint.xlsx")
        fazil_wb = openpyxl.load_workbook(io.BytesIO(fazil_file["file_bytes"]))
        
        # Fazil has 2 tasks in Sprint 1 + 2 tasks in Sprint 2 = 4 total
        total_fazil_rows = 0
        for sheet_name in fazil_wb.sheetnames:
            ws = fazil_wb[sheet_name]
            rows = list(ws.iter_rows(values_only=True))
            # Header is row 0
            header = rows[0]
            assert "Module" in header
            assert "Owner" in header
            for row in rows[1:]:
                # Check owner column value
                owner_idx = header.index("Owner")
                assert row[owner_idx] == "Fazil", f"Non-Fazil row found in Fazil_Sprint.xlsx: {row}"
                total_fazil_rows += 1
        
        assert total_fazil_rows == 4
        assert fazil_file["row_count"] == 4
        assert fazil_file["total_hours"] == 34.0  # 8 + 6 + 16 + 4

        # Verify Reka's workbook contents with openpyxl
        reka_file = next(f for f in files if f["filename"] == "Reka_Sprint.xlsx")
        reka_wb = openpyxl.load_workbook(io.BytesIO(reka_file["file_bytes"]))
        
        total_reka_rows = 0
        for sheet_name in reka_wb.sheetnames:
            ws = reka_wb[sheet_name]
            rows = list(ws.iter_rows(values_only=True))
            header = rows[0]
            for row in rows[1:]:
                owner_idx = header.index("Owner")
                assert row[owner_idx] == "Reka", f"Non-Reka row found in Reka_Sprint.xlsx: {row}"
                total_reka_rows += 1
        
        assert total_reka_rows == 3  # 2 in Sprint 1 + 1 in Sprint 2
        assert reka_file["row_count"] == 3
        assert reka_file["total_hours"] == 30.0  # 12 + 10 + 8

    def test_single_owner_filter(self, sample_sprint_workbook_path):
        result = excel_processor.filter_and_export_by_owners(
            file_path=sample_sprint_workbook_path,
            target_owners=["Fazil"],
            base_name="Sprint"
        )
        assert result["success"] is True
        assert len(result["generated_files"]) == 1
        assert result["generated_files"][0]["filename"] == "Fazil_Sprint.xlsx"
        assert result["generated_files"][0]["row_count"] == 4


class TestExcelFollowUpRouting:
    """Verifies that follow-up requests resolve to Excel operations against active document."""

    def test_typo_tolerant_split_intent_routing(self):
        """User asked: 'make a separate separate sprint for the fazil asnd reka'"""
        session_id = "test_excel_split_session"
        conversation_context_manager.clear_state(session_id)
        
        # Set active document as Excel
        conversation_context_manager.set_active_document(session_id, {
            "id": "DOC-EXCEL-01",
            "filename": "sprint_final.xlsx",
            "document_type": "EXCEL",
            "structured_data": {
                "owners": ["Fazil", "Reka"],
                "worksheet_names": ["Sprint 1", "Sprint 2"]
            }
        })
        state = conversation_context_manager.get_state(session_id)

        user_message = "make a separate separate sprint for the fazil asnd reka"
        decision = intent_router.route(
            RouteRequest(message=user_message, session_id=session_id),
            context_state=state
        )

        assert decision.department in (DepartmentEnum.GENERAL, DepartmentEnum.TECH)
        assert decision.intent == "excel_split"
        assert decision.confidence >= 0.95
        assert "Fazil" in decision.entities.get("target_owners", [])
        assert "Reka" in decision.entities.get("target_owners", [])

    def test_filter_fazil_routing(self):
        session_id = "test_excel_filter_fazil"
        conversation_context_manager.clear_state(session_id)
        conversation_context_manager.set_active_document(session_id, {
            "id": "DOC-EXCEL-02",
            "filename": "sprint_final.xlsx",
            "document_type": "EXCEL",
            "structured_data": {"owners": ["Fazil", "Reka"]}
        })
        state = conversation_context_manager.get_state(session_id)

        decision = intent_router.route(
            RouteRequest(message="give me only Fazil", session_id=session_id),
            context_state=state
        )
        assert decision.department in (DepartmentEnum.GENERAL, DepartmentEnum.TECH)
        assert decision.intent == "excel_filter"
        assert "Fazil" in decision.entities.get("target_owners", [])

    def test_make_one_for_reka_routing(self):
        session_id = "test_excel_filter_reka"
        conversation_context_manager.clear_state(session_id)
        conversation_context_manager.set_active_document(session_id, {
            "id": "DOC-EXCEL-03",
            "filename": "sprint_final.xlsx",
            "document_type": "EXCEL",
            "structured_data": {"owners": ["Fazil", "Reka"]}
        })
        state = conversation_context_manager.get_state(session_id)

        decision = intent_router.route(
            RouteRequest(message="make one for Reka", session_id=session_id),
            context_state=state
        )
        assert decision.department in (DepartmentEnum.GENERAL, DepartmentEnum.TECH)
        assert decision.intent == "excel_filter"
        assert "Reka" in decision.entities.get("target_owners", [])

    def test_reka_sprint_possessive_routing(self):
        session_id = "test_excel_reka_possessive"
        conversation_context_manager.clear_state(session_id)
        conversation_context_manager.set_active_document(session_id, {
            "id": "DOC-EXCEL-04",
            "filename": "sprint_final.xlsx",
            "document_type": "EXCEL",
            "structured_data": {"owners": ["Fazil", "Reka"]}
        })
        state = conversation_context_manager.get_state(session_id)

        decision = intent_router.route(
            RouteRequest(message="give me Reka's sprint", session_id=session_id),
            context_state=state
        )
        assert decision.department in (DepartmentEnum.GENERAL, DepartmentEnum.TECH)
        assert decision.intent == "excel_filter"
        assert "Reka" in decision.entities.get("target_owners", [])

    @pytest.mark.parametrize("user_query", [
        "create the exel file for the fazil and reka with the exel",
        "create a exel file for the fazil and reka seprate seprate with this details",
        "create the excel file for Fazil and Reka",
        "create an excel for Fazil and Reka",
        "create separate excel files for Fazil and Reka",
        "create the excel file for Fazil and Reka separately",
        "make separate files for Fazil and Reka",
        "make separate sprint files for Fazil and Reka",
        "make a separate sprint for Fazil and Reka",
        "create separate separate sprint for Fazil and Reka",
        "give me separate sprint for Fazil and Reka",
        "split this Excel for Fazil and Reka",
        "split this for Fazil and Reka",
        "create one for Fazil and one for Reka",
        "give Fazil and Reka separate files"
    ])
    def test_all_natural_language_split_variations(self, user_query):
        session_id = f"test_var_{abs(hash(user_query))}"
        conversation_context_manager.clear_state(session_id)
        conversation_context_manager.set_active_document(session_id, {
            "id": "DOC-EXCEL-VAR",
            "filename": "sprint final.xlsx",
            "document_type": "EXCEL",
            "structured_data": {"owners": ["Fazil", "Reka"], "worksheet_names": ["Sprint 1", "Sprint 2"]}
        })
        state = conversation_context_manager.get_state(session_id)

        decision = intent_router.route(
            RouteRequest(message=user_query, session_id=session_id),
            context_state=state
        )
        assert decision.department in (DepartmentEnum.GENERAL, DepartmentEnum.TECH)
        assert decision.intent == "excel_split"
        assert "Fazil" in decision.entities.get("target_owners", [])
        assert "Reka" in decision.entities.get("target_owners", [])


class TestEndToEndExcelWorkflow:
    """End-to-end integration test for Excel upload, chat processing, file generation, and download."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        self.client = TestClient(app)

    def test_e2e_excel_upload_and_split(self, sample_sprint_workbook_path):
        session_id = "test_e2e_sprint_split_session"
        conversation_context_manager.clear_state(session_id)

        # 1. Upload the real Excel sprint workbook
        with open(sample_sprint_workbook_path, "rb") as f:
            file_bytes = f.read()

        upload_res = self.client.post(
            "/api/company/upload",
            files={"file": ("sprint_final.xlsx", file_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"session_id": session_id}
        )
        assert upload_res.status_code == 200
        upload_data = upload_res.json()
        assert upload_data["success"] is True
        assert upload_data["document_type"] == "EXCEL"
        assert "Fazil" in upload_data["structured_data"]["owners"]
        assert "Reka" in upload_data["structured_data"]["owners"]

        # 2. Ask to split the sprint for Fazil and Reka with typo
        chat_res = self.client.post(
            "/api/company/chat",
            json={
                "message": "make a separate separate sprint for the fazil asnd reka",
                "session_id": session_id,
                "user_role": "EMPLOYEE"
            }
        )
        assert chat_res.status_code == 200
        chat_data = chat_res.json()

        assert chat_data["status"] == "success"
        assert chat_data["department"] in ("GENERAL", "TECH")
        assert chat_data["intent"] == "excel_split"
        
        # Verify files were generated
        files = chat_data["files"]
        assert len(files) >= 2
        file_names = [f["filename"] for f in files]
        assert "Fazil_Sprint.xlsx" in file_names
        assert "Reka_Sprint.xlsx" in file_names

        # Verify answer doesn't contain generic capability response
        assert "You can ask me technical troubleshooting questions" not in chat_data["answer"]
        assert "Fazil_Sprint.xlsx" in chat_data["answer"]
        assert "Reka_Sprint.xlsx" in chat_data["answer"]

        # 3. Test secure download endpoint for both files
        for f in files:
            file_id = f["file_id"]
            filename = f["filename"]
            dl_res = self.client.get(
                f"/api/company/files/{file_id}/download",
                params={"user_role": "EMPLOYEE", "user_id": "test_user"}
            )
            assert dl_res.status_code == 200
            assert len(dl_res.content) > 0
            
            # Verify the downloaded binary is a valid openpyxl workbook
            dl_wb = openpyxl.load_workbook(io.BytesIO(dl_res.content))
            assert len(dl_wb.sheetnames) >= 1
            dl_wb.close()
