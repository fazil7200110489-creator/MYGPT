"""Canonical Skill Normalizer — Single Shared Normalization Layer for Resume Intelligence Engine.
"""

import re
from typing import Dict, Any, List, Set, Tuple, Optional

# Canonical skill map: lowercase variant -> Canonical Name
CANONICAL_SKILL_MAP: Dict[str, str] = {
    # REST API & Web Services
    "rest api": "REST API",
    "restful api": "REST API",
    "restful apis": "REST API",
    "rest apis": "REST API",
    "api development": "REST API",
    "api integration": "REST API",
    "backend apis": "REST API",
    "backend api": "REST API",
    "api design": "REST API",
    "restful api design": "REST API",
    "rest api development": "REST API",
    "web api": "REST API",
    "web apis": "REST API",

    # Frontend Frameworks & Libraries
    "react": "React",
    "react.js": "React",
    "reactjs": "React",
    "react js": "React",
    "react ecosystem": "React",
    "angular": "Angular",
    "angularjs": "Angular",
    "angular.js": "Angular",
    "vue": "Vue.js",
    "vue.js": "Vue.js",
    "vuejs": "Vue.js",
    "next.js": "Next.js",
    "nextjs": "Next.js",
    "nuxt": "Nuxt.js",
    "nuxt.js": "Nuxt.js",
    "svelte": "Svelte",
    "redux": "Redux",

    # Backend Runtimes & Frameworks
    "node": "Node.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "node js": "Node.js",
    "express": "Express.js",
    "express.js": "Express.js",
    "expressjs": "Express.js",
    "express js": "Express.js",
    "nest": "NestJS",
    "nestjs": "NestJS",
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "spring": "Spring Boot",
    "spring boot": "Spring Boot",
    "laravel": "Laravel",

    # Web Fundamentals
    "html": "HTML",
    "html5": "HTML",
    "css": "CSS",
    "css3": "CSS",
    "tailwind": "Tailwind CSS",
    "tailwind css": "Tailwind CSS",
    "tailwindcss": "Tailwind CSS",
    "bootstrap": "Bootstrap",
    "responsive ui": "Responsive UI",
    "responsive design": "Responsive UI",

    # Databases
    "mongodb": "MongoDB",
    "mongo": "MongoDB",
    "mongodb database": "MongoDB",
    "mysql": "MySQL",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "sqlite": "SQLite",
    "redis": "Redis",
    "oracle": "Oracle",
    "sql server": "SQL Server",
    "mssql": "SQL Server",

    # Programming Languages
    "javascript": "JavaScript",
    "js": "JavaScript",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    "php": "PHP",
    "php 8": "PHP",
    "php 7": "PHP",
    "php7": "PHP",
    "php8": "PHP",
    "python": "Python",
    "python 3": "Python",
    "java": "Java",
    "c++": "C++",
    "c#": "C#",
    "golang": "Go",
    "go": "Go",
    "rust": "Rust",
    "ruby": "Ruby",
    "swift": "Swift",
    "kotlin": "Kotlin",
    "dart": "Dart",
    "sql": "SQL",

    # Security & Auth
    "jwt": "JWT",
    "jwt authentication": "JWT",
    "jwt auth": "JWT",
    "oauth": "OAuth 2.0",
    "oauth2": "OAuth 2.0",
    "oauth 2.0": "OAuth 2.0",

    # DevOps & Infrastructure
    "docker": "Docker",
    "docker container": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "aws": "AWS",
    "amazon web services": "AWS",
    "gcp": "GCP",
    "google cloud": "GCP",
    "azure": "Azure",
    "git": "Git",
    "github": "GitHub",
    "gitlab": "GitLab",
    "ci/cd": "CI/CD",
}

# Alias Map: Canonical Name -> List of lowercase aliases
ALIAS_MAP: Dict[str, List[str]] = {
    "REST API": [
        "rest api", "restful api", "restful apis", "rest apis",
        "api development", "api integration", "backend apis", "backend api",
        "api design", "restful api design", "rest api development", "web api", "web apis"
    ],
    "React": ["react", "react.js", "reactjs", "react js", "react ecosystem"],
    "Node.js": ["node", "nodejs", "node.js", "node js"],
    "Express.js": ["express", "express.js", "expressjs", "express js"],
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3"],
    "JWT": ["jwt", "jwt authentication", "jwt auth"],
    "MongoDB": ["mongodb", "mongo", "mongodb database"],
    "PHP": ["php", "php 8", "php 7", "php7", "php8"],
    "JavaScript": ["javascript", "js"],
    "TypeScript": ["typescript", "ts"],
    "MySQL": ["mysql"],
    "PostgreSQL": ["postgresql", "postgres"],
    "Docker": ["docker", "docker container"],
    "Kubernetes": ["kubernetes", "k8s"],
    "AWS": ["aws", "amazon web services"],
    "Tailwind CSS": ["tailwind", "tailwind css", "tailwindcss"],
    "Git": ["git"],
    "GitHub": ["github"],
    "Python": ["python", "python 3"],
    "Java": ["java"],
    "C++": ["c++"],
    "C#": ["c#"],
    "Angular": ["angular", "angularjs", "angular.js"],
    "Vue.js": ["vue", "vue.js", "vuejs"],
    "Next.js": ["next.js", "nextjs"],
    "Responsive UI": ["responsive ui", "responsive design"],
}


class SkillNormalizer:
    """Canonical Skill Normalization service."""

    @staticmethod
    def normalize_skill(raw_skill: str) -> Tuple[str, List[str]]:
        """Normalize skill string to canonical name and return alias list.

        Args:
            raw_skill: Input skill name or string.

        Returns:
            Tuple of (canonical_name, alias_list).
        """
        s_clean = str(raw_skill).strip()
        s_lower = s_clean.lower()

        canonical_name = CANONICAL_SKILL_MAP.get(s_lower, s_clean.title())
        aliases = ALIAS_MAP.get(canonical_name, [s_lower])
        if s_lower not in aliases:
            aliases = list(aliases) + [s_lower]

        return canonical_name, aliases

    @staticmethod
    def search_skill_in_knowledge(
        candidate_profile: Dict[str, Any],
        full_text: str = "",
        query_skill: str = ""
    ) -> Tuple[bool, str, List[str]]:
        """Search ALL candidate knowledge sections for evidence of a normalized skill.

        Checks:
        1. Canonical Skills & Aliases
        2. Categorized Skills (Technical, Frontend, Backend, Database, Frameworks, Tools)
        3. Work Experience & Responsibilities
        4. Detailed Projects
        5. Summary & Overview
        6. Certifications & Education
        7. Full Resume Text

        Args:
            candidate_profile: Normalized candidate profile dictionary.
            full_text: Full raw resume text.
            query_skill: Skill to search for.

        Returns:
            Tuple of (is_present, canonical_name, evidence_sections).
        """
        if not query_skill:
            return False, "", []

        canonical_name, aliases = SkillNormalizer.normalize_skill(query_skill)
        alias_set = {a.lower() for a in aliases}
        alias_set.add(canonical_name.lower())
        alias_set.add(query_skill.lower())

        evidence_sections: List[str] = []

        # Helper to check if any alias is present in text or list of strings
        def matches_text(text: str) -> bool:
            t_lower = text.lower()
            for alias in alias_set:
                # Word boundary check for short tokens (e.g. "js", "ts", "go", "c")
                if len(alias) <= 3:
                    if re.search(r'\b' + re.escape(alias) + r'\b', t_lower):
                        return True
                else:
                    if alias in t_lower:
                        return True
            return False

        def matches_list(items: List[Any]) -> bool:
            for item in items:
                if isinstance(item, str) and matches_text(item):
                    return True
                elif isinstance(item, dict):
                    for val in item.values():
                        if isinstance(val, str) and matches_text(val):
                            return True
                        elif isinstance(val, list) and matches_list(val):
                            return True
            return False

        profile = candidate_profile or {}

        # 1. Technical Skills Section
        skills_list = profile.get("skills") or []
        canonical_skills = profile.get("canonical_skills") or []
        tech_skills = profile.get("technical_skills") or []
        if matches_list(skills_list) or matches_list(canonical_skills) or matches_list(tech_skills):
            evidence_sections.append("Technical Skills")

        # Categorized Skills
        cat_skills = profile.get("categorized_skills") or {}
        for cat_name, cat_items in cat_skills.items():
            if isinstance(cat_items, list) and matches_list(cat_items):
                sec_name = f"Categorized Skills ({cat_name})"
                if sec_name not in evidence_sections:
                    evidence_sections.append(sec_name)

        # 2. Work Experience & Responsibilities Section
        exp_list = profile.get("experience_history") or profile.get("experience_timeline") or profile.get("experience") or []
        if matches_list(exp_list):
            evidence_sections.append("Work Experience")

        # 3. Projects Section
        proj_list = profile.get("detailed_projects") or profile.get("projects") or profile.get("rich_projects") or []
        if matches_list(proj_list):
            evidence_sections.append("Projects")

        # 4. Summary & Overview
        summary = profile.get("summary") or profile.get("executive_summary") or ""
        if summary and matches_text(str(summary)):
            evidence_sections.append("Summary")

        # 5. Certifications & Education
        certs = profile.get("certifications") or []
        edu = profile.get("education") or []
        if matches_list(certs):
            evidence_sections.append("Certifications")
        if matches_list(edu):
            evidence_sections.append("Education")

        # 6. Fallback check on full text if not yet found in profile fields
        if not evidence_sections and full_text and matches_text(full_text):
            evidence_sections.append("Resume Context")

        is_present = len(evidence_sections) > 0
        return is_present, canonical_name, evidence_sections


# Global singleton instance
skill_normalizer = SkillNormalizer()
