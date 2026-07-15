"""Feed-Forward Network module for MyGPT.

This module implements the position-wise Feed-Forward Network (FFN) containing
a custom GELU activation layer, linear expansions, and dropout layers.
"""

import math
import torch
import torch.nn as nn


class GELU(nn.Module):
    """Gaussian Error Linear Unit (GELU) activation function from scratch.

    Computed using the exact erf-based formulation:
    GELU(x) = x * P(X <= x) = 0.5 * x * (1 + erf(x / sqrt(2)))
    """

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Applies GELU activation.

        Args:
            x: Input tensor.

        Returns:
            Activated tensor of the same shape as input.
        """
        # math.sqrt(2.0) is a constant. We divide x by it and pass it to torch.erf.
        return 0.5 * x * (1.0 + torch.erf(x / math.sqrt(2.0)))


class FeedForward(nn.Module):
    """Position-wise Feed-Forward Network inside each Transformer block."""

    def __init__(self, embedding_dim: int, hidden_dim: int, dropout: float = 0.0) -> None:
        """Initializes the FFN.

        Args:
            embedding_dim: Dimensionality of inputs (d_model).
            hidden_dim: Dimensionality of the expanded hidden layer (d_ff).
            dropout: Dropout probability.
        """
        super().__init__()

        # Linear projections
        self.fc1 = nn.Linear(embedding_dim, hidden_dim, bias=True)
        self.act = GELU()
        self.fc2 = nn.Linear(hidden_dim, embedding_dim, bias=True)

        # Dropout layers
        self.dropout1 = nn.Dropout(dropout)
        self.dropout2 = nn.Dropout(dropout)

        # Initialize weights
        self._init_weights()

    def _init_weights(self) -> None:
        """Initializes weights using normal distributions (std=0.02) and biases to zero."""
        nn.init.normal_(self.fc1.weight, mean=0.0, std=0.02)
        if self.fc1.bias is not None:
            nn.init.zeros_(self.fc1.bias)
            
        nn.init.normal_(self.fc2.weight, mean=0.0, std=0.02)
        if self.fc2.bias is not None:
            nn.init.zeros_(self.fc2.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Applies position-wise FFN forward pass.

        Args:
            x: Input tensor of shape (batch_size, seq_len, embedding_dim).

        Returns:
            Output tensor of shape (batch_size, seq_len, embedding_dim).
        """
        # Project to hidden space: (batch_size, seq_len, hidden_dim)
        x = self.fc1(x)
        x = self.act(x)
        x = self.dropout1(x)

        # Project back to embedding space: (batch_size, seq_len, embedding_dim)
        x = self.fc2(x)
        x = self.dropout2(x)
        
        return x
