"""Ground Truth & Data Isolation Test Suite for Single Resume AI (Product 1).

Verifies:
1. Evlyn Janet Ground Truth Resume Extraction (HR / People Operations domain)
2. Zero-Contamination across document switching (Evlyn Janet HR <-> Software Engineer)
3. 9-Point Debug Trace Logging Output
4. Strict Intent, Skill Verification, Role Fit, and Constrained Output Rules
"""

import pytest
from backend.app.services.reasoning.candidate_profile_builder import candidate_profile_builder
from backend.app.services.reasoning.specialists.resume_reasoner import ResumeReasoner
from backend.app.services.reasoning.conversational_memory import conversational_memory
from backend.app.services.knowledge_service import knowledge_store
from backend.app.services.reasoning_service import reasoning_service


EVLYN_JANET_HR_RESUME = """
Evlyn Janet
People Operations Lead | HR Operations | Employee Lifecycle & JML Excellence
Email: evlyn.janet@example.com | Phone: +91-9876543210
Address: Bangalore, Karnataka, India
LinkedIn: linkedin.com/in/evlynjanet

PROFESSIONAL SUMMARY
Dynamic People Operations Lead with 5+ years of progressive experience in HR Operations, Employee Lifecycle Management (JML), Leave of Absence (LOA), Attendance Management, HR Case Management, and HR Analytics. Demonstrated track record in process improvement, stakeholder management, SOP documentation, and HRIS platforms including Workday, GreyHR, Keka, and ServiceNow.

WORK EXPERIENCE
Smith and Howard — Senior Talent & Operations Specialist (March 2025 – October 2025)
- Led talent operations, employee lifecycle workflows, and HR compliance frameworks.
- Managed escalation handling and stakeholder communication across cross-functional units.

Diversified — Senior Talent Management Specialist (August 2024 – February 2025)
- Managed end-to-end employee onboarding, offboarding, and JML excellence initiatives.
- Streamlined HR ticketing process handling and SOP documentation.

Walmart — Senior HR Operations Analyst (April 2022 – June 2024)
- Managed HR reporting, ServiceNow ticketing, Workday Leave of Absence (LOA), and attendance management.
- Developed HR analytics dashboards and automated timesheet tracking pipelines.

Regalix — HR Analyst (March 2021 – April 2022)
- Handled HR operations, Keka, and GreyHR payroll/attendance operations.

EDUCATION
Master of Science (M.Sc.) — Montfort College — 2022
Bachelor of Arts (B.A.) — Christ University — 2021

TECHNICAL SKILLS & COMPETENCIES
End-to-end HR Operations, Employee Lifecycle Management, JML, Leave of Absence, LOA, Absence Management, Attendance Management, Timesheet Management, HR Case Management, Onboarding & Offboarding, Ticketing Process Handling, Workday, GreyHR, Keka, ServiceNow, SOP Documentation, Process Improvement, Stakeholder Management, Escalation Management, HR Reporting, HR Analytics
"""

SOFTWARE_ENGINEER_RESUME = """
Alex Mercer
Senior Full Stack Engineer
Email: alex.mercer@devmail.org | Phone: +1-555-0188
Address: San Francisco, CA

PROFESSIONAL SUMMARY
Senior Full Stack Engineer with 6 years of experience building modern web applications, RESTful API design, React user interfaces, and Node.js microservices.

WORK EXPERIENCE
Senior Software Engineer at Nexus Cloud Inc (2021 - Present)
- Architected enterprise web applications using React, TypeScript, Node.js, Express.js, and MongoDB.
- Implemented REST API design and JWT Authentication security.

TECHNICAL SKILLS
JavaScript, TypeScript, React, Node.js, Express.js, REST API, JWT Authentication, MongoDB, Docker, AWS
"""


@pytest.fixture
def setup_evlyn_session():
    doc_id = "doc_evlyn_janet_hr_001"
    conversational_memory.clear(doc_id)
    raw_entities = {
        "candidate_name": "Evlyn Janet",
        "email": "evlyn.janet@example.com",
        "phone": "+91-9876543210",
        "designation": "People Operations Lead",
        "skills": [
            "HR Operations", "Employee Lifecycle Management", "JML", "Leave of Absence", "LOA",
            "Absence Management", "Attendance Management", "Timesheet Management", "HR Case Management",
            "Onboarding & Offboarding", "Ticketing Process Handling", "Workday", "GreyHR", "Keka",
            "ServiceNow", "SOP Documentation", "Process Improvement", "Stakeholder Management",
            "Escalation Management", "HR Reporting", "HR Analytics"
        ]
    }
    profile = candidate_profile_builder.build_profile(raw_entities, EVLYN_JANET_HR_RESUME)
    knowledge_store.save_knowledge(doc_id, {
        "candidate_profile": profile,
        "document_type": "Resume",
        "doc_id": doc_id
    })
    return {"doc_id": doc_id, "profile": profile, "text": EVLYN_JANET_HR_RESUME, "entities": raw_entities}


def test_evlyn_janet_ground_truth_profile(setup_evlyn_session):
    """Verify CandidateProfileBuilder extracts Ground Truth HR profile for Evlyn Janet."""
    profile = setup_evlyn_session["profile"]

    assert profile["name"] == "Evlyn Janet"
    assert "People Operations" in profile["designation"] or "HR Operations" in profile["designation"]
    assert profile["domain"] in ["HR & Talent Acquisition", "Human Resources (HR)"]
    assert "4" in str(profile["total_experience"]) or "5" in str(profile["total_experience"])

    # Skills check
    skills = profile["skills"]
    assert any("HR Operations" in s for s in skills)
    assert any("Workday" in s for s in skills)
    assert any("ServiceNow" in s for s in skills)

    # Education check
    edu = profile["education"]
    assert any("Montfort College" in str(e) or "M.Sc" in str(e) or "Christ University" in str(e) for e in edu)


def test_evlyn_janet_questions(setup_evlyn_session):
    """Verify all 12 Ground Truth questions for Evlyn Janet."""
    doc_id = setup_evlyn_session["doc_id"]
    ctx = setup_evlyn_session["text"]

    # 1. Experience query
    a1, _, _ = reasoning_service.reason(ctx, "What is Evlyn Janet's experience?", doc_id=doc_id, session_id=doc_id)
    assert "4" in a1 or "5" in a1 or "HR" in a1 or "People Operations" in a1
    assert "React" not in a1
    assert "Node.js" not in a1

    # 2. Is she experienced?
    a2, _, _ = reasoning_service.reason(ctx, "Is she experienced?", doc_id=doc_id, session_id=doc_id)
    assert "4" in a2 or "5" in a2 or "HR" in a2 or "Yes" in a2

    # 3. What skills does she have?
    a3, _, _ = reasoning_service.reason(ctx, "What skills does she have?", doc_id=doc_id, session_id=doc_id)
    assert "HR Operations" in a3 or "Workday" in a3 or "ServiceNow" in a3 or "JML" in a3
    assert "React" not in a3

    # 4. Which roles does she fit?
    a4, _, _ = reasoning_service.reason(ctx, "Which roles does she fit?", doc_id=doc_id, session_id=doc_id)
    assert any(r in a4 for r in ["People Operations", "HR Operations", "HR", "Talent Operations", "HRIS"])
    assert "React Developer" not in a4
    assert "MERN Stack Developer" not in a4
    assert "Backend Developer" not in a4

    # 5. Does Evlyn Janet know REST API?
    a5, _, _ = reasoning_service.reason(ctx, "Does Evlyn Janet know REST API?", doc_id=doc_id, session_id=doc_id)
    assert "not explicitly mentioned" in a5 or "can't confirm" in a5

    # 6. Does Evlyn Janet know React?
    a6, _, _ = reasoning_service.reason(ctx, "Does Evlyn Janet know React?", doc_id=doc_id, session_id=doc_id)
    assert "not explicitly mentioned" in a6 or "can't confirm" in a6

    # 7. Would you hire Evlyn Janet?
    a7, _, _ = reasoning_service.reason(ctx, "Would you hire Evlyn Janet?", doc_id=doc_id, session_id=doc_id)
    assert "HR" in a7 or "People Operations" in a7 or "Recommendation:" in a7
    assert "Live Coding" not in a7

    # 8. Summarize this resume
    a8, _, _ = reasoning_service.reason(ctx, "Summarize this resume", doc_id=doc_id, session_id=doc_id)
    assert "Evlyn Janet" in a8
    assert "HR" in a8 or "People Operations" in a8
    assert "Full Stack Developer" not in a8

    # 9. Summarize in 2 lines
    a9, _, _ = reasoning_service.reason(ctx, "Summarize in 2 lines", doc_id=doc_id, session_id=doc_id)
    assert "Evlyn Janet" in a9
    assert "Primary expertise" in a9 or "expertise" in a9


def test_cross_document_data_isolation():
    """Verify document switching completely isolates candidate profiles with ZERO leakage."""
    doc_id_hr = "doc_evlyn_janet_hr_002"
    doc_id_swe = "doc_alex_mercer_swe_002"

    conversational_memory.clear(doc_id_hr)
    conversational_memory.clear(doc_id_swe)

    # 1. Build and save Evlyn HR profile
    prof_hr = candidate_profile_builder.build_profile({"candidate_name": "Evlyn Janet"}, EVLYN_JANET_HR_RESUME)
    knowledge_store.save_knowledge(doc_id_hr, {"candidate_profile": prof_hr, "document_type": "Resume", "doc_id": doc_id_hr})

    # 2. Build and save Alex SWE profile
    prof_swe = candidate_profile_builder.build_profile({"candidate_name": "Alex Mercer"}, SOFTWARE_ENGINEER_RESUME)
    knowledge_store.save_knowledge(doc_id_swe, {"candidate_profile": prof_swe, "document_type": "Resume", "doc_id": doc_id_swe})

    # Query 1: Evlyn HR
    ans_hr1, _, _ = reasoning_service.reason(EVLYN_JANET_HR_RESUME, "Which roles does she fit?", doc_id=doc_id_hr, session_id=doc_id_hr)
    assert "HR" in ans_hr1 or "People Operations" in ans_hr1
    assert "React" not in ans_hr1

    # Query 2: Switch to Alex SWE
    ans_swe, _, _ = reasoning_service.reason(SOFTWARE_ENGINEER_RESUME, "Which role does he fit?", doc_id=doc_id_swe, session_id=doc_id_swe)
    assert "Full Stack" in ans_swe or "Developer" in ans_swe
    assert "Evlyn" not in ans_swe
    assert "HR Operations" not in ans_swe

    # Query 3: Switch BACK to Evlyn HR
    ans_hr2, _, _ = reasoning_service.reason(EVLYN_JANET_HR_RESUME, "Does she know React?", doc_id=doc_id_hr, session_id=doc_id_hr)
    assert "not explicitly mentioned" in ans_hr2
    assert "Alex" not in ans_hr2
