"""Transformer Block module for MyGPT.

This module implements a single stack layer of a GPT-style decoder using the
Pre-LayerNorm architecture, self-attention, and a position-wise Feed-Forward Network.
"""

import torch
import torch.nn as nn
from typing import Tuple
from .layer_norm import LayerNorm
from .multi_head_attention import MultiHeadAttention
from .feed_forward import FeedForward
from .residual import ResidualConnection


class TransformerBlock(nn.Module):
    """A single Transformer Decoder block (GPT-style Pre-LayerNorm architecture)."""

    def __init__(self, embedding_dim: int, num_heads: int, hidden_dim: int, dropout: float = 0.0) -> None:
        """Initializes the TransformerBlock.

        Args:
            embedding_dim: Dimensionality of inputs (d_model).
            num_heads: Number of attention heads.
            hidden_dim: Dimensionality of FFN hidden layer (usually 4 * embedding_dim).
            dropout: Dropout probability.
        """
        super().__init__()

        # Pre-attention normalization and Multi-Head Attention
        self.ln1 = LayerNorm(normalized_shape=embedding_dim)
        self.attn = MultiHeadAttention(embedding_dim=embedding_dim, num_heads=num_heads)
        self.res1 = ResidualConnection()

        # Pre-FFN normalization and Feed-Forward Network
        self.ln2 = LayerNorm(normalized_shape=embedding_dim)
        self.ffn = FeedForward(embedding_dim=embedding_dim, hidden_dim=hidden_dim, dropout=dropout)
        self.res2 = ResidualConnection()

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Applies a Pre-LayerNorm Transformer Block forward pass.

        Args:
            x: Input float tensor of shape (batch_size, seq_len, embedding_dim).

        Returns:
            A tuple containing:
              - Output tensor of shape (batch_size, seq_len, embedding_dim).
              - Attention weights matrix of shape (batch_size, num_heads, seq_len, seq_len).
        """
        # Step 1: Normalization -> Attention -> Residual Add
        # x_norm1 has shape (batch_size, seq_len, embedding_dim)
        x_norm1 = self.ln1(x)
        # attn_out: (batch_size, seq_len, embedding_dim)
        # attn_weights: (batch_size, num_heads, seq_len, seq_len)
        attn_out, attn_weights = self.attn(x_norm1)
        # x: (batch_size, seq_len, embedding_dim)
        x = self.res1(x, attn_out)

        # Step 2: Normalization -> Feed-Forward -> Residual Add
        # x_norm2 has shape (batch_size, seq_len, embedding_dim)
        x_norm2 = self.ln2(x)
        # ffn_out: (batch_size, seq_len, embedding_dim)
        ffn_out = self.ffn(x_norm2)
        # x: (batch_size, seq_len, embedding_dim)
        x = self.res2(x, ffn_out)

        return x, attn_weights
