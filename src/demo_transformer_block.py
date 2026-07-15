"""Demonstration script for the TransformerBlock layer.
"""

import torch
from src.transformer_block import TransformerBlock


def main() -> None:
    print("--- MyGPT Transformer Block Demo ---")

    # Configuration dimensions
    batch_size = 2
    seq_len = 6
    embedding_dim = 16
    num_heads = 4
    hidden_dim = 64  # 4 * embedding_dim

    # Initialize Transformer Block
    print(f"\n1. Initializing Transformer Block...")
    print(f"   Embedding Dim : {embedding_dim}")
    print(f"   Number of Heads: {num_heads}")
    print(f"   Hidden Dim    : {hidden_dim} (FFN Expansion)")
    
    block = TransformerBlock(
        embedding_dim=embedding_dim,
        num_heads=num_heads,
        hidden_dim=hidden_dim,
        dropout=0.1
    )
    block.eval()  # Disable dropout for clean output verification

    # Generate random inputs
    x = torch.randn(batch_size, seq_len, embedding_dim)
    print(f"\n2. Mock Input Tensor (X):")
    print(f"   Shape: {list(x.shape)} (batch_size, seq_len, embedding_dim)")

    # Forward pass
    print(f"\n3. Executing Forward Pass...")
    out, weights = block(x)

    print(f"\n4. Output Tensors:")
    print(f"   Output Tensor (Y) Shape    : {list(out.shape)} (batch_size, seq_len, embedding_dim)")
    print(f"   Attention Weights (W) Shape: {list(weights.shape)} (batch_size, num_heads, seq_len, seq_len)")

    # 5. Draw ASCII Architecture Flow diagram
    print("\n5. Transformer Block Structural Layout:")
    print("=" * 65)
    print(f"Input Tensor: {list(x.shape)}")
    print("      |")
    print("      +-----------------------------------------+")
    print("      |                                         |  (Identity Stream)")
    print("      v                                         |")
    print("  [ LayerNorm 1 ]                               |")
    print(f"      | Shape: {list(x.shape)}                          |")
    print("      v                                         |")
    print("  [ Multi-Head Attention ]                      |")
    print(f"      | Output Shape: {list(x.shape)}                   |")
    print(f"      | Weights Shape: {list(weights.shape)}           |")
    print("      v                                         |")
    print("     (+) <--------------------------------------+  (Residual Addition 1)")
    print("      |")
    print(f"  Intermediate Tensor: {list(x.shape)}")
    print("      |")
    print("      +-----------------------------------------+")
    print("      |                                         |  (Identity Stream)")
    print("      v                                         |")
    print("  [ LayerNorm 2 ]                               |")
    print(f"      | Shape: {list(x.shape)}                          |")
    print("      v                                         |")
    print("  [ Feed-Forward Network ]                      |")
    print(f"      | Output Shape: {list(x.shape)}                   |")
    print("      v                                         |")
    print("     (+) <--------------------------------------+  (Residual Addition 2)")
    print("      |")
    print(f"Output Tensor: {list(out.shape)}")
    print("=" * 65)


if __name__ == "__main__":
    main()
