"""Confidence Calculator — Phase 7 of the Resume Intelligence Pipeline.

Provides a single, focused class for computing answer confidence scores.
Previously this logic was scattered across ReasoningService as private
methods.  Moving it here makes it independently testable and reusable
by any future document specialist.

Pipeline position:
    ResumeReasoner / Specialist
        ↓
    ConfidenceCalculator    ← THIS MODULE
        ↓
    AnswerBuilder
        ↓
    ...
"""

import re
from typing import Any, Dict, List, Optional


class ConfidenceCalculator:
    """Computes answer confidence scores from multiple quality signals.

    All scoring weights are class-level constants so they can be tuned
    without touching the algorithm.

    Usage::

        calc = ConfidenceCalculator()
        score = calc.calculate(
            answer="Flutter Developer",
            intent="GENERAL",
            entities={...},
            retrieved_chunks=[...],
        )
    """

    # Scoring weights (must sum ≤ 1.0 per dimension group)
    W_EVIDENCE  = 0.30   # Retrieval quality
    W_VALIDATION = 0.30  # Validator result
    W_ANSWER_TYPE = 0.20 # Answer-type heuristic
    W_CONSISTENCY = 0.20 # Structured-data consistency

    # Confidence bounds
    MIN_CONFIDENCE = 25.0
    MAX_CONFIDENCE = 99.0

    # Phrases that indicate a high-quality negative answer
    NEGATIVE_PHRASES = frozenset([
        "does not mention",
        "no certifications were found",
        "couldn't find that information",
        "not mention",
        "not mentioned",
    ])

    def calculate(
        self,
        answer: str,
        intent: str,
        entities: Dict[str, Any],
        retrieved_chunks: List[Dict[str, Any]],
        is_valid: bool = True,
        is_yes_no: bool = False,
        is_composite: bool = False,
        composite_scores: Optional[List[float]] = None,
    ) -> float:
        """Compute a confidence percentage [0, 99] for an answer.

        Args:
            answer:           Final cleaned answer string.
            intent:           Canonical intent string.
            entities:         Extracted entity dict from EntityExtractor.
            retrieved_chunks: Raw retrieved chunk list.
            is_valid:         Whether the answer passed Validator.validate().
            is_yes_no:        Whether the question is a Yes/No question.
            is_composite:     Whether this is a composite multi-intent query.
            composite_scores: Pre-calculated per-intent scores for composite.

        Returns:
            Confidence percentage in [MIN_CONFIDENCE, MAX_CONFIDENCE].
        """
        # Confirmed absent is 90% confident (we are sure it's missing)
        if self._is_negative_answer(answer):
            return 90.0

        # GENERAL / ROLE_INFERENCE: scored based on domain signal quality
        if intent.upper() in ("GENERAL", "ROLE_INFERENCE", "ROLE_COMPARE"):
            if answer and "based on" in answer.lower():
                return 78.0
            return 72.0

        if is_composite and composite_scores:
            return round(
                min(self.MAX_CONFIDENCE, max(self.MIN_CONFIDENCE,
                    sum(composite_scores) / len(composite_scores))),
                1,
            )

        return round(self._single_score(answer, intent, entities, retrieved_chunks, is_valid, is_yes_no), 1)

    def _single_score(
        self,
        answer: str,
        intent: str,
        entities: Dict[str, Any],
        retrieved_chunks: List[Dict[str, Any]],
        is_valid: bool,
        is_yes_no: bool,
    ) -> float:
        """Compute single-intent confidence."""
        # 1. Evidence quality
        evidence_quality = 0.50
        if retrieved_chunks:
            has_section_match = any(
                c.get("section", "Content") != "Content" for c in retrieved_chunks
            )
            evidence_quality = 0.95 if has_section_match else 0.75

        # 2. Validation success
        validation_success = 1.0 if is_valid else 0.2

        # 3. Answer-type heuristic
        answer_lower = answer.lower()
        if is_yes_no:
            ans_type_factor = 0.85
        elif "total experience" in answer_lower or re.search(r"\b\d+\s+years?\b", answer_lower):
            ans_type_factor = 0.90
        else:
            chunks_text = "\n".join(c.get("text", "") for c in retrieved_chunks).lower() if retrieved_chunks else ""
            if answer_lower in chunks_text or any(
                part.strip() in chunks_text
                for part in answer_lower.split("\n")
                if len(part.strip()) > 10
            ):
                ans_type_factor = 1.0
            else:
                ans_type_factor = 0.80

        # 4. Consistency
        consistency_factor = self._consistency_factor(answer_lower, entities)

        raw = (
            self.W_EVIDENCE    * evidence_quality
            + self.W_VALIDATION  * validation_success
            + self.W_ANSWER_TYPE * ans_type_factor
            + self.W_CONSISTENCY * consistency_factor
        ) * 100.0

        return min(self.MAX_CONFIDENCE, max(self.MIN_CONFIDENCE, raw))

    def _consistency_factor(
        self,
        answer_lower: str,
        entities: Dict[str, Any],
    ) -> float:
        """Checks experience year consistency between answer and structured data."""
        if not entities or "experience" not in entities:
            return 1.0
        try:
            from backend.app.services.reasoning.specialists.resume_reasoner import calculate_total_experience
            exp = entities.get("experience") or []
            total_exp = calculate_total_experience(exp)
            if total_exp == "0 years":
                return 1.0
            correct_match = re.search(r"\b\d+\b", total_exp)
            if not correct_match:
                return 1.0
            correct_years = correct_match.group(0)
            mentioned = re.findall(r"\b(\d+(?:\.\d+)?)\s*years?\b", answer_lower)
            if mentioned and any(y != correct_years for y in mentioned):
                return 0.70
        except Exception:
            pass
        return 1.0

    def _is_negative_answer(self, answer: str) -> bool:
        """Returns True if the answer is a high-confidence negative."""
        lower = answer.lower()
        return any(phrase in lower for phrase in self.NEGATIVE_PHRASES)

    def calculate_breakdown(
        self,
        answer: str,
        intent: str,
        entities: Dict[str, Any],
        retrieved_chunks: List[Dict[str, Any]],
        is_valid: bool = True,
        is_yes_no: bool = False,
        final_conf: Optional[float] = None
    ) -> Dict[str, float]:
        """Calculates granular confidence metrics:
          - intent_confidence
          - entity_confidence
          - evidence_confidence
          - final_confidence
        """
        # Use calibrated intent confidence: higher for structural intents, lower for inferred
        STRUCTURAL_INTENTS = [
            "CANDIDATE_NAME", "PHONE", "EMAIL", "DESIGNATION", "EDUCATION",
            "SKILLS", "SKILL_VERIFY", "AWARDS", "CERTIFICATIONS", "GRADUATION_YEAR", "CGPA"
        ]
        INFERRED_INTENTS = ["GENERAL", "ROLE_INFERENCE", "ROLE_COMPARE", "CAREER_TRANSITION"]

        intent_conf = (
            95.0 if intent.upper() in STRUCTURAL_INTENTS
            else 82.0 if intent.upper() in INFERRED_INTENTS
            else 90.0
        )
        entity_conf = min(97.0, 70.0 + (len(entities) * 2.0)) if entities else 65.0
        evidence_conf = (
            95.0 if (retrieved_chunks and any(c.get("section", "Content") != "Content" for c in retrieved_chunks))
            else 80.0 if retrieved_chunks
            else 65.0
        )
        calculated_final = final_conf if final_conf is not None else self.calculate(answer, intent, entities, retrieved_chunks, is_valid, is_yes_no)

        return {
            "intent_confidence": round(intent_conf, 1),
            "entity_confidence": round(entity_conf, 1),
            "evidence_confidence": round(evidence_conf, 1),
            "final_confidence": round(calculated_final, 1)
        }
