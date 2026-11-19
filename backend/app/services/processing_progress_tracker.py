"""
Real-Time AI Processing Status Tracker for MYGPT.
Manages stage-by-stage execution events, SSE streaming, and status snapshots
for long-running tender upload, extraction, and AI reasoning pipelines.
"""

import asyncio
import time
import json
import threading
from typing import Dict, Any, List, Optional, Set, AsyncGenerator
from loguru import logger
from fastapi import Request


class ProcessingProgressTracker:
    """Thread-safe event tracker and Server-Sent Events (SSE) broadcaster."""

    def __init__(self, ttl_seconds: int = 1800) -> None:
        self._lock = threading.Lock()
        self._tasks: Dict[str, Dict[str, Any]] = {}
        # Mapping from task_id -> set of asyncio.Queue instances
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        # Mapping from session_id -> task_id for session-level lookup
        self._session_to_task: Dict[str, str] = {}
        self._ttl_seconds = ttl_seconds

    def _cleanup_expired_tasks_locked(self) -> None:
        now = time.time()
        expired = [
            tid for tid, data in self._tasks.items()
            if now - data.get("updated_at", now) > self._ttl_seconds
        ]
        for tid in expired:
            self._tasks.pop(tid, None)
            self._subscribers.pop(tid, None)

    def start_task(
        self,
        task_id: str,
        task_type: str = "tender_analysis",
        session_id: Optional[str] = None,
        document_id: Optional[str] = None,
        initial_stage: str = "queued",
        initial_message: str = "Initializing request...",
    ) -> Dict[str, Any]:
        """Initializes tracking for a new processing task."""
        now = time.time()
        with self._lock:
            self._cleanup_expired_tasks_locked()
            task_data = {
                "task_id": task_id,
                "session_id": session_id,
                "document_id": document_id,
                "task_type": task_type,
                "status": "running",
                "current_stage": initial_stage,
                "current_message": initial_message,
                "stages": [
                    {
                        "stage": initial_stage,
                        "status": "running",
                        "message": initial_message,
                        "started_at": now,
                        "completed_at": None,
                    }
                ],
                "error": None,
                "created_at": now,
                "updated_at": now,
            }
            self._tasks[task_id] = task_data
            if session_id:
                self._session_to_task[session_id] = task_id

        self._broadcast(task_id, {
            "type": "stage_update",
            "task_id": task_id,
            "document_id": document_id,
            "stage": initial_stage,
            "status": "running",
            "message": initial_message,
            "timestamp": now,
        })
        return task_data

    def update_stage(
        self,
        task_id: Optional[str],
        stage: str,
        message: str,
        status: str = "running",
        document_id: Optional[str] = None,
        session_id: Optional[str] = None,
        task_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Updates or marks progress on a specific stage.
        
        Args:
            task_id: Task identifier. If None, silently no-ops.
            stage: Identifier key (e.g. 'extracting_pdf', 'analysing_eligibility').
            message: Human-readable activity message.
            status: 'pending' | 'running' | 'completed' | 'failed'.
            document_id: Optional attached document ID.
            session_id: Optional session identifier.
            task_type: Optional task type hint.
            details: Optional extra contextual details.
        """
        if not task_id:
            # If session_id is available, try mapping from session
            if session_id and session_id in self._session_to_task:
                task_id = self._session_to_task[session_id]
            else:
                return

        now = time.time()
        with self._lock:
            if task_id not in self._tasks:
                self._tasks[task_id] = {
                    "task_id": task_id,
                    "session_id": session_id,
                    "document_id": document_id,
                    "task_type": task_type or "general",
                    "status": "running",
                    "current_stage": stage,
                    "current_message": message,
                    "stages": [],
                    "error": None,
                    "created_at": now,
                    "updated_at": now,
                }
                if session_id:
                    self._session_to_task[session_id] = task_id

            task = self._tasks[task_id]
            task["updated_at"] = now
            if document_id and not task.get("document_id"):
                task["document_id"] = document_id

            # If moving to a new stage and previous stage was 'running', mark previous as completed
            if task["current_stage"] != stage:
                for s in task["stages"]:
                    if s["stage"] == task["current_stage"] and s["status"] == "running":
                        s["status"] = "completed"
                        s["completed_at"] = now

            task["current_stage"] = stage
            task["current_message"] = message

            # Find or append stage record
            existing_stage = next((s for s in task["stages"] if s["stage"] == stage), None)
            if existing_stage:
                existing_stage["status"] = status
                existing_stage["message"] = message
                if status == "completed":
                    existing_stage["completed_at"] = now
                if details:
                    existing_stage["details"] = details
            else:
                stage_rec = {
                    "stage": stage,
                    "status": status,
                    "message": message,
                    "started_at": now,
                    "completed_at": now if status == "completed" else None,
                }
                if details:
                    stage_rec["details"] = details
                task["stages"].append(stage_rec)

        payload = {
            "type": "stage_update",
            "task_id": task_id,
            "document_id": task.get("document_id"),
            "stage": stage,
            "status": status,
            "message": message,
            "timestamp": now,
            "details": details or {},
        }
        self._broadcast(task_id, payload)

    def complete_task(
        self,
        task_id: Optional[str],
        message: str = "Tender analysis completed successfully",
        document_id: Optional[str] = None,
        final_stage: Optional[str] = None,
    ) -> None:
        """Marks the entire task as successfully completed."""
        if not task_id:
            return

        now = time.time()
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            task["status"] = "completed"
            task["updated_at"] = now
            task["current_message"] = message
            if final_stage:
                task["current_stage"] = final_stage
            # Mark all active running stages as completed
            for s in task["stages"]:
                if s["status"] == "running":
                    s["status"] = "completed"
                    s["completed_at"] = now

        payload = {
            "type": "task_completed",
            "task_id": task_id,
            "document_id": task.get("document_id") or document_id,
            "stage": task.get("current_stage") or "completed",
            "final_stage": final_stage or task.get("current_stage"),
            "status": "completed",
            "message": message,
            "timestamp": now,
        }
        self._broadcast(task_id, payload)

    def fail_task(
        self,
        task_id: Optional[str],
        stage: str,
        error_message: str,
        document_id: Optional[str] = None,
    ) -> None:
        """Marks task and active stage as failed."""
        if not task_id:
            return

        now = time.time()
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                task = {
                    "task_id": task_id,
                    "status": "failed",
                    "current_stage": stage,
                    "current_message": error_message,
                    "stages": [],
                    "error": error_message,
                    "created_at": now,
                    "updated_at": now,
                }
                self._tasks[task_id] = task

            task["status"] = "failed"
            task["error"] = error_message
            task["current_stage"] = stage
            task["current_message"] = error_message
            task["updated_at"] = now

            existing_stage = next((s for s in task["stages"] if s["stage"] == stage), None)
            if existing_stage:
                existing_stage["status"] = "failed"
                existing_stage["message"] = error_message
                existing_stage["completed_at"] = now
            else:
                task["stages"].append({
                    "stage": stage,
                    "status": "failed",
                    "message": error_message,
                    "started_at": now,
                    "completed_at": now,
                })

        payload = {
            "type": "task_failed",
            "task_id": task_id,
            "document_id": task.get("document_id") or document_id,
            "stage": stage,
            "status": "failed",
            "message": error_message,
            "error": error_message,
            "timestamp": now,
        }
        self._broadcast(task_id, payload)

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Returns snapshot of current task progress and stage history."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            # Return deep copy of dictionary
            return json.loads(json.dumps(task))

    def _broadcast(self, task_id: str, event_data: Dict[str, Any]) -> None:
        """Pushes event data into all active asyncio subscribers for this task."""
        with self._lock:
            subscribers = list(self._subscribers.get(task_id, []))

        for q in subscribers:
            try:
                q.put_nowait(event_data)
            except Exception as e:
                logger.debug(f"[PROGRESS] Subscriber queue put failed: {e}")

    async def subscribe(
        self,
        task_id: str,
        request: Optional[Request] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Async generator yielding progress events for SSE streaming."""
        queue: asyncio.Queue = asyncio.Queue()

        with self._lock:
            if task_id not in self._subscribers:
                self._subscribers[task_id] = set()
            self._subscribers[task_id].add(queue)

            # Replay existing snapshot if task exists
            task_snapshot = self._tasks.get(task_id)

        try:
            if task_snapshot:
                # Send snapshot of current state
                yield {
                    "type": "snapshot",
                    "task_id": task_id,
                    "status": task_snapshot["status"],
                    "current_stage": task_snapshot["current_stage"],
                    "current_message": task_snapshot["current_message"],
                    "stages": task_snapshot["stages"],
                    "error": task_snapshot["error"],
                    "document_id": task_snapshot.get("document_id"),
                    "task_type": task_snapshot.get("task_type"),
                    "timestamp": time.time(),
                }
                # If task already completed or failed, terminate cleanly
                if task_snapshot["status"] in ("completed", "failed"):
                    return

            while True:
                if request and await request.is_disconnected():
                    break

                try:
                    event = await asyncio.wait_for(queue.get(), timeout=12.0)
                    yield event
                    if event.get("type") in ("task_completed", "task_failed"):
                        break
                except asyncio.TimeoutError:
                    # Send periodic keepalive comment
                    yield {"type": "ping", "timestamp": time.time()}

        finally:
            with self._lock:
                if task_id in self._subscribers:
                    self._subscribers[task_id].discard(queue)
                    if not self._subscribers[task_id]:
                        self._subscribers.pop(task_id, None)


# Global singleton instance
processing_progress_tracker = ProcessingProgressTracker()
