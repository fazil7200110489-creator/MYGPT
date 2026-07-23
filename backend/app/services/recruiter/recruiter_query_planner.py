"""Recruiter Query Planner — Converts Natural Language queries into Structured Query Plans.

Extracts:
- Target Role & Department
- Required / Requested Skills
- Location constraints (Chennai, Bangalore, Kochi, etc.)
- Experience constraints (3+ years, freshers, etc.)
- Education degree constraints (MBA, BCA, B.Tech, etc.)
- Specific candidate names (Mohamed Fazil, Rahul, etc.)
- Result limits (top 5, top 10, etc.)
- Sorting preferences
"""

import re
from typing import Dict, Any, List, Optional
from loguru import logger
from backend.app.services.recruiter.recruiter_intent_classifier import RecruiterIntent, recruiter_intent_classifier
from backend.app.services.recruiter.recruiter_knowledge_registry import recruiter_knowledge_registry


class QueryPlan:
    """Structured Query Plan object representing extracted recruiter criteria."""

    def __init__(
        self,
        raw_query: str,
        intent: RecruiterIntent,
        target_role: Optional[str] = None,
        department: Optional[str] = None,
        skills: Optional[List[str]] = None,
        location: Optional[str] = None,
        min_experience: Optional[float] = None,
        education_degree: Optional[str] = None,
        is_fresher: bool = False,
        candidate_names: Optional[List[str]] = None,
        limit: Optional[int] = None,
        sort_by: str = "Overall Score"
    ):
        self.raw_query = raw_query
        self.intent = intent
        self.target_role = target_role
        self.department = department
        self.skills = skills or []
        self.location = location
        self.min_experience = min_experience
        self.education_degree = education_degree
        self.is_fresher = is_fresher
        self.candidate_names = candidate_names or []
        self.limit = limit
        self.sort_by = sort_by

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_query": self.raw_query,
            "intent": self.intent.value,
            "target_role": self.target_role,
            "department": self.department,
            "skills": self.skills,
            "location": self.location,
            "min_experience": self.min_experience,
            "education_degree": self.education_degree,
            "is_fresher": self.is_fresher,
            "candidate_names": self.candidate_names,
            "limit": self.limit,
            "sort_by": self.sort_by
        }


class RecruiterQueryPlanner:
    """Parses recruiter natural language query into a structured QueryPlan."""

    def plan_query(self, query: str, default_intent: Optional[RecruiterIntent] = None) -> QueryPlan:
        """Parse query string and return structured QueryPlan."""
        intent = default_intent or recruiter_intent_classifier.classify(query)
        q_lower = (query or "").lower().strip()

        # 1. Limit extraction ("top 5", "first 3", "10 best")
        limit = None
        limit_match = re.search(r'\b(?:top|first|best)\s*(\d+)\b', q_lower)
        if limit_match:
            limit = int(limit_match.group(1))

        # 2. Location extraction ("from chennai", "in bangalore", "chennai")
        location = None
        KNOWN_CITIES = ["chennai", "bangalore", "bengaluru", "kochi", "mumbai", "delhi", "hyderabad", "pune", "kolkata"]
        for city in KNOWN_CITIES:
            if re.search(r'\b' + city + r'\b', q_lower):
                location = city.title()
                break

        # 3. Experience extraction ("3+ years", "5+ years experience", "freshers")
        min_exp = None
        is_fresher = False
        if "fresher" in q_lower or "student" in q_lower or "entry level" in q_lower:
            is_fresher = True
            min_exp = 0.0
        else:
            exp_match = re.search(r'\b(\d+(?:\.\d+)?)\s*(?:\+|\s*plus)?\s*(?:years?|yrs?)\b', q_lower)
            if exp_match:
                min_exp = float(exp_match.group(1))

        # 4. Education extraction ("with mba", "with bca", "b.tech", "m.tech")
        degree = None
        DEGREES = ["mba", "bca", "mca", "b.tech", "m.tech", "bba", "b.sc", "m.sc", "mbbs", "nursing", "ca", "cma"]
        for deg in DEGREES:
            if re.search(r'\b' + re.escape(deg) + r'\b', q_lower):
                degree = deg.upper()
                break

        # 5. Role and Department Matching via RecruiterKnowledgeRegistry
        target_role = None
        department = None
        matched_role_obj = None

        all_roles = recruiter_knowledge_registry.list_roles()
        for r in all_roles:
            rname = r["role_name"].lower()
            if rname in q_lower or any(alt.lower() in q_lower for alt in r.get("alternative_titles", [])):
                target_role = r["role_name"]
                department = r.get("department")
                matched_role_obj = r
                break

        # 6. Skill Extraction
        skills = []
        KNOWN_SKILLS = [
            "react", "angular", "vue", "node", "python", "java", "fastapi", "django",
            "docker", "kubernetes", "aws", "azure", "gcp", "sql", "postgresql",
            "mongodb", "payroll", "recruitment", "hrms", "gst", "tally", "sap",
            "nursing", "triage", "icu", "c++", "c#", "php", "laravel", "git"
        ]
        for sk in KNOWN_SKILLS:
            if re.search(r'\b' + re.escape(sk) + r'\b', q_lower):
                skills.append(sk.title() if len(sk) > 3 else sk.upper())

        # 7. Candidate Name Extraction for candidate-specific intents
        names = []
        NAME_INTENTS = {
            RecruiterIntent.CANDIDATE_COMPARISON,
            RecruiterIntent.CANDIDATE_EXPLANATION,
            RecruiterIntent.CANDIDATE_PROFILE,
            RecruiterIntent.CANDIDATE_SHORTLISTING,
            RecruiterIntent.INTERVIEW_QUESTION_GENERATION
        }
        if intent in NAME_INTENTS:
            name_match = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b', query)
            IGNORE_WORDS = {
                "Find", "Show", "Give", "Compare", "Why", "Generate", "Export", "Search",
                "React", "Angular", "Python", "Java", "Docker", "Aws", "Chennai", "Bangalore",
                "Doctor", "Doctor's", "Nurse", "Nurse's", "HR", "QA", "DevOps", "Mba", "Bca",
                "Developer", "Developers", "Engineer", "Engineers"
            }
            for n in name_match:
                if n not in IGNORE_WORDS and len(n) > 2 and not any(n.lower() in r.get("role_name", "").lower() for r in all_roles):
                    names.append(n)

        plan = QueryPlan(
            raw_query=query,
            intent=intent,
            target_role=target_role,
            department=department,
            skills=list(dict.fromkeys(skills)),
            location=location,
            min_experience=min_exp,
            education_degree=degree,
            is_fresher=is_fresher,
            candidate_names=list(dict.fromkeys(names)),
            limit=limit,
            sort_by="Overall Score"
        )

        logger.info(f"QueryPlanner generated plan for '{query}': Role={plan.target_role}, Skills={plan.skills}, Location={plan.location}, MinExp={plan.min_experience}, Limit={plan.limit}")
        return plan


# Singleton Instance
recruiter_query_planner = RecruiterQueryPlanner()
