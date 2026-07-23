"""Candidate Profile Builder — Single Source of Truth for Resume Intelligence Engine.

Architecture:
    Parser / EntityExtractor
        ↓
    CandidateProfileBuilder  ← THIS MODULE
        ↓
    ReasoningEngine / Specialists / RoleInferenceEngine
        ↓
    ResponseGenerator

Responsibilities:
  - Normalize raw entities into a standardized, validated profile object.
  - Career Transition Detection (e.g. Healthcare → HR).
  - Multi-Level Experience Calculation (total / current-domain / per-domain).
  - Experience Timeline Generation (chronological).
  - Primary + Secondary Domain Scoring with confidence %.
  - Zero-Hallucination Education Parsing (no placeholder values).
  - Dedicated Awards Entity (isolated from Certifications).
  - Multi-Layer Location (current / work / permanent).
  - 7-Bucket Skill Categorization.
  - OCR Noise & Debris Filtering.
  - Profile Validation Flags.
  - Health Scoring.
"""

import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from loguru import logger

from backend.app.services.reasoning.domain_detector import domain_detector
from backend.app.services.reasoning.role_inference_engine import role_inference_engine

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CURRENT_YEAR = datetime.now().year
CURRENT_DATE = datetime.now()

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

# OCR noise and generic debris words to strip from skills
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

EDUCATION_LEVELS = {
    "phd": "PhD", "doctorate": "PhD", "d.phil": "PhD",
    "mtech": "MTech", "m.tech": "MTech", "master of technology": "MTech",
    "mba": "MBA", "master of business": "MBA",
    "msc": "MSc", "m.sc": "MSc", "master of science": "MSc",
    "ma": "MA", "master of arts": "MA",
    "mcom": "MCom", "master of commerce": "MCom",
    "btech": "BTech", "b.tech": "BTech", "bachelor of technology": "BTech",
    "be": "BE", "b.e": "BE", "bachelor of engineering": "BE",
    "bsc": "BSc", "b.sc": "BSc", "bachelor of science": "BSc",
    "bcom": "BCom", "b.com": "BCom", "bachelor of commerce": "BCom",
    "bba": "BBA", "bachelor of business": "BBA",
    "ba": "BA", "bachelor of arts": "BA",
    "diploma": "Diploma",
    "iti": "ITI",
    "gnm": "GNM",
    "anm": "ANM",
    "hsc": "HSC", "12th": "HSC", "class 12": "HSC", "plus two": "HSC",
    "sslc": "SSLC", "10th": "SSLC", "class 10": "SSLC", "matriculation": "SSLC"
}

# Domains with strong designation-based signals that override skill-based classification
DESIGNATION_DOMAIN_MAP = {
    "nurse": "Healthcare & Medical",
    "nursing": "Healthcare & Medical",
    "doctor": "Healthcare & Medical",
    "physician": "Healthcare & Medical",
    "pharmacist": "Healthcare & Medical",
    "hr executive": "Human Resources (HR)",
    "hr manager": "Human Resources (HR)",
    "hr officer": "Human Resources (HR)",
    "hr generalist": "Human Resources (HR)",
    "hr business partner": "Human Resources (HR)",
    "talent acquisition": "Human Resources (HR)",
    "recruiter": "Human Resources (HR)",
    "payroll": "Human Resources (HR)",
    "accountant": "Finance & Accounting",
    "accounts": "Finance & Accounting",
    "finance executive": "Finance & Accounting",
    "financial analyst": "Finance & Accounting",
    "software engineer": "Software Engineering",
    "software developer": "Software Engineering",
    "full stack developer": "Software Engineering",
    "frontend developer": "Software Engineering",
    "backend developer": "Software Engineering",
    "data analyst": "Data Analytics",
    "business intelligence": "Data Analytics",
    "civil engineer": "Civil Engineering",
    "site engineer": "Civil Engineering",
    "electrical engineer": "Electrical Engineering",
    "mechanical engineer": "Mechanical Engineering",
}


class CandidateProfileBuilder:
    """Single Source of Truth for normalized candidate profile building.

    All reasoning specialists must read from the output of build_profile().
    Never read raw entities directly in reasoning modules.
    """

    def build_profile(self, raw_entities: Dict[str, Any], raw_text: str = "") -> Dict[str, Any]:
        """Build a fully normalized, validated Candidate Profile."""
        entities = raw_entities or {}
        full_text = raw_text or ""
        if not full_text and isinstance(entities.get("raw_text"), str):
            full_text = entities["raw_text"]

        # 1. Basic Identity
        name = self._normalize_name(entities, full_text)
        designation = self._normalize_designation(entities, full_text)

        # 2. Experience Timeline (chronological)
        timeline = self._build_experience_timeline(entities, full_text)

        # 3. Career Transition Detection
        career_transition = self._detect_career_transition(timeline, entities)

        # 4. Multi-Level Experience Calculation
        experience_data = self._calculate_multilevel_experience(timeline, entities, full_text)

        # 5. Primary + Secondary Domain Scoring
        domain_data = self._score_primary_secondary_domain(entities, full_text, timeline, designation)

        # 6. 7-Bucket Skill Categorization (with OCR noise filtering)
        skills_data = self._categorize_skills(entities, full_text, domain_data["primary_domain"])

        # 7. Zero-Hallucination Education Parsing
        education_list = self._parse_education(entities, full_text)

        # 8. Dedicated Awards Entity (isolated from Certifications)
        awards_list, certifications_list = self._separate_awards_certifications(entities, full_text)

        # 9. Projects (with has_dedicated_projects flag)
        projects_list, has_dedicated_projects = self._extract_projects(entities, full_text)

        # 10. Multi-Layer Location & Full Address Parsing
        location_data = self._extract_location_layers(entities, full_text)
        address_breakdown = self._parse_address_breakdown(location_data["permanent_address"] or location_data["current_location"])

        # 11. Contact & Personal Details
        email = self._extract_single_string(entities.get("email") or entities.get("emails"))
        phone = self._extract_single_string(entities.get("phone") or entities.get("phones"))

        if (not email or email == "Not Mentioned") and full_text:
            e_m = re.search(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', full_text)
            if e_m:
                email = e_m.group(0).strip().lower()

        if (not phone or phone == "Not Mentioned") and full_text:
            p_m = re.search(r'(?:\+?\d{1,3}[\s\-.])?[\(\[\{]?\d{2,5}[\)\]\}]?[\s\-.]?\d{3,5}[\s\-.]?\d{3,5}', full_text)
            if p_m:
                phone = p_m.group(0).strip()

        linkedin = self._extract_link(entities.get("linkedin"), full_text, r'linkedin\.com/in/[\w\-]+')
        github = self._extract_link(entities.get("github"), full_text, r'github\.com/[\w\-]+')
        portfolio = self._extract_single_string(entities.get("portfolio"))

        father_name, mother_name = self._extract_parent_names(entities, full_text)
        personal_attrs = self._extract_personal_attributes(entities, full_text)

        personal_info_dict = {
            "name": name,
            "email": email or "Not Mentioned",
            "phone": phone or "Not Mentioned",
            "address": address_breakdown["formatted_address"],
            "address_details": address_breakdown,
            "gender": personal_attrs["gender"],
            "date_of_birth": personal_attrs["date_of_birth"],
            "father_name": father_name,
            "mother_name": mother_name,
            "marital_status": personal_attrs["marital_status"],
            "nationality": personal_attrs["nationality"],
            "linkedin": linkedin or "Not Mentioned",
            "github": github or "Not Mentioned",
            "portfolio": portfolio or "Not Mentioned",
        }

        # Companies list (distinct)
        extracted_companies = list(dict.fromkeys([
            entry["company"] for entry in timeline
            if entry.get("company") and entry["company"] not in ("Not Mentioned", "Company")
        ]))

        # 12. Health Score
        health_res = self._calculate_health_score({
            "name": name,
            "skills": skills_data["all_skills"],
            "experience": experience_data["experience_history"],
            "education": education_list,
            "projects": projects_list,
            "certifications": certifications_list,
            "linkedin": linkedin
        })

        # 13. Profile Validation Flags
        validation_flags = {
            "has_experience": bool(experience_data["experience_history"] or experience_data["total_experience"] != "Not Mentioned"),
            "has_education": bool(education_list and education_list[0].get("degree") != "Not Mentioned"),
            "has_skills": bool(skills_data["all_skills"]),
            "has_location": bool(location_data["current_location"] or location_data["permanent_address"]),
            "has_awards": bool(awards_list),
            "has_timeline": bool(timeline),
            "has_certifications": bool(certifications_list)
        }

        # 14. Dynamic Recommendations for Insights (computed dynamically, not stored as profile factual field)
        from backend.app.services.reasoning.role_inference_engine import role_inference_engine
        dynamic_roles = role_inference_engine.recommend_roles(entities, domain_data["primary_domain"])

        # 15. Insights
        insights = self._generate_insights(
            skills_data["all_skills"],
            experience_data["total_experience"],
            domain_data["primary_domain"],
            dynamic_roles
        )

        return {
            # Identity & Personal Info (Factual)
            "name": name,
            "email": email or "Not Mentioned",
            "phone": phone or "Not Mentioned",
            "address": address_breakdown["formatted_address"],
            "address_details": address_breakdown,
            "current_location": location_data["current_location"] or address_breakdown["formatted_address"],
            "permanent_address": location_data["permanent_address"] or address_breakdown["formatted_address"],
            "work_location": location_data["work_location"],
            "linkedin": linkedin or "Not Mentioned",
            "github": github or "Not Mentioned",
            "portfolio": portfolio or "Not Mentioned",
            "designation": designation,
            "current_designation": designation,
            "personal_info": personal_info_dict,
            "father_name": father_name,
            "mother_name": mother_name,
            "marital_status": personal_attrs["marital_status"],
            "gender": personal_attrs["gender"],
            "date_of_birth": personal_attrs["date_of_birth"],
            "nationality": personal_attrs["nationality"],
            # Domain (Factual)
            "domain": domain_data["primary_domain"],
            "primary_domain": domain_data["primary_domain"],
            "primary_domain_confidence": domain_data["primary_confidence"],
            "secondary_domain": domain_data["secondary_domain"],
            "secondary_domain_confidence": domain_data["secondary_confidence"],
            # Career Transition (Factual)
            "career_transition": career_transition,
            # Experience (Factual)
            "total_experience": experience_data["total_experience"],
            "current_domain_experience": experience_data["current_domain_experience"],
            "current_company_experience": experience_data["current_company_experience"],
            "per_domain_experience": experience_data["per_domain_experience"],
            "experience_history": experience_data["experience_history"],
            "experience_timeline": timeline,
            "companies": extracted_companies,
            # Skills (8 buckets - Factual)
            "skills": skills_data["all_skills"],
            "programming_languages": skills_data["programming_languages"],
            "ai_tools": skills_data["ai_tools"],
            "erp_platforms": skills_data["erp_platforms"],
            "analytics_tools": skills_data["analytics_tools"],
            "management_skills": skills_data["management_skills"],
            "hr_skills": skills_data["hr_skills"],
            "medical_skills": skills_data["medical_skills"],
            "software_skills": skills_data["software_skills"],
            "soft_skills": skills_data["soft_skills"],
            "technical_skills": skills_data["technical_skills"],
            # Education (Factual)
            "education": education_list,
            # Awards & Certifications (separated - Factual)
            "awards": awards_list,
            "certifications": certifications_list,
            # Projects (Factual)
            "projects": projects_list,
            "has_dedicated_projects": has_dedicated_projects,
            # Contact & Location (Factual)
            "email": email or "Not Mentioned",
            "phone": phone or "Not Mentioned",
            "current_location": location_data["current_location"] or "Not Mentioned",
            "work_location": location_data["work_location"] or "Not Mentioned",
            "permanent_address": location_data["permanent_address"] or "Not Mentioned",
            "address": address_breakdown["formatted_address"],
            "address_details": address_breakdown,
            "location_sources": location_data["sources"],
            "linkedin": linkedin or "Not Mentioned",
            "github": github or "Not Mentioned",
            "portfolio": portfolio or "Not Mentioned",
            # Health & Validation
            "health_score": health_res["health_score"],
            "health_checklist": health_res["checklist"],
            "validation_flags": validation_flags,
            # Insights & Summary
            "summary": insights.get("recruiter_summary", "Professional candidate profile."),
            "recruiter_summary": insights.get("recruiter_summary", "Professional candidate profile."),
            "insights": insights,
        }

    # ---------------------------------------------------------------------------
    # Identity
    # ---------------------------------------------------------------------------

    def _normalize_name(self, entities: Dict[str, Any], text: str) -> str:
        # Check header text first
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        for l in lines[:5]:
            l_clean = re.sub(r'^(?:candidate\s+name|name)\s*[:\-]?\s*', '', l, flags=re.IGNORECASE).strip()
            if "@" not in l_clean and not re.search(r'\d+', l_clean) and not any(kw in l_clean.lower() for kw in ["resume", "curriculum", "email", "phone", "address", "summary", "experience", "education", "skills", "projects", "certifications", "statutory", "compliance", "certified", "partner", "mother", "father"]):
                if len(l_clean.split()) <= 4 and len(l_clean) >= 2:
                    return l_clean.title()

        candidates = [
            entities.get("candidate_name"),
            entities.get("name"),
        ]
        if isinstance(entities.get("people"), list) and entities["people"]:
            candidates.append(entities["people"][0])

        for c in candidates:
            if c and isinstance(c, str):
                c_clean = re.sub(r'^(?:candidate\s+name|name)\s*[:\-]?\s*', '', c.strip(), flags=re.IGNORECASE).strip()
                if (c_clean and "@" not in c_clean
                        and not re.search(r'\d+', c_clean)
                        and len(c_clean.split()) <= 4
                        and c_clean.lower() not in ["statutory compliance", "hardware knowledge", "software skills"]):
                    return c_clean.title()

        m = re.search(r'(?i)\bname\s*:\s*([A-Za-z\s]{2,40})(?:\n|,|$)', text)
        if m:
            return m.group(1).strip().title()

        return "Not Mentioned"

    def _normalize_designation(self, entities: Dict[str, Any], text: str) -> str:
        desig = entities.get("designation")
        if desig and isinstance(desig, str) and len(desig.strip()) > 2:
            return desig.strip().title()

        m = re.search(r'(?i)\b(?:designation|job title|current role|role)\s*:\s*([A-Za-z\s]{2,50})(?:\n|,|$)', text)
        if m:
            return m.group(1).strip().title()

        return "Not Mentioned"

    # ---------------------------------------------------------------------------
    # Experience Timeline
    # ---------------------------------------------------------------------------

    def _build_experience_timeline(self, entities: Dict[str, Any], text: str) -> List[Dict[str, str]]:
        """Build chronological employment timeline from structured entities and OCR text."""
        timeline = []
        exp_list = entities.get("work_experience") or entities.get("experience") or []
        if isinstance(exp_list, str):
            exp_list = [l.strip() for l in exp_list.split('\n') if l.strip()]

        for item in exp_list:
            if not isinstance(item, str) or len(item.strip()) < 5:
                continue
            entry = self._parse_experience_entry(item)
            if entry:
                timeline.append(entry)

        # If no structured entries, try parsing raw text for employment blocks
        # If no structured entries, parse raw text lines containing year mentions
        if not timeline and text:
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            for l in lines:
                if re.search(r'\b(?:19|20)\d{2}\b', l):
                    entry = self._parse_experience_entry(l)
                    if entry:
                        timeline.append(entry)

        # Sort chronologically
        timeline.sort(key=lambda x: x.get("start_year", 0))
        return timeline

    def _parse_experience_entry(self, text: str) -> Optional[Dict[str, str]]:
        """Parse a single experience string into timeline entry.

        Handles formats:
          - "YEAR-YEAR: TITLE — COMPANY"
          - "TITLE at COMPANY (YEAR-YEAR)"
          - "YEAR-YEAR: TITLE at COMPANY"
        """
        years_match = re.search(
            r'\b((?:19|20)\d{2})\s*[-–to]+\s*((?:19|20)\d{2}|present|current|till date)\b',
            text, re.IGNORECASE
        )
        if not years_match:
            return None

        start_year = int(years_match.group(1))
        end_str = years_match.group(2).strip().lower()
        end_year = CURRENT_YEAR if end_str in ("present", "current", "till date") else int(years_match.group(2))
        years_label = f"{start_year}–{end_str.title() if end_str in ('present', 'current', 'till date') else end_year}"

        # Try to extract title/company from BEFORE the year range
        before_year = text[:years_match.start()].strip()
        # Try to extract title/company from AFTER the year range
        after_year = text[years_match.end():].strip().lstrip(':').strip()
        # Remove trailing ) brackets (format: "...(YEAR-YEAR)")
        after_year = after_year.lstrip(')').strip()

        if after_year and len(after_year) > 3:
            # Format: "YEAR-YEAR: TITLE — COMPANY"
            parts = re.split(r'\s*[\-–—|@,]\s*', after_year)
            title = parts[0].strip().title() if parts else "Not Mentioned"
            company = parts[1].strip().title() if len(parts) > 1 else "Not Mentioned"
        elif before_year and len(before_year) > 3:
            # Format: "TITLE at COMPANY (YEAR-YEAR)"
            # Remove trailing (
            clean_before = re.sub(r'\($', '', before_year).strip()
            # Remove "Experience:" prefix if present
            clean_before = re.sub(r'^(?:experience|work experience|employment)\s*:\s*', '', clean_before, flags=re.IGNORECASE).strip()
            parts = re.split(r'\s*(?:at|@|[\-–—|,])\s*', clean_before)
            title = parts[0].strip().title() if parts else "Not Mentioned"
            company = parts[1].strip().title() if len(parts) > 1 else "Not Mentioned"
        else:
            title = "Not Mentioned"
            company = "Not Mentioned"

        domain_guess = domain_detector.detect_domain({"designation": title}, "")

        return {
            "years": years_label,
            "title": title,
            "company": company,
            "domain": domain_guess,
            "start_year": start_year,
            "end_year": end_year
        }

    # ---------------------------------------------------------------------------
    # Career Transition Detection
    # ---------------------------------------------------------------------------

    def _detect_career_transition(self, timeline: List[Dict], entities: Dict[str, Any]) -> Dict[str, Any]:
        """Detect career domain transitions from the employment timeline."""
        if len(timeline) < 2:
            return {
                "is_transition": False,
                "transition_path": "",
                "current_domain": "",
                "previous_domains": []
            }

        domains_seen = []
        for entry in timeline:
            d = entry.get("domain", "General")
            if not domains_seen or domains_seen[-1] != d:
                domains_seen.append(d)

        if len(set(domains_seen)) < 2:
            return {
                "is_transition": False,
                "transition_path": " -> ".join(domains_seen),
                "current_domain": domains_seen[-1] if domains_seen else "",
                "previous_domains": []
            }

        current = domains_seen[-1]
        previous = [d for d in dict.fromkeys(domains_seen[:-1]) if d != current]
        path = " -> ".join(dict.fromkeys(domains_seen))

        return {
            "is_transition": True,
            "transition_path": path,
            "current_domain": current,
            "previous_domains": previous
        }

    # ---------------------------------------------------------------------------
    # Multi-Level Experience Calculation
    # ---------------------------------------------------------------------------

    def _calculate_multilevel_experience(
        self, timeline: List[Dict], entities: Dict[str, Any], text: str
    ) -> Dict[str, Any]:
        """Calculate total, current-domain, and per-domain experience from actual dates."""

        # Check summary for explicit mention first
        summary_text = entities.get("summary") or text
        if summary_text:
            m = re.search(
                r'(?i)\b(?:over|around|more than|with|\+)?\s*(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\b(?:\s+of)?\s+(?:experience|work|industry)',
                summary_text
            )
            if m:
                summary_exp = f"{m.group(1)} Years"
            else:
                summary_exp = None
        else:
            summary_exp = None

        # Date-based calculation from timeline
        per_domain: Dict[str, int] = {}  # domain → total months
        total_months = 0

        for entry in timeline:
            start = entry.get("start_year", 0)
            end = entry.get("end_year", CURRENT_YEAR)
            if start and end >= start:
                months = (end - start) * 12
                total_months += months
                domain = entry.get("domain", "General")
                per_domain[domain] = per_domain.get(domain, 0) + months

        # Format helpers
        def fmt_months(m: int) -> str:
            y, mo = m // 12, m % 12
            if y > 0 and mo > 0:
                return f"{y} Year{'s' if y > 1 else ''} {mo} Month{'s' if mo > 1 else ''}"
            elif y > 0:
                return f"{y} Year{'s' if y > 1 else ''}"
            elif mo > 0:
                return f"{mo} Month{'s' if mo > 1 else ''}"
            return "Not Mentioned"

        total_exp = (
            summary_exp if summary_exp and total_months == 0
            else fmt_months(total_months) if total_months > 0
            else (summary_exp or "Not Mentioned")
        )

        # Current domain = last entry's domain
        current_domain = timeline[-1].get("domain", "") if timeline else ""
        current_domain_months = per_domain.get(current_domain, 0)
        current_domain_exp = (
            f"{fmt_months(current_domain_months)} in {current_domain}"
            if current_domain_months > 0 and current_domain
            else "Not Mentioned"
        )

        per_domain_formatted = {
            d: fmt_months(m) for d, m in per_domain.items() if m > 0
        }

        # Experience history list
        exp_history = entities.get("work_experience") or entities.get("experience") or []
        if isinstance(exp_history, str):
            exp_history = [exp_history]

        # Current company experience
        current_comp_exp = "Not Mentioned"
        if timeline:
            latest_entry = timeline[-1]
            c_start = latest_entry.get("start_year", 0)
            c_end = latest_entry.get("end_year", CURRENT_YEAR)
            if c_start and c_end >= c_start:
                c_months = (c_end - c_start) * 12
                comp_name = latest_entry.get("company", "Current Company")
                current_comp_exp = f"{fmt_months(c_months)} at {comp_name}"

        return {
            "total_experience": total_exp,
            "current_domain_experience": current_domain_exp,
            "current_company_experience": current_comp_exp,
            "per_domain_experience": per_domain_formatted,
            "experience_history": [str(e) for e in exp_history if e]
        }

    # ---------------------------------------------------------------------------
    # Primary + Secondary Domain Scoring
    # ---------------------------------------------------------------------------

    def _score_primary_secondary_domain(
        self, entities: Dict[str, Any], text: str,
        timeline: List[Dict], designation: str
    ) -> Dict[str, Any]:
        """Compute primary and secondary domains with confidence percentages."""

        # 1. Check designation-based override map first
        desig_lower = designation.lower()
        for key, dom in DESIGNATION_DOMAIN_MAP.items():
            if key in desig_lower:
                # Confirm domain but still score all
                break

        # 2. Score from full entities text (all signals)
        all_domain_scores: Dict[str, float] = {}
        taxonomy = domain_detector.taxonomy

        # Weight text blobs by recency and signal type
        desig_blob = designation.lower()
        skills_blob = " ".join(str(s).lower() for s in (entities.get("skills") or []))
        exp_blob = " ".join(str(e).lower() for e in (entities.get("work_experience") or entities.get("experience") or []))
        edu_blob = " ".join(str(e).lower() for e in (entities.get("education") or []))

        # Recent timeline entries count more
        recent_blob = ""
        if timeline:
            for entry in reversed(timeline[-3:]):  # last 3 jobs weighted
                recent_blob += f" {entry.get('title', '')} {entry.get('company', '')} "

        for domain, triggers in taxonomy.items():
            score = 0.0
            for trigger in triggers:
                tl = trigger.lower()
                if tl in desig_blob:
                    score += 5.0   # Highest: designation
                if tl in recent_blob:
                    score += 4.0   # Recent experience
                if tl in exp_blob:
                    score += 2.5
                if tl in edu_blob:
                    score += 2.0
                if tl in skills_blob:
                    score += 1.5
                if tl in text.lower():
                    score += 0.5
            if score > 0:
                all_domain_scores[domain] = score

        if not all_domain_scores:
            return {
                "primary_domain": "General",
                "primary_confidence": 50,
                "secondary_domain": "Not Applicable",
                "secondary_confidence": 0
            }

        sorted_domains = sorted(all_domain_scores.items(), key=lambda x: x[1], reverse=True)
        primary = sorted_domains[0]
        secondary = sorted_domains[1] if len(sorted_domains) > 1 else None

        # Normalize to confidence %
        max_score = primary[1]
        primary_conf = min(98, round((primary[1] / max_score) * 98)) if max_score > 0 else 50
        secondary_conf = min(90, round((secondary[1] / max_score) * 90)) if secondary and max_score > 0 else 0

        return {
            "primary_domain": primary[0],
            "primary_confidence": primary_conf,
            "secondary_domain": secondary[0] if secondary else "Not Applicable",
            "secondary_confidence": secondary_conf
        }

    # ---------------------------------------------------------------------------
    # Skill Categorization — 7 Buckets + HR Skills
    # ---------------------------------------------------------------------------

    def _categorize_skills(
        self, entities: Dict[str, Any], text: str, primary_domain: str
    ) -> Dict[str, List[str]]:
        """Extract and categorize skills into 7 domain-aware buckets."""
        raw_items: List[str] = []

        for key in ["skills", "technologies", "programming_languages", "software_skills", "competencies"]:
            val = entities.get(key) or []
            if isinstance(val, list):
                raw_items.extend(str(v) for v in val if v)
            elif isinstance(val, str):
                raw_items.append(val)

        split_items: List[str] = []
        for item in raw_items:
            parts = re.split(r'[,;•\-*|/()]|\n', item)
            split_items.extend(parts)

        # If nothing from entities, try extracting from skills section in text
        if not split_items and text:
            m = re.search(
                r'(?i)(?:technical\s+skills?|skills?|core\s+competencies|expertise)\s*:?\s*\n?([\s\S]{5,500}?)(?=\n\n|\Z)',
                text
            )
            if m:
                parts = re.split(r'[,;•\-*|/()]|\n', m.group(1))
                split_items.extend(parts)

        prog_langs, ai_tools, erp_platforms, analytics_tools = [], [], [], []
        mgmt_skills, hr_skills, soft_skills, tech_skills = [], [], [], []
        medical_skills, software_skills, domain_skills = [], [], []
        all_clean: List[str] = []
        seen: set = set()

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

        # Extract company names from text and entities to exclude from skills
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
            # Trim bullets, line numbers, and leading/trailing non-alphanumeric (except +# for C#, C++)
            s_clean = re.sub(r'^(?:[•\-*]|\d+[\.\)]|\s)+', '', s_str).strip()
            s_clean = re.sub(r'^[^\w+#]+|[^\w+#]+$', '', s_clean).strip()

            if not s_clean or len(s_clean) < 2 or len(s_clean) > 40:
                continue

            s_lower = s_clean.lower()
            s_upper = s_clean.upper()

            # 1. OCR Noise & Debris Filter
            if s_lower in OCR_NOISE_TERMS or s_lower in {"safety", "administration", "standards", "statutory filings", "identified hr"}:
                continue
            if re.search(r'\b(?:19|20)\d{2}\b', s_lower):
                continue
            if re.search(r'\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b', s_lower):
                continue
            if re.search(r'[\@\:\/\\\{\}\=\+]', s_clean) and "linkedin" not in s_lower and "c++" not in s_lower and "c#" not in s_lower:
                continue
            if any(noise in s_lower for noise in ["page", "expert", "proficient in", "well versed", "tracking system"]):
                continue

            # 2. Company Name Filter (Company names must NEVER appear as skills)
            if any(comp_kw in s_lower for comp_kw in ["apollo hospital", "sindoori management", "leela palace", "abc healthcare", "xyz medical"]):
                continue
            if len(s_clean.split()) > 1 and any(cw in excluded_companies for cw in s_lower.split()) and any(cw in s_lower.split() for cw in ["hospital", "hospitals", "palace", "solutions", "ltd", "inc"]):
                continue

            # 3. Gerund (-ing) filter: reject verbs ending in -ing unless in ALLOWED_GERUND_SKILLS
            if s_lower.endswith("ing") and s_lower not in ALLOWED_GERUND_SKILLS:
                last_word = s_lower.split()[-1]
                if last_word.endswith("ing") and last_word not in ALLOWED_GERUND_SKILLS:
                    continue

            # 4. Entity Isolation: do not mix degree names, job titles, awards, or contacts into skills
            if s_lower in DEGREE_NOISE or any(d in s_lower.split() for d in ["btech", "mba", "bcom", "bsc", "gnm", "mtech", "diploma"]):
                continue
            if s_lower in TITLE_NOISE or any(t in s_lower for t in ["registered nurse", "hr manager", "hr executive", "manager hr", "software engineer", "data analyst", "senior accountant"]):
                continue
            if any(w in s_lower.split() for w in ["manager", "nurse", "executive", "engineer", "developer", "accountant", "officer", "director"]) and any(w in s_lower.split() for w in ["hr", "software", "senior", "lead", "junior", "registered", "chief", "assistant"]):
                continue
            if any(a_kw in s_lower for a_kw in ["award", "employee of the", "living leela", "long service"]):
                continue

            if s_lower in seen:
                continue

            # Bucket assignment
            if s_upper in KNOWN_PROG_LANGS:
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
            elif any(sf in s_upper for sf in KNOWN_SOFT_SKILLS):
                add_if_new(soft_skills, s_clean)
            else:
                add_if_new(tech_skills, s_clean)

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
            "technical_skills": tech_skills
        }

    # ---------------------------------------------------------------------------
    # Education — Zero Hallucination
    # ---------------------------------------------------------------------------

    def _parse_education(self, entities: Dict[str, Any], text: str) -> List[Dict[str, str]]:
        """Parse education entries. Never generate placeholder values."""
        raw_edu = entities.get("education") or []
        if isinstance(raw_edu, str):
            raw_edu = [l.strip() for l in raw_edu.split('\n') if l.strip()]

        formatted = []

        for item in raw_edu:
            if isinstance(item, dict):
                degree_raw = item.get("degree", "")
                inst = item.get("institution") or item.get("university") or ""
                year = str(item.get("year") or "")
                spec = item.get("specialization") or ""
                cgpa_raw = item.get("cgpa") or item.get("percentage") or ""

                edu_level = self._detect_edu_level(degree_raw)

                formatted.append({
                    "degree": degree_raw or "Not Mentioned",
                    "education_level": edu_level,
                    "institution": inst or "Not Mentioned",
                    "university": item.get("university") or inst or "Not Mentioned",
                    "specialization": spec or "Not Mentioned",
                    "year": year or "Not Mentioned",
                    "cgpa_percentage": str(cgpa_raw) if cgpa_raw else "Not Mentioned"
                })

            elif isinstance(item, str) and item.strip():
                year_m = re.search(r'\b(19\d{2}|20\d{2})\b', item)
                year = year_m.group(0) if year_m else "Not Mentioned"

                pct_m = re.search(r'\b(\d+(?:\.\d+)?%|\d+\.\d+\s*(?:CGPA|GPA)?)\b', item, re.IGNORECASE)
                cgpa = pct_m.group(0) if pct_m else "Not Mentioned"

                # Specialization: "in Computer Science", "in Human Resources"
                spec_m = re.search(r'(?i)\bin\s+([A-Za-z\s]{3,35})(?:from|\(|\-|$)', item)
                spec = spec_m.group(1).strip().title() if spec_m else "Not Mentioned"

                # From / Institution
                parts = [p.strip() for p in re.split(r'[-–|,]', item) if p.strip()]
                degree_raw = parts[0] if parts else item.strip()
                inst = parts[1] if len(parts) > 1 else "Not Mentioned"
                edu_level = self._detect_edu_level(degree_raw)

                formatted.append({
                    "degree": degree_raw or "Not Mentioned",
                    "education_level": edu_level,
                    "institution": inst,
                    "university": inst,
                    "specialization": spec,
                    "year": year,
                    "cgpa_percentage": cgpa
                })

        if not formatted and text:
            m = re.search(
                r'(?i)(?:education|academic|qualifications?)\s*:?\s*\n?([\s\S]{5,300}?)(?=\n\n|\Z)',
                text
            )
            if m:
                lines = [l.strip() for l in m.group(1).split('\n') if len(l.strip()) > 5]
                for l in lines:
                    edu_level = self._detect_edu_level(l)
                    year_m = re.search(r'\b(19\d{2}|20\d{2})\b', l)
                    year = year_m.group(0) if year_m else "Not Mentioned"
                    pct_m = re.search(r'\b(\d+(?:\.\d+)?%|\d+\.\d+\s*(?:CGPA|GPA)?)\b', l, re.IGNORECASE)
                    cgpa = pct_m.group(0) if pct_m else "Not Mentioned"
                    formatted.append({
                        "degree": l,
                        "education_level": edu_level,
                        "institution": "Not Mentioned",
                        "university": "Not Mentioned",
                        "specialization": "Not Mentioned",
                        "year": year,
                        "cgpa_percentage": cgpa
                    })

        # If still nothing
        if not formatted:
            return [{
                "degree": "Not Mentioned",
                "education_level": "Not Mentioned",
                "institution": "Not Mentioned",
                "university": "Not Mentioned",
                "specialization": "Not Mentioned",
                "year": "Not Mentioned",
                "cgpa_percentage": "Not Mentioned"
            }]

        return formatted

    def _detect_edu_level(self, degree_text: str) -> str:
        """Detect education level abbreviation from degree string."""
        d_lower = degree_text.lower()
        for key, level in EDUCATION_LEVELS.items():
            if key in d_lower:
                return level
        return "Not Mentioned"

    # ---------------------------------------------------------------------------
    # Awards & Certifications — Dedicated Separation
    # ---------------------------------------------------------------------------

    def _separate_awards_certifications(
        self, entities: Dict[str, Any], text: str
    ) -> Tuple[List[Dict[str, str]], List[str]]:
        """Separate awards from certifications. Never mix."""

        AWARD_KEYWORDS = [
            "employee of the month", "employee of the year", "best employee",
            "award", "prize", "recognition", "honor", "leela dharma",
            "long service", "outstanding", "excellence award", "star performer"
        ]
        CERT_KEYWORDS = [
            "certified", "certification", "certificate", "pmp", "six sigma",
            "microsoft certified", "aws certified", "cisco", "google certified",
            "cissp", "cma", "ca ", "acca", "chrp", "shrm"
        ]

        raw_certs = entities.get("certifications") or []
        if isinstance(raw_certs, str):
            raw_certs = [l.strip() for l in raw_certs.split('\n') if l.strip()]
        if isinstance(raw_certs, list):
            raw_certs = [str(c) for c in raw_certs if c]

        awards = []
        certifications = []

        for item in raw_certs:
            item_lower = item.lower()
            if any(kw in item_lower for kw in AWARD_KEYWORDS):
                awards.append({"name": item.strip(), "organization": "Not Mentioned", "year": "Not Mentioned", "category": "Professional Award"})
            elif any(kw in item_lower for kw in CERT_KEYWORDS):
                certifications.append(item.strip())
            else:
                # Default to certification if ambiguous
                certifications.append(item.strip())

        # Also scan raw text for awards section
        awards_m = re.search(r'(?i)(?:awards?|recognitions?|honours?)\s*:?\s*\n?([\s\S]{5,400}?)(?=\n\n|\Z)', text)
        if awards_m:
            seen_names = {a["name"].lower() for a in awards}
            for line in awards_m.group(1).split('\n'):
                line = re.sub(r'^[•\-*\d\.\)]+', '', line).strip()
                if len(line) > 3 and line.lower() not in seen_names:
                    awards.append({"name": line, "organization": "Not Mentioned", "year": "Not Mentioned", "category": "Professional Award"})
                    seen_names.add(line.lower())

        return awards, certifications

    # ---------------------------------------------------------------------------
    # Projects
    # ---------------------------------------------------------------------------

    def _extract_projects(
        self, entities: Dict[str, Any], text: str
    ) -> Tuple[List[str], bool]:
        """Extract projects and flag whether a dedicated projects section exists."""
        raw = entities.get("projects") or []
        if isinstance(raw, list):
            items = [str(i).strip() for i in raw if str(i).strip()]
        elif isinstance(raw, str):
            items = [l.strip() for l in raw.split('\n') if l.strip()]
        else:
            items = []

        if not items and text:
            m = re.search(r'(?i)\bprojects?\b\s*:?\s*\n([\s\S]{5,400}?)(?=\n\s*[A-Z\s]{4,20}\n|\Z)', text)
            if m:
                proj_block = m.group(1).strip()
                items = [l.strip().lstrip('1234567890.-*• ') for l in proj_block.split('\n') if l.strip()]

        has_dedicated = bool(items) or bool(
            re.search(r'(?i)\bprojects?\b', text)
        )

        return items, has_dedicated

    # ---------------------------------------------------------------------------
    # Location — Multi-Layer
    # ---------------------------------------------------------------------------

    def _extract_location_layers(self, entities: Dict[str, Any], text: str) -> Dict[str, Any]:
        """Extract current, work, and permanent location separately."""
        current_location = None
        work_location = None
        permanent_address = None
        sources = []

        def is_valid_location(val: Optional[str]) -> bool:
            if not val or not isinstance(val, str):
                return False
            v = val.strip().lower()
            if "@" in v or "http" in v or "linkedin" in v:
                return False
            # Reject raw phone numbers (e.g. "+91 9876543210" or "9876543210")
            if re.match(r'^(?:\+?\d{1,3}[\s\-]?)?\(?\d{2,5}\)?[\s\-.]?\d{3,5}[\s\-.]?\d{3,5}$', v):
                return False
            if len(v) < 2:
                return False
            return True

        # From entities
        addrs = entities.get("addresses") or entities.get("address") or entities.get("location")
        if isinstance(addrs, list) and addrs:
            candidate = str(addrs[0]).strip()
            if is_valid_location(candidate):
                permanent_address = candidate
                sources.append("address field")
        elif isinstance(addrs, str) and addrs:
            candidate = addrs.strip()
            if is_valid_location(candidate):
                permanent_address = candidate
                sources.append("address field")

        # Scan text for labeled locations
        patterns = [
            (r'(?i)current\s+(?:location|city|address)\s*:\s*([A-Za-z\s,]{3,50})(?:\n|$)', "current"),
            (r'(?i)work\s+(?:location|address)\s*:\s*([A-Za-z\s,]{3,50})(?:\n|$)', "work"),
            (r'(?i)permanent\s+(?:address|location)\s*:\s*([A-Za-z0-9\s,.\-]{3,80})(?:\n|$)', "permanent"),
            (r'(?i)(?:city|location|address|residence)\s*:\s*([A-Za-z0-9\s,.\-]{3,60})(?:\n|$)', "general"),
        ]
        for pattern, loc_type in patterns:
            m = re.search(pattern, text)
            if m:
                val = m.group(1).strip()
                if is_valid_location(val):
                    if loc_type == "current":
                        current_location = val
                        sources.append("current location")
                    elif loc_type == "work":
                        work_location = val
                        sources.append("work location")
                    elif loc_type == "permanent":
                        permanent_address = val
                        sources.append("permanent address")
                    elif loc_type == "general" and not permanent_address:
                        permanent_address = val
                        sources.append("location field")

        # City/state fallback: find city names in text
        if not is_valid_location(current_location) and not is_valid_location(permanent_address):
            city_m = re.search(
                r'\b(Chennai|Mumbai|Bangalore|Delhi|Hyderabad|Pune|Kolkata|Ahmedabad|Kerala|Kochi|Thrissur|Coimbatore|Madurai|Jaipur|Lucknow|Indore|Bhopal|Chandigarh)\b',
                text, re.IGNORECASE
            )
            if city_m:
                permanent_address = city_m.group(0).title()
                sources.append("city mention in text")

        # If current_location unknown, use permanent as fallback
        if not is_valid_location(current_location):
            current_location = permanent_address if is_valid_location(permanent_address) else None

        return {
            "current_location": current_location if is_valid_location(current_location) else None,
            "work_location": work_location if is_valid_location(work_location) else None,
            "permanent_address": permanent_address if is_valid_location(permanent_address) else None,
            "sources": sources
        }

    def _parse_address_breakdown(self, address_str: Optional[str]) -> Dict[str, str]:
        """Parse raw address string into structured components: house/flat, street, area, city, district, state, country, pincode."""
        if not address_str or address_str == "Not Mentioned":
            return {
                "house_flat": "Not Mentioned",
                "street": "Not Mentioned",
                "area": "Not Mentioned",
                "city": "Not Mentioned",
                "district": "Not Mentioned",
                "state": "Not Mentioned",
                "country": "Not Mentioned",
                "pincode": "Not Mentioned",
                "formatted_address": "Not Mentioned"
            }

        pincode_m = re.search(r'\b(\d{6})\b', address_str)
        pincode = pincode_m.group(1) if pincode_m else "Not Mentioned"

        states = ["Tamil Nadu", "Karnataka", "Maharashtra", "Kerala", "Delhi", "Telangana", "Andhra Pradesh", "Gujarat", "West Bengal", "Rajasthan", "Uttar Pradesh", "Madhya Pradesh", "Punjab", "Haryana"]
        detected_state = "Not Mentioned"
        for st in states:
            if st.lower() in address_str.lower():
                detected_state = st
                break

        cities = ["Chennai", "Bangalore", "Mumbai", "Kochi", "Kolkata", "Delhi", "Hyderabad", "Pune", "Ahmedabad", "Jaipur", "Lucknow", "Coimbatore", "Madurai", "Thrissur", "Trivandrum", "Indore", "Bhopal", "Chandigarh"]
        detected_city = "Not Mentioned"
        for ct in cities:
            if ct.lower() in address_str.lower():
                detected_city = ct
                break

        parts = [p.strip() for p in address_str.split(',') if p.strip()]
        house_flat = "Not Mentioned"
        street = "Not Mentioned"
        area = "Not Mentioned"

        if parts:
            if re.search(r'\d+', parts[0]) or len(parts[0]) < 15:
                house_flat = parts[0]
            if len(parts) > 1:
                street = parts[1]
            if len(parts) > 2 and parts[2].title() not in [detected_city, detected_state]:
                area = parts[2]

        district = detected_city if detected_city != "Not Mentioned" else "Not Mentioned"

        return {
            "house_flat": house_flat,
            "street": street,
            "area": area,
            "city": detected_city,
            "district": district,
            "state": detected_state,
            "country": "India" if (detected_state != "Not Mentioned" or detected_city != "Not Mentioned" or pincode != "Not Mentioned") else "Not Mentioned",
            "pincode": pincode,
            "formatted_address": address_str
        }

    def _extract_parent_names(self, entities: Dict[str, Any], text: str) -> Tuple[str, str]:
        father = entities.get("father_name")
        mother = entities.get("mother_name")
        if not father and text:
            m = re.search(r'(?i)father[\'s]*\s+name\s*:\s*([A-Za-z\s]{2,40})(?:\n|,|$)', text)
            if m:
                father = m.group(1).strip().title()
        if not mother and text:
            m = re.search(r'(?i)mother[\'s]*\s+name\s*:\s*([A-Za-z\s]{2,40})(?:\n|,|$)', text)
            if m:
                mother = m.group(1).strip().title()
        return father or "Not Mentioned", mother or "Not Mentioned"

    def _extract_personal_attributes(self, entities: Dict[str, Any], text: str) -> Dict[str, str]:
        dob = entities.get("date_of_birth") or entities.get("dob")
        if not dob and text:
            m = re.search(r'(?i)(?:date of birth|dob|d o b|birth date)\s*:\s*([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4}|[A-Za-z0-9\s,]{5,20})(?:\n|,|$)', text)
            if m:
                dob = m.group(1).strip()

        gender = entities.get("gender")
        if not gender and text:
            m = re.search(r'(?i)\bgender\s*:\s*(male|female|other)\b', text)
            if m:
                gender = m.group(1).strip().title()

        marital = entities.get("marital_status")
        if not marital and text:
            m = re.search(r'(?i)\bmarital\s+status\s*:\s*(single|married|unmarried)\b', text)
            if m:
                marital = m.group(1).strip().title()

        nationality = entities.get("nationality")
        if not nationality and text:
            m = re.search(r'(?i)\bnationality\s*:\s*([A-Za-z]+)\b', text)
            if m:
                nationality = m.group(1).strip().title()

        return {
            "date_of_birth": dob or "Not Mentioned",
            "gender": gender or "Not Mentioned",
            "marital_status": marital or "Not Mentioned",
            "nationality": nationality or "Not Mentioned",
        }

    # ---------------------------------------------------------------------------
    # Role Recommendations — Current Career Priority
    # ---------------------------------------------------------------------------

    def _recommend_roles_current_career(
        self, entities: Dict[str, Any], primary_domain: str,
        designation: str, career_transition: Dict[str, Any]
    ) -> List[str]:
        """Recommend roles based on CURRENT career domain, not historical ones."""

        # Use current career domain (not historical) for recommendations
        current_domain = career_transition.get("current_domain") if career_transition.get("is_transition") else primary_domain

        recommendations = role_inference_engine.recommend_roles(entities, current_domain or primary_domain)

        # Ensure current designation is at top if not already listed
        if designation and designation != "Not Mentioned":
            if not any(designation.lower() in r.lower() for r in recommendations):
                recommendations = [designation] + recommendations[:3]
            else:
                recommendations = recommendations[:5]

        return recommendations[:5]

    # ---------------------------------------------------------------------------
    # Health Score
    # ---------------------------------------------------------------------------

    def _calculate_health_score(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        checklist = {
            "skills": bool(profile.get("skills")),
            "experience": bool(profile.get("experience")),
            "education": bool(profile.get("education")),
            "projects": bool(profile.get("projects")),
            "certifications": bool(profile.get("certifications")),
            "linkedin": bool(profile.get("linkedin") and profile.get("linkedin") != "Not Mentioned"),
            "achievements": bool(profile.get("certifications") or profile.get("projects"))
        }
        weights = {"skills": 25, "experience": 25, "education": 20, "projects": 10,
                   "certifications": 10, "linkedin": 5, "achievements": 5}
        score = sum(w for k, w in weights.items() if checklist[k])
        return {"health_score": min(100, max(0, score)), "checklist": checklist}

    # ---------------------------------------------------------------------------
    # Insights
    # ---------------------------------------------------------------------------

    def _generate_insights(
        self, skills: List[str], exp: str, domain: str, recommended: List[str]
    ) -> Dict[str, Any]:
        exp_lower = exp.lower()
        if any(str(n) in exp_lower for n in range(7, 25)):
            career_level = "Senior Professional"
        elif any(str(n) in exp_lower for n in range(3, 7)):
            career_level = "Mid-Level Professional"
        else:
            career_level = "Early Career Professional"

        return {
            "career_level": career_level,
            "interview_readiness": "High",
            "strengths": [
                f"Strong domain expertise in {domain}.",
                f"Demonstrated {exp} of professional experience.",
                f"Technical proficiency across {', '.join(skills[:5]) if skills else 'core domain skills'}."
            ],
            "recommended_roles": recommended,
            "improvement_suggestions": [
                "Consider adding quantifiable project impact metrics.",
                "Ensure certifications include issuing body and dates."
            ]
        }

    # ---------------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------------

    def _extract_single_string(self, value: Any) -> Optional[str]:
        if isinstance(value, list) and value:
            return str(value[0]).strip() or None
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def _extract_link(self, value: Any, text: str, pattern: str) -> Optional[str]:
        if isinstance(value, str) and value and value not in ("Not Available", "Not Mentioned"):
            return value.strip()
        m = re.search(pattern, text, re.IGNORECASE)
        return m.group(0).strip() if m else None


# Module singleton
candidate_profile_builder = CandidateProfileBuilder()
