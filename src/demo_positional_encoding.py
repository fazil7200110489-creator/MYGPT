"""Demonstration and visualization script for SinusoidalPositionalEncoding.
"""

import os
import torch
import matplotlib.pyplot as plt
from src.vocabulary import Vocabulary
from src.tokenizer import WordTokenizer
from src.embeddings import CustomEmbedding
from src.positional_encoding import SinusoidalPositionalEncoding


def main() -> None:
    print("--- MyGPT Positional Encoding Demo ---")

    # 1. Prepare dummy data and tokenizer
    vocab = Vocabulary()
    vocab.add_word("hello")
    vocab.add_word("world")
    vocab.add_word("transformers")
    vocab.add_word("are")
    vocab.add_word("amazing")
    tokenizer = WordTokenizer(vocab)

    text = "hello world transformers are amazing"
    print(f"\n1. Input Text: '{text}'")

    # 2. Encode to Token IDs
    token_ids = tokenizer.encode(text)
    print(f"2. Token IDs: {token_ids}")

    # Add batch dimension to simulate DataLoader output: shape (1, seq_len)
    token_tensor = torch.tensor([token_ids], dtype=torch.long)
    print(f"   Batch Input Tensor Shape: {list(token_tensor.shape)} (batch_size, seq_len)")

    # 3. Create CustomEmbedding layer
    embedding_dim = 128
    vocab_size = len(vocab)
    print(f"\n3. Initializing Embedding Layer (vocab_size={vocab_size}, embedding_dim={embedding_dim})...")
    embed_layer = CustomEmbedding(vocab_size=vocab_size, embedding_dim=embedding_dim)
    
    embeddings = embed_layer(token_tensor)
    print(f"   Output Embeddings Shape: {list(embeddings.shape)} (batch_size, seq_len, embedding_dim)")

    # 4. Create Positional Encoding Layer
    max_seq_len = 100
    print(f"\n4. Initializing Positional Encoding Layer (max_seq_len={max_seq_len}, embedding_dim={embedding_dim})...")
    pos_layer = SinusoidalPositionalEncoding(max_seq_len=max_seq_len, embedding_dim=embedding_dim)

    # 5. Add Positional Encoding
    pos_embeddings = pos_layer(embeddings)
    print(f"   Final Position-Aware Embeddings Shape: {list(pos_embeddings.shape)} (batch_size, seq_len, embedding_dim)")

    # 6. Generate Heatmap Visualization of the PE Matrix
    print("\n5. Generating Positional Encoding Matrix Heatmap...")
    # Retrieve PE matrix of shape (max_seq_len, embedding_dim)
    pe_matrix = pos_layer.pe.squeeze(0).cpu().numpy()

    plt.figure(figsize=(10, 6))
    # Display the first 50 positions to show high-frequency and low-frequency sinusoidal curves clearly
    plt.imshow(pe_matrix[:50, :], cmap="viridis", aspect="auto")
    plt.colorbar(label="Encoding Value")
    plt.title("Sinusoidal Positional Encoding Heatmap (First 50 Positions)")
    plt.xlabel("Embedding Dimension Index")
    plt.ylabel("Sequence Position")
    
    # Save the figure to the artifacts directory
    artifact_dir = r"C:\Users\mohamedfazil\.gemini\antigravity-ide\brain\59f94952-5f03-4aa6-a2f9-5871a9eec093"
    os.makedirs(artifact_dir, exist_ok=True)
    plot_path = os.path.join(artifact_dir, "positional_encoding_heatmap.png")
    
    plt.savefig(plot_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"   Heatmap successfully saved to: {plot_path}")

    # Explaining dimensions
    print("\nDimension Explanations:")
    print("  - batch_size: The number of sequences processed in parallel (here: 1).")
    print("  - seq_len: The number of tokens in the sequence (here: 5).")
    print("  - embedding_dim: The dense vector size representing each token and position (here: 128).")


if __name__ == "__main__":
    main()
