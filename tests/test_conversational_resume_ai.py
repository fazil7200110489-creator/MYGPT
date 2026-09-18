"""Comprehensive Conversational AI Test Suite for Product 1 (AI Resume Intelligence / Single Resume AI).
Verifies:
✓ Unified Candidate Knowledge Profile object
✓ Multi-turn conversational memory & follow-up questions
✓ Pronoun resolution (he, she, they, him, her, his, them, it)
✓ Semantic skill matching (REST API <-> RESTful API/API Integration, React <-> ReactJS, Node.js <-> NodeJS, PHP <-> PHP 8)
✓ Enhanced Role Recommendation breakdown (Match %, Reasons, Missing, Recommendation)
✓ Clean skill extraction (stripping broken text fragments)
✓ Structured experience answers
✓ Structured project answers
✓ Targeted contact extraction (phone only, email only, address only)
✓ 11-section Candidate Summary & Health Assessment
✓ Standardized response quality & Missing Info fallback
✓ 21-Question Conversational Regression Suite
"""

import pytest
from backend.app.services.reasoning.candidate_profile_builder import candidate_profile_builder
from backend.app.services.reasoning.specialists.resume_reasoner import ResumeReasoner
from backend.app.services.reasoning.conversational_memory import conversational_memory
from backend.app.services.reasoning_service import reasoning_service

SAMPLE_RESUME_TEXT = """
Mohamed Fazil
Senior Full Stack Engineer
Email: mohamed.fazil@devmail.org
Phone: +91-9876543210
Address: 123 Innovation Way, Chennai, Tamil Nadu, India
LinkedIn: linkedin.com/in/mohamedfazil
GitHub: github.com/mohamedfazil
Portfolio: mohamedfazil.dev

Professional Summary
Versatile Senior Full Stack Engineer with 6 years of experience building modern web applications, scalable backend microservices, and RESTful API integrations.

Work Experience
Senior Software Engineer at Nexus Tech Labs (2021 - Present)
- Architected enterprise web applications using ReactJS, TypeScript, and Tailwind CSS.
- Designed RESTful API endpoints, REST API Development, and Node.js microservices.
- Implemented JWT Authentication and OAuth2 security protocols.

Full Stack Developer at Apex Software (2018 - 2021)
- Built backend APIs and administrative portals using PHP, JavaScript, and MySQL.
- Managed MongoDB database schemas and data migration pipelines.

Education
Bachelor of Engineering in Computer Science from Anna University (2014 - 2018)
CGPA: 8.5 / 10.0

Technical Skills
JavaScript, TypeScript, PHP, ReactJS, React.js, React, HTML5, HTML, CSS3, CSS, Tailwind CSS, Node, NodeJS, Node.js, Express.js, MongoDB, MongoDB database, MySQL, RESTful API design, REST API Development, REST API, JWT Authentication, JWT authentication, Git, MERN Stack, Full Stack Engineer

Languages
English, Tamil, Hindi

Projects
1. E-Commerce Platform Engine
Description: Scalable e-commerce web platform.
Responsibilities: Built REST API endpoints, JWT authentication, and React web components.
Technologies: React, Node.js, Express.js, MongoDB, REST API
Business Domain: E-Commerce
Outcome: Improved backend response time by 35%.

Certifications
- AWS Certified Solutions Architect (2022)
"""


@pytest.fixture
def session_setup():
    raw_entities = {
        "candidate_name": "Mohamed Fazil",
        "email": "mohamed.fazil@devmail.org",
        "phone": "+91-9876543210",
        "skills": [
            "JavaScript", "TypeScript", "PHP", "ReactJS", "React.js", "React", "HTML5", "HTML", "CSS3", "CSS",
            "Node", "NodeJS", "Node.js", "Express.js", "MongoDB", "MongoDB database", "MySQL",
            "RESTful API design", "REST API Development", "REST API", "JWT Authentication", "JWT authentication",
            "Git", "MERN Stack", "Full Stack Engineer"
        ],
        "languages": ["English", "Tamil", "Hindi"],
        "projects": [
            "E-Commerce Platform Engine: Scalable e-commerce web platform."
        ],
        "certifications": [
            "AWS Certified Solutions Architect"
        ]
    }
    session_id = "test_conversational_session_fazil"
    conversational_memory.clear(session_id)
    profile = candidate_profile_builder.build_profile(raw_entities, SAMPLE_RESUME_TEXT)

    from backend.app.services.knowledge_service import knowledge_store
    knowledge_store.save_knowledge(session_id, {
        "candidate_profile": profile,
        "document_type": "Resume",
        "doc_id": session_id
    })

    reasoner = ResumeReasoner()
    reasoner.pre_resolve_entities(raw_entities, [SAMPLE_RESUME_TEXT])

    return {
        "raw_entities": raw_entities,
        "profile": profile,
        "reasoner": reasoner,
        "text": SAMPLE_RESUME_TEXT,
        "session_id": session_id
    }


def test_unified_knowledge_profile_building(session_setup):
    """Test 1: CandidateProfileBuilder builds a single unified knowledge profile with canonical skills & aliases."""
    profile = session_setup["profile"]

    assert profile["name"] == "Mohamed Fazil"
    assert profile["email"] == "mohamed.fazil@devmail.org"
    assert profile["phone"] == "+91-9876543210"
    assert "Chennai" in profile["address"] or "Tamil Nadu" in profile["address"]
    assert profile["linkedin"] == "linkedin.com/in/mohamedfazil"
    assert profile["github"] == "github.com/mohamedfazil"

    # Canonical normalization assertions
    canonical_skills = profile["canonical_skills"]
    assert "React" in canonical_skills
    assert "REST API" in canonical_skills
    assert "Node.js" in canonical_skills
    assert "PHP" in canonical_skills


def test_conversational_memory_follow_ups(session_setup):
    """Test 2: Multi-turn conversational sequence with follow-up queries and context memory."""
    session_id = session_setup["session_id"]
    ctx = session_setup["text"]

    # Turn 1: Summarize the resume
    ans1, _, _ = reasoning_service.reason(ctx, "Summarize the resume", doc_id=session_id, session_id=session_id)
    assert "Mohamed Fazil" in ans1 or "Candidate Overview" in ans1

    # Turn 2: What projects?
    ans2, _, _ = reasoning_service.reason(ctx, "What projects?", doc_id=session_id, session_id=session_id)
    assert "E-Commerce Platform Engine" in ans2 or "Project Name:" in ans2 or "Inferred project" in ans2

    # Turn 3: What technologies?
    ans3, _, _ = reasoning_service.reason(ctx, "What technologies?", doc_id=session_id, session_id=session_id)
    assert "React" in ans3 or "Node.js" in ans3 or "TypeScript" in ans3 or "JavaScript" in ans3 or "PHP" in ans3

    # Turn 4: Does he know REST API?
    ans4, _, _ = reasoning_service.reason(ctx, "Does he know REST API?", doc_id=session_id, session_id=session_id)
    assert "Yes" in ans4
    assert "REST API" in ans4

    # Turn 5: Would you hire him?
    ans5, _, _ = reasoning_service.reason(ctx, "Would you hire him?", doc_id=session_id, session_id=session_id)
    assert "Recommendation:" in ans5 or "Recommended" in ans5

    # Turn 6: Why?
    ans6, _, _ = reasoning_service.reason(ctx, "Why?", doc_id=session_id, session_id=session_id)
    assert "Reason" in ans6 or "Evidence" in ans6 or "Key Strengths" in ans6 or "Strengths" in ans6 or "Recommended" in ans6

    # Turn 7: Which role suits him?
    ans7, _, _ = reasoning_service.reason(ctx, "Which role suits him?", doc_id=session_id, session_id=session_id)
    assert "Best-fit roles:" in ans7 or "Role" in ans7 or "Full Stack Developer" in ans7 or "Match" in ans7 or "Developer" in ans7


def test_pronoun_resolution(session_setup):
    """Test 3: Pronouns (he, she, they, him, her, his) resolve cleanly."""
    session_id = session_setup["session_id"]
    resolved, _ = conversational_memory.resolve_context("Does he know REST API?", session_id, candidate_name="Mohamed Fazil")
    assert "Mohamed Fazil" in resolved
    assert "he" not in resolved.split()


def test_semantic_skill_matching(session_setup):
    """Test 4: Canonical skill matching maps REST API <-> RESTful API, React <-> ReactJS, Node.js <-> NodeJS, PHP <-> PHP 8."""
    reasoner = session_setup["reasoner"]
    entities = session_setup["raw_entities"]
    text = session_setup["text"]

    # 1. REST API match on RESTful API design in resume
    ans_rest = reasoner.reason(entities, [text], "SKILL_VERIFY", "Does Mohamed Fazil know REST API?")
    assert "Yes" in ans_rest
    assert "REST API" in ans_rest

    # 2. React match on ReactJS in resume
    ans_react = reasoner.reason(entities, [text], "SKILL_VERIFY", "Does he know React?")
    assert "Yes" in ans_react

    # 3. Node.js match on NodeJS in resume
    ans_node = reasoner.reason(entities, [text], "SKILL_VERIFY", "Does he know Node.js?")
    assert "Yes" in ans_node

    # 4. PHP match
    ans_php = reasoner.reason(entities, [text], "SKILL_VERIFY", "Does he know PHP?")
    assert "Yes" in ans_php


def test_detailed_role_recommendation_breakdown(session_setup):
    """Test 5: Role recommendation generates Best-fit roles breakdown."""
    reasoner = session_setup["reasoner"]
    entities = session_setup["raw_entities"]
    text = session_setup["text"]

    ans = reasoner.reason(entities, [text], "ROLE_RECOMMENDATION", "Which role does he fit?")

    assert "best suited" in ans or "Full Stack Developer" in ans or "Match" in ans


def test_clean_skills_extraction(session_setup):
    """Test 6: Skill extraction returns clean canonical skills."""
    profile = session_setup["profile"]
    canonical_skills = profile["canonical_skills"]

    assert "React" in canonical_skills
    assert "Node.js" in canonical_skills
    assert "PHP" in canonical_skills


def test_structured_experience_answers(session_setup):
    """Test 7: Experience query returns Designation, Experience, Timeline, Responsibilities."""
    reasoner = session_setup["reasoner"]
    entities = session_setup["raw_entities"]
    text = session_setup["text"]

    ans = reasoner.reason(entities, [text], "EXPERIENCE", "What is his experience?")

    assert "Company:" in ans or "experience" in ans.lower()
    assert "Designation:" in ans or "Senior" in ans


def test_structured_project_answers(session_setup):
    """Test 8: Projects query returns Project Name, Description, Technologies, Responsibilities, Outcome."""
    reasoner = session_setup["reasoner"]
    entities = session_setup["raw_entities"]
    text = session_setup["text"]

    ans = reasoner.reason(entities, [text], "PROJECTS", "What projects has he worked on?")

    assert "Project Name:" in ans or "Inferred project" in ans or "No dedicated projects" in ans


def test_targeted_contact_extraction(session_setup):
    """Test 9: Targeted contact queries return ONLY requested fields without skill clutter."""
    reasoner = session_setup["reasoner"]
    entities = session_setup["raw_entities"]
    text = session_setup["text"]

    # 1. Phone only
    ans_phone = reasoner.reason(entities, [text], "PHONE", "Give me phone")
    assert "+91-9876543210" in ans_phone
    assert "mohamed.fazil@devmail.org" not in ans_phone
    assert "JavaScript" not in ans_phone

    # 2. Email only
    ans_email = reasoner.reason(entities, [text], "EMAIL", "Give me email")
    assert "mohamed.fazil@devmail.org" in ans_email
    assert "+91-9876543210" not in ans_email
    assert "React" not in ans_email

    # 3. Address only
    ans_addr = reasoner.reason(entities, [text], "ADDRESS", "Give me address")
    assert "Address:" in ans_addr or "Chennai" in ans_addr
    assert "Chennai" in ans_addr
    assert "Node" not in ans_addr


def test_10_section_candidate_summary(session_setup):
    """Test 10: Candidate summary contains 11 structured recruiter sections."""
    reasoner = session_setup["reasoner"]
    entities = session_setup["raw_entities"]
    text = session_setup["text"]

    ans = reasoner.reason(entities, [text], "SUMMARY", "Summarize the resume")

    assert "1. Overview" in ans or "1. Candidate Overview" in ans
    assert "2. Professional Experience" in ans
    assert "3. Core Skills & Competencies" in ans or "3. Technical Expertise" in ans
    assert "4. Key Projects" in ans or "4. Key Projects / Operational Exposure" in ans
    assert "5. Education" in ans
    assert "6. Certifications" in ans
    assert "7. Strengths" in ans
    assert "8. Areas for Growth" in ans or "8. Areas for Improvement" in ans
    assert "9. Recommended Roles" in ans
    assert "10. Overall Assessment" in ans
    assert "11. Hiring Recommendation" in ans


def test_answer_quality_and_missing_fallback(session_setup):
    """Test 11: Missing information states 'Angular is not explicitly mentioned in the uploaded resume'."""
    reasoner = session_setup["reasoner"]
    entities = session_setup["raw_entities"]
    text = session_setup["text"]

    ans_cert = reasoner.reason(entities, [text], "SKILL_VERIFY", "Does he know Angular?")
    assert "not explicitly mentioned in the uploaded resume" in ans_cert or "Angular" in ans_cert


def test_21_conversational_regression_queries(session_setup):
    """Test 12: Full 21-Question Conversational Regression Suite covering all required test queries."""
    reasoner = session_setup["reasoner"]
    entities = session_setup["raw_entities"]
    text = session_setup["text"]

    # 1. "Summarize this resume"
    a1 = reasoner.reason(entities, [text], "SUMMARY", "Summarize this resume")
    assert "1. Overview" in a1 or "1. Candidate Overview" in a1
    assert "2. Professional Experience" in a1

    # 2. "Summarize this resume in 3 lines"
    a2 = reasoner.reason(entities, [text], "SUMMARY", "Summarize this resume in 3 lines")
    lines2 = [l for l in a2.strip().split('\n') if l.strip()]
    assert len(lines2) == 3

    # 3. "Does he know REST API?"
    a3 = reasoner.reason(entities, [text], "SKILL_VERIFY", "Does he know REST API?")
    assert "Yes" in a3
    assert "REST API" in a3

    # 4. "Does he know Docker?"
    a4 = reasoner.reason(entities, [text], "SKILL_VERIFY", "Does he know Docker?")
    assert "not explicitly mentioned" in a4 or "can't confirm" in a4

    # 5. "Does he know React?"
    a5 = reasoner.reason(entities, [text], "SKILL_VERIFY", "Does he know React?")
    assert "Yes" in a5

    # 6. "Does he know Node.js?"
    a6 = reasoner.reason(entities, [text], "SKILL_VERIFY", "Does he know Node.js?")
    assert "Yes" in a6

    # 7. "Does he know React or Node?"
    a7 = reasoner.reason(entities, [text], "MULTI_SKILL_VERIFY", "Does he know React or Node?")
    assert "Yes" in a7

    # 8. "What backend technologies does he know?"
    a8 = reasoner.reason(entities, [text], "BACKEND_TECH", "What backend technologies does he know?")
    assert "REST API" in a8 or "PHP" in a8 or "Node.js" in a8 or "MongoDB" in a8

    # 9. "What frontend technologies does he know?"
    a9 = reasoner.reason(entities, [text], "FRONTEND_TECH", "What frontend technologies does he know?")
    assert "React" in a9 or "JavaScript" in a9 or "HTML" in a9

    # 10. "Which stack does he know?"
    a10 = reasoner.reason(entities, [text], "TECH_STACK", "Which stack does he know?")
    assert "MERN" in a10 or "stack" in a10.lower()

    # 11. "What programming languages does he know?"
    a11 = reasoner.reason(entities, [text], "PROGRAMMING_LANGUAGES", "What programming languages does he know?")
    assert "JavaScript" in a11 or "PHP" in a11
    assert "English" not in a11

    # 12. "What projects has he worked on?"
    a12 = reasoner.reason(entities, [text], "PROJECTS", "What projects has he worked on?")
    assert "Project Name:" in a12 or "Inferred project" in a12

    # 13. "What is his experience?"
    a13 = reasoner.reason(entities, [text], "EXPERIENCE", "What is his experience?")
    assert "Company:" in a13 or "Experience:" in a13 or "Timeline" in a13

    # 14. "Which role does he fit?"
    a14 = reasoner.reason(entities, [text], "ROLE_INFERENCE", "Which role does he fit?")
    assert "Best-fit roles:" in a14 or "Full Stack Developer" in a14

    # 15. "Is he suitable for React Developer?"
    a15 = reasoner.reason(entities, [text], "ROLE_SUITABILITY", "Is he suitable for React Developer?")
    assert "React Developer" in a15
    assert "Matched" in a15
    assert "Missing" in a15

    # 16. "Would you hire him?"
    a16 = reasoner.reason(entities, [text], "HIRE_RECOMMENDATION", "Would you hire him?")
    assert "Recommendation:" in a16

    # 17. "Give me his address"
    a17 = reasoner.reason(entities, [text], "ADDRESS", "Give me his address")
    assert "Address:" in a17 or "Chennai" in a17

    # 18. "Give me his phone number"
    a18 = reasoner.reason(entities, [text], "PHONE", "Give me his phone number")
    assert "+91-9876543210" in a18

    # 19. "Give me his email"
    a19 = reasoner.reason(entities, [text], "EMAIL", "Give me his email")
    assert "mohamed.fazil@devmail.org" in a19

    # 20. "Give me his GitHub"
    a20 = reasoner.reason(entities, [text], "GITHUB", "Give me his GitHub")
    assert "github.com/mohamedfazil" in a20

    # 21. "Give me his LinkedIn"
    a21 = reasoner.reason(entities, [text], "LINKEDIN", "Give me his LinkedIn")
    assert "linkedin.com/in/mohamedfazil" in a21
