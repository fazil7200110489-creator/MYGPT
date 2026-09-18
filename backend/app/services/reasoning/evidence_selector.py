"""Evidence Selector — Phase of the Resume Intelligence Pipeline.

Selects precise evidence ONLY from relevant resume sections based on intent.
Enforces strict section boundaries to prevent cross-contamination (e.g.
requesting 'JavaScript' must NEVER return 'Internshala Certification').

Pipeline position:
    ResumeReasoner
        ↓
    EvidenceSelector    ← THIS MODULE
        ↓
    ConfidenceCalculator
        ↓
    AnswerBuilder
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SelectedEvidence:
    """Structured evidence selection result.

    Attributes:
        is_found:       True if target evidence was located in the resume.
        evidence_text:  Exact text/line retrieved as evidence.
        section_name:   Canonical name of the source section (e.g. "Technical Skills section").
        matched_tokens: List of tokens/skills that matched.
        reasoning:      Concise explanation of the finding.
    """
    is_found: bool
    evidence_text: str
    section_name: str
    matched_tokens: List[str]
    reasoning: str


class EvidenceSelector:
    """Selects target evidence strictly from designated resume sections.

    Usage::

        selector = EvidenceSelector()
        evidence = selector.select(
            entities=extracted_entities,
            sections=knowledge_sections,
            intent="SKILLS",
            topic="JavaScript"
        )
    """

    # Intent to allowed sections & entity keys mapping
    INTENT_SECTION_RULES: Dict[str, Tuple[List[str], List[str]]] = {
        "SKILLS": (
            ["skills", "technical skills", "technologies", "core competencies", "expertise", "programming", "software skills", "hr skills"],
            ["skills", "programming_languages", "technologies", "software_skills", "hardware_skills", "competencies", "hr_skills"],
        ),
        "SKILL_VERIFY": (
            ["skills", "technical skills", "technologies", "core competencies", "expertise", "hr skills"],
            ["skills", "programming_languages", "technologies", "software_skills", "hardware_skills", "competencies", "hr_skills"],
        ),
        "PROGRAMMING_LANGUAGES": (
            ["skills", "languages", "programming"],
            ["programming_languages", "skills"],
        ),
        "HUMAN_LANGUAGES": (
            ["languages", "spoken languages", "personal"],
            ["human_languages", "languages"],
        ),
        "EXPERIENCE": (
            ["experience", "work experience", "employment", "career", "work history"],
            ["work_experience", "experience", "companies", "designation"],
        ),
        "DOMAIN_EXPERIENCE": (
            ["experience", "work experience", "employment", "career history"],
            ["work_experience", "experience"],
        ),
        "TIMELINE": (
            ["experience", "work experience", "employment history"],
            ["work_experience", "experience"],
        ),
        "CAREER_TRANSITION": (
            ["experience", "work experience", "career"],
            ["work_experience", "experience", "designation"],
        ),
        "EDUCATION": (
            ["education", "academic", "qualifications", "degree", "schooling"],
            ["education"],
        ),
        "GRADUATION_YEAR": (
            ["education", "academic", "qualifications"],
            ["education"],
        ),
        "CGPA": (
            ["education", "academic", "qualifications"],
            ["education"],
        ),
        "PROJECTS": (
            ["projects", "portfolio", "built", "applications"],
            ["projects"],
        ),
        "CERTIFICATIONS": (
            ["certifications", "certificates", "courses", "professional certifications"],
            ["certifications"],
        ),
        "AWARDS": (
            ["awards", "recognitions", "honors", "achievements"],
            ["awards"],
        ),
        "CONTACT": (
            ["contact", "personal details", "address"],
            ["phones", "emails", "addresses", "phone", "email", "address", "linkedin", "github"],
        ),
        "PHONE": (
            ["contact", "personal"],
            ["phones", "phone"],
        ),
        "EMAIL": (
            ["contact", "personal"],
            ["emails", "email"],
        ),
        "ADDRESS": (
            ["contact", "address", "location"],
            ["addresses", "address", "location", "current_location", "permanent_address"],
        ),
        "CURRENT_COMPANY": (
            ["experience", "work experience", "employment"],
            ["work_experience", "experience"],
        ),
        "DESIGNATION": (
            ["experience", "personal", "profile"],
            ["designation"],
        ),
    }

    def select(
        self,
        entities: Dict[str, Any],
        sections: Dict[str, str],
        intent: str,
        topic: Optional[str] = None,
        question: Optional[str] = None,
    ) -> SelectedEvidence:
        """Select evidence strictly from the allowed section(s) for the given intent.

        Args:
            entities:  Extracted entities dict.
            sections:  Knowledge sections dict.
            intent:    Canonical intent string.
            topic:     Specific search topic (e.g. "JavaScript", "API Integration").
            question:  Full question text for context.

        Returns:
            ``SelectedEvidence`` object with selection details.
        """
        intent_upper = intent.upper()
        rules = self.INTENT_SECTION_RULES.get(
            intent_upper,
            (["skills", "experience", "education", "projects"], ["skills", "experience", "education", "projects"]),
        )
        allowed_sec_kws, allowed_entity_keys = rules

        topic_clean = (topic or "").strip().lower()

        # Step 1: Search structured entities in allowed entity keys ONLY
        for key in allowed_entity_keys:
            val = entities.get(key)
            if not val:
                continue
            val_list = val if isinstance(val, list) else [str(val)]
            for item in val_list:
                item_str = str(item).strip()
                item_lower = item_str.lower()
                if topic_clean:
                    # Match topic in item
                    if self._matches_topic(topic_clean, item_lower):
                        sec_label = self._format_section_name(key)
                        # Return exact matching tokens, not just item_str
                        matched_tokens_exact = [t for t in item_str.split() if topic_clean in t.lower()]
                        return SelectedEvidence(
                            is_found=True,
                            evidence_text=item_str,
                            section_name=sec_label,
                            matched_tokens=matched_tokens_exact or [topic_clean],
                            reasoning=f"{item_str} is listed under {sec_label}.",
                        )
                else:
                    # No specific topic, return first valid entry in allowed key
                    sec_label = self._format_section_name(key)
                    return SelectedEvidence(
                        is_found=True,
                        evidence_text=item_str,
                        section_name=sec_label,
                        matched_tokens=[],
                        reasoning=f"Found in {sec_label}.",
                    )

        # Step 2: Search allowed knowledge sections text ONLY
        for sec_name, sec_content in sections.items():
            sec_lower = sec_name.lower()
            if any(kw in sec_lower for kw in allowed_sec_kws):
                lines = [l.strip() for l in sec_content.split("\n") if l.strip()]
                for line in lines:
                    line_lower = line.lower()
                    if topic_clean and self._matches_topic(topic_clean, line_lower):
                        formatted_sec = f"{sec_name} section"
                        return SelectedEvidence(
                            is_found=True,
                            evidence_text=line,
                            section_name=formatted_sec,
                            matched_tokens=[topic_clean],
                            reasoning=f"Mentioned in {formatted_sec}.",
                        )

        # Fallback for skill synonym reasoning (e.g. API Integration -> .NET Web API / Express)
        if intent_upper in ["SKILLS", "PROGRAMMING_LANGUAGES", "GENERAL", "ROLE_INFERENCE"] and topic_clean:
            syn_evidence = self._check_skill_synonyms(entities, topic_clean)
            if syn_evidence:
                return syn_evidence

        # Not found in allowed section
        sec_display = allowed_sec_kws[0].title() if allowed_sec_kws else "Technical Skills"
        return SelectedEvidence(
            is_found=False,
            evidence_text="",
            section_name=f"{sec_display} section",
            matched_tokens=[],
            reasoning=f"The uploaded resume does not mention {topic or 'this information'} under {sec_display}.",
        )

    def _matches_topic(self, topic: str, text: str) -> bool:
        """Check if topic matches text using whole-word regex or boundary matching."""
        if not topic or not text:
            return False
        if topic in text:
            return True
        pattern = r"\b" + re.escape(topic) + r"\b"
        return bool(re.search(pattern, text))

    def _check_skill_synonyms(self, entities: Dict[str, Any], topic: str) -> Optional[SelectedEvidence]:
        """Check known skill/domain equivalences when exact keyword is absent.

        e.g. Topic "api integration" → matches ".net web api", "express.js", "rest api", "fastapi".
        """
        all_skills = [
            s.lower() for s in
            (entities.get("skills") or []) +
            (entities.get("programming_languages") or []) +
            (entities.get("software_skills") or []) +
            (entities.get("hardware_skills") or []) +
            (entities.get("technologies") or [])
        ]
        all_skills_text = " ".join(all_skills)

        synonym_maps = {
            "rest api": ["rest api", "restful api", "restful apis", "rest apis", "api integration", "api development", "backend apis", "api design", "web api", "express", "fastapi"],
            "restful api": ["rest api", "restful api", "restful apis", "rest apis", "api integration", "api development", "backend apis", "api design", "web api"],
            "api integration": [".net web api", "express", "fastapi", "rest api", "graphql", "web api", "api", "restful api"],
            "api development": [".net web api", "express", "fastapi", "rest api", "web api", "api", "restful api"],
            "api": [".net web api", "express", "fastapi", "rest api", "graphql", "web api", "restful api"],
            "react": ["react", "react.js", "reactjs", "react native"],
            "reactjs": ["react", "react.js", "reactjs"],
            "react.js": ["react", "react.js", "reactjs"],
            "react js": ["react", "react.js", "reactjs"],
            "node": ["node", "node.js", "nodejs", "express"],
            "nodejs": ["node", "node.js", "nodejs"],
            "node.js": ["node", "node.js", "nodejs"],
            "node js": ["node", "node.js", "nodejs", "express"],
            "express js": ["express", "express.js", "expressjs"],
            "php": ["php", "php 8", "php 7", "php7", "php8", "laravel"],
            "docker": ["docker", "containerization", "containers", "devops", "aws"],
            "javascript": ["javascript", "js", "typescript", "react", "node", "express"],
            "mobile development": ["flutter", "dart", "react native", "swift", "kotlin", "android", "ios"],
            "mobile": ["flutter", "dart", "react native", "swift", "kotlin", "android", "ios"],
            "full stack": ["react", "node", "express", "mongodb", "mern", "mean"],
            "frontend": ["react", "angular", "vue", "html", "css", "javascript", "tailwind"],
            "backend": ["node", "express", "django", "flask", "fastapi", "spring", "laravel", ".net"],
            "cloud": ["aws", "docker", "kubernetes", "gcp", "azure"],
            "devops": ["docker", "kubernetes", "jenkins", "ci/cd", "aws"],
            # Multi-domain synonyms
            "gst": ["gst", "goods and services tax", "tally", "taxation"],
            "tally": ["tally", "tally erp", "tally prime", "tally 9"],
            "accounting": ["tally", "gst", "sap fico", "bookkeeping", "balance sheet", "auditing", "quickbooks"],
            "accountant": ["tally", "gst", "sap fico", "accounting", "bookkeeping"],
            "payroll": ["payroll", "hrms", "employee relations", "labor laws", "compensation"],
            "hrms": ["hrms", "payroll", "onboarding", "recruitment"],
            "hr": ["recruitment", "payroll", "hrms", "employee relations", "onboarding", "talent acquisition"],
            "autocad": ["autocad", "cad", "2d autocad", "3d autocad"],
            "boq": ["boq", "bill of quantities", "estimation", "quantity surveying"],
            "civil": ["autocad", "boq", "primavera", "site execution", "staad pro", "quantity surveying"],
            "electrical": ["mv panel", "lv panel", "transformer", "switchgear", "plc", "scada", "single line diagram"],
            "mechanical": ["solidworks", "catia", "hvac", "piping", "ansys", "cad/cam"],
            "sql": ["sql", "mysql", "postgresql", "sql server", "sqlite"],
            "power bi": ["power bi", "tableau", "dashboards", "data visualization"],
            "data analytics": ["sql", "python", "power bi", "tableau", "excel", "pandas", "data visualization"],
            "selenium": ["selenium", "automation testing", "cypress", "postman"],
            "figma": ["figma", "wireframing", "adobe xd", "prototyping"]
        }

        matches = synonym_maps.get(topic, [])
        found_tokens = [m for m in matches if m in all_skills_text]
        if found_tokens:
            matched_names = [t.title() for t in found_tokens[:3]]
            matched_str = " and ".join(matched_names)
            return SelectedEvidence(
                is_found=True,
                evidence_text=", ".join(matched_names),
                section_name="Technical Skills section",
                matched_tokens=found_tokens,
                reasoning=f"The resume includes {matched_str}, indicating experience with {topic.title()}.",
            )
        return None

    def _format_section_name(self, entity_key: str) -> str:
        """Format an entity key into a user-friendly section name."""
        mapping = {
            "skills": "Technical Skills section",
            "programming_languages": "Technical Skills section",
            "technologies": "Technical Skills section",
            "software_skills": "Technical Skills section",
            "hardware_skills": "Technical Skills section",
            "competencies": "Skills & Competencies section",
            "work_experience": "Work Experience section",
            "experience": "Work Experience section",
            "education": "Education section",
            "projects": "Projects section",
            "certifications": "Certifications section",
            "phones": "Contact Information section",
            "emails": "Contact Information section",
            "addresses": "Contact Information section",
        }
        return mapping.get(entity_key, f"{entity_key.title()} section")


# Singleton instance
evidence_selector = EvidenceSelector()
