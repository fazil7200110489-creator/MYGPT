"""Unit tests for the custom GELU and FeedForward layers.
"""

import pytest
import torch
from src.feed_forward import GELU, FeedForward


def test_gelu_values():
    """Tests custom erf-based GELU outputs against PyTorch's native gelu implementation."""
    gelu = GELU()
    x = torch.tensor([-3.0, -1.0, 0.0, 1.0, 3.0])
    
    out = gelu(x)
    ref = torch.nn.functional.gelu(x)
    
    # Must match PyTorch's native function output exactly
    assert torch.allclose(out, ref, atol=1e-6)


def test_ffn_shapes():
    """Tests that FeedForward layer outputs preserve the input shapes."""
    batch_size = 2
    seq_len = 8
    embedding_dim = 16
    hidden_dim = 64

    ffn = FeedForward(embedding_dim=embedding_dim, hidden_dim=hidden_dim)
    x = torch.randn(batch_size, seq_len, embedding_dim)
    out = ffn(x)
    
    assert out.shape == (batch_size, seq_len, embedding_dim)


def test_dropout_behavior():
    """Tests that dropout is applied in training mode and disabled in evaluation mode."""
    embedding_dim = 16
    hidden_dim = 32
    dropout = 0.5  # High probability to guarantee zeroed values

    ffn = FeedForward(embedding_dim=embedding_dim, hidden_dim=hidden_dim, dropout=dropout)
    x = torch.ones(1, 20, embedding_dim)  # Uniform ones inputs

    # In eval mode, dropout is inactive. The forward pass is deterministic.
    ffn.eval()
    out_eval1 = ffn(x)
    out_eval2 = ffn(x)
    assert torch.equal(out_eval1, out_eval2), "Eval mode must be deterministic"

    # In train mode, dropout is active. Multiple passes must yield different values.
    ffn.train()
    out_train1 = ffn(x)
    out_train2 = ffn(x)
    assert not torch.equal(out_train1, out_train2), "Train mode must be non-deterministic (dropout active)"


def test_numerical_stability():
    """Tests that the custom GELU activation behaves correctly with extreme input ranges."""
    gelu = GELU()
    x = torch.tensor([-1e5, 0.0, 1e5])
    out = gelu(x)

    assert not torch.isnan(out).any()
    assert not torch.isinf(out).any()
    
    # Very large negative values must trigger a flat zero response
    assert out[0].item() == 0.0
    # Very large positive values must pass through unchanged (GELU(x) -> x)
    assert torch.allclose(out[2], torch.tensor(1e5))
