"""Phase 1 Verification Test Suite — Recruiter Knowledge Registry & Candidate Pool Store.

Verifies:
1. RecruiterKnowledgeRegistry loads dynamic department and role configurations.
2. Dynamic CRUD operations for adding/updating departments, roles, skills, and weights without source code modifications.
3. CandidatePoolStore consumes Version 1 CandidateProfile objects.
4. Batch candidate ingestion (10+ resumes), attribute filtering, and shortlist status updates.
"""

import pytest
from backend.app.services.recruiter.recruiter_knowledge_registry import recruiter_knowledge_registry
from backend.app.services.recruiter.candidate_pool_store import candidate_pool_store
from backend.app.services.reasoning.candidate_profile_builder import candidate_profile_builder

RESUME_TEXT_1 = """
FAZIL MOHAMED
Email: fazil@example.com | Phone: +91 9876543210
Address: Chennai, Tamil Nadu

SUMMARY
Senior Frontend Developer with 5 years experience in React, TypeScript, Redux, and TailwindCSS.

SKILLS
React, TypeScript, Redux, TailwindCSS, HTML, CSS, JavaScript

WORK EXPERIENCE
2019 - 2022: UI Engineer at TechSoft Chennai
2022 - Present: Senior Frontend Developer at CloudSolutions Chennai

EDUCATION
2015 - 2019: B.Tech Computer Science from Anna University
"""

RESUME_TEXT_2 = """
RAHUL SHARMA
Email: rahul@example.com | Phone: +91 9123456789
Address: Bangalore, Karnataka

SUMMARY
Backend Engineer with 4 years experience in Python, FastAPI, Django, PostgreSQL, and Docker.

WORK EXPERIENCE
2020 - 2022: Python Developer at DataCorp Bangalore
2022 - Present: Backend Developer at WebServices Bangalore

EDUCATION
2016 - 2020: BE Information Technology from VTU
"""


class TestPhase1StoreAndRegistry:

    @pytest.fixture(autouse=True)
    def reset_store(self):
        candidate_pool_store.clear()

    def test_knowledge_registry_departments_and_roles(self):
        """Verify registry loads departments and role definitions."""
        depts = recruiter_knowledge_registry.list_departments()
        assert "Technology Services" in depts
        assert "People And Culture" in depts

        fe_role = recruiter_knowledge_registry.find_role("Frontend Developer")
        assert fe_role is not None
        assert "React" in fe_role["preferred_skills"]
        assert fe_role["experience_min_years"] == 2

    def test_dynamic_crud_on_registry(self):
        """Verify dynamic addition/updating of roles without code changes."""
        new_role = {
            "role_name": "Cyber Security Specialist",
            "alternative_titles": ["Security Analyst", "InfoSec Specialist"],
            "required_skills": ["Network Security", "Penetration Testing", "SIEM"],
            "preferred_skills": ["Wireshark", "Metasploit", "Python"],
            "experience_min_years": 3,
            "skill_weight": 4.5
        }
        res = recruiter_knowledge_registry.add_or_update_role("Technology Services", new_role)
        assert res["role_name"] == "Cyber Security Specialist"

        found = recruiter_knowledge_registry.find_role("InfoSec Specialist")
        assert found is not None
        assert found["role_name"] == "Cyber Security Specialist"

    def test_candidate_pool_store_v1_profile_ingestion(self):
        """Verify candidate pool consumes V1 CandidateProfile objects."""
        prof1 = candidate_profile_builder.build_profile({}, RESUME_TEXT_1)
        prof2 = candidate_profile_builder.build_profile({}, RESUME_TEXT_2)

        cid1 = candidate_pool_store.add_candidate(prof1, filename="Fazil_Resume.pdf")
        cid2 = candidate_pool_store.add_candidate(prof2, filename="Rahul_Resume.pdf")

        assert candidate_pool_store.count() == 2

        rec1 = candidate_pool_store.get_candidate(cid1)
        assert rec1["name"] == "Fazil Mohamed"
        assert rec1["email"] == "fazil@example.com"
        assert "React" in rec1["skills"]

    def test_batch_ingestion_and_filtering(self):
        """Verify batch ingestion of 10 candidate profiles and attribute filtering."""
        batch_profiles = []
        for i in range(10):
            text = f"Name: Candidate {i}\nEmail: cand{i}@example.com\nSkills: React, Python\nLocation: Chennai"
            prof = candidate_profile_builder.build_profile({}, text)
            batch_profiles.append(prof)

        added_ids = candidate_pool_store.add_batch_candidates(batch_profiles)
        assert len(added_ids) == 10
        assert candidate_pool_store.count() == 10

        chennai_cands = candidate_pool_store.filter_candidates(location="Chennai")
        assert len(chennai_cands) == 10

    def test_candidate_status_workflow(self):
        """Verify updating candidate workflow stage."""
        prof = candidate_profile_builder.build_profile({}, RESUME_TEXT_1)
        cid = candidate_pool_store.add_candidate(prof)

        assert candidate_pool_store.get_candidate(cid)["status"] == "Unassigned"
        ok = candidate_pool_store.update_status(cid, "Shortlisted", notes="Top candidate for React role")
        assert ok is True
        assert candidate_pool_store.get_candidate(cid)["status"] == "Shortlisted"
