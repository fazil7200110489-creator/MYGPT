"""Model module for MyGPT.

This module implements the complete GPT-style Transformer language model
by stacking embeddings, positional encodings, and TransformerBlocks, ending
with the projection language model head.
"""

import torch
import torch.nn as nn
from typing import Tuple, List
from src.embeddings import CustomEmbedding
from src.positional_encoding import SinusoidalPositionalEncoding
from src.transformer_block import TransformerBlock
from src.layer_norm import LayerNorm


class GPTConfig:
    """Configuration class for GPT model hyperparameters."""

    def __init__(
        self,
        vocab_size: int = 80,
        context_len: int = 128,
        embedding_dim: int = 64,
        num_heads: int = 4,
        hidden_dim: int = 256,
        num_layers: int = 3,
        dropout: float = 0.1,
    ) -> None:
        """Initializes the configuration.

        Args:
            vocab_size: Vocabulary size.
            context_len: Maximum context/sequence length (block size).
            embedding_dim: Embedding dimension (d_model).
            num_heads: Number of attention heads.
            hidden_dim: FFN hidden dimension.
            num_layers: Number of stacked Transformer blocks.
            dropout: Dropout rate.
        """
        self.vocab_size = vocab_size
        self.context_len = context_len
        self.embedding_dim = embedding_dim
        self.num_heads = num_heads
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.dropout = dropout


class GPT(nn.Module):
    """The GPT-style autoregressive language model."""

    def __init__(self, config: GPTConfig) -> None:
        """Initializes the GPT model.

        Args:
            config: An instance of GPTConfig.
        """
        super().__init__()
        self.config = config

        # Token embedding layer
        self.token_embeddings = CustomEmbedding(
            vocab_size=config.vocab_size, embedding_dim=config.embedding_dim
        )
        
        # Absolute positional encoding layer (using sinusoidal waves)
        self.pos_embeddings = SinusoidalPositionalEncoding(
            max_seq_len=config.context_len, embedding_dim=config.embedding_dim
        )

        # Stacking multiple Transformer Blocks together
        self.blocks = nn.ModuleList([
            TransformerBlock(
                embedding_dim=config.embedding_dim,
                num_heads=config.num_heads,
                hidden_dim=config.hidden_dim,
                dropout=config.dropout,
            )
            for _ in range(config.num_layers)
        ])

        # Final pre-head LayerNorm layer
        self.ln_f = LayerNorm(normalized_shape=config.embedding_dim)

        # Language modeling head (projecting embedding representations to vocabulary logits)
        self.lm_head = nn.Linear(config.embedding_dim, config.vocab_size, bias=False)

        # Weight tying: share the token embeddings weight matrix with the LM head projection
        # This reduces parameter counts and helps stabilize training
        self.lm_head.weight = self.token_embeddings.weight

        # Apply custom standard initialization to other linear projections
        self.apply(self._init_weights)

    def _init_weights(self, module: nn.Module) -> None:
        """Applies normal distribution weights and zero biases to linear layers."""
        if isinstance(module, nn.Linear):
            # Do not re-initialize the tied lm_head
            if module is not self.lm_head:
                nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                nn.init.zeros_(module.bias)

    def forward(self, idx: torch.Tensor) -> Tuple[torch.Tensor, List[torch.Tensor]]:
        """Performs the forward pass.

        Args:
            idx: Integer tensor of token IDs with shape (batch_size, seq_len).

        Returns:
            A tuple of:
              - Logits tensor of shape (batch_size, seq_len, vocab_size).
              - List of attention weight matrices from each layer.
        """
        _, seq_len = idx.shape
        if seq_len > self.config.context_len:
            raise ValueError(
                f"Input sequence length {seq_len} exceeds context length "
                f"limit of {self.config.context_len}."
            )

        # 1. Fetch token and positional embeddings
        # shape: (batch_size, seq_len, embedding_dim)
        x = self.token_embeddings(idx)
        x = self.pos_embeddings(x)

        # 2. Sequential forward propagation through blocks
        # Storing attention weights for visualization and inspection
        attention_matrices = []
        for block in self.blocks:
            x, attn_weights = block(x)
            attention_matrices.append(attn_weights)

        # 3. Final layer normalization
        x = self.ln_f(x)

        # 4. Compute final output logits: (batch_size, seq_len, vocab_size)
        logits = self.lm_head(x)

        return logits, attention_matrices
