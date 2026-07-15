"""API Router for model inference predictions and token-by-token text generation streaming.
"""

import torch
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Dict, Any, List
from backend.app.schemas.responses import InferenceRequest, InferenceResponse
from backend.app.services.model_manager import model_manager
from backend.app.services.inference_service import generate_stream
from backend.app.model.inference import generate

router = APIRouter(tags=["Inference"])


@router.post("/inference", response_model=InferenceResponse)
async def post_inference(req: InferenceRequest) -> Dict[str, Any]:
    """Computes a standard next-token predictions sequence forward pass."""
    from backend.app.services.tokenizer_service import tokenizer
    
    ids = tokenizer.encode(req.prompt)
    if not ids:
        ids = [tokenizer.w2i[tokenizer.bos_token]]

    # Untrained model protection: check checkpoints and active training status
    import os
    from backend.app.core.config import settings
    from backend.app.services.trainer_service import trainer_service
    
    checkpoint_dir = settings.CHECKPOINT_DIR
    has_checkpoints = os.path.exists(checkpoint_dir) and any(f.endswith(".pt") for f in os.listdir(checkpoint_dir))
    is_trained = has_checkpoints or (trainer_service.model is not None and trainer_service.current_step > 0)
    
    if not is_trained:
        return {
            "prompt": req.prompt,
            "input_ids": ids,
            "output_ids": [],
            "generated_text": "This model has not been trained yet. Please train it before running inference."
        }

    model = model_manager.load_model()
    input_tensor = torch.tensor([ids], dtype=torch.long, device=model_manager.device)

    eos_id = tokenizer.w2i.get(tokenizer.eos_token, -1)
    
    # Resolve custom stop token IDs
    stop_ids = []
    if req.stop_tokens:
        for t in req.stop_tokens:
            if t in tokenizer.w2i:
                stop_ids.append(tokenizer.w2i[t])

    try:
        with torch.no_grad():
            output_ids = generate(
                model=model,
                idx=input_tensor,
                max_new_tokens=req.max_tokens,
                temperature=req.temperature,
                top_k=req.top_k,
                top_p=req.top_p,
                eos_id=eos_id,
                stop_ids=stop_ids
            )
        
        output_list = output_ids[0].cpu().tolist()
        generated_text = tokenizer.decode(output_list)
        
        return {
            "prompt": req.prompt,
            "input_ids": ids,
            "output_ids": output_list,
            "generated_text": generated_text
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference execution failed: {str(e)}")


@router.post("/inference/stream")
async def post_inference_stream(req: InferenceRequest) -> StreamingResponse:
    """Returns a Server-Sent Events (SSE) stream yielding generated subwords in real-time."""
    from backend.app.services.tokenizer_service import tokenizer
    
    async def token_generator():
        try:
            async for token in generate_stream(
                prompt=req.prompt,
                tokenizer=tokenizer,
                max_tokens=req.max_tokens,
                temperature=req.temperature,
                top_k=req.top_k,
                top_p=req.top_p
            ):
                yield token
        except Exception as e:
            yield f"\n[STREAM ERROR: {str(e)}]"

    return StreamingResponse(token_generator(), media_type="text/plain")
