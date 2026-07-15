"""API Router for attention weight heatmaps, Queries, Keys, and Values projections.
"""

import torch
from fastapi import APIRouter
from typing import Dict, Any
from backend.app.schemas.responses import TokenizerRequest, AttentionResponse
from backend.app.services.model_manager import model_manager
from backend.app.model.model import GPT, GPTConfig

router = APIRouter(tags=["Attention"])


@router.post("/attention", response_model=AttentionResponse)
async def get_attention_maps(req: TokenizerRequest) -> Dict[str, Any]:
    """Computes causal self-attention weights and Q/K/V dimensions."""
    from backend.app.services.tokenizer_service import tokenizer
    
    ids = tokenizer.encode(req.text)
    if not ids:
        return {"tokens": [], "attention_weights": []}

    seq_len = len(ids)
    embedding_dim = int(model_manager.config_dict["embedding_dim"])
    num_heads = int(model_manager.config_dict["num_heads"])

    # Load model dynamically to ensure the active model is loaded in memory
    model = model_manager.load_model()

    model.eval()
    
    input_tensor = torch.tensor([ids], dtype=torch.long)
    try:
        with torch.no_grad():
            _, attentions = model(input_tensor)
        # Select first block layer weights: (num_heads, seq_len, seq_len)
        layer_weights = attentions[0][0].cpu().numpy().tolist()
    except Exception as e:
        # Fallback triangular masking weights
        layer_weights = [
            [[1.0 if j <= i else 0.0 for j in range(seq_len)] for i in range(seq_len)] 
            for _ in range(num_heads)
        ]
        print(f"Router attention fallback: {str(e)}")

    tokens = [tokenizer.i2w.get(idx, tokenizer.unk_token) for idx in ids]
    return {
        "tokens": tokens,
        "attention_weights": layer_weights
    }
