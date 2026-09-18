import os
import asyncio
import pytest
from backend.app.services.recruiter.candidate_pool_store import CandidatePoolStore
from backend.app.services.hr.resume_comparator import (
    ResumeComparator,
    parse_resume_text,
    compare_resumes,
    generate_comparison_excel,
    resume_comparator,
)
from backend.app.services.routing.intent_router import IntentRouter
from backend.app.schemas.department import DepartmentEnum, RouteRequest
from backend.app.schemas.company_ai import CompanyAIResult, StructuredRequest, CompanyAIChatRequest
from backend.app.services.conversation_context_manager import (
    conversation_context_manager,
    ConversationContextManager,
    ConversationState,
)
from backend.app.services.company_ai_service import CompanyAIService


def test_candidate_pool_store_list_all_candidates_method():
    """Verify CandidatePoolStore has canonical list_all_candidates method returning actual records without mock/fake fallback."""
    store = CandidatePoolStore()
    assert hasattr(store, "list_all_candidates")
    candidates = store.list_all_candidates()
    assert isinstance(candidates, list)
    fake_names = ["Janet C", "Evlyn M", "Sample Candidate"]
    for c in candidates:
        name = c.get("candidate_name") if isinstance(c, dict) else getattr(c, "candidate_name", "")
        assert name not in fake_names or (c.get("actual_source") == "real_upload")


def test_resume_parser_factual_extraction():
    """Verify parse_resume_text extracts authentic details without guessing."""
    resume_text_evlyn = """
    EVLYN MARY
    HR Operations Specialist & Senior Talent Acquisition
    Email: evlyn@example.com | Phone: +1 555-0199
    
    PROFESSIONAL SUMMARY
    Dynamic HR Operations and Recruitment professional with 6 years of experience in talent acquisition,
    onboarding, employee relations, payroll compliance, attendance management, and HR policy execution.
    
    CORE SKILLS
    - Talent Acquisition & End-to-End Recruitment
    - HR Operations & Onboarding
    - Payroll Compliance & Statutory Benefits
    - Performance Management Systems (PMS)
    - HRIS (Workday, BambooHR)
    
    WORK EXPERIENCE
    Senior HR Executive | Acme Corp | 2021 - Present
    - Handled recruitment lifecycle for over 150 technical and managerial positions.
    - Managed employee lifecycle, documentation, grievance handling, and exit interviews.
    - Administered monthly payroll inputs and attendance tracking for 600+ employees.
    
    EDUCATION
    Master of Business Administration (MBA) in Human Resources - ABC University (2018)
    Bachelor of Commerce - XYZ College (2016)
    
    CERTIFICATIONS
    - SHRM Certified Professional (SHRM-CP)
    """
    
    parsed = parse_resume_text(resume_text_evlyn, filename="Evlyn HR OPS.pdf")
    assert "evlyn" in parsed["candidate_name"].lower()
    assert parsed["experience_years_num"] >= 6
    assert "MBA" in parsed["education"]
    assert any("Recruitment" in sk or "Talent Acquisition" in sk for sk in parsed["skills"])
    assert any("Payroll" in sk or "Compliance" in sk for sk in parsed["skills"])
    assert parsed["alignment_score"] > 60


def test_resume_parser_missing_info_handling():
    """Verify that missing fields report 'Not Mentioned' or 'Not Specified' rather than fabricating data."""
    minimal_text = """
    SHIJI JOHN
    Junior Coordinator
    Summary: Assisted with customer scheduling and office paperwork.
    """
    parsed = parse_resume_text(minimal_text, filename="Shiji_Resume (3).pdf")
    assert "shiji" in parsed["candidate_name"].lower()
    assert parsed["education"] == "Not Mentioned"
    assert parsed["email"] == "Not Mentioned"


def test_deterministic_resume_comparison():
    """Verify compare_resumes produces side-by-side criteria matrix and honest rationale."""
    doc_a = {
        "filename": "Evlyn HR OPS.pdf",
        "extracted_text": """
        Evlyn Mary
        HR Operations Specialist. 6 years of experience in HR recruitment, talent acquisition, payroll, employee relations.
        Education: MBA in HR. Certifications: SHRM-CP.
        """
    }
    doc_b = {
        "filename": "Shiji_Resume (3).pdf",
        "extracted_text": """
        Shiji John
        Operations Coordinator. 2 years in administrative support and general scheduling.
        Education: B.Com.
        """
    }
    
    comp = compare_resumes(doc_a, doc_b, target_role="HR Operations & Recruitment")
    assert "Evlyn" in comp["best_candidate"]
    assert comp["score_diff"] > 0
    assert len(comp["matrix"]) >= 5
    assert "Evlyn" in comp["recommendation_reason"]


def test_resume_comparison_excel_generation():
    """Verify Excel report generation creates valid multi-sheet workbook."""
    doc_a = {
        "filename": "Evlyn HR OPS.pdf",
        "extracted_text": "Evlyn Mary. 5 years HR Operations and Recruitment. MBA in HR."
    }
    doc_b = {
        "filename": "Shiji_Resume (3).pdf",
        "extracted_text": "Shiji John. 2 years Administrative Support. B.Com."
    }
    comp = compare_resumes(doc_a, doc_b, target_role="HR Role")
    
    wb_bytes = generate_comparison_excel(doc_a=doc_a, doc_b=doc_b, comp=comp)
    assert len(wb_bytes) > 2000
    assert wb_bytes[:2] == b"PK"


def test_intent_routing_resume_comparison():
    """Verify user comparison prompts route to HR / candidate_comparison with high confidence."""
    router = IntentRouter()
    
    prompts = [
        "compare this 2 resumes and tell me which resume is best for the hr role in detailed",
        "compare these two resumes for HR manager",
        "compare both resumes and tell me which candidate is better",
        "which resume matches this HR role better",
        "compare candidates from the uploaded resumes",
    ]
    
    for p in prompts:
        req = RouteRequest(message=p, user_role="HR_MANAGER")
        decision = router.route(request=req)
        assert decision.department == DepartmentEnum.HR, f"Failed for '{p}': got {decision.department}"
        assert decision.intent == "candidate_comparison", f"Failed for '{p}': got {decision.intent}"
        assert decision.confidence >= 0.95


def test_conversation_context_preserves_two_documents():
    """Verify ConversationContextManager preserves both resume documents and resolves them."""
    ctx_mgr = ConversationContextManager()
    session_id = "test_resume_session_001"
    
    doc1 = {
        "id": "doc_evlyn_123",
        "document_id": "doc_evlyn_123",
        "filename": "Evlyn HR OPS.pdf",
        "file_type": "PDF",
        "document_type": "RESUME",
        "raw_text": "Evlyn Mary. 6 years HR Recruitment and HR Operations. MBA in HR.",
    }
    doc2 = {
        "id": "doc_shiji_456",
        "document_id": "doc_shiji_456",
        "filename": "Shiji_Resume (3).pdf",
        "file_type": "PDF",
        "document_type": "RESUME",
        "raw_text": "Shiji John. 2 years Admin Coordinator. B.Com.",
    }
    
    ctx_mgr.set_active_document(session_id, doc1)
    ctx_mgr.set_active_document(session_id, doc2)
    
    state = ctx_mgr.get_state(session_id)
    assert len(state.documents) == 2
    assert any(d.get("id") == "doc_evlyn_123" for d in state.documents)
    assert any(d.get("id") == "doc_shiji_456" for d in state.documents)
    
    # Test document resolution for comparison
    doc_a, doc_b = ctx_mgr.resolve_comparison_documents(
        session_id=session_id,
        text="compare this 2 resumes and tell me which resume is best for the hr role in detailed"
    )
    assert doc_a is not None
    assert doc_b is not None
    assert {doc_a.get("id"), doc_b.get("id")} == {"doc_evlyn_123", "doc_shiji_456"}


def test_follow_up_context_details_and_excel():
    """Verify follow-up queries retain the two comparison documents."""
    ctx_mgr = ConversationContextManager()
    session_id = "test_resume_session_002"
    
    doc1 = {
        "id": "doc_evlyn_123",
        "document_id": "doc_evlyn_123",
        "filename": "Evlyn HR OPS.pdf",
        "file_type": "PDF",
        "document_type": "RESUME",
        "raw_text": "Evlyn Mary. 6 years HR Recruitment and HR Operations. MBA in HR.",
    }
    doc2 = {
        "id": "doc_shiji_456",
        "document_id": "doc_shiji_456",
        "filename": "Shiji_Resume (3).pdf",
        "file_type": "PDF",
        "document_type": "RESUME",
        "raw_text": "Shiji John. 2 years Admin Coordinator. B.Com.",
    }
    ctx_mgr.set_active_document(session_id, doc1)
    ctx_mgr.set_active_document(session_id, doc2)
    
    # First turn
    dummy_res = CompanyAIResult(
        department=DepartmentEnum.HR,
        intent="candidate_comparison",
        task="Resume Intelligence Comparison",
        summary="Compared Evlyn vs Shiji",
        status="success",
        authorized=True,
    )
    ctx_mgr.record_turn(
        session_id=session_id,
        user_message="compare this 2 resumes",
        verified_result=dummy_res,
        answer="Compared Evlyn vs Shiji",
        structured_req=None,
    )
    
    # Follow-up: "give me more details"
    state = ctx_mgr.get_state(session_id)
    signals_details = ctx_mgr.resolve_follow_up_signals("give me more details", state)
    assert signals_details["is_follow_up"] is True
    assert signals_details["entities"].get("doc_id_a") is not None
    assert signals_details["entities"].get("doc_id_b") is not None
    
    # Follow-up: "create an Excel comparison report"
    signals_excel = ctx_mgr.resolve_follow_up_signals("create an Excel comparison report", state)
    assert signals_excel["is_follow_up"] is True
    assert signals_excel["entities"].get("doc_id_a") is not None
    assert signals_excel["entities"].get("doc_id_b") is not None


def test_end_to_end_resume_comparison_chat():
    """Verify CompanyAIService processes resume comparison request end-to-end without CandidatePoolStore error."""
    service = CompanyAIService()
    session_id = "test_e2e_resume_session_99"
    
    doc1 = {
        "id": "doc_evlyn_001",
        "document_id": "doc_evlyn_001",
        "filename": "Evlyn HR OPS.pdf",
        "file_type": "PDF",
        "document_type": "RESUME",
        "raw_text": """
        EVLYN MARY
        6 Years Experience in HR Operations & Talent Acquisition.
        Key Skills: Recruitment, Onboarding, Payroll, Employee Engagement, HR Policies.
        Education: MBA in HR. Certifications: SHRM-CP.
        """,
    }
    doc2 = {
        "id": "doc_shiji_002",
        "document_id": "doc_shiji_002",
        "filename": "Shiji_Resume (3).pdf",
        "file_type": "PDF",
        "document_type": "RESUME",
        "raw_text": """
        SHIJI JOHN
        2 Years Experience in Admin Coordination.
        Key Skills: Scheduling, Office Administration, Travel Coordination.
        Education: B.Com.
        """,
    }
    conversation_context_manager.set_active_document(session_id, doc1)
    conversation_context_manager.set_active_document(session_id, doc2)
    
    req = CompanyAIChatRequest(
        message="compare this 2 resumes and tell me which resume is best for the hr role in detailed",
        conversation_id=session_id,
        user_role="HR_MANAGER",
        username="hr_lead",
    )
    
    resp = service.process_chat(req)
    
    assert resp.department == "HR"
    assert resp.intent == "candidate_comparison"
    assert resp.status == "success"
    assert "Evlyn" in resp.answer
    assert "Shiji" in resp.answer
    assert resp.tool_results is not None
    assert resp.tool_results.get("card_type") == "resume_comparison"
    assert len(resp.files) > 0
