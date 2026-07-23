"""Recruiter Session Memory — Maintains Recruiter state across continuous turns.

Enables multi-turn conversational sequences:
"Find Frontend Developers" -> "Show top 5" -> "Compare 1 and 3" -> "Explain why candidate 1 ranked higher"
"""

import uuid
from typing import Dict, Any, List, Optional
from loguru import logger


class RecruiterSessionMemory:
    """Manages conversational session context for recruiters."""

    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def get_session(self, session_id: str) -> Dict[str, Any]:
        """Get or initialize session object by ID."""
        if not session_id or session_id not in self._sessions:
            sid = session_id or str(uuid.uuid4())[:8]
            self._sessions[sid] = {
                "session_id": sid,
                "turns": [],
                "active_target_role": None,
                "active_department": None,
                "last_query_plan": None,
                "last_requirement_profile": None,
                "last_candidate_ids": [],
                "last_ranked_results": []
            }
            logger.info(f"Initialized new RecruiterSessionMemory for session {sid}")
            return self._sessions[sid]

        return self._sessions[session_id]

    def add_turn(
        self,
        session_id: str,
        raw_query: str,
        intent: str,
        query_plan: Optional[Any] = None,
        requirement_profile: Optional[Any] = None,
        candidate_ids: Optional[List[str]] = None,
        ranked_results: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Record a single recruiter turn and update active context."""
        session = self.get_session(session_id)

        turn_record = {
            "query": raw_query,
            "intent": intent,
            "query_plan": query_plan.to_dict() if hasattr(query_plan, "to_dict") else query_plan,
            "requirement_profile": requirement_profile.to_dict() if hasattr(requirement_profile, "to_dict") else requirement_profile,
            "candidate_ids": candidate_ids or [],
        }

        session["turns"].append(turn_record)

        if query_plan:
            session["last_query_plan"] = query_plan
            if hasattr(query_plan, "target_role") and query_plan.target_role:
                session["active_target_role"] = query_plan.target_role
            if hasattr(query_plan, "department") and query_plan.department:
                session["active_department"] = query_plan.department

        if requirement_profile:
            session["last_requirement_profile"] = requirement_profile

        if candidate_ids:
            session["last_candidate_ids"] = candidate_ids

        if ranked_results:
            session["last_ranked_results"] = ranked_results

        logger.info(f"Recorded turn '{raw_query}' ({intent}) in session {session_id}. Active Role: {session.get('active_target_role')}")
        return session

    def get_last_candidate_ids(self, session_id: str) -> List[str]:
        """Retrieve last set of active candidate IDs for sequential queries."""
        session = self.get_session(session_id)
        return session.get("last_candidate_ids", [])

    def get_last_ranked_results(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieve last set of ranked results."""
        session = self.get_session(session_id)
        return session.get("last_ranked_results", [])

    def clear_session(self, session_id: str) -> None:
        """Reset a session context."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Cleared session {session_id}")


# Singleton Instance
recruiter_session_memory = RecruiterSessionMemory()
