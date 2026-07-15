"""Layer Normalization module for MyGPT.

This module implements Layer Normalization from first principles.
"""

import torch
import torch.nn as nn


class LayerNorm(nn.Module):
    """Custom Layer Normalization built from scratch."""

    def __init__(self, normalized_shape: int, eps: float = 1e-5) -> None:
        """Initializes the LayerNorm layer.

        Args:
            normalized_shape: Size of the normalized dimension (usually embedding_dim).
            eps: Epsilon constant for numerical stability during division.
        """
        super().__init__()
        self.eps = eps

        # Learnable scale (gamma) and shift (beta) parameters
        self.gamma = nn.Parameter(torch.ones(normalized_shape))
        self.beta = nn.Parameter(torch.zeros(normalized_shape))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Applies Layer Normalization over the last dimension.

        Args:
            x: Input tensor of shape (..., normalized_shape).

        Returns:
            Normalized tensor of the same shape as input.
        """
        # Compute mean along the last dimension (dim=-1)
        mean = x.mean(dim=-1, keepdim=True)
        
        # Compute biased variance along the last dimension (dim=-1)
        # unbiased=False divides by N instead of N-1 to match standard behavior
        var = x.var(dim=-1, keepdim=True, unbiased=False)

        # Normalize activations to zero mean and unit variance
        x_norm = (x - mean) / torch.sqrt(var + self.eps)

        # Scale and shift using trainable parameters
        return self.gamma * x_norm + self.beta
