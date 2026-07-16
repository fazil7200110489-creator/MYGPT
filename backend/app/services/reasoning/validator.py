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
            # Skills must be in bullet points if they are lists
            lines = [l.strip() for l in answer.split('\n') if l.strip()]
            if lines and lines[0].lower() == "skills":
                lines = lines[1:]
            if len(lines) > 1:
                return all(l.startswith('•') for l in lines)
            return True

        elif intent_upper == "PROJECTS":
            # Projects must be numbered lists
            lines = [l.strip() for l in answer.split('\n') if l.strip()]
            if lines and lines[0].lower() == "projects":
                lines = lines[1:]
            if len(lines) > 1:
                return all(re.match(r'^\d+\.', l) for l in lines)
            return True

        return True
