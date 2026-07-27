import re
from typing import Dict, Any, List

class ResumeQualityAnalyzer:
    """Performs deep analysis of resume quality, formatting, technical depth, and growth trajectory."""

    def analyze(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """Runs quality analysis over the compiled CandidateProfile."""
        validation = profile.get("validation_flags", {})
        skills = profile.get("skills", [])
        experience = profile.get("experience_history", [])
        projects = profile.get("projects", [])
        timeline = profile.get("experience_timeline", [])
        domain = profile.get("domain", "General")

        # 1. Missing Sections
        missing_sections = []
        if not validation.get("has_experience"):
            missing_sections.append("Work Experience Section")
        if not validation.get("has_education"):
            missing_sections.append("Education Section")
        if not validation.get("has_skills"):
            missing_sections.append("Skills Section")
        if not validation.get("has_certifications"):
            missing_sections.append("Certifications / Achievements Section")
        if not validation.get("has_awards"):
            missing_sections.append("Professional Honors / Awards Section")
        
        # 2. Formatting Quality
        formatting_issues = []
        formatting_score = 100.0
        
        personal = profile.get("personal_info", {})
        if not personal.get("email") or personal.get("email") == "Not Mentioned":
            formatting_issues.append("Missing contact email address")
            formatting_score -= 15.0
        if not personal.get("phone") or personal.get("phone") == "Not Mentioned":
            formatting_issues.append("Missing contact phone number")
            formatting_score -= 15.0
        if not personal.get("linkedin") or personal.get("linkedin") == "Not Mentioned":
            formatting_issues.append("LinkedIn profile link not listed")
            formatting_score -= 10.0
        if not personal.get("github") or personal.get("github") == "Not Mentioned":
            formatting_issues.append("GitHub repository link not listed")
            formatting_score -= 5.0
        if not personal.get("address") or personal.get("address") == "Not Mentioned":
            formatting_issues.append("Missing physical or residential address details")
            formatting_score -= 10.0
            
        formatting_score = max(30.0, formatting_score)
        formatting_tier = "Excellent" if formatting_score >= 90 else "Good" if formatting_score >= 70 else "Needs Improvement"

        # 3. Technical Depth
        tech_depth_score = 50.0
        tech_reasons = []
        
        # Check frameworks density
        frameworks = profile.get("skills_data", {}).get("modern_groups", []) or []
        prog_langs = profile.get("programming_languages", [])
        
        if len(prog_langs) >= 3:
            tech_depth_score += 15.0
            tech_reasons.append(f"Demonstrates multi-language proficiency ({', '.join(prog_langs[:3])})")
        elif len(prog_langs) >= 1:
            tech_depth_score += 5.0
            
        if len(frameworks) >= 2:
            tech_depth_score += 15.0
            tech_reasons.append(f"Familiar with modern stack frameworks ({', '.join(frameworks[:2])})")
            
        # Check project complexity
        detailed_projs = profile.get("detailed_projects", [])
        high_complexity_count = sum(1 for p in detailed_projs if p.get("complexity_tier") == "High")
        med_complexity_count = sum(1 for p in detailed_projs if p.get("complexity_tier") == "Medium")
        
        if high_complexity_count >= 1:
            tech_depth_score += 20.0
            tech_reasons.append("Experience executing High Complexity architecture projects")
        elif med_complexity_count >= 1:
            tech_depth_score += 10.0
            tech_reasons.append("Experience executing Medium Complexity software projects")

        tech_depth_score = min(100.0, tech_depth_score)
        tech_depth_tier = "Advanced" if tech_depth_score >= 85 else "Intermediate" if tech_depth_score >= 60 else "Foundational"

        # 4. Career Growth
        growth_score = 50.0
        growth_reasons = []
        
        if len(timeline) >= 2:
            # Check promotion signals in timeline designations
            titles = [t.get("title", "").lower() for t in timeline]
            growth_keywords = ["lead", "senior", "sr", "manager", "head", "principal", "chief", "director"]
            
            promoted = False
            for idx in range(1, len(titles)):
                prev = titles[idx-1]
                curr = titles[idx]
                # If current has a growth keyword and previous does not, or current is senior
                if any(kw in curr for kw in growth_keywords) and not any(kw in prev for kw in growth_keywords):
                    promoted = True
                    break
                    
            if promoted:
                growth_score += 35.0
                growth_reasons.append("Chronological progression into leadership / senior roles detected")
            else:
                growth_score += 15.0
                growth_reasons.append("Steady career tenure across multiple roles")
        else:
            growth_reasons.append("Single-tenure timeline (limited chronological progression details)")

        growth_score = min(100.0, growth_score)
        growth_tier = "Accelerated" if growth_score >= 85 else "Steady" if growth_score >= 60 else "Stable"

        # 5. Skill Coverage
        skill_coverage_score = min(100.0, max(20.0, len(skills) * 4.0))
        skill_coverage_tier = "High Coverage" if skill_coverage_score >= 80 else "Moderate Coverage" if skill_coverage_score >= 50 else "Limited Coverage"

        # 6. Resume Strengths
        strengths = []
        if len(skills) >= 8:
            strengths.append("Broad technical skillset spanning multiple domains.")
        if len(timeline) >= 2:
            strengths.append(f"Stable chronological work history with {profile.get('total_experience', 'several years')} of experience.")
        if high_complexity_count >= 1:
            strengths.append("Proven capability in architecting and delivering high-complexity projects.")
        if profile.get("certifications"):
            strengths.append(f"Committed to professional validation with {len(profile['certifications'])} certifications.")
        if not strengths:
            strengths.append(f"Solid alignment with {domain} domain.")

        # 7. Resume Weaknesses
        weaknesses = []
        if missing_sections:
            weaknesses.append(f"Missing core section(s): {', '.join(missing_sections)}.")
        if formatting_issues:
            weaknesses.append(f"Incomplete professional metadata: {', '.join(formatting_issues[:2])}.")
        if len(skills) < 5:
            weaknesses.append("Thin technical skills list. Consider listing programming languages, tools, and methodologies.")
        if len(timeline) == 1:
            weaknesses.append("Single employer work history. Consider detailing past projects or internships to show versatility.")
        if not weaknesses:
            weaknesses.append("Resume contains solid fundamentals; consider adding quantifiable business impact metrics.")

        return {
            "scorecard": {
                "overall_quality_score": round((formatting_score + tech_depth_score + growth_score + skill_coverage_score) / 4.0),
                "formatting_quality": {
                    "score": formatting_score,
                    "tier": formatting_tier,
                    "issues": formatting_issues
                },
                "technical_depth": {
                    "score": tech_depth_score,
                    "tier": tech_depth_tier,
                    "reasons": tech_reasons
                },
                "career_growth": {
                    "score": growth_score,
                    "tier": growth_tier,
                    "reasons": growth_reasons
                },
                "skill_coverage": {
                    "score": skill_coverage_score,
                    "tier": skill_coverage_tier
                }
            },
            "strengths": strengths,
            "weaknesses": weaknesses,
            "missing_sections": missing_sections
        }

# Module singleton
resume_quality_analyzer = ResumeQualityAnalyzer()
