"""Unit tests for the custom BPETokenizer.
"""

import os
import tempfile
import pytest
from src.tokenizer import BPETokenizer


def test_bpe_training():
    """Tests that BPE training completes and populates merges and vocabulary correctly."""
    corpus = "hug pug hug hug pug hug"
    tokenizer = BPETokenizer()
    # Train BPE to build vocabulary
    tokenizer.train(corpus, vocab_size=12, min_freq=2)
    
    # Vocabulary size should be restricted
    assert len(tokenizer.w2i) <= 12
    # Ensure standard BPE merges like 'ug' or 'hug' were identified
    assert "ug" in tokenizer.w2i or "hug" in tokenizer.w2i
    assert len(tokenizer.merges) > 0


def test_bpe_roundtrip():
    """Tests that encoding and then decoding a sentence preserves the contents (case-normalized)."""
    corpus = "the quick brown fox jumps over the lazy dog."
    tokenizer = BPETokenizer()
    tokenizer.train(corpus, vocab_size=40, min_freq=1)

    test_text = "the quick brown fox"
    encoded = tokenizer.encode(test_text)
    decoded = tokenizer.decode(encoded)

    assert decoded == test_text.lower()


def test_unseen_characters():
    """Tests that completely unseen characters are mapped to the <UNK> token."""
    corpus = "abc"
    tokenizer = BPETokenizer()
    tokenizer.train(corpus, vocab_size=10, min_freq=1)

    # 'z' is unseen and must be replaced by <UNK>
    encoded = tokenizer.encode("azb")
    assert tokenizer.w2i["<UNK>"] in encoded

    decoded = tokenizer.decode(encoded, skip_special=False)
    assert "<UNK>" in decoded


def test_save_load():
    """Tests that BPE states can be saved to and loaded from JSON correctly."""
    corpus = "hello world hello hello world"
    tokenizer = BPETokenizer()
    tokenizer.train(corpus, vocab_size=20, min_freq=1)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "bpe.json")
        tokenizer.save(path)

        loaded = BPETokenizer(vocab_file=path)
        assert len(loaded.w2i) == len(tokenizer.w2i)
        assert loaded.merges == tokenizer.merges

        test_text = "hello world"
        assert loaded.encode(test_text) == tokenizer.encode(test_text)
        assert loaded.decode(loaded.encode(test_text)) == tokenizer.decode(tokenizer.encode(test_text))
