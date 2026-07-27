"""Candidate Comparison Engine — Side-by-Side Head-to-Head Candidate Evaluation.

Compares 2 or more candidates across:
- Overall Score & Rank
- Experience & Education
- Matched Skills vs Missing Skills
- Projects & Certifications
- Candidate Strengths & Weaknesses
- Declares Winner with explicit comparison rationale
"""

from typing import Dict, Any, List, Optional
from loguru import logger
from backend.app.services.recruiter.candidate_explanation_engine import candidate_explanation_engine
from backend.app.services.recruiter.job_requirement_builder import RequirementProfile


class CandidateComparisonEngine:
    """Performs side-by-side comparative evaluation of candidate profiles."""

    def compare(
        self,
        candidate_scorecards: List[Dict[str, Any]],
        requirement_profile: RequirementProfile
    ) -> Dict[str, Any]:
        """Compare 2+ candidate scorecards side-by-side and declare a winner."""
        if not candidate_scorecards:
            logger.warning("CandidateComparisonEngine: Received empty scorecards list.")
            return {"error": "At least two candidates are required for comparison."}

        # Ensure candidates are sorted by score
        sorted_cands = sorted(candidate_scorecards, key=lambda x: x.get("overall_score", 0.0), reverse=True)

        candidate_matrix = []
        for cand in sorted_cands:
            explanation = candidate_explanation_engine.explain(cand, requirement_profile)
            profile = cand.get("candidate_profile", {})

            cand_entry = {
                "candidate_id": cand.get("candidate_id"),
                "candidate_name": cand.get("candidate_name"),
                "rank": cand.get("rank"),
                "overall_score": cand.get("overall_score"),
                "suitability_tier": cand.get("suitability_tier"),
                "total_experience": profile.get("total_experience", "Not Mentioned"),
                "education": profile.get("education", [{}])[0].get("degree", "Not Mentioned") if profile.get("education") else "Not Mentioned",
                "dimension_scores": cand.get("dimension_scores", {}),
                "matched_skills": cand.get("matched_skills", []),
                "missing_skills": cand.get("missing_skills", []),
                "projects_count": len(profile.get("projects", [])),
                "certifications_count": len(profile.get("certifications", [])),
                "strengths": explanation.get("strengths", []),
                "weaknesses": explanation.get("weaknesses", []),
                "reasons": explanation.get("reasons", [])
            }
            candidate_matrix.append(cand_entry)

        winner = candidate_matrix[0]
        runner_up = candidate_matrix[1] if len(candidate_matrix) > 1 else None

        # Build comparison sections matching Step 5 requirement
        tech_comp = []
        exp_comp = []
        proj_comp = []
        edu_comp = []

        for c in candidate_matrix:
            dims = c.get("dimension_scores", {})
            tech_comp.append(f"{c['candidate_name']}: {dims.get('technical_skills', 0)}/100 (Matched: {', '.join(c['matched_skills'][:4]) or 'None'})")
            exp_comp.append(f"{c['candidate_name']}: {c['total_experience']} (Score: {dims.get('experience', 0)}/100)")
            proj_comp.append(f"{c['candidate_name']}: {c['projects_count']} project(s) (Score: {dims.get('project_match', dims.get('projects', 0))}/100)")
            edu_comp.append(f"{c['candidate_name']}: {c['education']} (Score: {dims.get('education', 0)}/100)")

        if runner_up:
            margin = round(winner["overall_score"] - runner_up["overall_score"], 1)
            reason = (
                f"{winner['candidate_name']} is recommended as the top candidate (Score: {winner['overall_score']}/100) "
                f"outperforming {runner_up['candidate_name']} (Score: {runner_up['overall_score']}/100) by {margin} points. "
                f"{winner['candidate_name']} offers superior technical skill alignment ({len(winner['matched_skills'])} matched skills) "
                f"and {winner['total_experience']} of experience."
            )
            confidence = round(min(98.0, 85.0 + (margin * 1.5)), 1)
        else:
            reason = f"{winner['candidate_name']} is the sole evaluated candidate with an overall score of {winner['overall_score']}/100."
            confidence = 90.0

        result = {
            "target_role": requirement_profile.target_role,
            "department": requirement_profile.department,
            "candidates_compared_count": len(candidate_matrix),
            "winner": winner["candidate_name"],
            "winner_candidate_name": winner["candidate_name"],
            "winner_candidate_id": winner["candidate_id"],
            "winner_score": winner["overall_score"],
            "reason": reason,
            "comparison_rationale": reason,
            "confidence": confidence,
            "comparisons": {
                "technical_skills_comparison": tech_comp,
                "experience_comparison": exp_comp,
                "projects_comparison": proj_comp,
                "education_comparison": edu_comp
            },
            "candidate_matrix": candidate_matrix
        }

        logger.info(f"CandidateComparisonEngine compared {len(candidate_matrix)} candidates. Winner: {winner['candidate_name']} ({winner['overall_score']}%)")
        return result


# Singleton Instance
candidate_comparison_engine = CandidateComparisonEngine()
