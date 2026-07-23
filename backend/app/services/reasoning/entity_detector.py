"""Entity Detector — Phase 2 of the Resume Intelligence Pipeline.

Detects *which resume fields* the user is asking about in a normalized
question.  This is distinct from the EntityExtractor (which extracts
fields FROM the resume text).  The EntityDetector operates on the
*question* to understand intent multiplicity, e.g.::

    "name and age"  →  [QuestionEntity.NAME, QuestionEntity.AGE]
    "skills"        →  [QuestionEntity.SKILLS]
    "experience"    →  [QuestionEntity.WORK_EXPERIENCE]

Pipeline position:
    QuestionNormalizer
        ↓
    EntityDetector      ← THIS MODULE
        ↓
    IntentClassifier
        ↓
    ...
"""

import re
from enum import Enum
from typing import List, Dict, Tuple


class QuestionEntity(str, Enum):
    """Canonical question-entity types for resume queries.

    Adding a new entity type only requires:
    1. Adding a member here.
    2. Adding its trigger tokens to ENTITY_TRIGGERS below.
    No other code changes required.
    """
    # Personal / Contact
    NAME             = "NAME"
    AGE              = "AGE"
    DATE_OF_BIRTH    = "DATE_OF_BIRTH"
    GENDER           = "GENDER"
    EMAIL            = "EMAIL"
    PHONE            = "PHONE"
    ADDRESS          = "ADDRESS"
    LINKEDIN         = "LINKEDIN"
    GITHUB           = "GITHUB"
    NATIONALITY      = "NATIONALITY"

    # Professional
    DESIGNATION      = "DESIGNATION"
    WORK_EXPERIENCE  = "WORK_EXPERIENCE"
    SKILLS           = "SKILLS"
    PROJECTS         = "PROJECTS"
    CERTIFICATIONS   = "CERTIFICATIONS"
    EDUCATION        = "EDUCATION"
    LANGUAGES        = "LANGUAGES"
    PROGRAMMING_LANGS = "PROGRAMMING_LANGS"
    ACHIEVEMENTS     = "ACHIEVEMENTS"
    OBJECTIVE        = "OBJECTIVE"

    # Inference / Reasoning
    DOMAIN           = "DOMAIN"       # "what is the domain", "which industry"
    ROLE             = "ROLE"         # "is he a backend developer?"
    SUITABILITY      = "SUITABILITY"  # "is this candidate suitable for X?"
    SUMMARY          = "SUMMARY"      # "summarize", "overview"
    CONTACT          = "CONTACT"      # broad "contact details"
    BASIC_PROFILE    = "BASIC_PROFILE"

    # Family / Personal Details (not usually in resume)
    FATHER_NAME      = "FATHER_NAME"
    MOTHER_NAME      = "MOTHER_NAME"
    MARITAL_STATUS   = "MARITAL_STATUS"
    SALARY           = "SALARY"
    NOTICE_PERIOD    = "NOTICE_PERIOD"


# ---------------------------------------------------------------------------
# Configuration: entity → trigger tokens (normalized, lowercase)
# ---------------------------------------------------------------------------
# Each entry is (QuestionEntity, [trigger_token_or_phrase, ...])
# Tokens are matched as whole words (word-boundary regex).
# Multi-word phrases take priority if listed before single words.
# ---------------------------------------------------------------------------

ENTITY_TRIGGERS: List[Tuple[QuestionEntity, List[str]]] = [
    # Family
    (QuestionEntity.FATHER_NAME,      ["father name", "father's name", "father"]),
    (QuestionEntity.MOTHER_NAME,      ["mother name", "mother's name", "mother"]),
    (QuestionEntity.MARITAL_STATUS,   ["marital", "married", "marital status", "relationship status"]),

    # Specific personal
    (QuestionEntity.DATE_OF_BIRTH,    ["date of birth", "dob", "d o b", "birth date", "birthday"]),
    (QuestionEntity.AGE,              ["age"]),
    (QuestionEntity.GENDER,           ["gender", "sex", "male", "female"]),
    (QuestionEntity.NATIONALITY,      ["nationality", "citizen", "citizenship"]),
    (QuestionEntity.SALARY,           ["salary", "ctc", "compensation", "pay"]),
    (QuestionEntity.NOTICE_PERIOD,    ["notice period", "notice"]),

    # Role / suitability inference / Domain
    (QuestionEntity.DOMAIN,           ["domain", "industry", "field of work", "profession", "sector"]),
    (QuestionEntity.SUITABILITY,      [
        "suitable for", "fit for", "good for", "right for",
        "qualify for", "apply for", "eligible for",
    ]),
    (QuestionEntity.ROLE,             [
        "app developer", "backend developer", "frontend developer",
        "full stack developer", "fullstack developer",
        "mobile developer", "devops engineer", "cloud engineer",
        "ml engineer", "ai engineer", "data engineer",
        "work as", "work like", "act as", "serve as",
        "developer", "engineer", "programmer",
    ]),

    # Summary
    (QuestionEntity.SUMMARY,          [
        "summarize", "summary", "overview", "brief", "synopsis",
        "profile summary", "who is", "who's", "who is this",
        "summarize education",
    ]),

    # Name
    (QuestionEntity.NAME,             ["name", "candidate name", "applicant name", "full name"]),

    # Contact details (broad query, prioritized before specific fields)
    (QuestionEntity.CONTACT,          ["contact details", "contact info", "contact information", "contact"]),
    (QuestionEntity.EMAIL,            ["email", "gmail", "e-mail", "mail"]),
    (QuestionEntity.PHONE,            ["phone", "mobile", "cell", "telephone"]),
    (QuestionEntity.BASIC_PROFILE,    ["basic details", "basic profile", "basic info", "basic information"]),
    (QuestionEntity.ADDRESS,          ["address", "location", "city", "residence", "place"]),
    (QuestionEntity.LINKEDIN,         ["linkedin"]),
    (QuestionEntity.GITHUB,           ["github"]),

    # Professional
    (QuestionEntity.DESIGNATION,      ["designation", "job role", "job title", "position", "role"]),
    (QuestionEntity.WORK_EXPERIENCE,  [
        "experience", "work history", "employment", "career",
        "company", "worked", "employment history",
    ]),
    (QuestionEntity.SKILLS,           [
        "skills", "technical skills", "technologies", "frameworks",
        "tools", "libraries", "tech stack", "software", "expertise",
    ]),
    (QuestionEntity.PROGRAMMING_LANGS,["programming language", "programming languages", "coding language"]),
    (QuestionEntity.LANGUAGES,        ["language", "languages", "speak", "spoken", "human language"]),
    (QuestionEntity.PROJECTS,         ["projects", "project", "portfolio", "developed", "built", "application"]),
    (QuestionEntity.CERTIFICATIONS,   ["certifications", "certification", "certificate", "courses", "training"]),
    (QuestionEntity.EDUCATION,        [
        "education", "degree", "college", "university", "school",
        "academic", "graduation", "qualification", "qualifications",
    ]),
    (QuestionEntity.ACHIEVEMENTS,     ["achievement", "achievements", "award", "awards", "honor", "honours"]),
    (QuestionEntity.OBJECTIVE,        ["objective", "goal", "target", "career objective"]),
]

# Pre-sort: multi-word triggers before single-word ones to prevent partial match
_SORTED_TRIGGERS: List[Tuple[QuestionEntity, List[str]]] = [
    (entity, sorted(tokens, key=len, reverse=True))
    for entity, tokens in ENTITY_TRIGGERS
]


class EntityDetector:
    """Identifies which resume entities the user's *question* is asking about.

    Works on the *normalized* question (output of QuestionNormalizer).

    Usage::

        detector = EntityDetector()
        entities = detector.detect("name and age")
        # → [QuestionEntity.NAME, QuestionEntity.AGE]
    """

    def detect(self, normalized_question: str) -> List[QuestionEntity]:
        """Detect ordered list of question entities in the normalized question.

        Detection is positional — entities are returned in the order they
        appear in the question, enabling natural multi-entity resolution.

        Args:
            normalized_question: Output of QuestionNormalizer.normalize().

        Returns:
            Ordered list of unique QuestionEntity members detected.
            Returns empty list if no resume entities found.
        """
        if not normalized_question:
            return []

        q = normalized_question.strip().lower()
        found: List[Tuple[int, QuestionEntity]] = []  # (position, entity)
        seen_entities: set = set()

        for entity, tokens in _SORTED_TRIGGERS:
            if entity in seen_entities:
                continue
            for token in tokens:
                # Use word-boundary for single words, substring for phrases
                if " " in token:
                    # Multi-word: substring search
                    idx = q.find(token)
                    if idx != -1:
                        found.append((idx, entity))
                        seen_entities.add(entity)
                        break
                else:
                    # Single word: whole-word match
                    m = re.search(r"\b" + re.escape(token) + r"\b", q)
                    if m:
                        found.append((m.start(), entity))
                        seen_entities.add(entity)
                        break

        # Sort by position to preserve user's question order
        found.sort(key=lambda x: x[0])
        return [entity for _, entity in found]

    def has_entity(self, normalized_question: str, entity: QuestionEntity) -> bool:
        """Convenience method: check if a specific entity is present.

        Args:
            normalized_question: Output of QuestionNormalizer.normalize().
            entity: QuestionEntity to check for.

        Returns:
            True if entity is detected, False otherwise.
        """
        return entity in self.detect(normalized_question)

    def is_role_inference_query(self, normalized_question: str) -> bool:
        """Returns True if the question is asking about developer role suitability.

        Examples:
            "is he app developer" → True
            "can he work as backend developer" → True
            "what is his experience" → False
        """
        entities = self.detect(normalized_question)
        return QuestionEntity.ROLE in entities or QuestionEntity.SUITABILITY in entities
