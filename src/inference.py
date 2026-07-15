"""Inference engine module for MyGPT.

This module implements autoregressive text generation algorithms supporting greedy,
temperature scaling, top-k, and top-p (nucleus) sampling strategies.
"""

import torch
import torch.nn.functional as F
from src.model import GPT


@torch.no_grad()
def generate(
    model: GPT,
    idx: torch.Tensor,
    max_new_tokens: int,
    temperature: float = 1.0,
    top_k: int = 0,
    top_p: float = 0.0,
    eos_id: int = -1,
) -> torch.Tensor:
    """Generates a sequence of token IDs starting from a prompt context.

    Args:
        model: An instantiated, trained GPT model.
        idx: Initial prompt ID tensor of shape (batch_size, seq_len).
        max_new_tokens: Maximum number of tokens to generate.
        temperature: Scaling factor for logits (lower increases confidence, higher increases random diversity).
        top_k: Keep only top-k highest probability tokens (0 means disabled).
        top_p: Keep only tokens whose cumulative probability is less than top-p (0.0 means disabled).
        eos_id: Optional end-of-sequence token ID. Generation halts if this ID is drawn.

    Returns:
        The token ID tensor with shape (batch_size, seq_len + generated_len) containing prompt and generated outputs.
    """
    model.eval()
    context_len = model.config.context_len

    for _ in range(max_new_tokens):
        # Crop prompt context if it exceeds the model's max positional context length
        idx_cond = idx[:, -context_len:]

        # Forward pass to retrieve logits
        logits, _ = model(idx_cond)

        # Focus only on the prediction at the last step: shape (batch_size, vocab_size)
        logits = logits[:, -1, :]

        # 1. Apply Temperature Scaling
        if temperature > 0.0 and temperature != 1.0:
            logits = logits / temperature

        # 2. Apply Top-k Filtering
        if top_k > 0:
            k_val = min(top_k, logits.size(-1))
            # Find the value of the kth element in each row
            v, _ = torch.topk(logits, k_val)
            # Mask out any logits smaller than the kth value
            logits[logits < v[:, [-1]]] = float("-inf")

        # 3. Apply Top-p (Nucleus) Filtering
        if 0.0 < top_p < 1.0:
            # Sort logits in descending order
            sorted_logits, sorted_indices = torch.sort(logits, descending=True, dim=-1)
            cumulative_probs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)

            # Mask tokens with cumulative probability exceeding threshold
            # Shift mask right to include the first token exceeding the threshold
            sorted_indices_to_remove = cumulative_probs > top_p
            sorted_indices_to_remove[..., 1:] = sorted_indices_to_remove[..., :-1].clone()
            sorted_indices_to_remove[..., 0] = False

            # Scatter back to the original index positions
            indices_to_remove = sorted_indices_to_remove.scatter(
                1, sorted_indices, sorted_indices_to_remove
            )
            logits[indices_to_remove] = float("-inf")

        # Compute probabilities
        probs = F.softmax(logits, dim=-1)

        # 4. Draw next token index
        if temperature == 0.0:
            # Greedy decoding: pick the absolute highest probability index
            next_id = torch.argmax(probs, dim=-1, keepdim=True)
        else:
            # Multinomial sampling based on computed probability weights
            next_id = torch.multinomial(probs, num_samples=1)

        # Concatenate generated index to sequence context
        idx = torch.cat((idx, next_id), dim=1)

        # Stop early if the model generates the EOS token
        if eos_id >= 0 and next_id.item() == eos_id:
            break

    return idx
