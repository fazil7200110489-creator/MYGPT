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
                "matched_skills": cand.get("matched_skills", []),
                "missing_skills": cand.get("missing_skills", []),
                "projects_count": len(profile.get("projects", [])),
                "certifications_count": len(profile.get("certifications", [])),
                "strengths": explanation.get("strengths", []),
                "weaknesses": explanation.get("weaknesses", [])
            }
            candidate_matrix.append(cand_entry)

        winner = candidate_matrix[0]
        runner_up = candidate_matrix[1] if len(candidate_matrix) > 1 else None

        if runner_up:
            margin = round(winner["overall_score"] - runner_up["overall_score"], 1)
            comparison_rationale = (
                f"{winner['candidate_name']} is recommended as the top candidate (Score: {winner['overall_score']}%) "
                f"outperforming {runner_up['candidate_name']} (Score: {runner_up['overall_score']}%) by {margin} points. "
                f"{winner['candidate_name']} offers higher skill alignment ({len(winner['matched_skills'])} matched skills vs {len(runner_up['matched_skills'])}) "
                f"and {winner['total_experience']} of relevant experience."
            )
        else:
            comparison_rationale = f"{winner['candidate_name']} is the sole candidate evaluated for this role with an overall score of {winner['overall_score']}%."

        result = {
            "target_role": requirement_profile.target_role,
            "department": requirement_profile.department,
            "candidates_compared_count": len(candidate_matrix),
            "winner_candidate_id": winner["candidate_id"],
            "winner_candidate_name": winner["candidate_name"],
            "winner_score": winner["overall_score"],
            "comparison_rationale": comparison_rationale,
            "candidate_matrix": candidate_matrix
        }

        logger.info(f"CandidateComparisonEngine compared {len(candidate_matrix)} candidates. Winner: {winner['candidate_name']} ({winner['overall_score']}%)")
        return result


# Singleton Instance
candidate_comparison_engine = CandidateComparisonEngine()
