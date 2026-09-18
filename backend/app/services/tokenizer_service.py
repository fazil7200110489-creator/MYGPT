"""Tokenizer service initializing BPE vocabulary from sample text.
"""

import os
from loguru import logger
from backend.app.core.config import settings
from backend.app.model.tokenizer import BPETokenizer

tokenizer = BPETokenizer()

# Restore production vocabulary from checkpoints if available, else pre-train
vocab_path = os.path.join(settings.CHECKPOINT_DIR, "vocab.json")
if os.path.exists(vocab_path):
    try:
        tokenizer.load(vocab_path)
        logger.info(f"BPETokenizer restored from {vocab_path} with {len(tokenizer.w2i)} tokens.")
    except Exception as e:
        logger.error(f"Failed to load vocabulary from {vocab_path}: {e}")

if len(tokenizer.w2i) == 0:
    dataset_path = settings.DATASET_PATH
    if os.path.exists(dataset_path):
        try:
            with open(dataset_path, "r", encoding="utf-8") as f:
                corpus_text = f.read()
            tokenizer.train(corpus_text, vocab_size=100, min_freq=1)
            logger.info(f"BPETokenizer successfully trained with {len(tokenizer.w2i)} tokens.")
        except Exception as e:
            logger.error(f"Failed to pre-train BPE tokenizer: {str(e)}")
    else:
        # Minimal initial training on a dummy string to avoid empty vocabs if file is missing
        tokenizer.train("the cat sat on the mat. learning is rewarding.", vocab_size=50, min_freq=1)
        logger.warning("Dataset path not found. Initialized tokenizer with mock BPE vocabulary.")

