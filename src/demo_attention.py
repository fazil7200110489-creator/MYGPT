"""Demonstration and visualization script for CausalSelfAttention.
"""

import os
import torch
import matplotlib.pyplot as plt
from src.vocabulary import Vocabulary
from src.tokenizer import WordTokenizer
from src.embeddings import CustomEmbedding
from src.positional_encoding import SinusoidalPositionalEncoding
from src.attention import CausalSelfAttention


def main() -> None:
    print("--- MyGPT Causal Self-Attention Demo ---")

    # 1. Initialize tokenizer and tokenize a sentence
    vocab = Vocabulary()
    vocab.add_word("the")
    vocab.add_word("cat")
    vocab.add_word("sat")
    vocab.add_word("on")
    vocab.add_word("mat")
    vocab.add_word(".")
    tokenizer = WordTokenizer(vocab)

    text = "the cat sat on the mat ."
    print(f"\n1. Input Text: '{text}'")
    tokens = tokenizer.tokenize(text)
    print(f"   Tokens: {tokens}")
    token_ids = tokenizer.encode(text)
    print(f"   Token IDs: {token_ids}")

    # Convert to batch tensor of shape (1, seq_len)
    x_ids = torch.tensor([token_ids], dtype=torch.long)
    print(f"   Input IDs Shape: {list(x_ids.shape)} (batch_size, seq_len)")

    # 2. Embedding Layer
    embedding_dim = 16
    embed_layer = CustomEmbedding(vocab_size=len(vocab), embedding_dim=embedding_dim)
    embeddings = embed_layer(x_ids)
    print(f"\n2. Embeddings Shape: {list(embeddings.shape)} (batch_size, seq_len, embedding_dim)")

    # 3. Positional Encoding
    pos_layer = SinusoidalPositionalEncoding(max_seq_len=20, embedding_dim=embedding_dim)
    pos_embeddings = pos_layer(embeddings)
    print(f"\n3. Position-Aware Embeddings Shape: {list(pos_embeddings.shape)} (batch_size, seq_len, embedding_dim)")

    # 4. Self-Attention Block
    print("\n4. Initializing Causal Self-Attention Layer...")
    attention_layer = CausalSelfAttention(embedding_dim=embedding_dim)
    out, weights = attention_layer(pos_embeddings)
    
    print(f"   Attention Output Shape : {list(out.shape)} (batch_size, seq_len, embedding_dim)")
    print(f"   Attention Weights Shape: {list(weights.shape)} (batch_size, seq_len, seq_len)")

    # Print the weights matrix for the batch
    print("\nComputed Attention Matrix (Weights) Row-by-Row:")
    weights_matrix = weights[0].detach().numpy()
    for i, row in enumerate(weights_matrix):
        row_str = " ".join([f"{val:.3f}" for val in row])
        print(f"  Token {i} ('{tokens[i]}') attends to: [{row_str}]")

    # 5. Visualize the attention weight matrix
    print("\n5. Generating Attention Matrix Heatmap...")
    plt.figure(figsize=(8, 6))
    plt.imshow(weights_matrix, cmap="Blues", aspect="auto")
    plt.colorbar(label="Attention Weight")
    
    # Set tick labels to tokens
    plt.xticks(range(len(tokens)), tokens, rotation=45)
    plt.yticks(range(len(tokens)), tokens)
    
    plt.title("Causal Self-Attention Weight Heatmap")
    plt.xlabel("Key Tokens (Attended To)")
    plt.ylabel("Query Tokens (Attending)")
    
    # Save the figure to the artifacts directory
    artifact_dir = r"C:\Users\mohamedfazil\.gemini\antigravity-ide\brain\59f94952-5f03-4aa6-a2f9-5871a9eec093"
    os.makedirs(artifact_dir, exist_ok=True)
    plot_path = os.path.join(artifact_dir, "attention_matrix_heatmap.png")
    
    plt.savefig(plot_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"   Heatmap successfully saved to: {plot_path}")


if __name__ == "__main__":
    main()
