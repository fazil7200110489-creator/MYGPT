"""API Router for model status, dashboard statistics, and health checks.
"""

from fastapi import APIRouter
from typing import Dict, Any
from backend.app.services.model_manager import model_manager
from backend.app.services.trainer_service import trainer_service
from backend.app.schemas.responses import (
    DashboardResponse, ModelInfoResponse, TrainingRequest, ModelConfigRequest, ModelConfigResponse
)

router = APIRouter(tags=["Model"])


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Basic health check endpoint."""
    return {"status": "healthy"}


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard_stats() -> Dict[str, Any]:
    """Returns real-time dashboard variables and current training progress."""
    model = model_manager.load_model()
    total_params = sum(p.numel() for p in model.parameters())

    # Dynamically extract details from trainer
    from backend.app.services.tokenizer_service import tokenizer
    vocab_size = len(tokenizer.w2i)
    
    return {
        "model_name": "MyGPT-v2",
        "version": "2.0.0",
        "device": model_manager.device,
        "is_training": trainer_service.is_training,
        "vocab_size": vocab_size,
        "embedding_dim": int(trainer_service.config["embedding_dim"]),
        "num_layers": int(trainer_service.config["num_layers"]),
        "num_heads": int(trainer_service.config["num_heads"]),
        "context_len": int(trainer_service.config["seq_len"]),
        "current_epoch": trainer_service.current_epoch,
        "current_step": trainer_service.current_step,
        "total_params": total_params
    }


@router.get("/model/info", response_model=ModelInfoResponse)
async def get_model_info() -> Dict[str, Any]:
    """Returns model weights dictionary keys and dimension shapes."""
    return model_manager.get_info()


@router.get("/model/status")
async def get_model_status() -> Dict[str, Any]:
    """Returns active loading status and device details."""
    return model_manager.get_status()


@router.get("/settings")
async def get_settings() -> Dict[str, Any]:
    """Returns active settings parameters."""
    return {"settings": trainer_service.config}


@router.post("/settings/save")
async def post_settings_save(req: TrainingRequest) -> Dict[str, Any]:
    """Updates hyperparameter settings."""
    from backend.app.services.tokenizer_service import tokenizer
    # Sync with trainer configurations
    trainer_service.configure(req.settings, tokenizer)
    # Sync with model manager configurations
    model_manager.config_dict.update(req.settings)
    
    # Reload model dynamically if not actively training
    if not trainer_service.is_training:
        try:
            model_manager.reload_model(req.settings)
        except Exception as e:
            return {"success": False, "message": f"Settings updated, but model rebuild failed: {str(e)}"}
            
    return {"success": True, "message": "Settings saved successfully."}


@router.get("/model/config", response_model=ModelConfigResponse)
async def get_model_config() -> Dict[str, int]:
    """Returns the persistent model configuration."""
    cfg = model_manager.load_persistent_config()
    return {
        "max_sequence_length": cfg["max_sequence_length"],
        "embedding_dimension": cfg["embedding_dimension"]
    }


@router.post("/model/config")
async def post_model_config(req: ModelConfigRequest) -> Dict[str, Any]:
    """Updates and persists the model configuration."""
    model_manager.save_persistent_config(
        max_sequence_length=req.max_sequence_length,
        embedding_dimension=req.embedding_dimension
    )
    
    # Sync active configuration settings
    model_manager.config_dict["seq_len"] = req.max_sequence_length
    model_manager.config_dict["embedding_dim"] = req.embedding_dimension
    trainer_service.config["seq_len"] = req.max_sequence_length
    trainer_service.config["embedding_dim"] = req.embedding_dimension

    # Reload model dynamically if not actively training
    rebuilt = False
    message = "Configuration saved successfully."
    if not trainer_service.is_training:
        try:
            model_manager.reload_model()
            rebuilt = True
            message = "Configuration saved and model reinitialized successfully."
        except Exception as e:
            return {"success": False, "message": f"Configuration saved, but model rebuild failed: {str(e)}"}
    else:
        message = "Configuration saved. Model reinitialization will take effect on next start, as training is currently active."

    return {
        "success": True,
        "message": message,
        "rebuilt": rebuilt,
        "config": {
            "max_sequence_length": req.max_sequence_length,
            "embedding_dimension": req.embedding_dimension
        }
    }

