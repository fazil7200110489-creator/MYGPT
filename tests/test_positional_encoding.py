"""Unit tests for the SinusoidalPositionalEncoding layer.
"""

import pytest
import torch
from src.positional_encoding import SinusoidalPositionalEncoding


def test_output_shapes():
    """Tests that the positional encoding returns the correct tensor shape."""
    batch_size = 4
    seq_len = 16
    embedding_dim = 64
    max_seq_len = 32

    pe_layer = SinusoidalPositionalEncoding(max_seq_len=max_seq_len, embedding_dim=embedding_dim)
    
    # Mock input embeddings: (batch_size, seq_len, embedding_dim)
    x = torch.randn(batch_size, seq_len, embedding_dim)
    out = pe_layer(x)
    
    # Shape must be preserved
    assert out.shape == x.shape


def test_correct_addition():
    """Tests that the positional encoding is added correctly, not multiplied or concatenated."""
    seq_len = 3
    embedding_dim = 4
    max_seq_len = 10

    pe_layer = SinusoidalPositionalEncoding(max_seq_len=max_seq_len, embedding_dim=embedding_dim)
    
    # Inputs initialized to zero so the output will be exactly the positional encoding values
    x = torch.zeros(1, seq_len, embedding_dim)
    out = pe_layer(x)
    
    # Get direct reference from registered buffer
    buffer_pe = pe_layer.pe[:, :seq_len, :]
    
    # Output must equal the buffer slice
    assert torch.allclose(out, buffer_pe)


def test_odd_embedding_dimension():
    """Tests that the module handles odd embedding dimensions without crashing."""
    batch_size = 2
    seq_len = 5
    embedding_dim = 33  # Odd dimension
    max_seq_len = 10

    pe_layer = SinusoidalPositionalEncoding(max_seq_len=max_seq_len, embedding_dim=embedding_dim)
    x = torch.randn(batch_size, seq_len, embedding_dim)
    out = pe_layer(x)
    
    assert out.shape == x.shape


def test_exceeding_max_len():
    """Tests that an error is raised when input sequence length exceeds max_seq_len."""
    max_seq_len = 8
    pe_layer = SinusoidalPositionalEncoding(max_seq_len=max_seq_len, embedding_dim=16)
    
    # Sequence length of 9 exceeds max of 8
    x = torch.randn(2, 9, 16)
    
    with pytest.raises(ValueError, match="Input sequence length .* exceeds max_seq_len"):
        pe_layer(x)


def test_boundary_conditions():
    """Tests zero length sequence or maximum sequence length boundaries."""
    max_seq_len = 10
    pe_layer = SinusoidalPositionalEncoding(max_seq_len=max_seq_len, embedding_dim=16)
    
    # Zero sequence length
    x_zero = torch.randn(2, 0, 16)
    out_zero = pe_layer(x_zero)
    assert out_zero.shape == (2, 0, 16)

    # Maximum sequence length boundary
    x_max = torch.randn(2, max_seq_len, 16)
    out_max = pe_layer(x_max)
    assert out_max.shape == (2, max_seq_len, 16)
