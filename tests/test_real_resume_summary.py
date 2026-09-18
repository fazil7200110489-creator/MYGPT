"""Test suite testing real document summary and follow-up sequence."""

import pytest
from backend.app.schemas.company_ai import CompanyAIChatRequest
from backend.app.schemas.security import UserRoleEnum
from backend.app.services.company_ai_service import company_ai_service
from backend.app.services.conversation_context_manager import conversation_context_manager


def test_resume_summary_followup_chain():
    """Tests the exact scenario:
    1. Upload Shiji_Resume (3).pdf
    2. Ask: "Summarize this document"
    3. Ask: "give me that in Excel"
    4. Ask: "what is the purpose of this document?"
    5. Ask: "create an offer letter for Shiji as Lead Architect, salary $160,000, start date 1 Nov 2026"
    """
    session_id = "test_shiji_resume_flow"
    company_ai_service.clear_history(session_id)

    resume_text = (
        "Shiji Kumar\n"
        "Lead Software Architect & Full Stack Engineer\n"
        "Email: shiji.kumar@example.com | Phone: +1 555-0199\n\n"
        "Professional Summary:\n"
        "Over 10 years of experience designing high-scale cloud platforms, microservices architectures, and distributed databases.\n\n"
        "Technical Skills:\n"
        "Python, FastAPI, TypeScript, React, Docker, Kubernetes, PostgreSQL, Redis, AWS.\n\n"
        "Work Experience:\n"
        "Principal Architect at Global Tech Systems (2020 - Present) - Led migration of monolithic backend to event-driven microservices.\n"
        "Senior Software Engineer at Nexus Soft (2016 - 2020) - Developed real-time streaming analytics pipelines.\n\n"
        "Education:\n"
        "Bachelor of Science in Computer Engineering, State University (2016)"
    )

    # 1. Set active document as uploaded resume
    conversation_context_manager.set_active_document(session_id, {
        "document_id": "DOC-SHIJI-RESUME-03",
        "filename": "Shiji_Resume (3).pdf",
        "file_type": ".pdf",
        "document_type": "RESUME",
        "extracted_text": resume_text,
        "structured_data": {
            "candidate_name": "Shiji Kumar",
            "email": "shiji.kumar@example.com",
            "phone": "+1 555-0199"
        }
    })

    # 2. Test A: "Summarize this document"
    req_a = CompanyAIChatRequest(
        message="Summarize this document",
        session_id=session_id,
        user_role=UserRoleEnum.HR_MANAGER
    )
    res_a = company_ai_service.process_chat(req_a)

    # Must NOT have old mock values
    assert "Candidate Name: Candidate" not in res_a.answer
    assert "$120,000" not in res_a.answer
    assert "2026-10-01" not in res_a.answer

    # Must contain real resume details
    assert "Shiji" in res_a.answer
    assert "Shiji_Resume (3).pdf" in res_a.answer
    assert res_a.intent == "document_summary"

    # 3. Test B: "give me that in Excel"
    req_b = CompanyAIChatRequest(
        message="give me that in Excel",
        session_id=session_id,
        user_role=UserRoleEnum.HR_MANAGER
    )
    res_b = company_ai_service.process_chat(req_b)

    assert len(res_b.files) > 0
    assert res_b.files[0]["filename"].endswith(".xlsx")
    assert res_b.intent == "document_export"

    # 4. Test C: "what is the purpose of this document?"
    req_c = CompanyAIChatRequest(
        message="what is the purpose of this document?",
        session_id=session_id,
        user_role=UserRoleEnum.HR_MANAGER
    )
    res_c = company_ai_service.process_chat(req_c)

    assert res_c.intent == "document_summary"
    assert "Shiji" in res_c.answer

    # 5. Test D: "create an offer letter for Shiji as Lead Architect, salary $160,000, start date 1 Nov 2026"
    req_d = CompanyAIChatRequest(
        message="create an offer letter for Shiji as Lead Architect, salary $160,000, start date 1 Nov 2026",
        session_id=session_id,
        user_role=UserRoleEnum.HR_MANAGER
    )
    res_d = company_ai_service.process_chat(req_d)

    assert res_d.intent == "offer_letter"
    assert "Shiji" in res_d.answer
    assert "Lead Architect" in res_d.answer
    assert "$160,000" in res_d.answer or "160,000" in res_d.answer
    assert len(res_d.files) > 0
    assert res_d.files[0]["filename"].endswith(".docx")
