"""Unit tests for the WordTokenizer and Vocabulary classes.
"""

import os
import tempfile
import pytest
from src.vocabulary import Vocabulary
from src.tokenizer import WordTokenizer


def test_empty_and_whitespace():
    """Tests how the tokenizer handles empty or whitespace-only inputs."""
    vocab = Vocabulary()
    tokenizer = WordTokenizer(vocab)

    assert tokenizer.tokenize("") == []
    assert tokenizer.tokenize("   ") == []
    assert tokenizer.encode("") == []
    assert tokenizer.decode([]) == ""


def test_lowercase_and_multiple_spaces():
    """Tests lowercase normalization and handling of multiple spaces."""
    vocab = Vocabulary()
    vocab.add_word("hello")
    vocab.add_word("world")
    tokenizer = WordTokenizer(vocab)

    text = "  HELLO    world   "
    tokens = tokenizer.tokenize(text)
    assert tokens == ["hello", "world"]

    encoded = tokenizer.encode(text)
    assert len(encoded) == 2
    assert tokenizer.decode(encoded) == "hello world"


def test_punctuation_and_numbers():
    """Tests handling of preserved and discarded punctuation and numbers."""
    vocab = Vocabulary()
    vocab.add_word("hello")
    vocab.add_word("world")
    vocab.add_word("123")
    vocab.add_word(".")
    vocab.add_word(",")
    tokenizer = WordTokenizer(vocab)

    # '@' and '#' should be discarded; ',' and '.' should be preserved.
    text = "Hello, world @# 123."
    tokens = tokenizer.tokenize(text)
    assert tokens == ["hello", ",", "world", "123", "."]

    encoded = tokenizer.encode(text)
    # Reconstructed output should clean up spaces before punctuation.
    assert tokenizer.decode(encoded) == "hello, world 123."


def test_unknown_words():
    """Tests that unseen words map to the <UNK> token ID and decode accordingly."""
    vocab = Vocabulary()
    vocab.add_word("hello")
    tokenizer = WordTokenizer(vocab)

    encoded = tokenizer.encode("hello world")
    assert encoded == [vocab.get_id("hello"), vocab.unk_id]

    decoded = tokenizer.decode(encoded)
    assert decoded == f"hello {vocab.unk_token}"


def test_special_tokens():
    """Tests option to add BOS/EOS markers and skip them during decoding."""
    vocab = Vocabulary()
    vocab.add_word("hello")
    tokenizer = WordTokenizer(vocab)

    encoded = tokenizer.encode("hello", add_bos=True, add_eos=True)
    assert encoded == [vocab.bos_id, vocab.get_id("hello"), vocab.eos_id]

    decoded_with_special = tokenizer.decode(encoded, skip_special=False)
    assert decoded_with_special == f"{vocab.bos_token} hello {vocab.eos_token}"

    decoded_without_special = tokenizer.decode(encoded, skip_special=True)
    assert decoded_without_special == "hello"


def test_save_load_vocab():
    """Tests vocabulary serialization to and deserialization from JSON."""
    vocab = Vocabulary()
    vocab.add_word("hello")
    vocab.add_word("world")

    with tempfile.TemporaryDirectory() as tmpdir:
        vocab_path = os.path.join(tmpdir, "vocab.json")
        vocab.save(vocab_path)

        loaded_vocab = Vocabulary.load(vocab_path)
        assert len(loaded_vocab) == len(vocab)
        assert loaded_vocab.get_id("hello") == vocab.get_id("hello")
        assert loaded_vocab.get_id("world") == vocab.get_id("world")
        assert loaded_vocab.get_id("unseen") == loaded_vocab.unk_id
