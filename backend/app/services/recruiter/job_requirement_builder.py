"""Job Requirement Builder — Converts Recruiter Query / Plan into a Canonical RequirementProfile.

Mandatory Requirement: Resumes are NEVER compared directly to each other.
The Ranking Engine compares CandidateProfile objects against the RequirementProfile generated here.
"""

from typing import Dict, Any, List, Optional
from loguru import logger
from backend.app.services.recruiter.recruiter_query_planner import QueryPlan
from backend.app.services.recruiter.recruiter_knowledge_registry import recruiter_knowledge_registry


class RequirementProfile:
    """Canonical Requirement Profile for scoring candidate pools."""

    def __init__(
        self,
        target_role: str,
        department: str = "General",
        required_skills: Optional[List[str]] = None,
        preferred_skills: Optional[List[str]] = None,
        nice_to_have_skills: Optional[List[str]] = None,
        min_experience_years: float = 0.0,
        education_requirements: Optional[List[str]] = None,
        certification_requirements: Optional[List[str]] = None,
        tools: Optional[List[str]] = None,
        technology_stack: Optional[List[str]] = None,
        weights: Optional[Dict[str, float]] = None
    ):
        self.target_role = target_role
        self.department = department
        self.required_skills = required_skills or []
        self.preferred_skills = preferred_skills or []
        self.nice_to_have_skills = nice_to_have_skills or []
        self.min_experience_years = min_experience_years
        self.education_requirements = education_requirements or []
        self.certification_requirements = certification_requirements or []
        self.tools = tools or []
        self.technology_stack = technology_stack or []

        default_weights = {
            "skill_weight": 4.0,
            "experience_weight": 3.0,
            "education_weight": 2.0,
            "certification_weight": 1.5,
            "project_weight": 1.5,
            "domain_weight": 2.0,
            "department_weight": 1.5,
            "role_weight": 2.5,
            "tool_weight": 1.0,
            "technology_weight": 1.0
        }
        if weights:
            default_weights.update(weights)
        self.weights = default_weights

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_role": self.target_role,
            "department": self.department,
            "required_skills": self.required_skills,
            "preferred_skills": self.preferred_skills,
            "nice_to_have_skills": self.nice_to_have_skills,
            "min_experience_years": self.min_experience_years,
            "education_requirements": self.education_requirements,
            "certification_requirements": self.certification_requirements,
            "tools": self.tools,
            "technology_stack": self.technology_stack,
            "weights": self.weights
        }


class JobRequirementBuilder:
    """Builds a canonical RequirementProfile from a QueryPlan or target role specification."""

    def build_from_plan(self, query_plan: QueryPlan) -> RequirementProfile:
        """Build RequirementProfile from structured QueryPlan and RecruiterKnowledgeRegistry."""
        target_role = query_plan.target_role or "General Specialist"
        department = query_plan.department or "General"

        # Lookup registered role configuration if available
        role_obj = recruiter_knowledge_registry.find_role(target_role, department)

        req_skills = []
        pref_skills = []
        nice_skills = []
        min_exp = query_plan.min_experience or 0.0
        edu_reqs = []
        cert_reqs = []
        tools = []
        tech_stack = []
        weights = {}

        if role_obj:
            target_role = role_obj.get("role_name", target_role)
            department = role_obj.get("department", department)
            req_skills = list(role_obj.get("required_skills", []))
            pref_skills = list(role_obj.get("preferred_skills", []))
            nice_skills = list(role_obj.get("nice_to_have_skills", []))
            if not query_plan.min_experience:
                min_exp = float(role_obj.get("experience_min_years", 0.0))
            edu_reqs = list(role_obj.get("education_requirements", []))
            cert_reqs = list(role_obj.get("certification_requirements", []))
            tools = list(role_obj.get("tools", []))
            tech_stack = list(role_obj.get("technology_stack", []))

            weights["skill_weight"] = float(role_obj.get("skill_weight", 4.0))
            weights["role_weight"] = float(role_obj.get("role_weight", 2.5))
            weights["domain_weight"] = float(role_obj.get("domain_weight", 2.0))
        else:
            # Dynamic inference fallback
            from backend.app.services.recruiter.role_requirement_analyzer import role_requirement_analyzer
            inferred = role_requirement_analyzer.analyze_role(target_role, explicit_skills=query_plan.skills)
            department = inferred.department
            req_skills = inferred.required_skills
            pref_skills = inferred.preferred_skills
            nice_skills = inferred.nice_to_have_skills
            if not query_plan.min_experience:
                min_exp = inferred.min_experience_years
            edu_reqs = inferred.education_requirements
            tools = inferred.tools
            tech_stack = inferred.technology_stack
            weights = inferred.weights

        # Merge additional explicit query skills into preferred/required
        if query_plan.skills:
            for sk in query_plan.skills:
                if sk not in req_skills and sk not in pref_skills:
                    pref_skills.append(sk)

        if query_plan.education_degree and query_plan.education_degree not in edu_reqs:
            edu_reqs.append(query_plan.education_degree)

        profile = RequirementProfile(
            target_role=target_role,
            department=department,
            required_skills=req_skills,
            preferred_skills=pref_skills,
            nice_to_have_skills=nice_skills,
            min_experience_years=min_exp,
            education_requirements=edu_reqs,
            certification_requirements=cert_reqs,
            tools=tools,
            technology_stack=tech_stack,
            weights=weights
        )

        logger.info(f"JobRequirementBuilder created RequirementProfile for role '{target_role}' (Dept: {department}) with {len(req_skills + pref_skills)} skills and min {min_exp} yrs exp.")
        return profile


# Singleton Instance
job_requirement_builder = JobRequirementBuilder()
