"""Enterprise Audit Logger for tracking Company AI queries, access decisions, and security events.
"""

import os
import json
import uuid
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from loguru import logger

from backend.app.core.config import settings
from backend.app.schemas.security import AuditRecord


class AuditLogger:
    """Thread-safe Audit Logger maintaining local security compliance traces."""

    def __init__(self):
        self.audit_log_path = os.path.join(settings.DATA_DIR, "audit_log.json")
        self._ensure_file()

    def _ensure_file(self) -> None:
        """Initializes the audit log storage file if absent."""
        if not os.path.exists(self.audit_log_path):
            try:
                os.makedirs(os.path.dirname(self.audit_log_path), exist_ok=True)
                with open(self.audit_log_path, "w", encoding="utf-8") as f:
                    json.dump([], f)
            except Exception as e:
                logger.error(f"Failed to initialize audit log file: {e}")

    def _read_records(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.audit_log_path):
            return []
        try:
            with open(self.audit_log_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read audit log: {e}")
            return []

    def _write_records(self, records: List[Dict[str, Any]]) -> None:
        try:
            with open(self.audit_log_path, "w", encoding="utf-8") as f:
                json.dump(records[-500:], f, indent=2)  # retain last 500 records
        except Exception as e:
            logger.error(f"Failed to persist audit log: {e}")

    def log_event(
        self,
        user_id: str,
        user_role: str,
        department: str,
        requested_resource: str,
        operation: str,
        access_allowed: bool,
        details: Optional[Dict[str, Any]] = None
    ) -> AuditRecord:
        """Records an audit event for security and compliance monitoring."""
        record = AuditRecord(
            audit_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            user_id=user_id or "anonymous",
            user_role=str(user_role),
            department=str(department),
            requested_resource=requested_resource,
            operation=operation,
            access_allowed=access_allowed,
            details=details or {}
        )

        status_str = "ALLOWED" if access_allowed else "DENIED"
        logger.info(
            f"[AUDIT] {status_str} | User={record.user_id} ({record.user_role}) | "
            f"Dept={record.department} | Op={record.operation} | Resource={record.requested_resource}"
        )

        records = self._read_records()
        records.append(record.model_dump())
        self._write_records(records)
        return record

    def get_recent_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves the most recent audit records."""
        records = self._read_records()
        return records[-limit:]

    def clear_logs(self) -> None:
        """Clears audit logs (for testing resets)."""
        self._write_records([])


# Global singleton instance
audit_logger = AuditLogger()
