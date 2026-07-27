"""Retrieval Service for matching queries against stored document chunks.
"""

import math
import re
from typing import Dict, Any, List, Optional, Set
from loguru import logger

from backend.app.services.storage_service import storage_service


class RetrievalService:
    """Performs cosine-similarity search over indexed document chunks."""

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        """Calculates cosine similarity between two vector lists.
        
        Args:
            v1: Vector 1.
            v2: Vector 2.
            
        Returns:
            Cosine similarity score (-1.0 to 1.0).
        """
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))
        
        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0
            
        return dot_product / (norm1 * norm2)

    def _text_overlap_ratio(self, text_a: str, text_b: str) -> float:
        """Computes what fraction of text_a's words are contained within text_b.

        Used to detect near-duplicate chunks so the lower-ranked one can be
        suppressed before it reaches the context builder.

        Args:
            text_a: Candidate (potentially duplicate) text.
            text_b: Reference (higher-ranked) text.

        Returns:
            Fraction in [0.0, 1.0].  1.0 means text_a is fully contained in text_b.
        """
        words_a: Set[str] = set(re.findall(r"\w+", text_a.lower()))
        words_b: Set[str] = set(re.findall(r"\w+", text_b.lower()))
        if not words_a:
            return 0.0
        return len(words_a & words_b) / len(words_a)

    def _deduplicate_chunks(
        self, scored_chunks: List[Dict[str, Any]], overlap_threshold: float = 0.65
    ) -> List[Dict[str, Any]]:
        """Removes lower-ranked chunks that are heavily overlapping with higher-ranked ones.

        Args:
            scored_chunks: List sorted descending by score (already ranked).
            overlap_threshold: If a chunk shares this fraction of its words with
                a higher-ranked chunk it is suppressed.

        Returns:
            Filtered list preserving only non-overlapping chunks.
        """
        kept: List[Dict[str, Any]] = []
        for candidate in scored_chunks:
            candidate_text = candidate.get("text", "")
            is_duplicate = False
            for reference in kept:
                ref_text = reference.get("text", "")
                ratio = self._text_overlap_ratio(candidate_text, ref_text)
                if ratio >= overlap_threshold:
                    is_duplicate = True
                    break
            if not is_duplicate:
                kept.append(candidate)
        return kept

    def _compress_context(self, text: str, query: str) -> str:
        """Compresses a chunk's text by keeping sentences with query keyword overlap,
        preserving paragraph context if it is already compact.
        """
        if not query or len(text) < 150:
            return text
            
        # Clean query words (remove short stop words)
        stop_words = {"what", "who", "is", "are", "the", "and", "for", "with", "from", "this", "that", "about", "describe", "explain", "summarize", "list", "show"}
        query_words = [w.lower() for w in re.findall(r'\b\w{3,}\b', query) if w.lower() not in stop_words]
        if not query_words:
            return text
            
        sentences = re.split(r'(?<=[.!?])\s+', text)
        kept_sentences = []
        for s in sentences:
            s_lower = s.lower()
            # If sentence contains any query keyword, keep it
            if any(w in s_lower for w in query_words):
                kept_sentences.append(s)
            # Also keep if it's very short (headings, dates)
            elif len(s) < 45 and not any(ch in s for ch in ['.', '!', '?']):
                kept_sentences.append(s)
                
        # If too few sentences kept, fall back to full text
        if len(kept_sentences) < len(sentences) * 0.3 or len(kept_sentences) < 2:
            return text
            
        return " ".join(kept_sentences)

    def retrieve_relevant_chunks(
        self,
        query_embedding: List[float],
        doc_id: Optional[str] = None,
        top_k: int = 3,
        similarity_threshold: float = 0.0,
        query: Optional[str] = None,
        intent: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieves and ranks the top-K non-overlapping chunks by cosine similarity score.
        Supports resume-aware ranking boosts and semantic compression.
        
        Args:
            query_embedding: Embedding vector of the query.
            doc_id: Specific document ID to filter by. If None, searches all docs.
            top_k: Maximum number of chunks to return.
            similarity_threshold: Minimum similarity score.
            query: Raw query text for context compression.
            intent: Optional query intent for section-specific boosts.
            
        Returns:
            List of ranked, deduplicated chunk dictionaries (including score details).
        """
        # Fetch candidate chunks
        if doc_id and doc_id != "all":
            chunks = storage_service.get_chunks(doc_id)
        else:
            chunks = storage_service.get_all_chunks()

        logger.info(
            f"Searching {len(chunks)} chunks (doc_id={doc_id}) with threshold={similarity_threshold}"
        )

        scored_chunks = []

        for chunk in chunks:
            chunk_embedding = chunk.get("embedding")
            if not chunk_embedding:
                continue

            score = self._cosine_similarity(query_embedding, chunk_embedding)
            
            # --- Resume-aware ranking boost ---
            # Prioritize matching sections based on intent
            sec = str(chunk.get("section", "")).lower()
            
            intent_lower = ""
            if intent:
                intent_lower = intent.lower()
            elif query:
                q_lower = query.lower()
                if any(k in q_lower for k in ["experience", "work", "employment", "career", "worked", "job", "history"]):
                    intent_lower = "experience"
                elif any(k in q_lower for k in ["education", "degree", "university", "college", "school", "graduate", "academic", "qualification"]):
                    intent_lower = "education"
                elif any(k in q_lower for k in ["skills", "technolog", "proficien", "language", "tool", "stack", "know"]):
                    intent_lower = "skills"
                elif any(k in q_lower for k in ["project", "build", "develop", "portfolio", "system", "app"]):
                    intent_lower = "projects"
                elif any(k in q_lower for k in ["certif", "award", "achieve", "training", "license"]):
                    intent_lower = "certifications"

            boost = 0.0
            if intent_lower == "experience":
                if any(kw in sec for kw in ["experience", "work", "employment", "history", "career"]):
                    boost = 0.15
            elif intent_lower == "education":
                if any(kw in sec for kw in ["education", "academic", "qualification", "degree", "schooling"]):
                    boost = 0.15
            elif intent_lower == "skills":
                if any(kw in sec for kw in ["skills", "technical skills", "technologies", "competencies", "expertise"]):
                    boost = 0.15
            elif intent_lower == "projects":
                if any(kw in sec for kw in ["projects", "portfolio", "applications", "built"]):
                    boost = 0.15
            elif intent_lower == "certifications":
                if any(kw in sec for kw in ["certifications", "certificates", "courses", "awards", "achievements"]):
                    boost = 0.15
            else:
                # Default V1 boost
                if any(kw in sec for kw in ["experience", "employment", "history", "profile", "projects"]):
                    boost = 0.05
                    
            score += boost

            if score >= similarity_threshold:
                # Store score and clean chunk mapping (remove raw float embedding from return payload)
                clean_chunk = {k: v for k, v in chunk.items() if k != "embedding"}
                clean_chunk["score"] = float(score)
                scored_chunks.append(clean_chunk)

        # Sort descending by score
        scored_chunks.sort(key=lambda x: x["score"], reverse=True)

        # --- Overlap-aware deduplication ---
        deduplicated = self._deduplicate_chunks(scored_chunks, overlap_threshold=0.65)

        results = deduplicated[:top_k]

        # --- Context Compression ---
        # Clean text sentences if query is provided to prioritize key entities matching the query
        if query:
            for r in results:
                r["text"] = self._compress_context(r["text"], query)

        # Print cosine similarity scores and retrieved chunks with clear section headers
        print("\n" + "="*80)
        print(f"DEBUG: RETRIEVAL MATCHING & SIMILARITY SCORES (Total Candidate Chunks: {len(chunks)})")
        print("="*80)
        print(f"Scored {len(scored_chunks)} chunks | After dedup: {len(deduplicated)}")
        print("Similarity scores for all matching candidate chunks:")
        for idx, chunk in enumerate(scored_chunks):
            dup_flag = " [SUPPRESSED-DUP]" if chunk not in deduplicated else ""
            print(f"  - Candidate ID: {chunk['chunk_id']} | Doc: {chunk['doc_id']} | Score: {chunk['score']:.4f}{dup_flag}")
        
        print("\n" + "-"*40)
        print(f"Top-{top_k} Retrieved Chunks (Matched, deduplicated):")
        print("-"*40)
        for rank, chunk in enumerate(results, 1):
            print(f"Rank {rank} | ID: {chunk['chunk_id']} | Doc: {chunk['doc_id']} | Page: {chunk['page_number']} | Score: {chunk['score']:.4f}")
            print(f"Text Content: \"{chunk['text']}\"")
            print("-"*40)
        print("="*80 + "\n")

        logger.info(f"Retrieved {len(results)} relevant chunks (after overlap dedup) matching search criteria.")
        return results


retrieval_service = RetrievalService()
