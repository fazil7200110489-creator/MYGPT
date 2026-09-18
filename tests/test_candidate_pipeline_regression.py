"""Multi Resume AI Platform — End-to-End Regression Test Suite.

Automated tests covering:
1. Candidate parsing (ensuring section headings like 'Army Certificate' are never extracted as candidate names)
2. Candidate reference resolution (ensuring single-candidate queries resolve to exactly 1 candidate)
3. Contact lookup (ensuring ContactExtractionEngine outputs resolved candidate only)
4. Address lookup (ensuring AddressExtractionEngine is invoked directly)
5. Candidate details engine (verifying all 9 required fields)
6. Domain recommendation engine (verifying Best Domain, Suitable Roles, Strengths, Reason, Confidence)
7. Summary engine (ensuring string input handling without 'str' object has no attribute 'get')
8. Ranking validation (ensuring invalid candidate identities like 'Army Certificate' are excluded from ranking)
"""

import pytest
from backend.app.services.reasoning.candidate_profile_builder import candidate_profile_builder
from backend.app.services.recruiter.candidate_pool_store import candidate_pool_store
from backend.app.services.recruiter.candidate_reference_resolver import candidate_reference_resolver
from backend.app.services.recruiter.recruiter_intent_classifier import recruiter_intent_classifier, RecruiterIntent
from backend.app.services.recruiter.recruiter_orchestration_engine import (
    recruiter_orchestration_engine,
    ContactExtractionEngine,
    AddressExtractionEngine,
    CandidateDetailsEngine,
    DomainRecommendationEngine,
    CandidateSummaryEngine
)
from backend.app.services.recruiter.multi_candidate_ranking import multi_candidate_ranking
from backend.app.services.recruiter.job_requirement_builder import job_requirement_builder
from backend.app.services.recruiter.recruiter_query_planner import recruiter_query_planner


# Sample test raw resume text containing section headings like Army Certificate
RESUME_WITH_HEADING = """
Army Certificate
Curriculum Vitae

Candidate Name: Ravi Kumar
Email: ravi.kumar@example.com | Phone: +91 9876543210
Address: Chennai, Tamil Nadu

SUMMARY
Senior Software Engineer with 5 years experience in React, Python, and AWS.

EXPERIENCE
Software Engineer at TechCorp (2020 - Present)

EDUCATION
B.Tech Computer Science from Anna University (2020)

PROJECTS
E-Commerce Platform (React, Node.js)
"""

RESUME_KOMAL = """
Komal Kumari
Email: komal.k@example.com | Phone: +91 9123456789
Address: Bangalore, Karnataka

SUMMARY
HR Specialist with 4 years experience in Payroll, Recruitment, and HRMS.

EXPERIENCE
HR Executive at HRCorp Bangalore (2021 - Present)

EDUCATION
MBA HR from Bangalore University (2021)
"""

RESUME_SHEKHAR = """
Shekhar Sharma
Email: shekhar.s@example.com | Phone: +91 9988776655
Address: Mumbai, Maharashtra

SUMMARY
Backend Developer with 6 years experience in Java, Spring Boot, and PostgreSQL.

EXPERIENCE
Senior Developer at DataSys Mumbai (2019 - Present)

EDUCATION
B.E. Information Technology from Mumbai University (2019)
"""


class TestCandidatePipelineRegression:

    @pytest.fixture(autouse=True)
    def setup_pool(self):
        candidate_pool_store.clear()

        # Parse and populate test pool with candidates
        prof_ravi = candidate_profile_builder.build_profile({"candidate_name": "Ravi Kumar"}, RESUME_WITH_HEADING)
        cid_ravi = candidate_pool_store.add_candidate(prof_ravi, candidate_id="cand_ravi", filename="Ravi_Kumar.pdf")

        prof_komal = candidate_profile_builder.build_profile({"candidate_name": "Komal Kumari"}, RESUME_KOMAL)
        cid_komal = candidate_pool_store.add_candidate(prof_komal, candidate_id="cand_komal", filename="Komal_Kumari.pdf")

        prof_shekhar = candidate_profile_builder.build_profile({"candidate_name": "Shekhar Sharma"}, RESUME_SHEKHAR)
        cid_shekhar = candidate_pool_store.add_candidate(prof_shekhar, candidate_id="cand_shekhar", filename="Shekhar_Sharma.pdf")

    # 1. Candidate Parsing Tests
    def test_candidate_parsing_ignores_section_headings(self):
        """Verify section heading 'Army Certificate' is never extracted as a candidate name."""
        prof = candidate_profile_builder.build_profile({}, "Army Certificate\nWork Experience\nSummary\nEducation")
        assert prof["name"] != "Army Certificate"
        assert prof["name"] == "Not Mentioned"

        prof_valid = candidate_profile_builder.build_profile({}, RESUME_WITH_HEADING)
        assert prof_valid["name"] == "Ravi Kumar"

    # 2. Candidate Reference Resolution Tests
    def test_candidate_reference_resolution_single_candidate(self):
        """Verify queries resolve to exactly 1 candidate and do not include unrequested candidates."""
        pool = candidate_pool_store.list_all()

        cands, is_ambig = candidate_reference_resolver.resolve_candidates_with_ambiguity("Give me Ravi Kumar details", pool)
        assert len(cands) == 1
        assert (cands[0].get("candidate_name") or cands[0].get("name")) == "Ravi Kumar"
        assert not is_ambig

        cands, _ = candidate_reference_resolver.resolve_candidates_with_ambiguity("Give me only Ravi Kumar", pool)
        assert len(cands) == 1
        assert (cands[0].get("candidate_name") or cands[0].get("name")) == "Ravi Kumar"

        cands, _ = candidate_reference_resolver.resolve_candidates_with_ambiguity("Phone number of Ravi Kumar", pool)
        assert len(cands) == 1
        assert (cands[0].get("candidate_name") or cands[0].get("name")) == "Ravi Kumar"

        cands, _ = candidate_reference_resolver.resolve_candidates_with_ambiguity("Address of Shekhar", pool)
        assert len(cands) == 1
        assert (cands[0].get("candidate_name") or cands[0].get("name")) == "Shekhar Sharma"

        cands, _ = candidate_reference_resolver.resolve_candidates_with_ambiguity("Email of Komal", pool)
        assert len(cands) == 1
        assert (cands[0].get("candidate_name") or cands[0].get("name")) == "Komal Kumari"

    # 3. Contact Lookup Tests
    def test_contact_extraction_engine_single_candidate(self):
        """Verify ContactExtractionEngine outputs contact details for the resolved candidate ONLY."""
        pool = candidate_pool_store.list_all()
        ref_cands = candidate_reference_resolver.resolve_candidates("Phone number of Ravi Kumar", pool)
        assert len(ref_cands) == 1

        output = ContactExtractionEngine.execute(ref_cands, "Phone number of Ravi Kumar")
        assert "Ravi Kumar" in output
        assert "Komal Kumari" not in output
        assert "Shekhar Sharma" not in output
        assert "ravi.kumar@example.com" in output

    # 4. Address Extraction Tests
    def test_address_extraction_engine_invocation(self):
        """Verify AddressExtractionEngine is invoked for location queries without fallback to generic overview."""
        res = recruiter_orchestration_engine.process_query("Where does Shekhar live?")
        assert res["verification"]["selected_engine"] == "AddressExtractionEngine"
        assert "Shekhar Sharma" in res["data"]["formatted"]["markdown_text"]
        assert "Mumbai" in res["data"]["formatted"]["markdown_text"]

        res_addr = recruiter_orchestration_engine.process_query("Address of Ravi")
        assert res_addr["verification"]["selected_engine"] == "AddressExtractionEngine"
        assert "Ravi Kumar" in res_addr["data"]["formatted"]["markdown_text"]

    # 5. Candidate Details Engine Tests
    def test_candidate_details_engine_all_9_fields(self):
        """Verify CandidateDetailsEngine outputs all 9 required profile fields."""
        pool = candidate_pool_store.list_all()
        ref_cands = candidate_reference_resolver.resolve_candidates("Give me Ravi details", pool)

        output = CandidateDetailsEngine.execute(ref_cands, "Give me Ravi details")
        assert "Name" in output
        assert "Experience" in output
        assert "Education" in output
        assert "Skills" in output
        assert "Projects" in output
        assert "Current Role" in output
        assert "Contact" in output
        assert "Summary" in output
        assert "Recommended Roles" in output
        assert "Ravi Kumar" in output

    # 6. Domain Recommendation Engine Tests
    def test_domain_recommendation_engine_outputs(self):
        """Verify DomainRecommendationEngine outputs Best Domain, Suitable Roles, Strengths, Reason, Confidence."""
        pool = candidate_pool_store.list_all()
        res = recruiter_orchestration_engine.process_query("Which domain do these resumes fit?")

        assert res["verification"]["selected_engine"] == "DomainRecommendationEngine"
        output = res["data"]["formatted"]["markdown_text"]
        assert "Best Domain" in output
        assert "Suitable Roles" in output
        assert "Strengths" in output
        assert "Reason" in output
        assert "Confidence" in output

    # 7. Summary Runtime Bug Tests
    def test_summary_engine_handles_raw_string_and_dict_inputs(self):
        """Verify CandidateSummaryEngine handles string candidate IDs without 'str' object has no attribute 'get'."""
        # Test passing list of string candidate IDs
        string_inputs = ["cand_ravi", "cand_komal"]
        output_str = CandidateSummaryEngine.execute(string_inputs, "Summary of candidates")
        assert "Ravi Kumar" in output_str
        assert "Komal Kumari" in output_str

        # Test passing dict candidates
        dict_inputs = candidate_pool_store.list_all()
        output_dict = CandidateSummaryEngine.execute(dict_inputs, "Summary of candidates")
        assert "Ravi Kumar" in output_dict
        assert "Komal Kumari" in output_dict

    # 8. Ranking Validation Tests
    def test_ranking_excludes_invalid_headings(self):
        """Verify MultiCandidateRanking excludes invalid candidate identities like 'Army Certificate'."""
        # Add an invalid candidate record with name 'Army Certificate'
        candidate_pool_store.add_candidate({"name": "Army Certificate"}, candidate_id="cand_invalid")
        all_cands = candidate_pool_store.list_all()

        plan = recruiter_query_planner.plan_query("Rank candidates for Software Engineer")
        req = job_requirement_builder.build_from_plan(plan)

        ranked = multi_candidate_ranking.rank_candidates(all_cands, req)
        ranked_names = [r.get("candidate_name") or r.get("name") for r in ranked]

        assert "Army Certificate" not in ranked_names
        assert "Ravi Kumar" in ranked_names
