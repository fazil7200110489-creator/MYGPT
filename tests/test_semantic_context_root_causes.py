"""Unit and integration tests for Semantic Understanding and Conversation Context Root Causes.

Verifies fixes for:
1. 'give me only the upi mode transaction count' -> EXCEL_COUNT (filter: mode=UPI)
2. 'give me only the qr mode transaction' -> EXCEL_FILTER (filter: mode=QR)
3. 'can u give me as exel' / 'give me as exel sheet' -> EXCEL_EXPORT_RESULT on previous UPI result
4. Resume follow-ups ('which degree is he completed?', 'passed out year') maintain resume context
5. 'summary of this resume' after Finance queries resolves to the uploaded resume
6. Unseen variations and semantic formulations.
"""

import os
import pytest
from backend.app.schemas.department import DepartmentEnum
from backend.app.schemas.security import UserRoleEnum
from backend.app.schemas.company_ai import CompanyAIChatRequest, ConversationState, CompanyAIResult
from backend.app.services.company_ai_service import CompanyAIService
from backend.app.services.conversation_context_manager import conversation_context_manager
from backend.app.services.document_manager import document_manager
from backend.app.services.excel.semantic_excel_resolver import semantic_excel_resolver


@pytest.fixture
def company_ai():
    return CompanyAIService()


@pytest.fixture(autouse=True)
def clean_context():
    yield
    # Clean up test sessions
    for sess in ["test_upi_sess", "test_resume_sess", "test_cross_sess", "test_unseen_sess"]:
        conversation_context_manager.clear_state(sess)


def test_failure_1_upi_mode_transaction_count(company_ai):
    """Failure 1: 'give me only the upi mode transaction count' must return COUNT for UPI, NOT bank names."""
    headers = ["Bank_Name", "Unique_ID", "CRTD_DATE", "Transaction Mode", "Status", "Amount"]
    
    # 1. Semantic Excel Resolver test
    sem_req = semantic_excel_resolver.understand_request("give me only the upi mode transaction count", headers)
    assert sem_req.operation == "COUNT"
    assert sem_req.filters.get("mode") == "UPI"
    assert sem_req.operation != "UNIQUE_VALUES"
    
    # 2. Context Manager detection test
    op, owners, meta = conversation_context_manager._detect_excel_operation("give me only the upi mode transaction count")
    assert op == "EXCEL_COUNT"
    assert meta.get("filter", {}).get("mode") == "UPI"


def test_failure_2_qr_mode_transaction(company_ai):
    """Failure 2: 'give me only the qr mode transaction' must return FILTER for QR, NOT bank names."""
    headers = ["Bank_Name", "Unique_ID", "CRTD_DATE", "Transaction Mode", "Status", "Amount"]
    
    # 1. Semantic Excel Resolver test
    sem_req = semantic_excel_resolver.understand_request("give me only the qr mode transaction", headers)
    assert sem_req.operation == "FILTER"
    assert sem_req.filters.get("mode") == "QR"
    assert sem_req.operation != "UNIQUE_VALUES"
    
    # 2. Context Manager detection test
    op, owners, meta = conversation_context_manager._detect_excel_operation("give me only the qr mode transaction")
    assert op == "EXCEL_FILTER"
    assert meta.get("filter", {}).get("mode") == "QR"


def test_failure_3_and_4_export_previous_upi_result_to_excel(company_ai):
    """Failures 3 & 4: After UPI transaction details/count, 'can u give me as exel' / 'give me as exel sheet' exports UPI result."""
    session_id = "test_upi_sess"
    
    # Simulate a prior UPI transaction filter execution
    fake_upi_result = CompanyAIResult(
        department=DepartmentEnum.FINANCE,
        intent="excel_filter",
        task="Filter by Mode: UPI",
        summary="Found 593 UPI transactions totaling ₹7,12,365 in UPI_Recon.xlsx.",
        findings=["- **UPI Transactions**: **593** records", "- **Total UPI Amount**: **₹7,12,365**"],
        citations=["UPI_Recon.xlsx"],
        confidence=0.99,
        tool_results={
            "card_type": "metric_card",
            "title": "UPI Transactions",
            "primary_value": "593",
            "secondary_value": "Total: ₹7,12,365",
            "filter": {"mode": "UPI"},
            "source_file": "UPI_Recon.xlsx"
        }
    )
    
    conversation_context_manager.record_turn(
        session_id=session_id,
        user_message="give me the UPI transaction details",
        verified_result=fake_upi_result,
        answer="Found 593 UPI transactions totaling ₹7,12,365."
    )
    
    state = conversation_context_manager.get_state(session_id)
    assert state.last_result_type == "UPI_FILTER_RESULT"
    assert state.last_filters.get("mode") == "UPI"
    
    # Resolve follow-up: "can u give me as exel"
    sig1 = conversation_context_manager.resolve_follow_up_signals("can u give me as exel", state)
    assert sig1["is_follow_up"] is True
    assert sig1["target_action"] == "EXCEL_EXPORT_RESULT"
    assert sig1["entities"].get("last_result_type") == "UPI_FILTER_RESULT"
    assert sig1["entities"].get("last_filters", {}).get("mode") == "UPI"
    
    # Resolve follow-up: "give me as exel sheet"
    sig2 = conversation_context_manager.resolve_follow_up_signals("give me as exel sheet", state)
    assert sig2["is_follow_up"] is True
    assert sig2["target_action"] == "EXCEL_EXPORT_RESULT"


def test_failure_5_resume_educational_follow_ups(company_ai):
    """Failure 5: In resume context, 'which degree is he completed?' and 'passed out year' continue candidate inquiry."""
    session_id = "test_resume_sess"
    
    fake_doc = {
        "id": "DOC-RESUME-001",
        "filename": "Candidate_Reka_Resume.pdf",
        "document_type": "RESUME",
        "department": "HR"
    }
    conversation_context_manager.set_active_document(session_id, fake_doc)
    
    fake_resume_result = CompanyAIResult(
        department=DepartmentEnum.HR,
        intent="candidate_summary",
        task="Candidate Resume Summary",
        summary="Reka is a Senior Talent Acquisition Specialist with 5 years experience.",
        findings=["Summary of candidate"],
        citations=["Candidate_Reka_Resume.pdf"],
        confidence=0.99
    )
    
    conversation_context_manager.record_turn(
        session_id=session_id,
        user_message="summary of this resume",
        verified_result=fake_resume_result,
        answer="Summary of candidate profile."
    )
    
    state = conversation_context_manager.get_state(session_id)
    
    # Query 1: "which degree is he completed?"
    sig_deg = conversation_context_manager.resolve_follow_up_signals("which degree is he completed?", state)
    assert sig_deg["is_follow_up"] is True
    assert sig_deg["target_action"] == "CANDIDATE_EDUCATION"
    assert sig_deg["inherited_department"] == DepartmentEnum.HR.value
    
    # Query 2: "passed out year"
    sig_year = conversation_context_manager.resolve_follow_up_signals("passed out year", state)
    assert sig_year["is_follow_up"] is True
    assert sig_year["target_action"] == "CANDIDATE_EDUCATION"


def test_failure_6_resolve_resume_after_finance_conversation(company_ai):
    """Failure 6: After Finance queries, 'summary of this resume' resolves to the uploaded resume document."""
    session_id = "test_cross_sess"
    
    # 1. User uploaded resume earlier
    resume_doc = {
        "id": "DOC-RES-888",
        "filename": "Fazil_Resume.pdf",
        "document_type": "RESUME",
        "department": "HR"
    }
    conversation_context_manager.set_active_document(session_id, resume_doc)
    
    # 2. User then uploaded and worked with Finance Excel
    excel_doc = {
        "id": "DOC-FIN-999",
        "filename": "EBO_Topup_History.xlsx",
        "document_type": "EXCEL",
        "department": "FINANCE"
    }
    conversation_context_manager.set_active_document(session_id, excel_doc)
    
    state = conversation_context_manager.get_state(session_id)
    assert state.active_document_name == "EBO_Topup_History.xlsx"
    
    # 3. User asks: "summary of this resume"
    resolved = conversation_context_manager.resolve_document_for_query(session_id, "summary of this resume")
    assert resolved is not None
    assert resolved["id"] == "DOC-RES-888"
    assert resolved["filename"] == "Fazil_Resume.pdf"
    assert state.active_document_name == "Fazil_Resume.pdf"
    assert state.active_document_type == "RESUME"


def test_unseen_semantic_queries(company_ai):
    """Tests various unseen natural language formulations."""
    headers = ["Bank_Name", "Unique_ID", "CRTD_DATE", "Transaction Mode", "Status", "Amount"]
    
    # 1. "how many payments happened through UPI?" -> COUNT, filter mode=UPI
    s1 = semantic_excel_resolver.understand_request("how many payments happened through UPI?", headers)
    assert s1.operation == "COUNT"
    assert s1.filters.get("mode") == "UPI"
    
    # 2. "show me just QR transactions" -> FILTER, filter mode=QR
    s2 = semantic_excel_resolver.understand_request("show me just QR transactions", headers)
    assert s2.operation == "FILTER"
    assert s2.filters.get("mode") == "QR"
    
    # 3. "put those UPI transactions into a spreadsheet" -> EXPORT_RESULT
    s3 = semantic_excel_resolver.understand_request("put those UPI transactions into a spreadsheet", headers)
    assert s3.operation == "EXPORT_RESULT"
    
    # 4. "which payment was the largest?" -> MAX on Amount
    s4 = semantic_excel_resolver.understand_request("which payment was the largest?", headers)
    assert s4.operation == "MAX"
    assert s4.target_column == "Amount"
    
    # 5. "what banks are represented?" -> UNIQUE_VALUES on Bank Name
    s5 = semantic_excel_resolver.understand_request("what banks are represented?", headers)
    assert s5.operation == "UNIQUE_VALUES"
    assert s5.target_concept == "bank"


def test_explicit_user_scenarios(company_ai):
    """Verifies the explicit scenarios from the user's prompt."""
    headers = ["Bank_Name", "Unique_ID", "CRTD_DATE", "Transaction Mode", "Status", "Amount", "Mobile_Number"]
    
    # 1. "give me the total UPI amount" must mean FILTER Transaction Mode=UPI -> SUM Amount
    s1 = semantic_excel_resolver.understand_request("give me the total UPI amount", headers)
    assert s1.operation == "TOTAL"
    assert s1.filters.get("mode") == "UPI"
    assert s1.target_column == "Amount"

    # 2. "give me UPI transaction as Excel" must mean FILTER Transaction Mode=UPI -> EXPORT XLSX
    s2 = semantic_excel_resolver.understand_request("give me UPI transaction as Excel", headers)
    assert s2.operation == "EXPORT_RESULT"
    assert s2.filters.get("mode") == "UPI"
    assert s2.output_format == "XLSX"

    # 3. "mobile numbers as Excel" / typo "moile number column as exel" must resolve to actual mobile_number column
    res_col1 = semantic_excel_resolver.resolve_column("mobile numbers", headers, concept_hint="phone")
    assert res_col1 == "Mobile_Number"
    res_col2 = semantic_excel_resolver.resolve_column("moile number", headers, concept_hint="phone")
    assert res_col2 == "Mobile_Number"

    # 4. "QR transaction mode as Excel" must mean filter Transaction Mode=QR and export those rows
    s4 = semantic_excel_resolver.understand_request("QR transaction mode as Excel", headers)
    assert s4.operation == "EXPORT_RESULT"
    assert s4.filters.get("mode") == "QR"
    assert s4.output_format == "XLSX"

    # 5. "Excel sheet" must inherit the previous exportable result
    session_id = "test_upi_sess"
    fake_upi_result = CompanyAIResult(
        department=DepartmentEnum.FINANCE,
        intent="excel_filter",
        task="Filter by Mode: UPI",
        summary="Found 593 UPI transactions in UPI.xlsx.",
        findings=["593 UPI records"],
        citations=["UPI.xlsx"],
        confidence=0.99,
        tool_results={
            "card_type": "metric_card",
            "title": "UPI Transactions",
            "primary_value": "593",
            "filter": {"mode": "UPI"},
            "source_file": "UPI.xlsx"
        }
    )
    conversation_context_manager.record_turn(
        session_id=session_id,
        user_message="give me the UPI transaction details",
        verified_result=fake_upi_result,
        answer="Found 593 UPI transactions."
    )
    state = conversation_context_manager.get_state(session_id)
    sig = conversation_context_manager.resolve_follow_up_signals("Excel sheet", state)
    assert sig["is_follow_up"] is True
    assert sig["target_action"] == "EXCEL_EXPORT_RESULT"
    assert sig["entities"].get("last_filters", {}).get("mode") == "UPI"


def test_what_are_the_transaction_modes(company_ai):
    """'what are the transaction modes' -> UNIQUE_VALUES, column=Transaction Mode."""
    headers = ["Bank_Name", "Unique_ID", "CRTD_DATE", "Transaction Mode", "Status", "Amount", "Mobile_Number"]
    s = semantic_excel_resolver.understand_request("what are the transaction modes", headers)
    assert s.operation == "UNIQUE_VALUES"
    assert s.target_column == "Transaction Mode"
    assert s.target_concept == "mode"


def test_mobile_numbers_export_typo_resilience(company_ai):
    """'give me mobile numbers only as Excel' and 'mobil enumbers only as exel sheet' -> COLUMN_EXPORT, actual column=Mobile_Number."""
    headers = ["Bank_Name", "Unique_ID", "CRTD_DATE", "Transaction Mode", "Status", "Amount", "Mobile_Number"]
    
    # 1. Clean query
    col1 = semantic_excel_resolver.resolve_column("mobile numbers only as Excel", headers, concept_hint="phone")
    assert col1 == "Mobile_Number"
    
    # 2. Typo query
    col2 = semantic_excel_resolver.resolve_column("mobil enumbers only as exel sheet", headers, concept_hint="phone")
    assert col2 == "Mobile_Number"


def test_two_excel_comparison_mismatches(company_ai):
    """'what are the mismatches in the 2 Excel files' -> executes COMPARE/MISMATCH on both active documents."""
    session_id = "test_multi_doc_sess"
    
    doc_a = {
        "id": "DOC-A-001",
        "filename": "EBO_Topup_History.xlsx",
        "document_type": "EXCEL",
        "department": "FINANCE"
    }
    doc_b = {
        "id": "DOC-B-002",
        "filename": "UPI_QR_History.xlsx",
        "document_type": "EXCEL",
        "department": "FINANCE"
    }
    conversation_context_manager.set_active_document(session_id, doc_a)
    conversation_context_manager.set_active_document(session_id, doc_b)
    
    state = conversation_context_manager.get_state(session_id)
    assert len(state.conversation_documents) == 2
    
    sig = conversation_context_manager.resolve_follow_up_signals("what are the mismatches in the 2 Excel files", state)
    assert sig["is_follow_up"] is True
    assert sig["target_action"] in ("EXCEL_COMPARE", "EXCEL_MULTI_DOCUMENT_SUMMARY")
    assert sig["entities"].get("doc_id_a") is not None
    assert sig["entities"].get("doc_id_b") is not None
    assert sig["entities"].get("doc_id_a") != sig["entities"].get("doc_id_b")
    
    conversation_context_manager.clear_state(session_id)


def test_never_interpret_mode_as_literal_column(company_ai):
    """Never interpret 'UPI transaction', 'QR transactions', 'mobile numbers', 'bank names', etc. as literal column names before semantic interpretation."""
    headers = ["Bank_Name", "Unique_ID", "CRTD_DATE", "Transaction Mode", "Status", "Amount", "Mobile_Number"]
    
    # "give me UPI transaction details only as Excel" -> FILTER_EXPORT, Transaction Mode=UPI, not column export of "UPI transaction"
    op, owners, meta = conversation_context_manager._detect_excel_operation("give me UPI transaction details only as Excel")
    assert op != "EXCEL_COLUMN_EXPORT" or meta.get("target_column") != "UPI transaction"
    assert op in ("EXCEL_EXPORT_RESULT", "EXCEL_FILTER")
    
    # Resolver check
    s = semantic_excel_resolver.understand_request("give me UPI transaction details only as Excel", headers)
    assert s.operation == "EXPORT_RESULT"
    assert s.filters.get("mode") == "UPI"

