"""Question Normalizer — Phase 1 of the Resume Intelligence Pipeline.

Converts raw user questions into clean, canonical forms before intent
classification. This stage is document-type agnostic; all transformations
are configuration-driven so new abbreviations or filler phrases can be
added without touching control-flow logic.

Pipeline position:
    Raw Question
        ↓
    QuestionNormalizer   ← THIS MODULE
        ↓
    EntityDetector
        ↓
    IntentClassifier
        ↓
    ...
"""

import re
from typing import Dict, List, Tuple


# ---------------------------------------------------------------------------
# Configuration tables (extend here — no code changes needed elsewhere)
# ---------------------------------------------------------------------------

# 1. Abbreviation expansion — short-form → full canonical phrase
#    Ordered by length (longest first) to prevent partial replacements.
ABBREVIATION_MAP: Dict[str, str] = {
    # Experience variants
    "exp":              "experience",
    "exps":             "experience",
    "wrk hist":         "work history",
    "wrk history":      "work history",
    "work hist":        "work history",
    "prof exp":         "professional experience",
    "career hist":      "career history",
    "job hist":         "job history",
    # Skills / Technologies
    "tech skills":      "technical skills",
    "tech stack":       "technical skills",
    "tech":             "technical skills",
    "skls":             "skills",
    "skll":             "skills",
    # Education
    "edu":              "education",
    "acad":             "academic background",
    "qual":             "qualifications",
    # Certifications
    "certs":            "certifications",
    "cert":             "certifications",
    # Projects
    "proj":             "projects",
    "projs":            "projects",
    "portfolio":        "projects",
    # Contact
    "mob":              "mobile",
    "ph":               "phone",
    "ph no":            "phone number",
    "mob no":           "phone number",
    "phone no":         "phone number",
    "contact no":       "phone number",
    "email id":         "email",
    "mail id":          "email",
    "e mail":           "email",
    # Summary
    "smry":             "summary",
    "ovrvw":            "overview",
    # Background
    "bg":               "background",
    # Programming
    "prog langs":       "programming languages",
    "prog lang":        "programming language",
    "coding lang":      "programming language",
}

# 2. Phrase normalizations — multi-word equivalents → canonical word
#    Used after abbreviation expansion.
PHRASE_MAP: Dict[str, str] = {
    # Experience phrases
    "professional experience":      "experience",
    "work experience":              "experience",
    "working experience":           "experience",
    "employment history":           "experience",
    "career history":               "experience",
    "career details":               "experience",
    "job history":                  "experience",
    "work history":                 "experience",
    "industry experience":          "experience",
    "professional background":      "experience",
    "years of experience":          "experience",
    # Skills phrases
    "technical skills":             "skills",
    "technical expertise":          "skills",
    "technologies used":            "skills",
    "technology stack":             "skills",
    "software skills":              "skills",
    "what can he do":               "skills",
    "what does he know":            "skills",
    "what she knows":               "skills",
    "what they know":               "skills",
    "what can she do":              "skills",
    # Education phrases
    "academic background":          "education",
    "academic qualification":       "education",
    "educational background":       "education",
    "educational qualification":    "education",
    "schooling":                    "education",
    # Contact phrases
    "contact number":               "phone",
    "mobile number":                "phone",
    "cell number":                  "phone",
    "phone number":                 "phone",
    "contact details":              "contact",
    "contact info":                 "contact",
    "contact information":          "contact",
    # Name phrases
    "full name":                    "name",
    "candidate name":               "name",
    "applicant name":               "name",
    "person name":                  "name",
    # Role / Designation
    "job role":                     "designation",
    "job title":                    "designation",
    "job position":                 "designation",
    "current role":                 "designation",
    "current position":             "designation",
    "position held":                "designation",
    # Summary
    "profile summary":              "summary",
    "candidate profile":            "summary",
    "overall profile":              "summary",
    "give me an overview":          "summary",
    # LinkedIn
    "linked in":                    "linkedin",
    "linked inn":                   "linkedin",
    "linkedinn":                    "linkedin",
}

# 3. Spell corrections — resume-domain typos only (conservative)
SPELL_MAP: Dict[str, str] = {
    "exprience":        "experience",
    "expereince":       "experience",
    "experiance":       "experience",
    "experiece":        "experience",
    "ksills":           "skills",
    "skils":            "skills",
    "skilles":          "skills",
    "eductaion":        "education",
    "educaton":         "education",
    "certfication":     "certification",
    "cerification":     "certification",
    "certifcation":     "certification",
    "certificaton":     "certification",
    "pthon":            "python",
    "phyton":           "python",
    "adress":           "address",
    "addresss":         "address",
    "desgnation":       "designation",
    "deisgnation":      "designation",
    "proects":          "projects",
    "porjects":         "projects",
    "summry":           "summary",
    "sumary":           "summary",
    "qualifcation":     "qualification",
    "qualifiation":     "qualification",
}

# 4. Filler phrases to strip — purely conversational noise with no semantic value.
#    Ordered longest-first to prevent partial stripping.
FILLER_PHRASES: List[str] = [
    "tell me more about",
    "can you please show me",
    "can you please tell me",
    "can you please give me",
    "can you show me",
    "can you tell me",
    "can you give me",
    "please tell me about",
    "please show me",
    "please give me",
    "tell me about",
    "show me about",
    "give me about",
    "what are the",
    "what is the",
    "what does the",
    "what did the",
    "what is his",
    "what is her",
    "what is their",
    "what are his",
    "what are her",
    "what are their",
    "of the candidate",
    "of this candidate",
    "of the applicant",
    "of this applicant",
    "this candidate has",
    "the candidate has",
    "this candidate",
    "the candidate",
    "of candidate",
    "for candidate",
    "about the",
    "about this",
    "for the",
    "for this",
    "of the",
    "of this",
    "show me",
    "tell me",
    "give me",
    "show the",
    "list the",
    "list all",
]

# Pre-sort filler phrases by length descending (longest first) for greedy match
_FILLER_SORTED: List[str] = sorted(FILLER_PHRASES, key=len, reverse=True)

# Pre-sort abbreviation and phrase maps by key length descending
_ABB_SORTED: List[Tuple[str, str]] = sorted(ABBREVIATION_MAP.items(), key=lambda x: len(x[0]), reverse=True)
_PHRASE_SORTED: List[Tuple[str, str]] = sorted(PHRASE_MAP.items(), key=lambda x: len(x[0]), reverse=True)


class QuestionNormalizer:
    """Converts raw user questions into clean, canonical forms.

    All transformations are configuration-driven; to extend behavior, add
    entries to the module-level dictionaries — no code changes required.

    Usage::

        normalizer = QuestionNormalizer()
        clean = normalizer.normalize("tell me about exprience")
        # → "experience"
    """

    def normalize(self, question: str) -> str:
        """Run the full normalization pipeline on a raw question.

        Steps (in order):
            1. Lowercase + strip leading/trailing whitespace.
            2. Remove punctuation (preserve apostrophes and hyphens inside words).
            3. Normalize internal whitespace to single spaces.
            4. Apply word-level spell correction.
            5. Apply filler-phrase stripping.
            6. Apply abbreviation expansion.
            7. Apply phrase normalization.
            8. Final whitespace cleanup.

        Args:
            question: Raw question string from the user.

        Returns:
            Normalized, canonical question string suitable for intent
            classification and entity detection.
        """
        if not question or not question.strip():
            return ""

        q = question.strip().lower()

        # Step 2: Remove punctuation except apostrophes/hyphens inside words
        # This keeps "c++" intact and removes trailing "?"
        q = re.sub(r"[^\w\s+#'-]", " ", q)
        # Collapse + signs used as conjunctions (e.g. "name + age" → "name age")
        q = re.sub(r"\s*\+\s*", " ", q)

        # Step 3: Normalize whitespace
        q = re.sub(r"\s+", " ", q).strip()

        # Step 4: Word-level spell correction
        q = self._apply_spell_correction(q)

        # Step 5: Filler phrase stripping
        q = self._strip_fillers(q)

        # Step 6: Abbreviation expansion
        q = self._apply_abbreviations(q)

        # Step 7: Phrase normalization
        q = self._apply_phrases(q)

        # Step 8: Final cleanup
        q = re.sub(r"\s+", " ", q).strip()

        return q

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _apply_spell_correction(self, q: str) -> str:
        """Corrects known resume-domain typos at word level."""
        words = q.split()
        corrected = []
        for word in words:
            corrected.append(SPELL_MAP.get(word, word))
        return " ".join(corrected)

    def _strip_fillers(self, q: str) -> str:
        """Removes conversational filler phrases (longest-first greedy)."""
        for filler in _FILLER_SORTED:
            if q.startswith(filler):
                q = q[len(filler):].strip()
                # Only strip one filler prefix per call to avoid over-stripping
                break
            # Also strip when filler appears mid-sentence and leaves meaningful text
            if q == filler:
                return ""
        return q

    def _apply_abbreviations(self, q: str) -> str:
        """Expands abbreviations using whole-word matching (longest-first)."""
        for abbr, expansion in _ABB_SORTED:
            pattern = r"\b" + re.escape(abbr) + r"\b"
            q = re.sub(pattern, expansion, q)
        return q

    def _apply_phrases(self, q: str) -> str:
        """Normalizes multi-word equivalents to canonical single terms (longest-first)."""
        for phrase, canonical in _PHRASE_SORTED:
            if phrase in q:
                q = q.replace(phrase, canonical)
        return q
