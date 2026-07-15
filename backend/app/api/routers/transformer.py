"""API Router for hidden states trace analysis and block configurations inspector.
"""

import torch
from fastapi import APIRouter
from typing import Dict, Any, List
from backend.app.schemas.responses import TokenizerRequest
from backend.app.services.model_manager import model_manager
from backend.app.model.model import GPT, GPTConfig

router = APIRouter(tags=["Transformer"])


@router.post("/transformer")
async def trace_transformer_hidden_states(req: TokenizerRequest) -> Dict[str, Any]:
    """Runs a trace of hidden states layer by layer, returning shapes and memory stats."""
    from backend.app.services.tokenizer_service import tokenizer
    
    ids = tokenizer.encode(req.text)
    if not ids:
        return {"layers": []}

    seq_len = len(ids)
    # Load model dynamically to ensure the active model is loaded in memory
    model = model_manager.load_model()

    model.eval()

    layers_trace = []
    
    # Trace step-by-step activations
    with torch.no_grad():
        # 1. Embeddings
        x = model.token_embeddings(torch.tensor([ids], dtype=torch.long))
        x = model.pos_embeddings(x)
        
        layers_trace.append({
            "component": "Embedding & Positional Add",
            "shape": list(x.shape),
            "mean": float(x.mean()),
            "std": float(x.std()),
            "memory_bytes": x.element_size() * x.nelement()
        })

        # 2. Block Stacks
        for idx, block in enumerate(model.blocks):
            x, _ = block(x)
            layers_trace.append({
                "component": f"Transformer Block {idx + 1}",
                "shape": list(x.shape),
                "mean": float(x.mean()),
                "std": float(x.std()),
                "memory_bytes": x.element_size() * x.nelement()
            })

        # 3. Final layer norm
        x = model.ln_f(x)
        layers_trace.append({
            "component": "Final LayerNorm",
            "shape": list(x.shape),
            "mean": float(x.mean()),
            "std": float(x.std()),
            "memory_bytes": x.element_size() * x.nelement()
        })

    return {
        "sequence_length": seq_len,
        "embedding_dim": model.config.embedding_dim,
        "layers": layers_trace
    }
