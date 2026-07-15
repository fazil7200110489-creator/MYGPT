"""Embeddings module for MyGPT.

This module implements:
1. A custom embedding layer built from first principles using tensor indexing.
2. An embedding layer wrapping PyTorch's native nn.Embedding.
"""

import torch
import torch.nn as nn


class CustomEmbedding(nn.Module):
    """Custom embedding layer built from first principles using tensor indexing."""

    def __init__(self, vocab_size: int, embedding_dim: int) -> None:
        """Initializes the custom embedding layer.

        Args:
            vocab_size: Size of the vocabulary.
            embedding_dim: Dimension of each dense embedding vector.
        """
        super().__init__()
        self.vocab_size = vocab_size
        self.embedding_dim = embedding_dim
        
        # Initialize the embedding matrix as a trainable parameter
        # Standard GPT initialization: normal distribution with mean=0, std=0.02
        self.weight = nn.Parameter(torch.randn(vocab_size, embedding_dim) * 0.02)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Performs embedding lookup via tensor indexing.

        Args:
            x: An integer tensor of token IDs with shape (batch_size, sequence_length).

        Returns:
            A float tensor of embedding vectors with shape
            (batch_size, sequence_length, embedding_dim).
        """
        # Retrieve dense vectors directly using PyTorch index selection.
        # This operates as a lookup operation equivalent to standard matrix indexing.
        return self.weight[x]


class PyTorchEmbedding(nn.Module):
    """Embedding layer wrapping PyTorch's native nn.Embedding."""

    def __init__(self, vocab_size: int, embedding_dim: int) -> None:
        """Initializes the PyTorch embedding layer.

        Args:
            vocab_size: Size of the vocabulary.
            embedding_dim: Dimension of each dense embedding vector.
        """
        super().__init__()
        self.vocab_size = vocab_size
        self.embedding_dim = embedding_dim
        self.embedding = nn.Embedding(vocab_size, embedding_dim)

        # Initialize the native weights to match standard GPT setup (mean=0.0, std=0.02)
        # for a fair numerical comparison
        with torch.no_grad():
            self.embedding.weight.normal_(mean=0.0, std=0.02)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Performs embedding lookup using PyTorch's native nn.Embedding.

        Args:
            x: An integer tensor of token IDs with shape (batch_size, sequence_length).

        Returns:
            A float tensor of embedding vectors with shape
            (batch_size, sequence_length, embedding_dim).
        """
        return self.embedding(x)
