"""Reasoning Trace Service for generating step-by-step reasoning logs and debug metadata.

Captures:
    - Detected Intent
    - Resolved Entity Subtree
    - Evidence Used
    - Business Rules Applied
    - Decision Taken
    - Final Answer
    - Confidence Score
"""

from typing import Dict, Any, List, Optional
from loguru import logger


class ReasoningStepTrace:
    """Represents a single step in the reasoning pipeline trace."""

    def __init__(self, step_name: str, details: str):
        self.step_name = step_name
        self.details = details

    def to_dict(self) -> Dict[str, str]:
        return {"step": self.step_name, "details": self.details}


class ReasoningTrace:
    """Encapsulates the complete reasoning trace for a query execution."""

    def __init__(
        self,
        question: str,
        detected_intent: str,
        resolved_entity: str = "CandidateProfile",
        evidence_used: str = "Not Mentioned",
        business_rules_applied: Optional[List[str]] = None,
        decision_taken: str = "Default Decision",
        final_answer: str = "",
        confidence_score: float = 90.0,
    ):
        self.question = question
        self.detected_intent = detected_intent
        self.resolved_entity = resolved_entity
        self.evidence_used = evidence_used
        self.business_rules_applied = business_rules_applied or []
        self.decision_taken = decision_taken
        self.final_answer = final_answer
        self.confidence_score = confidence_score
        self.steps: List[ReasoningStepTrace] = []

    def add_step(self, step_name: str, details: str) -> None:
        self.steps.append(ReasoningStepTrace(step_name, details))

    def to_dict(self) -> Dict[str, Any]:
        """Convert trace to API debug mode dictionary payload."""
        return {
            "question": self.question,
            "detected_intent": self.detected_intent,
            "resolved_entity": self.resolved_entity,
            "evidence_used": self.evidence_used,
            "business_rules_applied": self.business_rules_applied,
            "decision_taken": self.decision_taken,
            "confidence_score": round(self.confidence_score, 2),
            "trace_steps": [s.to_dict() for s in self.steps],
        }

    def format_debug_summary(self) -> str:
        """Format trace as human-readable debug summary text."""
        rules_str = "\n  • ".join(self.business_rules_applied) if self.business_rules_applied else "Standard Factual Lookup"
        return (
            f"=== MYGPT REASONING TRACE ===\n"
            f"Question:           '{self.question}'\n"
            f"Detected Intent:    {self.detected_intent}\n"
            f"Resolved Entity:    {self.resolved_entity}\n"
            f"Evidence Used:      {self.evidence_used}\n"
            f"Rules Applied:\n  • {rules_str}\n"
            f"Decision Taken:     {self.decision_taken}\n"
            f"Confidence Score:   {self.confidence_score}%\n"
            f"============================="
        )


class ReasoningTraceService:
    """Service for building and tracking reasoning traces."""

    def create_trace(
        self,
        question: str,
        intent: str,
        resolved_entity: str = "CandidateProfile",
    ) -> ReasoningTrace:
        trace = ReasoningTrace(
            question=question,
            detected_intent=intent,
            resolved_entity=resolved_entity
        )
        logger.debug(f"Created reasoning trace for question '{question}' with intent '{intent}'")
        return trace


# Singleton instance
reasoning_trace_service = ReasoningTraceService()
