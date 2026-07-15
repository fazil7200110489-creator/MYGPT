"""Unit tests for the complete TransformerBlock layer.
"""

import pytest
import torch
from src.transformer_block import TransformerBlock


def test_transformer_block_shapes():
    """Tests that the Transformer Block output and attention weights shapes are correct."""
    batch_size = 2
    seq_len = 8
    embedding_dim = 16
    num_heads = 2
    hidden_dim = 64

    block = TransformerBlock(
        embedding_dim=embedding_dim,
        num_heads=num_heads,
        hidden_dim=hidden_dim
    )
    x = torch.randn(batch_size, seq_len, embedding_dim)
    out, weights = block(x)

    assert out.shape == (batch_size, seq_len, embedding_dim)
    assert weights.shape == (batch_size, num_heads, seq_len, seq_len)


def test_gradient_flow():
    """Tests that backpropagation successfully propagates gradients back to all layers."""
    embedding_dim = 16
    num_heads = 2
    hidden_dim = 32

    block = TransformerBlock(
        embedding_dim=embedding_dim,
        num_heads=num_heads,
        hidden_dim=hidden_dim
    )
    
    # Enable grad tracking on input
    x = torch.randn(1, 4, embedding_dim, requires_grad=True)
    out, _ = block(x)

    # Compute a dummy loss and backward pass
    loss = out.sum()
    loss.backward()

    # Gradients must exist for all projected weights
    assert block.attn.q_proj.weight.grad is not None
    assert block.ffn.fc1.weight.grad is not None
    assert x.grad is not None


def test_train_eval_dropout():
    """Tests that dropout is toggled off during eval and active during train."""
    embedding_dim = 16
    num_heads = 2
    hidden_dim = 32
    dropout = 0.5

    block = TransformerBlock(
        embedding_dim=embedding_dim,
        num_heads=num_heads,
        hidden_dim=hidden_dim,
        dropout=dropout
    )
    x = torch.ones(1, 15, embedding_dim)

    # Evaluation mode: must be deterministic
    block.eval()
    out_eval1, _ = block(x)
    out_eval2, _ = block(x)
    assert torch.equal(out_eval1, out_eval2)

    # Training mode: must be non-deterministic due to active dropouts
    block.train()
    out_train1, _ = block(x)
    out_train2, _ = block(x)
    assert not torch.equal(out_train1, out_train2)
