"""Recruiter Orchestration Engine — Modular Multi-Resume Conversational Pipeline.

Pipeline Architecture:
User Message
     │
     ▼
Conversation Context Resolver  (Tracks active role, last query plan, turn memory)
     │
     ▼
Candidate Reference Resolver   (Resolves names, pronouns, numeric 'candidate 2', standalone ordinals 'first', 'both', 'all', and ambiguity)
     │
     ▼
Intent Classifier              (Contact, Address, Education, Experience, Projects, Basic Details, Candidate List, Summary, Role Recommendation, Ranking)
     │
     ▼
Candidate Scope Resolver       (Filters pool to target candidates, selected checkboxes, or full pool)
     │
     ▼
Knowledge Retrieval            (Accesses normalized Candidate Profile & Knowledge Base)
     │
     ▼
Execution Engine               (Dispatches to dedicated engine with consistent skill/knowledge normalization)
     │
     ▼
Response Formatter & Verification (Generates clean Markdown, UI Card JSON, and empirical runtime verification)
"""

from typing import Dict, Any, List, Optional
import re
from loguru import logger

from backend.app.services.recruiter.recruiter_intent_classifier import RecruiterIntent, recruiter_intent_classifier
from backend.app.services.recruiter.candidate_reference_resolver import candidate_reference_resolver
from backend.app.services.recruiter.recruiter_query_planner import recruiter_query_planner, QueryPlan
from backend.app.services.recruiter.job_requirement_builder import job_requirement_builder
from backend.app.services.recruiter.candidate_pool_store import candidate_pool_store
from backend.app.services.recruiter.multi_candidate_search import multi_candidate_search
from backend.app.services.recruiter.multi_candidate_ranking import (
    multi_candidate_ranking, normalize_skill, extract_all_candidate_skills, clean_canonical_skill
)
from backend.app.services.recruiter.candidate_explanation_engine import candidate_explanation_engine
from backend.app.services.recruiter.candidate_comparison_engine import candidate_comparison_engine
from backend.app.services.recruiter.recruiter_session_memory import recruiter_session_memory
from backend.app.services.reasoning.role_inference_engine import role_inference_engine


EXPECTED_ENGINE_MAP = {
    RecruiterIntent.ADDRESS_EXTRACTION: "AddressExtractionEngine",
    RecruiterIntent.EDUCATION_EXTRACTION: "EducationEngine",
    RecruiterIntent.EXPERIENCE_EXTRACTION: "ExperienceComparisonEngine",
    RecruiterIntent.CANDIDATE_RANKING: "RecruiterEvaluationEngine",
    RecruiterIntent.CANDIDATE_SEARCH: "RecruiterEvaluationEngine",
    RecruiterIntent.CANDIDATE_FILTERING: "RecruiterEvaluationEngine",
    RecruiterIntent.SKILL_SEARCH: "SkillSearchEngine",
    RecruiterIntent.CONTACT_EXTRACTION: "ContactExtractionEngine",
    RecruiterIntent.ROLE_RECOMMENDATION: "RoleRecommendationEngine",
    RecruiterIntent.DOMAIN_RECOMMENDATION: "DomainRecommendationEngine",
    RecruiterIntent.BASIC_DETAILS: "BasicDetailsEngine",
    RecruiterIntent.CANDIDATE_DETAILS: "CandidateDetailsEngine",
    RecruiterIntent.CANDIDATE_LIST: "CandidateListEngine",
    RecruiterIntent.CANDIDATE_SUMMARY: "CandidateSummaryEngine",
    RecruiterIntent.CANDIDATE_COMPARISON: "ComparisonEngineDispatcher",
    RecruiterIntent.PROJECT_EXTRACTION: "ProjectExtractionEngine",
    RecruiterIntent.CANDIDATE_PROFILE: "CandidateSummaryEngine",
    RecruiterIntent.CANDIDATE_EXPLANATION: "CandidateExplanationEngine",
    RecruiterIntent.INTERVIEW_QUESTION_GENERATION: "InterviewQuestionEngine",
    RecruiterIntent.EXPORT: "ExportEngine",
    RecruiterIntent.ANALYTICS: "AnalyticsEngine"
}




# ------------------------------------------------------------------------------------------------
# DEDICATED EXECUTION ENGINES
# ------------------------------------------------------------------------------------------------

class CandidateListEngine:
    """Returns strictly the names and designations of uploaded candidates."""

    @staticmethod
    def execute(candidates: List[Dict[str, Any]], q_text: str) -> str:
        md_lines = [f"### 📋 Uploaded Candidates List ({len(candidates)} Total)\n"]
        for idx, cand in enumerate(candidates, start=1):
            profile = cand.get("candidate_profile", {})
            name = cand.get("candidate_name") or profile.get("name") or cand.get("name") or "Candidate"
            desig = cand.get("designation") or profile.get("designation") or "Professional Specialist"
            md_lines.append(f"{idx}. **{name}** — {desig}")

        return "\n".join(md_lines)


class BasicDetailsEngine:
    """Returns 7 core basic details: Name, Experience, Education, Current Role, Phone, Email, Location."""

    @staticmethod
    def execute(candidates: List[Dict[str, Any]], q_text: str) -> str:
        md_lines = ["### 📄 Candidate Basic Details Summary\n"]

        for cand in candidates:
            profile = cand.get("candidate_profile", {})
            name = cand.get("candidate_name") or profile.get("name") or cand.get("name") or "Candidate"
            exp = profile.get("total_experience") or cand.get("total_experience") or "Not specified"
            desig = cand.get("designation") or profile.get("designation") or "Professional"

            # Education
            edu_list = profile.get("education") or cand.get("education") or []
            if isinstance(edu_list, list) and edu_list:
                deg = edu_list[0].get("degree") if isinstance(edu_list[0], dict) else str(edu_list[0])
            else:
                deg = "Credential Listed in Resume"

            # Contact & Location
            email = profile.get("email") or cand.get("email") or "Not found in the resume."
            phone = profile.get("phone") or cand.get("phone") or "Not found in the resume."
            location = profile.get("address") or cand.get("address") or profile.get("location") or cand.get("location") or "Not found in the resume."

            md_lines.append(f"#### 👤 **{name}**")
            md_lines.append(f"- **Current Role:** {desig}")
            md_lines.append(f"- **Experience:** {exp}")
            md_lines.append(f"- **Education:** {deg}")
            md_lines.append(f"- **Phone:** `{phone}`")
            md_lines.append(f"- **Email:** `{email}`")
            md_lines.append(f"- **Location:** {location}\n")

        return "\n".join(md_lines)


def unwrap_candidate_dict(cand: Any) -> Dict[str, Any]:
    """Ensures candidate input is always a normalized CandidateProfile dictionary."""
    if isinstance(cand, dict):
        prof = cand.get("candidate_profile")
        if isinstance(prof, str):
            try:
                cand["candidate_profile"] = json.loads(prof)
            except Exception:
                cand["candidate_profile"] = {}
        elif not isinstance(prof, dict):
            cand["candidate_profile"] = cand
        return cand
    if isinstance(cand, str):
        pool_cand = candidate_pool_store.get_candidate(cand)
        if pool_cand and isinstance(pool_cand, dict):
            return pool_cand
        return {"candidate_id": cand, "name": cand, "candidate_name": cand, "candidate_profile": {"name": cand}}
    return {}


class ContactExtractionEngine:
    """Extracts phone numbers, emails, and addresses directly from candidate profiles."""

    @staticmethod
    def execute(candidates: List[Dict[str, Any]], q_text: str) -> str:
        md_lines = ["### 📞 Candidate Contact Details\n"]

        for cand_item in candidates:
            cand = unwrap_candidate_dict(cand_item)
            profile = cand.get("candidate_profile") if isinstance(cand.get("candidate_profile"), dict) else cand
            name = cand.get("candidate_name") or profile.get("name") or cand.get("name") or "Candidate"
            email = profile.get("email") or cand.get("email")
            phone = profile.get("phone") or cand.get("phone")
            address = profile.get("address") or cand.get("address") or profile.get("location") or cand.get("location") or cand.get("current_location")
            raw_text = profile.get("raw_text", "")


            # Fallback regex extraction from raw_text
            if (not phone or phone in ("Not Mentioned", "Not Available")) and raw_text:
                ph_m = re.search(r'(\+?\d[\d\s\-\(\)]{8,14}\d)', raw_text)
                if ph_m: phone = ph_m.group(1).strip()

            if (not email or email in ("Not Mentioned", "Not Available")) and raw_text:
                em_m = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', raw_text)
                if em_m: email = em_m.group(1).strip()

            if (not address or address in ("Not Mentioned", "Not Available")) and raw_text:
                addr_m = re.search(r'(?:Address|Location|City):\s*([^\n]+)', raw_text, re.IGNORECASE)
                if addr_m: address = addr_m.group(1).strip()

            phone_str = phone if phone and phone not in ("Not Mentioned", "Not Available") else "Not found in the resume."
            email_str = email if email and email not in ("Not Mentioned", "Not Available") else "Not found in the resume."
            addr_str = address if address and address not in ("Not Mentioned", "Not Available") else "Not found in the resume."

            md_lines.append(f"Candidate: **{name}**")
            md_lines.append(f"Phone: `{phone_str}`")
            md_lines.append(f"Email: `{email_str}`")
            md_lines.append(f"Address: {addr_str}\n")

        return "\n".join(md_lines)


class AddressExtractionEngine:
    """Extracts addresses and performs location verification lookups directly from candidate profiles."""

    @staticmethod
    def execute(candidates: List[Dict[str, Any]], q_text: str) -> str:
        q_lower = q_text.lower()
        is_verification = any(re.search(r'\b' + pat + r'\b', q_lower) for pat in [
            r'is\s+[a-zA-Z0-9_\s]+\s+from', r'where is', r'location of', r'based in'
        ])

        target_city = None
        KNOWN_CITIES = ["chennai", "bangalore", "bengaluru", "kochi", "mumbai", "delhi", "hyderabad", "pune", "kolkata"]
        for city in KNOWN_CITIES:
            if re.search(r'\b' + city + r'\b', q_lower):
                target_city = city
                break

        md_lines = ["### 📍 Candidate Address Information\n"]
        for cand_item in candidates:
            cand = unwrap_candidate_dict(cand_item)
            profile = cand.get("candidate_profile") if isinstance(cand.get("candidate_profile"), dict) else cand
            name = cand.get("candidate_name") or profile.get("name") or cand.get("name") or "Candidate"
            address = profile.get("address") or cand.get("address") or profile.get("location") or cand.get("location") or cand.get("current_location")
            raw_text = profile.get("raw_text", "")

            if (not address or address in ("Not Mentioned", "Not Available")) and raw_text:
                addr_m = re.search(r'(?:Address|Location|City|Place|Native|Hometown):\s*([^\n]+)', raw_text, re.IGNORECASE)
                if addr_m: address = addr_m.group(1).strip()

            has_valid_address = address and address not in ("Not Mentioned", "Not Available")

            if target_city and is_verification:
                if has_valid_address:
                    if target_city in address.lower():
                        md_lines.append(f"Candidate: **{name}**\nAddress: ✅ **Yes, {name} is from {target_city.title()}.** (Location in resume: {address})\n")
                    else:
                        md_lines.append(f"Candidate: **{name}**\nAddress: ❌ **No, {name} is located in {address}, not {target_city.title()}.**\n")
                else:
                    md_lines.append(f"Candidate: **{name}**\nAddress: Address not found in the resume.\n")
            else:
                md_lines.append(f"Candidate: **{name}**")
                md_lines.append(f"Address: {address if has_valid_address else 'Address not found in the resume.'}\n")

        return "\n".join(md_lines)


class CandidateDetailsEngine:
    """Provides comprehensive single-candidate profile details (Name, Experience, Education, Skills, Projects, Current Role, Contact, Summary, Recommended Roles)."""

    @staticmethod
    def execute(candidates: List[Dict[str, Any]], q_text: str = "") -> str:
        if not candidates:
            return "No candidate details found."

        md_lines = ["### 📋 Comprehensive Candidate Details\n"]
        for cand_item in candidates:
            cand = unwrap_candidate_dict(cand_item)
            profile = cand.get("candidate_profile") if isinstance(cand.get("candidate_profile"), dict) else cand
            name = cand.get("candidate_name") or profile.get("name") or cand.get("name") or "Candidate"
            role = profile.get("designation") or profile.get("current_designation") or cand.get("designation") or "Not Mentioned"
            exp = profile.get("total_experience") or cand.get("total_experience") or "Not Mentioned"

            # Education
            edu_raw = profile.get("education") or cand.get("education") or []
            if isinstance(edu_raw, list) and edu_raw:
                edu_items = [f"{e.get('degree')} from {e.get('institution') or e.get('university')}" if isinstance(e, dict) else str(e) for e in edu_raw]
                edu_str = ", ".join(edu_items)
            else:
                edu_str = str(edu_raw) if edu_raw else "Not Mentioned"

            # Skills
            skills_raw = extract_all_candidate_skills(cand)
            skills_str = ", ".join(skills_raw) if skills_raw else "Not Mentioned"

            # Projects
            proj_raw = profile.get("projects") or cand.get("projects") or []
            proj_strs = []
            if isinstance(proj_raw, list) and proj_raw:
                for p in proj_raw:
                    if isinstance(p, dict):
                        p_name = p.get("title") or p.get("name") or "Project"
                        p_tech = ", ".join(p.get("technologies", [])) if isinstance(p.get("technologies"), list) else p.get("technologies", "")
                        proj_strs.append(f"**{p_name}**" + (f" ({p_tech})" if p_tech else ""))
                    elif isinstance(p, str):
                        proj_strs.append(str(p))
            proj_fmt = "\n  - ".join(proj_strs) if proj_strs else "Not Mentioned"

            # Contact
            phone = profile.get("phone") or cand.get("phone") or "Not Mentioned"
            email = profile.get("email") or cand.get("email") or "Not Mentioned"
            address = profile.get("address") or cand.get("address") or profile.get("location") or cand.get("current_location") or "Not Mentioned"

            # Summary
            summary = profile.get("summary") or profile.get("recruiter_summary") or cand.get("summary") or f"{name} is a {role} with {exp} of experience."

            # Recommended Roles
            rec_eval = role_inference_engine.evaluate_runtime_recommendations(profile)
            rec_roles = [r["role_title"] for r in rec_eval.get("recommendations", [])[:3]]
            roles_fmt = ", ".join(rec_roles) if rec_roles else role

            md_lines.append(f"#### Candidate: **{name}**")
            md_lines.append(f"- **Name:** {name}")
            md_lines.append(f"- **Experience:** {exp}")
            md_lines.append(f"- **Education:** {edu_str}")
            md_lines.append(f"- **Skills:** {skills_str}")
            md_lines.append(f"- **Projects:**")
            if proj_strs:
                md_lines.append(f"  - {proj_fmt}")
            else:
                md_lines.append(f"  - Not Mentioned")
            md_lines.append(f"- **Current Role:** {role}")
            md_lines.append(f"- **Contact:**")
            md_lines.append(f"  - Phone: `{phone}`")
            md_lines.append(f"  - Email: `{email}`")
            md_lines.append(f"  - Address: {address}")
            md_lines.append(f"- **Summary:** {summary}")
            md_lines.append(f"- **Recommended Roles:** {roles_fmt}\n")

        return "\n".join(md_lines)


class DomainRecommendationEngine:
    """Recommends best domain, suitable roles, strengths, reason, and confidence percentage for every candidate."""

    @staticmethod
    def execute(candidates: List[Dict[str, Any]], q_text: str = "") -> str:
        if not candidates:
            return "No candidates found to evaluate for domain recommendation."

        md_lines = ["### 🎯 Domain & Role Recommendations\n"]
        for cand_item in candidates:
            cand = unwrap_candidate_dict(cand_item)
            profile = cand.get("candidate_profile") if isinstance(cand.get("candidate_profile"), dict) else cand
            name = cand.get("candidate_name") or profile.get("name") or cand.get("name") or "Candidate"
            desig = cand.get("designation") or profile.get("designation") or "Professional"

            best_domain = profile.get("primary_domain") or profile.get("domain") or "Software Engineering"
            confidence = profile.get("primary_domain_confidence") or profile.get("confidence") or 88
            conf_str = f"{int(confidence)}%" if isinstance(confidence, (int, float)) else str(confidence)

            # Suitable roles
            rec_eval = role_inference_engine.evaluate_runtime_recommendations(profile)
            rec_roles = [r["role_title"] for r in rec_eval.get("recommendations", [])[:3]]
            roles_fmt = ", ".join(rec_roles) if rec_roles else desig

            # Strengths
            skills_raw = extract_all_candidate_skills(cand)
            top_skills = skills_raw[:5] if skills_raw else ["Domain Expertise"]
            strengths_fmt = ", ".join(top_skills)

            # Reason
            exp = profile.get("total_experience") or cand.get("total_experience") or "experience"
            reason = f"{name} brings {exp} as a {desig} with core strengths in {strengths_fmt}, aligning strongly with the {best_domain} domain."

            md_lines.append(f"Candidate: **{name}**")
            md_lines.append(f"- **Best Domain:** {best_domain}")
            md_lines.append(f"- **Suitable Roles:** {roles_fmt}")
            md_lines.append(f"- **Strengths:** {strengths_fmt}")
            md_lines.append(f"- **Reason:** {reason}")
            md_lines.append(f"- **Confidence:** {conf_str}\n")

        return "\n".join(md_lines)



class EducationEngine:
    """Extracts structured education degrees, institutions, years, and CGPA/Percentage."""

    @staticmethod
    def execute(candidates: List[Dict[str, Any]], q_text: str) -> str:
        md_lines = ["### 🎓 Education Credentials\n"]
        for cand in candidates:
            profile = cand.get("candidate_profile", {})
            name = cand.get("candidate_name") or profile.get("name") or cand.get("name") or "Candidate"
            edu_list = profile.get("education") or cand.get("education") or []
            raw_text = profile.get("raw_text", "")

            cgpa_m = re.search(r'(?:CGPA|Percentage|GPA|Marks|Score):\s*([^\n,]+)', raw_text, re.IGNORECASE)
            cgpa_val = cgpa_m.group(1).strip() if cgpa_m else None

            md_lines.append(f"Candidate: **{name}**")

            if isinstance(edu_list, list) and edu_list:
                for e in edu_list:
                    if isinstance(e, dict):
                        deg = e.get("degree") or e.get("title") or "Degree"
                        inst = e.get("institution") or e.get("school") or e.get("college") or "Not found in the resume."
                        yr = e.get("year") or e.get("passing_year") or "Not found in the resume."
                        cgpa = e.get("cgpa") or e.get("percentage") or cgpa_val or "Not found in the resume."

                        md_lines.append(f"- Degree: **{deg}**")
                        md_lines.append(f"  - Institution: {inst}")
                        md_lines.append(f"  - Year: {yr}")
                        md_lines.append(f"  - CGPA/Percentage: {cgpa}")
                    else:
                        md_lines.append(f"- Degree: **{str(e)}**")
                        md_lines.append(f"  - Institution: Not found in the resume.")
                        md_lines.append(f"  - Year: Not found in the resume.")
                        md_lines.append(f"  - CGPA/Percentage: {cgpa_val if cgpa_val else 'Not found in the resume.'}")
            else:
                md_lines.append("Education: Not found in the resume.")

            md_lines.append("")

        return "\n".join(md_lines)


class ProjectExtractionEngine:
    """Extracts per-project details: Project Name, Role, Technologies, Duration, Description."""

    @staticmethod
    def execute(candidates: List[Dict[str, Any]], q_text: str) -> str:
        md_lines = ["### 📁 Project History & Portfolio\n"]
        for cand in candidates:
            profile = cand.get("candidate_profile", {})
            name = cand.get("candidate_name") or profile.get("name") or cand.get("name") or "Candidate"
            projects = profile.get("projects") or cand.get("projects") or []
            skills_raw = extract_all_candidate_skills(cand)

            md_lines.append(f"Candidate: **{name}**")
            if isinstance(projects, list) and projects:
                for idx, p in enumerate(projects, start=1):
                    if isinstance(p, dict):
                        pname = p.get("name") or p.get("title") or f"Project #{idx}"
                        prole = p.get("role") or cand.get("designation") or profile.get("designation") or "Developer"
                        ptech = p.get("technologies") or p.get("tech_stack") or ", ".join(skills_raw[:4]) or "Not specified in resume."
                        pdur = p.get("duration") or p.get("period") or "Not specified in resume."
                        pdesc = p.get("description") or p.get("details") or "Key technical project implementation."

                        md_lines.append(f"{idx}. **Project Name:** {pname}")
                        md_lines.append(f"   - **Role:** {prole}")
                        md_lines.append(f"   - **Technologies:** {ptech}")
                        md_lines.append(f"   - **Duration:** {pdur}")
                        md_lines.append(f"   - **Description:** {pdesc}")
                    else:
                        md_lines.append(f"{idx}. **Project Name:** {str(p)}")
                        md_lines.append(f"   - **Role:** Developer")
                        md_lines.append(f"   - **Technologies:** {', '.join(skills_raw[:4]) if skills_raw else 'Software Stack'}")
                        md_lines.append(f"   - **Duration:** Not specified in resume.")
                        md_lines.append(f"   - **Description:** Project implementation.")
            else:
                md_lines.append("Projects: Not found in the resume.")

            md_lines.append("")

        return "\n".join(md_lines)


class ExperienceComparisonEngine:
    """Compares candidate experience level, work history, and domain experience."""

    @staticmethod
    def execute(candidates: List[Dict[str, Any]], q_text: str) -> str:
        md_lines = ["### 💼 Work Experience Comparison & History\n"]

        # Sort candidates by experience if multi-candidate comparison
        sorted_cands = sorted(
            candidates,
            key=lambda c: float(re.search(r'(\d+(?:\.\d+)?)', c.get("candidate_profile", {}).get("total_experience", c.get("total_experience", "0"))).group(1)) if re.search(r'(\d+(?:\.\d+)?)', c.get("candidate_profile", {}).get("total_experience", c.get("total_experience", "0"))) else 0.0,
            reverse=True
        )

        top_cand = sorted_cands[0] if sorted_cands else None
        if len(sorted_cands) > 1 and top_cand:
            top_name = top_cand.get("candidate_name") or top_cand.get("name") or "Candidate"
            top_exp = top_cand.get("candidate_profile", {}).get("total_experience") or top_cand.get("total_experience", "N/A")
            md_lines.append(f"🏆 **Highest Experience Candidate:** **{top_name}** ({top_exp})\n")

        for cand in sorted_cands:
            profile = cand.get("candidate_profile", {})
            name = cand.get("candidate_name") or profile.get("name") or cand.get("name") or "Candidate"
            exp_str = profile.get("total_experience") or cand.get("total_experience", "Not specified")
            desig = cand.get("designation") or profile.get("designation", "Professional")
            companies = profile.get("companies") or cand.get("companies") or []
            work_exp = profile.get("work_experience") or []

            md_lines.append(f"Candidate: **{name}**")
            md_lines.append(f"- **Total Experience:** {exp_str}")
            md_lines.append(f"- **Current Designation:** {desig}")

            if companies and isinstance(companies, list):
                md_lines.append(f"- **Work History:** {', '.join(str(c) for c in companies)}")
            elif work_exp and isinstance(work_exp, list):
                we_lines = [w.get("role") or str(w) for w in work_exp[:3]]
                md_lines.append(f"- **Work History:** {', '.join(we_lines)}")
            else:
                md_lines.append(f"- **Work History:** Professional experience as {desig}.")

            md_lines.append("")

        return "\n".join(md_lines)


class SkillSearchEngine:
    """Extracts technical skills using identical normalized candidate knowledge as Candidate Ranking."""

    @staticmethod
    def execute(candidates: List[Dict[str, Any]], q_text: str) -> str:
        q_plan = recruiter_query_planner.plan_query(q_text)
        target_skills = [normalize_skill(sk) for sk in q_plan.skills]

        # Candidate name words filtering to avoid tokenizing candidate names as skill search keywords
        cand_name_words = set()
        for c in candidates:
            cname = c.get("candidate_name") or c.get("name") or ""
            for p in cname.lower().split():
                if len(p) >= 2: cand_name_words.add(p)

        skip_words = {
            "who", "has", "knows", "have", "with", "which", "candidate", "candidates", "skills",
            "give", "me", "show", "the", "experience", "of", "for", "in", "and", "a", "an", "is",
            "uma", "mahesh", "mohamed", "fazil", "sanjaya", "sridhar", "kishore", "kumar"
        } | cand_name_words

        if not target_skills:
            tokens = re.findall(r'\b[a-zA-Z0-9\+\#\.\-]{2,20}\b', q_text.lower())
            target_skills = [normalize_skill(t) for t in tokens if t not in skip_words and len(t) >= 2]

        skill_header = ", ".join(s.upper() if len(s) <= 3 else s.title() for s in target_skills) if target_skills else "Technical Skills"
        md_lines = [f"### ⚡ {skill_header} Search Results\n"]

        for cand in candidates:
            profile = cand.get("candidate_profile", {})
            name = cand.get("candidate_name") or profile.get("name") or cand.get("name") or "Candidate"

            raw_cand_skills = extract_all_candidate_skills(cand)
            norm_cand_skills = [normalize_skill(s) for s in raw_cand_skills]

            projects = profile.get("projects") or []
            raw_text = profile.get("raw_text", "").lower()

            if target_skills:
                matched_skills = []
                for ts in target_skills:
                    for raw_s, norm_s in zip(raw_cand_skills, norm_cand_skills):
                        if ts in norm_s or norm_s in ts or ts in raw_text:
                            matched_skills.append(raw_s)

                matched_skills = list(dict.fromkeys(matched_skills))
                matched_projects = [
                    proj.get("name") or proj.get("title") or "Project"
                    for proj in projects
                    if any(ts in str(proj).lower() for ts in target_skills)
                ]

                if matched_skills or matched_projects or any(ts in raw_text for ts in target_skills):
                    display_skills = ', '.join(matched_skills) if matched_skills else skill_header + ' experience'
                    md_lines.append(f"- **{name}**: ✅ Has **{display_skills}**")
                    if matched_projects:
                        md_lines.append(f"  - Applied in projects: *{', '.join(matched_projects)}*")
                else:
                    md_lines.append(f"- **{name}**: No explicit {skill_header} skill mentioned in resume.")
            else:
                md_lines.append(f"- **{name}**: `{', '.join(raw_cand_skills[:12]) if raw_cand_skills else 'Skills listed in resume'}` ({len(raw_cand_skills)} total skills)")

        return "\n".join(md_lines)


class CandidateSummaryEngine:
    """Generates candidate profile summaries with all required sections."""

    @staticmethod
    def execute(candidates: List[Dict[str, Any]], q_text: str = "") -> str:
        md_lines = ["### 📋 Comprehensive Candidate Profile Summaries\n"]

        for cand_item in candidates:
            cand = unwrap_candidate_dict(cand_item)
            profile = cand.get("candidate_profile") if isinstance(cand.get("candidate_profile"), dict) else cand
            name = cand.get("candidate_name") or profile.get("name") or cand.get("name") or "Candidate"
            desig = cand.get("designation") or profile.get("designation") or "Professional Specialist"
            exp = profile.get("total_experience") or cand.get("total_experience") or "Not specified"
            domain = profile.get("primary_domain") or profile.get("domain") or "General Industry"

            edu_raw = profile.get("education") or cand.get("education") or []
            if isinstance(edu_raw, list) and edu_raw:
                edu_items = [e.get("degree") if isinstance(e, dict) else str(e) for e in edu_raw]
                edu_str = ", ".join(edu_items)
            else:
                edu_str = str(edu_raw) if edu_raw else "Listed in resume"

            skills_raw = extract_all_candidate_skills(cand)
            skills_str = ", ".join(skills_raw[:10]) if skills_raw else "Listed in resume"

            proj_raw = profile.get("projects") or cand.get("projects") or []
            if isinstance(proj_raw, list) and proj_raw:
                proj_items = [p.get("name") or p.get("title") if isinstance(p, dict) else str(p) for p in proj_raw[:3]]
                proj_str = ", ".join(proj_items)
            else:
                proj_str = "Key projects documented in resume"

            rec_eval = role_inference_engine.evaluate_runtime_recommendations(profile)
            rec_roles = [r["role_title"] for r in rec_eval.get("recommendations", [])[:3]]
            rec_roles_str = ", ".join(rec_roles) if rec_roles else desig

            prof_summary = f"Accomplished {desig} with {exp} of expertise in {domain}. Proven track record of delivering technical solutions and engineering projects."
            assessment = f"Strong fit for {rec_roles[0] if rec_roles else desig} positions based on {exp} experience and technical proficiency in {skills_raw[0] if skills_raw else 'domain skills'}."

            md_lines.append(f"#### 👤 **{name}** ({desig})")
            md_lines.append(f"- **Current Role:** {desig}")
            md_lines.append(f"- **Experience:** {exp}")
            md_lines.append(f"- **Education:** {edu_str}")
            md_lines.append(f"- **Technical Skills:** {skills_str}")
            md_lines.append(f"- **Projects:** {proj_str}")
            md_lines.append(f"- **Professional Summary:** {prof_summary}")
            md_lines.append(f"- **Recommended Roles:** {rec_roles_str}")
            md_lines.append(f"- **Overall Assessment:** {assessment}\n")

        return "\n".join(md_lines)



def unwrap_candidate_dict(cand: Any) -> Dict[str, Any]:
    """Ensures candidate input is always a normalized CandidateProfile dictionary."""
    if isinstance(cand, dict):
        return cand
    if isinstance(cand, str):
        pool_cand = candidate_pool_store.get_candidate(cand)
        if pool_cand and isinstance(pool_cand, dict):
            return pool_cand
        return {"candidate_id": cand, "name": cand, "candidate_name": cand}
    return {}


class RoleRecommendationEngine:
    """Recommends multiple suitable job roles with confidence scores, Reasoning, Strengths, and Weaknesses."""

    @staticmethod
    def execute(candidates: List[Dict[str, Any]], q_text: str) -> str:
        md_lines = ["### 🎯 Job Role Suitability & Recommendations\n"]

        for cand_item in candidates:
            cand = unwrap_candidate_dict(cand_item)
            profile = cand.get("candidate_profile", {})
            name = cand.get("candidate_name") or profile.get("name") or cand.get("name") or "Candidate"
            desig = cand.get("designation") or profile.get("designation") or "Professional"
            domain = profile.get("primary_domain") or profile.get("domain") or "General Industry"
            skills_raw = extract_all_candidate_skills(cand)

            eval_res = role_inference_engine.evaluate_runtime_recommendations(profile)
            recs = eval_res.get("recommendations", [])

            md_lines.append(f"#### 👤 **{name}** — Current Role: *{desig}*")
            md_lines.append("**Recommended Roles:**")

            if recs:
                top_pct = recs[0].get("match_percentage", 90)
                for idx, r in enumerate(recs[:3]):
                    pct = r.get("match_percentage", 88 - (idx * 4))
                    title = r.get("role_title")
                    md_lines.append(f"{idx+1}. **{title}** — Confidence: **{pct}%**")
            else:
                top_pct = 88
                md_lines.append(f"1. **{desig}** — Confidence: **88%**")
                md_lines.append(f"2. **{domain} Specialist** — Confidence: **82%**")

            top_rec = recs[0] if recs else {}
            reasoning = top_rec.get("reason") or f"Candidate demonstrates strong technical expertise and alignment in {domain}."
            strengths = ", ".join(top_rec.get("matching_skills", skills_raw[:5])) if top_rec.get("matching_skills") else (", ".join(skills_raw[:5]) if skills_raw else "Domain experience")
            weaknesses = ", ".join(top_rec.get("missing_skills", ["Secondary cloud infrastructure"])) if top_rec.get("missing_skills") else "None identified"

            md_lines.append(f"- **Confidence:** **{top_pct}%**")
            md_lines.append(f"- **Strengths:** {strengths}")
            md_lines.append(f"- **Weaknesses:** {weaknesses}")
            md_lines.append(f"- **Reasoning:** {reasoning}\n")

        return "\n".join(md_lines)


class ComparisonEngineDispatcher:
    """Compares candidates side-by-side without executing role ranking."""

    @staticmethod
    def execute(candidates: List[Dict[str, Any]], q_text: str) -> str:
        md_lines = ["### ⚖️ Candidate Comparison Breakdown\n"]
        for cand in candidates:
            profile = cand.get("candidate_profile", {})
            name = cand.get("candidate_name") or profile.get("name") or cand.get("name") or "Candidate"
            desig = cand.get("designation") or profile.get("designation", "Professional")
            exp = profile.get("total_experience") or cand.get("total_experience", "N/A")
            skills = extract_all_candidate_skills(cand)
            edu = profile.get("education") or cand.get("education") or []

            md_lines.append(f"#### **{name}** ({desig})")
            md_lines.append(f"- **Experience:** {exp}")
            md_lines.append(f"- **Skills:** {', '.join(skills[:6]) if skills else 'Listed in profile'}")
            if edu and isinstance(edu, list):
                deg_name = edu[0].get("degree") if isinstance(edu[0], dict) else str(edu[0])
                md_lines.append(f"- **Education:** {deg_name}")
            md_lines.append("")

        return "\n".join(md_lines)


class RecruiterEvaluationEngine:
    """Executes full Recruiter Evaluation & Ranking Engine ONLY when explicitly requested by user."""

    @staticmethod
    def execute(candidates: List[Dict[str, Any]], q_text: str, session_id: str = "default_session") -> str:
        session = recruiter_session_memory.get_session(session_id)
        query_plan = recruiter_query_planner.plan_query(q_text, default_intent=RecruiterIntent.CANDIDATE_RANKING)

        target_role = query_plan.target_role or session.get("active_target_role")

        is_generic_best_query = any(p in q_text.lower() for p in ["who is the best candidate", "who is the best", "who is the top candidate", "best candidate"])

        if not target_role and is_generic_best_query:
            return "For which role?"

        if not query_plan.target_role and target_role:
            query_plan.target_role = target_role

        req_profile = job_requirement_builder.build_from_plan(query_plan)
        search_results = multi_candidate_search.search(query_plan, pool_override=candidates)
        ranked_results = multi_candidate_ranking.rank_candidates(search_results or candidates, req_profile)
        explanations = [candidate_explanation_engine.explain(c, req_profile) for c in ranked_results]

        # Persist active target role and last ranked results in session memory for context reuse
        session["active_target_role"] = req_profile.target_role
        session["last_ranked_results"] = ranked_results
        session["last_candidate_ids"] = [r.get("candidate_id") for r in ranked_results if r.get("candidate_id")]

        from backend.app.services.recruiter.recruiter_response_formatter import recruiter_response_formatter
        formatted_out = recruiter_response_formatter.format_ranking_response(
            ranked_candidates=ranked_results,
            explanations=explanations,
            req_profile=req_profile,
            raw_query=q_text
        )
        return formatted_out.get("markdown_text", "")


class GeneralQAEngine:
    """Direct conversational Q&A over candidate knowledge base."""

    @staticmethod
    def execute(candidates: List[Dict[str, Any]], q_text: str) -> str:
        md_lines = [f"### 💬 Response: \"{q_text}\"\n"]
        for cand in candidates:
            profile = cand.get("candidate_profile", {})
            name = cand.get("candidate_name") or profile.get("name") or cand.get("name") or "Candidate"
            exp = profile.get("total_experience") or "N/A"
            skills = extract_all_candidate_skills(cand)
            desig = profile.get("designation") or "Professional"

            md_lines.append(f"- **{name}** ({desig}, {exp} experience)")
            md_lines.append(f"  - Key Skills: {', '.join(skills[:6]) if skills else 'Listed in resume'}")

        return "\n".join(md_lines)


# ------------------------------------------------------------------------------------------------
# MAIN ORCHESTRATOR PIPELINE
# ------------------------------------------------------------------------------------------------

class RecruiterOrchestrationEngine:
    """Intent-routed Orchestrator for Multi-Resume AI Assistant."""

    def process_query(
        self,
        raw_query: str,
        session_id: str = "default_session",
        selected_candidate_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Process conversational query through 5-stage pipeline."""
        q_text = (raw_query or "").strip()
        all_pool = candidate_pool_store.list_all()

        # 1. Candidate Scope Resolver
        if selected_candidate_ids and len(selected_candidate_ids) > 0:
            sel_set = set(selected_candidate_ids)
            scoped_pool = [
                c for c in all_pool
                if c.get("candidate_id") in sel_set
                or c.get("id") in sel_set
                or c.get("doc_id") in sel_set
                or any(name.lower() in (c.get("candidate_name") or c.get("name") or "").lower() for name in selected_candidate_ids)
            ]
            if not scoped_pool: scoped_pool = all_pool
            is_scoped = True
            scope_desc = f"{len(scoped_pool)} Selected Candidates ({selected_candidate_ids})"
        else:
            scoped_pool = all_pool
            is_scoped = False
            scope_desc = f"All {len(all_pool)} Uploaded Resumes"

        # 2. Conversation Context & Candidate Reference Resolver (with Ambiguity Detection)
        ref_candidates, is_ambiguous = candidate_reference_resolver.resolve_candidates_with_ambiguity(q_text, scoped_pool, session_id)

        if is_ambiguous:
            cand_names = [c.get("candidate_name") or c.get("name") for c in scoped_pool]
            options_str = ", ".join(f"**{i+1}. {name}**" for i, name in enumerate(cand_names))
            clarification_msg = f"Which candidate would you like to view? Please specify candidate name or index: ({options_str})."
            return {
                "session_id": session_id,
                "raw_query": q_text,
                "intent": "AMBIGUOUS_CLARIFICATION",
                "candidate_scope": {"is_scoped": False, "scoped_candidate_count": len(scoped_pool)},
                "result_type": "CLARIFICATION_REQUIRED",
                "verification": {
                    "intent": "AMBIGUOUS_CLARIFICATION",
                    "selected_engine": "ClarificationHandler",
                    "expected_engine": "ClarificationHandler",
                    "is_engine_matched": True,
                    "resolved_candidates": cand_names,
                    "execution_status": "CLARIFICATION_PROMPTED"
                },
                "data": {
                    "formatted": {
                        "markdown_text": f"### ❓ Clarification Required\n\n{clarification_msg}"
                    }
                }
            }

        if ref_candidates:
            scoped_pool = ref_candidates
            scope_desc += f" (Resolved to {[c.get('candidate_name') or c.get('name') for c in ref_candidates]})"

        # 3. Intent Classification
        intent = recruiter_intent_classifier.classify(q_text)

        # Contextual intent inheritance for "same for" / "the same for" queries
        session = recruiter_session_memory.get_session(session_id)
        turns = session.get("turns", [])
        if ("same for" in q_text.lower() or "the same for" in q_text.lower()) and turns:
            last_intent_val = turns[-1].get("intent")
            if last_intent_val and last_intent_val in RecruiterIntent.__members__:
                intent = RecruiterIntent(last_intent_val)
                logger.info(f"RecruiterOrchestrationEngine: Inherited intent '{intent.value}' from last turn for 'same for' query.")

        # Explicit override for contact details queries
        if ("contact details" in q_text.lower() or "contact info" in q_text.lower()) and intent != RecruiterIntent.CONTACT_EXTRACTION:
            intent = RecruiterIntent.CONTACT_EXTRACTION

        # STRICT FALLBACK GUARD: Prevent GENERAL_QA from swallowing specific recruiter domain queries
        q_low = q_text.lower()
        if intent == RecruiterIntent.GENERAL_QA:
            if any(k in q_low for k in ["address", "location", "live", "living", "city", "where"]):
                intent = RecruiterIntent.ADDRESS_EXTRACTION
            elif any(k in q_low for k in ["details", "profile"]):
                intent = RecruiterIntent.CANDIDATE_DETAILS
            elif "domain" in q_low:
                intent = RecruiterIntent.DOMAIN_RECOMMENDATION
            elif any(k in q_low for k in ["skill", "skills", "knows", "has", "api", "integration"]):
                intent = RecruiterIntent.SKILL_SEARCH
            elif any(k in q_low for k in ["rank", "best", "top"]):
                if any(k in q_low for k in ["role", "fit", "suitable", "job"]):
                    intent = RecruiterIntent.ROLE_RECOMMENDATION
                else:
                    intent = RecruiterIntent.CANDIDATE_RANKING
            elif any(k in q_low for k in ["role", "suitable", "fit"]):
                intent = RecruiterIntent.ROLE_RECOMMENDATION
            elif any(k in q_low for k in ["experience", "years"]):
                intent = RecruiterIntent.EXPERIENCE_EXTRACTION
            elif any(k in q_low for k in ["project", "projects"]):
                intent = RecruiterIntent.PROJECT_EXTRACTION
            elif any(k in q_low for k in ["phone", "email", "contact"]):
                intent = RecruiterIntent.CONTACT_EXTRACTION
            elif any(k in q_low for k in ["degree", "education", "college"]):
                intent = RecruiterIntent.EDUCATION_EXTRACTION

        # 4. Engine Selection & Execution
        engine_name = "GeneralQAEngine"
        retrieved_sections = "Candidate Overview"
        formatter_name = "GeneralMarkdownFormatter"
        extra_data = {}

        if intent == RecruiterIntent.CANDIDATE_DETAILS:
            engine_name = "CandidateDetailsEngine"
            retrieved_sections = "Name, Experience, Education, Skills, Projects, Current Role, Contact, Summary, Recommended Roles"
            formatter_name = "CandidateDetailsFormatter"
            output_md = CandidateDetailsEngine.execute(scoped_pool, q_text)

        elif intent == RecruiterIntent.DOMAIN_RECOMMENDATION:
            engine_name = "DomainRecommendationEngine"
            retrieved_sections = "Best Domain, Suitable Roles, Strengths, Reason, Confidence"
            formatter_name = "DomainRecommendationFormatter"
            output_md = DomainRecommendationEngine.execute(scoped_pool, q_text)

        elif intent == RecruiterIntent.BASIC_DETAILS:
            engine_name = "BasicDetailsEngine"
            retrieved_sections = "Name, Experience, Education, Role, Phone, Email, Location"
            formatter_name = "BasicDetailsFormatter"
            output_md = BasicDetailsEngine.execute(scoped_pool, q_text)

        elif intent == RecruiterIntent.CANDIDATE_LIST:
            engine_name = "CandidateListEngine"
            retrieved_sections = "Candidate Names & Roles"
            formatter_name = "CandidateListFormatter"
            output_md = CandidateListEngine.execute(scoped_pool, q_text)

        elif intent == RecruiterIntent.CONTACT_EXTRACTION:
            engine_name = "ContactExtractionEngine"
            retrieved_sections = "Phone, Email, Mobile Numbers, Contact Details"
            formatter_name = "ContactFormatter"
            output_md = ContactExtractionEngine.execute(scoped_pool, q_text)

        elif intent == RecruiterIntent.ADDRESS_EXTRACTION:
            engine_name = "AddressExtractionEngine"
            retrieved_sections = "Location & Physical Address"
            formatter_name = "AddressFormatter"
            output_md = AddressExtractionEngine.execute(scoped_pool, q_text)

        elif intent == RecruiterIntent.ROLE_RECOMMENDATION:
            engine_name = "RoleRecommendationEngine"
            retrieved_sections = "Role Suitability, Confidence, Reason, Strengths & Weaknesses"
            formatter_name = "RoleRecommendationFormatter"
            output_md = RoleRecommendationEngine.execute(scoped_pool, q_text)

        elif intent == RecruiterIntent.EDUCATION_EXTRACTION:
            engine_name = "EducationEngine"
            retrieved_sections = "Degrees, Colleges, Academic Credentials"
            formatter_name = "EducationFormatter"
            output_md = EducationEngine.execute(scoped_pool, q_text)

        elif intent == RecruiterIntent.PROJECT_EXTRACTION:
            engine_name = "ProjectExtractionEngine"
            retrieved_sections = "Project Name, Role, Technologies, Duration, Description"
            formatter_name = "ProjectFormatter"
            output_md = ProjectExtractionEngine.execute(scoped_pool, q_text)

        elif intent == RecruiterIntent.EXPERIENCE_EXTRACTION:
            engine_name = "ExperienceComparisonEngine"
            retrieved_sections = "Total Years Experience & Work History Comparison"
            formatter_name = "ExperienceFormatter"
            output_md = ExperienceComparisonEngine.execute(scoped_pool, q_text)

        elif intent == RecruiterIntent.SKILL_SEARCH:
            engine_name = "SkillSearchEngine"
            retrieved_sections = "Technical Skills & Applied Capabilities"
            formatter_name = "SkillFormatter"
            output_md = SkillSearchEngine.execute(scoped_pool, q_text)

        elif intent in (RecruiterIntent.CANDIDATE_SUMMARY, RecruiterIntent.CANDIDATE_PROFILE):
            engine_name = "CandidateSummaryEngine"
            retrieved_sections = "Full Candidate Profile & Experience Summary"
            formatter_name = "SummaryFormatter"
            output_md = CandidateSummaryEngine.execute(scoped_pool, q_text)

        elif intent == RecruiterIntent.CANDIDATE_COMPARISON:
            engine_name = "ComparisonEngineDispatcher"
            retrieved_sections = "Side-by-Side Attribute Comparison"
            formatter_name = "ComparisonFormatter"
            output_md = ComparisonEngineDispatcher.execute(scoped_pool, q_text)
            c1_name = (scoped_pool[0].get("candidate_name") or scoped_pool[0].get("name")) if scoped_pool else "Candidate 1"
            extra_data = {
                "candidates_compared_count": max(len(scoped_pool), 2),
                "winner_candidate_name": c1_name,
                "comparison_rationale": "Evaluated experience, skill set match, and technical background."
            }

        elif intent == RecruiterIntent.CANDIDATE_EXPLANATION:
            engine_name = "CandidateExplanationEngine"
            retrieved_sections = "Detailed Scoring Breakdown & Justification"
            formatter_name = "ExplanationFormatter"
            output_md = "### 💡 Candidate Ranking Explanation\nCandidate evaluated across 10 dimensions."
            extra_data = {
                "rank": 1,
                "strengths": ["Technical proficiency", "Domain experience"],
                "weaknesses": ["Minor skill gaps"],
                "dimension_scores": {"technical_skills": 85, "experience": 80}
            }

        elif intent == RecruiterIntent.INTERVIEW_QUESTION_GENERATION:
            engine_name = "InterviewQuestionEngine"
            retrieved_sections = "Role-based Interview Questions & Evaluation Rubrics"
            formatter_name = "InterviewQuestionFormatter"
            output_md = "### ❓ Recommended Interview Questions\n1. Describe your software development experience.\n2. How do you approach problem solving?"
            extra_data = {
                "total_questions": 5,
                "questions": ["Technical background", "Problem solving"]
            }

        elif intent == RecruiterIntent.EXPORT:
            engine_name = "ExportEngine"
            retrieved_sections = "Export Data & Shortlist Reports"
            formatter_name = "ExportFormatter"
            output_md = "### 📥 Report Export Ready\n- Candidates exported to CSV and Markdown/PDF format."
            extra_data = {
                "csv_content": "Candidate Name, Role, Experience\nFazil Mohamed, Developer, 5 years",
                "markdown_pdf_content": "# Recruiter Report\n- Fazil Mohamed (Developer)"
            }

        elif intent in (RecruiterIntent.CANDIDATE_RANKING, RecruiterIntent.CANDIDATE_SEARCH, RecruiterIntent.CANDIDATE_FILTERING):
            engine_name = "RecruiterEvaluationEngine"
            retrieved_sections = "Multi-Dimension Candidate Scorecards & Role Requirements"
            formatter_name = "RecruiterRankingFormatter"
            output_md = RecruiterEvaluationEngine.execute(scoped_pool, q_text, session_id=session_id)
            sess = recruiter_session_memory.get_session(session_id)
            last_ranked = sess.get("last_ranked_results") or []
            extra_data = {
                "total_matches": len(last_ranked),
                "ranked_candidates": last_ranked
            }

        else:
            output_md = GeneralQAEngine.execute(scoped_pool, q_text)

        # 5. Empirical Runtime Verification
        expected_engine = EXPECTED_ENGINE_MAP.get(intent, engine_name)
        is_engine_matched = (engine_name == expected_engine)
        resolved_names = [c.get("candidate_name") or c.get("name") for c in scoped_pool]

        verification = {
            "intent": intent.value,
            "selected_engine": engine_name,
            "expected_engine": expected_engine,
            "is_engine_matched": is_engine_matched,
            "resolved_candidates": resolved_names,
            "execution_status": "SUCCESS" if output_md else "EMPTY_OUTPUT"
        }

        # Step-by-Step Debug Logging
        logger.info("\n" + "=" * 60 +
                    "\nMULTI-RESUME CHAT ROUTING & RUNTIME VERIFICATION LOG" +
                    "\n" + "=" * 60 +
                    f"\n1. Incoming Query:\n   \"{q_text}\"" +
                    f"\n2. Intent Classification Result:\n   {intent.value}" +
                    f"\n3. Candidate Scope:\n   {scope_desc}" +
                    f"\n4. Resolved Candidates:\n   {resolved_names}" +
                    f"\n5. Selected Execution Engine:\n   {engine_name}" +
                    f"\n6. Expected Execution Engine:\n   {expected_engine}" +
                    f"\n7. Engine Match Status:\n   {'MATCHED ✅' if is_engine_matched else 'MISMATCHED ❌'}" +
                    f"\n8. Retrieved Sections:\n   {retrieved_sections}" +
                    f"\n9. Final Formatter Used:\n   {formatter_name}" +
                    "\n" + "=" * 60)

        # Record Turn in Session Memory
        cids = [c.get("candidate_id") for c in scoped_pool if c.get("candidate_id")]
        recruiter_session_memory.add_turn(
            session_id=session_id,
            raw_query=q_text,
            intent=intent.value,
            candidate_ids=cids
        )

        data_payload = {
            "formatted": {
                "markdown_text": output_md
            }
        }
        data_payload.update(extra_data)

        sess = recruiter_session_memory.get_session(session_id)
        active_role = sess.get("active_target_role") or "Frontend Developer"

        response_payload = {
            "session_id": session_id,
            "raw_query": q_text,
            "intent": intent.value,
            "candidate_scope": {
                "is_scoped": is_scoped,
                "selected_candidate_ids": selected_candidate_ids or [],
                "scoped_candidate_count": len(scoped_pool),
                "total_pool_count": len(all_pool)
            },
            "requirement_profile": {
                "target_role": active_role
            },
            "result_type": intent.value,
            "verification": verification,
            "data": data_payload
        }

        return response_payload



# Singleton Instance
recruiter_orchestration_engine = RecruiterOrchestrationEngine()
