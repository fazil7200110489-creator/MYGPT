"""Loss module for MyGPT.

This module implements the cross-entropy loss calculations for next-token predictions
while ignoring the PAD token.
"""

import torch
import torch.nn as nn


class GPTLoss(nn.Module):
    """Calculates cross entropy loss for causal language modeling."""

    def __init__(self, ignore_index: int = 0) -> None:
        """Initializes the loss module.

        Args:
            ignore_index: The token ID to ignore during loss calculation (defaults to PAD ID, 0).
        """
        super().__init__()
        # Standard CrossEntropyLoss with ignore_index configuration
        self.loss_fn = nn.CrossEntropyLoss(ignore_index=ignore_index)

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """Computes loss on shifted sequence predictions.

        Args:
            logits: Logits tensor of shape (batch_size, seq_len, vocab_size).
            targets: Target token IDs tensor of shape (batch_size, seq_len).

        Returns:
            The scalar loss tensor.
        """
        batch_size, seq_len, vocab_size = logits.shape
        
        # Flatten tensors to fit PyTorch's CrossEntropyLoss signature:
        # logits -> (batch_size * seq_len, vocab_size)
        # targets -> (batch_size * seq_len)
        flat_logits = logits.view(batch_size * seq_len, vocab_size)
        flat_targets = targets.view(batch_size * seq_len)

        return self.loss_fn(flat_logits, flat_targets)
