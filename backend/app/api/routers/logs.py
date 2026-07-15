"""API Router for reading trailing console execution logs.
"""

import os
from fastapi import APIRouter
from typing import Dict, Any, List
from backend.app.core.config import settings

router = APIRouter(tags=["Logs"])


@router.get("/logs")
async def get_console_logs(lines: int = 50) -> Dict[str, List[str]]:
    """Retrieves the trailing lines of the main application log file."""
    log_filepath = os.path.join(settings.LOGS_DIR, "app.log")
    
    if not os.path.exists(log_filepath):
        return {"logs": ["Log file has not been initialized yet."]}

    try:
        with open(log_filepath, "r", encoding="utf-8") as f:
            log_lines = f.readlines()
        
        # Take the trailing lines
        trailing_lines = [line.strip() for line in log_lines[-lines:]]
        return {"logs": trailing_lines}
    except Exception as e:
        return {"logs": [f"Error reading log file: {str(e)}"]}
