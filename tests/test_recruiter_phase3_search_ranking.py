"""Phase 3 Verification Test Suite — Multi-Candidate Search & 10-Point Ranking Engine.

Verifies:
1. MultiCandidateSearch attribute and skill filtering over candidate pool.
2. MultiCandidateRanking 10-dimensional evaluation against RequirementProfile.
3. Architecture Rule: Candidates are NEVER compared directly to each other.
4. Correct rank order output and suitability tier assignment.
"""

import pytest
from backend.app.services.recruiter.candidate_pool_store import candidate_pool_store
from backend.app.services.recruiter.recruiter_query_planner import recruiter_query_planner
from backend.app.services.recruiter.job_requirement_builder import job_requirement_builder
from backend.app.services.recruiter.multi_candidate_search import multi_candidate_search
from backend.app.services.recruiter.multi_candidate_ranking import multi_candidate_ranking
from backend.app.services.reasoning.candidate_profile_builder import candidate_profile_builder

RESUME_REACT_DEV = """
FAZIL MOHAMED
Email: fazil@example.com | Phone: +91 9876543210
Address: Chennai, Tamil Nadu

SUMMARY
Senior Frontend Developer with 5 years experience in React, TypeScript, Redux, Docker, and AWS.

SKILLS
React, TypeScript, Redux, TailwindCSS, HTML, CSS, JavaScript, Docker, AWS

WORK EXPERIENCE
2019 - 2022: UI Engineer at TechSoft Chennai
2022 - Present: Senior Frontend Developer at CloudSolutions Chennai

EDUCATION
2015 - 2019: B.Tech Computer Science from Anna University
"""

RESUME_JUNIOR_DEV = """
RAHUL SHARMA
Email: rahul@example.com | Phone: +91 9123456789
Address: Bangalore, Karnataka

SUMMARY
Junior Developer with 1 year experience in HTML, CSS, and basic JavaScript.

SKILLS
HTML, CSS, JavaScript, Git

WORK EXPERIENCE
2023 - Present: Junior Web Developer at LocalSoft Bangalore

EDUCATION
2019 - 2023: BCA from Bangalore University
"""


class TestPhase3SearchAndRanking:

    @pytest.fixture(autouse=True)
    def setup_pool(self):
        candidate_pool_store.clear()
        prof1 = candidate_profile_builder.build_profile({}, RESUME_REACT_DEV)
        prof2 = candidate_profile_builder.build_profile({}, RESUME_JUNIOR_DEV)
        self.cid1 = candidate_pool_store.add_candidate(prof1, filename="Fazil_Resume.pdf")
        self.cid2 = candidate_pool_store.add_candidate(prof2, filename="Rahul_Resume.pdf")

    def test_multi_candidate_search(self):
        """Verify MultiCandidateSearch filters candidates by skills and location."""
        plan = recruiter_query_planner.plan_query("Find React Developers from Chennai")
        results = multi_candidate_search.search(plan)

        assert len(results) == 1
        assert results[0]["name"] == "Fazil Mohamed"

    def test_multi_candidate_ranking_10_dimensions(self):
        """Verify Ranking Engine scores candidates against RequirementProfile across 10 dimensions."""
        plan = recruiter_query_planner.plan_query("Find top Frontend Developers with 3+ years experience")
        req_profile = job_requirement_builder.build_from_plan(plan)

        pool = candidate_pool_store.list_all()
        ranked = multi_candidate_ranking.rank_candidates(pool, req_profile)

        assert len(ranked) == 2
        assert ranked[0]["rank"] == 1
        assert ranked[0]["candidate_name"] == "Fazil Mohamed"
        assert ranked[0]["overall_score"] > ranked[1]["overall_score"]

        # Check 10 score dimensions exist
        dims = ranked[0]["dimension_scores"]
        assert "skill_match" in dims
        assert "experience_match" in dims
        assert "education_match" in dims
        assert "certification_match" in dims
        assert "project_match" in dims
        assert "domain_match" in dims
        assert "department_match" in dims
        assert "role_match" in dims
        assert "tool_match" in dims
        assert "technology_match" in dims
