import re
from typing import List

class Formatter:
    """Normalizes whitespace, cleans duplicate words/syllables, and cleans punctuation.

    Must preserve: emails, URLs, dates, numbers, currency, and IDs.
    """

    def clean(self, text: str) -> str:
        """Applies robust deduplication and cleanup without altering original facts."""
        if not text:
            return ""

        # 1. Shield elements to preserve
        patterns = [
            # URLs
            r'https?://[^\s/$.?#].[^\s]*',
            # Emails
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            # Phone numbers
            r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}',
            # Dates
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{2,4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+\d{2,4}\b',
            # Currency
            r'[\$\u20b9\u20ac\u00a3]\s*[\d,]+\.?\d*',
            # Alphanumeric IDs and pure numbers
            r'\b[A-Za-z0-9]+-\d+\b|\b\d+\b'
        ]

        placeholders = []
        
        def shield_match(match):
            val = match.group(0)
            idx = len(placeholders)
            placeholders.append(val)
            return f"__SHIELD_VAL_{idx}__"

        # Replace each matched pattern in order of complexity
        for pattern in patterns:
            text = re.sub(pattern, shield_match, text)

        # 2. Perform the cleaning of duplicate words on the shielded text
        # A. Clean run-together duplicate words like "SummarySummary" -> "Summary"
        def replace_run_together(match):
            word = match.group(0)
            L = len(word)
            # Try all possible divisor lengths of the word
            for chunk_len in range(2, L // 2 + 1):
                if L % chunk_len == 0:
                    chunk = word[:chunk_len]
                    if chunk.lower() * (L // chunk_len) == word.lower():
                        # Check exceptions list
                        if word.lower() not in {"murmur", "tartar", "couscous", "cancan", "meme", "haha", "dodo", "coco", "gogo"}:
                            return word[:chunk_len]
            return word

        text = re.sub(r'[A-Za-z]+', replace_run_together, text)

        # B. Clean space-separated duplicate words: "Word Word" -> "Word"
        prev = None
        while prev != text:
            prev = text
            text = re.sub(r'\b([A-Za-z]+)\b\s+\b\1\b', r'\1', text, flags=re.IGNORECASE)

        # 3. Restore the shielded elements
        for idx, val in reversed(list(enumerate(placeholders))):
            text = text.replace(f"__SHIELD_VAL_{idx}__", val)

        # 4. Normalize spacing and punctuation
        text = re.sub(r"[ \t]+", " ", text).strip()
        text = re.sub(r"\s+([.,!?;:])", r"\1", text)
        text = re.sub(r"\.{2,}", ".", text)

        return text
