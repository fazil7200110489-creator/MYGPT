"""Vocabulary module for MyGPT.

This module manages mapping between tokens and unique integer IDs, including
special tokens (PAD, UNK, BOS, EOS) and vocabulary generation.
"""

import json
from collections import Counter
from typing import List, Dict, Callable


class Vocabulary:
    """Manages mapping between tokens and unique integer IDs, including special tokens."""

    def __init__(self, special_tokens: List[str] = None) -> None:
        """Initializes the vocabulary mappings.

        Args:
            special_tokens: A list of special tokens to register. If None, defaults to
                            ['<PAD>', '<UNK>', '<BOS>', '<EOS>'].
        """
        if special_tokens is None:
            self.special_tokens = ["<PAD>", "<UNK>", "<BOS>", "<EOS>"]
        else:
            self.special_tokens = special_tokens

        self.w2i: Dict[str, int] = {}
        self.i2w: Dict[int, str] = {}

        # Register special tokens first
        for token in self.special_tokens:
            self.add_word(token)

        # Definitions
        self.pad_token = "<PAD>"
        self.unk_token = "<UNK>"
        self.bos_token = "<BOS>"
        self.eos_token = "<EOS>"

        self.pad_id = self.get_id(self.pad_token)
        self.unk_id = self.get_id(self.unk_token)
        self.bos_id = self.get_id(self.bos_token)
        self.eos_id = self.get_id(self.eos_token)

    def add_word(self, word: str) -> int:
        """Adds a word to the vocabulary if it doesn't already exist.

        Args:
            word: The string token to add.

        Returns:
            The integer ID assigned to the word.
        """
        if word not in self.w2i:
            idx = len(self.w2i)
            self.w2i[word] = idx
            self.i2w[idx] = word
        return self.w2i[word]

    def get_id(self, word: str) -> int:
        """Retrieves the integer ID for a given word.

        Defaults to the <UNK> token ID if the word is not in the vocabulary.

        Args:
            word: The string token.

        Returns:
            The integer ID.
        """
        # If vocabulary has <UNK>, use it for unseen words
        unk_idx = self.w2i.get(self.unk_token, 1)
        return self.w2i.get(word, unk_idx)

    def get_word(self, idx: int) -> str:
        """Retrieves the string token for a given integer ID.

        Defaults to the <UNK> token string if the ID is invalid.

        Args:
            idx: The integer ID.

        Returns:
            The string token.
        """
        unk_str = self.unk_token if self.unk_token in self.w2i else "<UNK>"
        return self.i2w.get(idx, unk_str)

    def __len__(self) -> int:
        """Returns the size of the vocabulary."""
        return len(self.w2i)

    def build_from_text(self, text: str, tokenize_fn: Callable[[str], List[str]], min_freq: int = 1) -> None:
        """Builds vocabulary from a raw text string.

        Args:
            text: The corpus text.
            tokenize_fn: A function that takes a string and returns a list of string tokens.
            min_freq: The minimum frequency threshold for a word to be included.
        """
        tokens = tokenize_fn(text)
        self.build_from_tokens(tokens, min_freq=min_freq)

    def build_from_file(self, filepath: str, tokenize_fn: Callable[[str], List[str]], min_freq: int = 1) -> None:
        """Builds vocabulary from a text file.

        Args:
            filepath: Path to the text file.
            tokenize_fn: A function that takes a string and returns a list of string tokens.
            min_freq: The minimum frequency threshold for a word to be included.
        """
        counter = Counter()
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                tokens = tokenize_fn(line)
                counter.update(tokens)

        # Filter by minimum frequency
        # Sort by frequency descending, then alphabetically for deterministic IDs
        for word, freq in sorted(counter.items(), key=lambda x: (-x[1], x[0])):
            if freq >= min_freq and word not in self.special_tokens:
                self.add_word(word)

    def build_from_tokens(self, tokens: List[str], min_freq: int = 1) -> None:
        """Builds vocabulary from a list of tokens.

        Args:
            tokens: A list of string tokens.
            min_freq: The minimum frequency threshold for a word to be included.
        """
        counter = Counter(tokens)
        for word, freq in sorted(counter.items(), key=lambda x: (-x[1], x[0])):
            if freq >= min_freq and word not in self.special_tokens:
                self.add_word(word)

    def save(self, filepath: str) -> None:
        """Saves vocabulary mappings to a JSON file.

        Args:
            filepath: Path where the JSON file will be saved.
        """
        data = {
            "special_tokens": self.special_tokens,
            "w2i": self.w2i
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    @classmethod
    def load(cls, filepath: str) -> "Vocabulary":
        """Loads vocabulary from a JSON file.

        Args:
            filepath: Path to the saved JSON file.

        Returns:
            An instantiated Vocabulary object.
        """
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        vocab = cls(special_tokens=data.get("special_tokens"))
        vocab.w2i = data["w2i"]
        vocab.i2w = {v: k for k, v in vocab.w2i.items()}
        return vocab
