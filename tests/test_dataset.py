"""Unit tests for the TextDataset and DataLoader pipeline.
"""

import pytest
import torch
from src.vocabulary import Vocabulary
from src.tokenizer import WordTokenizer
from src.dataset import TextDataset
from src.dataloader import get_dataloader


@pytest.fixture
def sample_tokenizer() -> WordTokenizer:
    """Provides a tokenizer initialized with a tiny mock vocabulary."""
    vocab = Vocabulary()
    vocab.add_word("the")
    vocab.add_word("cat")
    vocab.add_word("sat")
    vocab.add_word("on")
    vocab.add_word("mat")
    vocab.add_word(".")
    return WordTokenizer(vocab)


def test_empty_dataset_padding(sample_tokenizer):
    """Tests that an empty string initializes a single, fully-padded sample."""
    seq_len = 4
    dataset = TextDataset("", sample_tokenizer, seq_len=seq_len)
    
    # Length must be 1 since constructor pads to seq_len + 1
    assert len(dataset) == 1
    
    x, y = dataset[0]
    assert x.shape == (seq_len,)
    assert y.shape == (seq_len,)
    
    # All values must correspond to the PAD ID
    pad_id = sample_tokenizer.vocab.pad_id
    assert torch.all(x == pad_id)
    assert torch.all(y == pad_id)


def test_small_dataset_padding(sample_tokenizer):
    """Tests that texts shorter than seq_len + 1 are padded correctly."""
    # "the cat" has 2 tokens. We request a sequence length of 4.
    # The dataset requires 5 tokens total, so it will append 3 PAD tokens.
    dataset = TextDataset("the cat", sample_tokenizer, seq_len=4)
    assert len(dataset) == 1

    x, y = dataset[0]
    pad_id = sample_tokenizer.vocab.pad_id
    the_id = sample_tokenizer.vocab.get_id("the")
    cat_id = sample_tokenizer.vocab.get_id("cat")

    # Tokens array: [the_id, cat_id, pad_id, pad_id, pad_id]
    # Expected x (tokens[0:4]): [the_id, cat_id, pad_id, pad_id]
    # Expected y (tokens[1:5]): [cat_id, pad_id, pad_id, pad_id]
    expected_x = torch.tensor([the_id, cat_id, pad_id, pad_id])
    expected_y = torch.tensor([cat_id, pad_id, pad_id, pad_id])

    assert torch.equal(x, expected_x)
    assert torch.equal(y, expected_y)


def test_input_target_alignment(sample_tokenizer):
    """Tests that the target sequence is shifted by exactly one token."""
    text = "the cat sat on the mat ."
    # Tokens: ["the", "cat", "sat", "on", "the", "mat", "."] (7 tokens)
    seq_len = 4
    dataset = TextDataset(text, sample_tokenizer, seq_len=seq_len, stride=1)
    
    # Number of samples = (7 - 4) = 3 samples (starts at indices 0, 1, 2)
    assert len(dataset) == 3

    for i in range(len(dataset)):
        x, y = dataset[i]
        assert x.shape == (seq_len,)
        assert y.shape == (seq_len,)
        # Target sequence must align with the input sequence shifted left by 1 token
        assert torch.equal(y[:-1], x[1:])


def test_stride(sample_tokenizer):
    """Tests that strides skip token indices correctly."""
    text = "the cat sat on the mat ."
    seq_len = 4
    # Stride = 2
    # Sample 0 starts at index 0
    # Sample 1 starts at index 2
    dataset = TextDataset(text, sample_tokenizer, seq_len=seq_len, stride=2)
    assert len(dataset) == 2

    x0, _ = dataset[0]
    x1, _ = dataset[1]

    the_id = sample_tokenizer.vocab.get_id("the")
    sat_id = sample_tokenizer.vocab.get_id("sat")

    assert x0[0] == the_id
    assert x1[0] == sat_id


def test_dataloader_batching(sample_tokenizer):
    """Tests batch creation, shapes, and drop_last flag."""
    text = "the cat sat on the mat . the cat sat on the mat ."
    # 14 tokens
    seq_len = 4
    dataset = TextDataset(text, sample_tokenizer, seq_len=seq_len, stride=1)
    
    # 14 - 4 = 10 samples
    assert len(dataset) == 10

    batch_size = 4
    # With batch_size 4 and drop_last=True, we expect 2 batches of size 4 (2 samples dropped)
    dataloader = get_dataloader(dataset, batch_size=batch_size, shuffle=False, drop_last=True)
    
    batches = list(dataloader)
    assert len(batches) == 2
    for bx, by in batches:
        assert bx.shape == (batch_size, seq_len)
        assert by.shape == (batch_size, seq_len)
