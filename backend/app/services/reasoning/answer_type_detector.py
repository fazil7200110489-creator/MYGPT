"""Answer Type Detector for routing query intents to target presentation formatters.

Ensures every intent uses its dedicated presentation format instead of a generic executive summary.
"""

from enum import Enum
from typing import Dict, Any, Optional
from loguru import logger


class AnswerType(str, Enum):
    CONTACT = "CONTACT"
    EDUCATION = "EDUCATION"
    SKILLS_BULLET = "SKILLS_BULLET"
    SKILL_VERIFICATION = "SKILL_VERIFICATION"
    EXPERIENCE_TIMELINE = "EXPERIENCE_TIMELINE"
    ROLE_MATCH_SCORECARD = "ROLE_MATCH_SCORECARD"
    RECRUITER_SUMMARY = "RECRUITER_SUMMARY"
    AWARDS = "AWARDS"
    PROJECTS = "PROJECTS"
    PLAIN_TEXT = "PLAIN_TEXT"


class AnswerTypeDetector:
    """Detects the appropriate AnswerType presentation format from intent and query."""

    INTENT_MAP: Dict[str, AnswerType] = {
        "CONTACT": AnswerType.CONTACT,
        "CONTACT_DETAILS": AnswerType.CONTACT,
        "PHONE": AnswerType.CONTACT,
        "PHONE_NUMBERS": AnswerType.CONTACT,
        "EMAIL": AnswerType.CONTACT,
        "ADDRESS": AnswerType.CONTACT,
        "LOCATION": AnswerType.CONTACT,
        "LINKEDIN": AnswerType.CONTACT,
        "GITHUB": AnswerType.CONTACT,
        "PORTFOLIO": AnswerType.CONTACT,

        "EDUCATION": AnswerType.EDUCATION,
        "CGPA": AnswerType.EDUCATION,
        "GRADUATION_YEAR": AnswerType.EDUCATION,

        "SKILLS": AnswerType.SKILLS_BULLET,
        "PROGRAMMING_LANGUAGES": AnswerType.SKILLS_BULLET,
        "HUMAN_LANGUAGES": AnswerType.SKILLS_BULLET,
        "ERP_PLATFORMS": AnswerType.SKILLS_BULLET,
        "TECHNICAL_SKILLS": AnswerType.SKILLS_BULLET,
        "SOFT_SKILLS": AnswerType.SKILLS_BULLET,

        "SKILL_VERIFY": AnswerType.SKILL_VERIFICATION,

        "EXPERIENCE": AnswerType.EXPERIENCE_TIMELINE,
        "TIMELINE": AnswerType.EXPERIENCE_TIMELINE,
        "DOMAIN_EXPERIENCE": AnswerType.EXPERIENCE_TIMELINE,
        "CURRENT_COMPANY": AnswerType.EXPERIENCE_TIMELINE,

        "ROLE_INFERENCE": AnswerType.ROLE_MATCH_SCORECARD,
        "ROLE_MATCH": AnswerType.ROLE_MATCH_SCORECARD,
        "ROLE_COMPARE": AnswerType.ROLE_MATCH_SCORECARD,
        "SUITABILITY": AnswerType.ROLE_MATCH_SCORECARD,

        "SUMMARY": AnswerType.RECRUITER_SUMMARY,
        "BASIC_PROFILE": AnswerType.RECRUITER_SUMMARY,
        "CAREER_TRANSITION": AnswerType.RECRUITER_SUMMARY,

        "AWARDS": AnswerType.AWARDS,
        "CERTIFICATIONS": AnswerType.AWARDS,

        "PROJECTS": AnswerType.PROJECTS,
    }

    def detect(self, intent: str, question: Optional[str] = None) -> AnswerType:
        """Detect answer presentation type from intent string and query."""
        intent_upper = (intent or "").upper().strip()
        answer_type = self.INTENT_MAP.get(intent_upper, AnswerType.PLAIN_TEXT)
        logger.debug(f"Mapped intent '{intent}' → AnswerType.{answer_type.value}")
        return answer_type


# Singleton instance
answer_type_detector = AnswerTypeDetector()
