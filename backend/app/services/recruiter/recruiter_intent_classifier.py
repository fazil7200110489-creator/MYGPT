"""Recruiter / Multi-Resume Intent Classifier — Canonical Intent Classification Engine.
"""

import re
from enum import Enum
from typing import Dict, Any, List, Optional
from loguru import logger


class RecruiterIntent(str, Enum):
    CONTACT_EXTRACTION = "CONTACT_EXTRACTION"
    ADDRESS_EXTRACTION = "ADDRESS_EXTRACTION"
    EDUCATION_EXTRACTION = "EDUCATION_EXTRACTION"
    EXPERIENCE_EXTRACTION = "EXPERIENCE_EXTRACTION"
    SKILL_SEARCH = "SKILL_SEARCH"
    PROJECT_EXTRACTION = "PROJECT_EXTRACTION"
    BASIC_DETAILS = "BASIC_DETAILS"
    CANDIDATE_DETAILS = "CANDIDATE_DETAILS"
    DOMAIN_RECOMMENDATION = "DOMAIN_RECOMMENDATION"
    CANDIDATE_LIST = "CANDIDATE_LIST"
    CANDIDATE_SUMMARY = "CANDIDATE_SUMMARY"
    CANDIDATE_COMPARISON = "CANDIDATE_COMPARISON"
    CANDIDATE_RANKING = "CANDIDATE_RANKING"
    ROLE_RECOMMENDATION = "ROLE_RECOMMENDATION"
    CANDIDATE_SEARCH = "CANDIDATE_SEARCH"
    CANDIDATE_PROFILE = "CANDIDATE_PROFILE"
    CANDIDATE_EXPLANATION = "CANDIDATE_EXPLANATION"
    CANDIDATE_FILTERING = "CANDIDATE_FILTERING"
    CANDIDATE_SHORTLISTING = "CANDIDATE_SHORTLISTING"
    INTERVIEW_QUESTION_GENERATION = "INTERVIEW_QUESTION_GENERATION"
    EXPORT = "EXPORT"
    ANALYTICS = "ANALYTICS"
    GENERAL_QA = "GENERAL_QA"


class RecruiterIntentClassifier:
    """Classifies user queries into specific natural language intents with strict keyword boundary matching."""

    def __init__(self):
        self._intent_rules = [
            # 1. Candidate Search (High Priority for Search / Find queries)
            (RecruiterIntent.CANDIDATE_SEARCH, [
                r'\bfind\b', r'\bsearch\b', r'\bsearch candidates\b', r'\bfind candidates\b', r'\blook for\b'
            ]),

            # 2. Candidate Profile / Details (Give me details, Show profile, Tell me about)
            (RecruiterIntent.CANDIDATE_PROFILE, [
                r'\bcomplete profile\b', r'\bfull profile\b', r'\bshow candidate profile\b', r'\bcandidate profile\b',
                r'\'s complete profile\b', r'\'s profile\b', r'\'s details\b', r'\bprofile of\b', r'\bdetails of\b',
                r'\bgive me\s+[a-zA-Z0-9_\s]+\s+details\b', r'\bgive me only\b', r'\bshow\s+[a-zA-Z0-9_\s]+\s+profile\b',
                r'\btell me about\b', r'\bselected candidate\b', r'\bgive me the selected candidate\b'
            ]),
            (RecruiterIntent.CANDIDATE_DETAILS, [
                r'\bdetails of\b', r'\bprofile of\b', r'\bshow profile\b', r'\bgive me details\b'
            ]),

            # 3. Domain Recommendation Engine
            (RecruiterIntent.DOMAIN_RECOMMENDATION, [
                r'\bwhich domain do these resumes fit\b', r'\bwhich domain do these candidates fit\b',
                r'\bwhich domain\b', r'\bwhat domain\b', r'\bdomain recommendation\b', r'\bdomain fit\b',
                r'\bdomains fit\b', r'\bbest domain\b'
            ]),

            # 4. Contact / Address / Basic Details / Candidate List Extraction
            (RecruiterIntent.BASIC_DETAILS, [
                r'\bbasic details\b', r'\bgive me the basic details\b', r'\bbasic info\b', r'\bbasic information\b',
                r'\bkey details\b', r'\bquick info\b'
            ]),
            (RecruiterIntent.CANDIDATE_LIST, [
                r'\bnames of the candidates\b', r'\bnames of candidates\b', r'\blist all candidates\b', r'\blist candidates\b',
                r'\blist resumes\b', r'\blist all resumes\b', r'\bshow resumes\b',
                r'\bwho are the uploaded candidates\b', r'\buploaded candidates\b', r'\bcandidate list\b', r'\bshow candidates\b'
            ]),
            (RecruiterIntent.CONTACT_EXTRACTION, [
                r'\bphone\b', r'\bphone number\b', r'\bphone numbers\b', r'\bmobile\b', r'\bmobile number\b', r'\bmobile numbers\b',
                r'\bemail\b', r'\bemails\b', r'\bcontact\b', r'\bcontact details\b', r'\bcontact information\b', r'\bhow to reach\b',
                r'\bphone,\s*email,\s*address\b', r'\bphone\s+email\s+address\b',
                r'\bgive me the same for\b', r'\bsame for\b', r'\'s contact details\b', r'\'s contact\b'
            ]),
            (RecruiterIntent.CANDIDATE_FILTERING, [
                r'\bshow only candidates\b', r'\bonly candidates\b', r'\bfilter candidates\b', r'\bshow candidates with\b'
            ]),
            (RecruiterIntent.ADDRESS_EXTRACTION, [
                r'^address$', r'^location$', r'\baddress\b', r'\baddresses\b', r'\blocation\b', r'\bwhere (?:does|do|is)\b', r'\blive\b', r'\bliving\b',
                r'\bis\s+[a-zA-Z0-9_\s]+\s+from\b', r'\bwhere is he from\b', r'\bwhere is she from\b', r'\blocation of\b', r'\bwhere is\b', r'\bbased in\b',
                r'\bgive me the address\b', r'\bgive me address\b', r'\baddress of\b'
            ]),




            # 2. Role Recommendation
            (RecruiterIntent.ROLE_RECOMMENDATION, [
                r'^frontend developer$', r'^backend developer$', r'^full stack developer$', r'^software engineer$', r'^data analyst$',
                r'\bwhich role do these resumes fit\b', r'\bwhich role do these candidates fit\b',
                r'\bwhat roles are these candidates suitable for\b', r'\bwhat roles are these resumes suitable for\b',
                r'\brecommend suitable roles\b', r'\bsuitable roles\b', r'\bbest suited roles\b',
                r'\bwhich (?:job|role|job role) fits\b', r'\bwhich (?:job|role) is suitable\b',
                r'\bwhat (?:job|role) fits\b', r'\bwhat (?:job|role) is suitable\b',
                r'\brole recommendation\b', r'\brecommend (?:job|role|job role)\b',
                r'\bwhich role she fit for\b', r'\bwhich role he fit for\b',
                r'\bwhat can\s+[a-zA-Z0-9_\s]+\s+do\b'
            ]),

            # 3. Skills & Technical Extraction
            (RecruiterIntent.SKILL_SEARCH, [
                r'^rest api$', r'^docker$', r'^react$', r'^angular$', r'^python$', r'^java$', r'^aws$', r'^technical skills$', r'^skills$',
                r'\bgive me the skills\b', r'\bshow skills\b', r'\bskills\b', r'\bskill list\b',
                r'\bskills of\b', r'\'s skills\b', r'\bshow\s+[a-zA-Z0-9_\s]+\s+skills\b',
                r'\bwho knows\b', r'\bwho knows\s+[a-zA-Z0-9\+\#\.\-\s]{2,30}\b',
                r'\bwho has\s+[a-zA-Z0-9\+\#\.\-\s]{2,30}\b', r'\bwhich candidate has\b', r'\bcandidates with\b',
                r'\bknows aws\b', r'\bknows react\b', r'\bknows python\b', r'\bhas python\b', r'\bhas aws\b', r'\bhas react\b',
                r'\bwith react\b', r'\bwith aws\b', r'\bwith python\b', r'\bskilled in\b',
                r'\b(?:python|react|aws|java|docker|node|sql|fastapi|django|kubernetes|gcp|azure|html|css|javascript|typescript|c\+\+|c\#|php|git|tailwind|redux|api)\s+(?:experience|integration|skills)?\b'
            ]),

            # 4. Education & Projects Extraction
            (RecruiterIntent.EDUCATION_EXTRACTION, [
                r'\beducation\b', r'\bshow education\b', r'\bdegree\b', r'\bcollege\b', r'\buniversity\b', r'\bqualification\b',
                r'\beducational qualification\b', r'\bqualifications\b', r'\bwhat degree\b'
            ]),
            (RecruiterIntent.PROJECT_EXTRACTION, [
                r'\bprojects\b', r'\bshow projects\b', r'\bgive me projects\b', r'\bproject history\b', r'\bkey projects\b',
                r'\bwhich projects\b', r'\bworked on\b', r'\bprojects of\b'
            ]),

            # 5. Experience Comparison / Extraction
            (RecruiterIntent.EXPERIENCE_EXTRACTION, [
                r'^experience$', r'^work experience$', r'^career history$', r'^employment$',
                r'\bwho has better experience\b', r'\bwho has more frontend experience\b', r'\bwho has more backend experience\b',
                r'\bwho has more experience\b', r'\bwho has the most experience\b', r'\bmost experience\b',
                r'\bhighest experience\b', r'\byears of experience\b', r'\bexperience level\b', r'\bcompare experience\b',
                r'\bshow work experience\b', r'\bwork experience\b', r'\btotal experience\b', r'\bhis experience\b', r'\bher experience\b',
                r'\bwhat is\s+[a-zA-Z0-9_\'\s]+\s+experience\b', r'\bexperience of\b'
            ]),

            # 8. Candidate Summaries (Normalized SUMMARY_ALL Intent)
            (RecruiterIntent.CANDIDATE_SUMMARY, [
                r'^summarize all uploaded resumes$', r'^summarize all resumes$', r'^summarize uploaded resumes$',
                r'^summarize candidates$', r'^candidate summary$', r'^resume summary$', r'^overview of all candidates$',
                r'^overview of candidates$', r'^all resumes summary$', r'\bsummarize all uploaded resumes\b',
                r'\bsummarize all resumes\b', r'\bsummarize uploaded resumes\b', r'\bsummarize candidates\b',
                r'\bsummarise candidates\b', r'\bsummarise all resumes\b', r'\bsummarise uploaded resumes\b',
                r'\bsummarize\b', r'\bsummarise\b', r'\bsummary of\b', r'\btell me about\b', r'\boverview of\b',
                r'\bprofile summary\b', r'\bcandidate summary\b', r'\bresume summary\b'
            ]),

            # 9. Explicit Candidate Comparison (Requires explicit comparison keywords)
            (RecruiterIntent.CANDIDATE_COMPARISON, [
                r'\bcompare\b', r'\bcompare\s+(?:all|candidates|resumes|them|profiles)\b', r'\bcompare\s+candidate\b', r'\bcompare\s+resume\b',
                r'\bversus\b', r'\bvs\.?\b', r'\bbetter than\b', r'\bwho is better\b', r'\bcomparison of\b'
            ]),

            # 10. Candidate Profile / Selected Candidate Details
            (RecruiterIntent.CANDIDATE_PROFILE, [
                r'\bcomplete profile\b', r'\bfull profile\b', r'\bshow candidate profile\b', r'\bcandidate profile\b', r'\bshow profile\b', r'\bdetails of\b',
                r'\bgive me the selected candidate\b', r'\bselected candidate\b'
            ]),

            # 11. Candidate Ranking / Best Candidate Evaluation
            (RecruiterIntent.CANDIDATE_RANKING, [
                r'\brank candidates\b', r'\brank candidates for\b', r'\brank for\b',
                r'\bevaluate candidates\b', r'\bevaluate candidates for\b', r'\brank them\b', r'\brank\b',
                r'\bwhich one is best for\b', r'\bwhich candidate is best for\b', r'\bbest for\b', r'\bbest candidate for\b',
                r'\bwho is the best developer\b', r'\bwho is the best engineer\b', r'\bwho is the best coder\b', r'\bwho is the best programmer\b',
                r'\bwho is the best candidate\b', r'\bwho is the best\b', r'\bwho is the top candidate\b', r'\bbest candidate\b'
            ]),

            # 11. Secondary Operations
            (RecruiterIntent.CANDIDATE_EXPLANATION, [
                r'\bwhy is candidate\b', r'\bwhy is\b', r'\bexplain why\b', r'\bwhy ranked\b', r'\breason for\b'
            ]),
            (RecruiterIntent.INTERVIEW_QUESTION_GENERATION, [
                r'\binterview questions\b', r'\bgenerate interview\b', r'\bquestions for\b'
            ]),
            (RecruiterIntent.EXPORT, [
                r'\bexport\b', r'\bdownload\b', r'\bgenerate report\b', r'\bcsv\b', r'\bpdf\b'
            ]),
            (RecruiterIntent.CANDIDATE_SHORTLISTING, [
                r'\bshortlist\b', r'\breject\b', r'\bhold\b'
            ]),
            (RecruiterIntent.ANALYTICS, [
                r'\banalytics\b', r'\bmetrics\b', r'\bpool summary\b'
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

        logger.debug(f"RecruiterIntentClassifier: '{query}' fallback -> GENERAL_QA")
        return RecruiterIntent.GENERAL_QA


# Singleton Instance
recruiter_intent_classifier = RecruiterIntentClassifier()
