"""Unit and Integration tests for Phase 4 Real Chat Orchestration.

Validates the 5 mandatory exact test cases:
1. TEST A: Follow-up question context retention (HR -> "Can you give me more detailed?" remains HR).
2. TEST B: Deterministic arithmetic calculation (1200 + 800 + 250 = 2250, Python math engine).
3. TEST C: Technical error diagnosis (PHP API returning HTTP 500).
4. TEST D: Conversational greeting ("hi" -> GENERAL / greeting).
5. TEST E: RBAC authorization boundary (TECH_ADMIN requesting privileged Finance info is DENIED).
"""

import pytest
from backend.app.schemas.department import DepartmentEnum, RouteRequest
from backend.app.schemas.security import UserRoleEnum
from backend.app.schemas.company_ai import CompanyAIChatRequest
from backend.app.services.routing.intent_router import intent_router
from backend.app.services.company_ai_service import company_ai_service
from backend.app.services.security.permission_manager import permission_manager


class TestPhase4Orchestration:
    """Verification test suite for all Phase 4 requirements."""

    def test_case_a_hr_follow_up_context(self):
        """TEST A:
        1. 'What is our casual leave policy?' -> HR / policy_question
        2. 'Can you give me more detailed?' -> HR / policy_question follow-up (NOT GENERAL)
        """
        session_id = "test_session_hr_followup"
        company_ai_service.clear_history(session_id)

        # Turn 1
        req1 = CompanyAIChatRequest(
            message="What is our casual leave policy?",
            session_id=session_id,
            user_role=UserRoleEnum.EMPLOYEE,
            user_id="emp_user_1"
        )
        res1 = company_ai_service.process_chat(req1)
        assert res1.department == "HR"
        assert res1.intent == "policy_question"
        assert res1.status == "success"
        assert "18" in res1.answer or "casual leave" in res1.answer.lower()

        # Turn 2 (Follow-up)
        req2 = CompanyAIChatRequest(
            message="Can you give me more detailed?",
            session_id=session_id,
            user_role=UserRoleEnum.EMPLOYEE,
            user_id="emp_user_1"
        )
        res2 = company_ai_service.process_chat(req2)
        assert res2.department == "HR", f"Expected HR, got {res2.department}"
        assert res2.intent == "policy_question", f"Expected policy_question, got {res2.intent}"
        assert res2.status == "success"
        assert "18" in res2.answer or "casual leave" in res2.answer.lower()
        # Ensure it does not invent unverified facts
        assert "18" in res2.answer

    def test_case_b_deterministic_calculation(self):
        """TEST B:
        'Calculate 1200 + 800 + 250.' -> Deterministic calculation = 2250 (zero LLM math)
        """
        req = CompanyAIChatRequest(
            message="Calculate 1200 + 800 + 250.",
            session_id="test_calc_session",
            user_role=UserRoleEnum.EMPLOYEE,
            user_id="emp_user_2"
        )
        res = company_ai_service.process_chat(req)
        assert res.department == "FINANCE"
        assert res.intent == "expense_calculation"
        assert res.status == "success"
        assert "2250" in res.answer or "2,250" in res.answer
        assert "1200" in res.answer

    def test_case_c_tech_http_500_error_diagnosis(self):
        """TEST C:
        'My PHP API is returning HTTP 500. Find the problem.' -> TECH / error_diagnosis
        """
        req = CompanyAIChatRequest(
            message="My PHP API is returning HTTP 500. Find the problem.",
            session_id="test_tech_session",
            user_role=UserRoleEnum.EMPLOYEE,
            user_id="dev_user_1"
        )
        res = company_ai_service.process_chat(req)
        assert res.department == "TECH"
        assert res.intent in ["error_diagnosis", "code_analysis"]
        assert res.status == "success"
        assert "500" in res.answer or "PHP" in res.answer

    def test_case_d_greeting(self):
        """TEST D:
        'hi' -> GENERAL / greeting -> natural conversational response without capability dump
        """
        req = CompanyAIChatRequest(
            message="hi",
            session_id="test_greeting_session",
            user_role=UserRoleEnum.EMPLOYEE,
            user_id="emp_user_3"
        )
        res = company_ai_service.process_chat(req)
        assert res.department == "GENERAL"
        assert res.intent == "greeting"
        assert res.status == "success"
        assert len(res.answer) > 5
        assert "hello" in res.answer.lower() or "how can i" in res.answer.lower()

    def test_case_e_rbac_denial(self):
        """TEST E:
        TECH_ADMIN requests privileged Finance information -> RBAC denial.
        """
        req = CompanyAIChatRequest(
            message="Generate monthly expense report and financial audit breakdown.",
            session_id="test_rbac_session",
            user_role=UserRoleEnum.TECH_ADMIN,
            user_id="tech_admin_1"
        )
        res = company_ai_service.process_chat(req)
        assert res.department == "FINANCE"
        assert res.status == "permission_denied"
        assert "restricted" in res.answer.lower() or "permission" in res.answer.lower() or "access" in res.answer.lower()

    def test_conversation_memory_security_enforcement(self):
        """Conversation memory must NEVER bypass authorization."""
        session_id = "test_sec_memory_session"
        company_ai_service.clear_history(session_id)

        # First request as ADMIN (allowed)
        req1 = CompanyAIChatRequest(
            message="Generate the monthly travel expense report for July.",
            session_id=session_id,
            user_role=UserRoleEnum.ADMIN,
            user_id="admin_1"
        )
        res1 = company_ai_service.process_chat(req1)
        assert res1.status == "success"

        # Subsequent follow-up by TECH_ADMIN in same session must still be DENIED for finance
        req2 = CompanyAIChatRequest(
            message="Can you give me more detailed breakdown of this report?",
            session_id=session_id,
            user_role=UserRoleEnum.TECH_ADMIN,
            user_id="tech_admin_1"
        )
        res2 = company_ai_service.process_chat(req2)
        assert res2.department == "FINANCE"
        assert res2.status == "permission_denied"
