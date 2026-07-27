"""Intent Classifier — Phase 3 of the Resume Intelligence Pipeline.

Classifies a *normalized* question into one or more canonical intent
strings.  This version is entirely data-driven: intent definitions live
in the ``INTENT_DEFINITIONS`` configuration table at the top of this
module.  To add a new intent, add one entry to that table — no control-
flow code changes are required.

Pipeline position:
    QuestionNormalizer
        ↓
    EntityDetector
        ↓
    IntentClassifier    ← THIS MODULE
        ↓
    KnowledgeRetriever
        ↓
    ...

Design principles:
- Single source of truth: ``INTENT_DEFINITIONS`` drives everything.
- No long if/else chains for keyword matching.
- EntityDetector findings are the primary signal; keyword fallback is
  secondary.
- Semantic embedding similarity is used as a last resort.
- For resume documents: *never* returns ``UNKNOWN_QUERY``.
"""

import os
import json
import re
from typing import Dict, List, Optional, Set, Tuple

from loguru import logger

from backend.app.services.reasoning.entity_detector import EntityDetector, QuestionEntity
from backend.app.services.reasoning.question_normalizer import QuestionNormalizer

RESUME_TOKENS = {
    "resume", "cv", "candidate", "applicant", "profile", "summary",
    "experience", "education", "skills", "projects", "certifications",
    "contact", "details", "overview", "qualification", "qualifications"
}

def _load_intent_aliases_from_json() -> Dict[str, List[str]]:
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    config_path = os.path.join(base_dir, "config", "intent_aliases.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                intents = data.get("intents", {})
                if intents:
                    logger.info("Loaded intent aliases dynamically from intent_aliases.json")
                    return intents
        except Exception as e:
            logger.warning(f"Failed to load intent_aliases.json: {e}")
    return {}


# ---------------------------------------------------------------------------
# Intent Definitions — add new intents here only
# ---------------------------------------------------------------------------
# Structure:
#   intent_name (str) → {
#       "entities": [QuestionEntity, ...]  – entity types that map to this intent
#       "keywords": [str, ...]             – normalized keyword triggers (fallback)
#   }
# ---------------------------------------------------------------------------

INTENT_DEFINITIONS: Dict[str, Dict] = {
    "CANDIDATE_NAME": {
        "entities": [QuestionEntity.NAME],
        "keywords": ["name"],
    },
    "FATHER_NAME": {
        "entities": [QuestionEntity.FATHER_NAME],
        "keywords": ["father name", "father"],
    },
    "MOTHER_NAME": {
        "entities": [QuestionEntity.MOTHER_NAME],
        "keywords": ["mother name", "mother"],
    },
    "PHONE": {
        "entities": [QuestionEntity.PHONE],
        "keywords": ["phone", "mobile", "cell", "telephone"],
    },
    "EMAIL": {
        "entities": [QuestionEntity.EMAIL],
        "keywords": ["email", "gmail", "e-mail", "mail"],
    },
    "CONTACT": {
        "entities": [QuestionEntity.CONTACT],
        "keywords": ["contact details", "contact info", "contact information"],
    },
    "ADDRESS": {
        "entities": [QuestionEntity.ADDRESS],
        "keywords": [
            "address", "location", "city", "residence", "place", "native", "native place",
            "hometown", "permanent location", "current location", "where is candidate from",
            "where is the candidate from", "residence address", "full address", "district", "state",
            "give me the address", "give me address", "where is he from", "where is she from", "based in"
        ],
    },
    "COMPANIES": {
        "entities": [QuestionEntity.COMPANIES],
        "keywords": [
            "companies", "company", "companies worked", "companies worked in",
            "worked in", "worked at", "employers", "organizations worked",
            "list of companies", "company names", "all companies"
        ],
    },
    "LINKEDIN": {
        "entities": [QuestionEntity.LINKEDIN],
        "keywords": ["linkedin", "linkedin profile"],
    },
    "GITHUB": {
        "entities": [QuestionEntity.GITHUB],
        "keywords": ["github", "github profile"],
    },
    "DOMAIN": {
        "entities": [QuestionEntity.DOMAIN],
        "keywords": ["domain", "industry", "field of work", "profession", "sector"],
    },
    "DESIGNATION": {
        "entities": [QuestionEntity.DESIGNATION],
        "keywords": ["designation", "job title", "position", "current role", "job role"],
    },
    "EXPERIENCE": {
        "entities": [QuestionEntity.WORK_EXPERIENCE],
        "keywords": [
            "experience", "experience of candidate", "work history", "employment",
            "career", "company", "worked", "employment history", "career history",
            "experienced"
        ],
    },
    "SKILLS": {
        "entities": [QuestionEntity.SKILLS, QuestionEntity.PROGRAMMING_LANGS],
        "keywords": [
            "skills", "technical skills", "professional skills", "core skills",
            "technologies", "frameworks", "tools", "libraries", "tech stack",
            "software", "expertise", "competencies", "programming language",
            "programming languages",
        ],
    },
    "ERP_PLATFORMS": {
        "entities": [QuestionEntity.SKILLS],
        "keywords": [
            "erp", "erp platforms", "erp systems", "erp software",
            "sap", "oracle", "tally", "workday", "epicor", "peoplesoft", "dynamics 365",
        ],
    },
    "AWARDS": {
        "entities": [QuestionEntity.CERTIFICATIONS],
        "keywords": ["awards", "achievements", "honors", "recognitions"],
    },
    "PROGRAMMING_LANGUAGES": {
        "entities": [QuestionEntity.PROGRAMMING_LANGS],
        "keywords": ["programming language", "programming languages", "coding language"],
    },
    "PROJECTS": {
        "entities": [QuestionEntity.PROJECTS],
        "keywords": ["projects", "project", "portfolio", "developed", "application"],
    },
    "CERTIFICATIONS": {
        "entities": [QuestionEntity.CERTIFICATIONS],
        "keywords": ["certifications", "certification", "certificate", "courses", "training"],
    },
    "EDUCATION": {
        "entities": [QuestionEntity.EDUCATION],
        "keywords": [
            "education", "degree", "college", "university",
            "school", "academic", "graduation", "qualification",
            "graduated", "graduate"
        ],
    },
    "HUMAN_LANGUAGES": {
        "entities": [QuestionEntity.LANGUAGES],
        "keywords": ["language", "languages", "speak", "spoken"],
    },
    "SUMMARY": {
        "entities": [QuestionEntity.SUMMARY, QuestionEntity.BASIC_PROFILE],
        "keywords": ["summary", "summarize", "overview", "brief", "synopsis", "profile"],
    },
    "BASIC_PROFILE": {
        "entities": [QuestionEntity.BASIC_PROFILE],
        "keywords": ["basic details", "basic profile", "basic info"],
    },
    "PROFILE_SUMMARY": {
        "entities": [QuestionEntity.SUMMARY],
        "keywords": ["profile summary", "tell me about this candidate"],
    },
    "CONTACT": {
        "entities": [QuestionEntity.CONTACT],
        "keywords": ["contact details", "contact info", "contact information"],
    },
    "GENDER": {
        "entities": [QuestionEntity.GENDER],
        "keywords": ["gender", "sex"],
    },
    "AGE": {
        "entities": [QuestionEntity.AGE],
        "keywords": ["age"],
    },
    "DATE_OF_BIRTH": {
        "entities": [QuestionEntity.DATE_OF_BIRTH],
        "keywords": ["date of birth", "dob", "birthday"],
    },
    "OBJECTIVE": {
        "entities": [QuestionEntity.OBJECTIVE],
        "keywords": ["objective", "career objective", "goal"],
    },
    "ACHIEVEMENTS": {
        "entities": [QuestionEntity.ACHIEVEMENTS],
        "keywords": ["achievement", "achievements", "award", "awards"],
    },
    "SALARY": {
        "entities": [QuestionEntity.SALARY],
        "keywords": ["salary", "ctc", "compensation"],
    },
    "NOTICE_PERIOD": {
        "entities": [QuestionEntity.NOTICE_PERIOD],
        "keywords": ["notice period", "notice"],
    },
    "MARITAL_STATUS": {
        "entities": [QuestionEntity.MARITAL_STATUS],
        "keywords": ["marital", "married"],
    },
    "ROLE_INFERENCE": {
        "entities": [QuestionEntity.ROLE, QuestionEntity.SUITABILITY],
        "keywords": [
            "suitable for", "fit for", "can he", "can she",
            "app developer", "backend developer", "frontend developer",
            "can work as", "suitable", "role match", "role recommendation",
        ],
    },
    "ROLE_COMPARE": {
        "entities": [],
        "keywords": ["vs", "versus", "compare", "better suited for", "more suitable", "between"],
    },
    "CAREER_TRANSITION": {
        "entities": [],
        "keywords": ["career transition", "career change", "previous career", "changed career", "career path", "transition from"],
    },
    "DOMAIN_EXPERIENCE": {
        "entities": [],
        "keywords": ["hr experience", "healthcare experience", "finance experience", "current domain experience",
                     "previous domain", "how many years in hr", "how many years in", "domain experience",
                     "years in current domain", "experience in hr"],
    },
    "TIMELINE": {
        "entities": [],
        "keywords": ["career timeline", "experience timeline", "employment history", "work timeline", "career journey", "chronological"],
    },
    "GRADUATION_YEAR": {
        "entities": [],
        "keywords": ["passed out year", "graduation year", "passing year", "year of passing",
                     "completed degree", "when did she graduate", "when did he graduate", "passed out", "passing out year"],
    },
    "CGPA": {
        "entities": [],
        "keywords": ["cgpa", "percentage", "marks", "gpa", "grades", "academic score", "what is cgpa", "what percentage"],
    },
    "CURRENT_COMPANY": {
        "entities": [],
        "keywords": ["current company", "current employer", "working at", "company name", "present company",
                     "where is she working", "where is he working", "which company"],
    },
    "SKILL_VERIFY": {
        "entities": [],
        "keywords": ["does she know", "does he know", "does the candidate know", "is she proficient in",
                     "is he proficient in", "can she use", "can he use", "knowledge of",
                     "does she have experience with"],
    },
    "AWARDS": {
        "entities": [],
        "keywords": ["awards", "award", "award received", "honors", "recognitions", "award name",
                     "prizes", "accolades", "recognition", "employee of the month", "achievement award"],
    },
    # Non-resume intents
    "INVOICE_TOTAL": {
        "entities": [],
        "keywords": ["total amount", "grand total", "invoice total", "amount to pay"],
    },
    "COUNT": {
        "entities": [],
        "keywords": ["count", "how many", "number of"],
    },
    "AVERAGE": {
        "entities": [],
        "keywords": ["average", "mean", "avg"],
    },
    "HIGHEST": {
        "entities": [],
        "keywords": ["highest", "maximum", "max"],
    },
    "LOWEST": {
        "entities": [],
        "keywords": ["lowest", "minimum", "min"],
    },
}

# ---------------------------------------------------------------------------
# Intent group expansions: a single trigger → multiple intents
# ---------------------------------------------------------------------------
INTENT_GROUPS: Dict[str, List[str]] = {
    "contact details":      ["CONTACT"],
    "contact info":         ["CONTACT"],
    "contact":              ["CONTACT"],
    "basic details":        ["BASIC_PROFILE"],
    "basic profile":        ["BASIC_PROFILE"],
    "academic details":     ["EDUCATION", "CERTIFICATIONS"],
    "technical profile":    ["SKILLS", "PROGRAMMING_LANGUAGES", "PROJECTS"],
    "career summary":       ["CAREER_TRANSITION", "DOMAIN_EXPERIENCE", "TIMELINE"],
    "full summary":         ["SUMMARY"],
}

# Resume-domain tokens (used to confirm a query is resume-related before
# falling back to GENERAL instead of UNKNOWN_QUERY)
RESUME_TOKENS: Set[str] = {
    "skill", "skills", "experience", "education", "project", "projects",
    "certification", "certifications", "certificate", "name", "phone",
    "mobile", "email", "address", "language", "languages", "designation",
    "summary", "summarize", "summarise", "overview", "brief", "profile",
    "objective", "degree", "college", "university", "work", "employment",
    "company", "linkedin", "github", "contact", "location", "role", "career",
    "qualification", "qualifications", "academic", "employer", "training",
    "course", "resume", "cv", "candidate", "applicant", "technologies",
    "technology", "frameworks", "tools", "developer", "engineer", "python",
    "java", "react", "angular", "docker", "aws", "age", "gender", "salary",
    "notice", "achievement", "achievements", "exp",
}


class IntentClassifier:
    """Classifies normalized questions into canonical intent strings.

    All classification logic is driven by ``INTENT_DEFINITIONS``.
    The classifier uses a three-tier strategy:
        1. Group intent expansion (multi-intent triggers).
        2. EntityDetector findings → intent mapping.
        3. Keyword substring fallback.
        4. Semantic embedding similarity (last resort).

    For resume documents it never returns ``UNKNOWN_QUERY`` — it falls
    back to ``GENERAL`` which the reasoning service routes to the
    ResumeReasoner with a role-inference pass.
    """

    # Sentinel values
    UNKNOWN_QUERY_INTENT: str = "UNKNOWN_QUERY"
    GENERAL_INTENT: str = "GENERAL"

    def __init__(self) -> None:
        self._normalizer = QuestionNormalizer()
        self._detector = EntityDetector()
        aliases = _load_intent_aliases_from_json()
        for intent_name, keywords in aliases.items():
            if intent_name in INTENT_DEFINITIONS:
                existing_kw = set(INTENT_DEFINITIONS[intent_name].get("keywords", []))
                for kw in keywords:
                    if kw not in existing_kw:
                        INTENT_DEFINITIONS[intent_name]["keywords"].append(kw)
        self.intent_embeddings: Dict[str, List[List[float]]] = {}
        self._precompute_embeddings()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify_multi(self, question: str, doc_type: str = "Generic") -> List[str]:
        """Classify a question into one or more ordered canonical intents.

        Args:
            question: Raw user question (will be normalized internally).
            doc_type: Document type from knowledge store (e.g. "Resume").

        Returns:
            Ordered list of unique intent strings.  Never empty.
        """
        normalized = self._normalizer.normalize(question)
        logger.debug(f"IntentClassifier normalized: '{question}' → '{normalized}'")

        # --- Tier 1: Group intent expansion ---
        group_intents = self._match_group_intents(normalized)
        if group_intents:
            return group_intents

        # --- Tier 2: EntityDetector → intent mapping ---
        entity_intents = self._entities_to_intents(normalized)

        # --- Tier 3: Keyword fallback ---
        kw_intents = self._keyword_intents(normalized)

        # Merge, preserving order
        merged = self._merge_unique(entity_intents, kw_intents)

        # Disambiguate overlapping intents
        if "CONTACT" in merged and any(i in merged for i in ["PHONE", "EMAIL", "ADDRESS"]):
            merged = [i for i in merged if i != "CONTACT"]

        if "PROGRAMMING_LANGUAGES" in merged and ("programming" in normalized or "coding" in normalized):
            merged = [i for i in merged if i != "HUMAN_LANGUAGES"]

        if "HUMAN_LANGUAGES" in merged and any(w in normalized for w in ["speak", "spoken", "mother tongue"]):
            merged = [i for i in merged if i not in ("PROGRAMMING_LANGUAGES", "SKILLS")]

        if "CERTIFICATIONS" in merged and any(w in normalized for w in ["certification", "certifications", "certificate"]):
            merged = [i for i in merged if i != "AWARDS"]

        # If explicit skill-category keywords present (frameworks/libraries), strip SKILL_VERIFY
        if "SKILLS" in merged and "SKILL_VERIFY" in merged:
            if any(w in normalized for w in ["framework", "library", "libraries", "tech stack", "tools", "technologies"]):
                merged = [i for i in merged if i != "SKILL_VERIFY"]
            else:
                # Otherwise SKILL_VERIFY takes priority for "does she know X" type queries
                merged = [i for i in merged if i != "SKILLS"]

        if merged:
            return merged

        # --- Tier 4: Semantic embedding similarity ---
        semantic = self._semantic_classify(question)
        if semantic and semantic not in (self.GENERAL_INTENT, ""):
            return [semantic]

        # --- Fallback ---
        return self._fallback(normalized, doc_type)

    def classify(self, question: str) -> str:
        """Single-intent convenience wrapper (backward compatible).

        Args:
            question: Raw question string.

        Returns:
            Single intent string.
        """
        intents = self.classify_multi(question)
        return intents[0] if intents else self.GENERAL_INTENT

    def _preprocess_query(self, question: str) -> str:
        """Backward-compatible helper method delegating to QuestionNormalizer."""
        return self._normalizer.normalize(question)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _match_group_intents(self, normalized: str) -> List[str]:
        """Checks if the normalized query matches any group trigger phrase."""
        results: List[str] = []
        for phrase, intent_list in sorted(INTENT_GROUPS.items(), key=lambda x: len(x[0]), reverse=True):
            if phrase in ["contact", "contact details", "contact info", "contact information"]:
                if any(re.search(r"\b" + t + r"\b", normalized) for t in ["phone", "email", "address"]):
                    continue
            if phrase in normalized:
                for intent in intent_list:
                    if intent not in results:
                        results.append(intent)
        return results

    def _entities_to_intents(self, normalized: str) -> List[str]:
        """Maps EntityDetector findings to canonical intents."""
        detected_entities = self._detector.detect(normalized)
        if not detected_entities:
            return []

        result: List[str] = []
        seen: Set[str] = set()

        for entity in detected_entities:
            for intent_name, defn in INTENT_DEFINITIONS.items():
                if entity in defn["entities"] and intent_name not in seen:
                    result.append(intent_name)
                    seen.add(intent_name)
                    break

        return result

    def _keyword_intents(self, normalized: str) -> List[str]:
        """Keyword substring fallback classifier."""
        result: List[str] = []
        seen: Set[str] = set()

        for intent_name, defn in INTENT_DEFINITIONS.items():
            if intent_name in seen:
                continue
            for kw in sorted(defn["keywords"], key=len, reverse=True):
                if " " in kw:
                    if kw in normalized:
                        result.append(intent_name)
                        seen.add(intent_name)
                        break
                else:
                    if re.search(r"\b" + re.escape(kw) + r"\b", normalized):
                        result.append(intent_name)
                        seen.add(intent_name)
                        break

        return result

    @staticmethod
    def _merge_unique(*lists: List[str]) -> List[str]:
        """Merge multiple ordered lists, preserving first-occurrence order."""
        seen: Set[str] = set()
        result: List[str] = []
        for lst in lists:
            for item in lst:
                if item not in seen:
                    seen.add(item)
                    result.append(item)
        return result

    def _fallback(self, normalized: str, doc_type: str) -> List[str]:
        """Final fallback: returns UNKNOWN_QUERY_INTENT if question lacks domain tokens."""
        tokens = set(re.findall(r"\b\w+\b", normalized.lower()))
        has_resume_token = bool(tokens & RESUME_TOKENS)

        if has_resume_token or any(k in normalized.lower() for k in ["summary", "profile", "overview", "resume", "cv", "details"]):
            return [self.GENERAL_INTENT]

        return [self.UNKNOWN_QUERY_INTENT]

    def _precompute_embeddings(self) -> None:
        """Pre-computes and caches embeddings for semantic intent classification."""
        try:
            from backend.app.services.embedding_service import embedding_service

            seed_phrases: List[str] = []
            phrase_to_intent: Dict[str, str] = {}

            for intent_name, defn in INTENT_DEFINITIONS.items():
                for kw in defn["keywords"]:
                    seed_phrases.append(kw)
                    phrase_to_intent[kw] = intent_name

            if not seed_phrases:
                return

            logger.info("Pre-computing semantic intent classifier embeddings...")
            embeddings = embedding_service.get_embeddings(seed_phrases)

            for phrase, emb in zip(seed_phrases, embeddings):
                intent = phrase_to_intent[phrase]
                if intent not in self.intent_embeddings:
                    self.intent_embeddings[intent] = []
                self.intent_embeddings[intent].append(emb)

            logger.info("Semantic intent embeddings loaded successfully.")
        except Exception as exc:
            logger.warning(f"Failed to pre-compute intent embeddings (using keyword fallback): {exc}")

    def _semantic_classify(self, question: str) -> Optional[str]:
        """Cosine-similarity semantic classification over intent seed embeddings."""
        if not self.intent_embeddings:
            return None

        # Skip semantic matching for single short words that have zero keyword match
        q_words = question.strip().split()
        if len(q_words) == 1 and len(q_words[0]) < 6:
            return None

        try:
            from backend.app.services.embedding_service import embedding_service

            q_emb = embedding_service.get_embeddings([question])[0]
            best_intent: Optional[str] = None
            best_score = -1.0

            for intent, embeddings in self.intent_embeddings.items():
                for emb in embeddings:
                    dot = sum(a * b for a, b in zip(q_emb, emb))
                    q_norm = sum(a * a for a in q_emb) ** 0.5
                    e_norm = sum(b * b for b in emb) ** 0.5
                    score = dot / (q_norm * e_norm + 1e-9)
                    if score > best_score:
                        best_score = score
                        best_intent = intent

            if best_score > 0.90:
                return best_intent
        except Exception as exc:
            logger.warning(f"Semantic similarity classification failed: {exc}")

        return None
