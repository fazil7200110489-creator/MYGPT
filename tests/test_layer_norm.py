"""Unit tests for the custom LayerNorm and ResidualConnection modules.
"""

import pytest
import torch
from src.layer_norm import LayerNorm
from src.residual import ResidualConnection


def test_layer_norm_shapes():
    """Tests that LayerNorm output dimensions match the input dimensions."""
    batch_size = 2
    seq_len = 5
    embedding_dim = 16

    ln = LayerNorm(normalized_shape=embedding_dim)
    x = torch.randn(batch_size, seq_len, embedding_dim)
    out = ln(x)
    
    assert out.shape == x.shape


def test_layer_norm_zero_mean_unit_var():
    """Tests that activations are normalized to mean=0 and variance=1."""
    embedding_dim = 32
    ln = LayerNorm(normalized_shape=embedding_dim)
    
    # Generate input tensor with non-zero mean and large variance
    x = torch.randn(4, 10, embedding_dim) * 5.0 + 3.0
    out = ln(x)

    # Calculate mean and variance across the channel dimension
    mean = out.mean(dim=-1)
    var = out.var(dim=-1, unbiased=False)

    # After normalization: mean -> 0.0, variance -> 1.0
    assert torch.allclose(mean, torch.zeros_like(mean), atol=1e-5)
    assert torch.allclose(var, torch.ones_like(var), atol=1e-5)


def test_layer_norm_ref_match():
    """Tests that custom LayerNorm outputs match PyTorch's native LayerNorm exactly."""
    embedding_dim = 16
    custom_ln = LayerNorm(normalized_shape=embedding_dim)
    ref_ln = torch.nn.LayerNorm(normalized_shape=embedding_dim)

    # Sync weights to make comparison fair
    with torch.no_grad():
        ref_ln.weight.copy_(custom_ln.gamma)
        ref_ln.bias.copy_(custom_ln.beta)

    x = torch.randn(2, 5, embedding_dim)
    custom_out = custom_ln(x)
    ref_out = ref_ln(x)

    assert torch.allclose(custom_out, ref_out, atol=1e-6)


def test_residual_addition():
    """Tests that ResidualConnection adds inputs correctly."""
    res = ResidualConnection()
    x = torch.randn(2, 4, 8)
    sub = torch.randn(2, 4, 8)
    
    out = res(x, sub)
    assert torch.equal(out, x + sub)


def test_residual_mismatch():
    """Tests that ResidualConnection raises a ValueError during shape mismatches."""
    res = ResidualConnection()
    x = torch.randn(2, 4, 8)
    sub = torch.randn(2, 4, 9)  # Embedding size mismatch (8 vs 9)

    with pytest.raises(ValueError, match="Shape mismatch"):
        res(x, sub)


def test_numerical_stability():
    """Tests that LayerNorm handles constant zero tensors without throwing NaNs."""
    ln = LayerNorm(normalized_shape=8)
    
    # Constant zero tensor (variance is 0)
    x = torch.zeros(1, 3, 8)
    out = ln(x)

    # Division by zero must be protected by eps, returning zeros
    assert not torch.isnan(out).any()
    assert torch.allclose(out, torch.zeros_like(out))
