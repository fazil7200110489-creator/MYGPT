"""Dedicated Asynchronous Integration API (/api/v1/tender/*) for PHP Bid Portal."""

import hmac
import json
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile, status
from loguru import logger

from backend.app.core.config import settings
from backend.app.services.tender.tender_job_store import tender_job_store

router = APIRouter(prefix="/v1/tender", tags=["Tender Integration v1"])

ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv",
    ".txt", ".rtf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp",
}


def verify_api_key(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id"),
) -> str:
    """Validates API key using constant-time comparison and returns owner hash."""
    expected = settings.MYGPT_API_KEY
    if not x_api_key or not hmac.compare_digest(x_api_key.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing MYGPT API key.",
        )
    return tender_job_store.hash_owner(x_api_key, x_client_id)


@router.post("/extract", status_code=status.HTTP_202_ACCEPTED)
async def start_tender_extraction(
    file: UploadFile = File(...),
    request_id: Optional[str] = Form(default=None),
    nas_path: Optional[str] = Form(default=None),
    use_llm: bool = Form(default=True),
    owner_hash: str = Depends(verify_api_key),
) -> Dict[str, Any]:
    """Validates uploaded tender document, queues async extraction, and returns job_id immediately."""
    filename = os.path.basename(file.filename or "")
    if not filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing uploaded filename.")

    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file format '{ext}'.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    max_bytes = settings.TENDER_MAX_UPLOAD_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Uploaded file exceeds maximum limit of {settings.TENDER_MAX_UPLOAD_MB} MB.",
        )

    existing = tender_job_store.find_by_request_id(owner_hash, request_id) if request_id else None
    if existing:
        return {
            "job_id": existing["job_id"],
            "status": existing["status"],
            "message": "Tender extraction job already exists for request_id",
        }

    job = tender_job_store.create_job(
        owner_hash=owner_hash,
        filename=filename,
        file_bytes=content,
        request_id=request_id,
    )
    tender_job_store.submit_extraction(job["job_id"], nas_path=nas_path, use_llm=use_llm)
    logger.info(f"[TENDER_V1] Started job {job['job_id']} for '{filename}' ({len(content)} bytes)")
    return {
        "job_id": job["job_id"],
        "status": "PROCESSING",
        "message": "Tender extraction started",
    }


@router.get("/status/{job_id}")
async def get_tender_extraction_status(
    job_id: str,
    owner_hash: str = Depends(verify_api_key),
) -> Dict[str, Any]:
    """Returns current asynchronous job status and measurable stage progress."""
    job = tender_job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extraction job not found or expired.")
    if not hmac.compare_digest(job["owner_hash"], owner_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this extraction job.")

    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "progress": job["progress"],
        "stage": job["stage"],
        "error": job.get("error_message"),
    }


@router.get("/result/{job_id}")
async def get_tender_extraction_result(
    job_id: str,
    owner_hash: str = Depends(verify_api_key),
) -> Dict[str, Any]:
    """Retrieves the completed TenderExtractionResult for a finished job."""
    job = tender_job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extraction job not found or expired.")
    if not hmac.compare_digest(job["owner_hash"], owner_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this extraction job.")

    if job["status"] == "PROCESSING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tender extraction is still processing.",
        )
    if job["status"] == "FAILED":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=job.get("error_message") or "Tender extraction failed.",
        )

    result_raw = job.get("result_json")
    if not result_raw:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Extraction result payload missing.",
        )

    return {
        "job_id": job["job_id"],
        "status": "COMPLETED",
        "tender_extraction": json.loads(result_raw),
    }

