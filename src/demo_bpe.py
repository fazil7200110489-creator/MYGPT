"""Demonstration and comparison script for the BPE Tokenizer.
"""

import re
from src.tokenizer import BPETokenizer


def get_word_tokenizer_length(text: str) -> int:
    """Calculates sequence length using a simple word splitter."""
    return len(re.findall(r"\w+|[^\w\s]", text))


def get_char_tokenizer_length(text: str) -> int:
    """Calculates sequence length using character split."""
    return len(text)


def main() -> None:
    print("--- MyGPT BPE Tokenizer Demo & Comparison ---")

    # Sample corpus to train tokenizer on
    corpus = (
        "hug pug hug hug pug hug. "
        "the quick brown fox jumps over the lazy dog. "
        "learning transformers from scratch is fun and rewarding. "
        "building a language model requires a tokenizer. "
        "subword tokenizers like byte pair encoding represent words efficiently. "
        "unseen words are split into known subwords."
    )

    # 1. Train BPE Tokenizer
    vocab_size = 80
    print(f"\n1. Training BPE Tokenizer on sample corpus (target vocab_size={vocab_size})...")
    tokenizer = BPETokenizer()
    tokenizer.train(corpus, vocab_size=vocab_size, min_freq=1)
    
    print(f"   Trained Vocabulary size: {len(tokenizer.w2i)} tokens.")
    print("   Top 10 discovered merges (by rank):")
    sorted_merges = sorted(tokenizer.merges.items(), key=lambda x: x[1])
    for pair, rank in sorted_merges[:10]:
        print(f"     Rank {rank:02d}: '{pair[0]}' + '{pair[1]}' -> '{pair[0] + pair[1]}'")

    # 2. Word Tokenization Example
    test_word = "transformers"
    print(f"\n2. BPE Subword breakdown for word: '{test_word}'")
    tokens = tokenizer.tokenize(test_word)
    print(f"   Resulting BPE subwords: {tokens}")

    # 3. Strategy Comparison on unseen/out-of-vocabulary sentence
    sample_sentence = "unseen words like HuggingFace are tokenized as subwords."
    print(f"\n3. Tokenizer Strategy Comparison on sentence:")
    print(f"   '{sample_sentence}'")
    print("=" * 80)

    # Word-level simulation
    word_len = get_word_tokenizer_length(sample_sentence)
    print("Strategy 1: Word-Level Tokenizer")
    print(f"  - Vocabulary Size: ~1,000,000 (Very Large)")
    print(f"  - Sequence Length: {word_len} tokens")
    print(f"  - Unseen words (e.g. 'HuggingFace'): treated as <UNK> (Information lost)")
    print("-" * 75)

    # Character-level simulation
    char_len = get_char_tokenizer_length(sample_sentence)
    print("Strategy 2: Character-Level Tokenizer")
    print(f"  - Vocabulary Size: ~256 (Tiny)")
    print(f"  - Sequence Length: {char_len} tokens (Extremely long sequences)")
    print(f"  - Unseen words: Handled perfectly (zero OOV)")
    print("-" * 75)

    # BPE-level
    bpe_ids = tokenizer.encode(sample_sentence)
    bpe_tokens = tokenizer.tokenize(sample_sentence)
    bpe_len = len(bpe_ids)
    print("Strategy 3: Byte Pair Encoding (BPE) Tokenizer")
    print(f"  - Vocabulary Size: {vocab_size} (Configurable & Balanced)")
    print(f"  - Sequence Length: {bpe_len} tokens (Compressed representation)")
    print(f"  - Subwords generated: {bpe_tokens}")
    print(f"  - Unseen words (e.g. 'HuggingFace'): split into known subwords (Meaning preserved)")
    print(f"  - Decoded Text: '{tokenizer.decode(bpe_ids)}'")
    print("=" * 80)

    # Compression Metric
    compression_ratio = char_len / bpe_len
    print(f"\nCompression Metrics:")
    print(f"  - BPE Compression Ratio: {compression_ratio:.2f}x (characters per token)")


if __name__ == "__main__":
    main()
