"""API Router for triggering, pausing, resuming, halting training, and fetching metrics.
"""

from fastapi import APIRouter
from typing import Dict, Any
from backend.app.schemas.responses import TrainingRequest, TrainingStatusResponse
from backend.app.services.trainer_service import trainer_service
from backend.app.core.config import settings

router = APIRouter(tags=["Training"])


@router.post("/train/start")
async def post_train_start(req: TrainingRequest) -> Dict[str, Any]:
    """Starts model training in a background daemon thread."""
    if trainer_service.is_training:
        return {"success": False, "message": "Training session is already active."}

    from backend.app.services.tokenizer_service import tokenizer
    trainer_service.configure(req.settings, tokenizer)
    success = trainer_service.start(settings.DATA_DIR)
    
    if success:
        return {"success": True, "message": "Training started successfully."}
    return {"success": False, "message": "Could not launch background thread."}


@router.post("/train/pause")
async def post_train_pause() -> Dict[str, Any]:
    """Pauses the active training process."""
    if not trainer_service.is_training:
        return {"success": False, "message": "Training is not running."}
    trainer_service.pause()
    return {"success": True, "message": "Training paused successfully."}


@router.post("/train/resume")
async def post_train_resume() -> Dict[str, Any]:
    """Resumes the paused training process."""
    if not trainer_service.is_training:
        return {"success": False, "message": "Training is not running."}
    trainer_service.resume()
    return {"success": True, "message": "Training resumed successfully."}


@router.post("/train/stop")
async def post_train_stop() -> Dict[str, Any]:
    """Stops the active training thread."""
    if not trainer_service.is_training:
        return {"success": False, "message": "Training is not running."}
    trainer_service.stop()
    return {"success": True, "message": "Training stop request dispatched."}


@router.get("/train/status", response_model=TrainingStatusResponse)
async def get_train_status() -> Dict[str, Any]:
    """Queries current training steps metrics and trailing logs."""
    return {
        "is_training": trainer_service.is_training,
        "current_epoch": trainer_service.current_epoch,
        "current_step": trainer_service.current_step,
        "losses": trainer_service.losses[-100:],  # Return trailing 100 entries
        "val_losses": trainer_service.val_losses,
        "logs": trainer_service.logs[-50:]  # Return last 50 lines
    }


@router.get("/train/history")
async def get_train_history() -> Dict[str, Any]:
    """Returns the full loss and validation metrics history list."""
    return {
        "losses": trainer_service.losses,
        "val_losses": trainer_service.val_losses
    }


@router.get("/train/loss")
async def get_train_loss() -> Dict[str, Any]:
    """Returns the single current step loss value."""
    latest_loss = trainer_service.losses[-1] if trainer_service.losses else {"step": 0, "loss": 0.0}
    return {
        "loss": latest_loss.get("loss", 0.0),
        "step": latest_loss.get("step", 0)
    }
