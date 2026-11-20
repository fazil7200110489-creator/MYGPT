"""Local Vector Indexing Service using FAISS and FastEmbed for MYGPT Hybrid RAG.

Enforces:
1. 100% local CPU inference via ONNX Runtime (BAAI/bge-small-en-v1.5, 384-dim).
2. Exact Cosine Similarity (IndexFlatIP on L2-normalized embeddings).
3. Persistent disk storage isolated per tender document.
4. Instant index reloading from disk cache.
5. Resource-safe single-threaded execution (threads=1) and bounded batching (batch_size=32).
6. Memory safety with bounded in-memory LRU cache and immediate release of temporary arrays.
7. Stage-level telemetry logging for every embedding batch and FAISS construction.
"""

import os
import json
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from loguru import logger

try:
    import faiss
except ImportError:
    faiss = None

try:
    from fastembed import TextEmbedding
except ImportError:
    TextEmbedding = None

from .structure_chunker import TenderChunk
from backend.app.services.tender_intelligence.resource_monitor import resource_monitor

_INDEX_STORAGE_DIR = os.path.join("data", "rag_indices")
_EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
_EMBEDDING_DIM = 384
_EMBEDDING_BATCH_SIZE = 32
_EMBEDDING_THREADS = 1
_MAX_IN_MEMORY_INDICES = 5


class LocalEmbeddingProvider:
    """Manages the lightweight CPU embedding model instance with strict thread and memory safety."""

    _instance: Optional["LocalEmbeddingProvider"] = None
    _embedder: Optional[Any] = None

    def __new__(cls) -> "LocalEmbeddingProvider":
        if cls._instance is None:
            cls._instance = super(LocalEmbeddingProvider, cls).__new__(cls)
            cls._instance._init_embedder()
        return cls._instance

    def _init_embedder(self) -> None:
        if TextEmbedding is not None:
            try:
                t0 = time.time()
                # Initialize with exactly 1 thread to prevent multi-core thermal and CPU saturation
                self._embedder = TextEmbedding(
                    model_name=_EMBEDDING_MODEL_NAME,
                    threads=_EMBEDDING_THREADS,
                )
                logger.info(
                    f"[LOCAL_EMBEDDER] Initialized {_EMBEDDING_MODEL_NAME} "
                    f"(384-dim, ONNX, threads={_EMBEDDING_THREADS}, batch_size={_EMBEDDING_BATCH_SIZE}) "
                    f"in {time.time() - t0:.2f}s"
                )
            except Exception as e:
                logger.error(f"[LOCAL_EMBEDDER] Failed to initialize FastEmbed: {e}")
                self._embedder = None
        else:
            logger.warning("[LOCAL_EMBEDDER] fastembed not installed. Vector search disabled.")
            self._embedder = None

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """Generates L2-normalized float32 embeddings sequentially in bounded batches of 32."""
        if not texts or self._embedder is None:
            return np.zeros((len(texts), _EMBEDDING_DIM), dtype=np.float32)

        total_texts = len(texts)
        num_batches = (total_texts + _EMBEDDING_BATCH_SIZE - 1) // _EMBEDDING_BATCH_SIZE

        # Pre-allocate output matrix to avoid unbounded list growth in memory
        embeddings = np.empty((total_texts, _EMBEDDING_DIM), dtype=np.float32)

        try:
            for b_idx in range(num_batches):
                start_idx = b_idx * _EMBEDDING_BATCH_SIZE
                end_idx = min(start_idx + _EMBEDDING_BATCH_SIZE, total_texts)
                batch_slice = texts[start_idx:end_idx]
                t_batch_start = time.time()

                # Process batch slice sequentially
                raw_batch = list(self._embedder.embed(batch_slice, batch_size=_EMBEDDING_BATCH_SIZE))
                batch_arr = np.array(raw_batch, dtype=np.float32)
                embeddings[start_idx:end_idx] = batch_arr

                # Release intermediate batch array immediately
                del raw_batch
                del batch_arr

                # Log stage-level telemetry for each embedding batch
                resource_monitor.log_stage(
                    stage_name="embedding_batch",
                    start_time=t_batch_start,
                    extra={
                        "batch_num": b_idx + 1,
                        "total_batches": num_batches,
                        "batch_size": end_idx - start_idx,
                        "vectors_completed": end_idx,
                        "total_vectors": total_texts,
                    },
                )

            # In-place L2 normalization for cosine similarity
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            embeddings /= norms
            del norms
            return embeddings

        except Exception as e:
            logger.error(f"[LOCAL_EMBEDDER] Embedding generation error: {e}")
            return np.zeros((total_texts, _EMBEDDING_DIM), dtype=np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        """Embeds single query string into 1x384 float32 vector."""
        return self.embed_texts([query])


class TenderVectorIndex:
    """Isolated persistent FAISS vector index for a single tender document."""

    def __init__(self, doc_hash: str) -> None:
        self.doc_hash = doc_hash
        self.index: Optional[Any] = None
        self.chunks: List[TenderChunk] = []
        self.embedding_provider = LocalEmbeddingProvider()
        os.makedirs(_INDEX_STORAGE_DIR, exist_ok=True)
        self.index_file = os.path.join(_INDEX_STORAGE_DIR, f"{doc_hash}.faiss")
        self.meta_file = os.path.join(_INDEX_STORAGE_DIR, f"{doc_hash}_meta.json")

    def exists(self) -> bool:
        """Checks if pre-built persistent index exists on disk."""
        return os.path.exists(self.index_file) and os.path.exists(self.meta_file)

    def load_from_disk(self) -> bool:
        """Loads index and chunk metadata from disk if available."""
        if not self.exists() or faiss is None:
            return False

        try:
            t0 = time.time()
            self.index = faiss.read_index(self.index_file)
            with open(self.meta_file, "r", encoding="utf-8") as f:
                meta_json = json.load(f)
            self.chunks = [TenderChunk(**c) for c in meta_json.get("chunks", [])]
            logger.info(
                f"[TENDER_VECTOR_INDEX] Loaded {len(self.chunks)} vectors for hash={self.doc_hash[:12]} "
                f"from disk in {time.time() - t0:.3f}s"
            )
            return True
        except Exception as e:
            logger.warning(f"[TENDER_VECTOR_INDEX] Failed to load index {self.doc_hash}: {e}")
            self.index = None
            self.chunks = []
            return False

    def build_and_save(self, chunks: List[TenderChunk]) -> bool:
        """Embeds chunks in bounded batches, builds FAISS IndexFlatIP, and persists to disk."""
        if not chunks or faiss is None:
            return False

        t_build_start = time.time()
        texts = [c.text for c in chunks]

        # Sequential batch embedding with resource monitoring
        embeddings = self.embedding_provider.embed_texts(texts)

        # Build FAISS Flat Inner-Product Index (exact cosine similarity)
        t_faiss_start = time.time()
        index = faiss.IndexFlatIP(_EMBEDDING_DIM)
        index.add(embeddings)

        # Release numpy array immediately after transfer to FAISS C++ memory
        del embeddings

        self.index = index
        self.chunks = list(chunks)

        # Persist to disk
        try:
            faiss.write_index(index, self.index_file)
            meta_payload = {
                "doc_hash": self.doc_hash,
                "created_at": time.time(),
                "chunk_count": len(chunks),
                "chunks": [c.model_dump() for c in chunks],
            }
            with open(self.meta_file, "w", encoding="utf-8") as f:
                json.dump(meta_payload, f, ensure_ascii=False)
            del meta_payload

            resource_monitor.log_stage(
                stage_name="faiss_index_creation",
                start_time=t_faiss_start,
                extra={
                    "doc_hash": self.doc_hash[:12],
                    "chunk_count": len(chunks),
                    "total_vectors": index.ntotal,
                },
            )
            logger.info(
                f"[TENDER_VECTOR_INDEX] Built & saved {len(chunks)} vectors for {self.doc_hash[:12]} "
                f"in {time.time() - t_build_start:.2f}s"
            )
            return True
        except Exception as e:
            logger.error(f"[TENDER_VECTOR_INDEX] Failed saving index to disk: {e}")
            return False

    def search(
        self,
        query: str,
        top_k: int = 5,
        content_type: Optional[str] = None,
        min_page: Optional[int] = None,
        max_page: Optional[int] = None,
    ) -> List[Tuple[TenderChunk, float]]:
        """Performs semantic vector search with optional metadata filtering."""
        if self.index is None or not self.chunks or self.index.ntotal == 0:
            return []

        q_vec = self.embedding_provider.embed_query(query)
        fetch_k = min(top_k * 3, self.index.ntotal)
        scores, indices = self.index.search(q_vec, fetch_k)

        results: List[Tuple[TenderChunk, float]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.chunks):
                continue
            chunk = self.chunks[idx]

            # Metadata filtering
            if content_type and chunk.content_type != content_type:
                continue
            if min_page and chunk.page_number < min_page:
                continue
            if max_page and chunk.page_number > max_page:
                continue

            results.append((chunk, float(score)))
            if len(results) >= top_k:
                break

        return results

    def delete(self) -> None:
        """Purges index and metadata from disk and memory."""
        self.index = None
        self.chunks = []
        for fp in (self.index_file, self.meta_file):
            if os.path.exists(fp):
                try:
                    os.remove(fp)
                except Exception as e:
                    logger.warning(f"Failed to remove {fp}: {e}")


class TenderIndexRegistry:
    """Manages active in-memory TenderVectorIndex instances with bounded LRU eviction."""

    _indices: "OrderedDict[str, TenderVectorIndex]" = OrderedDict()

    @classmethod
    def get_or_create(cls, doc_hash: str, chunks: Optional[List[TenderChunk]] = None) -> TenderVectorIndex:
        """Retrieves loaded index or builds/loads it from disk, managing LRU bounded memory."""
        if doc_hash in cls._indices:
            cls._indices.move_to_end(doc_hash)
            idx = cls._indices[doc_hash]
            if idx.index is not None:
                return idx

        idx = TenderVectorIndex(doc_hash)
        if idx.load_from_disk():
            cls._register_index(doc_hash, idx)
            return idx

        if chunks:
            idx.build_and_save(chunks)
            cls._register_index(doc_hash, idx)
            return idx

        return idx

    @classmethod
    def _register_index(cls, doc_hash: str, idx: TenderVectorIndex) -> None:
        """Registers index and evicts oldest index from RAM if cache exceeds threshold."""
        if len(cls._indices) >= _MAX_IN_MEMORY_INDICES and doc_hash not in cls._indices:
            # Evict oldest in-memory index (its disk files remain persistent and safe)
            oldest_hash, oldest_idx = cls._indices.popitem(last=False)
            logger.info(
                f"[TENDER_INDEX_REGISTRY] Memory cache limit reached ({_MAX_IN_MEMORY_INDICES}). "
                f"Evicted index {oldest_hash[:12]} from RAM (persisted on disk)."
            )
            oldest_idx.index = None
            oldest_idx.chunks = []

        cls._indices[doc_hash] = idx
        cls._indices.move_to_end(doc_hash)

    @classmethod
    def delete_index(cls, doc_hash: str) -> None:
        """Removes index from registry and purges files."""
        if doc_hash in cls._indices:
            cls._indices[doc_hash].delete()
            del cls._indices[doc_hash]
        else:
            TenderVectorIndex(doc_hash).delete()


# Global index registry helper
tender_index_registry = TenderIndexRegistry
