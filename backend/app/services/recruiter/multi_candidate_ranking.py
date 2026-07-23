"""Multi-Candidate Ranking Engine — Evaluates candidate pool against RequirementProfile.

Mandatory Requirement: Resumes are NEVER compared directly to each other.
The Ranking Engine scores every CandidateProfile against a canonical RequirementProfile
across 10 evaluation dimensions using configurable weights.
"""

import re
from typing import Dict, Any, List, Optional
from loguru import logger
from backend.app.services.recruiter.job_requirement_builder import RequirementProfile


class MultiCandidateRanking:
    """Scores and ranks candidate pool against a RequirementProfile."""

    def rank_candidates(
        self,
        candidate_pool: List[Dict[str, Any]],
        requirement_profile: RequirementProfile
    ) -> List[Dict[str, Any]]:
        """Rank candidates against RequirementProfile across 10 evaluation dimensions."""
        if not candidate_pool:
            logger.warning("MultiCandidateRanking: Candidate pool is empty.")
            return []

        ranked_results = []

        for candidate_record in candidate_pool:
            scorecard = self.evaluate_candidate(candidate_record, requirement_profile)
            ranked_results.append(scorecard)

        # Sort descending by overall_score
        ranked_results.sort(key=lambda x: x["overall_score"], reverse=True)

        # Assign rank positions
        for idx, item in enumerate(ranked_results):
            item["rank"] = idx + 1

        logger.info(f"MultiCandidateRanking: Ranked {len(ranked_results)} candidates for role '{requirement_profile.target_role}'. Top score: {ranked_results[0]['overall_score'] if ranked_results else 0}%")
        return ranked_results

    def evaluate_candidate(
        self,
        candidate_record: Dict[str, Any],
        req: RequirementProfile
    ) -> Dict[str, Any]:
        """Evaluate a single candidate against RequirementProfile."""
        profile = candidate_record.get("candidate_profile") or candidate_record
        cid = candidate_record.get("candidate_id") or "UNKNOWN"
        cname = candidate_record.get("name") or profile.get("name", "Candidate")

        # 1. Skill Match Score
        cand_skills = [s.lower() for s in profile.get("skills", [])]
        req_skills_all = req.required_skills + req.preferred_skills + req.nice_to_have_skills
        matched_skills = []
        missing_skills = []

        for rsk in req_skills_all:
            rsk_lower = rsk.lower()
            if any(rsk_lower in s for s in cand_skills):
                matched_skills.append(rsk)
            else:
                missing_skills.append(rsk)

        skill_score = (len(matched_skills) / len(req_skills_all) * 100.0) if req_skills_all else 85.0

        # 2. Experience Match Score
        exp_str = profile.get("total_experience", "0")
        m_exp = re.search(r'(\d+)', str(exp_str))
        cand_years = float(m_exp.group(1)) if m_exp else 0.0

        if req.min_experience_years <= 0:
            exp_score = 90.0
        elif cand_years >= req.min_experience_years:
            exp_score = min(100.0, 80.0 + ((cand_years - req.min_experience_years) * 5.0))
        else:
            exp_score = max(20.0, (cand_years / req.min_experience_years) * 70.0)

        # 3. Education Match Score
        edu_list = profile.get("education", [])
        edu_str = " ".join(str(e).lower() for e in edu_list)
        edu_score = 60.0
        if req.education_requirements:
            if any(req_edu.lower() in edu_str for req_edu in req.education_requirements):
                edu_score = 95.0
            else:
                edu_score = 50.0
        else:
            edu_score = 85.0 if edu_list else 60.0

        # 4. Certification Match Score
        certs = [str(c).lower() for c in profile.get("certifications", [])]
        cert_score = 70.0
        if req.certification_requirements:
            cert_matches = [rc for rc in req.certification_requirements if any(rc.lower() in c for c in certs)]
            cert_score = (len(cert_matches) / len(req.certification_requirements) * 100.0) if cert_matches else 40.0

        # 5. Project Match Score
        projects = profile.get("projects", [])
        proj_score = 90.0 if profile.get("has_dedicated_projects") or len(projects) > 0 else 60.0

        # 6. Domain Match Score
        cand_domain = profile.get("primary_domain") or profile.get("domain", "")
        domain_score = 95.0 if req.department.lower() in cand_domain.lower() or "hr" in cand_domain.lower() and "hr" in req.department.lower() else 75.0

        # 7. Department Match Score
        dept_score = 90.0 if domain_score >= 85.0 else 65.0

        # 8. Role Match Score
        desig = (profile.get("designation") or "").lower()
        role_score = 95.0 if req.target_role.lower() in desig else 75.0

        # 9. Tool Match Score
        tool_score = 85.0 if matched_skills else 60.0

        # 10. Technology Match Score
        tech_score = 85.0 if matched_skills else 60.0

        # Weighted Overall Score Calculation
        w = req.weights
        total_weight = sum(w.values())
        weighted_sum = (
            (skill_score * w.get("skill_weight", 4.0)) +
            (exp_score * w.get("experience_weight", 3.0)) +
            (edu_score * w.get("education_weight", 2.0)) +
            (cert_score * w.get("certification_weight", 1.5)) +
            (proj_score * w.get("project_weight", 1.5)) +
            (domain_score * w.get("domain_weight", 2.0)) +
            (dept_score * w.get("department_weight", 1.5)) +
            (role_score * w.get("role_weight", 2.5)) +
            (tool_score * w.get("tool_weight", 1.0)) +
            (tech_score * w.get("technology_weight", 1.0))
        )

        overall_score = round(weighted_sum / total_weight, 1)

        # Suitability Tier Assignment
        if overall_score >= 88.0:
            suitability_tier = "Exceptional Match"
        elif overall_score >= 74.0:
            suitability_tier = "Highly Suitable"
        elif overall_score >= 55.0:
            suitability_tier = "Moderate Fit"
        else:
            suitability_tier = "Unsuitable"

        return {
            "candidate_id": cid,
            "candidate_name": cname,
            "filename": candidate_record.get("filename", "Resume.pdf"),
            "target_role": req.target_role,
            "overall_score": overall_score,
            "suitability_tier": suitability_tier,
            "dimension_scores": {
                "skill_match": round(skill_score, 1),
                "experience_match": round(exp_score, 1),
                "education_match": round(edu_score, 1),
                "certification_match": round(cert_score, 1),
                "project_match": round(proj_score, 1),
                "domain_match": round(domain_score, 1),
                "department_match": round(dept_score, 1),
                "role_match": round(role_score, 1),
                "tool_match": round(tool_score, 1),
                "technology_match": round(tech_score, 1)
            },
            "matched_skills": list(dict.fromkeys(matched_skills)),
            "missing_skills": list(dict.fromkeys(missing_skills)),
            "candidate_profile": profile
        }


# Singleton Instance
multi_candidate_ranking = MultiCandidateRanking()
