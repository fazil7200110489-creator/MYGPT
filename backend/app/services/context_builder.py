"""Context Builder Service for formatting and ranking context chunks.
"""

import re
from typing import Dict, Any, List, Optional
from loguru import logger


class ContextBuilder:
    """Aggregates, deduplicates, and constructs context for local reasoning."""

    def build_context(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
        max_context_chars: int = 1500,
        intent: Optional[str] = None,
    ) -> str:
        """Constructs a clean context text block from retrieved chunks.
        
        Args:
            query: User's query question.
            retrieved_chunks: Chunks returned from SearchCoordinator.
            max_context_chars: Max character limit for the aggregated context block.
            intent: Optional inferred intent for dynamic sizing.
            
        Returns:
            Structured reasoning context block.
        """
        logger.info(f"Building reasoning context for query '{query[:30]}...' with {len(retrieved_chunks)} chunks.")

        if not retrieved_chunks:
            return ""

        # Dynamic context sizing based on intent
        if intent in ["Summary", "Extraction", "Research", "Comparison"]:
            max_context_chars = 2500
        elif intent in ["Invoice", "Dates", "Numbers", "Contacts", "Emails", "Phone Numbers"]:
            max_context_chars = 1000

        # 1. Split all chunks into sentences and deduplicate
        unique_sentences = []
        seen_sentences = set()
        
        for chunk in retrieved_chunks:
            chunk_text = chunk.get("text", "")
            # Preserve list blocks and table rows as single entries
            blocks = re.split(r'\n\n+', chunk_text)
            for block in blocks:
                block = block.strip()
                if not block:
                    continue
                # If block is a list or table, keep as one entry
                is_structured = bool(re.match(r'^[\s]*[\u2022\-*|]', block)) or '|' in block
                if is_structured:
                    if block not in seen_sentences:
                        seen_sentences.add(block)
                        unique_sentences.append(block)
                else:
                    # Split into sentences using a lookbehind assertion
                    sentences = [s.strip() for s in re.split(r"(?<=\.|\?)\s+", block) if s.strip()]
                    for s in sentences:
                        if s not in seen_sentences:
                            seen_sentences.add(s)
                            unique_sentences.append(s)

        # 2. Overlap removal: if sentence A is a substring of sentence B, drop sentence A.
        filtered_sentences = []
        for s in unique_sentences:
            is_substring = False
            for other in unique_sentences:
                if s != other and s in other:
                    is_substring = True
                    break
            if not is_substring:
                filtered_sentences.append(s)

        # 3. Relevance re-ranking: score each sentence by keyword overlap with query, emit highest-scoring sentences first.
        query_words = set(re.findall(r"\w+", query.lower()))
        
        def get_overlap_score(s: str) -> int:
            s_words = set(re.findall(r"\w+", s.lower()))
            return len(query_words.intersection(s_words))

        sorted_sentences = sorted(filtered_sentences, key=get_overlap_score, reverse=True)

        # 4. Clean output: build final context block of raw text up to max_context_chars
        context_parts = []
        current_len = 0

        for s in sorted_sentences:
            if current_len + len(s) + 2 > max_context_chars:
                remaining_chars = max_context_chars - current_len
                if remaining_chars > 30:
                    context_parts.append(s[:remaining_chars] + "... [truncated]")
                break
            context_parts.append(s)
            current_len += len(s) + 2  # Account for separating double newlines

        final_context = "\n\n".join(context_parts).strip()
        logger.info(f"Reasoning context assembled successfully. Length: {len(final_context)} chars.")
        return final_context


context_builder = ContextBuilder()

