"""Test suite verifying removal of all mock/fallback company data from production workflows."""

import pytest
from backend.app.schemas.company_ai import CompanyAIChatRequest
from backend.app.schemas.security import UserRoleEnum
from backend.app.schemas.department import DepartmentEnum
from backend.app.services.company_ai_service import company_ai_service
from backend.app.services.conversation_context_manager import conversation_context_manager


def test_empty_document_summary_no_fake_candidate():
    """Verifies that summarizing an unreadable or empty document does NOT fabricate Candidate, Software Engineer, or $120,000."""
    session_id = "test_empty_doc_session"
    company_ai_service.clear_history(session_id)

    # Attach empty active document
    conversation_context_manager.set_active_document(session_id, {
        "document_id": "DOC-EMPTY-1",
        "filename": "empty_file.pdf",
        "file_type": ".pdf",
        "document_type": "GENERAL_DOCUMENT",
        "extracted_text": "",
        "structured_data": {}
    })

    req = CompanyAIChatRequest(
        message="Summarize this document",
        session_id=session_id,
        user_role=UserRoleEnum.HR_MANAGER
    )
    res = company_ai_service.process_chat(req)

    # Must NOT contain old mock values
    forbidden_mocks = ["Candidate Name: Candidate", "Software Engineer", "$120,000", "2026-10-01", "Offer Generated / Active"]
    for mock in forbidden_mocks:
        assert mock not in res.answer, f"Forbidden mock value found in summary: {mock}"

    assert "couldn't extract readable text" in res.answer.lower() or "no readable text" in res.answer.lower()


def test_finance_calculation_no_fake_2250():
    """Verifies that asking to calculate without numbers asks for operands rather than defaulting to $2,250.00."""
    session_id = "test_calc_no_mock"
    company_ai_service.clear_history(session_id)

    req = CompanyAIChatRequest(
        message="Calculate my expenses please",
        session_id=session_id,
        user_role=UserRoleEnum.FINANCE_MANAGER
    )
    res = company_ai_service.process_chat(req)

    # Must not fabricate $2,250.00 or 1200+800+250
    assert "$2,250.00" not in res.answer
    assert "$1200.00" not in res.answer
    assert "operands" in res.answer.lower() or "provide" in res.answer.lower() or "numbers" in res.answer.lower()


def test_finance_calculation_real_numbers():
    """Verifies that supplying real numbers calculates deterministically from user input."""
    session_id = "test_calc_real"
    company_ai_service.clear_history(session_id)

    req = CompanyAIChatRequest(
        message="Calculate 1200 + 800 + 250",
        session_id=session_id,
        user_role=UserRoleEnum.FINANCE_MANAGER
    )
    res = company_ai_service.process_chat(req)

    assert "2,250" in res.answer or "2250" in res.answer
    assert "1200" in res.answer and "800" in res.answer and "250" in res.answer


def test_offer_letter_without_candidate_prompts_user():
    """Verifies that requesting an offer letter without candidate details prompts the user rather than defaulting to Mohamed Fazil / $125,000."""
    session_id = "test_offer_no_cand"
    company_ai_service.clear_history(session_id)

    req = CompanyAIChatRequest(
        message="Create an offer letter",
        session_id=session_id,
        user_role=UserRoleEnum.HR_MANAGER
    )
    res = company_ai_service.process_chat(req)

    assert "Mohamed Fazil" not in res.answer
    assert "provide the candidate" in res.answer.lower() or "name" in res.answer.lower()


def test_offer_letter_with_candidate_details_generates_real_docx():
    """Verifies that providing candidate details generates a real DOCX with supplied values."""
    session_id = "test_offer_real_cand"
    company_ai_service.clear_history(session_id)

    req = CompanyAIChatRequest(
        message="Create offer letter for Alice Smith, Senior Data Scientist, salary $150,000, start date 15 November 2026",
        session_id=session_id,
        user_role=UserRoleEnum.HR_MANAGER
    )
    res = company_ai_service.process_chat(req)

    assert "Alice Smith" in res.answer
    assert "$150,000" in res.answer or "150,000" in res.answer
    assert len(res.files) > 0
    assert res.files[0]["filename"].endswith(".docx")


def test_expense_report_without_data_no_fake_july_report():
    """Verifies that generating an expense report without source data does NOT create fake July 2026 / $2,250 report."""
    session_id = "test_expense_no_mock"
    company_ai_service.clear_history(session_id)

    req = CompanyAIChatRequest(
        message="Generate an expense report",
        session_id=session_id,
        user_role=UserRoleEnum.FINANCE_MANAGER
    )
    res = company_ai_service.process_chat(req)

    assert "No verified expense data is available" in res.answer or "source data required" in res.answer.lower()
    assert "$2,250.00" not in res.answer


def test_invoice_without_document_prompts_for_upload():
    """Verifies that asking about invoice total without an attached invoice prompts user instead of returning INV-2026-089 / $1770."""
    session_id = "test_inv_no_doc"
    company_ai_service.clear_history(session_id)

    req = CompanyAIChatRequest(
        message="How much is the total invoice amount?",
        session_id=session_id,
        user_role=UserRoleEnum.FINANCE_MANAGER
    )
    res = company_ai_service.process_chat(req)

    assert "INV-2026-089" not in res.answer
    assert "$1,770.00" not in res.answer
    assert "upload" in res.answer.lower() or "attach" in res.answer.lower()
