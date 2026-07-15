"""API Router for token representation embedding weights and heatmap coordinates.
"""

import torch
from fastapi import APIRouter
from typing import Dict, Any
from backend.app.schemas.responses import TokenizerRequest, EmbeddingResponse
from backend.app.services.model_manager import model_manager
from backend.app.model.embeddings import CustomEmbedding

router = APIRouter(tags=["Embeddings"])


@router.post("/embedding", response_model=EmbeddingResponse)
async def get_embedding_weights(req: TokenizerRequest) -> Dict[str, Any]:
    """Retrieves embedding coordinates and statistical summary for text tokens."""
    from backend.app.services.tokenizer_service import tokenizer
    
    ids = tokenizer.encode(req.text)
    if not ids:
        return {"shape": [0, 0], "embeddings": []}

    embedding_dim = int(model_manager.config_dict["embedding_dim"])
    
    # Check if model manager already holds loaded embeddings
    if model_manager.model:
        embed_layer = model_manager.model.token_embeddings
    else:
        embed_layer = CustomEmbedding(len(tokenizer.w2i), embedding_dim)

    # Perform lookup
    token_tensor = torch.tensor([ids], dtype=torch.long)
    with torch.no_grad():
        vectors = embed_layer(token_tensor).squeeze(0).cpu().numpy()

    # Convert vectors to serializable dictionary formats
    embeddings_data = []
    for idx, vec in zip(ids, vectors):
        embeddings_data.append({
            "id": idx,
            "token": tokenizer.i2w.get(idx, tokenizer.unk_token),
            "vector": vec.tolist(),
            "mean": float(vec.mean()),
            "std": float(vec.std()),
            "min": float(vec.min()),
            "max": float(vec.max()),
        })

    return {
        "shape": [len(ids), embedding_dim],
        "embeddings": embeddings_data
    }
