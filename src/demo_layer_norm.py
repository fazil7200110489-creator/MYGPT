"""Demonstration script for LayerNorm, Residual Connections, and Pre-LayerNorm sequence.
"""

import torch
from src.layer_norm import LayerNorm
from src.residual import ResidualConnection
from src.attention import CausalSelfAttention
from src.feed_forward import FeedForward


def main() -> None:
    print("--- MyGPT LayerNorm & Residual Connections Demo ---")

    # Dimensions
    batch_size = 1
    seq_len = 5
    embedding_dim = 8
    hidden_dim = 32  # 4x embedding_dim
    
    # 1. Initialize components
    print("\n1. Initializing structural components...")
    ln1 = LayerNorm(normalized_shape=embedding_dim)
    ln2 = LayerNorm(normalized_shape=embedding_dim)
    res = ResidualConnection()
    
    # Using small dimension weights for demo
    attention = CausalSelfAttention(embedding_dim=embedding_dim)
    ffn = FeedForward(embedding_dim=embedding_dim, hidden_dim=hidden_dim)

    # 2. Mock Input
    # Initialize with non-zero mean and large variance to clearly observe normalization
    x = torch.randn(batch_size, seq_len, embedding_dim) * 5.0 + 10.0
    print(f"\n2. Mock Input Tensor (X):")
    print(f"   Shape: {list(x.shape)} (batch_size, seq_len, embedding_dim)")
    print(f"   Channel Mean (across last dim)   : {x.mean(dim=-1).squeeze(0).tolist()}")
    print(f"   Channel Variance (across last dim): {x.var(dim=-1, unbiased=False).squeeze(0).tolist()}")

    # 3. Step-by-Step Pre-LayerNorm Block Order Trace
    print("\n3. Executing Pre-LayerNorm Block sequence:")
    print("=" * 70)

    # Step A: Apply first LayerNorm
    x_norm1 = ln1(x)
    print("Step A: LayerNorm 1 (applied before Attention)")
    print(f"  Shape: {list(x_norm1.shape)}")
    print(f"  Mean after LN1 (must be ~0.0) : {x_norm1.mean(dim=-1).squeeze(0).tolist()}")
    print(f"  Var after LN1  (must be ~1.0) : {x_norm1.var(dim=-1, unbiased=False).squeeze(0).tolist()}")
    print("-" * 60)

    # Step B: Pass through Causal Self-Attention
    attn_out, _ = attention(x_norm1)
    print("Step B: Causal Self-Attention")
    print(f"  Shape: {list(attn_out.shape)}")
    print("-" * 60)

    # Step C: First Residual Connection (Add input X back to attention output)
    x_res1 = res(x, attn_out)
    print("Step C: First Residual Addition (Input X + Attention Output)")
    print(f"  Shape: {list(x_res1.shape)}")
    print(f"  Mean  : {x_res1.mean(dim=-1).squeeze(0).tolist()}")
    print("-" * 60)

    # Step D: Apply second LayerNorm
    x_norm2 = ln2(x_res1)
    print("Step D: LayerNorm 2 (applied before FFN)")
    print(f"  Shape: {list(x_norm2.shape)}")
    print(f"  Mean after LN2 (must be ~0.0) : {x_norm2.mean(dim=-1).squeeze(0).tolist()}")
    print(f"  Var after LN2  (must be ~1.0) : {x_norm2.var(dim=-1, unbiased=False).squeeze(0).tolist()}")
    print("-" * 60)

    # Step E: Pass through Feed-Forward Network
    ffn_out = ffn(x_norm2)
    print("Step E: Position-wise Feed-Forward Network")
    print(f"  Shape: {list(ffn_out.shape)}")
    print("-" * 60)

    # Step F: Second Residual Connection (Add attention output x_res1 back to FFN output)
    final_out = res(x_res1, ffn_out)
    print("Step F: Second Residual Addition (X_res1 + FFN Output) -> Final Output")
    print(f"  Shape: {list(final_out.shape)}")
    print("=" * 70)


if __name__ == "__main__":
    main()
