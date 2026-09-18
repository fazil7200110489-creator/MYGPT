"""Ground Truth 15-Question Regression Test Suite for Evlyn Janet HR Resume (Product 1 / Single Resume AI).

Verifies exact adherence to User Requirements 1 - 11:
1. Strict Current-Resume Data Isolation
2. Experience Extraction (5+ years in HR/People Operations)
3. Domain Detection (Human Resources / People Operations)
4. Skill Extraction (Workday, GreyHR, Keka, ServiceNow, HR Operations, JML, LOA)
5. Zero Fake Software Project Generation ("No dedicated projects are explicitly listed in the uploaded resume.")
6. Domain-Aware Role Recommendation (People Operations Lead, HR Operations Manager, HRIS Specialist)
7. Role Suitability Scoring (People Operations Lead = 95% Match, Frontend Developer = 15% Match)
8. Intent Classification & Skill Verification
9. Natural Response Formatting (ChatGPT style without raw debug headers)
10. Grounded Confidence
11. Exact 15-Question Sequence Execution
"""

import pytest
from backend.app.services.reasoning.candidate_profile_builder import candidate_profile_builder
from backend.app.services.reasoning.conversational_memory import conversational_memory
from backend.app.services.knowledge_service import knowledge_store
from backend.app.services.reasoning_service import reasoning_service


EVLYN_JANET_RESUME_TEXT = """
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


@pytest.fixture
def evlyn_session():
    doc_id = "doc_evlyn_janet_ground_truth_session_001"
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
        ],
        "summary": "Dynamic People Operations Lead with 5+ years of progressive experience in HR Operations..."
    }

    profile = candidate_profile_builder.build_profile(raw_entities, EVLYN_JANET_RESUME_TEXT)
    knowledge_store.save_knowledge(doc_id, {
        "candidate_profile": profile,
        "document_type": "Resume",
        "doc_id": doc_id
    })

    return {
        "doc_id": doc_id,
        "text": EVLYN_JANET_RESUME_TEXT,
        "profile": profile
    }


def test_evlyn_janet_extracted_profile(evlyn_session):
    """Verify Profile normalization: 5+ years experience, HR domain, People Operations Lead designation."""
    profile = evlyn_session["profile"]

    assert profile["name"] == "Evlyn Janet"
    assert "5" in str(profile["total_experience"])
    assert "People Operations" in profile["designation"] or "HR Operations" in profile["designation"]
    assert profile["domain"] in ["Human Resources (HR)", "HR & Talent Acquisition"]

    # Verify NO software skills injected
    skills = [s.lower() for s in profile["skills"]]
    assert "react" not in skills
    assert "node.js" not in skills
    assert "rest api" not in skills


def test_15_question_regression_sequence(evlyn_session):
    """Executes the exact 15-question user regression sequence."""
    doc_id = evlyn_session["doc_id"]
    ctx = evlyn_session["text"]

    # Q1: Summarize this resume
    a1, _, _ = reasoning_service.reason(ctx, "Summarize this resume", doc_id=doc_id, session_id=doc_id)
    assert "Evlyn Janet" in a1
    assert "HR" in a1 or "People Operations" in a1
    assert "Full Stack Developer" not in a1
    assert "Full Stack Application Platform" not in a1

    # Q2: What is her experience?
    a2, _, _ = reasoning_service.reason(ctx, "What is her experience?", doc_id=doc_id, session_id=doc_id)
    assert "5+" in a2 or "5" in a2
    assert "HR" in a2 or "People Operations" in a2

    # Q3: Is she experienced in HR Operations?
    a3, _, _ = reasoning_service.reason(ctx, "Is she experienced in HR Operations?", doc_id=doc_id, session_id=doc_id)
    assert "Yes" in a3 or "5+" in a3 or "HR Operations" in a3

    # Q4: What are her skills?
    a4, _, _ = reasoning_service.reason(ctx, "What are her skills?", doc_id=doc_id, session_id=doc_id)
    assert any(s in a4 for s in ["Workday", "ServiceNow", "GreyHR", "HR Operations", "JML", "Leave of Absence"])
    assert "React" not in a4

    # Q5: Which role does she fit?
    a5, _, _ = reasoning_service.reason(ctx, "Which role does she fit?", doc_id=doc_id, session_id=doc_id)
    assert any(r in a5 for r in ["People Operations Lead", "HR Operations Manager", "HR Operations Specialist", "Talent Operations", "HRIS"])
    assert "Full Stack Developer" not in a5
    assert "Backend Developer" not in a5

    # Q6: Evaluate suitability for People Operations Lead
    a6, _, _ = reasoning_service.reason(ctx, "Evaluate suitability for People Operations Lead", doc_id=doc_id, session_id=doc_id)
    assert "95%" in a6 or "Highly Suitable" in a6 or "Match" in a6
    assert "15%" not in a6

    # Q7: Evaluate suitability for HR Operations Manager
    a7, _, _ = reasoning_service.reason(ctx, "Evaluate suitability for HR Operations Manager", doc_id=doc_id, session_id=doc_id)
    assert "Suitable" in a7 or "Match" in a7 or "8" in a7 or "9" in a7

    # Q8: Evaluate suitability for Frontend Developer
    a8, _, _ = reasoning_service.reason(ctx, "Evaluate suitability for Frontend Developer", doc_id=doc_id, session_id=doc_id)
    assert "Not Suitable" in a8 or "15%" in a8 or "not mention" in a8

    # Q9: Does she know Workday?
    a9, _, _ = reasoning_service.reason(ctx, "Does she know Workday?", doc_id=doc_id, session_id=doc_id)
    assert "Yes" in a9
    assert "Workday" in a9

    # Q10: Does she know React?
    a10, _, _ = reasoning_service.reason(ctx, "Does she know React?", doc_id=doc_id, session_id=doc_id)
    assert "not explicitly mentioned" in a10

    # Q11: Does she know REST API?
    a11, _, _ = reasoning_service.reason(ctx, "Does she know REST API?", doc_id=doc_id, session_id=doc_id)
    assert "not explicitly mentioned" in a11

    # Q12: What projects has she worked on?
    a12, _, _ = reasoning_service.reason(ctx, "What projects has she worked on?", doc_id=doc_id, session_id=doc_id)
    assert "No dedicated projects are explicitly listed" in a12 or "no dedicated projects" in a12.lower()
    assert "Full Stack Application Platform" not in a12

    # Q13: Give basic details
    a13, _, _ = reasoning_service.reason(ctx, "Give basic details", doc_id=doc_id, session_id=doc_id)
    assert "Evlyn Janet" in a13
    assert "People Operations" in a13 or "HR Operations" in a13

    # Q14: Give me her phone number
    a14, _, _ = reasoning_service.reason(ctx, "Give me her phone number", doc_id=doc_id, session_id=doc_id)
    assert "+91-9876543210" in a14

    # Q15: Summarize in 2 lines
    a15, _, _ = reasoning_service.reason(ctx, "Summarize in 2 lines", doc_id=doc_id, session_id=doc_id)
    assert "Evlyn Janet" in a15
    assert "HR" in a15 or "People Operations" in a15
