"""Causal Self-Attention module for MyGPT.

This module implements scaled dot-product attention with causal masking to support
autoregressive text generation.
"""

import math
import torch
import torch.nn as nn
from typing import Tuple


class CausalSelfAttention(nn.Module):
    """Causal Self-Attention layer built from first principles."""

    def __init__(self, embedding_dim: int) -> None:
        """Initializes the causal self-attention layer.

        Args:
            embedding_dim: Dimensionality of input token representations.
        """
        super().__init__()
        self.embedding_dim = embedding_dim

        # Query, Key, and Value linear projection layers
        self.q_proj = nn.Linear(embedding_dim, embedding_dim, bias=True)
        self.k_proj = nn.Linear(embedding_dim, embedding_dim, bias=True)
        self.v_proj = nn.Linear(embedding_dim, embedding_dim, bias=True)

        # Scale factor for scaled dot-product attention
        self.scale = 1.0 / math.sqrt(embedding_dim)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Performs causal self-attention on input embeddings.

        Args:
            x: A float tensor of shape (batch_size, seq_len, embedding_dim).

        Returns:
            A tuple containing:
              - The attention output tensor of shape (batch_size, seq_len, embedding_dim).
              - The attention weight matrix of shape (batch_size, seq_len, seq_len).
        """
        batch_size, seq_len, _ = x.shape

        # 1. Compute linear projections for Q, K, and V
        # Shapes: (batch_size, seq_len, embedding_dim)
        q = self.q_proj(x)
        k = self.k_proj(x)
        v = self.v_proj(x)

        # 2. Compute similarity scores: Q * K^T
        # Transpose K's last two dimensions: (batch_size, embedding_dim, seq_len)
        # Resulting scores shape: (batch_size, seq_len, seq_len)
        scores = torch.matmul(q, k.transpose(-2, -1)) * self.scale

        # 3. Apply Causal Masking
        # Create lower triangular boolean mask of shape (seq_len, seq_len)
        # registered on the same device as the inputs
        mask = torch.tril(torch.ones(seq_len, seq_len, device=x.device)).view(1, seq_len, seq_len)
        
        # Fill masked positions (zeros in the lower triangular mask) with negative infinity.
        # This causes them to evaluate to exactly 0 when softmax is computed.
        scores = scores.masked_fill(mask == 0, float("-inf"))

        # 4. Softmax normalization to compute attention weights
        # Shape: (batch_size, seq_len, seq_len)
        weights = torch.softmax(scores, dim=-1)

        # 5. Compute attention output: Weights * V
        # Shape: (batch_size, seq_len, embedding_dim)
        out = torch.matmul(weights, v)

        return out, weights
