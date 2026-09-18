import re
from typing import Dict, Any

class Validator:
    """Validates final generated answers against intent structural rules."""

    def validate(self, answer: str, intent: str) -> bool:
        """Confirms formatting rules are met, returning True if valid."""
        if not answer or answer == "I couldn't find that information in the uploaded document.":
            return True

        intent_upper = intent.upper()

        if intent_upper in ["PHONE", "PHONE_NUMBERS"]:
            # Check for at least 6 digits
            digits = re.sub(r'[^\d]', '', answer)
            return len(digits) >= 6

        elif intent_upper == "EMAIL":
            # Check for '@' and basic dot structure
            return "@" in answer and "." in answer.split("@")[-1]

        elif intent_upper == "SKILLS":
            answer_lower = answer.lower()
            forbidden_kws = ["father name", "mother name", "marital status", "religion", "nationality", "date of birth"]
            if any(k in answer_lower for k in forbidden_kws):
                return False
            return True

        elif intent_upper == "PROJECTS":
            answer_lower = answer.lower()
            forbidden_keywords = [
                "father name", "mother name", "date of birth", "d.o.b",
                "religion", "marital status", "spouse"
            ]
            if any(k in answer_lower for k in forbidden_keywords):
                return False
            return True

        return True
