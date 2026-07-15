"""Positional encoding module for MyGPT.

This module implements sinusoidal positional encoding to inject absolute sequence
order information into token embeddings.
"""

import math
import torch
import torch.nn as nn


class SinusoidalPositionalEncoding(nn.Module):
    """Sinusoidal Positional Encoding layer from scratch.

    Computes sine and cosine waves of different frequencies to represent
    token positions.
    """

    def __init__(self, max_seq_len: int, embedding_dim: int) -> None:
        """Initializes the sinusoidal positional encoding layer.

        Args:
            max_seq_len: Maximum sequence length supported by the encoding.
            embedding_dim: Dimensionality of the embeddings.
        """
        super().__init__()
        self.max_seq_len = max_seq_len
        self.embedding_dim = embedding_dim

        # Initialize the positional encoding matrix with zeros
        pe = torch.zeros(max_seq_len, embedding_dim)
        
        # position tensor shape: (max_seq_len, 1)
        position = torch.arange(0, max_seq_len, dtype=torch.float).unsqueeze(1)
        
        # division term for the sinusoidal frequencies: 10000^(2i/embedding_dim)
        # computed in the log domain for numerical stability
        # We step by 2 to compute shared frequencies for sine and cosine pairs
        div_term = torch.exp(
            torch.arange(0, embedding_dim, 2).float() * (-math.log(10000.0) / embedding_dim)
        )

        # Apply sine to even indices (0, 2, 4, ...)
        pe[:, 0::2] = torch.sin(position * div_term)
        
        # Apply cosine to odd indices (1, 3, 5, ...)
        # Handle odd dimensions gracefully: slice to match odd sequence spaces
        pe[:, 1::2] = torch.cos(position * div_term[: embedding_dim // 2])

        # Register the matrix as a PyTorch buffer.
        # This keeps the parameters non-trainable, but attaches them to the model state,
        # ensuring they are saved with checkpoints and moved with .to(device) calls.
        # We add an extra dimension at the start for batch broadcasting: (1, max_seq_len, embedding_dim)
        self.register_buffer("pe", pe.unsqueeze(0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Adds positional encodings to the input embeddings.

        Args:
            x: A tensor of shape (batch_size, seq_len, embedding_dim).

        Returns:
            The position-aware embedding tensor of shape
            (batch_size, seq_len, embedding_dim).
        """
        seq_len = x.size(1)
        if seq_len > self.max_seq_len:
            raise ValueError(
                f"Input sequence length {seq_len} exceeds max_seq_len {self.max_seq_len}."
            )

        # Add the positional encoding slice to the inputs.
        # self.pe[:, :seq_len, :] has shape (1, seq_len, embedding_dim).
        # PyTorch automatically broadcasts the batch dimension to match x.
        return x + self.pe[:, :seq_len, :]
