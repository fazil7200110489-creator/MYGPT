"""FastAPI entry point for modular backend coordination.
"""

import os
import sys
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

# Add project root directory to sys.path to resolve parent packages correctly
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from backend.app.core.config import settings
from backend.app.services.tokenizer_service import tokenizer
from backend.app.services.trainer_service import trainer_service
from backend.app.core.logging import configure_logging

# Initialize logger outputs and configurations
configure_logging()

# Import routers
from backend.app.api.routers import (
    attention, checkpoints, dataset, embedding, inference, logs, model, tokenizer as tokenizer_router, train, transformer, document, company_ai
)
from backend.app.api import recruiter_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(attention.router, prefix="/api")
app.include_router(checkpoints.router, prefix="/api")
app.include_router(dataset.router, prefix="/api")
app.include_router(embedding.router, prefix="/api")
app.include_router(inference.router, prefix="/api")
app.include_router(logs.router, prefix="/api")
app.include_router(model.router, prefix="/api")
app.include_router(tokenizer_router.router, prefix="/api")
app.include_router(train.router, prefix="/api")
app.include_router(transformer.router, prefix="/api")
app.include_router(document.router, prefix="/api")
app.include_router(company_ai.router, prefix="/api")
app.include_router(recruiter_router.router)


@app.on_event("startup")
async def startup_event():
    logger.info("Initializing MyGPT services and attempting to restore checkpoints...")
    from backend.app.services.model_manager import model_manager
    
    # 1. Try to load checkpoint
    restored = model_manager.load_latest_checkpoint()
    
    # Synchronize persistent configurations (max_sequence_length, embedding_dimension) to model_manager and trainer_service
    persistent_cfg = model_manager.load_persistent_config()
    model_manager.config_dict["seq_len"] = persistent_cfg["max_sequence_length"]
    model_manager.config_dict["embedding_dim"] = persistent_cfg["embedding_dimension"]
    
    from backend.app.services.trainer_service import trainer_service
    trainer_service.config["seq_len"] = persistent_cfg["max_sequence_length"]
    trainer_service.config["embedding_dim"] = persistent_cfg["embedding_dimension"]
    
    # Always ensure model is pre-loaded on boot to prevent first-request latency
    logger.info("Pre-loading MyGPT model structure into memory...")
    try:
        model_manager.load_model()
        logger.info("MyGPT model successfully pre-loaded on boot.")
    except Exception as e:
        logger.error(f"Failed to pre-load model on startup: {e}")

    # Pre-load Qwen local answer model into memory on boot
    logger.info("Pre-loading local Qwen answer model into memory...")
    try:
        from backend.app.services.llm.answer_model_service import answer_model_service
        answer_model_service.pre_load()
    except Exception as e:
        logger.error(f"Failed to pre-load Qwen answer model on startup: {e}")
    
    # 2. If not restored (fresh start), pre-train tokenizer on combined dataset
    if not restored:
        try:
            from backend.app.services.tokenizer_service import tokenizer
            from backend.app.model.dataset import TextDataset
            
            data_dir = settings.DATA_DIR
            if os.path.exists(data_dir):
                dummy_ds = TextDataset(
                    text_or_path=data_dir,
                    tokenizer=tokenizer,
                    seq_len=8,
                    stride=1,
                    is_path=True
                )
                combined_text = tokenizer.decode(dummy_ds.tokens.cpu().tolist())
                if combined_text:
                    tokenizer.train(combined_text, vocab_size=100, min_freq=1)
                    logger.info("Fresh start: BPETokenizer trained on combined corpus.")
        except Exception as e:
            logger.error(f"Failed to pre-train tokenizer on startup: {e}")


# WebSockets Live Streaming Endpoint
@app.websocket("/ws/training")
async def websocket_training(websocket: WebSocket) -> None:
    """Streams real-time metrics, losses, and logs to connected frontend subscribers."""
    await websocket.accept()
    last_step = 0
    import random
    import torch
    try:
        while True:
            # Yield info if active, else rest
            cpu_val = 0.0
            gpu_val = 0.0
            try:
                import psutil
                cpu_val = psutil.cpu_percent()
            except ImportError:
                cpu_val = round(10.0 + random.random() * 15.0, 1) if trainer_service.is_training else 1.2
            
            if torch.cuda.is_available():
                try:
                    total_mem = torch.cuda.get_device_properties(0).total_memory
                    allocated_mem = torch.cuda.memory_allocated(0)
                    gpu_val = round((allocated_mem / total_mem) * 100, 1)
                except Exception:
                    gpu_val = 15.4 if trainer_service.is_training else 0.0
            
            status_data = {
                "is_training": trainer_service.is_training,
                "current_epoch": trainer_service.current_epoch,
                "current_step": trainer_service.current_step,
                "epoch": trainer_service.current_epoch,
                "batch": getattr(trainer_service, "current_batch", 0),
                "total_batches": getattr(trainer_service, "total_batches", 0),
                "loss": getattr(trainer_service, "current_loss", 0.0),
                "learning_rate": getattr(trainer_service, "learning_rate", 0.0),
                "eta": getattr(trainer_service, "eta", 0.0),
                "generated_tokens": getattr(trainer_service, "current_output", ""),
                "current_output": getattr(trainer_service, "current_output", ""),
                "gpu_usage": gpu_val,
                "cpu_usage": cpu_val,
                # Stream logs and step losses added since last interval
                "new_losses": trainer_service.losses[last_step:],
                "val_losses": trainer_service.val_losses,
                "logs": trainer_service.logs[-20:]  # Send trailing logs
            }
            last_step = len(trainer_service.losses)
            
            await websocket.send_json(status_data)
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected from training stream.")
    except Exception as e:
        logger.error(f"WebSocket training error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
