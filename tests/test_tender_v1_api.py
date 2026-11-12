"""Tests for dedicated asynchronous PHP integration API (/api/v1/tender/*)."""

import io
import os
import time
import fitz
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.services.tender.tender_job_store import tender_job_store


def _make_sample_tender_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    lines = [
        "STATE TELECOM INFRASTRUCTURE BOARD",
        "NOTICE INVITING e-TENDER",
        "Tender ID: STIB/NET/2026/101",
        "Name of Work: Supply and Maintenance of Campus Wi-Fi Network",
        "State: Karnataka",
        "Tender Portal URL: https://eproc.karnataka.gov.in",
        "Estimated Tender Value: Rs. 50,00,000",
        "Earnest Money Deposit: Rs. 1,00,000",
        "Bid Submission Start: 10-11-2026 at 10 AM",
        "Bid Submission End: 25-11-2026 at 5 PM",
        "Technical Bid Opening Date: 27-11-2026 at 11 AM",
    ]
    y = 72
    for ln in lines:
        page.insert_text((72, y), ln, fontsize=11)
        y += 18
    return doc.tobytes()


def test_v1_auth_and_validation():
    client = TestClient(app)
    pdf_bytes = _make_sample_tender_pdf()

    # Missing / invalid API key -> 401
    r_no_key = client.post(
        "/api/v1/tender/extract",
        files={"file": ("tender.pdf", pdf_bytes, "application/pdf")},
    )
    assert r_no_key.status_code == 401

    r_bad_key = client.post(
        "/api/v1/tender/extract",
        headers={"X-API-Key": "wrong-key"},
        files={"file": ("tender.pdf", pdf_bytes, "application/pdf")},
    )
    assert r_bad_key.status_code == 401

    # Unsupported file -> 415
    r_bad_ext = client.post(
        "/api/v1/tender/extract",
        headers={"X-API-Key": settings.MYGPT_API_KEY},
        files={"file": ("malware.exe", b"MZ", "application/octet-stream")},
    )
    assert r_bad_ext.status_code == 415

    # Empty file -> 400
    r_empty = client.post(
        "/api/v1/tender/extract",
        headers={"X-API-Key": settings.MYGPT_API_KEY},
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert r_empty.status_code == 400


def test_v1_async_lifecycle_ownership_and_idempotency():
    client = TestClient(app)
    pdf_bytes = _make_sample_tender_pdf()
    headers_a = {"X-API-Key": settings.MYGPT_API_KEY, "X-Client-Id": "user_a"}
    headers_b = {"X-API-Key": settings.MYGPT_API_KEY, "X-Client-Id": "user_b"}

    # Start async job with use_llm=false for fast deterministic E2E test
    req_id = f"test-req-{int(time.time() * 1000)}"
    r_start = client.post(
        "/api/v1/tender/extract",
        headers=headers_a,
        data={"request_id": req_id, "use_llm": "false"},
        files={"file": ("sample_tender.pdf", pdf_bytes, "application/pdf")},
    )
    assert r_start.status_code == 202
    start_data = r_start.json()
    assert start_data["status"] == "PROCESSING"
    job_id = start_data["job_id"]
    assert job_id

    # Idempotency check with same request_id + owner
    r_dup = client.post(
        "/api/v1/tender/extract",
        headers=headers_a,
        data={"request_id": req_id, "use_llm": "false"},
        files={"file": ("sample_tender.pdf", pdf_bytes, "application/pdf")},
    )
    assert r_dup.status_code == 202
    assert r_dup.json()["job_id"] == job_id

    # Different client cannot read status or result -> 403
    r_forbid = client.get(f"/api/v1/tender/status/{job_id}", headers=headers_b)
    assert r_forbid.status_code == 403

    # Poll until completed
    final_status = None
    for _ in range(40):
        st = client.get(f"/api/v1/tender/status/{job_id}", headers=headers_a)
        assert st.status_code == 200
        body = st.json()
        if body["status"] in ("COMPLETED", "FAILED"):
            final_status = body
            break
        time.sleep(0.25)

    assert final_status is not None
    assert final_status["status"] == "COMPLETED"
    assert final_status["progress"] == 100

    # Retrieve result
    r_res = client.get(f"/api/v1/tender/result/{job_id}", headers=headers_a)
    assert r_res.status_code == 200
    res_json = r_res.json()
    assert res_json["status"] == "COMPLETED"
    te = res_json["tender_extraction"]
    assert te["basic_information"]["tender_id"]["value"] == "STIB/NET/2026/101"
    assert "1,00,000" in te["financial_information"]["bid_emd_value"]["value"]

    # Verify temporary upload file was cleaned up
    assert not os.path.exists(os.path.join(tender_job_store.uploads_dir, job_id))

    # Unknown job -> 404
    r_404 = client.get("/api/v1/tender/status/nonexistent-job-id", headers=headers_a)
    assert r_404.status_code == 404

