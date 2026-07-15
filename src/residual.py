"""Residual Connection module for MyGPT.

This module implements residual connection wrapping (identity skip connection).
"""

import torch
import torch.nn as nn


class ResidualConnection(nn.Module):
    """Applies a residual skip connection: input + sublayer_output."""

    def forward(self, x: torch.Tensor, sublayer_out: torch.Tensor) -> torch.Tensor:
        """Adds the input tensor back to the sublayer output.

        Args:
            x: Original input tensor of shape (batch_size, seq_len, embedding_dim).
            sublayer_out: Sublayer output tensor of the same shape.

        Returns:
            The sum of input and sublayer output.
        """
        if x.shape != sublayer_out.shape:
            raise ValueError(
                f"Shape mismatch: input shape {list(x.shape)} and sublayer output "
                f"shape {list(sublayer_out.shape)} must be identical."
            )
        return x + sublayer_out
