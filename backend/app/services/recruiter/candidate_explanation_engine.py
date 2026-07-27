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

        # Construct Bullet Reasons (matching Step 4 requirement)
        reasons = []
        if matched:
            reasons.append(f"Strong expertise in {', '.join(matched[:3])}")
        if exp_str and exp_str != "Not Mentioned":
            reasons.append(f"{exp_str} of relevant experience")
        if dims.get("projects", 0) >= 80:
            reasons.append("Relevant project portfolio demonstrating production work")
        if dims.get("resume_quality", 0) >= 80:
            reasons.append("High resume quality and complete profile data")
        if missing:
            reasons.append(f"Lacks explicit mention of: {', '.join(missing[:3])}")
        if not reasons:
            reasons.append(f"Basic alignment with {role} requirements")

        # Construct Strengths
        strengths = []
        tech_score = dims.get("technical_skills", dims.get("skill_match", 0))
        exp_score = dims.get("experience", dims.get("experience_match", 0))
        edu_score = dims.get("education", dims.get("education_match", 0))

        if tech_score >= 75:
            strengths.append(f"Strong technical skill alignment ({tech_score}%) with key skills: {', '.join(matched[:5]) or 'Core skills'}.")
        if exp_score >= 80:
            strengths.append(f"Solid professional experience ({exp_str}) meeting role requirements.")
        if dims.get("domain_match", 0) >= 85:
            strengths.append(f"Direct domain expertise in {profile.get('primary_domain', 'their primary domain')}.")
        if certs:
            strengths.append(f"Certified professional holding: {', '.join(str(c) for c in certs[:2])}.")
        if not strengths:
            strengths.append(f"Foundational skills present for role criteria.")

        # Construct Weaknesses
        weaknesses = []
        if missing:
            weaknesses.append(f"Missing specific requested skills: {', '.join(missing[:5])}.")
        if exp_score < 70:
            weaknesses.append(f"Experience level ({exp_str}) is below optimal threshold.")
        if edu_score < 70:
            weaknesses.append(f"Education degree does not fully match preferred qualifications.")
        if not weaknesses:
            weaknesses.append("No major red flags identified relative to requirement profile.")

        # Dynamic Confidence Score calculation based on data richness & overall score
        data_richness = 0.8 if (matched or missing) else 0.5
        confidence_score = round(min(98.0, max(75.0, 70.0 + (overall * 0.2) + (data_richness * 10))), 1)

        # Hiring Recommendation
        if overall >= 88.0:
            hiring_rec = "Strongly Recommended for Immediate Shortlisting & Interview"
        elif overall >= 74.0:
            hiring_rec = "Recommended for Technical Screening"
        elif overall >= 55.0:
            hiring_rec = "Consider as Backup / Secondary Option"
        else:
            hiring_rec = "Not Recommended for this Role"

        # Evidence Citations
        evidence = [
            f"Skills Section: {', '.join(profile.get('skills', [])[:8]) or 'Extracted skills'}",
            f"Experience Section: {exp_str} across {profile.get('primary_domain', 'Primary domain')}",
            f"Education Section: {edu_str}"
        ]

        # Concise Explanation Summary
        explanation_text = (
            f"{cname} is ranked #{rank} with an Overall Score of {overall}/100 ({tier}) for {role}. "
            f"Key factors: {', '.join(reasons[:3])}."
        )

        explanation_report = {
            "candidate_name": cname,
            "rank": rank,
            "overall_score": overall,
            "suitability_tier": tier,
            "target_role": role,
            "department": requirement_profile.department,
            "reasons": reasons,
            "explanation_summary": explanation_text,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "matched_skills": matched,
            "missing_skills": missing,
            "dimension_scores": dims,
            "evidence": evidence,
            "confidence_score": confidence_score,
            "hiring_recommendation": hiring_rec
        }

        logger.info(f"CandidateExplanationEngine generated explanation for {cname} (Rank #{rank}, Score {overall}%)")
        return explanation_report


# Singleton Instance
candidate_explanation_engine = CandidateExplanationEngine()
