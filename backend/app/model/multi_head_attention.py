"""Multi-Head Self-Attention module for MyGPT.

This module implements parallel causal self-attention projections over multiple
subspace heads, followed by output projection mixing.
"""

import math
import torch
import torch.nn as nn
from typing import Tuple


class MultiHeadAttention(nn.Module):
    """Multi-Head Self-Attention layer built from scratch."""

    def __init__(self, embedding_dim: int, num_heads: int) -> None:
        """Initializes the multi-head self-attention layer.

        Args:
            embedding_dim: Dimensionality of token representations.
            num_heads: Number of attention heads.
        """
        super().__init__()
        
        # Verify divisibility
        if embedding_dim % num_heads != 0:
            raise ValueError(
                f"embedding_dim ({embedding_dim}) must be cleanly divisible by "
                f"num_heads ({num_heads})."
            )

        self.embedding_dim = embedding_dim
        self.num_heads = num_heads
        self.head_dim = embedding_dim // num_heads

        # Linear projections for Query, Key, and Value
        self.q_proj = nn.Linear(embedding_dim, embedding_dim, bias=True)
        self.k_proj = nn.Linear(embedding_dim, embedding_dim, bias=True)
        self.v_proj = nn.Linear(embedding_dim, embedding_dim, bias=True)

        # Output projection (mixes heads together)
        self.out_proj = nn.Linear(embedding_dim, embedding_dim, bias=True)

        # Scale factor for scaled dot-product attention
        self.scale = 1.0 / math.sqrt(self.head_dim)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Performs multi-head causal self-attention on input embeddings.

        Args:
            x: A float tensor of shape (batch_size, seq_len, embedding_dim).

        Returns:
            A tuple containing:
              - Output tensor of shape (batch_size, seq_len, embedding_dim).
              - Attention weights matrix of shape (batch_size, num_heads, seq_len, seq_len).
        """
        batch_size, seq_len, _ = x.shape

        # 1. Compute projections Q, K, V
        # Shape: (batch_size, seq_len, embedding_dim)
        q = self.q_proj(x)
        k = self.k_proj(x)
        v = self.v_proj(x)

        # 2. Reshape and Transpose to split into parallel heads
        # Step 1: view splits embedding_dim into (num_heads, head_dim)
        #         Shape: (batch_size, seq_len, num_heads, head_dim)
        # Step 2: transpose swaps seq_len and num_heads dimensions
        #         Shape: (batch_size, num_heads, seq_len, head_dim)
        q = q.view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
        k = k.view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
        v = v.view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)

        # 3. Compute attention scores: Q * K^T
        # Transpose last two dimensions of K: (batch_size, num_heads, head_dim, seq_len)
        # Resulting scores shape: (batch_size, num_heads, seq_len, seq_len)
        scores = torch.matmul(q, k.transpose(-2, -1)) * self.scale

        # 4. Apply Causal Masking
        # Mask shape: (1, 1, seq_len, seq_len) to broadcast across batch and heads
        mask = torch.tril(torch.ones(seq_len, seq_len, device=x.device)).view(1, 1, seq_len, seq_len)
        scores = scores.masked_fill(mask == 0, float("-inf"))

        # 5. Compute attention weights via Softmax
        # Shape: (batch_size, num_heads, seq_len, seq_len)
        weights = torch.softmax(scores, dim=-1)

        # 6. Compute attention output: Weights * V
        # Shape: (batch_size, num_heads, seq_len, head_dim)
        out = torch.matmul(weights, v)

        # 7. Concatenate all heads back
        # Step 1: Transpose back: (batch_size, seq_len, num_heads, head_dim)
        # Step 2: contiguous() allocates a sequential block in memory
        # Step 3: view flattens last two dimensions back to embedding_dim
        #         Shape: (batch_size, seq_len, embedding_dim)
        out = out.transpose(1, 2).contiguous().view(batch_size, seq_len, self.embedding_dim)

        # 8. Apply final mixing output projection
        out = self.out_proj(out)

        return out, weights
