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

    # CORS Configurations
    ALLOWED_ORIGINS: list = ["*"]


settings = Settings()
