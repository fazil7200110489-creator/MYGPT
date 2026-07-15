"""Demonstration and comparison script for FeedForward and GELU layers.
"""

import os
import torch
import matplotlib.pyplot as plt
from src.feed_forward import GELU, FeedForward


def main() -> None:
    print("--- MyGPT Feed-Forward Network (FFN) Demo ---")

    # 1. Pipeline Trace
    batch_size = 2
    seq_len = 5
    embedding_dim = 16
    hidden_dim = 64  # 4x embedding_dim

    print(f"\n1. Initializing FFN (embedding_dim={embedding_dim}, hidden_dim={hidden_dim})...")
    ffn = FeedForward(embedding_dim=embedding_dim, hidden_dim=hidden_dim)
    ffn.eval()  # Disable dropout for deterministic logging

    # Generate random inputs
    x = torch.randn(batch_size, seq_len, embedding_dim)
    print(f"   Input Tensor Shape  : {list(x.shape)} (batch_size, seq_len, embedding_dim)")

    # Trace step-by-step
    with torch.no_grad():
        h1 = ffn.fc1(x)
        print(f"   Shape after Linear 1: {list(h1.shape)} (batch_size, seq_len, hidden_dim) [Expanded 4x]")
        
        h2 = ffn.act(h1)
        print(f"   Shape after GELU    : {list(h2.shape)} (batch_size, seq_len, hidden_dim)")
        
        out = ffn.fc2(h2)
        print(f"   Final Output Shape  : {list(out.shape)} (batch_size, seq_len, embedding_dim) [Projected back]")

    # 2. Activation Function Comparison Plot
    print("\n2. Plotting GELU vs. ReLU Activation Comparison...")
    
    # Generate points from -4.0 to 4.0
    x_vals = torch.linspace(-4.0, 4.0, 1000)
    
    # Compute activations
    custom_gelu = GELU()
    y_gelu = custom_gelu(x_vals).numpy()
    y_relu = torch.relu(x_vals).numpy()
    
    x_numpy = x_vals.numpy()

    plt.figure(figsize=(8, 6))
    plt.plot(x_numpy, y_gelu, label="GELU (Gaussian Error Linear Unit)", color="royalblue", linewidth=2.5)
    plt.plot(x_numpy, y_relu, label="ReLU (Rectified Linear Unit)", color="tomato", linestyle="--", linewidth=2)
    plt.axhline(0, color="gray", linestyle=":", alpha=0.6)
    plt.axvline(0, color="gray", linestyle=":", alpha=0.6)
    
    plt.title("Activation Functions: GELU vs. ReLU Comparison", fontsize=14)
    plt.xlabel("Input Value (x)")
    plt.ylabel("Output Value (f(x))")
    plt.legend(fontsize=11)
    plt.grid(True, alpha=0.3)
    
    # Save the figure to the artifacts directory
    artifact_dir = r"C:\Users\mohamedfazil\.gemini\antigravity-ide\brain\59f94952-5f03-4aa6-a2f9-5871a9eec093"
    os.makedirs(artifact_dir, exist_ok=True)
    plot_path = os.path.join(artifact_dir, "gelu_vs_relu_comparison.png")
    
    plt.savefig(plot_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"   Comparison plot successfully saved to: {plot_path}")


if __name__ == "__main__":
    main()
