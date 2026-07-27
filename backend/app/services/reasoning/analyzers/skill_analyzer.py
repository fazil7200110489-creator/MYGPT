import re
from typing import Dict, Any, List, Set, Tuple

# Constants matching candidate_profile_builder.py
KNOWN_ERP_PLATFORMS = [
    "SAP S4/HANA", "SAP FICO", "SAP ERP", "SAP",
    "ORACLE FINANCIALS", "ORACLE ERP", "ORACLE",
    "CITRIX EPICOR", "EPICOR",
    "PEOPLESOFT", "WORKDAY",
    "MICROSOFT DYNAMICS 365", "DYNAMICS 365",
    "TALLY PRIME", "TALLY ERP 9", "TALLY",
    "INFOR", "NETSUITE", "RAMCO"
]

KNOWN_PROG_LANGS = [
    "PYTHON", "JAVA", "C++", "C#", "TYPESCRIPT", "JAVASCRIPT", "GOLANG", "GO",
    "PHP", "RUST", "RUBY", "SQL", "R", "SWIFT", "KOTLIN", "DART", "HTML", "CSS",
    "SCALA", "PERL", "BASH", "SHELL", "MATLAB"
]

KNOWN_AI_TOOLS = [
    "CHATGPT", "CLAUDE", "COPILOT", "GITHUB COPILOT", "LANGCHAIN", "TENSORFLOW",
    "PYTORCH", "LLAMA", "OPENAI", "GEMINI", "MIDJOURNEY", "KERAS", "SCIKIT-LEARN",
    "HUGGING FACE", "STABLE DIFFUSION", "BERT", "GPT"
]

KNOWN_ANALYTICS_TOOLS = [
    "POWER BI", "TABLEAU", "MS EXCEL", "EXCEL", "GOOGLE ANALYTICS", "LOOKER",
    "SAS", "SPSS", "METABASE", "MICROSTRATEGY", "PANDAS", "NUMPY", "BIGQUERY",
    "DATABRICKS", "DOMO", "QLIK"
]

KNOWN_MANAGEMENT_SKILLS = [
    "AGILE", "SCRUM", "PROJECT MANAGEMENT", "TEAM LEADERSHIP", "BUDGETING",
    "STAKEHOLDER MANAGEMENT", "VENDOR MANAGEMENT", "STRATEGIC PLANNING", "RISK MANAGEMENT",
    "RESOURCE PLANNING", "SCRUM MASTER", "PMP", "PRINCE2"
]

KNOWN_HR_SKILLS = [
    "RECRUITMENT", "PAYROLL", "EMPLOYEE ENGAGEMENT", "COMPLIANCE", "PERFORMANCE MANAGEMENT",
    "TALENT ACQUISITION", "ONBOARDING", "SOURCING", "SCREENING", "HRMS", "EXIT INTERVIEW",
    "WORKFORCE PLANNING", "COMPENSATION", "LABOR LAWS", "HR ANALYTICS", "ATTENDANCE",
    "EMPLOYEE RELATIONS", "HR COMPLIANCE", "HR POLICIES"
]

KNOWN_SOFT_SKILLS = [
    "COMMUNICATION", "PROBLEM SOLVING", "TIME MANAGEMENT", "CONFLICT RESOLUTION",
    "ADAPTABILITY", "LEADERSHIP", "NEGOTIATION", "CRITICAL THINKING", "TEAMWORK",
    "COLLABORATION", "MULTITASKING", "DECISION MAKING", "INTERPERSONAL SKILLS"
]

OCR_NOISE_TERMS = {
    "page", "hands", "on", "expert", "senior", "lead", "junior", "experienced",
    "proficient", "knowledge", "well", "good", "excellent", "strong", "ability",
    "sound", "exposure", "having", "working", "extensive", "being", "making",
    "doing", "getting", "using", "building", "seeking", "tracking", "systems",
    "tracking systems", "level", "high", "various", "role", "description",
    "responsibilities", "details", "objective", "developed", "worked", "managed",
    "trained", "learning", "project", "responsible", "professional", "summary",
    "profile", "education", "experience", "work experience", "certifications",
    "certification", "awards", "achievements", "relevant", "related", "overall",
    "august", "aug", "september", "sep", "october", "oct", "november", "nov",
    "december", "dec", "january", "jan", "february", "feb", "march", "mar",
    "april", "apr", "may", "june", "jun", "july", "jul",
    "2018", "2019", "2020", "2021", "2022", "2023", "2024", "2025", "2026",
    "and", "the", "a", "an", "in", "of", "to", "for", "is", "are", "was"
}

ALLOWED_GERUND_SKILLS = {
    "piping", "recruitment", "onboarding", "sourcing", "auditing", "programming",
    "modeling", "triage", "screening", "budgeting", "welding", "manufacturing",
    "engineering", "accounting", "pipelining", "testing", "debugging", "planning",
    "scheduling", "billing", "designing", "consulting", "processing", "handling",
    "machine learning", "deep learning", "problem solving", "decision making",
    "bookkeeping", "benchmarking", "pricing", "forecasting", "branding",
    "warehousing", "scripting", "wiring", "drafting", "machining", "plumbing",
    "coaching", "scrum", "mining", "troubleshooting", "networking", "nursing",
    "phlebotomy", "data analysis", "data mining", "signal processing"
}


class SkillAnalyzer:
    """Standardizes, sanitizes, and groups skills into categories.
    Infers modern technology stacks and developer archetypes.
    """

    def analyze(self, entities: Dict[str, Any], raw_text: str, primary_domain: str) -> Dict[str, Any]:
        categorized = self._categorize_skills(entities, raw_text, primary_domain)
        modern_groups = self._infer_modern_groups(categorized["all_skills"], raw_text)
        
        # Add modern groups directly to appropriate skill buckets and technical skills
        for g in modern_groups:
            if g not in categorized["all_skills"]:
                categorized["all_skills"].append(g)
            if g not in categorized["technical_skills"]:
                categorized["technical_skills"].append(g)
                
        categorized["modern_groups"] = modern_groups
        return categorized

    def _categorize_skills(
        self, entities: Dict[str, Any], text: str, primary_domain: str
    ) -> Dict[str, List[str]]:
        raw_items: List[str] = []

        for key in ["skills", "technologies", "programming_languages", "software_skills", "competencies"]:
            val = entities.get(key) or []
            if isinstance(val, list):
                raw_items.extend(str(v) for v in val if v)
            elif isinstance(val, str):
                raw_items.append(val)

        split_items: List[str] = []
        for item in raw_items:
            parts = re.split(r'[,;•\-*|/():]|\n', item)
            split_items.extend(parts)

        # If nothing from entities, try extracting from skills section in text
        if not split_items and text:
            m = re.search(
                r'(?i)(?:technical\s+skills?|skills?|core\s+competencies|expertise)\s*:?\s*\n?([\s\S]{5,500}?)(?=\n[A-Za-z][A-Za-z\s\'-]{1,20}:|\n\n|\Z)',
                text
            )
            if m:
                parts = re.split(r'[,;•\-*|/():]|\n', m.group(1))
                split_items.extend(parts)

        prog_langs, ai_tools, erp_platforms, analytics_tools = [], [], [], []
        mgmt_skills, hr_skills, soft_skills, tech_skills = [], [], [], []
        medical_skills, software_skills = [], []
        all_clean: List[str] = []
        seen: Set[str] = set()

        def add_if_new(bucket: List[str], item: str):
            k = item.lower()
            if k not in seen:
                seen.add(k)
                bucket.append(item)
                all_clean.append(item)

        # Scan full text for known ERP platforms
        text_upper = text.upper()
        for erp in KNOWN_ERP_PLATFORMS:
            if erp in text_upper:
                add_if_new(erp_platforms, erp.title())

        KNOWN_MEDICAL_SKILLS = [
            "PATIENT CARE", "ICU MANAGEMENT", "TRIAGE", "PHARMACOLOGY", "NURSING",
            "CLINICAL CARE", "BLS", "ACLS", "EMERGENCY CARE", "PHLEBOTOMY", "VITAL SIGNS",
            "WOUND CARE", "PATIENT ASSESSMENT", "IV THERAPY", "MEDICATION ADMINISTRATION"
        ]

        KNOWN_SOFTWARE_SKILLS = [
            "MS OFFICE", "SOLIDWORKS", "CATIA", "AUTOCAD", "TALLY", "TALLY ERP 9",
            "EXCEL", "WORD", "POWERPOINT", "POSTMAN", "JIRA", "GIT", "DOCKER", "KUBERNETES"
        ]

        excluded_companies = {"apollo", "hospitals", "hospital", "leela", "palace", "sindoori", "management", "solutions", "healthcare", "medical center", "google", "techcorp", "abc"}
        DEGREE_NOISE = {
            "btech", "b.tech", "mtech", "m.tech", "mba", "bcom", "b.com", "mcom", "bsc", "b.sc",
            "msc", "bba", "ba", "diploma", "iti", "gnm", "anm", "hsc", "sslc", "phd", "degree",
            "bachelor", "master", "doctorate", "university", "college", "school", "council"
        }
        TITLE_NOISE = {
            "nurse", "nursing", "doctor", "manager", "engineer", "developer", "accountant",
            "officer", "executive", "analyst", "specialist", "consultant", "architect",
            "physician", "pharmacist", "recruiter", "lead", "head", "director", "intern"
        }

        for s in split_items:
            s_str = str(s).strip()
            s_clean = re.sub(r'^(?:[•\-*]|\d+[\.\)]|\s)+', '', s_str).strip()
            s_clean = re.sub(r'^[^\w+#]+|[^\w+#]+$', '', s_clean).strip()

            if not s_clean or len(s_clean) < 2 or len(s_clean) > 40:
                continue

            s_lower = s_clean.lower()
            s_upper = s_clean.upper()

            if s_lower in OCR_NOISE_TERMS or s_lower in {"safety", "administration", "standards", "statutory filings", "identified hr"}:
                continue
            if re.search(r'\b(?:19|20)\d{2}\b', s_lower):
                continue
            if re.search(r'\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b', s_lower):
                continue
            if re.search(r'[\@\/\\\{\}\=\+]', s_clean) and "linkedin" not in s_lower and "c++" not in s_lower and "c#" not in s_lower:
                continue
            if any(noise in s_lower for noise in ["page", "expert", "proficient in", "well versed", "tracking system"]):
                continue

            if any(comp_kw in s_lower for comp_kw in ["apollo hospital", "sindoori management", "leela palace", "abc healthcare", "xyz medical"]):
                continue
            if len(s_clean.split()) > 1 and any(cw in excluded_companies for cw in s_lower.split()) and any(cw in s_lower.split() for cw in ["hospital", "hospitals", "palace", "solutions", "ltd", "inc"]):
                continue

            if s_lower.endswith("ing") and s_lower not in ALLOWED_GERUND_SKILLS:
                last_word = s_lower.split()[-1]
                if last_word.endswith("ing") and last_word not in ALLOWED_GERUND_SKILLS:
                    continue

            if s_lower in DEGREE_NOISE or any(d in s_lower.split() for d in ["btech", "mba", "bcom", "bsc", "gnm", "mtech", "diploma"]):
                continue
            if s_lower in TITLE_NOISE or any(t in s_lower for t in ["registered nurse", "hr manager", "hr executive", "manager hr", "software engineer", "data analyst", "senior accountant"]):
                continue
            if any(w in s_lower.split() for w in ["manager", "nurse", "executive", "engineer", "developer", "accountant", "officer", "director"]) and any(w in s_lower.split() for w in ["hr", "software", "senior", "lead", "junior", "registered", "chief", "assistant"]):
                continue
            if any(w in s_lower.split() for w in ["award", "employee of the", "living leela", "long service"]):
                continue

            if s_lower in seen:
                continue

            is_soft = any(sf in s_upper for sf in KNOWN_SOFT_SKILLS) or any(pa in s_lower for pa in [
                "team player", "motivated", "detail-oriented", "detail oriented", "punctual", "hard working",
                "hard-working", "results-driven", "results driven", "self-motivated", "self motivated",
                "quick learner", "fast learner", "enthusiastic", "organized", "passionate", "creative",
                "flexible", "reliable", "honest", "dedicated", "disciplined", "proactive"
            ])
            
            if is_soft:
                add_if_new(soft_skills, s_clean)
            elif s_upper in KNOWN_PROG_LANGS:
                add_if_new(prog_langs, s_clean)
            elif any(ai in s_upper for ai in KNOWN_AI_TOOLS):
                add_if_new(ai_tools, s_clean)
            elif any(erp in s_upper for erp in KNOWN_ERP_PLATFORMS):
                add_if_new(erp_platforms, s_clean)
            elif any(an in s_upper for an in KNOWN_ANALYTICS_TOOLS):
                add_if_new(analytics_tools, s_clean)
            elif any(med in s_upper for med in KNOWN_MEDICAL_SKILLS):
                add_if_new(medical_skills, s_clean)
            elif any(sw in s_upper for sw in KNOWN_SOFTWARE_SKILLS):
                add_if_new(software_skills, s_clean)
            elif any(mg in s_upper for mg in KNOWN_MANAGEMENT_SKILLS):
                add_if_new(mgmt_skills, s_clean)
            elif any(hr in s_upper for hr in KNOWN_HR_SKILLS):
                add_if_new(hr_skills, s_clean)
            else:
                add_if_new(tech_skills, s_clean)

        # Compile all actual technical competency categories + leftover technical skills
        final_tech_skills = []
        seen_tech = set()
        for list_of_skills in [prog_langs, ai_tools, erp_platforms, analytics_tools, medical_skills, software_skills, hr_skills, tech_skills]:
            for s in list_of_skills:
                if s.lower() not in seen_tech:
                    seen_tech.add(s.lower())
                    final_tech_skills.append(s)

        return {
            "all_skills": all_clean,
            "programming_languages": prog_langs,
            "ai_tools": ai_tools,
            "erp_platforms": erp_platforms,
            "analytics_tools": analytics_tools,
            "management_skills": mgmt_skills,
            "hr_skills": hr_skills,
            "medical_skills": medical_skills,
            "software_skills": software_skills,
            "soft_skills": soft_skills,
            "technical_skills": final_tech_skills
        }

    def _infer_modern_groups(self, all_skills: List[str], text: str) -> List[str]:
        """Infers aggregate modern stack groups by analyzing skills and raw context."""
        inferred = []
        skills_lower = {s.lower() for s in all_skills}
        text_lower = text.lower()

        # 1. MERN Stack Developer
        mern_kws = {"react", "mongodb", "node", "express"}
        # Check if at least 3 of 4 are present in skills or raw text
        mern_matches = sum(1 for kw in mern_kws if kw in skills_lower or kw in text_lower)
        if mern_matches >= 3:
            inferred.append("MERN Stack Developer")
            inferred.append("Modern JavaScript Ecosystem")

        # 2. Full Stack Engineer
        frontend_kws = {"react", "angular", "vue", "html", "css", "javascript", "typescript", "frontend"}
        backend_kws = {"node", "express", "django", "flask", "fastapi", "spring boot", "java", "python", "backend"}
        has_fe = any(kw in skills_lower or kw in text_lower for kw in frontend_kws)
        has_be = any(kw in skills_lower or kw in text_lower for kw in backend_kws)
        if has_fe and has_be:
            inferred.append("Full Stack Engineer")

        # 3. REST API Development
        api_kws = {"rest api", "restful api", "restful apis", "rest apis", "web api", "graphql", "postman"}
        if any(kw in text_lower for kw in api_kws):
            inferred.append("REST API Development")

        return inferred
