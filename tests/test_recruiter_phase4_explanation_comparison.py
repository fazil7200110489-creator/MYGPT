"""Phase 4 Verification Test Suite — Candidate Explanation & Head-to-Head Comparison Engine.

Verifies:
1. CandidateExplanationEngine generates detailed scorecard explanations, strengths, weaknesses, and evidence.
2. CandidateComparisonEngine evaluates 2+ candidates side-by-side and declares a winner with rationale.
"""

import pytest
from backend.app.services.recruiter.candidate_pool_store import candidate_pool_store
from backend.app.services.recruiter.recruiter_query_planner import recruiter_query_planner
from backend.app.services.recruiter.job_requirement_builder import job_requirement_builder
from backend.app.services.recruiter.multi_candidate_ranking import multi_candidate_ranking
from backend.app.services.recruiter.candidate_explanation_engine import candidate_explanation_engine
from backend.app.services.recruiter.candidate_comparison_engine import candidate_comparison_engine
from backend.app.services.reasoning.candidate_profile_builder import candidate_profile_builder

RESUME_1 = """
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

RESUME_2 = """
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


class TestPhase4ExplanationAndComparison:

    @pytest.fixture(autouse=True)
    def setup_ranked_data(self):
        candidate_pool_store.clear()
        prof1 = candidate_profile_builder.build_profile({}, RESUME_1)
        prof2 = candidate_profile_builder.build_profile({}, RESUME_2)
        cid1 = candidate_pool_store.add_candidate(prof1, filename="Fazil_Resume.pdf")
        cid2 = candidate_pool_store.add_candidate(prof2, filename="Rahul_Resume.pdf")

        plan = recruiter_query_planner.plan_query("Find Frontend Developers with 3+ years experience")
        self.req_profile = job_requirement_builder.build_from_plan(plan)
        pool = candidate_pool_store.list_all()
        self.ranked_scorecards = multi_candidate_ranking.rank_candidates(pool, self.req_profile)

    def test_candidate_explanation_engine(self):
        """Verify CandidateExplanationEngine generates detailed breakdown and evidence."""
        cand_scorecard = self.ranked_scorecards[0]
        exp_report = candidate_explanation_engine.explain(cand_scorecard, self.req_profile)

        assert exp_report["candidate_name"] == "Fazil Mohamed"
        assert exp_report["rank"] == 1
        assert len(exp_report["strengths"]) > 0
        assert len(exp_report["evidence"]) > 0
        assert exp_report["confidence_score"] >= 80.0

    def test_candidate_comparison_engine_winner_selection(self):
        """Verify CandidateComparisonEngine compares candidates and declares winner with rationale."""
        comp_report = candidate_comparison_engine.compare(self.ranked_scorecards, self.req_profile)

        assert comp_report["candidates_compared_count"] == 2
        assert comp_report["winner_candidate_name"] == "Fazil Mohamed"
        assert comp_report["winner_score"] > self.ranked_scorecards[1]["overall_score"]
        assert "recommended as the top candidate" in comp_report["comparison_rationale"]
        assert len(comp_report["candidate_matrix"]) == 2
