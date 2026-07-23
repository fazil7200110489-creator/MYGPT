"""Recruiter Intent Classifier — Pre-classifies recruiter requests into 10 canonical intents.

Supported Intents:
1. CANDIDATE_SEARCH
2. CANDIDATE_RANKING
3. CANDIDATE_COMPARISON
4. CANDIDATE_EXPLANATION
5. CANDIDATE_PROFILE
6. CANDIDATE_FILTERING
7. CANDIDATE_SHORTLISTING
8. INTERVIEW_QUESTION_GENERATION
9. EXPORT
10. ANALYTICS
"""

import re
from enum import Enum
from typing import Dict, Any, List, Optional
from loguru import logger


class RecruiterIntent(str, Enum):
    CANDIDATE_SEARCH = "CANDIDATE_SEARCH"
    CANDIDATE_RANKING = "CANDIDATE_RANKING"
    CANDIDATE_COMPARISON = "CANDIDATE_COMPARISON"
    CANDIDATE_EXPLANATION = "CANDIDATE_EXPLANATION"
    CANDIDATE_PROFILE = "CANDIDATE_PROFILE"
    CANDIDATE_FILTERING = "CANDIDATE_FILTERING"
    CANDIDATE_SHORTLISTING = "CANDIDATE_SHORTLISTING"
    INTERVIEW_QUESTION_GENERATION = "INTERVIEW_QUESTION_GENERATION"
    EXPORT = "EXPORT"
    ANALYTICS = "ANALYTICS"


class RecruiterIntentClassifier:
    """Classifies recruiter natural language queries into canonical recruiter intents."""

    def __init__(self):
        self._intent_rules = [
            (RecruiterIntent.CANDIDATE_COMPARISON, [
                r'\bcompare\b', r'\bversus\b', r'\bvs\.?\b', r'\bbetter than\b',
                r'\bwho is better\b', r'\bcompare candidates\b', r'\bcomparison\b'
            ]),
            (RecruiterIntent.CANDIDATE_EXPLANATION, [
                r'\bwhy is\b', r'\bwhy candidate\b', r'\bexplain why\b', r'\bwhy ranked\b',
                r'\breason for\b', r'\bexplain recommendation\b', r'\bwhy first\b', r'\bwhy top\b'
            ]),
            (RecruiterIntent.INTERVIEW_QUESTION_GENERATION, [
                r'\binterview questions\b', r'\bgenerate interview\b', r'\bquestions for\b',
                r'\binterview question\b', r'\btechnical questions\b', r'\binterview script\b'
            ]),
            (RecruiterIntent.EXPORT, [
                r'\bexport\b', r'\bdownload\b', r'\bgenerate report\b', r'\bpdf\b',
                r'\bexcel\b', r'\bcsv\b', r'\bdownload shortlisted\b'
            ]),
            (RecruiterIntent.CANDIDATE_SHORTLISTING, [
                r'\bshortlist\b', r'\breject\b', r'\bhold\b', r'\bmark as interview\b',
                r'\bchange status\b', r'\bselect candidate\b', r'\bstage\b'
            ]),
            (RecruiterIntent.CANDIDATE_PROFILE, [
                r'\bcomplete profile\b', r'\bfull profile\b', r'\bshow profile\b',
                r'\bgive .* profile\b', r'\bdetails of\b', r'\bprojects of\b',
                r'\bcertifications of\b', r'\beducation of\b', r'\bwork history of\b'
            ]),
            (RecruiterIntent.CANDIDATE_SEARCH, [
                r'^(?:find|search|look for|get candidates|show candidates)\b'
            ]),
            (RecruiterIntent.CANDIDATE_FILTERING, [
                r'\bshow only\b', r'\bfilter by\b', r'\bfrom chennai\b', r'\bfrom bangalore\b',
                r'\bwith mba\b', r'\bwith bca\b', r'\bwith aws\b', r'\bwith docker\b',
                r'\bfreshers\b', r'\bexperienced candidates\b', r'\b5\+\s*years\b'
            ]),
            (RecruiterIntent.CANDIDATE_RANKING, [
                r'\brank\b', r'\btop\s*\d+\b', r'\bbest\b', r'\branked\b',
                r'\bsuitable for\b', r'\branking\b', r'\bscorecard\b'
            ]),
            (RecruiterIntent.ANALYTICS, [
                r'\banalytics\b', r'\bmetrics\b', r'\bpool summary\b', r'\bdistribution\b',
                r'\bstatistics\b', r'\bhow many candidates\b'
            ])
        ]

    def classify(self, query: str) -> RecruiterIntent:
        """Classify natural language query into RecruiterIntent."""
        q_lower = (query or "").lower().strip()

        for intent, patterns in self._intent_rules:
            for pat in patterns:
                if re.search(pat, q_lower):
                    logger.debug(f"RecruiterIntentClassifier: '{query}' -> {intent.value} (matched: {pat})")
                    return intent

        logger.debug(f"RecruiterIntentClassifier: '{query}' fallback -> CANDIDATE_SEARCH")
        return RecruiterIntent.CANDIDATE_SEARCH


# Singleton Instance
recruiter_intent_classifier = RecruiterIntentClassifier()
