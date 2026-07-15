"""Dataset module for MyGPT.

This module implements a custom PyTorch Dataset class to parse text corpora,
tokenize them, and prepare causally-aligned input-target training pairs.
"""

import os
from typing import Tuple, Union, Any
import torch
from torch.utils.data import Dataset


class TextDataset(Dataset):
    """A PyTorch Dataset for causal language modeling.

    Tokenizes text files or strings and formats them into input-target sequences
    shifted by one token.
    """

    def __init__(
        self,
        text_or_path: str,
        tokenizer: Any,
        seq_len: int,
        stride: int = 1,
        is_path: bool = False
    ) -> None:
        """Initializes the dataset.

        Args:
            text_or_path: Raw text string or the path to a text file.
            tokenizer: An instance of a tokenizer (e.g. BPETokenizer).
            seq_len: The length of input/target sequences.
            stride: The step size between starting indices of successive samples.
            is_path: If True, treats text_or_path as a filepath to load.
        """
        self.tokenizer = tokenizer
        self.seq_len = seq_len
        self.stride = stride

        if is_path:
            text = self._read_file(text_or_path)
        else:
            text = text_or_path

        # Convert raw text into token IDs
        token_ids = self.tokenizer.encode(text)
        self.tokens = torch.tensor(token_ids, dtype=torch.long)

        # Padding check: If the total token list is shorter than seq_len + 1,
        # pad it with the vocabulary pad ID. We need at least seq_len + 1 tokens
        # to form a single input-target sequence pair without throwing errors.
        required_len = seq_len + 1
        if len(self.tokens) < required_len:
            pad_id = getattr(self.tokenizer, 'pad_id', 0)
            padding_len = required_len - len(self.tokens)
            padding = torch.full((padding_len,), pad_id, dtype=torch.long)
            self.tokens = torch.cat([self.tokens, padding])

    def _read_file(self, filepath: str) -> str:
        """Reads text from a file with UTF-8 encoding.

        Args:
            filepath: Path to the file.

        Returns:
            The file contents as a single string.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found at: {filepath}")
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()

    def __len__(self) -> int:
        """Returns the total number of training sample pairs."""
        # The last sample starts at len(self.tokens) - seq_len - 1
        max_start = len(self.tokens) - self.seq_len
        if max_start <= 0:
            return 0
        return (max_start - 1) // self.stride + 1

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        """Retrieves a single (input, target) training pair.

        Args:
            idx: The index of the training sample.

        Returns:
            A tuple of (input_tensor, target_tensor), each of shape (seq_len,).
        """
        start_idx = idx * self.stride
        x = self.tokens[start_idx : start_idx + self.seq_len]
        y = self.tokens[start_idx + 1 : start_idx + self.seq_len + 1]
        return x, y
