"""Hybrid Retrieval Service (BM25 + Semantic Vector Search) for MYGPT.

Implements:
1. BM25Okapi Lexical Search (token-level precision for dates, amounts, codes, numbers).
2. FAISS Dense Vector Search (semantic similarity for conceptual matching).
3. Reciprocal Rank Fusion (RRF) with dynamic intent-aware weighting.
4. Surrounding context window stitching for contiguous clauses.
5. Deduplication and exact source page citation preservation.
6. Resource-safe bounded in-memory BM25 caching with telemetry.
"""

import math
import re
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field
from loguru import logger

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    BM25Okapi = None

from .structure_chunker import TenderChunk
from .tender_vector_index import TenderVectorIndex, tender_index_registry
from backend.app.services.tender_intelligence.resource_monitor import resource_monitor

_MAX_BM25_CACHE_SIZE = 5


class HybridSearchResult(BaseModel):
    """Unified evidence retrieval result with relevance scoring and page provenance."""

    chunk_id: str
    doc_id: Optional[str] = None
    filename: str
    page_number: int
    content_type: str
    section_heading: Optional[str] = None
    clause_number: Optional[str] = None
    text: str
    raw_content: str
    score: float
    retrieval_source: str  # "hybrid_rrf" | "vector_only" | "bm25_only"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HybridRetriever:
    """Combines BM25 and FAISS vector retrieval using Reciprocal Rank Fusion."""

    def __init__(self, rrf_k: int = 60) -> None:
        self.rrf_k = rrf_k
        self._bm25_cache: "OrderedDict[str, Tuple[Any, List[TenderChunk]]]" = OrderedDict()

    def _tokenize(self, text: str) -> List[str]:
        """Simple, fast lowercase alphanumeric tokenizer for BM25."""
        return re.findall(r"\b[a-zA-Z0-9_\-\.]{2,}\b", text.lower())

    def _get_or_create_bm25(self, doc_hash: str, chunks: List[TenderChunk]) -> Optional[Any]:
        """Caches in-memory BM25Okapi index per document hash with bounded LRU eviction."""
        if doc_hash in self._bm25_cache:
            self._bm25_cache.move_to_end(doc_hash)
            return self._bm25_cache[doc_hash][0]

        if not chunks or BM25Okapi is None:
            return None

        t_bm25_start = time.time()
        corpus = [self._tokenize(c.text) for c in chunks]
        bm25 = BM25Okapi(corpus)

        # Bounded LRU eviction
        if len(self._bm25_cache) >= _MAX_BM25_CACHE_SIZE and doc_hash not in self._bm25_cache:
            oldest_key, _ = self._bm25_cache.popitem(last=False)
            logger.info(f"[HYBRID_RETRIEVER] Evicted BM25 cache for {oldest_key[:12]}")

        self._bm25_cache[doc_hash] = (bm25, chunks)
        self._bm25_cache.move_to_end(doc_hash)

        resource_monitor.log_stage(
            stage_name="bm25_indexing",
            start_time=t_bm25_start,
            extra={
                "doc_hash": doc_hash[:12],
                "chunk_count": len(chunks),
                "corpus_size": len(corpus),
            },
        )
        return bm25

    def search(
        self,
        doc_hash: str,
        query: str,
        chunks: Optional[List[TenderChunk]] = None,
        top_k: int = 5,
        content_type: Optional[str] = None,
        min_page: Optional[int] = None,
        max_page: Optional[int] = None,
        expand_context: bool = True,
    ) -> List[HybridSearchResult]:
        """Executes Hybrid (BM25 + FAISS Vector) search with Reciprocal Rank Fusion."""
        if not query or not query.strip():
            return []

        t_search_start = time.time()

        # 1. Obtain or Load Vector Index
        vec_index = tender_index_registry.get_or_create(doc_hash, chunks=chunks)
        effective_chunks = vec_index.chunks or chunks or []
        if not effective_chunks:
            return []

        # 2. Vector Search (Top 2 * top_k)
        vector_results: List[Tuple[TenderChunk, float]] = []
        if vec_index.index is not None:
            vector_results = vec_index.search(
                query,
                top_k=top_k * 2,
                content_type=content_type,
                min_page=min_page,
                max_page=max_page,
            )

        # 3. BM25 Search (Top 2 * top_k)
        bm25 = self._get_or_create_bm25(doc_hash, effective_chunks)
        bm25_results: List[Tuple[TenderChunk, float]] = []
        if bm25 is not None:
            tokens = self._tokenize(query)
            if tokens:
                doc_scores = bm25.get_scores(tokens)
                top_indices = sorted(range(len(doc_scores)), key=lambda i: doc_scores[i], reverse=True)
                for idx in top_indices:
                    c = effective_chunks[idx]
                    sc = float(doc_scores[idx])
                    if sc <= 0.0:
                        break
                    # Filters
                    if content_type and c.content_type != content_type:
                        continue
                    if min_page and c.page_number < min_page:
                        continue
                    if max_page and c.page_number > max_page:
                        continue
                    bm25_results.append((c, sc))
                    if len(bm25_results) >= top_k * 2:
                        break

        # 4. Intent-Aware Fusion Weighting
        q_lower = query.lower()
        has_exact_signals = bool(
            re.search(r"\b\d+[\.,\d]*\b", query)
            or any(k in q_lower for k in ("rs.", "inr", "crore", "lakh", "%", "section", "clause"))
        )
        w_bm25 = 0.55 if has_exact_signals else 0.40
        w_vec = 0.45 if has_exact_signals else 0.60

        # 5. Reciprocal Rank Fusion (RRF)
        fused_scores: Dict[str, float] = {}
        chunk_map: Dict[str, TenderChunk] = {}
        source_map: Dict[str, str] = {}

        # Process Vector Rankings
        for rank, (chunk, _) in enumerate(vector_results, start=1):
            cid = chunk.chunk_id
            chunk_map[cid] = chunk
            fused_scores[cid] = fused_scores.get(cid, 0.0) + (w_vec / (self.rrf_k + rank))
            source_map[cid] = "vector"

        # Process BM25 Rankings
        for rank, (chunk, _) in enumerate(bm25_results, start=1):
            cid = chunk.chunk_id
            chunk_map[cid] = chunk
            fused_scores[cid] = fused_scores.get(cid, 0.0) + (w_bm25 / (self.rrf_k + rank))
            if cid in source_map and source_map[cid] == "vector":
                source_map[cid] = "hybrid_rrf"
            else:
                source_map[cid] = "bm25"

        ranked_cids = sorted(fused_scores.keys(), key=lambda c: fused_scores[c], reverse=True)

        # 6. Assemble Final Results & Optional Context Stitching
        final_results: List[HybridSearchResult] = []
        chunks_by_id = {c.chunk_id: c for c in effective_chunks}

        for cid in ranked_cids[:top_k]:
            target_chunk = chunk_map[cid]
            assembled_text = target_chunk.text
            assembled_raw = target_chunk.raw_content

            # Expand surrounding context for clauses if requested
            if expand_context and target_chunk.content_type == "clause":
                prev_c = chunks_by_id.get(target_chunk.prev_chunk_id or "")
                next_c = chunks_by_id.get(target_chunk.next_chunk_id or "")
                parts = []
                if prev_c and prev_c.page_number == target_chunk.page_number and prev_c.content_type == "clause":
                    parts.append(prev_c.raw_content[:250] + " ...")
                parts.append(assembled_raw)
                if next_c and next_c.page_number == target_chunk.page_number and next_c.content_type == "clause":
                    parts.append("... " + next_c.raw_content[:250])
                assembled_raw = "\n\n".join(parts)

            final_results.append(
                HybridSearchResult(
                    chunk_id=target_chunk.chunk_id,
                    doc_id=target_chunk.doc_id,
                    filename=target_chunk.filename,
                    page_number=target_chunk.page_number,
                    content_type=target_chunk.content_type,
                    section_heading=target_chunk.section_heading,
                    clause_number=target_chunk.clause_number,
                    text=assembled_text,
                    raw_content=assembled_raw,
                    score=round(fused_scores[cid], 5),
                    retrieval_source=source_map.get(cid, "hybrid_rrf"),
                    metadata=target_chunk.metadata,
                )
            )

        resource_monitor.log_stage(
            stage_name="hybrid_retrieval",
            start_time=t_search_start,
            extra={
                "doc_hash": doc_hash[:12],
                "top_k": top_k,
                "vector_candidates": len(vector_results),
                "bm25_candidates": len(bm25_results),
                "fused_results": len(final_results),
            },
        )
        return final_results


# Global singleton retriever instance
hybrid_retriever = HybridRetriever()
