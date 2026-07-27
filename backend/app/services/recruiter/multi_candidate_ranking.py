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
        """Evaluate a single candidate against RequirementProfile across 7 weighted dimensions."""
        profile = candidate_record.get("candidate_profile") or candidate_record
        cid = candidate_record.get("candidate_id") or "UNKNOWN"
        cname = candidate_record.get("name") or profile.get("name", "Candidate")

CANONICAL_SKILL_MAP = {
    "react.js": "React.js", "react": "React.js", "reactjs": "React.js",
    "node.js": "Node.js", "node": "Node.js", "nodejs": "Node.js",
    "express.js": "Express.js", "express": "Express.js", "expressjs": "Express.js",
    "mongodb": "MongoDB", "mongo": "MongoDB",
    "javascript": "JavaScript", "js": "JavaScript",
    "typescript": "TypeScript", "ts": "TypeScript",
    "rest api": "REST API", "restful api": "REST API", "rest apis": "REST API",
    "mern": "MERN Stack", "mern stack": "MERN Stack",
    "python": "Python", "py": "Python",
    "aws": "AWS", "amazon web services": "AWS",
    "docker": "Docker", "kubernetes": "Kubernetes", "k8s": "Kubernetes",
    "fastapi": "FastAPI", "django": "Django", "flask": "Flask",
    "postgresql": "PostgreSQL", "postgres": "PostgreSQL", "sql": "SQL",
    "tailwindcss": "TailwindCSS", "tailwind": "TailwindCSS",
    "html": "HTML/CSS", "css": "HTML/CSS", "html/css": "HTML/CSS",
    "redux": "Redux", "git": "Git", "java": "Java", "c++": "C++", "c#": "C#",
    "php": "PHP", "laravel": "Laravel", "power bi": "Power BI", "excel": "MS Excel",
    "tally": "Tally ERP", "gst": "GST", "sap": "SAP"
}


def normalize_skill(s: str) -> str:
    """Canonical normalization function for technical skills across ranking and search."""
    sl = str(s or "").lower().strip()
    return CANONICAL_SKILL_MAP.get(sl, sl)


def clean_canonical_skill(s: str) -> Optional[str]:
    """Cleans raw skill string, extracting canonical technical skills and filtering sentence fragments."""
    if not s or not isinstance(s, str):
        return None

    sl = s.lower().strip()

    # Direct match in canonical map
    if sl in CANONICAL_SKILL_MAP:
        return CANONICAL_SKILL_MAP[sl]

    # Check if a known canonical skill is embedded inside text (e.g. "applications using React.js" -> "React.js")
    for raw_k, canonical_v in CANONICAL_SKILL_MAP.items():
        if len(raw_k) >= 3 and re.search(r'\b' + re.escape(raw_k) + r'\b', sl):
            return canonical_v

    # Filter out obvious prose noise or sentence fragments
    NOISE_WORDS = {
        "the", "fies", "and", "a", "an", "in", "on", "at", "to", "of", "for", "with", "this", "that", "from",
        "applications", "using", "responsive", "real", "world", "built", "developing", "experience", "knowledge",
        "working", "system", "systems", "solutions", "all", "both", "candidate", "candidates"
    }
    words = set(re.findall(r'\b\w+\b', sl))
    if words and words.issubset(NOISE_WORDS):
        return None

    if len(words) >= 2 and words.intersection(NOISE_WORDS):
        return None

    if len(s.strip()) > 30:
        return None

    return s.strip().title()


def extract_all_candidate_skills(candidate_record: Dict[str, Any]) -> List[str]:
    """Extracts all raw skills, technologies, and programming languages from a candidate record."""
    profile = candidate_record.get("candidate_profile") or candidate_record
    skills_set = set()

    for k in ["skills", "technologies", "programming_languages", "software_skills", "competencies"]:
        vals = profile.get(k) or candidate_record.get(k) or []
        if isinstance(vals, list):
            for v in vals:
                if v and isinstance(v, str):
                    c_sk = clean_canonical_skill(v)
                    if c_sk:
                        skills_set.add(c_sk)
        elif isinstance(vals, str) and vals:
            for v in vals.split(","):
                c_sk = clean_canonical_skill(v)
                if c_sk:
                    skills_set.add(c_sk)

    return list(skills_set)


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
        """Evaluate a single candidate against RequirementProfile across 7 weighted dimensions."""
        profile = candidate_record.get("candidate_profile") or candidate_record
        cid = candidate_record.get("candidate_id") or "UNKNOWN"
        cname = candidate_record.get("name") or profile.get("name", "Candidate")

        # 1. Technical Skill Match Score (40% Weight)
        cand_skills_raw = extract_all_candidate_skills(candidate_record)
        cand_skills_norm = [normalize_skill(str(s)) for s in cand_skills_raw]
        req_skills_all = req.required_skills + req.preferred_skills

        matched_skills = []
        missing_skills = []

        if req_skills_all:
            for rsk in req_skills_all:
                r_norm = normalize_skill(rsk)
                if any(r_norm in cs or cs in r_norm for cs in cand_skills_norm):
                    matched_skills.append(rsk)
                else:
                    missing_skills.append(rsk)
            skill_score = (len(matched_skills) / len(req_skills_all)) * 100.0
        else:
            skill_score = 80.0

        # 2. Experience Match Score (20% Weight)
        exp_str = profile.get("total_experience", "0")
        m_exp = re.search(r'(\d+)', str(exp_str))
        cand_years = float(m_exp.group(1)) if m_exp else 0.0

        if req.min_experience_years <= 0:
            exp_score = 90.0
        elif cand_years >= req.min_experience_years:
            exp_score = min(100.0, 80.0 + ((cand_years - req.min_experience_years) * 5.0))
        else:
            exp_score = max(20.0, (cand_years / req.min_experience_years) * 70.0)

        # 3. Project Match Score (15% Weight)
        projects = profile.get("projects", [])
        proj_score = 50.0
        if projects:
            proj_score = 75.0
            # Check if project descriptions touch role skills
            proj_text = " ".join([str(p) for p in projects]).lower()
            if any(normalize_skill(sk) in proj_text for sk in matched_skills):
                proj_score = 95.0
        elif profile.get("has_dedicated_projects"):
            proj_score = 85.0

        # 4. Education Match Score (10% Weight)
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

        # 5. Certification Match Score (5% Weight)
        certs = [str(c).lower() for c in profile.get("certifications", [])]
        cert_score = 70.0
        if req.certification_requirements:
            cert_matches = [rc for rc in req.certification_requirements if any(rc.lower() in c for c in certs)]
            cert_score = (len(cert_matches) / len(req.certification_requirements) * 100.0) if cert_matches else 40.0
        else:
            cert_score = 85.0 if certs else 60.0

        # 6. Resume Quality Score (5% Weight)
        quality_factors = 0
        if profile.get("name") and profile.get("name") != "Not Mentioned": quality_factors += 1
        if profile.get("email") and profile.get("email") != "Not Mentioned": quality_factors += 1
        if profile.get("phone") and profile.get("phone") != "Not Mentioned": quality_factors += 1
        if profile.get("skills"): quality_factors += 1
        if profile.get("education"): quality_factors += 1
        if profile.get("work_experience") or profile.get("companies"): quality_factors += 1
        if profile.get("projects"): quality_factors += 1
        quality_score = min(100.0, (quality_factors / 7.0) * 100.0)

        # 7. Domain Match Score (5% Weight)
        cand_domain = profile.get("primary_domain") or profile.get("domain", "")
        domain_score = 95.0 if req.department.lower() in cand_domain.lower() or ("hr" in cand_domain.lower() and "hr" in req.department.lower()) else 75.0

        # Configurable Weighted Score Calculation (User Standard Weights: 40/20/15/10/5/5/5)
        weights = {
            "technical_skills": 40.0,
            "experience": 20.0,
            "projects": 15.0,
            "education": 10.0,
            "certifications": 5.0,
            "resume_quality": 5.0,
            "domain_match": 5.0
        }

        weighted_sum = (
            (skill_score * weights["technical_skills"]) +
            (exp_score * weights["experience"]) +
            (proj_score * weights["projects"]) +
            (edu_score * weights["education"]) +
            (cert_score * weights["certifications"]) +
            (quality_score * weights["resume_quality"]) +
            (domain_score * weights["domain_match"])
        )
        total_weight = sum(weights.values())
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
                "technical_skills": round(skill_score, 1),
                "skill_match": round(skill_score, 1),
                "experience": round(exp_score, 1),
                "experience_match": round(exp_score, 1),
                "projects": round(proj_score, 1),
                "project_match": round(proj_score, 1),
                "education": round(edu_score, 1),
                "education_match": round(edu_score, 1),
                "certifications": round(cert_score, 1),
                "certification_match": round(cert_score, 1),
                "resume_quality": round(quality_score, 1),
                "domain_match": round(domain_score, 1),
                "department_match": round(domain_score, 1),
                "role_match": round(skill_score, 1),
                "tool_match": round(skill_score, 1),
                "technology_match": round(skill_score, 1)
            },
            "matched_skills": list(dict.fromkeys(matched_skills)),
            "missing_skills": list(dict.fromkeys(missing_skills)),
            "candidate_profile": profile
        }


# Singleton Instance
multi_candidate_ranking = MultiCandidateRanking()
