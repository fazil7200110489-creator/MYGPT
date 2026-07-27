"""Search Service for word, phrase, and semantic vector queries.
"""

from typing import Dict, Any, List, Optional
import re
from loguru import logger

from backend.app.services.storage_service import storage_service
from backend.app.services.retrieval_service import retrieval_service
from backend.app.services.embedding_service import embedding_service


class SearchService:
    """Handles exact term, phrase, and semantic matches over local document databases."""

    def search(
        self,
        query: str,
        doc_id: Optional[str] = None,
        search_type: str = "hybrid",
        top_k: int = 3,
        similarity_threshold: float = 0.0,
        context_summary: Optional[str] = None,
        intent: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Searches local vector chunks using word, phrase, semantic, or hybrid models.
        
        Args:
            query: User search term.
            doc_id: Active document ID filter.
            search_type: Mode of search ('word', 'phrase', 'semantic', 'hybrid').
            top_k: Limit returned results.
            similarity_threshold: Cosine similarity cutoff.
            context_summary: Optional trailing dialogue summary to prepend for semantic search coherence.
            intent: Optional query intent for section-specific boosts.
            
        Returns:
            List of matches: [{"page_number": int, "chunk_id": str, "text": str, "similarity": float}]
        """
        logger.info(f"RETRIEVAL START")
        logger.info(f"TOP K: {top_k}")
        logger.info(f"SIMILARITY: {similarity_threshold}")
        logger.info(f"Search mode triggered: {search_type} for query: '{query}'")

        if not query.strip():
            return []

        # Get candidate chunks
        if doc_id and doc_id != "all":
            chunks = storage_service.get_chunks(doc_id)
        else:
            chunks = storage_service.get_all_chunks()

        # Deduplicate float embeddings from returned payloads
        clean_chunks = []
        for c in chunks:
            clean_chunk = {k: v for k, v in c.items() if k != "embedding"}
            clean_chunk["similarity"] = 0.0
            clean_chunks.append(clean_chunk)

        query_lower = query.lower().strip()
        query_words = set(re.findall(r"\w+", query_lower))

        # Prep embedding query for semantic models
        embedding_query = f"{context_summary} {query}" if context_summary else query

        results = []

        if search_type == "word":
            # Alphanumeric keyword subset inclusion
            for c in clean_chunks:
                c_text_lower = c["text"].lower()
                c_words = set(re.findall(r"\w+", c_text_lower))
                if query_words.issubset(c_words):
                    c["similarity"] = 1.0
                    results.append(c)

        elif search_type == "phrase":
            # Exact phrase substring occurrence
            for c in clean_chunks:
                if query_lower in c["text"].lower():
                    c["similarity"] = 1.0
                    results.append(c)

        elif search_type == "semantic":
            # Embed search query using local MyGPT model
            q_emb = embedding_service.get_embeddings([embedding_query])[0]
            # Match similarities
            retrieved = retrieval_service.retrieve_relevant_chunks(
                query_embedding=q_emb,
                doc_id=doc_id,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                query=query_lower,
                intent=intent
            )
            for r in retrieved:
                r["similarity"] = r.get("score", 0.0)
                results.append(r)

        else:  # "hybrid"
            # Combine semantic similarity with keyword match overlap bonuses
            q_emb = embedding_service.get_embeddings([embedding_query])[0]
            retrieved = retrieval_service.retrieve_relevant_chunks(
                query_embedding=q_emb,
                doc_id=doc_id,
                top_k=len(clean_chunks),
                similarity_threshold=0.0,
                query=query_lower,
                intent=intent
            )
            
            for r in retrieved:
                score = r.get("score", 0.0)
                r_text_lower = r["text"].lower()
                r_words = set(re.findall(r"\w+", r_text_lower))
                
                # Check for phrase match bonus
                if query_lower in r_text_lower:
                    score += 0.2
                # Check for keyword overlap bonus
                overlap = len(query_words.intersection(r_words))
                if len(query_words) > 0:
                    score += 0.1 * (overlap / len(query_words))
                
                r["similarity"] = min(float(score), 1.0)
                if r["similarity"] >= similarity_threshold:
                    results.append(r)

        # Sort and limit results
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]


search_service = SearchService()
