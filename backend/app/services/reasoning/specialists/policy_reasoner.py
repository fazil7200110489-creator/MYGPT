from typing import Dict, Any, List, Optional

class PolicyReasoner:
    """Document Specialist for company policies and guidelines."""

    def reason(self, entities: Dict[str, Any], facts: List[str], intent: str) -> Any:
        """Finds policy sections or details matching the intent."""
        if not facts:
            return "No policy records found."

        # Return combined unique facts/rules about the policy
        return facts
