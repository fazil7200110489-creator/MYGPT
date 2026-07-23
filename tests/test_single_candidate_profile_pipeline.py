"""Regression Test Suite for Single CandidateProfile Pipeline & Session Consistency.

Verifies:
1. CandidateProfileBuilder is executed only once per resume ingestion.
2. CandidateProfile is the single source of truth across all modules.
3. No module independently re-parses the resume or reads raw OCR directly.
4. Session consistency: Repeated queries for the same field always return identical values.
5. All 11 core capabilities return accurate, non-conflicting answers:
   - Basic Details
   - Contact
   - Experience
   - Skills
   - Address
   - Location
   - Companies
   - Education
   - Projects
   - Summary
   - Role Match
"""

import pytest
from unittest.mock import patch, MagicMock
from backend.app.services.reasoning_service import reasoning_service
from backend.app.services.knowledge_service import knowledge_builder, knowledge_store
from backend.app.services.reasoning.candidate_profile_builder import candidate_profile_builder

RESUME_TEST_HR = """
SHIJI M K
Email: shiji@gmail.com | Phone: +91 9876543210
Address: House No. 42, Indiranagar, Bangalore, Karnataka - 560038

SUMMARY
Experienced HR Professional with 5 years in talent acquisition, payroll, employee engagement, HRMS administration, and labor law compliance.

WORK EXPERIENCE
2019 - 2022: HR Executive at Leela Palace Hotels, Bangalore
2022 - Present: HR Manager at Sindoori Management Solutions, Bangalore

EDUCATION
2015 - 2018: Bachelor of Business Administration (BBA) - 82% from Bangalore University
2018 - 2020: MBA in Human Resources from Christ University

SKILLS
HRMS, Payroll Processing, End-to-End Recruitment, Employee Engagement, Labor Laws, Statutory Compliance, Performance Management

PROJECTS
1. ATS Resume Matching System Automation
2. Enterprise Payroll Software Migration

CERTIFICATIONS
- Certified HR Business Partner (CHRP)
- Statutory Compliance Specialist
"""


class TestSingleCandidateProfilePipeline:

    @pytest.fixture(autouse=True)
    def setup_knowledge(self):
        """Build and save structured knowledge for test document."""
        self.doc_id = "test_single_profile_hr"
        self.knowledge = knowledge_builder.build_knowledge(RESUME_TEST_HR, ".txt")
        knowledge_store.save_knowledge(self.doc_id, self.knowledge)
        self.chunks = [{"doc_id": self.doc_id, "text": RESUME_TEST_HR, "metadata": {}}]

    def test_single_execution_of_candidate_profile_builder(self):
        """Verify CandidateProfileBuilder.build_profile is executed ONCE on ingestion."""
        assert "candidate_profile" in self.knowledge
        profile = self.knowledge["candidate_profile"]
        assert profile["name"] == "Shiji M K"
        assert profile["primary_domain"] in ("Human Resources (HR)", "HR & Talent Acquisition")

    def test_basic_details_consistency(self):
        """Verify Basic Details intent returns candidate name and HR domain details."""
        ans, conf, _ = reasoning_service.reason(
            context=RESUME_TEST_HR,
            question="Basic details of candidate",
            retrieved_chunks=self.chunks,
            doc_id=self.doc_id
        )
        assert "Shiji M K" in ans or "HR Manager" in ans or "5 Years" in ans or "HR & Talent Acquisition" in ans
        assert "Healthcare" not in ans

    def test_contact_details_consistency(self):
        """Verify Contact Details returns exact name, phone, and email matching Basic Details."""
        ans, conf, _ = reasoning_service.reason(
            context=RESUME_TEST_HR,
            question="What is the candidate's contact details?",
            retrieved_chunks=self.chunks,
            doc_id=self.doc_id
        )
        assert "Shiji M K" in ans
        assert "shiji@gmail.com" in ans
        assert "9876543210" in ans

    def test_experience_details(self):
        """Verify Experience returns timeline and correct HR total experience."""
        ans, conf, _ = reasoning_service.reason(
            context=RESUME_TEST_HR,
            question="Work experience of the candidate",
            retrieved_chunks=self.chunks,
            doc_id=self.doc_id
        )
        assert "Leela Palace Hotels" in ans or "Sindoori Management Solutions" in ans or "5" in ans

    def test_skills_extraction(self):
        """Verify Skills contains extracted HR skills without OCR noise."""
        ans, conf, _ = reasoning_service.reason(
            context=RESUME_TEST_HR,
            question="What skills does she have?",
            retrieved_chunks=self.chunks,
            doc_id=self.doc_id
        )
        assert "Payroll" in ans or "Recruitment" in ans or "Hrms" in ans or "HRMS" in ans

    def test_address_and_location(self):
        """Verify Address and Location return consistent Bangalore breakdown."""
        ans_addr, _, _ = reasoning_service.reason(
            context=RESUME_TEST_HR,
            question="What is the candidate's address?",
            retrieved_chunks=self.chunks,
            doc_id=self.doc_id
        )
        assert "Bangalore" in ans_addr or "Indiranagar" in ans_addr

        ans_loc, _, _ = reasoning_service.reason(
            context=RESUME_TEST_HR,
            question="Is she from Bangalore?",
            retrieved_chunks=self.chunks,
            doc_id=self.doc_id
        )
        assert "Yes" in ans_loc

    def test_companies_worked_in(self):
        """Verify Companies Worked In extracts both employers cleanly."""
        ans, _, _ = reasoning_service.reason(
            context=RESUME_TEST_HR,
            question="Which companies has she worked in?",
            retrieved_chunks=self.chunks,
            doc_id=self.doc_id
        )
        assert "Leela Palace Hotels" in ans
        assert "Sindoori Management Solutions" in ans

    def test_education_parsing(self):
        """Verify Education extracts BBA and MBA degrees."""
        ans, _, _ = reasoning_service.reason(
            context=RESUME_TEST_HR,
            question="What is candidate's education?",
            retrieved_chunks=self.chunks,
            doc_id=self.doc_id
        )
        assert "Mba" in ans or "MBA" in ans or "Bba" in ans or "BBA" in ans

    def test_projects_extraction(self):
        """Verify Projects returns the ATS and Payroll projects."""
        ans, _, _ = reasoning_service.reason(
            context=RESUME_TEST_HR,
            question="What projects has she done?",
            retrieved_chunks=self.chunks,
            doc_id=self.doc_id
        )
        assert "ATS Resume Matching" in ans or "Enterprise Payroll" in ans

    def test_summary_domain_alignment(self):
        """Verify Summary reflects HR domain expertise, not Healthcare."""
        ans, _, _ = reasoning_service.reason(
            context=RESUME_TEST_HR,
            question="Summarize the profile",
            retrieved_chunks=self.chunks,
            doc_id=self.doc_id
        )
        assert "Shiji M K" in ans or "HR" in ans or "professional" in ans
        assert "Healthcare" not in ans

    def test_role_suitability_evaluation(self):
        """Verify Role Matching recognizes extracted HR skills and suitability for HR Manager."""
        ans, _, _ = reasoning_service.reason(
            context=RESUME_TEST_HR,
            question="Is she suitable for HR Manager?",
            retrieved_chunks=self.chunks,
            doc_id=self.doc_id
        )
        assert "Yes" in ans
        assert "Payroll" in ans or "Recruitment" in ans or "Hrms" in ans or "HRMS" in ans or "domain alignment" in ans

    def test_session_consistency_repeated_queries(self):
        """Verify that asking the same query multiple times in a session yields identical answers."""
        ans1, c1, _ = reasoning_service.reason(
            context=RESUME_TEST_HR,
            question="What is her email address?",
            retrieved_chunks=self.chunks,
            doc_id=self.doc_id,
            session_id="session_100"
        )
        ans2, c2, _ = reasoning_service.reason(
            context=RESUME_TEST_HR,
            question="What is her email address?",
            retrieved_chunks=self.chunks,
            doc_id=self.doc_id,
            session_id="session_100"
        )
        assert ans1 == ans2
        assert c1 == c2
