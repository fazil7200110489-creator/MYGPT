"""Search Coordinator for managing query preprocessing, retrieval, and re-ranking.
"""

from typing import Dict, Any, List, Optional
from loguru import logger

from backend.app.services.embedding_service import embedding_service
from backend.app.services.retrieval_service import retrieval_service


class SearchCoordinator:
    """Orchestrates query representation and semantic document retrieval stages.
    
    Supports future hybrid search integrations.
    """

    def search(
        self,
        query: str,
        doc_id: Optional[str] = None,
        top_k: int = 3,
        similarity_threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Coordinates embedding query text and calling similarity retrieval.
        
        Args:
            query: User search question string.
            doc_id: Active document session ID filter (None/all maps to global search).
            top_k: Top results counts limit.
            similarity_threshold: Minimum cosine score threshold.
            
        Returns:
            Ranked list of matching source chunks.
        """
        logger.info(f"Coordinating search for query: '{query}' (doc_id={doc_id})")

        # 1. Represent query using local embedding service
        embeddings = embedding_service.get_embeddings([query])
        if not embeddings:
            logger.warning("Failed to generate query embedding representation vector.")
            return []
            
        query_vector = embeddings[0]

        # 2. Query stored vectors
        retrieved_chunks = retrieval_service.retrieve_relevant_chunks(
            query_embedding=query_vector,
            doc_id=doc_id,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            query=query
        )

        # 3. Optional future step: Re-ranking/Keyword Hybrid blend
        # For version 2: return standard ranked list
        return retrieved_chunks


search_coordinator = SearchCoordinator()
