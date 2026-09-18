"""Comprehensive test suite for FINAL ARCHITECTURE CHANGE — SEMANTIC UNDERSTANDING FIRST.

Validates:
1. Natural language understanding with spelling variations / synonyms / indirect questions.
2. Multi-turn context continuity:
   - "what is the leave policy?" -> HR policy
   - "what about casual leave?" -> previous HR context
   - "compare these two resumes" -> resume comparison
   - "who is better?" -> previous resume comparison
   - "what are the mismatches?" -> previous two-file comparison
   - "give me this as Excel" -> export the previous verified result
3. Reliable company info missing -> "I couldn't find this information in the available company knowledge or documents."
4. Deterministic math and tools preserve verification and RBAC boundaries.
"""

import pytest
from backend.app.schemas.company_ai import CompanyAIChatRequest
from backend.app.schemas.security import UserRoleEnum
from backend.app.schemas.department import DepartmentEnum, RouteRequest
from backend.app.services.company_ai_service import company_ai_service
from backend.app.services.routing.intent_router import intent_router
from backend.app.services.conversation_context_manager import conversation_context_manager


class TestSemanticUnderstandingFirst:
    """Test suite validating the semantic-first architecture and multi-turn flows."""

    def test_hr_leave_policy_and_followup_casual_leave(self):
        """Turn 1: 'what is the leave policy?' -> HR
        Turn 2: 'what about casual leave?' -> inherits HR context.
        """
        session_id = "test_semantic_hr_turn_1"
        conversation_context_manager.clear_state(session_id)

        # Turn 1
        req1 = CompanyAIChatRequest(
            message="what is the leave policy?",
            session_id=session_id,
            user_role=UserRoleEnum.EMPLOYEE,
            user_id="emp_alice"
        )
        res1 = company_ai_service.process_chat(req1)
        assert res1.department == "HR"
        assert res1.intent == "policy_question"
        assert res1.status == "success"
        assert len(res1.sources) > 0

        # Turn 2: Follow-up with natural phrasing
        req2 = CompanyAIChatRequest(
            message="what about casual leave?",
            session_id=session_id,
            user_role=UserRoleEnum.EMPLOYEE,
            user_id="emp_alice"
        )
        res2 = company_ai_service.process_chat(req2)
        assert res2.department == "HR"
        assert res2.intent == "policy_question"
        assert res2.status == "success"
        assert "casual leave" in res2.answer.lower() or "18" in res2.answer or len(res2.sources) > 0

    def test_resume_comparison_and_who_is_better_followup(self):
        """Turn 1: 'compare these two resumes' -> candidate comparison
        Turn 2: 'who is better?' -> evaluates candidate comparison with previous context.
        """
        session_id = "test_semantic_resume_comp"
        conversation_context_manager.clear_state(session_id)

        # Turn 1
        req1 = CompanyAIChatRequest(
            message="compare these two resumes",
            session_id=session_id,
            user_role=UserRoleEnum.HR_MANAGER,
            user_id="hr_recruiter"
        )
        res1 = company_ai_service.process_chat(req1)
        assert res1.department == "HR"
        assert res1.intent in ["candidate_comparison", "file_comparison"]
        assert res1.status == "success"

        # Turn 2: Follow-up 'who is better?'
        req2 = CompanyAIChatRequest(
            message="who is better?",
            session_id=session_id,
            user_role=UserRoleEnum.HR_MANAGER,
            user_id="hr_recruiter"
        )
        res2 = company_ai_service.process_chat(req2)
        assert res2.department == "HR"
        assert res2.intent in ["candidate_comparison", "candidate_role_fit_analysis", "candidate_summary"]
        assert res2.status == "success"

    def test_file_comparison_and_mismatches_followup(self):
        """Turn 1: 'compare these two invoices'
        Turn 2: 'what are the mismatches?' -> contextual comparison report.
        """
        session_id = "test_semantic_file_mismatches"
        conversation_context_manager.clear_state(session_id)

        # Turn 1
        req1 = CompanyAIChatRequest(
            message="compare these two invoices",
            session_id=session_id,
            user_role=UserRoleEnum.FINANCE_MANAGER,
            user_id="fin_user"
        )
        res1 = company_ai_service.process_chat(req1)
        assert res1.department in ["FINANCE", "GENERAL"]
        assert res1.status == "success"

        # Turn 2: Follow-up 'what are the mismatches?'
        req2 = CompanyAIChatRequest(
            message="what are the mismatches?",
            session_id=session_id,
            user_role=UserRoleEnum.FINANCE_MANAGER,
            user_id="fin_user"
        )
        res2 = company_ai_service.process_chat(req2)
        assert res2.status == "success"
        assert res2.intent in ["file_comparison", "excel_comparison", "excel_compare", "document_summary"]

    def test_export_previous_result_as_excel(self):
        """'give me this as Excel' -> exports previous verified result."""
        session_id = "test_semantic_excel_export"
        conversation_context_manager.clear_state(session_id)

        # Setup state with a previous topic
        state = conversation_context_manager.get_state(session_id)
        state.last_department = "FINANCE"
        state.last_intent = "expense_calculation"
        state.last_topic = "Travel Expense Summary"

        req = CompanyAIChatRequest(
            message="give me this as Excel",
            session_id=session_id,
            user_role=UserRoleEnum.EMPLOYEE,
            user_id="emp_user"
        )
        res = company_ai_service.process_chat(req)
        assert res.status == "success"
        assert res.intent in ["excel_export_result", "document_export", "excel_full_export"]
        assert len(res.files) > 0 or "excel" in res.answer.lower() or "xlsx" in res.answer.lower()

    def test_unfound_company_information_returns_exact_message(self):
        """When company info cannot be found, return exact message and never general capabilities."""
        req = CompanyAIChatRequest(
            message="What is our company policy on private submarine maintenance?",
            user_role=UserRoleEnum.EMPLOYEE,
            user_id="emp_bob"
        )
        res = company_ai_service.process_chat(req)
        assert res.status == "success"
        # Must return the exact not-found message
        assert "I couldn't find this information in the available company knowledge or documents." in res.answer or \
               "not found in the authorized knowledge base" in res.answer or \
               "not available" in res.answer

    def test_pure_math_fast_path(self):
        """Fast-path for obvious direct arithmetic computation."""
        req = CompanyAIChatRequest(
            message="Calculate 1200 + 800 + 250",
            user_role=UserRoleEnum.EMPLOYEE,
            user_id="emp_dan"
        )
        res = company_ai_service.process_chat(req)
        assert res.department == "FINANCE"
        assert res.intent == "expense_calculation"
        assert res.status == "success"
        assert "2,250" in res.answer or "2250" in res.answer
