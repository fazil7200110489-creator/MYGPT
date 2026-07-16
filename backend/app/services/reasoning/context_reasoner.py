import re
from typing import List, Dict, Any

class ContextReasoner:
    """Synthesizes, combines, and cross-references multiple facts for inference/comparison queries."""

    def reason(self, facts: List[str], intent: str) -> List[str]:
        """Combines multiple facts into synthesized statements when they share subjects."""
        if not facts:
            return []

        intent_upper = intent.upper()
        synthesized = []

        # 1. Group facts by subject (e.g. Company name, Project name, or specific dates)
        # We can detect subjects using capitalized word sequences (proper nouns)
        subject_groups: Dict[str, List[str]] = {}
        for fact in facts:
            # Simple subject detection: find capitalized phrases (excluding sentence start)
            words = fact.split()
            proper_nouns = []
            for w in words[1:]:
                # Clean punctuation from word
                cleaned_w = re.sub(r'[^\w]', '', w)
                if cleaned_w and cleaned_w[0].isupper() and cleaned_w.lower() not in ["delhi", "google", "microsoft", "monday", "january", "february", "march"]:
                    proper_nouns.append(cleaned_w)
            
            subject = None
            if proper_nouns:
                subject = proper_nouns[0]
            else:
                # Fallback: look for common subjects
                for sub in ["skills", "experience", "education", "invoice", "payment", "due", "total"]:
                    if sub in fact.lower():
                        subject = sub
                        break
            
            if subject:
                if subject not in subject_groups:
                    subject_groups[subject] = []
                subject_groups[subject].append(fact)
            else:
                synthesized.append(fact)

        # 2. Merge facts inside each group
        for subject, group_facts in subject_groups.items():
            if len(group_facts) == 1:
                synthesized.append(group_facts[0])
            else:
                # Merge logic: combine clauses nicely
                merged_clauses = []
                for gf in group_facts:
                    # Strip common headers or prefixes
                    clause = gf.strip()
                    if clause.endswith("."):
                        clause = clause[:-1]
                    merged_clauses.append(clause)
                
                # Combine clauses with connectors
                if len(merged_clauses) == 2:
                    merged_text = f"{merged_clauses[0]}, and {merged_clauses[1]}."
                else:
                    merged_text = ", ".join(merged_clauses[:-1]) + f", and {merged_clauses[-1]}."
                
                # Normalize spaces and return
                merged_text = re.sub(r'\s+', ' ', merged_text)
                synthesized.append(merged_text)

        # 3. Handle specific intent-based inference (e.g. tenure calculation, tax sum)
        if intent_upper in ["EXPERIENCE", "SUMMARY"]:
            # Check for multiple dates to infer tenure
            years = []
            for fact in facts:
                found_years = re.findall(r'\b(20\d{2})\b', fact)
                years.extend([int(y) for y in found_years])
            if len(years) >= 2:
                min_yr, max_yr = min(years), max(years)
                tenure = max_yr - min_yr
                if tenure > 0:
                    synthesized.append(f"The document suggests a career span of approximately {tenure} years (from {min_yr} to {max_yr}).")

        return synthesized
