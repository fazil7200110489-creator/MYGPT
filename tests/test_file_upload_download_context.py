"""Tests for Company AI File Upload, Download, Active Document Multi-turn Context, and RBAC.
"""

import io
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_upload_invoice_and_ask_questions():
    session_id = "test_upload_invoice_sess"
    client.post("/api/company/chat/reset", params={"session_id": session_id})

    invoice_content = b"""
    INVOICE #INV-2026-9901
    Vendor: Acme Global Services
    Date: 2026-08-15
    Due Date: 2026-09-15
    Bill To: MYGPT Technologies

    Line Items:
    1. Cloud Hosting Infrastructure - $1,500.00
    2. SSL Enterprise Certificate - $300.00
    3. Dedicated Support Tier - $450.00

    Subtotal: $2,250.00
    Tax (10%): $225.00
    Total Amount: $2,475.00
    """

    # 1. Upload Invoice
    file_tuple = ("invoice_9901.txt", io.BytesIO(invoice_content), "text/plain")
    upload_res = client.post(
        "/api/company/upload",
        files={"file": file_tuple},
        data={
            "session_id": session_id,
            "user_role": "EMPLOYEE",
            "user_id": "test_user"
        }
    )
    assert upload_res.status_code == 200, upload_res.text
    up_data = upload_res.json()
    assert up_data["success"] is True
    assert up_data["document_type"] == "INVOICE"
    assert up_data["structured_data"]["invoice_number"] == "2026-9901" or "INV-2026-9901" in up_data["structured_data"]["invoice_number"]
    assert up_data["structured_data"]["total_amount"] == 2475.0

    # 2. Ask question referring to active document
    chat_res1 = client.post(
        "/api/company/chat",
        json={
            "message": "How much is the total amount on this invoice?",
            "session_id": session_id,
            "user_role": "EMPLOYEE",
            "user_id": "test_user"
        }
    )
    assert chat_res1.status_code == 200
    c_data1 = chat_res1.json()
    assert c_data1["department"] == "FINANCE"
    assert "2,475" in c_data1["answer"] or "2475" in c_data1["answer"]
    assert "**svg**" not in c_data1["answer"]

    # 3. Follow-up summary of this document
    chat_res2 = client.post(
        "/api/company/chat",
        json={
            "message": "give me a summary of this report",
            "session_id": session_id,
            "user_role": "EMPLOYEE",
            "user_id": "test_user"
        }
    )
    assert chat_res2.status_code == 200
    c_data2 = chat_res2.json()
    assert c_data2["department"] == "FINANCE"
    assert "Acme Global Services" in c_data2["answer"] or "2026-9901" in c_data2["answer"] or "2,475" in c_data2["answer"]

    # 4. Request Excel export of the invoice
    chat_res3 = client.post(
        "/api/company/chat",
        json={
            "message": "Export this invoice to Excel",
            "session_id": session_id,
            "user_role": "FINANCE_MANAGER",
            "user_id": "fin_manager"
        }
    )
    assert chat_res3.status_code == 200
    c_data3 = chat_res3.json()
    assert c_data3["files"] and len(c_data3["files"]) > 0
    file_id = c_data3["files"][0].get("file_id")
    assert file_id is not None

    # 5. Download the file
    down_res = client.get(
        f"/api/company/files/{file_id}/download",
        params={"user_role": "FINANCE_MANAGER", "user_id": "fin_manager"}
    )
    assert down_res.status_code == 200
    assert len(down_res.content) > 100


def test_rbac_download_restriction():
    session_id = "test_rbac_download_sess"
    client.post("/api/company/chat/reset", params={"session_id": session_id})

    # Generate restricted expense report as FINANCE_MANAGER
    chat_res = client.post(
        "/api/company/chat",
        json={
            "message": "Generate the monthly travel expense report for July.",
            "session_id": session_id,
            "user_role": "FINANCE_MANAGER",
            "user_id": "fin_mgr"
        }
    )
    assert chat_res.status_code == 200
    data = chat_res.json()
    assert data["files"] and len(data["files"]) > 0
    file_id = data["files"][0]["file_id"]

    # Attempt download as EMPLOYEE -> Expect 403 Forbidden
    down_employee = client.get(
        f"/api/company/files/{file_id}/download",
        params={"user_role": "EMPLOYEE", "user_id": "emp_01"}
    )
    assert down_employee.status_code == 403

    # Attempt download as FINANCE_MANAGER -> Expect 200 OK
    down_manager = client.get(
        f"/api/company/files/{file_id}/download",
        params={"user_role": "FINANCE_MANAGER", "user_id": "fin_mgr"}
    )
    assert down_manager.status_code == 200
