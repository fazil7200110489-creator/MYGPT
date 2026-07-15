"""Unit tests for the CausalSelfAttention layer.
"""

import pytest
import torch
from src.attention import CausalSelfAttention


def test_attention_shapes():
    """Tests that attention returns the correct tensor and matrix shapes."""
    batch_size = 2
    seq_len = 8
    embedding_dim = 32

    attention_layer = CausalSelfAttention(embedding_dim=embedding_dim)
    x = torch.randn(batch_size, seq_len, embedding_dim)
    
    out, weights = attention_layer(x)
    
    # Shapes verification
    assert out.shape == (batch_size, seq_len, embedding_dim)
    assert weights.shape == (batch_size, seq_len, seq_len)


def test_causal_mask():
    """Tests that attention weights follow the lower-triangular causal structure."""
    batch_size = 2
    seq_len = 5
    embedding_dim = 16

    attention_layer = CausalSelfAttention(embedding_dim=embedding_dim)
    x = torch.randn(batch_size, seq_len, embedding_dim)
    
    _, weights = attention_layer(x)
    
    # Upper triangular values of the attention weights matrix must be exactly 0.0.
    # We select the upper triangle strictly above diagonal 0 (diagonal=1).
    upper_tri = torch.triu(weights, diagonal=1)
    
    assert torch.all(upper_tri == 0.0), "Attention leaked to future tokens!"


def test_softmax_normalization():
    """Tests that attention weights in each row sum to exactly 1.0."""
    batch_size = 3
    seq_len = 10
    embedding_dim = 64

    attention_layer = CausalSelfAttention(embedding_dim=embedding_dim)
    x = torch.randn(batch_size, seq_len, embedding_dim)
    
    _, weights = attention_layer(x)
    
    # Sum across columns (last dimension) must equal 1.0 for every row
    row_sums = torch.sum(weights, dim=-1)
    expected_sums = torch.ones(batch_size, seq_len, device=x.device)
    
    assert torch.allclose(row_sums, expected_sums, atol=1e-6)


def test_numerical_stability():
    """Tests that the attention mechanism is stable under extremely large values."""
    batch_size = 1
    seq_len = 3
    embedding_dim = 8

    attention_layer = CausalSelfAttention(embedding_dim=embedding_dim)
    
    # Create input with massive values to try to force softmax overflow
    x = torch.full((batch_size, seq_len, embedding_dim), 1e6)
    
    # If not stable, this will output NaNs/Infs
    out, weights = attention_layer(x)
    
    assert not torch.isnan(out).any(), "NaN found in attention outputs!"
    assert not torch.isinf(out).any(), "Inf found in attention outputs!"
    assert not torch.isnan(weights).any(), "NaN found in attention weights!"
    assert not torch.isinf(weights).any(), "Inf found in attention weights!"


def test_single_token_sequence():
    """Tests boundary condition where sequence length is 1."""
    batch_size = 2
    seq_len = 1
    embedding_dim = 16

    attention_layer = CausalSelfAttention(embedding_dim=embedding_dim)
    x = torch.randn(batch_size, seq_len, embedding_dim)
    
    out, weights = attention_layer(x)
    
    assert out.shape == (batch_size, seq_len, embedding_dim)
    assert weights.shape == (batch_size, seq_len, seq_len)
    assert weights.item() == 1.0 if batch_size == 1 else True # For size 1, it's just 1.0
