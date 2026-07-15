"""Inference service wrapper for executing text generation and token streaming.
"""

import torch
import torch.nn.functional as F
import asyncio
from typing import AsyncGenerator, Any
from loguru import logger
from backend.app.services.model_manager import model_manager


async def generate_stream(
    prompt: str,
    tokenizer: Any,
    max_tokens: int,
    temperature: float = 1.0,
    top_k: int = 0,
    top_p: float = 0.0,
) -> AsyncGenerator[str, None]:
    """Generates tokens autoregressively and yields them one-by-one.

    Args:
        prompt: Starting input context prompt text.
        tokenizer: Trained BPETokenizer.
        max_tokens: Maximum number of tokens to draw.
        temperature: Logits scaling parameter.
        top_k: Top-K filters count.
        top_p: Nucleus top-p threshold.

    Yields:
        Each generated token string in succession.
    """
    model = model_manager.load_model()
    model.eval()

    device = model_manager.device
    context_len = model.config.context_len
    eos_id = tokenizer.w2i.get(tokenizer.eos_token, -1)

    # Encode initial prompt context
    ids = tokenizer.encode(prompt)
    if not ids:
        ids = [tokenizer.w2i[tokenizer.bos_token]]

    idx = torch.tensor([ids], dtype=torch.long, device=device)
    logger.info(f"Stream generation triggered for prompt: '{prompt}'")

    for _ in range(max_tokens):
        # Yield execution thread time slice
        await asyncio.sleep(0.01)

        # Crop input context size if it exceeds structural context length
        idx_cond = idx[:, -context_len:]
        
        with torch.no_grad():
            logits, _ = model(idx_cond)

        # Target logits of the final sequence index
        logits = logits[:, -1, :]

        # 1. Temperature scaling
        if temperature > 0.0 and temperature != 1.0:
            logits = logits / temperature

        # 2. Top-K filtering
        if top_k > 0:
            k_val = min(top_k, logits.size(-1))
            v, _ = torch.topk(logits, k_val)
            logits[logits < v[:, [-1]]] = float("-inf")

        # 3. Top-P nucleus filtering
        if 0.0 < top_p < 1.0:
            sorted_logits, sorted_indices = torch.sort(logits, descending=True, dim=-1)
            cumulative_probs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)

            sorted_indices_to_remove = cumulative_probs > top_p
            sorted_indices_to_remove[..., 1:] = sorted_indices_to_remove[..., :-1].clone()
            sorted_indices_to_remove[..., 0] = False

            indices_to_remove = sorted_indices_to_remove.scatter(
                1, sorted_indices, sorted_indices_to_remove
            )
            logits[indices_to_remove] = float("-inf")

        # Probability distribution mapping
        probs = F.softmax(logits, dim=-1)

        # Draw next index
        if temperature == 0.0:
            next_id = torch.argmax(probs, dim=-1, keepdim=True)
        else:
            next_id = torch.multinomial(probs, num_samples=1)

        # Concatenate generated index
        idx = torch.cat((idx, next_id), dim=1)

        # Format subword token string
        token_str = tokenizer.i2w.get(next_id.item(), tokenizer.unk_token)
        clean_token = token_str.replace("</w>", " ")

        yield clean_token

        # Break early if end-of-sequence token is reached
        if next_id.item() == eos_id:
            break
