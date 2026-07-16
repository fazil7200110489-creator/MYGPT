from typing import Dict, Any, List, Optional

class ResearchReasoner:
    """Document Specialist for research papers and publications."""

    def reason(self, entities: Dict[str, Any], facts: List[str], intent: str) -> Any:
        """Finds abstract, methods, results, or conclusions of the paper."""
        if not facts:
            return "No research paper records found."

        # Return relevant facts (the fact extractor already filtered by intent/keywords)
        return facts
