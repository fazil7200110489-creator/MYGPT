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
from backend.app.core.logging import configure_logging

# Initialize logger outputs and configurations
configure_logging()

# Import routers
from backend.app.api.routers import company_ai, tender_v1

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
app.include_router(company_ai.router, prefix="/api")
app.include_router(tender_v1.router, prefix="/api")


@app.get("/")
async def root():
    """Root status endpoint confirming the backend service is running."""
    return {
        "status": "online",
        "message": "MyGPT Backend Running",
        "version": settings.VERSION,
        "docs": "/docs"
    }


@app.on_event("startup")
async def startup_event():
    logger.info("Initializing MyGPT Tender Extraction Engine services...")

    # Pre-load primary general answer model (Gemma 4 E2B, with Qwen fallback) into memory on boot
    logger.info("Pre-loading local answer model into memory...")
    try:
        from backend.app.services.llm.answer_model_service import answer_model_service
        answer_model_service.pre_load()
    except Exception as e:
        logger.error(f"Failed to pre-load answer model on startup: {e}")

    # Initialize ModelRegistry on boot
    logger.info("Initializing ModelRegistry...")
    try:
        from backend.app.services.llm.model_registry import model_registry
        logger.info(f"ModelRegistry initialized with {len(model_registry.list_models())} models.")
    except Exception as e:
        logger.error(f"Failed to initialize ModelRegistry on startup: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
