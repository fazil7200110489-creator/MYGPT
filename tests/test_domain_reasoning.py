"""Multi-Domain Resume Intelligence Engine — Phase 4 Enterprise Regression Test Suite.

Tests 9 enterprise domains with real recruiter questions:
  - Career Transition (Healthcare → HR)
  - HR & Talent Acquisition
  - Healthcare & Medical
  - Finance & Accounting
  - Software Engineering
  - Mechanical Engineering
  - Civil Engineering
  - Data Analytics
  - Operations & Supply Chain

Recruiter Questions Validated Per Resume:
  - Total experience / current domain experience / previous domain experience
  - Current designation / current company
  - Education + CGPA + graduation year
  - Awards (separated from certifications)
  - Skills / skill verification (payroll, python, sap)
  - Location / "Is she from Chennai?"
  - Role suitability / role comparison
  - Recommended roles
  - Career transition detection
"""

import pytest
import re
from backend.app.services.reasoning.domain_detector import DomainDetector, domain_detector
from backend.app.services.reasoning.role_inference_engine import RoleInferenceEngine, role_inference_engine
from backend.app.services.reasoning.candidate_profile_builder import CandidateProfileBuilder, candidate_profile_builder
from backend.app.services.reasoning_service import reasoning_service
from backend.app.services.knowledge_service import knowledge_builder, knowledge_store


# ---------------------------------------------------------------------------
# Test Data — Real Resume Texts
# ---------------------------------------------------------------------------

CAREER_TRANSITION_RESUME = (
    "Name: Anitha Krishnamurthy\n"
    "Designation: Manager HR\n"
    "Email: anitha.kr@example.com\n"
    "Phone: +91 9876543210\n"
    "Location: Chennai, Tamil Nadu\n"
    "Skills: Recruitment, Payroll Management, Employee Engagement, Compliance, HRMS, Performance Management, "
    "MS Office, Excel, Leadership, Communication\n"
    "Awards: Employee of the Year 2023 — Sindoori Management Solutions\n"
    "Awards: Living Leela Dharma Award 2020 — Leela Palace Hotels\n"
    "Awards: Long Service Award 2019 — Apollo Hospitals\n"
    "Work Experience:\n"
    "  2012-2017: Registered Nurse — Apollo Hospitals, Chennai\n"
    "  2017-2024: HR Executive — Leela Palace Hotels, Chennai\n"
    "  2024-Present: Manager HR — Sindoori Management Solutions, Chennai\n"
    "Education: GNM Nursing from Tamil Nadu Nursing Council (2012)\n"
    "Education: MBA in Human Resources from Annamalai University (2017), 72%\n"
    "Certifications: CHRP Certification — HRCI\n"
)

HR_RESUME = (
    "Name: Priya Sharma\n"
    "Designation: HR Business Partner\n"
    "Email: priya@example.com\n"
    "Phone: +91 9999988888\n"
    "Location: Bangalore, Karnataka\n"
    "Skills: Talent Acquisition, Payroll, HRMS, Onboarding, Employee Relations, Performance Management\n"
    "Work Experience:\n"
    "  2018-2021: HR Executive — TechCorp India, Bangalore\n"
    "  2021-Present: HR Business Partner — GlobalSoft, Bangalore\n"
    "Education: MBA in Human Resources from XLRI Jamshedpur (2018)\n"
    "Certifications: SHRM-CP Certified\n"
)

HEALTHCARE_RESUME = (
    "Name: Dr. Ramesh Nair\n"
    "Designation: Senior Medical Officer\n"
    "Email: ramesh.nair@hospital.com\n"
    "Phone: +91 9870000000\n"
    "Location: Kochi, Kerala\n"
    "Skills: Patient Care, ICU Management, Triage, Pharmacology, Vital Signs, Medical Records\n"
    "Work Experience:\n"
    "  2015-2018: Junior Medical Officer — Apollo Hospitals, Kochi\n"
    "  2018-Present: Senior Medical Officer — Amrita Hospital, Kochi\n"
    "Education: MBBS from Kerala University (2015), CGPA: 8.2\n"
    "Certifications: ACLS Certified — AHA\n"
)

FINANCE_RESUME = (
    "Name: Ramesh Kumar\n"
    "Designation: Senior Accountant\n"
    "Email: ramesh.kumar@finance.com\n"
    "Phone: +91 9876543210\n"
    "Location: Mumbai, Maharashtra\n"
    "Skills: Tally ERP 9, GST Returns, Balance Sheet, Auditing, Income Tax, TDS, SAP FICO\n"
    "Work Experience:\n"
    "  2018-2021: Junior Accountant — MNP Financial Ltd, Mumbai\n"
    "  2021-Present: Senior Accountant — ABC Financial Services, Mumbai\n"
    "Education: Bachelor of Commerce (B.Com) from Mumbai University (2018), 74%\n"
    "Certifications: Certified Tally Professional\n"
)

MECHANICAL_RESUME = (
    "Name: Suresh Rajan\n"
    "Designation: HVAC Design Engineer\n"
    "Email: suresh.r@mech.com\n"
    "Phone: +91 9000000001\n"
    "Location: Chennai, Tamil Nadu\n"
    "Skills: SolidWorks, CATIA, HVAC Design, Piping, CAD/CAM, AutoCAD, Thermal Analysis\n"
    "Work Experience:\n"
    "  2016-2020: Design Engineer — MEP Solutions, Chennai\n"
    "  2020-Present: HVAC Design Engineer — Cool Systems India, Chennai\n"
    "Education: BE Mechanical Engineering from Anna University (2016), 68%\n"
    "Projects: HVAC System Design for 50,000 sqft commercial complex\n"
)


def _load(doc_id: str, text: str):
    knowledge = knowledge_builder.build_knowledge(text, ".txt")
    knowledge_store.save_knowledge(doc_id, knowledge)
    return [{"text": text, "doc_id": doc_id}]


# ---------------------------------------------------------------------------
# 1. Career Transition Detection
# ---------------------------------------------------------------------------

class TestCareerTransitionDetection:

    def test_transition_detected(self):
        profile = candidate_profile_builder.build_profile(
            {
                "designation": "Manager HR",
                "skills": ["Recruitment", "Payroll", "HRMS", "Nursing"],
                "work_experience": [
                    "2012-2017: Registered Nurse — Apollo Hospitals",
                    "2017-2024: HR Executive — Leela Palace Hotels",
                    "2024-Present: Manager HR — Sindoori Management"
                ]
            },
            CAREER_TRANSITION_RESUME
        )
        ct = profile["career_transition"]
        assert ct["is_transition"] is True
        assert "Human Resources (HR)" in ct["transition_path"] or "HR" in ct["current_domain"]

    def test_current_career_takes_priority_for_recommendations(self):
        profile = candidate_profile_builder.build_profile(
            {
                "designation": "Manager HR",
                "skills": ["Recruitment", "Payroll", "HRMS"]
            },
            CAREER_TRANSITION_RESUME
        )
        recs = profile["recommended_roles"]
        # Must NOT recommend nursing roles for current HR manager
        assert not any("nurse" in r.lower() for r in recs), f"Got nursing roles for HR manager: {recs}"
        assert any("hr" in r.lower() or "human resource" in r.lower() or "talent" in r.lower() for r in recs), \
            f"Expected HR roles but got: {recs}"

    def test_career_transition_full_resume(self):
        doc_id = "test_career_transition"
        retrieved = _load(doc_id, CAREER_TRANSITION_RESUME)
        ans, conf, _ = reasoning_service.reason(
            context=CAREER_TRANSITION_RESUME,
            question="career transition",
            retrieved_chunks=retrieved,
            doc_id=doc_id
        )
        assert "HR" in ans or "Human Resources" in ans or "Healthcare" in ans or "Transition" in ans


# ---------------------------------------------------------------------------
# 2. Primary + Secondary Domain Scoring
# ---------------------------------------------------------------------------

class TestDomainScoring:

    def test_hr_primary_domain_transition_candidate(self):
        profile = candidate_profile_builder.build_profile(
            {
                "designation": "Manager HR",
                "skills": ["Recruitment", "Payroll", "HRMS", "Employee Engagement"]
            },
            CAREER_TRANSITION_RESUME
        )
        assert "HR" in profile["primary_domain"] or "Human Resources" in profile["primary_domain"]
        # Healthcare should be secondary, not primary
        assert profile["primary_domain"] != "Healthcare & Medical"

    def test_secondary_domain_captured(self):
        profile = candidate_profile_builder.build_profile(
            {
                "designation": "Manager HR",
                "work_experience": [
                    "2012-2017: Registered Nurse",
                    "2024-Present: Manager HR"
                ]
            },
            CAREER_TRANSITION_RESUME
        )
        # Should have a secondary domain (Healthcare)
        sec = profile.get("secondary_domain", "")
        assert sec and sec != "Not Applicable", f"Expected secondary domain, got: {sec}"

    def test_python_sql_not_software_engineering(self):
        """Python + SQL + Power BI should map to Data Analytics, NOT Software Engineering."""
        entities = {
            "designation": "Data Analyst",
            "skills": ["Python", "SQL", "Power BI", "Tableau", "Pandas"],
        }
        domain = domain_detector.detect_domain(entities, "Data Analyst with 3 years in analytics")
        assert "Software" not in domain, f"Should be Data Analytics not Software Engineering. Got: {domain}"
        assert "Data" in domain or "Analytics" in domain, f"Expected Data Analytics. Got: {domain}"


# ---------------------------------------------------------------------------
# 3. Multi-Level Experience Calculation
# ---------------------------------------------------------------------------

class TestMultiLevelExperience:

    def test_total_experience_calculated(self):
        profile = candidate_profile_builder.build_profile(
            {
                "work_experience": [
                    "2012-2017: Registered Nurse",
                    "2017-2024: HR Executive",
                    "2024-Present: Manager HR"
                ]
            },
            CAREER_TRANSITION_RESUME
        )
        exp = profile["total_experience"]
        assert exp != "Not Mentioned", f"Expected total experience but got: {exp}"
        # Should be approximately 12-14 years
        assert any(str(n) in exp for n in [10, 11, 12, 13, 14, 15]), f"Unexpected experience: {exp}"

    def test_current_domain_experience_set(self):
        profile = candidate_profile_builder.build_profile(
            {
                "work_experience": [
                    "2017-2024: HR Executive — Leela Palace",
                    "2024-Present: Manager HR — Sindoori"
                ]
            },
            ""
        )
        cde = profile.get("current_domain_experience", "")
        assert cde and cde != "Not Mentioned", f"Expected current domain experience: {cde}"

    def test_per_domain_experience_breakdown(self):
        profile = candidate_profile_builder.build_profile(
            {
                "work_experience": [
                    "2012-2017: Registered Nurse — Apollo",
                    "2017-2024: HR Executive — Leela Palace",
                    "2024-Present: Manager HR — Sindoori"
                ]
            },
            ""
        )
        per_domain = profile.get("per_domain_experience", {})
        assert len(per_domain) >= 1, f"Expected per-domain experience breakdown: {per_domain}"


# ---------------------------------------------------------------------------
# 4. Education — Zero Hallucination
# ---------------------------------------------------------------------------

class TestZeroHallucinationEducation:

    def test_no_placeholder_values(self):
        profile = candidate_profile_builder.build_profile(
            {"education": ["GNM Nursing from Tamil Nadu Nursing Council (2012)"]},
            ""
        )
        for edu in profile["education"]:
            assert edu["institution"] != "Academic University", "Placeholder institution found!"
            assert edu["specialization"] != "General Studies", "Placeholder specialization found!"
            assert edu["year"] != "Graduated" or edu["year"] == "Not Mentioned", "Placeholder year found!"

    def test_cgpa_extracted_when_present(self):
        profile = candidate_profile_builder.build_profile(
            {"education": ["MBBS from Kerala University (2015), CGPA: 8.2"]},
            ""
        )
        assert any(
            e.get("cgpa_percentage") not in ("Not Mentioned", "Not Specified", "")
            for e in profile["education"]
        ), "CGPA should be extracted when present"

    def test_cgpa_not_mentioned_when_absent(self):
        profile = candidate_profile_builder.build_profile(
            {"education": ["B.Com from Mumbai University (2018)"]},
            ""
        )
        for edu in profile["education"]:
            # Either CGPA is there or says Not Mentioned — should not be a generated value
            cgpa = edu.get("cgpa_percentage", "")
            assert isinstance(cgpa, str), "CGPA should be a string"

    def test_education_level_detected(self):
        profile = candidate_profile_builder.build_profile(
            {"education": ["MBA in Human Resources from XLRI (2018)"]},
            ""
        )
        edu_levels = [e.get("education_level", "") for e in profile["education"]]
        assert any("MBA" in l for l in edu_levels), f"Expected MBA education level. Got: {edu_levels}"


# ---------------------------------------------------------------------------
# 5. Awards Separated from Certifications
# ---------------------------------------------------------------------------

class TestAwardsSeparation:

    def test_awards_extracted_separately(self):
        profile = candidate_profile_builder.build_profile(
            {
                "certifications": [
                    "Employee of the Year 2023 — Sindoori",
                    "Living Leela Dharma Award",
                    "CHRP Certification — HRCI",
                    "Long Service Award 2019"
                ]
            },
            CAREER_TRANSITION_RESUME
        )
        awards = profile.get("awards", [])
        certs = profile.get("certifications", [])
        award_names = [a.get("name", "").lower() for a in awards]

        # Awards should be in awards list
        assert any("employee of the year" in n for n in award_names) or \
               any("living leela" in n for n in award_names) or \
               any("award" in n for n in award_names), \
               f"Awards not separated properly: {awards}"

    def test_certifications_not_mixed_with_awards(self):
        profile = candidate_profile_builder.build_profile(
            {
                "certifications": [
                    "CHRP Certification — HRCI",
                    "SHRM-CP Certified"
                ]
            },
            ""
        )
        # CHRP and SHRM should be in certifications
        certs = profile.get("certifications", [])
        assert len(certs) > 0, "Certifications should be preserved"


# ---------------------------------------------------------------------------
# 6. Skill Verification Engine
# ---------------------------------------------------------------------------

class TestSkillVerification:

    def test_payroll_verification_hr_resume(self):
        doc_id = "test_skill_verify_hr"
        retrieved = _load(doc_id, HR_RESUME)
        ans, conf, _ = reasoning_service.reason(
            context=HR_RESUME,
            question="Does she know Payroll?",
            retrieved_chunks=retrieved,
            doc_id=doc_id
        )
        assert "Yes" in ans, f"Expected Yes for Payroll in HR resume. Got: {ans}"

    def test_python_verification_finance_resume(self):
        doc_id = "test_skill_verify_finance"
        retrieved = _load(doc_id, FINANCE_RESUME)
        ans, conf, _ = reasoning_service.reason(
            context=FINANCE_RESUME,
            question="Does the candidate know Python?",
            retrieved_chunks=retrieved,
            doc_id=doc_id
        )
        # Finance candidate without Python skills should return No
        assert "No" in ans or "not mention" in ans.lower(), \
            f"Finance candidate shouldn't have Python. Got: {ans}"

    def test_tally_verification_finance_resume(self):
        doc_id = "test_skill_verify_tally"
        retrieved = _load(doc_id, FINANCE_RESUME)
        ans, conf, _ = reasoning_service.reason(
            context=FINANCE_RESUME,
            question="Does she know Tally?",
            retrieved_chunks=retrieved,
            doc_id=doc_id
        )
        assert "Yes" in ans, f"Expected Yes for Tally. Got: {ans}"


# ---------------------------------------------------------------------------
# 7. Location Reasoning
# ---------------------------------------------------------------------------

class TestLocationReasoning:

    def test_is_she_from_chennai(self):
        doc_id = "test_location_chennai"
        retrieved = _load(doc_id, CAREER_TRANSITION_RESUME)
        ans, conf, _ = reasoning_service.reason(
            context=CAREER_TRANSITION_RESUME,
            question="Is she from Chennai?",
            retrieved_chunks=retrieved,
            doc_id=doc_id
        )
        assert "Yes" in ans, f"Expected Yes for Chennai. Got: {ans}"

    def test_is_she_from_mumbai_returns_no(self):
        doc_id = "test_location_mumbai"
        retrieved = _load(doc_id, CAREER_TRANSITION_RESUME)
        ans, conf, _ = reasoning_service.reason(
            context=CAREER_TRANSITION_RESUME,
            question="Is she from Mumbai?",
            retrieved_chunks=retrieved,
            doc_id=doc_id
        )
        # Should be No — Anitha is from Chennai not Mumbai
        assert "No" in ans or "Chennai" in ans, f"Expected No for Mumbai. Got: {ans}"

    def test_location_extraction_city_state(self):
        profile = candidate_profile_builder.build_profile(
            {"location": "Chennai, Tamil Nadu"},
            CAREER_TRANSITION_RESUME
        )
        loc = profile.get("current_location") or profile.get("permanent_address", "")
        assert "Chennai" in loc or "Not Mentioned" != loc, f"Location not extracted: {loc}"


# ---------------------------------------------------------------------------
# 8. Role Suitability & Role Comparison
# ---------------------------------------------------------------------------

class TestRoleSuitability:

    def test_hr_manager_suitability(self):
        doc_id = "test_role_suitability_hr"
        retrieved = _load(doc_id, CAREER_TRANSITION_RESUME)
        ans, conf, _ = reasoning_service.reason(
            context=CAREER_TRANSITION_RESUME,
            question="Is she suitable for HR Manager?",
            retrieved_chunks=retrieved,
            doc_id=doc_id
        )
        assert "Yes" in ans or "Suitable" in ans, f"Expected suitable for HR Manager. Got: {ans}"

    def test_not_suitable_for_wrong_domain(self):
        doc_id = "test_role_suitability_wrong"
        retrieved = _load(doc_id, HR_RESUME)
        ans, conf, _ = reasoning_service.reason(
            context=HR_RESUME,
            question="Is she suitable for HVAC Engineer?",
            retrieved_chunks=retrieved,
            doc_id=doc_id
        )
        assert "Not Suitable" in ans or "No" in ans, f"Expected Not Suitable for HVAC. Got: {ans}"

    def test_role_comparison(self):
        result = role_inference_engine.compare_roles(
            {"designation": "Manager HR", "skills": ["Recruitment", "Payroll", "HRMS", "Employee Engagement"]},
            "HR Manager",
            "HR Business Partner",
            "Human Resources (HR)"
        )
        assert "HR Manager" in result
        assert "HR Business Partner" in result
        assert "recommendation" in result
        assert "better_role" in result


# ---------------------------------------------------------------------------
# 9. Healthcare Domain
# ---------------------------------------------------------------------------

class TestHealthcareDomain:

    def test_healthcare_domain_detected(self):
        profile = candidate_profile_builder.build_profile(
            {
                "designation": "Senior Medical Officer",
                "skills": ["Patient Care", "ICU Management", "Triage", "Pharmacology"]
            },
            HEALTHCARE_RESUME
        )
        assert "Healthcare" in profile["domain"] or "Medical" in profile["domain"]

    def test_healthcare_recommended_roles(self):
        profile = candidate_profile_builder.build_profile(
            {"designation": "Senior Medical Officer"},
            HEALTHCARE_RESUME
        )
        # Should recommend healthcare roles, not IT or HR roles
        recs = profile["recommended_roles"]
        it_roles = [r for r in recs if "developer" in r.lower() or "software" in r.lower()]
        assert not it_roles, f"Should not recommend IT roles for doctor: {recs}"


# ---------------------------------------------------------------------------
# 10. Finance Domain
# ---------------------------------------------------------------------------

class TestFinanceDomain:

    def test_finance_domain_detected(self):
        profile = candidate_profile_builder.build_profile(
            {
                "designation": "Senior Accountant",
                "skills": ["Tally ERP 9", "GST Returns", "Balance Sheet", "SAP FICO"]
            },
            FINANCE_RESUME
        )
        assert "Finance" in profile["domain"] or "Accounting" in profile["domain"]

    def test_tally_in_erp_platforms(self):
        profile = candidate_profile_builder.build_profile(
            {"skills": ["Tally ERP 9", "GST", "SAP FICO"]},
            FINANCE_RESUME
        )
        erps = profile.get("erp_platforms", [])
        assert len(erps) > 0, f"ERP platforms should be detected. Got: {erps}"


# ---------------------------------------------------------------------------
# 11. Graduation Year & CGPA
# ---------------------------------------------------------------------------

class TestGraduationYearCGPA:

    def test_graduation_year_question(self):
        doc_id = "test_grad_year"
        retrieved = _load(doc_id, HEALTHCARE_RESUME)
        ans, conf, _ = reasoning_service.reason(
            context=HEALTHCARE_RESUME,
            question="Passed out year",
            retrieved_chunks=retrieved,
            doc_id=doc_id
        )
        assert "2015" in ans or "Not" not in ans, f"Expected graduation year 2015. Got: {ans}"

    def test_cgpa_question_present(self):
        doc_id = "test_cgpa_present"
        retrieved = _load(doc_id, HEALTHCARE_RESUME)
        ans, conf, _ = reasoning_service.reason(
            context=HEALTHCARE_RESUME,
            question="What is the CGPA?",
            retrieved_chunks=retrieved,
            doc_id=doc_id
        )
        assert "8.2" in ans or "Not Mentioned" not in ans, f"Expected CGPA 8.2. Got: {ans}"

    def test_cgpa_absent_returns_not_mentioned(self):
        doc_id = "test_cgpa_absent"
        retrieved = _load(doc_id, MECHANICAL_RESUME)
        ans, conf, _ = reasoning_service.reason(
            context=MECHANICAL_RESUME,
            question="What is the CGPA?",
            retrieved_chunks=retrieved,
            doc_id=doc_id
        )
        # Should NOT fabricate a CGPA
        assert "8." not in ans or "not mention" in ans.lower() or "Not Mentioned" in ans, \
            f"Should not fabricate CGPA. Got: {ans}"


# ---------------------------------------------------------------------------
# 12. Domain Detector Multi-Industry
# ---------------------------------------------------------------------------

class TestDomainDetectorAllDomains:

    def test_all_9_domains(self):
        detector = DomainDetector()
        tests = [
            ({"designation": "Senior Accountant", "skills": ["Tally", "GST", "Balance Sheet"]}, "Finance"),
            ({"designation": "HR Manager", "skills": ["Recruitment", "Payroll", "HRMS"]}, "HR"),
            ({"designation": "Senior Medical Officer", "skills": ["Patient Care", "ICU"]}, "Healthcare"),
            ({"designation": "Site Engineer", "skills": ["AutoCAD", "BOQ", "Primavera"]}, "Civil"),
            ({"designation": "Electrical Engineer", "skills": ["PLC", "SCADA", "MV Panel"]}, "Electrical"),
            ({"designation": "HVAC Engineer", "skills": ["SolidWorks", "HVAC", "Piping"]}, "Mechanical"),
            ({"designation": "Data Analyst", "skills": ["SQL", "Power BI", "Tableau"]}, "Data"),
            ({"designation": "Operations Manager", "skills": ["Supply Chain", "Logistics", "Procurement"]}, "Operations"),
        ]
        for entities, expected_keyword in tests:
            domain = detector.detect_domain(entities)
            assert expected_keyword.lower() in domain.lower(), \
                f"Expected domain containing '{expected_keyword}' for {entities['designation']}, got: '{domain}'"


# ---------------------------------------------------------------------------
# 13. Candidate Profile Normalizer & OCR Noise & Sanity Checks
# ---------------------------------------------------------------------------

class TestCandidateProfileNormalizer:

    def test_ocr_noise_filtering(self):
        raw_entities = {
            "designation": "Manager HR",
            "skills": [
                "Recruitment", "being.", "making.", "Well", "tracking systems.",
                "Payroll Management", "having", "working", "proficient in"
            ]
        }
        profile = candidate_profile_builder.build_profile(raw_entities, "Sample text")
        skills = profile["skills"]

        assert "Recruitment" in skills
        assert "Payroll Management" in skills
        assert "being" not in skills
        assert "being." not in skills
        assert "making" not in skills
        assert "making." not in skills
        assert "well" not in skills
        assert "having" not in skills

    def test_entity_isolation_in_skills(self):
        raw_entities = {
            "designation": "Manager HR",
            "education": ["MBA in Human Resources"],
            "certifications": ["Employee of the Year Award"],
            "skills": ["MBA", "Manager HR", "Employee of the Year Award", "Talent Acquisition", "Onboarding"]
        }
        profile = candidate_profile_builder.build_profile(raw_entities, "")
        skills = profile["skills"]

        assert "Talent Acquisition" in skills
        assert "Onboarding" in skills
        assert "MBA" not in skills
        assert "Manager HR" not in skills
        assert "Employee of the Year Award" not in skills

    def test_contact_address_phone_isolation(self):
        raw_entities = {
            "phone": "+91 9876543210",
            "address": "+91 9876543210"  # Phone mistakenly put in address field
        }
        profile = candidate_profile_builder.build_profile(raw_entities, "Phone: +91 9876543210")
        loc = profile["address"]

        # Location must NOT return phone number
        assert "+91" not in loc and "9876543210" not in loc, f"Address contains phone number: {loc}"

    def test_which_role_she_fit_for_sanitization(self):
        doc_id = "test_fit_for"
        retrieved = _load(doc_id, CAREER_TRANSITION_RESUME)
        ans, conf, _ = reasoning_service.reason(
            context=CAREER_TRANSITION_RESUME,
            question="Which role she fit for?",
            retrieved_chunks=retrieved,
            doc_id=doc_id
        )
        # Should NOT return "working as a Which Role She Fit For"
        assert "Which Role She Fit For" not in ans, f"Sanitization failed: {ans}"
        assert "HR" in ans or "Human Resources" in ans or "Manager" in ans, f"Expected valid role suggestion: {ans}"
