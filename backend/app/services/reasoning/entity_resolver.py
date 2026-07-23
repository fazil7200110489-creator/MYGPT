"""Entity Resolver module for mapping canonical query intents to CandidateProfile subtrees.

Implements Targeted Fallback Search:
    If an entity is absent from CandidateProfile, performs a targeted text search,
    extracts the missing entity, updates CandidateProfile, and re-executes reasoning over
    the updated Single Source of Truth.
"""

import re
from typing import Dict, Any, Tuple, Optional, List
from loguru import logger

from backend.app.services.reasoning.candidate_profile_builder import candidate_profile_builder


class EntityResolver:
    """Resolves canonical intents to CandidateProfile subtrees with targeted fallback profile updates."""

    INTENT_SUBTREE_MAP: Dict[str, str] = {
        "CONTACT": "personal_info",
        "PHONE": "personal_info.phone",
        "EMAIL": "personal_info.email",
        "ADDRESS": "personal_info.address",
        "LINKEDIN": "personal_info.linkedin",
        "GITHUB": "personal_info.github",
        "PORTFOLIO": "personal_info.portfolio",
        "CANDIDATE_NAME": "personal_info.name",

        "EDUCATION": "education",
        "CGPA": "education.cgpa_percentage",
        "GRADUATION_YEAR": "education.year",

        "SKILLS": "skills",
        "PROGRAMMING_LANGUAGES": "skills.programming_languages",
        "ERP_PLATFORMS": "skills.erp_platforms",
        "AI_TOOLS": "skills.ai_tools",
        "ANALYTICS_TOOLS": "skills.analytics_tools",
        "HR_SKILLS": "skills.hr_skills",
        "SOFT_SKILLS": "skills.soft_skills",

        "EXPERIENCE": "experience",
        "TIMELINE": "experience.timeline",
        "DOMAIN_EXPERIENCE": "experience.domain_experience",
        "CURRENT_COMPANY": "experience.current_company",

        "AWARDS": "awards",
        "CERTIFICATIONS": "certifications",

        "PROJECTS": "projects",

        "COMPANIES": "companies",
        "DOMAIN": "domains",
        "SUMMARY": "full_profile",
    }

    def resolve(
        self,
        profile: Dict[str, Any],
        intent: str,
        question: Optional[str] = None,
        raw_text: str = "",
        raw_entities: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Any, str, bool]:
        """Resolves the requested entity from CandidateProfile.

        Args:
            profile: Factual CandidateProfile dictionary.
            intent: Canonical intent string.
            question: Raw query string.
            raw_text: Full document text (used for targeted fallback if profile field is missing).
            raw_entities: Raw entities dictionary (optional).

        Returns:
            Tuple of (resolved_value, resolved_subtree_path, was_updated_by_fallback).
        """
        intent_upper = (intent or "").upper().strip()
        subtree_path = self.INTENT_SUBTREE_MAP.get(intent_upper, "full_profile")

        value, is_present = self._extract_field(profile, intent_upper)

        # If data is present in CandidateProfile, return immediately (Single Source of Truth)
        if is_present:
            return value, subtree_path, False

        # If missing and raw text is available, trigger Targeted Fallback Search to update CandidateProfile
        if raw_text:
            logger.info(f"Field for intent '{intent_upper}' missing in profile. Triggering Targeted Fallback Search...")
            updated_profile = self._targeted_fallback_update(profile, intent_upper, question or "", raw_text, raw_entities)
            value, is_present = self._extract_field(updated_profile, intent_upper)
            return value, subtree_path, True

        return value, subtree_path, False

    def _extract_field(self, profile: Dict[str, Any], intent: str) -> Tuple[Any, bool]:
        """Extract field value and check presence from profile."""
        if intent in ["CANDIDATE_NAME", "NAME"]:
            val = profile.get("name")
            return val, bool(val and val != "Not Mentioned")

        if intent in ["CONTACT", "CONTACT_DETAILS"]:
            val = {
                "name": profile.get("name"),
                "email": profile.get("email"),
                "phone": profile.get("phone"),
                "address": profile.get("address"),
                "current_location": profile.get("current_location"),
                "permanent_address": profile.get("permanent_address"),
                "linkedin": profile.get("linkedin"),
                "github": profile.get("github"),
                "portfolio": profile.get("portfolio"),
            }
            is_present = any(v and v != "Not Mentioned" for k, v in val.items() if k != "name")
            return val, is_present

        if intent == "PHONE":
            val = profile.get("phone")
            return val, bool(val and val != "Not Mentioned")

        if intent == "EMAIL":
            val = profile.get("email")
            return val, bool(val and val != "Not Mentioned")

        if intent in ["ADDRESS", "LOCATION"]:
            val = {
                "current_location": profile.get("current_location"),
                "permanent_address": profile.get("permanent_address"),
                "work_location": profile.get("work_location"),
                "address": profile.get("address"),
                "address_details": profile.get("address_details"),
            }
            is_present = any(v and v != "Not Mentioned" for v in val.values() if v)
            return val, is_present

        if intent == "COMPANIES":
            val = profile.get("companies", [])
            return val, bool(val)

        if intent == "EDUCATION":
            val = profile.get("education", [])
            is_present = bool(val and val[0].get("degree") != "Not Mentioned")
            return val, is_present

        if intent == "CGPA":
            val = [e.get("cgpa_percentage") for e in profile.get("education", []) if e.get("cgpa_percentage") != "Not Mentioned"]
            return val[0] if val else "Not Mentioned", bool(val)

        if intent == "SKILLS":
            val = profile.get("skills", [])
            return val, bool(val)

        if intent == "ERP_PLATFORMS":
            val = profile.get("erp_platforms", [])
            return val, bool(val)

        if intent == "PROGRAMMING_LANGUAGES":
            val = profile.get("programming_languages", [])
            return val, bool(val)

        if intent == "EXPERIENCE":
            val = {
                "total_experience": profile.get("total_experience"),
                "current_domain_experience": profile.get("current_domain_experience"),
                "current_company_experience": profile.get("current_company_experience"),
                "per_domain_experience": profile.get("per_domain_experience"),
                "timeline": profile.get("experience_timeline", []),
                "companies": profile.get("companies", []),
                "history": profile.get("experience_history", []),
            }
            is_present = bool(profile.get("experience_timeline") or profile.get("total_experience") != "Not Mentioned")
            return val, is_present

        if intent == "AWARDS":
            val = profile.get("awards", [])
            return val, bool(val)

        if intent == "CERTIFICATIONS":
            val = profile.get("certifications", [])
            return val, bool(val)

        if intent == "PROJECTS":
            val = profile.get("projects", [])
            return val, bool(val)

        # Default fallback to full profile
        return profile, True

    def _targeted_fallback_update(
        self,
        profile: Dict[str, Any],
        intent: str,
        question: str,
        text: str,
        raw_entities: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Performs targeted extraction over OCR text and updates CandidateProfile."""
        entities = raw_entities or {}

        if intent in ["PHONE", "EMAIL", "CONTACT"]:
            # Targeted regex scan for email/phone in raw text
            emails = re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', text)
            phones = re.findall(r'(?:\+?\d{1,3}[\s\-.])?[\(\[\{]?\d{2,5}[\)\]\}]?[\s\-.]?\d{3,5}[\s\-.]?\d{3,5}', text)
            if emails and profile.get("email") == "Not Mentioned":
                profile["email"] = emails[0].strip().lower()
            if phones and profile.get("phone") == "Not Mentioned":
                profile["phone"] = phones[0].strip()

        elif intent == "COMPANIES":
            timeline = profile.get("experience_timeline", [])
            comps = [t["company"] for t in timeline if t.get("company") and t["company"] not in ("Not Mentioned", "Company")]
            if not comps and text:
                matches = re.findall(r'(?:at|—|-|–|by)\s+([A-Z][A-Za-z0-9\s]+?)(?:,|\n|\(|\d{4}|$)', text)
                comps = list(dict.fromkeys([m.strip() for m in matches if len(m.strip()) > 3 and m.strip().lower() not in ("present", "current")]))
            profile["companies"] = comps

        elif intent == "AWARDS":
            awards_m = re.search(r'(?i)(?:awards?|recognitions?|honours?)\s*:?\s*\n?([\s\S]{5,400}?)(?=\n\n|\Z)', text)
            if awards_m:
                lines = [l.strip() for l in awards_m.group(1).split('\n') if len(l.strip()) > 3]
                if lines:
                    new_awards = [{"name": l, "organization": "Not Mentioned", "year": "Not Mentioned", "category": "Award"} for l in lines]
                    profile["awards"] = profile.get("awards", []) + new_awards

        # Re-run candidate profile validation flags
        profile["validation_flags"] = {
            "has_experience": bool(profile.get("experience_timeline") or profile.get("total_experience") != "Not Mentioned"),
            "has_education": bool(profile.get("education") and profile["education"][0].get("degree") != "Not Mentioned"),
            "has_skills": bool(profile.get("skills")),
            "has_location": bool(profile.get("current_location") != "Not Mentioned" or profile.get("permanent_address") != "Not Mentioned"),
            "has_awards": bool(profile.get("awards")),
            "has_timeline": bool(profile.get("experience_timeline")),
            "has_certifications": bool(profile.get("certifications"))
        }

        return profile


# Singleton instance
entity_resolver = EntityResolver()
