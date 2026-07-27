"""Recruiter Response Formatter — Standard Output Generator (Step 7 Output Format).

Formats all Recruiter Platform V2 engine outputs into:
1. Requirement Summary
2. Ranking Table
3. Detailed Score Breakdown
4. Reasoning
5. Strengths
6. Weaknesses
7. Missing Skills
8. Confidence
9. Hiring Recommendation
"""

from typing import Dict, Any, List, Optional
from loguru import logger
from backend.app.services.recruiter.job_requirement_builder import RequirementProfile


class RecruiterResponseFormatter:
    """Formats recruiter query evaluation into canonical output format."""

    def format_ranking_response(
        self,
        ranked_candidates: List[Dict[str, Any]],
        explanations: List[Dict[str, Any]],
        req_profile: RequirementProfile,
        raw_query: str
    ) -> Dict[str, Any]:
        """Build standard output dictionary for candidate ranking."""

        # 1. Requirement Summary
        req_summary = {
            "target_role": req_profile.target_role,
            "department": req_profile.department,
            "required_skills": req_profile.required_skills,
            "preferred_skills": req_profile.preferred_skills,
            "min_experience_years": req_profile.min_experience_years,
            "education_requirements": req_profile.education_requirements
        }

        # 2. Ranking Table
        ranking_table = []
        for item in ranked_candidates:
            ranking_table.append({
                "rank": item.get("rank"),
                "candidate_id": item.get("candidate_id"),
                "candidate_name": item.get("candidate_name"),
                "overall_score": f"{item.get('overall_score')}/100",
                "suitability_tier": item.get("suitability_tier"),
                "matched_skills_count": len(item.get("matched_skills", [])),
                "missing_skills_count": len(item.get("missing_skills", []))
            })

        # 3. Detailed Score Breakdown & Reasoning per Candidate
        candidate_details = []
        for exp in explanations:
            candidate_details.append({
                "rank": exp.get("rank"),
                "candidate_name": exp.get("candidate_name"),
                "score": f"{exp.get('overall_score')}/100",
                "suitability_tier": exp.get("suitability_tier"),
                "reasons": exp.get("reasons", []),
                "strengths": exp.get("strengths", []),
                "weaknesses": exp.get("weaknesses", []),
                "matched_skills": exp.get("matched_skills", []),
                "missing_skills": exp.get("missing_skills", []),
                "dimension_scores": exp.get("dimension_scores", {}),
                "confidence": f"{exp.get('confidence_score')}%",
                "hiring_recommendation": exp.get("hiring_recommendation")
            })

        # Top candidate overall metrics
        top_exp = explanations[0] if explanations else {}

        # 4. Construct Markdown Formatting for Chat Interface
        md_lines = [
            f"# Recruiter Evaluation: {req_profile.target_role}\n",
            "### 📋 Requirement Summary",
            f"- **Role:** {req_profile.target_role} ({req_profile.department})",
            f"- **Required Skills:** {', '.join(req_profile.required_skills) if req_profile.required_skills else 'Domain Knowledge'}",
            f"- **Preferred Skills:** {', '.join(req_profile.preferred_skills) if req_profile.preferred_skills else 'N/A'}",
            f"- **Min Experience:** {req_profile.min_experience_years} years\n",
            "### 🏆 Candidate Ranking Table\n",
            "| Rank | Candidate Name | Score | Suitability Tier | Matched Skills | Missing Skills |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |"
        ]

        for item in ranked_candidates:
            matched_str = ", ".join(item.get("matched_skills", [])[:3]) or "None"
            missing_str = ", ".join(item.get("missing_skills", [])[:3]) or "None"
            md_lines.append(f"| #{item.get('rank')} | **{item.get('candidate_name')}** | **{item.get('overall_score')}/100** | {item.get('suitability_tier')} | {matched_str} | {missing_str} |")

        md_lines.append("\n### 🔬 Detailed Candidate Evaluations\n")

        for exp in explanations:
            md_lines.append(f"#### Rank #{exp.get('rank')} — {exp.get('candidate_name')} ({exp.get('overall_score')}/100)")
            md_lines.append(f"**Suitability:** {exp.get('suitability_tier')} | **Confidence:** {exp.get('confidence_score')}%\n")
            md_lines.append("**Reasoning:**")
            for r in exp.get("reasons", []):
                md_lines.append(f"- {r}")

            md_lines.append(f"\n- **✓ Matched Skills:** {', '.join(exp.get('matched_skills', [])) if exp.get('matched_skills') else 'None'}")
            md_lines.append(f"- **✗ Missing Skills:** {', '.join(exp.get('missing_skills', [])) if exp.get('missing_skills') else 'None'}")
            md_lines.append(f"- **💡 Recommendation:** {exp.get('hiring_recommendation')}\n")

        formatted_markdown = "\n".join(md_lines)

        return {
            "query": raw_query,
            "target_role": req_profile.target_role,
            "requirement_summary": req_summary,
            "ranking_table": ranking_table,
            "candidate_details": candidate_details,
            "top_candidate": {
                "name": top_exp.get("candidate_name"),
                "score": top_exp.get("overall_score"),
                "recommendation": top_exp.get("hiring_recommendation"),
                "confidence": top_exp.get("confidence_score")
            },
            "markdown_text": formatted_markdown
        }

    def format_comparison_response(
        self,
        comp_data: Dict[str, Any],
        req_profile: RequirementProfile,
        raw_query: str
    ) -> Dict[str, Any]:
        """Build standard output dictionary for candidate comparison."""

        winner = comp_data.get("winner", "Candidate")
        score = comp_data.get("winner_score", 0)
        reason = comp_data.get("reason", "")
        confidence = comp_data.get("confidence", 90.0)
        matrix = comp_data.get("candidate_matrix", [])
        comparisons = comp_data.get("comparisons", {})

        md_lines = [
            f"# Head-to-Head Candidate Comparison: {req_profile.target_role}\n",
            f"### 👑 Recommended Winner: **{winner}** ({score}/100)",
            f"- **Confidence:** {confidence}%",
            f"- **Reason:** {reason}\n",
            "### 📊 Side-by-Side Comparison Matrix\n",
            "| Metric | " + " | ".join([f"**{c['candidate_name']}**" for c in matrix]) + " |",
            "| :--- | " + " | ".join([":---" for _ in matrix]) + " |",
            "| **Overall Score** | " + " | ".join([f"**{c['overall_score']}/100**" for c in matrix]) + " |",
            "| **Suitability** | " + " | ".join([str(c['suitability_tier']) for c in matrix]) + " |",
            "| **Experience** | " + " | ".join([str(c['total_experience']) for c in matrix]) + " |",
            "| **Education** | " + " | ".join([str(c['education']) for c in matrix]) + " |",
            "| **Matched Skills** | " + " | ".join([", ".join(c['matched_skills'][:4]) or 'None' for c in matrix]) + " |",
            "| **Missing Skills** | " + " | ".join([", ".join(c['missing_skills'][:3]) or 'None' for c in matrix]) + " |",
            "| **Projects** | " + " | ".join([f"{c['projects_count']} project(s)" for c in matrix]) + " |\n"
        ]

        if comparisons:
            md_lines.append("### 🔍 Category Breakdown")
            if comparisons.get("technical_skills_comparison"):
                md_lines.append("\n**Technical Skills:**")
                for line in comparisons["technical_skills_comparison"]:
                    md_lines.append(f"- {line}")
            if comparisons.get("experience_comparison"):
                md_lines.append("\n**Experience:**")
                for line in comparisons["experience_comparison"]:
                    md_lines.append(f"- {line}")

        formatted_markdown = "\n".join(md_lines)

        return {
            "query": raw_query,
            "target_role": req_profile.target_role,
            "winner": winner,
            "winner_score": score,
            "reason": reason,
            "confidence": confidence,
            "comparisons": comparisons,
            "candidate_matrix": matrix,
            "markdown_text": formatted_markdown
        }

    def format_single_candidate_response(
        self,
        candidate_data: Dict[str, Any],
        explanation: Dict[str, Any],
        req_profile: RequirementProfile,
        raw_query: str
    ) -> Dict[str, Any]:
        """Build standard output dictionary for single candidate analysis in recruiter platform."""
        name = candidate_data.get("candidate_name") or candidate_data.get("name") or "Candidate"
        profile = candidate_data.get("candidate_profile", {})
        
        md_lines = [
            f"# Recruiter Profile Analysis: **{name}**\n",
            f"### 📊 Overall Score: **{candidate_data.get('overall_score', 85)}/100** ({candidate_data.get('suitability_tier', 'Qualified')})\n",
            f"- **Target Role Match:** {req_profile.target_role}",
            f"- **Total Experience:** {profile.get('total_experience', candidate_data.get('total_experience', 'N/A'))}",
            f"- **Education:** {profile.get('education', [{}])[0].get('degree', 'N/A') if isinstance(profile.get('education'), list) and profile.get('education') else 'N/A'}\n",
            "### 🌟 Key Strengths",
        ]
        
        for st in explanation.get("strengths", []):
            md_lines.append(f"- {st}")
            
        md_lines.append("\n### ⚠️ Areas of Note / Weaknesses")
        for wk in explanation.get("weaknesses", []):
            md_lines.append(f"- {wk}")
            
        md_lines.append("\n### 🛠️ Skills & Experience Match")
        md_lines.append(f"- **Matched Skills:** {', '.join(candidate_data.get('matched_skills', [])) if candidate_data.get('matched_skills') else 'See profile'}")
        md_lines.append(f"- **Missing Skills:** {', '.join(candidate_data.get('missing_skills', [])) if candidate_data.get('missing_skills') else 'None'}\n")
        
        md_lines.append(f"### 💡 Hiring Recommendation: {explanation.get('hiring_recommendation', 'Strong Candidate')}")

        formatted_markdown = "\n".join(md_lines)

        return {
            "query": raw_query,
            "candidate_name": name,
            "score": candidate_data.get("overall_score", 85),
            "suitability_tier": candidate_data.get("suitability_tier", "Qualified"),
            "explanation": explanation,
            "markdown_text": formatted_markdown
        }


# Singleton Instance
recruiter_response_formatter = RecruiterResponseFormatter()
