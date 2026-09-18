"""End-to-end integration tests for full Company AI Pipeline:
USER -> MYGPT Router -> RBAC -> Department RAG / Deterministic Tools -> Verified Contract -> Qwen -> USER.
"""

import pytest
from backend.app.schemas.company_ai import CompanyAIChatRequest
from backend.app.schemas.security import UserRoleEnum
from backend.app.services.company_ai_service import company_ai_service


class TestCompanyAIPipeline:
    """Test suite validating full end-to-end department workflows."""

    def test_hr_leave_policy_end_to_end(self):
        """USER -> HR -> RAG -> Verified Result -> Qwen -> Answer."""
        req = CompanyAIChatRequest(
            message="What is our casual leave policy?",
            user_role=UserRoleEnum.EMPLOYEE,
            user_id="emp_alice"
        )
        res = company_ai_service.process_chat(req)

        assert res.department == "HR"
        assert res.intent == "policy_question"
        assert res.status == "success"
        assert "18" in res.answer or "casual leave" in res.answer.lower()
        assert len(res.sources) > 0
        assert any("hr_leave_policy" in s.get("doc_id", "") for s in res.sources)

    def test_tech_http_500_error_diagnosis_end_to_end(self):
        """USER -> TECH -> Error Diagnosis -> Verified Result -> Qwen -> Answer."""
        req = CompanyAIChatRequest(
            message="My application is returning HTTP 500. What is causing this?",
            user_role=UserRoleEnum.EMPLOYEE,
            user_id="dev_bob"
        )
        res = company_ai_service.process_chat(req)

        assert res.department == "TECH"
        assert res.intent == "error_diagnosis"
        assert res.status == "success"
        assert "500" in res.answer
        assert len(res.actions) > 0

    def test_tech_troubleshooting_end_to_end(self):
        """USER -> TECH -> Troubleshooting -> Verified Result -> Qwen -> Answer."""
        req = CompanyAIChatRequest(
            message="My laptop has Wi-Fi but internet is not working.",
            user_role=UserRoleEnum.EMPLOYEE,
            user_id="emp_charlie"
        )
        res = company_ai_service.process_chat(req)

        assert res.department == "TECH"
        assert res.intent == "troubleshooting"
        assert res.status == "success"
        assert "DNS" in res.answer or "gateway" in res.answer.lower() or "Wi-Fi" in res.answer or "network" in res.answer.lower()

    def test_finance_expense_calculation_deterministic_math(self):
        """USER -> FINANCE -> Deterministic Python Math -> Verified Result -> Qwen -> Answer."""
        req = CompanyAIChatRequest(
            message="Calculate total travel expenses for July: Flights $1200, Hotel $800, Meals $250.",
            user_role=UserRoleEnum.EMPLOYEE,
            user_id="emp_david"
        )
        res = company_ai_service.process_chat(req)

        assert res.department == "FINANCE"
        assert res.intent == "expense_calculation"
        assert res.status == "success"
        # Deterministic Python arithmetic must be accurately reflected ($1200 + $800 + $250 = $2250)
        assert "2,250" in res.answer or "2250" in res.answer or "$2250" in res.answer

    def test_finance_expense_report_document_workflow(self):
        """USER -> FINANCE -> Report Generation -> File attachment -> Verified Result -> Qwen -> Answer."""
        req = CompanyAIChatRequest(
            message="Generate the monthly travel expense report for July.",
            user_role=UserRoleEnum.FINANCE_MANAGER,
            user_id="emp_eve"
        )
        res = company_ai_service.process_chat(req)

        assert res.department == "FINANCE"
        assert res.intent == "expense_report"
        assert res.status == "success"
        assert len(res.files) > 0
        assert res.files[0]["type"] == "XLSX"
        assert "expense_report" in res.files[0]["filename"]

    def test_general_capabilities_workflow(self):
        """USER -> GENERAL -> Capabilities -> Qwen -> Answer."""
        req = CompanyAIChatRequest(
            message="Hello, what can you help me with?",
            user_role=UserRoleEnum.EMPLOYEE
        )
        res = company_ai_service.process_chat(req)

        assert res.department == "GENERAL"
        assert res.status == "success"
        assert len(res.answer) > 30
