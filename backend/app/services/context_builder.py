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
        if intent in ["SUMMARY", "COMPARISON", "EXPLANATION", "GENERAL"]:
            max_context_chars = 2500
        else:
            max_context_chars = 1000

        # 1. Format chunks with structural metadata and split into blocks
        unique_blocks = []
        seen_blocks = set()
        
        for chunk in retrieved_chunks:
            chunk_text = chunk.get("text", "").strip()
            if not chunk_text:
                continue
            page_num = chunk.get("page_number", 1)
            section = chunk.get("section", "Content")
            
            # Format chunk text with structural page and section metadata
            formatted_text = f"[Page {page_num} | Section: {section}]\n{chunk_text}"
            
            blocks = re.split(r'\n\n+', formatted_text)
            for block in blocks:
                block = block.strip()
                if not block:
                    continue
                if block not in seen_blocks:
                    seen_blocks.add(block)
                    unique_blocks.append(block)

        # 2. Overlap removal: if block A is a substring of block B, drop block A.
        filtered_blocks = []
        for b in unique_blocks:
            is_substring = False
            for other in unique_blocks:
                if b != other and b in other:
                    is_substring = True
                    break
            if not is_substring:
                filtered_blocks.append(b)

        # 3. Relevance re-ranking: score each block by keyword overlap with query
        query_words = set(re.findall(r"\w+", query.lower()))
        
        def get_overlap_score(b: str) -> int:
            b_words = set(re.findall(r"\w+", b.lower()))
            return len(query_words.intersection(b_words))

        sorted_blocks = sorted(filtered_blocks, key=get_overlap_score, reverse=True)

        # 4. Clean output: build final context block of raw text up to max_context_chars
        context_parts = []
        current_len = 0

        for b in sorted_blocks:
            if current_len + len(b) + 2 > max_context_chars:
                remaining_chars = max_context_chars - current_len
                if remaining_chars > 30:
                    context_parts.append(b[:remaining_chars] + "... [truncated]")
                break
            context_parts.append(b)
            current_len += len(b) + 2

        final_context = "\n\n".join(context_parts).strip()
        logger.info(f"Reasoning context assembled successfully. Length: {len(final_context)} chars.")
        return final_context


context_builder = ContextBuilder()

