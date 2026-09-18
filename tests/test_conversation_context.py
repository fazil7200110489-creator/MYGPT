"""Comprehensive test suite for Phase 4 Conversation Orchestration & Context Retention in MYGPT Company AI.

Covers all 16 required test scenarios:
 1. Department declaration ("I'm from tech department")
 2. Troubleshooting intake ("i have issue in my project")
 3. Confirmation continuation ("yes" when awaiting error details)
 4. Error stack trace diagnosis (TypeError in userController.js:42)
 5. Target location follow-up ("where should I fix it")
 6. Code analysis follow-up ("show me the corrected code")
 7. Clean topic switch to HR ("What is our casual leave policy?")
 8. HR detail expansion follow-up ("can u give me more detailed")
 9. HR contextual document export ("make me an excel document")
10. HR contextual document modification ("add employee acknowledgement section")
11. Finance arithmetic ("calculate 1200 + 800 + 250")
12. Finance continuation arithmetic ("add 500 more" -> 2250 + 500 = 2750)
13. Finance excel comparison ("compare these two excel files")
14. Ambiguous document request with zero context ("make me an excel document" -> clarification)
15. RBAC enforcement on every turn (Guest denied privileged access)
16. Session isolation (Session A and Session B maintain independent state)
"""

import pytest
from backend.app.schemas.company_ai import CompanyAIChatRequest
from backend.app.schemas.security import UserRoleEnum
from backend.app.services.company_ai_service import company_ai_service
from backend.app.services.conversation_context_manager import conversation_context_manager


@pytest.fixture(autouse=True)
def clean_context():
    """Ensure context is clean before each test."""
    conversation_context_manager.clear_state("test_session_1")
    conversation_context_manager.clear_state("test_session_2")
    company_ai_service.clear_history("test_session_1")
    company_ai_service.clear_history("test_session_2")
    yield
    conversation_context_manager.clear_state("test_session_1")
    conversation_context_manager.clear_state("test_session_2")
    company_ai_service.clear_history("test_session_1")
    company_ai_service.clear_history("test_session_2")


def test_01_department_declaration():
    """Test 1: 'I'm from tech department' sets TECH context."""
    req = CompanyAIChatRequest(
        message="I'm from tech department",
        session_id="test_session_1",
        user_role=UserRoleEnum.EMPLOYEE
    )
    resp = company_ai_service.process_chat(req)
    assert resp.department == "TECH"
    assert resp.intent == "department_declaration"
    assert "technical" in resp.answer.lower() or "tech" in resp.answer.lower()


def test_02_troubleshooting_intake():
    """Test 2: 'i have issue in my project' prompts for error details and sets pending action."""
    # First set tech department
    company_ai_service.process_chat(CompanyAIChatRequest(
        message="I'm from tech department",
        session_id="test_session_1",
        user_role=UserRoleEnum.EMPLOYEE
    ))

    req = CompanyAIChatRequest(
        message="i have issue in my project",
        session_id="test_session_1",
        user_role=UserRoleEnum.EMPLOYEE
    )
    resp = company_ai_service.process_chat(req)
    assert resp.department == "TECH"
    assert resp.intent == "troubleshooting"
    assert "diagnose" in resp.answer.lower() or "error" in resp.answer.lower()

    state = conversation_context_manager.get_state("test_session_1")
    assert state.pending_action == "awaiting_error_details"


def test_03_confirmation_continuation():
    """Test 3: 'yes' confirms ongoing troubleshooting session."""
    # Step 1: Issue
    company_ai_service.process_chat(CompanyAIChatRequest(
        message="i have issue in my project",
        session_id="test_session_1",
        user_role=UserRoleEnum.EMPLOYEE
    ))
    # Step 2: Confirmation
    req = CompanyAIChatRequest(
        message="yes",
        session_id="test_session_1",
        user_role=UserRoleEnum.EMPLOYEE
    )
    resp = company_ai_service.process_chat(req)
    assert resp.department == "TECH"
    assert resp.intent == "troubleshooting"
    assert "share the error" in resp.answer.lower() or "log" in resp.answer.lower() or "code" in resp.answer.lower()


def test_04_error_stack_trace_diagnosis():
    """Test 4: Node.js express TypeError stack trace diagnosis."""
    req = CompanyAIChatRequest(
        message="node.js express app TypeError: Cannot read property 'map' of undefined in userController.js:42",
        session_id="test_session_1",
        user_role=UserRoleEnum.EMPLOYEE
    )
    resp = company_ai_service.process_chat(req)
    assert resp.department == "TECH"
    assert resp.intent == "error_diagnosis"
    assert "typeerror" in resp.answer.lower()
    assert "usercontroller.js" in resp.answer.lower()
    assert "42" in resp.answer.lower()


def test_05_target_location_follow_up():
    """Test 5: 'where should I fix it' points to userController.js line 42."""
    # Step 1: diagnose error
    company_ai_service.process_chat(CompanyAIChatRequest(
        message="TypeError: Cannot read property 'map' of undefined in userController.js:42",
        session_id="test_session_1",
        user_role=UserRoleEnum.EMPLOYEE
    ))
    # Step 2: where to fix
    req = CompanyAIChatRequest(
        message="where should I fix it",
        session_id="test_session_1",
        user_role=UserRoleEnum.EMPLOYEE
    )
    resp = company_ai_service.process_chat(req)
    assert resp.department == "TECH"
    assert "usercontroller.js" in resp.answer.lower()
    assert "42" in resp.answer.lower()


def test_06_code_analysis_follow_up():
    """Test 6: 'show me the corrected code' provides JavaScript patch."""
    # Step 1: error
    company_ai_service.process_chat(CompanyAIChatRequest(
        message="TypeError: Cannot read property 'map' of undefined in userController.js:42",
        session_id="test_session_1",
        user_role=UserRoleEnum.EMPLOYEE
    ))
    # Step 2: show code
    req = CompanyAIChatRequest(
        message="show me the corrected code",
        session_id="test_session_1",
        user_role=UserRoleEnum.EMPLOYEE
    )
    resp = company_ai_service.process_chat(req)
    assert resp.department == "TECH"
    assert resp.intent == "code_analysis"
    assert "usercontroller.js" in resp.answer.lower()
    assert "map" in resp.answer.lower()


def test_07_clean_topic_switch_to_hr():
    """Test 7: Clean topic switch from TECH to HR policy question."""
    # Step 1: Tech error
    company_ai_service.process_chat(CompanyAIChatRequest(
        message="TypeError: Cannot read property 'map' of undefined in userController.js:42",
        session_id="test_session_1",
        user_role=UserRoleEnum.EMPLOYEE
    ))
    # Step 2: HR question
    req = CompanyAIChatRequest(
        message="What is our casual leave policy?",
        session_id="test_session_1",
        user_role=UserRoleEnum.EMPLOYEE
    )
    resp = company_ai_service.process_chat(req)
    assert resp.department == "HR"
    assert resp.intent == "policy_question"
    assert "leave" in resp.answer.lower()


def test_08_hr_detail_expansion_follow_up():
    """Test 8: 'can u give me more detailed' retains HR policy context."""
    # Step 1: Policy question
    company_ai_service.process_chat(CompanyAIChatRequest(
        message="What is our casual leave policy?",
        session_id="test_session_1",
        user_role=UserRoleEnum.EMPLOYEE
    ))
    # Step 2: Detail expansion
    req = CompanyAIChatRequest(
        message="can u give me more detailed",
        session_id="test_session_1",
        user_role=UserRoleEnum.EMPLOYEE
    )
    resp = company_ai_service.process_chat(req)
    assert resp.department == "HR"
    assert resp.intent == "policy_question"
    assert "12 days" in resp.answer or "casual leave" in resp.answer.lower()


def test_09_hr_contextual_document_export():
    """Test 9: 'make me an excel document' in HR context generates real .xlsx."""
    # Step 1: Policy question
    company_ai_service.process_chat(CompanyAIChatRequest(
        message="What is our casual leave policy?",
        session_id="test_session_1",
        user_role=UserRoleEnum.EMPLOYEE
    ))
    # Step 2: Document export
    req = CompanyAIChatRequest(
        message="make me an excel document",
        session_id="test_session_1",
        user_role=UserRoleEnum.EMPLOYEE
    )
    resp = company_ai_service.process_chat(req)
    assert resp.department == "HR"
    assert resp.intent == "document_export"
    assert len(resp.files) > 0
    assert resp.files[0]["filename"].endswith(".xlsx")
    assert "data_base64" in resp.files[0]


def test_10_hr_contextual_document_modification():
    """Test 10: 'add employee acknowledgement section' modifies/updates document."""
    # Step 1: Policy question
    company_ai_service.process_chat(CompanyAIChatRequest(
        message="What is our casual leave policy?",
        session_id="test_session_1",
        user_role=UserRoleEnum.EMPLOYEE
    ))
    # Step 2: Document export
    company_ai_service.process_chat(CompanyAIChatRequest(
        message="make me an excel document",
        session_id="test_session_1",
        user_role=UserRoleEnum.EMPLOYEE
    ))
    # Step 3: Add section
    req = CompanyAIChatRequest(
        message="add employee acknowledgement section",
        session_id="test_session_1",
        user_role=UserRoleEnum.EMPLOYEE
    )
    resp = company_ai_service.process_chat(req)
    assert resp.department == "HR"
    assert resp.intent in ("document_creation", "document_modification")
    assert "acknowledgement" in resp.answer.lower()


def test_11_finance_arithmetic():
    """Test 11: Pure deterministic arithmetic in Finance."""
    req = CompanyAIChatRequest(
        message="calculate 1200 + 800 + 250",
        session_id="test_session_1",
        user_role=UserRoleEnum.EMPLOYEE
    )
    resp = company_ai_service.process_chat(req)
    assert resp.department == "FINANCE"
    assert resp.intent == "expense_calculation"
    assert "2,250" in resp.answer or "2250" in resp.answer


def test_12_finance_continuation_arithmetic():
    """Test 12: 'add 500 more' continues previous total (2250 + 500 = 2750)."""
    # Step 1: Base calculation
    company_ai_service.process_chat(CompanyAIChatRequest(
        message="calculate 1200 + 800 + 250",
        session_id="test_session_1",
        user_role=UserRoleEnum.EMPLOYEE
    ))
    # Step 2: Add 500 more
    req = CompanyAIChatRequest(
        message="add 500 more",
        session_id="test_session_1",
        user_role=UserRoleEnum.EMPLOYEE
    )
    resp = company_ai_service.process_chat(req)
    assert resp.department == "FINANCE"
    assert resp.intent == "expense_calculation"
    assert "2,750" in resp.answer or "2750" in resp.answer


def test_13_finance_file_comparison():
    """Test 13: Excel spreadsheet comparison in Finance."""
    req = CompanyAIChatRequest(
        message="compare these two excel files and generate report",
        session_id="test_session_1",
        user_role=UserRoleEnum.EMPLOYEE
    )
    resp = company_ai_service.process_chat(req)
    assert resp.department == "FINANCE"
    assert resp.intent in ("excel_comparison", "file_comparison")
    assert "comparison" in resp.answer.lower() or "ledger" in resp.answer.lower()


def test_14_ambiguous_document_request_zero_context():
    """Test 14: 'make me an excel document' with zero prior context prompts for clarification."""
    req = CompanyAIChatRequest(
        message="make me an excel document",
        session_id="fresh_session_no_context",
        user_role=UserRoleEnum.EMPLOYEE
    )
    resp = company_ai_service.process_chat(req)
    assert resp.department == "GENERAL"
    assert resp.intent == "ambiguous_document_request"
    assert "what would you like" in resp.answer.lower() or "specify" in resp.answer.lower()


def test_15_rbac_enforcement_on_every_turn():
    """Test 15: Unauthorized role (e.g. HR_MANAGER accessing TECH log analysis) is denied regardless of history."""
    req = CompanyAIChatRequest(
        message="download server log stream and analyze errors",
        session_id="test_session_1",
        user_role=UserRoleEnum.HR_MANAGER
    )
    resp = company_ai_service.process_chat(req)
    assert resp.status == "permission_denied"
    assert "restricted" in resp.answer.lower() or "rbac" in resp.answer.lower()


def test_16_session_isolation():
    """Test 16: Session A and Session B maintain independent dialogue states."""
    # Session A is in TECH context
    company_ai_service.process_chat(CompanyAIChatRequest(
        message="TypeError: Cannot read property 'map' of undefined in userController.js:42",
        session_id="test_session_1",
        user_role=UserRoleEnum.EMPLOYEE
    ))

    # Session B is in HR context
    company_ai_service.process_chat(CompanyAIChatRequest(
        message="What is our casual leave policy?",
        session_id="test_session_2",
        user_role=UserRoleEnum.EMPLOYEE
    ))

    # Ask Session A "where should I fix it" -> must answer TECH userController.js
    resp_a = company_ai_service.process_chat(CompanyAIChatRequest(
        message="where should I fix it",
        session_id="test_session_1",
        user_role=UserRoleEnum.EMPLOYEE
    ))
    assert resp_a.department == "TECH"
    assert "usercontroller.js" in resp_a.answer.lower()

    # Ask Session B "can u give me more detailed" -> must answer HR leave policy
    resp_b = company_ai_service.process_chat(CompanyAIChatRequest(
        message="can u give me more detailed",
        session_id="test_session_2",
        user_role=UserRoleEnum.EMPLOYEE
    ))
    assert resp_b.department == "HR"
    assert "leave" in resp_b.answer.lower()
