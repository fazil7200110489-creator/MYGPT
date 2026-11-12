"""Configuration settings module for MyGPT Studio backend.
"""

import os


class Settings:
    """Global configuration settings for backend directories and CORS."""
    
    PROJECT_NAME: str = "MyGPT Studio API"
    VERSION: str = "2.0.0"
    API_PREFIX: str = "/api"

    # Directory Paths
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    CHECKPOINT_DIR: str = os.path.join(BASE_DIR, "checkpoints")
    LOGS_DIR: str = os.path.join(BASE_DIR, "logs")
    DATA_DIR: str = os.path.join(BASE_DIR, "data")
    DATASET_PATH: str = os.path.join(DATA_DIR, "sample.txt")
    MODELS_DIR: str = os.path.join(BASE_DIR, "models")

    # Local LLM and Specialized Model Paths (Configurable)
    _GEMMA4_GENERAL_PATH: str = os.path.join(MODELS_DIR, "local_llm", "gemma-4-E2B-it-Q4_K_M.gguf")
    _QWEN_ROLLBACK_PATH: str = (
        os.path.join(MODELS_DIR, "local_llm", "coding", "qwen2.5-coder-3b-instruct-q4_k_m.gguf")
        if os.path.exists(os.path.join(MODELS_DIR, "local_llm", "coding", "qwen2.5-coder-3b-instruct-q4_k_m.gguf"))
        else os.path.join(MODELS_DIR, "local_llm", "qwen2.5-coder-3b-instruct-q4_k_m.gguf")
    )
    ROLLBACK_GENERAL_MODEL_PATH: str = _QWEN_ROLLBACK_PATH
    GENERAL_MODEL_PATH: str = os.environ.get(
        "GENERAL_MODEL_PATH",
        _QWEN_ROLLBACK_PATH
        if os.environ.get("MYGPT_GENERAL_MODEL_ROLLBACK", "").strip().lower() in ("qwen", "qwen2.5", "1", "true")
        else (_GEMMA4_GENERAL_PATH if os.path.exists(_GEMMA4_GENERAL_PATH) else _QWEN_ROLLBACK_PATH)
    )
    CODING_MODEL_PATH: str = os.environ.get(
        "CODING_MODEL_PATH",
        os.path.join(MODELS_DIR, "local_llm", "coding", "qwen2.5-coder-3b-instruct-q4_k_m.gguf")
    )
    VISION_MODEL_PATH: str = os.environ.get(
        "VISION_MODEL_PATH",
        os.path.join(MODELS_DIR, "vision", "Qwen2-VL-2B-Instruct-Q4_K_M.gguf")
    )
    VISION_MMPROJ_PATH: str = os.environ.get(
        "VISION_MMPROJ_PATH",
        os.path.join(MODELS_DIR, "vision", "mmproj-Qwen2-VL-2B-Instruct-f16.gguf")
    )

    # CORS Configurations
    ALLOWED_ORIGINS: list = ["*"]

    # Dedicated PHP Integration API (v1) Security & Persistent Job Storage
    MYGPT_API_KEY: str = os.environ.get("MYGPT_API_KEY", "mygpt-dev-tender-key-change-in-prod")
    TENDER_JOB_DIR: str = os.environ.get("MYGPT_TENDER_JOB_DIR", os.path.join(DATA_DIR, "tender_jobs"))
    TENDER_JOB_TTL_SECONDS: int = int(os.environ.get("MYGPT_TENDER_JOB_TTL_SECONDS", "86400"))
    TENDER_MAX_UPLOAD_MB: int = int(os.environ.get("MYGPT_TENDER_MAX_UPLOAD_MB", "200"))


settings = Settings()
