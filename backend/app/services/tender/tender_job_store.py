"""Persistent SQLite-backed asynchronous job store and worker pool for /api/v1/tender/*."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import shutil
import sqlite3
import threading
import time
import uuid
from typing import Any, Dict, Optional

from loguru import logger

from backend.app.core.config import settings


class TenderJobStore:
    """Thread-safe SQLite job store + bounded worker pool for async tender extraction."""

    def __init__(self, job_dir: Optional[str] = None, max_workers: int = 2) -> None:
        self.job_dir = job_dir or settings.TENDER_JOB_DIR
        self.uploads_dir = os.path.join(self.job_dir, "uploads")
        self.db_path = os.path.join(self.job_dir, "jobs.db")
        os.makedirs(self.uploads_dir, exist_ok=True)
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="tender-v1")
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS tender_jobs (
                        job_id TEXT PRIMARY KEY,
                        request_id TEXT,
                        owner_hash TEXT NOT NULL,
                        filename TEXT NOT NULL,
                        file_size INTEGER NOT NULL,
                        status TEXT NOT NULL,
                        progress INTEGER NOT NULL DEFAULT 0,
                        stage TEXT NOT NULL DEFAULT 'queued',
                        error_message TEXT,
                        result_json TEXT,
                        temp_path TEXT,
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL,
                        expires_at REAL NOT NULL
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_tender_jobs_req ON tender_jobs(owner_hash, request_id)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_tender_jobs_exp ON tender_jobs(expires_at)"
                )
                conn.commit()
            finally:
                conn.close()

    @staticmethod
    def hash_owner(api_key: str, client_id: Optional[str] = None) -> str:
        raw = f"{api_key}:{client_id or ''}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def purge_expired(self) -> int:
        now = time.time()
        removed = 0
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT job_id, temp_path FROM tender_jobs WHERE expires_at < ?",
                    (now,),
                ).fetchall()
                for row in rows:
                    self._cleanup_temp_path(row["temp_path"], row["job_id"])
                    removed += 1
                if rows:
                    conn.execute("DELETE FROM tender_jobs WHERE expires_at < ?", (now,))
                    conn.commit()
            finally:
                conn.close()
        return removed

    def _cleanup_temp_path(self, temp_path: Optional[str], job_id: str) -> None:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        job_upload_dir = os.path.join(self.uploads_dir, job_id)
        if os.path.isdir(job_upload_dir):
            try:
                shutil.rmtree(job_upload_dir, ignore_errors=True)
            except OSError:
                pass

    def find_by_request_id(self, owner_hash: str, request_id: str) -> Optional[Dict[str, Any]]:
        if not request_id:
            return None
        now = time.time()
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    """
                    SELECT * FROM tender_jobs
                    WHERE owner_hash = ? AND request_id = ? AND expires_at >= ?
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (owner_hash, request_id, now),
                ).fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

    def create_job(
        self,
        owner_hash: str,
        filename: str,
        file_bytes: bytes,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        self.purge_expired()
        if request_id:
            existing = self.find_by_request_id(owner_hash, request_id)
            if existing:
                return existing

        job_id = str(uuid.uuid4())
        job_upload_dir = os.path.join(self.uploads_dir, job_id)
        os.makedirs(job_upload_dir, exist_ok=True)
        safe_name = os.path.basename(filename or "tender.pdf").replace("..", "_")
        temp_path = os.path.join(job_upload_dir, safe_name)
        with open(temp_path, "wb") as f:
            f.write(file_bytes)

        now = time.time()
        expires_at = now + settings.TENDER_JOB_TTL_SECONDS

        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO tender_jobs (
                        job_id, request_id, owner_hash, filename, file_size,
                        status, progress, stage, error_message, result_json,
                        temp_path, created_at, updated_at, expires_at
                    ) VALUES (?, ?, ?, ?, ?, 'PROCESSING', 5, 'queued', NULL, NULL, ?, ?, ?, ?)
                    """,
                    (
                        job_id,
                        request_id,
                        owner_hash,
                        safe_name,
                        len(file_bytes),
                        temp_path,
                        now,
                        now,
                        expires_at,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

        return self.get_job(job_id)  # type: ignore[return-value]

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        now = time.time()
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM tender_jobs WHERE job_id = ? AND expires_at >= ?",
                    (job_id, now),
                ).fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

    def update_progress(self, job_id: str, progress: int, stage: str) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "UPDATE tender_jobs SET progress = ?, stage = ?, updated_at = ? WHERE job_id = ?",
                    (progress, stage, time.time(), job_id),
                )
                conn.commit()
            finally:
                conn.close()

    def mark_completed(self, job_id: str, result_dict: Dict[str, Any]) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    UPDATE tender_jobs
                    SET status = 'COMPLETED', progress = 100, stage = 'completed',
                        result_json = ?, error_message = NULL, updated_at = ?
                    WHERE job_id = ?
                    """,
                    (json.dumps(result_dict, ensure_ascii=False), time.time(), job_id),
                )
                conn.commit()
            finally:
                conn.close()

    def mark_failed(self, job_id: str, error_message: str) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    UPDATE tender_jobs
                    SET status = 'FAILED', stage = 'failed',
                        error_message = ?, updated_at = ?
                    WHERE job_id = ?
                    """,
                    (error_message[:1000], time.time(), job_id),
                )
                conn.commit()
            finally:
                conn.close()

    def submit_extraction(
        self,
        job_id: str,
        nas_path: Optional[str] = None,
        use_llm: bool = True,
    ) -> None:
        self._executor.submit(self._run_extraction_worker, job_id, nas_path, use_llm)

    def _run_extraction_worker(
        self,
        job_id: str,
        nas_path: Optional[str],
        use_llm: bool,
    ) -> None:
        job = self.get_job(job_id)
        if not job:
            return

        temp_path = job.get("temp_path")
        filename = job.get("filename") or "tender.pdf"
        try:
            self.update_progress(job_id, 20, "parsing_and_ocr")
            from backend.app.services.document_parser import document_parser
            from backend.app.services.tender.tender_extractor import tender_extractor

            parsed = document_parser.parse(temp_path)
            if not parsed or parsed.get("error"):
                err = (parsed or {}).get("error") or "Failed to parse tender document."
                self.mark_failed(job_id, err)
                return

            self.update_progress(job_id, 55, "extracting_tender_fields")
            doc_meta = {
                "doc_id": job_id,
                "filename": filename,
                "file_path": temp_path,
                "file_type": parsed.get("file_type") or os.path.splitext(filename)[1].lower(),
                "document_type": "TENDER",
                "extracted_text": parsed.get("text", ""),
                "total_pages": parsed.get("total_pages", len(parsed.get("pages", [])) or 1),
                "pages": parsed.get("pages", []),
                "sheets": parsed.get("sheets", []),
                "ocr_pages": parsed.get("ocr_pages", []),
                "unreadable_pages": parsed.get("unreadable_pages", []),
                "ocr_engine": parsed.get("ocr_engine"),
                "nas_path": nas_path,
            }

            result = tender_extractor.extract_from_documents(
                [doc_meta],
                nas_path=nas_path,
                use_llm=use_llm,
            )
            self.mark_completed(job_id, result.model_dump())
            logger.info(f"[TENDER_V1] Job {job_id} completed successfully for '{filename}'.")
        except Exception as exc:
            logger.error(f"[TENDER_V1] Job {job_id} failed: {exc}")
            self.mark_failed(job_id, str(exc))
        finally:
            self._cleanup_temp_path(temp_path, job_id)


tender_job_store = TenderJobStore()
