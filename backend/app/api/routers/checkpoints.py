"""API Router for listing, saving, loading, and deleting model weights checkpoints.
"""

import os
import time
import torch
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from backend.app.core.config import settings
from backend.app.schemas.responses import CheckpointResponse, LoadCheckpointRequest, TrainingRequest
from backend.app.services.model_manager import model_manager
from backend.app.model.model import GPT, GPTConfig

router = APIRouter(tags=["Checkpoints"])


@router.get("/checkpoints", response_model=List[CheckpointResponse])
async def get_checkpoints_list() -> List[Dict[str, Any]]:
    """Lists saved checkpoint metadata files."""
    checkpoints_list = []
    checkpoint_dir = settings.CHECKPOINT_DIR
    if os.path.exists(checkpoint_dir):
        files = [f for f in os.listdir(checkpoint_dir) if f.endswith(".pt")]
        for f in sorted(files):
            filepath = os.path.join(checkpoint_dir, f)
            stats = os.stat(filepath)
            
            try:
                ckpt = torch.load(filepath, map_location="cpu")
                epoch = ckpt.get("epoch", "-")
                # Look for losses
                loss_val = ckpt.get("loss", "N/A")
                if isinstance(loss_val, float):
                    loss_val = f"{loss_val:.4f}"
            except Exception:
                epoch = "-"
                loss_val = "N/A"

            checkpoints_list.append({
                "filename": f,
                "epoch": epoch,
                "loss": loss_val,
                "size_mb": round(stats.st_size / (1024 * 1024), 2),
                "date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stats.st_mtime))
            })
    return checkpoints_list


@router.post("/checkpoint/load")
async def post_checkpoint_load(req: LoadCheckpointRequest) -> Dict[str, Any]:
    """Loads weights from a saved checkpoint file into active memory."""
    filepath = os.path.join(settings.CHECKPOINT_DIR, req.filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"Checkpoint file {req.filename} not found.")

    try:
        from backend.app.services.tokenizer_service import tokenizer
        checkpoint = torch.load(filepath, map_location="cpu")
        cfg_dict = checkpoint["config"]
        
        # Instantiate model structure
        cfg = GPTConfig(
            vocab_size=len(tokenizer.w2i),
            context_len=int(cfg_dict["seq_len"]),
            embedding_dim=int(cfg_dict["embedding_dim"]),
            num_heads=int(cfg_dict["num_heads"]),
            hidden_dim=int(cfg_dict["hidden_dim"]),
            num_layers=int(cfg_dict["num_layers"])
        )
        
        # Load weights
        model_manager.model = GPT(cfg)
        model_manager.model.load_state_dict(checkpoint["model_state_dict"])
        model_manager.model = model_manager.model.to(model_manager.device)
        model_manager.config_dict.update(cfg_dict)
        
        # Sync trainer if active
        from backend.app.services.trainer_service import trainer_service
        trainer_service.model = model_manager.model
        trainer_service.config.update(cfg_dict)
        trainer_service.current_epoch = checkpoint.get("epoch", 1)

        return {"success": True, "message": f"Checkpoint {req.filename} loaded successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load checkpoint: {str(e)}")


@router.post("/checkpoint/save")
async def post_checkpoint_save(req: TrainingRequest) -> Dict[str, Any]:
    """Manually saves current active model weights to the checkpoint directory."""
    if not model_manager.model:
        raise HTTPException(status_code=400, detail="No active model found in memory to save.")

    os.makedirs(settings.CHECKPOINT_DIR, exist_ok=True)
    filename = f"manual_checkpoint_{int(time.time())}.pt"
    filepath = os.path.join(settings.CHECKPOINT_DIR, filename)

    try:
        torch.save({
            "epoch": "manual",
            "model_state_dict": model_manager.model.state_dict(),
            "config": model_manager.config_dict,
            "loss": 0.0
        }, filepath)
        return {"success": True, "message": f"Manual checkpoint saved: {filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save checkpoint: {str(e)}")


@router.delete("/checkpoint/delete")
async def delete_checkpoint(filename: str) -> Dict[str, Any]:
    """Deletes a saved checkpoint file from disk."""
    filepath = os.path.join(settings.CHECKPOINT_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Checkpoint file not found.")

    try:
        os.remove(filepath)
        return {"success": True, "message": f"Checkpoint {filename} deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete checkpoint file: {str(e)}")
