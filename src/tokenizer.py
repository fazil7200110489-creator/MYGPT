"""Byte Pair Encoding (BPE) Tokenizer module for MyGPT.

This module implements a subword-level BPE tokenizer completely from scratch.
"""

import re
import json
from typing import List, Dict, Tuple, Optional


class BPETokenizer:
    """A subword BPE tokenizer built from first principles."""

    def __init__(self, vocab_file: Optional[str] = None) -> None:
        """Initializes the tokenizer.

        Args:
            vocab_file: Optional path to a JSON file containing pre-trained vocabulary and merges.
        """
        self.special_tokens = ["<PAD>", "<UNK>", "<BOS>", "<EOS>"]
        self.w2i: Dict[str, int] = {}
        self.i2w: Dict[int, str] = {}
        self.merges: Dict[Tuple[str, str], int] = {}  # Maps pair of subwords -> merge rank index

        # Definitions
        self.pad_token = "<PAD>"
        self.unk_token = "<UNK>"
        self.bos_token = "<BOS>"
        self.eos_token = "<EOS>"

        if vocab_file is not None:
            self.load(vocab_file)
        else:
            self._init_special_tokens()

    def _init_special_tokens(self) -> None:
        """Registers the default special tokens in vocabulary mappings."""
        self.w2i = {}
        self.i2w = {}
        for token in self.special_tokens:
            self._add_to_vocab(token)

        self.pad_id = self.w2i[self.pad_token]
        self.unk_id = self.w2i[self.unk_token]
        self.bos_id = self.w2i[self.bos_token]
        self.eos_id = self.w2i[self.eos_token]

    def _add_to_vocab(self, token: str) -> int:
        """Adds a token string to the vocabulary if not already present."""
        if token not in self.w2i:
            idx = len(self.w2i)
            self.w2i[token] = idx
            self.i2w[idx] = token
        return self.w2i[token]

    def train(self, text: str, vocab_size: int, min_freq: int = 2) -> None:
        """Trains the BPE tokenizer on a raw text corpus.

        Iteratively discovers and records the most frequent adjacent character/subword merges.

        Args:
            text: Training corpus.
            vocab_size: Target vocabulary size.
            min_freq: Minimum frequency threshold to permit a merge.
        """
        self._init_special_tokens()

        # Step 1: Pre-tokenize corpus into words and punctuation
        # We append </w> (end-of-word marker) to each token
        raw_words = re.findall(r"\w+|[^\w\s]", text.lower())
        
        # Word frequency dictionary: tuple of characters -> frequency
        word_freqs: Dict[Tuple[str, ...], int] = {}
        for word in raw_words:
            char_tuple = tuple(list(word) + ["</w>"])
            word_freqs[char_tuple] = word_freqs.get(char_tuple, 0) + 1

        # Register all initial unique characters in the vocabulary
        unique_chars = set()
        for word_tuple in word_freqs.keys():
            for char in word_tuple:
                unique_chars.add(char)
        
        for char in sorted(list(unique_chars)):
            self._add_to_vocab(char)

        # Step 2: Iterative merge discovery loop
        # We stop if we reach the target vocab size, or if no pair exceeds min_freq
        self.merges = {}
        merge_rank = 0

        while len(self.w2i) < vocab_size:
            # Count adjacent pairs
            pair_counts: Dict[Tuple[str, str], int] = {}
            for word_tuple, freq in word_freqs.items():
                for i in range(len(word_tuple) - 1):
                    pair = (word_tuple[i], word_tuple[i + 1])
                    pair_counts[pair] = pair_counts.get(pair, 0) + freq

            if not pair_counts:
                break

            # Find the most frequent pair
            best_pair = max(pair_counts, key=pair_counts.get)
            best_freq = pair_counts[best_pair]

            if best_freq < min_freq:
                # Stop if frequency is too low
                break

            # Save the merge rule and update vocabulary
            self.merges[best_pair] = merge_rank
            merge_rank += 1

            new_token = best_pair[0] + best_pair[1]
            self._add_to_vocab(new_token)

            # Update the corpus word_freqs by merging the best pair
            word_freqs = self._merge_pair_in_corpus(best_pair, word_freqs)

    def _merge_pair_in_corpus(
        self, pair: Tuple[str, str], word_freqs: Dict[Tuple[str, ...], int]
    ) -> Dict[Tuple[str, ...], int]:
        """Performs merge substitution on all word tuples in the corpus representation."""
        p1, p2 = pair
        new_token = p1 + p2
        merged_freqs = {}

        for word, freq in word_freqs.items():
            new_word = []
            i = 0
            while i < len(word):
                if i < len(word) - 1 and word[i] == p1 and word[i + 1] == p2:
                    new_word.append(new_token)
                    i += 2
                else:
                    new_word.append(word[i])
                    i += 1
            merged_freqs[tuple(new_word)] = freq
        return merged_freqs

    def tokenize(self, text: str) -> List[str]:
        """Tokenizes raw text into a list of BPE subwords."""
        if not text:
            return []
        
        # Split text into words and punctuation
        words = re.findall(r"\w+|[^\w\s]", text.lower())
        tokens = []

        for word_str in words:
            # Initialize word as a list of characters, replacing unseen ones with <UNK>
            word_tokens = []
            for char in word_str:
                if char in self.w2i:
                    word_tokens.append(char)
                else:
                    word_tokens.append(self.unk_token)
            word_tokens.append("</w>")

            # Iteratively apply merges
            while len(word_tokens) > 1:
                # Find all current adjacent pairs
                pairs = [(word_tokens[i], word_tokens[i + 1]) for i in range(len(word_tokens) - 1)]
                # Filter to pairs present in merges
                valid_pairs = [p for p in pairs if p in self.merges]
                if not valid_pairs:
                    break
                # Select the merge rule with the lowest rank (first trained)
                best_pair = min(valid_pairs, key=lambda p: self.merges[p])

                # Apply merge
                new_tokens = []
                p1, p2 = best_pair
                new_token = p1 + p2
                i = 0
                while i < len(word_tokens):
                    if i < len(word_tokens) - 1 and word_tokens[i] == p1 and word_tokens[i + 1] == p2:
                        new_tokens.append(new_token)
                        i += 2
                    else:
                        new_tokens.append(word_tokens[i])
                        i += 1
                word_tokens = new_tokens

            tokens.extend(word_tokens)

        return tokens

    def encode(self, text: str, add_bos: bool = False, add_eos: bool = False) -> List[int]:
        """Converts raw text into a list of integer token IDs."""
        tokens = self.tokenize(text)
        ids = [self.w2i.get(token, self.w2i[self.unk_token]) for token in tokens]

        if add_bos:
            ids.insert(0, self.w2i[self.bos_token])
        if add_eos:
            ids.append(self.w2i[self.eos_token])

        return ids

    def decode(self, ids: List[int], skip_special: bool = True) -> str:
        """Converts token IDs back to a readable text string."""
        tokens = []
        for idx in ids:
            token = self.i2w.get(idx, self.unk_token)
            if skip_special and token in self.special_tokens:
                continue
            tokens.append(token)

        if not tokens:
            return ""

        # Reconstruct text by replacing </w> with spaces
        raw_text = "".join(tokens)
        decoded = raw_text.replace("</w>", " ")
        return decoded.strip()

    def save(self, filepath: str) -> None:
        """Saves BPE configuration (vocabulary and merges) to a JSON file."""
        # Convert merges tuple keys to strings for JSON compatibility
        serializable_merges = {f"{p[0]} {p[1]}": rank for p, rank in self.merges.items()}
        data = {
            "w2i": self.w2i,
            "merges": serializable_merges
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def load(self, filepath: str) -> None:
        """Loads BPE configuration from a JSON file."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.w2i = data["w2i"]
        self.i2w = {int(k) if k.isdigit() else k: v for k, v in self.w2i.items()}
        # Reconstruct i2w
        self.i2w = {v: k for k, v in self.w2i.items()}

        # Reconstruct merges dictionary
        self.merges = {}
        for pair_str, rank in data["merges"].items():
            p1, p2 = pair_str.split(" ")
            self.merges[(p1, p2)] = rank

        self.pad_id = self.w2i[self.pad_token]
        self.unk_id = self.w2i[self.unk_token]
        self.bos_id = self.w2i[self.bos_token]
        self.eos_id = self.w2i[self.eos_token]


class WordTokenizer:
    """A simple word-level tokenizer using basic string splitting and punctuation preservation."""

    def __init__(self, vocab: "Vocabulary") -> None:
        """Initializes the tokenizer with a Vocabulary instance.

        Args:
            vocab: An instance of the Vocabulary class.
        """
        self.vocab = vocab

    def tokenize(self, text: str) -> List[str]:
        """Splits raw text into a list of word and punctuation tokens.

        Converts text to lowercase, preserves words, numbers, and punctuation
        characters like ',' and '.', and discards other characters.

        Args:
            text: Raw input text.

        Returns:
            A list of string tokens.
        """
        if not text:
            return []
        # Match words, numbers, or specific punctuation: comma and period.
        # Other characters like @ and # are ignored.
        tokens = re.findall(r"\w+|[,.]", text.lower())
        return tokens

    def encode(self, text: str, add_bos: bool = False, add_eos: bool = False) -> List[int]:
        """Converts raw text into a list of integer token IDs.

        Args:
            text: Raw input text.
            add_bos: If True, adds the BOS token ID to the beginning.
            add_eos: If True, adds the EOS token ID to the end.

        Returns:
            A list of integer token IDs.
        """
        tokens = self.tokenize(text)
        ids = [self.vocab.get_id(token) for token in tokens]

        if add_bos:
            ids.insert(0, self.vocab.bos_id)
        if add_eos:
            ids.append(self.vocab.eos_id)

        return ids

    def decode(self, ids: List[int], skip_special: bool = True) -> str:
        """Converts token IDs back to a readable text string.

        Joins the tokens with spaces and corrects spaces before punctuation.

        Args:
            ids: List of integer token IDs.
            skip_special: If True, excludes special tokens (except UNK).

        Returns:
            Reconstructed string text.
        """
        # When skip_special is True, we only skip PAD, BOS, and EOS.
        # We preserve UNK so that unknown tokens can be visualized.
        skip_tokens = {self.vocab.pad_token, self.vocab.bos_token, self.vocab.eos_token}
        
        decoded_tokens = []
        for idx in ids:
            token = self.vocab.get_word(idx)
            if skip_special and token in skip_tokens:
                continue
            decoded_tokens.append(token)

        if not decoded_tokens:
            return ""

        # Join tokens with space, then clean up spacing before punctuation
        text = " ".join(decoded_tokens)
        # Remove spaces before comma, period, question mark, exclamation, colon, semicolon
        text = re.sub(r"\s+([,.:!?])", r"\1", text)
        return text.strip()
