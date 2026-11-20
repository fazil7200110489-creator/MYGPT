"""Tender Evaluation Concurrency Guard for MYGPT.

Provides cross-thread and cross-process mutual exclusion to guarantee:
1. Only one resource-intensive tender evaluation executes at any given time.
2. Concurrent requests receive an explicit, immediate busy signal (HTTP 429 / clear message).
3. Guaranteed lock release upon completion, error, exception, or cancellation.
4. Full compatibility across multi-threaded Uvicorn and multiple worker processes via FileLock.
"""

import os
import threading
from contextlib import contextmanager
from typing import Generator, Optional
from filelock import FileLock, Timeout
from loguru import logger

_LOCK_DIR = "data"
_LOCK_FILE = os.path.join(_LOCK_DIR, "tender_evaluation.lock")


class TenderEvaluationBusyError(Exception):
    """Raised when an evaluation request cannot proceed because another evaluation is active."""

    def __init__(
        self,
        message: str = (
            "A tender evaluation is currently in progress. To protect system resources, "
            "only one evaluation can run at a time. Please wait for the current analysis to complete."
        ),
    ) -> None:
        super().__init__(message)
        self.message = message


class TenderEvaluationLock:
    """Combines an in-process thread lock with a cross-process file lock."""

    def __init__(self, lock_file: str = _LOCK_FILE) -> None:
        os.makedirs(os.path.dirname(lock_file), exist_ok=True)
        self.lock_file = lock_file
        self._thread_lock = threading.Lock()
        self._file_lock = FileLock(lock_file, timeout=0)
        self._is_evaluating = False

    @property
    def is_locked(self) -> bool:
        return self._is_evaluating or self._file_lock.is_locked

    @contextmanager
    def acquire(self, timeout: float = 0.0) -> Generator[None, None, None]:
        """Acquires both thread and file locks.

        Raises:
            TenderEvaluationBusyError: If another evaluation holds the lock.
        """
        # 1. Thread-level check
        if timeout > 0:
            acquired_thread = self._thread_lock.acquire(blocking=True, timeout=timeout)
        else:
            acquired_thread = self._thread_lock.acquire(blocking=False)
        if not acquired_thread:
            logger.warning("[EVAL_LOCK] Evaluation rejected: thread lock busy.")
            raise TenderEvaluationBusyError()

        try:
            # 2. Process-level check via FileLock
            try:
                self._file_lock.acquire(timeout=timeout)
            except Timeout:
                logger.warning("[EVAL_LOCK] Evaluation rejected: cross-process file lock busy.")
                raise TenderEvaluationBusyError()

            self._is_evaluating = True
            logger.info(f"[EVAL_LOCK] Evaluation lock acquired (pid={os.getpid()}).")
            try:
                yield
            finally:
                self._is_evaluating = False
                try:
                    self._file_lock.release()
                except Exception as fe:
                    logger.warning(f"[EVAL_LOCK] Error releasing file lock: {fe}")
                logger.info(f"[EVAL_LOCK] Evaluation lock released (pid={os.getpid()}).")
        finally:
            self._thread_lock.release()


# Global evaluation lock singleton
tender_evaluation_lock = TenderEvaluationLock()

