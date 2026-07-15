"""Conversation Memory Service for maintaining multi-turn chat history state.
"""

import time
from typing import Dict, Any, List, Optional
from loguru import logger


class ConversationMemory:
    """Manages active chat sessions, dialogue histories, and session parameters."""

    def __init__(self) -> None:
        # Maps session_id -> { "history": [...], "active_doc_id": str }
        self.sessions: Dict[str, Dict[str, Any]] = {}
        logger.info("ConversationMemory service initialized.")

    def _ensure_session(self, session_id: str) -> None:
        """Initializes session state if not already created."""
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "history": [],
                "active_doc_id": None,
                "last_active": time.time(),
            }

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Appends a new turn message to the conversation history.
        
        Args:
            session_id: Dialogue session identifier.
            role: Sender role ('user' or 'assistant').
            content: Text contents of the message.
            metadata: Formatted source references and confidence payloads.
        """
        self._ensure_session(session_id)
        message = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
            "metadata": metadata or {},
        }
        self.sessions[session_id]["history"].append(message)
        self.sessions[session_id]["last_active"] = time.time()
        logger.info(f"Added message to session {session_id} from role '{role}'")

    def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieves history list of messages for a session.
        
        Args:
            session_id: Dialogue session identifier.
            
        Returns:
            List of message dictionaries.
        """
        self._ensure_session(session_id)
        return self.sessions[session_id]["history"]

    def get_context_for_llm(self, session_id: str, max_turns: int = 3) -> str:
        """Assembles trailing turns of dialogue context for multi-turn prompt building.
        
        Args:
            session_id: Dialogue session ID.
            max_turns: Number of trailing turns of conversation to fetch.
            
        Returns:
            Formatted chat logs string.
        """
        history = self.get_history(session_id)
        trailing = history[-max_turns * 2:]  # 1 turn = user + assistant
        
        context_parts = []
        for msg in trailing:
            role_tag = "Human" if msg["role"] == "user" else "Assistant"
            context_parts.append(f"{role_tag}: {msg['content']}")
            
        return "\n".join(context_parts)

    def set_active_document(self, session_id: str, doc_id: Optional[str]) -> None:
        """Sets the selected document filter ID for a session.
        
        Args:
            session_id: Session ID.
            doc_id: Document ID or None.
        """
        self._ensure_session(session_id)
        self.sessions[session_id]["active_doc_id"] = doc_id
        logger.info(f"Session {session_id} active document set to {doc_id}")

    def get_active_document(self, session_id: str) -> Optional[str]:
        """Gets the active document ID of a session.
        
        Args:
            session_id: Session ID.
            
        Returns:
            Document ID or None.
        """
        self._ensure_session(session_id)
        return self.sessions[session_id]["active_doc_id"]

    def get_context_summary(self, session_id: str) -> str:
        """Returns the last user question + last assistant answer for follow-up context injection.
        
        Args:
            session_id: Session ID.
            
        Returns:
            A string containing the summary of the last conversation turn, or empty string.
        """
        self._ensure_session(session_id)
        history = self.get_history(session_id)
        
        user_msg = None
        assistant_msg = None
        
        # Traverse backwards to find the last assistant message and last user message before it
        for msg in reversed(history):
            if msg["role"] == "assistant" and not assistant_msg:
                assistant_msg = msg["content"]
            elif msg["role"] == "user" and assistant_msg and not user_msg:
                user_msg = msg["content"]
                break
                
        if user_msg and assistant_msg:
            # Strip sources block from the assistant answer if present to keep it clean
            import re
            clean_assistant = re.sub(r"\n\n\*\*Sources:\*\*.*$", "", assistant_msg, flags=re.DOTALL).strip()
            return f"Previous Question: {user_msg} | Previous Answer: {clean_assistant}"
        return ""

    def clear_history(self, session_id: str) -> None:
        """Resets dialogue history for a session while preserving document filters.
        
        Args:
            session_id: Session ID.
        """
        self._ensure_session(session_id)
        self.sessions[session_id]["history"] = []
        logger.info(f"Cleared history logs for session {session_id}")


conversation_memory = ConversationMemory()
