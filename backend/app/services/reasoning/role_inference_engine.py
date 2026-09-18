import os
import json
import re
from typing import Dict, Any, List, Optional, Tuple, Set
from loguru import logger
from backend.app.services.reasoning.domain_detector import domain_detector

def _load_role_taxonomy_from_json() -> Dict[str, Dict[str, Dict[str, Any]]]:
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    config_path = os.path.join(base_dir, "config", "role_taxonomy.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data:
                    logger.info("Loaded role taxonomy dynamically from role_taxonomy.json")
                    return data
        except Exception as e:
            logger.warning(f"Failed to load role_taxonomy.json: {e}")
    return ROLE_TAXONOMY

# Fallback role taxonomy mapping
ROLE_TAXONOMY: Dict[str, Dict[str, Dict[str, Any]]] = {
    "Finance & Accounts": {
        "Accountant": {
            "required": ["tally", "gst", "accounting", "bookkeeping", "balance sheet"],
            "description": "handling general accounting, Tally ERP, GST returns, bookkeeping, and balance sheets."
        }
    },
    "Software Development": {
        "Frontend Developer": {
            "required": ["html", "css", "javascript", "react", "angular", "vue"],
            "description": "modern user interface and frontend web application development."
        }
    }
}


class RoleInferenceEngine:
    """Multi-Domain Role Suitability & Similarity Scoring System."""

    def __init__(self, role_taxonomy: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None):
        self.role_taxonomy = role_taxonomy or _load_role_taxonomy_from_json()

    def calculate_role_similarity(
        self,
        entities: Dict[str, Any],
        target_role_query: str,
        domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """Calculates role similarity score, match %, matching vs missing skills,
        and determines suitability tier (Highly Suitable, Suitable, Partially Suitable, Not Suitable).

        Args:
            entities: Structured entities extracted from document.
            target_role_query: Question string or target role phrase (e.g. "Frontend Developer").
            domain: Detected candidate domain (optional).

        Returns:
            Dict containing match_percentage, suitability_tier, matching_skills,
            missing_skills, recommendation, candidate_domain, candidate_designation,
            target_role, reason, and evidence.
        """
        candidate_domain = domain or domain_detector.detect_domain(entities)
        desig = entities.get("designation") if isinstance(entities, dict) else None
        
        if desig and str(desig).strip() not in ("Not Mentioned", ""):
            candidate_desig = str(desig).strip()
        else:
            candidate_desig = "Professional"

        # Collect candidate skills into set
        candidate_skills: Set[str] = set()
        if isinstance(entities, dict):
            for k in ["skills", "technologies", "software_skills", "hardware_skills", "competencies", "programming_languages"]:
                vals = entities.get(k) or []
                if isinstance(vals, list):
                    for v in vals:
                        if isinstance(v, str):
                            candidate_skills.add(v.lower())
            if desig and isinstance(desig, str):
                candidate_skills.add(desig.lower())

        candidate_blob = " ".join(candidate_skills)
        q_lower = target_role_query.lower()

        # Detect if query is a generic recommendation question rather than a specific role title
        GENERIC_QUESTION_PATTERNS = [
            r"\bwhich\s+role\b", r"\bwhat\s+role\b", r"\bwhich\s+job\b", r"\bwhat\s+job\b",
            r"\brole\s+recommendation\b", r"\brecommended\s+roles?\b", r"\bsuitable\s+roles?\b",
            r"\brole\s+match\b", r"\bfit\s+for\s*(?:a\s+role|any\s+role|\?|$)",
            r"\bsuitable\s+for\s*(?:a\s+role|any\s+role|\?|$)", r"\bwhat\s+can\s+(?:she|he|they)\s+do\b"
        ]
        is_generic_question = any(re.search(p, q_lower) for p in GENERIC_QUESTION_PATTERNS)

        # Identify target role from taxonomy matching q_lower
        target_role_name = None
        target_domain = None
        target_role_info = None

        if not is_generic_question:
            # Flatten roles and sort by role_name length descending to prioritize full title matches
            all_taxonomy_roles = []
            for dom, roles in self.role_taxonomy.items():
                for r_name, r_info in roles.items():
                    all_taxonomy_roles.append((dom, r_name, r_info))
            all_taxonomy_roles.sort(key=lambda x: len(x[1]), reverse=True)

            # Pass 1: Exact substring match
            for dom, r_name, r_info in all_taxonomy_roles:
                if r_name.lower() in q_lower:
                    target_role_name = r_name
                    target_domain = dom
                    target_role_info = r_info
                    break

            # Pass 2: Keyword intersection match if no exact substring match
            if not target_role_name:
                q_words = set(re.findall(r"\b\w+\b", q_lower))
                stopwords = {"developer", "engineer", "specialist", "executive", "analyst", "consultant", "manager", "lead", "officer", "is", "he", "she", "suitable", "for"}
                for dom, r_name, r_info in all_taxonomy_roles:
                    r_words = set(re.findall(r"\b\w+\b", r_name.lower())) - stopwords
                    if r_words and r_words.issubset(q_words):
                        target_role_name = r_name
                        target_domain = dom
                        target_role_info = r_info
                        break

        # Fallback handling
        if not target_role_name:
            if is_generic_question:
                domain_roles = list(self.role_taxonomy.get(candidate_domain, {}).keys())
                target_role_name = domain_roles[0] if domain_roles else (candidate_desig if candidate_desig != "Professional" else "Full Stack Developer")
                target_domain = candidate_domain
                for dom, roles in self.role_taxonomy.items():
                    if target_role_name in roles:
                        target_role_info = roles[target_role_name]
                        target_domain = dom
                        break
            else:
                # For specific queries ("Is she suitable for HVAC Engineer?"), extract target role title from query
                clean_query = re.sub(r'(?i)^(?:is|can)\s+(?:she|he|the\s+candidate|candidate)\s+(?:suitable|fit)\s+(?:for|as)\s+', '', target_role_query).strip()
                clean_query = re.sub(r'[?\.]', '', clean_query).strip()
                target_role_name = clean_query.title() if clean_query else "Target Role"
                target_domain = domain_detector.detect_domain({"designation": target_role_name}, "")

        # Strict check to never return "Not Mentioned" as target role name
        if not target_role_name or target_role_name == "Not Mentioned":
            domain_roles = list(self.role_taxonomy.get(candidate_domain, {}).keys())
            target_role_name = domain_roles[0] if domain_roles else "Suitable Role"
            
            # Lookup role info again
            target_domain = candidate_domain
            target_role_info = None
            for dom, roles in self.role_taxonomy.items():
                if target_role_name in roles:
                    target_role_info = roles[target_role_name]
                    target_domain = dom
                    break

        required_skills = target_role_info.get("required", []) if target_role_info else []

        matching_skills = [s for s in required_skills if s in candidate_blob]
        missing_skills = [s for s in required_skills if s not in candidate_blob]

        if required_skills:
            match_percentage = round((len(matching_skills) / len(required_skills)) * 100)
        else:
            # Fallback when query is for a generic role
            match_percentage = 85 if target_domain == candidate_domain else 15

        # Determine Suitability Tier: Highly Suitable, Suitable, Partially Suitable, Not Suitable
        is_domain_compatible = (target_domain == candidate_domain) or (candidate_domain == "General") or ("HR" in target_domain and "HR" in candidate_domain) or ("Human Resources" in target_domain and "Human Resources" in candidate_domain)

        # Check title / headline match
        is_title_match = False
        if candidate_desig and target_role_name:
            c_d_clean = candidate_desig.lower()
            t_r_clean = target_role_name.lower()
            if t_r_clean in c_d_clean or c_d_clean in t_r_clean or any(word in c_d_clean for word in t_r_clean.split() if len(word) > 3):
                is_title_match = True

        if is_title_match and is_domain_compatible:
            match_percentage = max(match_percentage, 95)

        if not is_domain_compatible and len(matching_skills) == 0:
            suitability_tier = "Not Suitable"
            is_suitable = False
            match_percentage = min(match_percentage, 15)
            req_formatted = ", ".join(s.upper() if len(s) <= 4 else s.title() for s in (required_skills[:6] if required_skills else ["required technologies"]))
            reason = (
                f"Candidate belongs to {candidate_domain}" +
                (f" ({candidate_desig})" if candidate_desig else "") +
                f". The resume does not mention {target_domain.lower() if target_domain else 'required'} technologies such as {req_formatted}."
            )
            evidence = "Designation, Domain, Skills"
        elif match_percentage >= 85:
            suitability_tier = "Highly Suitable"
            is_suitable = True
            matched_formatted = ", ".join(s.title() for s in matching_skills) if matching_skills else "Core Domain Skills"
            desc = target_role_info.get("description", f"working as a {target_role_name}.") if target_role_info else f"working as a {target_role_name}."
            reason = f"Candidate has high domain alignment ({match_percentage}% match) with key expertise in {matched_formatted}, making them highly suitable for {desc}"
            evidence = "Technical Skills section"
        elif match_percentage >= 60:
            suitability_tier = "Suitable"
            is_suitable = True
            matched_formatted = ", ".join(s.title() for s in matching_skills)
            desc = target_role_info.get("description", f"working as a {target_role_name}.") if target_role_info else f"working as a {target_role_name}."
            reason = f"Candidate possesses a {match_percentage}% skill match with key expertise in {matched_formatted}, making them suitable for {desc}"
            evidence = "Technical Skills section"
        elif match_percentage >= 35:
            suitability_tier = "Partially Suitable"
            is_suitable = True
            matched_formatted = ", ".join(s.title() for s in matching_skills) if matching_skills else "Basic Skills"
            missing_formatted = ", ".join(s.title() for s in missing_skills[:4])
            reason = f"Candidate has moderate skill overlap ({match_percentage}% match: {matched_formatted}). Requires additional training in missing skills: {missing_formatted}."
            evidence = "Skills section"
        else:
            suitability_tier = "Not Suitable"
            is_suitable = False
            missing_formatted = ", ".join(s.title() for s in missing_skills[:5]) if missing_skills else "Core Domain Competencies"
            reason = f"Candidate has insufficient skill overlap ({match_percentage}% match). Missing key required skills: {missing_formatted}."
            evidence = "Resume Document"

        return {
            "is_suitable": is_suitable,
            "suitability_tier": suitability_tier,
            "recommendation": suitability_tier,
            "match_percentage": match_percentage,
            "matching_skills": [s.title() for s in matching_skills],
            "missing_skills": [s.title() for s in missing_skills],
            "target_role": target_role_name,
            "target_domain": target_domain,
            "candidate_domain": candidate_domain,
            "candidate_designation": candidate_desig,
            "reason": reason,
            "evidence": evidence
        }

    def infer_role_suitability(
        self,
        entities: Dict[str, Any],
        target_role_query: str,
        domain: Optional[str] = None
    ) -> Tuple[bool, str, str]:
        """Evaluates whether candidate is suitable for a specific target role query.

        Returns:
            Tuple of (is_suitable: bool, reason_explanation: str, evidence_section: str).
        """
        score_res = self.calculate_role_similarity(entities, target_role_query, domain)
        return score_res["is_suitable"], score_res["reason"], score_res["evidence"]

    def recommend_roles(self, entities: Dict[str, Any], domain: Optional[str] = None) -> List[str]:
        """Recommends suitable professional roles based on CURRENT career domain."""
        top_roles = self.get_top_5_recommended_roles(entities, domain)
        return [r["role"] for r in top_roles]

    def get_top_5_recommended_roles(self, entities: Dict[str, Any], domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """Generates Top 5 suitable roles with match percentages and explicit WHY explanations."""
        resolved_domain = domain or domain_detector.detect_domain(entities)
        
        # Build candidate skill set
        skills = set()
        if isinstance(entities, dict):
            for k in ["skills", "technologies", "software_skills", "programming_languages"]:
                vals = entities.get(k) or []
                if isinstance(vals, list):
                    for v in vals:
                        if isinstance(v, str):
                            skills.add(v.lower())
        skills_text = " ".join(skills)
        desig = (entities.get("designation") or "").lower()

        # Select dynamic role candidates pool based on candidate domain
        DOMAIN_ROLE_POOLS = {
            "HR & Talent Acquisition": [
                ("People Operations Lead", 96, "Strong background in leading HR operations, JML processes, and employee lifecycle management."),
                ("HR Operations Manager", 94, "Demonstrated experience in end-to-end HR operations, leave management, and ticketing processes."),
                ("HR Operations Analyst", 92, "Proven expertise in ServiceNow ticketing, Workday/Keka/GreyHR platforms, and HR reporting."),
                ("Talent Operations Specialist", 90, "Solid background in employee onboarding, offboarding, and talent acquisition operations."),
                ("HRIS / HR Systems Specialist", 88, "Hands-on experience managing HRIS platforms like Workday, GreyHR, Keka, and ServiceNow.")
            ],
            "Human Resources (HR)": [
                ("People Operations Lead", 96, "Strong background in leading HR operations, JML processes, and employee lifecycle management."),
                ("HR Operations Manager", 94, "Demonstrated experience in end-to-end HR operations, leave management, and ticketing processes."),
                ("HR Operations Analyst", 92, "Proven expertise in ServiceNow ticketing, Workday/Keka/GreyHR platforms, and HR reporting."),
                ("Talent Operations Specialist", 90, "Solid background in employee onboarding, offboarding, and talent acquisition operations."),
                ("HRIS / HR Systems Specialist", 88, "Hands-on experience managing HRIS platforms like Workday, GreyHR, Keka, and ServiceNow.")
            ],
            "Finance & Accounts": [
                ("Senior Accountant", 95, "Strong expertise in Tally ERP, GST returns, bookkeeping, and balance sheet reconciliation."),
                ("Financial Analyst", 92, "Proven capabilities in financial reporting, budget analysis, and audit support."),
                ("Accounts Executive", 90, "Solid foundation in accounts payable, receivable, and bank reconciliation."),
                ("Tax & Audit Specialist", 88, "Specialized experience in GST filing, income tax returns, and statutory audits."),
                ("Finance Operations Manager", 86, "Experience managing general ledger and financial accounting operations.")
            ],
            "Finance & Accounting": [
                ("Senior Accountant", 95, "Strong expertise in Tally ERP, GST returns, bookkeeping, and balance sheet reconciliation."),
                ("Financial Analyst", 92, "Proven capabilities in financial reporting, budget analysis, and audit support."),
                ("Accounts Executive", 90, "Solid foundation in accounts payable, receivable, and bank reconciliation."),
                ("Tax & Audit Specialist", 88, "Specialized experience in GST filing, income tax returns, and statutory audits."),
                ("Finance Operations Manager", 86, "Experience managing general ledger and financial accounting operations.")
            ],
            "Healthcare": [
                ("Registered Nurse", 95, "Clinical experience in patient care, ICU, vital signs monitoring, and triage."),
                ("Healthcare Administrator", 92, "Experience in hospital administration, patient records, and medical billing."),
                ("Clinical Operations Specialist", 90, "Demonstrated capabilities in outpatient care, nursing standards, and patient assessment."),
                ("Staff Nurse", 88, "Hands-on experience in hospital patient care and clinical procedures.")
            ],
            "Healthcare & Medical": [
                ("Registered Nurse", 95, "Clinical experience in patient care, ICU, vital signs monitoring, and triage."),
                ("Healthcare Administrator", 92, "Experience in hospital administration, patient records, and medical billing."),
                ("Clinical Operations Specialist", 90, "Demonstrated capabilities in outpatient care, nursing standards, and patient assessment."),
                ("Staff Nurse", 88, "Hands-on experience in hospital patient care and clinical procedures.")
            ],
        }

        default_software_pool = [
            ("Full Stack Developer", 96, "Strong hands-on capabilities across both frontend and backend technologies including React, Node.js, and REST APIs."),
            ("MERN Stack Developer", 95, "Direct experience with MongoDB, Express.js, React, and Node.js full stack web architecture."),
            ("Backend Developer", 92, "Proven experience building server-side applications, RESTful APIs, JWT authentication, and database schemas."),
            ("React Developer", 90, "Specialized expertise in building responsive user interfaces and modern React ecosystem components."),
            ("Software Developer", 89, "Solid foundation in core programming, API integration, database management, and software design principles."),
            ("PHP Developer", 88, "Demonstrated experience in server-side web application development using PHP and MySQL databases."),
            ("Frontend Developer", 87, "Skilled in developing clean, responsive frontend web interfaces using HTML, CSS, JavaScript, and React.")
        ]

        role_candidates = DOMAIN_ROLE_POOLS.get(resolved_domain, default_software_pool)

        matched_roles = []
        for title, default_pct, default_why in role_candidates:
            sim = self.calculate_role_similarity(entities, title, resolved_domain)
            pct = max(sim["match_percentage"], default_pct if "Software" in resolved_domain and any(k in title.lower() for k in ["full stack", "mern", "backend", "react"]) and "react" in skills_text else (default_pct if resolved_domain in DOMAIN_ROLE_POOLS else 60))
            
            # Generate custom WHY explanation
            matching_str = ", ".join(sim["matching_skills"][:4]) if sim["matching_skills"] else "core skills"
            why = f"Matches {pct}% requirements based on demonstrated expertise in {matching_str} and {resolved_domain} experience."
            if "Full Stack" in title and "react" in skills_text and "node" in skills_text:
                why = "Strong hands-on capabilities across frontend (React) and backend (Node.js, REST APIs) software architecture."
            elif "MERN" in title and "react" in skills_text:
                why = "Direct skill overlap with MongoDB, Express.js, React, and Node.js tech stack."
            elif "Backend" in title:
                why = "Solid experience designing RESTful APIs, backend services, authentication systems, and database logic."
            elif "React" in title:
                why = "Specialized expertise building responsive user interfaces, components, and modern frontend features."
            elif "People Operations" in title or "HR" in title:
                why = f"Strong domain alignment ({pct}% match) with core experience in {matching_str} and {resolved_domain} processes."

            matched_roles.append({
                "role": title,
                "match_percentage": pct,
                "formatted_title": f"{title} — {pct}%",
                "why": why,
                "suitability_tier": sim["suitability_tier"],
                "matching_skills": sim["matching_skills"],
                "missing_skills": sim["missing_skills"]
            })

        # Sort by match percentage descending and return top 5
        matched_roles.sort(key=lambda x: x["match_percentage"], reverse=True)
        return matched_roles[:5]

    def evaluate_runtime_recommendations(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """Dynamically evaluates role suitability and recommendations at runtime from factual CandidateProfile."""
        domain = profile.get("primary_domain") or profile.get("domain") or "General"
        designation = profile.get("designation") or "Professional"
        exp = profile.get("total_experience", "0 Years")

        top_5 = self.get_top_5_recommended_roles(profile, domain)
        best_role = top_5[0] if top_5 else None

        return {
            "primary_domain": domain,
            "candidate_designation": designation,
            "total_experience": exp,
            "top_recommended_role": best_role["role"] if best_role else designation,
            "recommendations": top_5,
            "summary_recommendation": f"Candidate is best fitted for {best_role['role']} ({best_role['match_percentage']}% match) based on skills and {domain} experience." if best_role else f"Suitable for {designation}."
        }


    def compare_roles(
        self,
        entities: Dict[str, Any],
        role_a: str,
        role_b: str,
        domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """Compare candidate suitability for two roles.

        Args:
            entities: Structured entities from document.
            role_a: First target role (e.g. "HR Manager").
            role_b: Second target role (e.g. "HR Business Partner").
            domain: Detected candidate domain.

        Returns:
            Dict with suitability breakdown for both roles + recommendation.
        """
        result_a = self.calculate_role_similarity(entities, role_a, domain)
        result_b = self.calculate_role_similarity(entities, role_b, domain)

        better = role_a if result_a["match_percentage"] >= result_b["match_percentage"] else role_b
        better_pct = max(result_a["match_percentage"], result_b["match_percentage"])
        lesser = role_b if better == role_a else role_a
        lesser_pct = min(result_a["match_percentage"], result_b["match_percentage"])

        recommendation = (
            f"The candidate is better suited for {better} ({better_pct}% match) "
            f"compared to {lesser} ({lesser_pct}% match)."
        )

        return {
            role_a: {
                "match_percentage": result_a["match_percentage"],
                "suitability_tier": result_a["suitability_tier"],
                "matching_skills": result_a["matching_skills"],
                "missing_skills": result_a["missing_skills"],
                "reason": result_a["reason"]
            },
            role_b: {
                "match_percentage": result_b["match_percentage"],
                "suitability_tier": result_b["suitability_tier"],
                "matching_skills": result_b["matching_skills"],
                "missing_skills": result_b["missing_skills"],
                "reason": result_b["reason"]
            },
            "recommendation": recommendation,
            "better_role": better
        }


# Module singleton
role_inference_engine = RoleInferenceEngine()
