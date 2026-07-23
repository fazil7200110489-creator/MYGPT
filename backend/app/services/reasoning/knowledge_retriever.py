"""Knowledge Retriever — Phase 4 of the Resume Intelligence Pipeline.

Retrieves only the *relevant slice* of a structured knowledge store for a
given intent, instead of passing the entire document to the reasoner.
This eliminates full-document scanning for every query and makes each
component responsible for its own data access.

Pipeline position:
    IntentClassifier
        ↓
    KnowledgeRetriever  ← THIS MODULE
        ↓
    ResumeReasoner / Specialist
        ↓
    ...

Design principles:
- Intent → section mapping lives in ``INTENT_SECTION_MAP`` (data-driven).
- Returns a typed ``RetrievedKnowledge`` dataclass so callers get a
  consistent, self-documenting result.
- Reusable for any document type (Resume, Invoice, Policy, Contract, RFP).
  To support a new document type, add entries to ``INTENT_SECTION_MAP``.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Intent → section/field mapping
# ---------------------------------------------------------------------------
# Structure:
#   intent_name → {
#       "fields": [str, ...]       – top-level knowledge dict keys to retrieve
#       "section_keys": [str, ...] – partial section heading matches
#   }
# ---------------------------------------------------------------------------

INTENT_SECTION_MAP: Dict[str, Dict[str, List[str]]] = {
    "CANDIDATE_NAME": {
        "fields":       ["candidate_name", "name"],
        "section_keys": [],
    },
    "FATHER_NAME": {
        "fields":       ["father_name"],
        "section_keys": [],
    },
    "MOTHER_NAME": {
        "fields":       ["mother_name"],
        "section_keys": [],
    },
    "EMAIL": {
        "fields":       ["email", "emails"],
        "section_keys": ["contact", "personal"],
    },
    "PHONE": {
        "fields":       ["phone", "phones"],
        "section_keys": ["contact", "personal"],
    },
    "ADDRESS": {
        "fields":       ["address", "location", "addresses"],
        "section_keys": ["contact", "address", "personal"],
    },
    "LINKEDIN": {
        "fields":       ["linkedin"],
        "section_keys": ["contact"],
    },
    "GITHUB": {
        "fields":       ["github"],
        "section_keys": ["contact"],
    },
    "DESIGNATION": {
        "fields":       ["designation", "designations", "job_title"],
        "section_keys": ["designation", "objective", "profile"],
    },
    "EXPERIENCE": {
        "fields":       ["work_experience", "experience"],
        "section_keys": ["experience", "work experience", "employment", "career"],
    },
    "SKILLS": {
        "fields":       ["skills", "technologies"],
        "section_keys": ["skills", "technical skills", "technologies", "core competencies", "expertise"],
    },
    "PROGRAMMING_LANGUAGES": {
        "fields":       ["programming_languages", "skills"],
        "section_keys": ["skills", "technical skills", "languages"],
    },
    "HUMAN_LANGUAGES": {
        "fields":       ["languages", "human_languages"],
        "section_keys": ["languages"],
    },
    "PROJECTS": {
        "fields":       ["projects"],
        "section_keys": ["projects", "portfolio", "applications"],
    },
    "CERTIFICATIONS": {
        "fields":       ["certifications"],
        "section_keys": ["certifications", "certificates", "achievements", "awards"],
    },
    "EDUCATION": {
        "fields":       ["education"],
        "section_keys": ["education", "academic", "qualifications", "schooling"],
    },
    "OBJECTIVE": {
        "fields":       ["objective", "career_objective"],
        "section_keys": ["objective", "summary", "profile"],
    },
    "ACHIEVEMENTS": {
        "fields":       ["achievements", "awards", "certifications"],
        "section_keys": ["achievements", "awards", "certifications"],
    },
    "SUMMARY": {
        "fields":       ["summary", "profile_summary"],
        "section_keys": ["summary", "profile", "about"],
    },
    "PROFILE_SUMMARY": {
        "fields":       ["summary", "profile_summary"],
        "section_keys": ["summary", "profile"],
    },
    "BASIC_PROFILE": {
        "fields":       [
            "candidate_name", "name", "designation", "email",
            "phone", "address", "work_experience", "experience", "education",
        ],
        "section_keys": [],
    },
    "CONTACT": {
        "fields":       ["email", "phone", "address", "linkedin", "github"],
        "section_keys": ["contact", "personal"],
    },
    "GENDER": {
        "fields":       ["gender"],
        "section_keys": ["personal"],
    },
    "AGE": {
        "fields":       ["age", "date_of_birth"],
        "section_keys": ["personal"],
    },
    "DATE_OF_BIRTH": {
        "fields":       ["date_of_birth", "dob"],
        "section_keys": ["personal"],
    },
    "SALARY": {
        "fields":       ["salary", "ctc"],
        "section_keys": [],
    },
    "NOTICE_PERIOD": {
        "fields":       ["notice_period"],
        "section_keys": [],
    },
    "MARITAL_STATUS": {
        "fields":       ["marital_status"],
        "section_keys": ["personal"],
    },
    "ROLE_INFERENCE": {
        "fields":       ["skills", "technologies", "work_experience", "experience", "designation"],
        "section_keys": ["skills", "experience"],
    },
    "GENERAL": {
        "fields":       ["skills", "work_experience", "experience", "designation",
                         "candidate_name", "name"],
        "section_keys": [],
    },
    # Invoice / Excel / Generic intents
    "INVOICE_TOTAL": {
        "fields":       ["total", "grand_total", "amount"],
        "section_keys": ["total", "payment"],
    },
    "COUNT": {
        "fields":       ["tables"],
        "section_keys": [],
    },
}


@dataclass
class RetrievedKnowledge:
    """Structured result returned by KnowledgeRetriever.

    Attributes:
        intent:        The intent this retrieval was performed for.
        fields:        Dict of {field_name: value} for relevant top-level fields.
        sections:      Dict of {section_name: section_text} for relevant sections.
        raw_knowledge: The full knowledge dict (for specialist use when needed).
    """
    intent: str
    fields: Dict[str, Any] = field(default_factory=dict)
    sections: Dict[str, str] = field(default_factory=dict)
    raw_knowledge: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Convenience accessor — checks fields first, then raw_knowledge."""
        if key in self.fields:
            return self.fields[key]
        return self.raw_knowledge.get(key, default)

    @property
    def is_empty(self) -> bool:
        """True if no meaningful data was retrieved."""
        return not self.fields and not self.sections


class KnowledgeRetriever:
    """Retrieves the relevant slice of a knowledge store for a given intent.

    Usage::

        retriever = KnowledgeRetriever()
        rk = retriever.retrieve(knowledge_dict, "EXPERIENCE")
        exp_data = rk.fields.get("work_experience")
    """

    def retrieve(
        self,
        knowledge: Dict[str, Any],
        intent: str,
    ) -> RetrievedKnowledge:
        """Retrieve the knowledge slice relevant to *intent*.

        Args:
            knowledge: Full knowledge dict from the knowledge store.
            intent:    Canonical intent string (e.g. "EXPERIENCE").

        Returns:
            ``RetrievedKnowledge`` with populated fields and sections.
        """
        if not knowledge:
            return RetrievedKnowledge(intent=intent, raw_knowledge={})

        mapping = INTENT_SECTION_MAP.get(intent.upper(), {
            "fields": [],
            "section_keys": [],
        })

        # --- Extract top-level fields ---
        fields: Dict[str, Any] = {}
        for field_name in mapping["fields"]:
            val = self._get_nested(knowledge, field_name)
            if val is not None:
                fields[field_name] = val

        # --- Extract matching sections ---
        sections: Dict[str, str] = {}
        all_sections: Dict[str, str] = knowledge.get("sections", {})
        section_keys: List[str] = mapping["section_keys"]

        for sec_name, sec_content in all_sections.items():
            sec_lower = sec_name.lower()
            if any(key in sec_lower for key in section_keys):
                sections[sec_name] = sec_content

        return RetrievedKnowledge(
            intent=intent,
            fields=fields,
            sections=sections,
            raw_knowledge=knowledge,
        )

    def retrieve_multi(
        self,
        knowledge: Dict[str, Any],
        intents: List[str],
    ) -> Dict[str, RetrievedKnowledge]:
        """Retrieve knowledge slices for multiple intents at once.

        Args:
            knowledge: Full knowledge dict from the knowledge store.
            intents:   List of canonical intent strings.

        Returns:
            Dict mapping each intent to its ``RetrievedKnowledge``.
        """
        return {intent: self.retrieve(knowledge, intent) for intent in intents}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_nested(d: Dict[str, Any], key: str) -> Any:
        """Look up a key, also checking common nested locations."""
        # Direct lookup
        if key in d:
            return d[key]

        # Check under 'facts'
        facts = d.get("facts", {})
        if isinstance(facts, dict) and key in facts:
            return facts[key]

        # Check under 'entities'
        entities = d.get("entities", {})
        if isinstance(entities, dict) and key in entities:
            return entities[key]

        return None
