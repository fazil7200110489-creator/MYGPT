"""Logging configuration module for MyGPT Studio.

Sets up Loguru handles writing API, Training, and System logs to the logs/ directory.
"""

import os
import sys
from loguru import logger
from backend.app.core.config import settings


def configure_logging() -> None:
    """Configures the global Loguru logger formatting and file targets."""
    # Ensure logs directory exists
    os.makedirs(settings.LOGS_DIR, exist_ok=True)

    # Clean existing handlers
    logger.remove()

    # Console output handler
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:7}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )

    # General app log file
    logger.add(
        os.path.join(settings.LOGS_DIR, "app.log"),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:7} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="10 MB",
        retention="7 days",
        encoding="utf-8"
    )

    # Separate training specifics log file
    logger.add(
        os.path.join(settings.LOGS_DIR, "training.log"),
        format="{time:YYYY-MM-DD HH:mm:ss} | {message}",
        level="INFO",
        filter=lambda record: "training" in record["extra"] or "train" in record["message"].lower(),
        rotation="20 MB",
        retention="14 days",
        encoding="utf-8"
    )

    logger.info("Application logging successfully initialized.")
