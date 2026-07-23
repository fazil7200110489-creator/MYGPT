"""Phase 5 Verification Test Suite — Shortlist Management, Interview Question Generator & Export Service.

Verifies:
1. ShortlistManagementService candidate stage updates and pipeline status summary.
2. InterviewQuestionGenerator dynamic 4-category interview question script generation.
3. RecruiterReportExportService CSV, JSON, and Markdown PDF export.
"""

import pytest
from backend.app.services.recruiter.candidate_pool_store import candidate_pool_store
from backend.app.services.recruiter.recruiter_query_planner import recruiter_query_planner
from backend.app.services.recruiter.job_requirement_builder import job_requirement_builder
from backend.app.services.recruiter.shortlist_management_service import shortlist_management_service
from backend.app.services.recruiter.interview_question_generator import interview_question_generator
from backend.app.services.recruiter.recruiter_report_export_service import recruiter_report_export_service
from backend.app.services.reasoning.candidate_profile_builder import candidate_profile_builder

RESUME_TEXT = """
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


class TestPhase5ShortlistInterviewExport:

    @pytest.fixture(autouse=True)
    def setup_data(self):
        candidate_pool_store.clear()
        prof = candidate_profile_builder.build_profile({}, RESUME_TEXT)
        self.cid = candidate_pool_store.add_candidate(prof, filename="Fazil_Resume.pdf")

        plan = recruiter_query_planner.plan_query("Find Frontend Developers with React")
        self.req_profile = job_requirement_builder.build_from_plan(plan)

    def test_shortlist_management_workflow(self):
        """Verify updating candidate workflow stage."""
        res = shortlist_management_service.update_stage(self.cid, "Shortlisted", "Top candidate")
        assert res["success"] is True
        assert res["new_stage"] == "Shortlisted"

        summary = shortlist_management_service.get_pipeline_summary()
        assert summary["Shortlisted"] == 1

    def test_interview_question_generator(self):
        """Verify dynamic interview questions generation across 4 categories."""
        cand_rec = candidate_pool_store.get_candidate(self.cid)
        report = interview_question_generator.generate_questions(cand_rec, self.req_profile)

        assert report["candidate_name"] == "Fazil Mohamed"
        assert report["total_questions"] >= 5
        cats = report["question_categories"]
        assert "technical_deep_dive" in cats
        assert "architecture_and_design" in cats
        assert "skill_gap_verification" in cats
        assert "behavioral_and_scenario" in cats

    def test_recruiter_report_export(self):
        """Verify exporting candidate records to CSV and Markdown PDF."""
        cands = candidate_pool_store.list_all()

        csv_str = recruiter_report_export_service.export_to_csv(cands)
        assert "Fazil Mohamed" in csv_str
        assert "fazil@example.com" in csv_str

        pdf_md = recruiter_report_export_service.export_to_markdown_pdf(cands, "Frontend Developer")
        assert "# AI Recruiter Platform V2" in pdf_md
        assert "Fazil Mohamed" in pdf_md
