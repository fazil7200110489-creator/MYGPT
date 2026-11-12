"""Embedding Service defining an interface and lightweight local deterministic embedding implementation.
"""

from abc import ABC, abstractmethod
import hashlib
import math
import re
from typing import List
from loguru import logger


class EmbeddingInterface(ABC):
    """Abstract interface defining the embedding generation operations."""

    @abstractmethod
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generates embedding vectors for a list of string texts.

        Args:
            texts: List of text blocks to embed.

        Returns:
            List of embedding lists (vectors).
        """
        pass


class LocalHashEmbedding(EmbeddingInterface):
    """Lightweight deterministic token-hash embedding generator (no PyTorch dependency)."""

    def __init__(self, dim: int = 64) -> None:
        self.dim = dim
        logger.info("Initializing LocalHashEmbedding provider.")

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generates L2-normalized deterministic hashing embeddings for texts."""
        if not texts:
            return []

        embeddings: List[List[float]] = []
        for text in texts:
            if not text or not text.strip():
                embeddings.append([0.0] * self.dim)
                continue

            vec = [0.0] * self.dim
            tokens = re.findall(r"[a-z0-9]+", text.lower())
            for tok in tokens:
                digest = hashlib.md5(tok.encode("utf-8")).digest()
                idx = int.from_bytes(digest[:2], "little") % self.dim
                sign = 1.0 if (digest[2] & 1) else -1.0
                vec[idx] += sign

            norm = math.sqrt(sum(v * v for v in vec))
            if norm > 0:
                vec = [v / norm for v in vec]
            embeddings.append(vec)

        return embeddings


# Instantiate embedding service
embedding_service = LocalHashEmbedding()
