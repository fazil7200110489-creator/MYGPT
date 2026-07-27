"""Comprehensive Automated Regression Test Suite for Multi-Resume Conversational AI Dispatcher.

Tests all 5 explicit runtime failure queries:
1. "Which one is best for Frontend Developer?" -> CANDIDATE_RANKING (RecruiterEvaluationEngine)
2. "Who knows API Integration?" -> SKILL_SEARCH (SkillSearchEngine)
3. "Give me the skills" -> SKILL_SEARCH (SkillSearchEngine)
4. "Which role do these resumes fit?" -> ROLE_RECOMMENDATION (RoleRecommendationEngine)
5. "Who is the best developer?" -> CANDIDATE_RANKING (RecruiterEvaluationEngine)

Verifies zero fallback to Generic Candidate Overview (GeneralQAEngine).
"""

import os
import sys
from loguru import logger

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.services.recruiter.candidate_pool_store import candidate_pool_store
from backend.app.services.recruiter.recruiter_orchestration_engine import recruiter_orchestration_engine
from backend.app.services.recruiter.recruiter_session_memory import recruiter_session_memory
from backend.app.services.recruiter.candidate_reference_resolver import candidate_reference_resolver


def setup_mock_candidate_pool():
    """Populate CandidatePoolStore with representative test profiles."""
    candidate_pool_store.clear()

    cand1 = {
        "candidate_id": "cand_mf",
        "name": "Mohamed Fazil",
        "email": "mohamed.fazil@gmail.com",
        "phone": "+91 9876543210",
        "address": "Chennai, Tamil Nadu",
        "designation": "Senior Frontend Developer",
        "primary_domain": "Software Development",
        "total_experience": "5 Years",
        "skills": ["React.js", "JavaScript", "TypeScript", "HTML/CSS", "Redux", "TailwindCSS", "API Integration"],
        "education": [{"degree": "B.E. Computer Science", "institution": "Anna University", "year": "2021", "cgpa": "8.5/10"}],
        "projects": [{"name": "E-Commerce Dashboard", "role": "Lead Frontend Dev", "technologies": "React, TailwindCSS, API Integration", "duration": "6 Months", "details": "Built responsive React dashboard with API Integration"}],
        "raw_text": "Mohamed Fazil Phone: +91 9876543210 Email: mohamed.fazil@gmail.com Address: Chennai, Tamil Nadu. Senior Frontend Developer with 5 years experience in React, TypeScript, and API Integration."
    }

    cand2 = {
        "candidate_id": "cand_ss",
        "name": "Sanjaya Sridhar",
        "email": "sanjaya.sridhar@gmail.com",
        "phone": "+91 9988776655",
        "address": "Chennai, Tamil Nadu",
        "designation": "Full Stack Engineer",
        "primary_domain": "Software Development",
        "total_experience": "4 Years",
        "skills": ["React.js", "Node.js", "Python", "FastAPI", "PostgreSQL", "Docker", "AWS", "MERN", "API Integration"],
        "education": [{"degree": "B.Tech Information Technology", "institution": "SRM Institute", "year": "2022"}],
        "projects": [{"name": "AI Resume Scanner", "role": "Full Stack Dev", "technologies": "FastAPI, React, Python", "duration": "4 Months", "details": "Developed backend with FastAPI and React frontend"}],
        "raw_text": "Sanjaya Sridhar Email: sanjaya.sridhar@gmail.com Location: Chennai, Tamil Nadu. Full Stack Engineer with 4 years experience in Python, AWS, and API Integration."
    }

    cand3 = {
        "candidate_id": "cand_um",
        "name": "Uma Mahesh",
        "email": "uma.mahesh@gmail.com",
        "phone": "+91 9123456789",
        "address": "Bangalore, Karnataka",
        "designation": "DevOps & Cloud Engineer",
        "primary_domain": "Cloud Infrastructure",
        "total_experience": "6 Years",
        "skills": ["AWS", "Docker", "Kubernetes", "Terraform", "Python", "Linux"],
        "education": [{"degree": "B.Sc Computer Science", "institution": "Bangalore University", "year": "2020"}],
        "projects": [{"name": "Multi-Region Cloud Deployment", "role": "DevOps Engineer", "technologies": "AWS, Terraform, Docker", "duration": "8 Months", "details": "Automated AWS Terraform infrastructure"}],
        "raw_text": "Uma Mahesh Phone: +91 9123456789 Email: uma.mahesh@gmail.com Address: Bangalore, Karnataka. DevOps Engineer with 6 years experience in AWS, Docker, Kubernetes."
    }

    candidate_pool_store.add_candidate(cand1, candidate_id="cand_mf")
    candidate_pool_store.add_candidate(cand2, candidate_id="cand_ss")
    candidate_pool_store.add_candidate(cand3, candidate_id="cand_um")

    logger.info("Test candidate pool initialized with 3 candidates.")


def run_conversational_test_suite():
    """Run 20 prompt dispatcher verification suite."""
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    setup_mock_candidate_pool()

    session_id = "dispatcher_verification_session"
    recruiter_session_memory.clear_session(session_id)

    prompts = [
        # The 5 Explicit Failure Queries
        ("1. Ranking Dispatch", "Which one is best for Frontend Developer?", "CANDIDATE_RANKING", "RecruiterEvaluationEngine"),
        ("2. Skill Search Dispatch", "Who knows API Integration?", "SKILL_SEARCH", "SkillSearchEngine"),
        ("3. Skill Search Dispatch", "Give me the skills", "SKILL_SEARCH", "SkillSearchEngine"),
        ("4. Role Recommendation Dispatch", "Which role do these resumes fit?", "ROLE_RECOMMENDATION", "RoleRecommendationEngine"),
        ("5. Ranking / Best Candidate Dispatch", "Who is the best developer?", "CANDIDATE_RANKING", "RecruiterEvaluationEngine"),

        # General Overview Queries (Intentionally Allowed to GeneralQA / Summary)
        ("6. General Overview Allowed", "Show uploaded candidates", "CANDIDATE_LIST", "CandidateListEngine"),
        ("6. General Overview Allowed", "List resumes", "CANDIDATE_LIST", "CandidateListEngine"),
        ("6. General Overview Allowed", "Overview of resumes", "CANDIDATE_SUMMARY", "CandidateSummaryEngine")
    ]

    passed_count = 0
    failed_count = 0

    print("\n" + "=" * 80)
    print("MULTI-RESUME DISPATCHER VERIFICATION & REGRESSION SUITE")
    print("=" * 80 + "\n")

    for idx, (cat, prompt, expected_intent, expected_engine) in enumerate(prompts, start=1):
        res = recruiter_orchestration_engine.process_query(raw_query=prompt, session_id=session_id)
        actual_intent = res["intent"]
        markdown_text = res["data"]["formatted"]["markdown_text"]
        verification = res.get("verification", {})

        actual_engine = verification.get("selected_engine")
        is_matched = (actual_intent == expected_intent) and (actual_engine == expected_engine)
        success = is_matched and actual_engine != "GeneralQAEngine" and bool(markdown_text.strip())

        if "General Overview Allowed" in cat:
            success = is_matched and bool(markdown_text.strip())

        if success:
            passed_count += 1
            print(f"[{idx:02d}/08] PASSED | [{cat}] Prompt: \"{prompt}\" -> Engine: {actual_engine} ✅")
        else:
            failed_count += 1
            print(f"[{idx:02d}/08] FAILED | [{cat}] Prompt: \"{prompt}\" -> Expected: {expected_intent}/{expected_engine}, Got: {actual_intent}/{actual_engine}\nVerification: {verification}\nOutput:\n{markdown_text}\n")

    print("\n" + "=" * 80)
    print(f"REGRESSION TEST SUITE SUMMARY: {passed_count}/{len(prompts)} Passed ({passed_count/len(prompts)*100:.1f}%) | {failed_count} Failed")
    print("=" * 80 + "\n")

    assert failed_count == 0, f"{failed_count} tests failed in regression verification suite!"


if __name__ == "__main__":
    run_conversational_test_suite()
