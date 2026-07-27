"""Embedding Service defining an interface and MyGPT model concrete implementation.
"""

from abc import ABC, abstractmethod
from typing import List
import torch
from loguru import logger

from backend.app.services.model_manager import model_manager
from backend.app.services.tokenizer_service import tokenizer


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


class MyGPTEmbedding(EmbeddingInterface):
    """Concrete embedding generator using MyGPT's internal representations."""

    def __init__(self) -> None:
        logger.info("Initializing MyGPTEmbedding provider.")

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generates embeddings using the MyGPT model's weights and layers.
        
        Uses token embeddings, positional encodings, transformer blocks, 
        and performs mean-pooling over the sequence dimension.
        
        Args:
            texts: List of text segments to encode.
            
        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []

        # Load active model from ModelManager
        model = model_manager.load_model()
        model.eval()

        device = model_manager.device
        context_len = model.config.context_len
        embedding_dim = model.config.embedding_dim

        embeddings = []

        for text in texts:
            if not text.strip():
                # Zero vector fallback for empty text
                embeddings.append([0.0] * embedding_dim)
                continue

            try:
                # Tokenize text using the BPE tokenizer
                ids = tokenizer.encode(text)
                if not ids:
                    ids = [tokenizer.w2i.get(tokenizer.bos_token, 2)]

                # Crop sequence length to fit model's max positional context
                if len(ids) > context_len:
                    ids = ids[-context_len:]

                # Move input to device
                input_tensor = torch.tensor([ids], dtype=torch.long, device=device)

                with torch.no_grad():
                    # Replicate model forward pass layers up to ln_f
                    # 1. Embed tokens
                    x = model.token_embeddings(input_tensor)
                    # 2. Add positional encoding
                    x = model.pos_embeddings(x)
                    # 3. Propagate through stacked Transformer Blocks
                    for block in model.blocks:
                        x, _ = block(x)
                    # 4. Apply pre-head normalizer
                    x = model.ln_f(x)
                    # Mean-pool along sequence dimension (dim=1) to yield dense sentence vector
                    pooled = x.mean(dim=1).squeeze(0)
                    vector = pooled.cpu().numpy().tolist()
                    embeddings.append(vector)
            except Exception as e:
                logger.error(f"Failed to generate embedding for text '{text[:30]}...': {e}")
                # Fallback to zero vector on error
                embeddings.append([0.0] * embedding_dim)

        return embeddings



# Instantiate MyGPT embedding service
embedding_service = MyGPTEmbedding()
