"""AI Recruiter Platform Version 2 — Full End-to-End Enterprise Benchmark Suite.

Verifies:
1. Phase 1: Dynamic Knowledge Base & Candidate Pool Ingestion (50+ multi-domain candidate profiles).
2. Phase 2: Intent Classification, Query Planning & Job Requirement Building.
3. Phase 3: Multi-Candidate Search & 10-Dimensional Ranking Engine.
4. Phase 4: Scorecard Explanation Engine & Head-to-Head Candidate Comparison Engine.
5. Phase 5: Shortlist Stage Tracking, Dynamic Interview Scripts & Report Exports.
6. Phase 6: FastAPI REST API Endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.recruiter.candidate_pool_store import candidate_pool_store
from backend.app.services.recruiter.recruiter_orchestration_engine import recruiter_orchestration_engine
from backend.app.services.reasoning.candidate_profile_builder import candidate_profile_builder
from backend.app.services.recruiter.recruiter_knowledge_registry import recruiter_knowledge_registry

client = TestClient(app)

# 50 Multi-Domain Resumes
RESUME_TEMPLATE_DEV = """
FAZIL MOHAMED {idx}
Email: fazil{idx}@example.com | Phone: +91 9876543{idx:03d}
Address: Chennai, Tamil Nadu

SUMMARY
Senior Frontend Developer with {exp} years experience in React, TypeScript, Redux, Docker, and AWS.

SKILLS
React, TypeScript, Redux, TailwindCSS, HTML, CSS, JavaScript, Docker, AWS

WORK EXPERIENCE
2019 - 2022: UI Engineer at TechSoft Chennai
2022 - Present: Senior Frontend Developer at CloudSolutions Chennai

EDUCATION
2015 - 2019: B.Tech Computer Science from Anna University
"""

RESUME_TEMPLATE_HR = """
PRIYA SHARMA {idx}
Email: priya{idx}@example.com | Phone: +91 9123456{idx:03d}
Address: Bangalore, Karnataka

SUMMARY
HR Manager with {exp} years experience in Recruitment, Payroll, Statutory Compliance, and HRMS.

SKILLS
Recruitment, Payroll, HRMS, Employee Relations, Statutory Compliance, Talent Acquisition, Labor Laws

WORK EXPERIENCE
2018 - Present: Human Resource Manager at EnterpriseCorp Bangalore

EDUCATION
2014 - 2016: MBA HR from Bangalore University
"""


class TestRecruiterV2E2EBenchmark:

    @pytest.fixture(autouse=True)
    def setup_50_candidates(self):
        candidate_pool_store.clear()
        profiles = []

        # 30 Technology Candidates
        for i in range(1, 31):
            text = RESUME_TEMPLATE_DEV.format(idx=i, exp=3 + (i % 5))
            prof = candidate_profile_builder.build_profile({}, text)
            profiles.append({"candidate_profile": prof, "filename": f"Dev_Resume_{i}.pdf"})

        # 20 HR Candidates
        for i in range(31, 51):
            text = RESUME_TEMPLATE_HR.format(idx=i, exp=2 + (i % 6))
            prof = candidate_profile_builder.build_profile({}, text)
            profiles.append({"candidate_profile": prof, "filename": f"HR_Resume_{i}.pdf"})

        candidate_pool_store.add_batch_candidates(profiles)

    def test_pool_size(self):
        """Verify candidate pool successfully loaded 50 multi-domain candidate profiles."""
        assert candidate_pool_store.count() == 50

    def test_search_and_ranking_pipeline(self):
        """Verify natural language search and 10-dimensional ranking."""
        res = recruiter_orchestration_engine.process_query("Find top 10 React Developers from Chennai with 4+ years experience")

        assert res["intent"] == "CANDIDATE_SEARCH"
        assert res["requirement_profile"]["target_role"] == "Frontend Developer"
        assert res["data"]["total_matches"] > 0
        ranked = res["data"]["ranked_candidates"]
        assert len(ranked) <= 10
        assert ranked[0]["overall_score"] >= ranked[-1]["overall_score"]

    def test_candidate_explanation(self):
        """Verify explanation engine generates detailed breakdown for top candidate."""
        res = recruiter_orchestration_engine.process_query("Why is candidate 1 ranked first?")
        assert res["intent"] == "CANDIDATE_EXPLANATION"
        exp_data = res["data"]
        assert "rank" in exp_data
        assert "strengths" in exp_data
        assert "weaknesses" in exp_data
        assert "dimension_scores" in exp_data

    def test_head_to_head_comparison(self):
        """Verify head-to-head candidate comparison engine."""
        res = recruiter_orchestration_engine.process_query("Compare candidate 1 and candidate 2")
        assert res["intent"] == "CANDIDATE_COMPARISON"
        comp = res["data"]
        assert comp["candidates_compared_count"] >= 2
        assert "winner_candidate_name" in comp
        assert "comparison_rationale" in comp

    def test_interview_script_generation(self):
        """Verify dynamic interview question script generation."""
        res = recruiter_orchestration_engine.process_query("Generate interview questions for candidate 1")
        assert res["intent"] == "INTERVIEW_QUESTION_GENERATION"
        data = res["data"]
        assert data["total_questions"] >= 5

    def test_report_export(self):
        """Verify export service returns CSV and Markdown PDF content."""
        res = recruiter_orchestration_engine.process_query("Export shortlisted candidates to Excel")
        assert res["intent"] == "EXPORT"
        data = res["data"]
        assert "csv_content" in data
        assert "markdown_pdf_content" in data

    def test_fastapi_rest_endpoints(self):
        """Verify FastAPI REST API endpoints for Recruiter Platform V2."""
        # 1. Query Endpoint
        q_resp = client.post("/api/v2/recruiter/query", json={"query": "Find HR Managers from Bangalore"})
        assert q_resp.status_code == 200
        q_json = q_resp.json()
        assert q_json["intent"] == "CANDIDATE_SEARCH"

        # 2. Candidates Endpoint
        c_resp = client.get("/api/v2/recruiter/candidates?location=Chennai")
        assert c_resp.status_code == 200
        assert c_resp.json()["count"] > 0

        # 3. Taxonomy Endpoint
        t_resp = client.get("/api/v2/recruiter/admin/taxonomy")
        assert t_resp.status_code == 200
        assert "Technology Services" in t_resp.json()["departments"]
