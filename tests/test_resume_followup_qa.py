"""Regression tests for Resume Follow-Up Questions and Candidate-Aware Context Routing.

Verifies:
1. Active RESUME context resolves follow-up queries referring to she/her/candidate/this person.
2. Route priority checks active_document before falling back to GENERAL.
3. Follow-up questions route to HR with intents:
   - candidate_experience ("how much experience she has", "does she have recruitment experience?")
   - candidate_role_fit_analysis ("is she fit for the hr role?")
   - candidate_skills ("what are her skills?")
   - candidate_education ("what is her education?")
   - candidate_summary / profile ("give me her professional summary")
4. Zero hallucinated data (answers come strictly from active resume text, e.g. "seven years into my HR career").
5. No active resume returns strict notice without fake candidate data.
6. Zero literal 'svg' or '<svg>' leakage.
"""

import pytest
import os
from backend.app.schemas.department import DepartmentEnum
from backend.app.schemas.security import UserRoleEnum
from backend.app.schemas.company_ai import CompanyAIChatRequest
from backend.app.services.company_ai_service import CompanyAIService
from backend.app.services.conversation_context_manager import conversation_context_manager


@pytest.fixture
def clean_services():
    service = CompanyAIService()
    return conversation_context_manager, None, service


MOCK_SHIJI_RESUME_TEXT = """
SHIJI RESUME
Senior HR Generalist & Recruitment Specialist
Email: shiji@example.com | Phone: +1-555-0199 | Location: Chicago, IL

PROFESSIONAL SUMMARY
Dynamic Human Resources professional with seven years into my HR career, driving end-to-end recruitment, talent acquisition, employee relations, and compliance across high-growth technology organizations.

KEY SKILLS
• Core Competencies: End-to-End Recruitment, Talent Acquisition, Candidate Sourcing, Interviewing, Onboarding, Employee Relations, HR Policies, Performance Management.
• HR Systems & Tools: Workday, BambooHR, LinkedIn Recruiter, Greenhouse ATS, Microsoft Excel.
• Compliance: Labor Law Compliance, Statutory Filings, POSH Compliance, HR Auditing.

WORK EXPERIENCE
Senior HR Specialist | Nexus Global Solutions (2020 – Present)
• Managed full lifecycle recruiting for technical and corporate roles across multiple business units.
• Partnered with hiring managers to define job requisitions and improved time-to-hire by 25%.
• Administered Workday HRIS and coordinated company-wide annual appraisal cycles.

HR Generalist | Apex Tech Systems (2017 – 2020)
• Spearheaded campus recruitment drives and structured employee onboarding programs.
• Maintained employee personnel records and assisted in HR compliance audits.

EDUCATION
Master of Business Administration (MBA) in Human Resource Management
University of Illinois (2015 – 2017)

Bachelor of Commerce (B.Com)
State University (2012 – 2015)
"""


def test_resume_followup_experience_routing(clean_services):
    """Test 1: Upload resume -> summarize resume -> ask 'how much experience she has' -> must route to HR (candidate_experience)."""
    context_mgr, router, service = clean_services
    session_id = "test_sess_resume_exp"

    # Step 1: Set active resume document in session
    context_mgr.set_active_document(session_id, {
        "id": "DOC-RESUME-001",
        "filename": "Shiji_Resume (3).pdf",
        "document_type": "RESUME",
        "department": "HR",
        "extracted_text": MOCK_SHIJI_RESUME_TEXT,
        "structured_data": {"candidate_name": "Shiji"}
    })

    # Step 2: Summarize document
    resp1 = service.process_chat(CompanyAIChatRequest(
        message="summarize this document",
        session_id=session_id,
        user_role=UserRoleEnum.HR_MANAGER
    ))
    assert resp1.department == "HR"
    assert resp1.intent == "document_summary"
    assert "Shiji" in resp1.answer

    # Step 3: Follow-up question referring to "she"
    resp2 = service.process_chat(CompanyAIChatRequest(
        message="how much experience she has",
        session_id=session_id,
        user_role=UserRoleEnum.HR_MANAGER
    ))

    assert resp2.department == "HR", f"Expected HR but got {resp2.department}"
    assert resp2.intent == "candidate_experience", f"Expected candidate_experience but got {resp2.intent}"
    assert "seven years" in resp2.answer.lower() or "7 years" in resp2.answer.lower()
    assert "Shiji" in resp2.answer


def test_resume_followup_role_fit_routing(clean_services):
    """Test 2: Upload resume -> ask 'is she fit for the hr role' -> must route to HR / candidate_role_fit_analysis."""
    context_mgr, router, service = clean_services
    session_id = "test_sess_resume_fit"

    context_mgr.set_active_document(session_id, {
        "id": "DOC-RESUME-002",
        "filename": "Shiji_Resume (3).pdf",
        "document_type": "RESUME",
        "department": "HR",
        "extracted_text": MOCK_SHIJI_RESUME_TEXT,
        "structured_data": {"candidate_name": "Shiji"}
    })

    resp = service.process_chat(CompanyAIChatRequest(
        message="is she fit for the hr role",
        session_id=session_id,
        user_role=UserRoleEnum.HR_MANAGER
    ))

    assert resp.department == "HR"
    assert resp.intent == "candidate_role_fit_analysis"
    assert "Role-Fit Analysis" in resp.answer or "Relevant HR Experience" in resp.answer
    assert "Shiji" in resp.answer
    assert "seven years" in resp.answer.lower() or "hr" in resp.answer.lower()


def test_resume_followup_skills(clean_services):
    """Test 3: Upload resume -> ask 'what are her skills?' -> must use active resume."""
    context_mgr, router, service = clean_services
    session_id = "test_sess_resume_skills"

    context_mgr.set_active_document(session_id, {
        "id": "DOC-RESUME-003",
        "filename": "Shiji_Resume (3).pdf",
        "document_type": "RESUME",
        "department": "HR",
        "extracted_text": MOCK_SHIJI_RESUME_TEXT,
        "structured_data": {"candidate_name": "Shiji"}
    })

    resp = service.process_chat(CompanyAIChatRequest(
        message="what are her skills?",
        session_id=session_id,
        user_role=UserRoleEnum.HR_MANAGER
    ))

    assert resp.department == "HR"
    assert resp.intent == "candidate_skills"
    assert "Recruitment" in resp.answer or "Workday" in resp.answer or "BambooHR" in resp.answer
    assert "Shiji" in resp.answer


def test_resume_followup_recruitment_experience(clean_services):
    """Test 4: Upload resume -> ask 'does she have recruitment experience?' -> must use active resume."""
    context_mgr, router, service = clean_services
    session_id = "test_sess_resume_recruit"

    context_mgr.set_active_document(session_id, {
        "id": "DOC-RESUME-004",
        "filename": "Shiji_Resume (3).pdf",
        "document_type": "RESUME",
        "department": "HR",
        "extracted_text": MOCK_SHIJI_RESUME_TEXT,
        "structured_data": {"candidate_name": "Shiji"}
    })

    resp = service.process_chat(CompanyAIChatRequest(
        message="does she have recruitment experience?",
        session_id=session_id,
        user_role=UserRoleEnum.HR_MANAGER
    ))

    assert resp.department == "HR"
    assert resp.intent == "candidate_experience"
    assert "Recruitment" in resp.answer or "recruiting" in resp.answer.lower()


def test_resume_followup_education(clean_services):
    """Test 5: Upload resume -> ask 'what is her education?' -> must use active resume."""
    context_mgr, router, service = clean_services
    session_id = "test_sess_resume_edu"

    context_mgr.set_active_document(session_id, {
        "id": "DOC-RESUME-005",
        "filename": "Shiji_Resume (3).pdf",
        "document_type": "RESUME",
        "department": "HR",
        "extracted_text": MOCK_SHIJI_RESUME_TEXT,
        "structured_data": {"candidate_name": "Shiji"}
    })

    resp = service.process_chat(CompanyAIChatRequest(
        message="what is her education?",
        session_id=session_id,
        user_role=UserRoleEnum.HR_MANAGER
    ))

    assert resp.department == "HR"
    assert resp.intent == "candidate_education"
    assert "Master of Business Administration" in resp.answer or "MBA" in resp.answer or "University of Illinois" in resp.answer


def test_no_active_resume_returns_clean_notice(clean_services):
    """Test 6: No active resume -> 'how much experience does she have?' -> do not invent candidate data."""
    context_mgr, router, service = clean_services
    session_id = "test_sess_no_resume"

    resp = service.process_chat(CompanyAIChatRequest(
        message="how much experience does she have?",
        session_id=session_id,
        user_role=UserRoleEnum.HR_MANAGER
    ))

    assert resp.department == "HR"
    assert "No candidate resume is currently active" in resp.answer
    assert "Mohamed Fazil" not in resp.answer
    assert "$120,000" not in resp.answer


def test_no_svg_text_leakage_in_response(clean_services):
    """Test 7: Frontend response must not contain literal 'svg' or '<svg>' markup."""
    context_mgr, router, service = clean_services
    session_id = "test_sess_svg_clean"

    context_mgr.set_active_document(session_id, {
        "id": "DOC-RESUME-007",
        "filename": "Shiji_Resume (3).pdf",
        "document_type": "RESUME",
        "department": "HR",
        "extracted_text": MOCK_SHIJI_RESUME_TEXT,
        "structured_data": {"candidate_name": "Shiji"}
    })

    resp = service.process_chat(CompanyAIChatRequest(
        message="summarize this document",
        session_id=session_id,
        user_role=UserRoleEnum.HR_MANAGER
    ))

    assert "<svg" not in resp.answer.lower()
    assert "</svg>" not in resp.answer.lower()
    assert "**svg**" not in resp.answer.lower()
    assert "[svg]" not in resp.answer.lower()
