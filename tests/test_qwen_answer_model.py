"""Unit and integration tests for Qwen Local Answer Model Service (Phase 4).
"""

import pytest
from backend.app.schemas.department import DepartmentEnum
from backend.app.schemas.company_ai import CompanyAIResult
from backend.app.services.llm.qwen_answer_model import QwenAnswerModel
from backend.app.services.llm.answer_model_service import answer_model_service


class TestQwenAnswerModel:
    """Test suite verifying Qwen local answer layer contract and strictly bounded response formatting."""

    def test_qwen_model_interface_and_info(self):
        """Validates that Qwen answer model exposes required interface and metadata."""
        info = answer_model_service.get_status()
        assert info["model_name"] == "Qwen3-4B-Q4_K_M"
        assert info["quantization"] == "Q4_K_M"
        assert info["format"] == "GGUF"
        assert info["runtime"] == "llama.cpp"
        assert info["local_only"] is True

    def test_qwen_generates_response_from_tech_verified_result(self):
        """Verifies natural language formatting for Tech error diagnosis."""
        tech_result = CompanyAIResult(
            success=True,
            department=DepartmentEnum.TECH,
            intent="error_diagnosis",
            task="HTTP 500 Internal Error Diagnosis",
            summary="Diagnosed root cause for HTTP 500 application failure.",
            findings=[
                "Database connection pool exhausted.",
                "Recommended fix: Increase pool_size to 20 in database.py."
            ],
            evidence=["TimeoutError: QueuePool limit of size 5 overflow 10 reached"],
            actions_taken=["Analyzed status code 500", "Checked connection pool configuration"],
            tool_results={"status_code": "500", "severity": "HIGH"},
            citations=["application_log"],
            confidence=0.95
        )

        answer = answer_model_service.generate_answer(tech_result)
        assert isinstance(answer, str)
        assert len(answer) > 20
        # Answer must communicate the verified findings
        assert "500" in answer
        assert "Database" in answer or "connection" in answer or "pool" in answer

    def test_qwen_generates_response_from_hr_verified_result(self):
        """Verifies natural language formatting for HR policy question."""
        hr_result = CompanyAIResult(
            success=True,
            department=DepartmentEnum.HR,
            intent="policy_question",
            task="Casual Leave Policy Inquiry",
            summary="Retrieved official company HR policy guidelines.",
            findings=["Employees receive 18 casual leave days per calendar year."],
            evidence=["HR_TEST_POLICY: Employees receive 18 casual leave days"],
            citations=["hr_leave_policy"],
            confidence=0.98
        )

        answer = answer_model_service.generate_answer(hr_result)
        assert isinstance(answer, str)
        assert "18" in answer
        assert "leave" in answer.lower()

    def test_qwen_generates_response_from_finance_verified_result(self):
        """Verifies natural language formatting for Finance deterministic calculations."""
        finance_result = CompanyAIResult(
            success=True,
            department=DepartmentEnum.FINANCE,
            intent="expense_calculation",
            task="July Travel Expense Calculation",
            summary="Calculated verified total expenses for July via deterministic Python arithmetic.",
            findings=["Total Calculated Expense: $2,250.00", "Breakdown: Flights $1200 + Hotel $800 + Meals $250 = $2250.00"],
            tool_results={"total_amount": "$2,250.00", "currency": "USD", "formula": "$1200 + $800 + $250 = $2250.00"},
            citations=["finance_expense_ledger"],
            confidence=0.99
        )

        answer = answer_model_service.generate_answer(finance_result)
        assert isinstance(answer, str)
        assert "2,250" in answer or "2250" in answer
        assert "July" in answer or "expense" in answer.lower()

    def test_qwen_handles_empty_or_unavailable_gracefully(self):
        """Ensures answer model reports unavailability when result states data is unavailable."""
        empty_result = CompanyAIResult(
            success=False,
            department=DepartmentEnum.GENERAL,
            intent="unknown",
            task="Unknown Inquiry",
            summary="The requested information is unavailable in company records.",
            findings=[],
            warnings=["No matching company records found."]
        )

        answer = answer_model_service.generate_answer(empty_result)
        assert isinstance(answer, str)
        assert "unavailable" in answer.lower() or "no matching" in answer.lower()
