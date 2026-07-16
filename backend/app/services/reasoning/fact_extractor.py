import re
from typing import List, Dict, Any, Optional

class FactExtractor:
    """Filters chunks to extract only unique, normalized relevant facts."""

    def extract(self, retrieved_chunks: List[Dict[str, Any]], intent: str, query: Optional[str] = None) -> List[str]:
        """Extracts individual sentences from retrieved chunks, keeping only relevant and unique facts."""
        if not retrieved_chunks:
            return []

        # 1. Gather text blocks and strip metadata headers
        raw_blocks = []
        for chunk in retrieved_chunks:
            text = chunk.get("text", "")
            # Strip page indicators
            text = re.sub(r'\[Page \d+ \| Section: [^\]]+\]', '', text)
            raw_blocks.append(text)

        # 2. Segment blocks into individual sentences
        raw_sentences = []
        for block in raw_blocks:
            # Split by double newline or sentence punctuation
            lines = [l.strip() for l in block.split('\n') if l.strip()]
            for line in lines:
                sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', line) if s.strip()]
                raw_sentences.extend(sentences)

        # 3. Clean and normalize sentences
        normalized_sentences = []
        for s in raw_sentences:
            # Collapse whitespace
            s = re.sub(r'\s+', ' ', s)
            # Remove leading bullets or list dashes
            s = re.sub(r'^[•\-*\d\.\s]+', '', s).strip()
            # Standardize smart quotes and em-dashes
            s = s.replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
            s = s.replace("\u2013", "-").replace("\u2014", "-")
            # Avoid single words/punctuation debris
            if len(s) > 2:
                normalized_sentences.append(s)

        # 4. Deduplicate sentences case-insensitively
        unique_facts = []
        seen = set()
        for s in normalized_sentences:
            key = s.lower().strip()
            # Basic sentence overlap thresholding to avoid minor variations
            if key not in seen:
                seen.add(key)
                unique_facts.append(s)

        # 5. Filter for relevance based on intent and query keywords
        intent_upper = intent.upper()
        
        # Relevant words from query
        q_words = set()
        if query:
            q_words = set(w.lower() for w in re.findall(r'\w+', query) if len(w) > 3)

        relevant_facts = []
        for fact in unique_facts:
            fact_lower = fact.lower()
            
            # Intent specific filtering
            if intent_upper in ["PHONE", "PHONE_NUMBERS"]:
                if any(w in fact_lower for w in ["phone", "mobile", "cell", "contact", "call"]) or re.search(r'\d{3,}', fact):
                    relevant_facts.append(fact)
            elif intent_upper == "EMAIL":
                if "@" in fact or any(w in fact_lower for w in ["email", "e-mail", "mail", "gmail"]):
                    relevant_facts.append(fact)
            elif intent_upper == "SKILLS":
                if any(w in fact_lower for w in ["skill", "technolog", "proficien", "language", "tool", "stack", "know", "experience"]):
                    relevant_facts.append(fact)
            elif intent_upper == "PROJECTS":
                if any(w in fact_lower for w in ["project", "build", "develop", "implement", "portfolio", "system", "app"]):
                    relevant_facts.append(fact)
            elif intent_upper == "EDUCATION":
                if any(w in fact_lower for w in ["education", "degree", "university", "college", "school", "graduate", "academic", "bachelor", "master"]):
                    relevant_facts.append(fact)
            elif intent_upper == "CERTIFICATIONS":
                if any(w in fact_lower for w in ["certif", "award", "achieve", "training", "license"]):
                    relevant_facts.append(fact)
            elif intent_upper == "EXPERIENCE":
                if any(w in fact_lower for w in ["experience", "work", "employ", "job", "career", "role", "position"]):
                    relevant_facts.append(fact)
            elif intent_upper in ["INVOICE_TOTAL", "TOTAL"]:
                if any(w in fact_lower for w in ["total", "due", "amount", "cost", "price", "grand", "charge"]):
                    relevant_facts.append(fact)
            else:
                # If we have query keywords, check if sentence has overlap
                if q_words:
                    f_words = set(re.findall(r'\w+', fact_lower))
                    if q_words.intersection(f_words):
                        relevant_facts.append(fact)
                else:
                    relevant_facts.append(fact)

        # Fallback: if filtering left us with nothing, return unique_facts
        if not relevant_facts:
            relevant_facts = unique_facts

        return relevant_facts[:12] # Limit number of extracted facts
