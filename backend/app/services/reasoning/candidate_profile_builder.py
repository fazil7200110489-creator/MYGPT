"""Candidate Profile Builder — Single Source of Truth for Resume Intelligence Engine.
"""

import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from loguru import logger

from backend.app.services.reasoning.domain_detector import domain_detector
from backend.app.services.reasoning.role_inference_engine import role_inference_engine
from backend.app.services.reasoning.analyzers.timeline_analyzer import TimelineAnalyzer
from backend.app.services.reasoning.analyzers.skill_analyzer import SkillAnalyzer
from backend.app.services.reasoning.analyzers.project_analyzer import ProjectAnalyzer
from backend.app.services.reasoning.analyzers.semantic_analyzer import SemanticAnalyzer

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CURRENT_YEAR = datetime.now().year

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
    "manager hr": "Human Resources (HR)",
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
    Orchestrates the specialized sub-analyzers.
    """

    def __init__(self):
        self.timeline_analyzer = TimelineAnalyzer()
        self.skill_analyzer = SkillAnalyzer()
        self.project_analyzer = ProjectAnalyzer()
        self.semantic_analyzer = SemanticAnalyzer()

    def build_profile(self, raw_entities: Dict[str, Any], raw_text: str = "") -> Dict[str, Any]:
        """Build a fully normalized, validated Candidate Profile."""
        entities = raw_entities or {}
        full_text = raw_text or ""
        if not full_text and isinstance(entities.get("raw_text"), str):
            full_text = entities["raw_text"]

        # 1. Basic Identity
        name = self._normalize_name(entities, full_text)
        designation = self._normalize_designation(entities, full_text)

        # 2. Specialized Analyzers Delegation (Timeline & Experience)
        timeline_data = self.timeline_analyzer.analyze(entities, full_text)
        timeline = timeline_data["timeline"]
        career_transition = timeline_data["career_transition"]
        experience_data = {
            "total_experience": timeline_data["total_experience"],
            "current_domain_experience": timeline_data["current_domain_experience"],
            "current_company_experience": timeline_data["current_company_experience"],
            "per_domain_experience": timeline_data["per_domain_experience"],
            "experience_history": timeline_data["experience_history"]
        }

        # 3. Domain Detection (with robust reverse designation match logic)
        domain_data = self._score_primary_secondary_domain(entities, full_text, timeline, designation)

        # 4. Skill Extraction & Modern Stack Normalization
        skills_data = self.skill_analyzer.analyze(entities, full_text, domain_data["primary_domain"])

        # 5. Zero-Hallucination Education Parsing
        education_list = self._parse_education(entities, full_text)

        # 6. Awards & Certifications isolation
        awards_list, certifications_list = self._separate_awards_certifications(entities, full_text)

        # 7. Projects Extraction & Complexity Analysis
        projects_data = self.project_analyzer.analyze(entities, full_text)
        projects_list = projects_data["projects"]
        has_dedicated_projects = projects_data["has_dedicated_projects"]
        detailed_projects = projects_data["detailed_projects"]

        # 8. Location & Address details
        location_data = self._extract_location_layers(entities, full_text)
        address_breakdown = self._parse_address_breakdown(location_data["permanent_address"] or location_data["current_location"])

        # 9. Contact Info & Parents
        email = self._extract_single_string(entities.get("email") or entities.get("emails"))
        phone = self._extract_single_string(entities.get("phone") or entities.get("phones"))

        if (not email or email == "Not Mentioned") and full_text:
            e_m = re.search(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', full_text)
            if e_m:
                email = e_m.group(0).strip().lower()

        if (not phone or phone == "Not Mentioned") and full_text:
            p_m = re.search(r'(?i)(?:\+?\d{1,3}[\s\-.])?[\(\[\{]?\d{2,5}[\)\]\}]?[\s\-.]?\d{3,5}[\s\-.]?\d{3,5}', full_text)
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

        # 10. Distinct Companies list
        extracted_companies = list(dict.fromkeys([
            entry["company"] for entry in timeline
            if entry.get("company") and entry["company"] not in ("Not Mentioned", "Company")
        ]))

        # 11. Profile Validation Flags
        validation_flags = {
            "has_experience": bool(experience_data["experience_history"] or experience_data["total_experience"] != "Not Mentioned"),
            "has_education": bool(education_list and education_list[0].get("degree") != "Not Mentioned"),
            "has_skills": bool(skills_data["all_skills"]),
            "has_location": bool(location_data["current_location"] or location_data["permanent_address"]),
            "has_awards": bool(awards_list),
            "has_timeline": bool(timeline),
            "has_certifications": bool(certifications_list)
        }

        # 12. Recommendations & Insights
        dynamic_roles = role_inference_engine.recommend_roles(entities, domain_data["primary_domain"])
        insights = self._generate_insights(
            skills_data["all_skills"],
            experience_data["total_experience"],
            domain_data["primary_domain"],
            dynamic_roles
        )

        # 13. Health Score
        health_res = self._calculate_health_score({
            "name": name,
            "skills": skills_data["all_skills"],
            "experience": experience_data["experience_history"],
            "education": education_list,
            "projects": projects_list,
            "certifications": certifications_list,
            "linkedin": linkedin
        })

        # Assemble temporary profile to run semantic analyzer
        temp_profile = {
            "skills": skills_data["all_skills"],
            "projects": projects_list,
            "certifications": certifications_list,
            "experience_history": experience_data["experience_history"]
        }
        semantic_data = self.semantic_analyzer.analyze(temp_profile, full_text)


        # Generate dynamic summary prose
        edu_text_str = ""
        if education_list and education_list[0].get("degree") != "Not Mentioned":
            edu_text_str = f" who holds a {education_list[0]['degree']}"
        display_desig = designation
        if not display_desig or display_desig == "Not Mentioned":
            display_desig = dynamic_roles[0] if dynamic_roles else "Professional"

        summary_prose = (
            f"{name} is a professional working as a {display_desig} with a focus on {domain_data['primary_domain']}. "
            f"Candidate has a total experience of {experience_data['total_experience']}{edu_text_str}."
        )
        insights["recruiter_summary"] = summary_prose

        # Insights & Summary
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
            "skills_data": skills_data,
            # Education (Factual)
            "education": education_list,
            # Awards & Certifications
            "awards": awards_list,
            "certifications": certifications_list,
            # Projects (Factual)
            "projects": projects_list,
            "detailed_projects": detailed_projects,
            "has_dedicated_projects": has_dedicated_projects,
            # Contact & Location (Factual)
            "location_sources": location_data["sources"],
            # Health & Validation
            "health_score": health_res["health_score"],
            "health_checklist": health_res["checklist"],
            "validation_flags": validation_flags,
            # Insights & Summary
            "summary": summary_prose,
            "recruiter_summary": summary_prose,
            "insights": insights,
            
            # Semantic attributes & Evidence Graph (added for intelligence capability improvement)
            "semantic_features": semantic_data["semantic_features"],
            "evidence_graph": semantic_data["evidence_graph"]
        }

    # ---------------------------------------------------------------------------
    # Identity & Personal parsing
    # ---------------------------------------------------------------------------

    def _normalize_name(self, entities: Dict[str, Any], text: str) -> str:
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

    def _score_primary_secondary_domain(
        self, entities: Dict[str, Any], text: str,
        timeline: List[Dict], designation: str
    ) -> Dict[str, Any]:
        """Compute primary and secondary domains with confidence percentages.
        Features reverse ordering support for designation override matching.
        """
        desig_lower = designation.lower()
        
        # Check designation-based override map first with reverse designation logic
        for key, dom in DESIGNATION_DOMAIN_MAP.items():
            key_words = re.findall(r"\b\w+\b", key)
            if len(key_words) > 1 and all(re.search(r'\b' + re.escape(w) + r'\b', desig_lower) for w in key_words):
                break
            elif key in desig_lower:
                break

        all_domain_scores: Dict[str, float] = {}
        taxonomy = domain_detector.taxonomy

        desig_blob = designation.lower()
        skills_blob = " ".join(str(s).lower() for s in (entities.get("skills") or []))
        exp_blob = " ".join(str(e).lower() for e in (entities.get("work_experience") or entities.get("experience") or []))
        edu_blob = " ".join(str(e).lower() for e in (entities.get("education") or []))

        recent_blob = ""
        if timeline:
            for entry in reversed(timeline[-3:]):
                recent_blob += f" {entry.get('title', '')} {entry.get('company', '')} "

        for domain, triggers in taxonomy.items():
            score = 0.0
            for trigger in triggers:
                tl = trigger.lower()
                
                # Check subset match for multi-word triggers to handle reverse ordering (e.g. "hr manager" vs "manager hr")
                trig_words = re.findall(r"\b\w+\b", tl)
                if len(trig_words) > 1 and all(re.search(r'\b' + re.escape(w) + r'\b', desig_blob) for w in trig_words):
                    score += 5.0
                elif tl in desig_blob:
                    score += 5.0

                if tl in recent_blob:
                    score += 4.0
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

        max_score = primary[1]
        primary_conf = min(98, round((primary[1] / max_score) * 98)) if max_score > 0 else 50
        secondary_conf = min(90, round((secondary[1] / max_score) * 90)) if secondary and max_score > 0 else 0

        return {
            "primary_domain": primary[0],
            "primary_confidence": primary_conf,
            "secondary_domain": secondary[0] if secondary else "Not Applicable",
            "secondary_confidence": secondary_conf
        }

    def _parse_education(self, entities: Dict[str, Any], text: str) -> List[Dict[str, str]]:
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

                spec_m = re.search(r'(?i)\bin\s+([A-Za-z\s]{3,35})(?:from|\(|\-|$)', item)
                spec = spec_m.group(1).strip().title() if spec_m else "Not Mentioned"

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
            edu_lines = []
            collecting = False
            
            edu_headers = ["education", "academic", "qualifications", "degree", "schooling", "qualification"]
            stop_headers = ["skills", "experience", "work", "employment", "projects", "certifications", "awards", "summary", "contact", "personal", "declaration", "hobbies", "languages", "interests", "activities", "strengths"]
            
            for line in text.split('\n'):
                line_strip = line.strip()
                if not line_strip:
                    continue
                line_lower = line_strip.lower()
                
                # Check for stop headers first
                if collecting:
                    if any(re.match(r'(?i)^\b' + re.escape(h) + r'\b\s*:', line_strip) for h in stop_headers):
                        collecting = False
                        break
                    if len(line_strip) < 30 and any(re.search(r'\b' + re.escape(h) + r'\b', line_lower) for h in stop_headers):
                        collecting = False
                        break
                        
                # Check for start header
                if not collecting:
                    inline_match = re.match(r'(?i)^\b(?:education|academic|qualifications?)\b\s*:\s*(.*)', line_strip)
                    if inline_match:
                        collecting = True
                        content = inline_match.group(1).strip()
                        if content:
                            edu_lines.append(content)
                        continue
                        
                    if len(line_strip) < 30 and any(re.search(r'\b' + re.escape(h) + r'\b', line_lower) for h in edu_headers):
                        collecting = True
                        continue
                
                if collecting:
                    # Ignore page numbers or very short noisy lines
                    if len(line_strip) > 3 and not re.match(r'^\bpage\b\s*\d+', line_strip, re.IGNORECASE):
                        edu_lines.append(line_strip)
                        
            # If we collected lines, parse them
            for l in edu_lines:
                edu_level = self._detect_edu_level(l)
                year_m = re.search(r'\b(19\d{2}|20\d{2})\b', l)
                year = year_m.group(0) if year_m else "Not Mentioned"
                pct_m = re.search(r'\b(\d+(?:\.\d+)?%|\d+\.\d+\s*(?:CGPA|GPA)?)\b', l, re.IGNORECASE)
                cgpa = pct_m.group(0) if pct_m else "Not Mentioned"
                
                # Extract degree and institution/university
                parts = re.split(r'\b(?:from|at)\b', l, flags=re.IGNORECASE)
                if len(parts) > 1:
                    degree_raw = parts[0].strip()
                    inst = parts[1].strip()
                else:
                    subparts = [p.strip() for p in re.split(r'[-–|]', l) if p.strip()]
                    degree_raw = subparts[0] if subparts else l
                    inst = subparts[1] if len(subparts) > 1 else "Not Mentioned"
                
                # Clean degree and institution
                degree_raw = re.sub(r'\b\d{4}\b', '', degree_raw)
                degree_raw = re.sub(r'\b(?:\d+(?:\.\d+)?%|\d+\.\d+\s*(?:CGPA|GPA)?)\b', '', degree_raw, flags=re.IGNORECASE)
                degree_raw = re.sub(r'^\s*[\d\s\-–:]+', '', degree_raw)
                degree_raw = re.sub(r'\s+', ' ', degree_raw).strip().strip(':-–,')
                
                inst = re.sub(r'\b\d{4}\b', '', inst)
                inst = re.sub(r'\b(?:\d+(?:\.\d+)?%|\d+\.\d+\s*(?:CGPA|GPA)?)\b', '', inst, flags=re.IGNORECASE)
                inst = re.sub(r'\s+', ' ', inst).strip().strip('():-–,')
                
                # Extract specialization
                spec_m = re.search(r'(?i)\bin\s+([A-Za-z\s&]{3,35})', degree_raw)
                spec = spec_m.group(1).strip().title() if spec_m else "Not Mentioned"
                
                if not degree_raw:
                    degree_raw = l
                
                formatted.append({
                    "degree": degree_raw,
                    "education_level": edu_level,
                    "institution": inst,
                    "university": inst,
                    "specialization": spec,
                    "year": year,
                    "cgpa_percentage": cgpa
                })

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
        d_lower = degree_text.lower()
        for key, level in EDUCATION_LEVELS.items():
            if key in d_lower:
                return level
        return "Not Mentioned"

    def _separate_awards_certifications(
        self, entities: Dict[str, Any], text: str
    ) -> Tuple[List[Dict[str, str]], List[str]]:
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
                certifications.append(item.strip())

        awards_m = re.search(r'(?i)(?:awards?|recognitions?|honours?)\s*:?\s*\n?([\s\S]{5,400}?)(?=\n\n|\Z)', text)
        if awards_m:
            seen_names = {a["name"].lower() for a in awards}
            for line in awards_m.group(1).split('\n'):
                line = re.sub(r'^[•\-*\d\.\)]+', '', line).strip()
                if len(line) > 3 and line.lower() not in seen_names:
                    awards.append({"name": line, "organization": "Not Mentioned", "year": "Not Mentioned", "category": "Professional Award"})
                    seen_names.add(line.lower())

        return awards, certifications

    def _extract_location_layers(self, entities: Dict[str, Any], text: str) -> Dict[str, Any]:
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
            if re.match(r'^(?:\+?\d{1,3}[\s\-]?)?\(?\d{2,5}\)?[\s\-.]?\d{3,5}[\s\-.]?\d{3,5}$', v):
                return False
            if len(v) < 2:
                return False
            return True

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

        if not is_valid_location(current_location) and not is_valid_location(permanent_address):
            city_m = re.search(
                r'\b(Chennai|Mumbai|Bangalore|Delhi|Hyderabad|Pune|Kolkata|Ahmedabad|Kerala|Kochi|Thrissur|Coimbatore|Madurai|Jaipur|Lucknow|Indore|Bhopal|Chandigarh)\b',
                text, re.IGNORECASE
            )
            if city_m:
                permanent_address = city_m.group(0).title()
                sources.append("city mention in text")

        if not is_valid_location(current_location):
            current_location = permanent_address if is_valid_location(permanent_address) else None

        return {
            "current_location": current_location if is_valid_location(current_location) else None,
            "work_location": work_location if is_valid_location(work_location) else None,
            "permanent_address": permanent_address if is_valid_location(permanent_address) else None,
            "sources": sources
        }

    def _parse_address_breakdown(self, address_str: Optional[str]) -> Dict[str, str]:
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
            # Replaced [A-Za-z\s] with [A-Za-z \t] to ignore newline matches and avoid grabbing next line names
            m = re.search(r'(?i)mother[\'s]*\s+name\s*:\s*([A-Za-z \t]{2,40})(?:\n|,|$)', text)
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
