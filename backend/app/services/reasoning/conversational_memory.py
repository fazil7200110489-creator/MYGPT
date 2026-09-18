"""Single Resume Conversational Memory & Context Resolver.
Manages multi-turn conversation memory for Product 1 (Single Resume AI).
Resolves pronouns, implicit follow-up queries, and context references.
"""

import re
from typing import Dict, Any, List, Optional
from loguru import logger


class SingleResumeConversationalMemory:
    """Session-based conversational memory manager for Single Resume AI."""

    def __init__(self):
        # Maps session_key (doc_id or session_id) -> list of turn dicts
        self._sessions: Dict[str, List[Dict[str, Any]]] = {}

    def get_history(self, session_key: str) -> List[Dict[str, Any]]:
        return self._sessions.get(session_key, [])

    def clear(self, session_key: str):
        if session_key in self._sessions:
            del self._sessions[session_key]

    def record_turn(
        self,
        session_key: str,
        user_query: str,
        resolved_query: str,
        classified_intent: str,
        candidate_name: str = "",
        system_response: str = "",
    ):
        """Record a single QA turn in the session history."""
        if not session_key:
            session_key = "default_single_resume_session"

        if session_key not in self._sessions:
            self._sessions[session_key] = []

        turn = {
            "user_query": user_query,
            "resolved_query": resolved_query,
            "classified_intent": classified_intent,
            "candidate_name": candidate_name,
            "system_response": system_response,
        }

        # Keep last 10 turns per session
        self._sessions[session_key].append(turn)
        if len(self._sessions[session_key]) > 10:
            self._sessions[session_key].pop(0)

    def resolve_context(
        self,
        user_query: str,
        session_key: str,
        candidate_name: str = "the candidate",
    ) -> Tuple[str, str]:
        """Resolve pronouns, implicit follow-ups, and context references based on turn history.

        Args:
            user_query: Raw user input.
            session_key: Unique session identifier (e.g. doc_id).
            candidate_name: Candidate's full name.

        Returns:
            Tuple of (resolved_query, inferred_intent_override)
        """
        if not user_query or not user_query.strip():
            return user_query, ""

        name_display = candidate_name.strip() if candidate_name and candidate_name != "Not Mentioned" else "the candidate"
        q_raw = user_query.strip()
        q_lower = q_raw.lower()

        history = self.get_history(session_key)
        last_turn = history[-1] if history else None

        intent_override = ""
        resolved = q_raw

        # 1. Pronoun Replacement: he/she/they/him/her/his/them/it -> candidate name
        resolved = re.sub(r'\b(?:he|she|they)\b', name_display, resolved, flags=re.IGNORECASE)
        resolved = re.sub(r'\b(?:him|her|them)\b', name_display, resolved, flags=re.IGNORECASE)
        resolved = re.sub(r'\b(?:his|her|their)\b', f"{name_display}'s", resolved, flags=re.IGNORECASE)

        # 2. Implicit Follow-up Question Resolution
        if last_turn:
            last_intent = last_turn.get("classified_intent", "")
            last_query = last_turn.get("user_query", "").lower()

            # Short follow-ups like "Why?", "Why would you hire him?", "Why?"
            if q_lower in ["why", "why?", "why is that", "why is that?", "explain why"]:
                if last_intent in ["HIRE_RECOMMENDATION", "ROLE_INFERENCE", "ROLE_RECOMMENDATION", "GENERAL"]:
                    resolved = f"Why is {name_display} suitable or recommended for the role?"
                    intent_override = "ROLE_INFERENCE"
                else:
                    resolved = f"Why is this the case for {name_display}?"
                    intent_override = last_intent

            # Follow-up: "Does he know Docker?" / "Is she familiar with React?"
            elif any(prefix in q_lower for prefix in ["does he know", "does she know", "does candidate know", "is he familiar with", "is she familiar with", "know docker", "know react", "know python", "know java"]):
                if not any(cat in q_lower for cat in ["framework", "frameworks", "library", "libraries", "technology", "technologies", "tech stack", "programming language", "programming languages", "coding language"]):
                    intent_override = "SKILL_VERIFY"

            # Follow-up: "Would you hire him?" / "Would you hire her?"
            elif any(ph in q_lower for ph in ["would you hire", "should we hire", "is he hireable", "is she hireable", "hire him", "hire her"]):
                resolved = f"Would you hire {name_display} based on their overall profile and skills?"
                intent_override = "HIRE_RECOMMENDATION"

            # Follow-up: "Which role suits him?" / "Which role suits her?" / "What role?"
            elif any(ph in q_lower for ph in ["which role suits", "what role suits", "best role", "suitable role", "which role"]):
                resolved = f"Which job roles are suitable for {name_display}?"
                intent_override = "ROLE_RECOMMENDATION"

            # Follow-up sequence:
            # Turn 1: Summarize resume -> Turn 2: What projects? -> Turn 3: What technologies? -> Turn 4: Does he know Docker?
            elif q_lower in ["what projects?", "what projects", "projects", "projects?"]:
                resolved = f"What projects has {name_display} worked on?"
                intent_override = "PROJECTS"

            elif q_lower in ["what technologies?", "what technologies", "technologies", "technologies?", "what tech stack?"]:
                resolved = f"What technical skills and technologies does {name_display} know?"
                intent_override = "SKILLS"

            elif q_lower in ["what experience?", "what experience", "experience", "experience?"]:
                resolved = f"What is the work experience of {name_display}?"
                intent_override = "EXPERIENCE"

            elif q_lower in ["what education?", "what education", "education", "education?"]:
                resolved = f"What is the education background of {name_display}?"
                intent_override = "EDUCATION"

            elif q_lower in ["contact?", "contact", "how to contact?", "how to reach"]:
                resolved = f"What are the contact details of {name_display}?"
                intent_override = "CONTACT"

        return resolved, intent_override


# Global singleton instance
conversational_memory = SingleResumeConversationalMemory()
