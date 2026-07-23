"""Candidate Explanation Engine — Provides Recruiter Scorecard Explanations & Evidence.

Explains:
- Overall Score & 10 dimension scores
- Matched Skills vs Missing Skills
- Key Candidate Strengths & Weaknesses
- Work Experience & Education Analysis
- Reason for Ranking position
- Evidence citations from candidate profile
"""

from typing import Dict, Any, List, Optional
from loguru import logger
from backend.app.services.recruiter.job_requirement_builder import RequirementProfile


class CandidateExplanationEngine:
    """Generates comprehensive recruiter explanations for candidate scores and rankings."""

    def explain(
        self,
        candidate_scorecard: Dict[str, Any],
        requirement_profile: RequirementProfile
    ) -> Dict[str, Any]:
        """Generate structured explanation report for a candidate scorecard."""
        cname = candidate_scorecard.get("candidate_name", "Candidate")
        overall = candidate_scorecard.get("overall_score", 0.0)
        tier = candidate_scorecard.get("suitability_tier", "Unassigned")
        rank = candidate_scorecard.get("rank", 1)
        role = requirement_profile.target_role

        dims = candidate_scorecard.get("dimension_scores", {})
        matched = candidate_scorecard.get("matched_skills", [])
        missing = candidate_scorecard.get("missing_skills", [])
        profile = candidate_scorecard.get("candidate_profile", {})

        exp_str = profile.get("total_experience", "Not Mentioned")
        edu_list = profile.get("education", [])
        edu_str = edu_list[0].get("degree", "Not Mentioned") if edu_list else "Not Mentioned"
        certs = profile.get("certifications", [])

        # Construct Strengths
        strengths = []
        if dims.get("skill_match", 0) >= 75:
            strengths.append(f"Strong skill alignment ({dims['skill_match']}%) matching key technologies: {', '.join(matched[:5]) or 'Core skills'}.")
        if dims.get("experience_match", 0) >= 80:
            strengths.append(f"Solid professional experience ({exp_str}) meeting or exceeding role requirements ({requirement_profile.min_experience_years} yrs).")
        if dims.get("domain_match", 0) >= 85:
            strengths.append(f"Direct domain expertise in {profile.get('primary_domain', 'their primary domain')}.")
        if certs:
            strengths.append(f"Certified professional holding: {', '.join(str(c) for c in certs[:2])}.")
        if not strengths:
            strengths.append(f"Basic foundational background matching role criteria.")

        # Construct Weaknesses
        weaknesses = []
        if missing:
            weaknesses.append(f"Missing specific requested skills: {', '.join(missing[:5])}.")
        if dims.get("experience_match", 0) < 70:
            weaknesses.append(f"Experience level ({exp_str}) is below optimal threshold ({requirement_profile.min_experience_years} yrs).")
        if dims.get("education_match", 0) < 70:
            weaknesses.append(f"Education degree does not fully align with preferred qualifications ({', '.join(requirement_profile.education_requirements) or 'Degree'}).")
        if not weaknesses:
            weaknesses.append("No major red flags identified relative to requirement profile.")

        # Evidence Citations
        evidence = [
            f"Skills Section: {', '.join(profile.get('skills', [])[:8]) or 'Extracted skills'}",
            f"Experience Section: {exp_str} across {profile.get('primary_domain', 'Primary domain')}",
            f"Education Section: {edu_str}"
        ]

        # Concise Explanation Summary
        explanation_text = (
            f"{cname} is ranked #{rank} with an Overall Fit Score of {overall}% ({tier}) for the {role} position. "
            f"They demonstrate {dims.get('skill_match', 0)}% skill match with expertise in {', '.join(matched[:4]) or 'core domain skills'} "
            f"and {exp_str} of professional experience."
        )

        explanation_report = {
            "candidate_name": cname,
            "rank": rank,
            "overall_score": overall,
            "suitability_tier": tier,
            "target_role": role,
            "department": requirement_profile.department,
            "explanation_summary": explanation_text,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "matched_skills": matched,
            "missing_skills": missing,
            "dimension_scores": dims,
            "evidence": evidence,
            "confidence_score": 92.0
        }

        logger.info(f"CandidateExplanationEngine generated explanation for {cname} (Rank #{rank}, Score {overall}%)")
        return explanation_report


# Singleton Instance
candidate_explanation_engine = CandidateExplanationEngine()
