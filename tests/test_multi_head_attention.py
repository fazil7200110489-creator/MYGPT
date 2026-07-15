"""Unit tests for the MultiHeadAttention layer.
"""

import pytest
import torch
from src.multi_head_attention import MultiHeadAttention


def test_mha_shapes():
    """Tests that Multi-Head Attention outputs correct tensor and weight matrix shapes."""
    batch_size = 2
    seq_len = 8
    embedding_dim = 32
    num_heads = 4

    mha = MultiHeadAttention(embedding_dim=embedding_dim, num_heads=num_heads)
    x = torch.randn(batch_size, seq_len, embedding_dim)
    
    out, weights = mha(x)
    
    assert out.shape == (batch_size, seq_len, embedding_dim)
    assert weights.shape == (batch_size, num_heads, seq_len, seq_len)


def test_indivisible_dimensions():
    """Tests that a ValueError is raised when embedding_dim is not divisible by num_heads."""
    # 32 is not divisible by 5
    with pytest.raises(ValueError, match="must be cleanly divisible by"):
        MultiHeadAttention(embedding_dim=32, num_heads=5)


def test_causal_mask_multi_head():
    """Tests that causal masking is applied correctly to all heads."""
    batch_size = 2
    seq_len = 5
    embedding_dim = 16
    num_heads = 2

    mha = MultiHeadAttention(embedding_dim=embedding_dim, num_heads=num_heads)
    x = torch.randn(batch_size, seq_len, embedding_dim)
    
    _, weights = mha(x)
    
    # Upper triangular values of attention weight matrices must be exactly 0.0 for ALL heads.
    # weights has shape: (batch_size, num_heads, seq_len, seq_len)
    upper_tri = torch.triu(weights, diagonal=1)
    
    assert torch.all(upper_tri == 0.0), "Attention leaked to future tokens in one or more heads!"


def test_softmax_multi_head():
    """Tests that attention weights sum to exactly 1.0 along the last dimension for all heads."""
    batch_size = 2
    seq_len = 6
    embedding_dim = 16
    num_heads = 4

    mha = MultiHeadAttention(embedding_dim=embedding_dim, num_heads=num_heads)
    x = torch.randn(batch_size, seq_len, embedding_dim)
    
    _, weights = mha(x)
    
    # Sum along last dimension must be 1.0 for every batch, head, and row
    row_sums = torch.sum(weights, dim=-1)
    expected = torch.ones(batch_size, num_heads, seq_len, device=x.device)
    
    assert torch.allclose(row_sums, expected, atol=1e-6)


def test_numerical_stability():
    """Tests that the multi-head attention module is numerically stable under massive values."""
    batch_size = 1
    seq_len = 3
    embedding_dim = 8
    num_heads = 2

    mha = MultiHeadAttention(embedding_dim=embedding_dim, num_heads=num_heads)
    
    # Massive values
    x = torch.full((batch_size, seq_len, embedding_dim), 1e6)
    
    out, weights = mha(x)
    
    assert not torch.isnan(out).any(), "NaN found in MHA outputs!"
    assert not torch.isinf(out).any(), "Inf found in MHA outputs!"
    assert not torch.isnan(weights).any(), "NaN found in MHA weights!"
    assert not torch.isinf(weights).any(), "Inf found in MHA weights!"
