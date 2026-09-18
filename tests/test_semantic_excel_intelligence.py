"""Automated test suite for Semantic Excel Intelligence, Multi-File Upload & Context,
and ChatGPT-style Persistent Chat History.
"""

import io
import pandas as pd
import pytest
from starlette.testclient import TestClient

from backend.app.main import app
from backend.app.services.conversation_context_manager import conversation_context_manager
from backend.app.services.company_ai_service import company_ai_service


@pytest.fixture
def client():
    return TestClient(app)


def test_semantic_excel_variations_and_group_max(client):
    """Tests semantic request understanding without fragile keyword-by-keyword if/else patches:
    - What's the largest payment?
    - Which payment is the biggest?
    - Show the maximum transaction.
    - Which payment mode has the largest transaction?
    - List every field in this spreadsheet.
    - Turn the transaction number field into Excel.
    - Export the complete topup history.
    - Convert that result into Excel.
    """
    rows = []
    for i in range(1, 100):
        mode = "QR" if i % 2 == 0 else "UPI"
        amt = 25000.0 if i == 1 else (15000.0 if i == 2 else 500.0)
        rows.append({
            "TRNSCTN_NMBR": f"TXN_{i:04d}",
            "Topup_Date": "2026-06-17",
            "Store_Code": f"STR_{100 + (i % 5)}",
            "Agent_name": f"Agent {i % 3}",
            "Transaction_Mode": mode,
            "Status": "Authorised",
            "Amount": amt,
            "Settled_Amount": amt
        })

    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    file_bytes = buf.getvalue()

    session_id = "test_semantic_excel_session_1"
    conversation_context_manager.clear_state(session_id)

    # 1. Upload workbook
    res_up = client.post(
        "/api/company/upload",
        files={"file": ("EBO TB Topup_export_20260617_160221.xlsx", file_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"session_id": session_id}
    )
    assert res_up.status_code == 200

    # 2. "What's the largest payment?" -> EXCEL_MAX
    r1 = client.post("/api/company/chat", json={
        "message": "What's the largest payment?",
        "session_id": session_id,
        "user_role": "EMPLOYEE"
    })
    assert r1.status_code == 200
    assert r1.json()["intent"] == "excel_max"
    assert "25,000.00" in r1.json()["answer"]

    # 3. "Which payment is the biggest?" -> EXCEL_MAX
    r2 = client.post("/api/company/chat", json={
        "message": "Which payment is the biggest?",
        "session_id": session_id,
        "user_role": "EMPLOYEE"
    })
    assert r2.status_code == 200
    assert r2.json()["intent"] == "excel_max"
    assert "25,000.00" in r2.json()["answer"]

    # 4. "Show the maximum transaction." -> EXCEL_MAX
    r3 = client.post("/api/company/chat", json={
        "message": "Show the maximum transaction.",
        "session_id": session_id,
        "user_role": "EMPLOYEE"
    })
    assert r3.status_code == 200
    assert r3.json()["intent"] == "excel_max"
    assert "25,000.00" in r3.json()["answer"]

    # 5. "Which payment mode has the largest transaction?" -> EXCEL_GROUP_MAX
    r4 = client.post("/api/company/chat", json={
        "message": "Which payment mode has the largest transaction?",
        "session_id": session_id,
        "user_role": "EMPLOYEE"
    })
    assert r4.status_code == 200
    assert r4.json()["intent"] == "excel_group_max"
    assert "UPI" in r4.json()["answer"] or "QR" in r4.json()["answer"]
    assert "25,000.00" in r4.json()["answer"]

    # 6. "List every field in this spreadsheet." -> EXCEL_COLUMNS (excel_column_list)
    r5 = client.post("/api/company/chat", json={
        "message": "List every field in this spreadsheet.",
        "session_id": session_id,
        "user_role": "EMPLOYEE"
    })
    assert r5.status_code == 200
    assert r5.json()["intent"] == "excel_column_list"
    assert "TRNSCTN_NMBR" in r5.json()["answer"]
    assert "Amount" in r5.json()["answer"]

    # 7. "Turn the transaction number field into Excel." -> EXCEL_COLUMN_EXPORT (resolved to TRNSCTN_NMBR)
    r6 = client.post("/api/company/chat", json={
        "message": "Turn the transaction number field into Excel.",
        "session_id": session_id,
        "user_role": "EMPLOYEE"
    })
    assert r6.status_code == 200
    assert r6.json()["intent"] == "excel_column_export"
    assert len(r6.json().get("files", [])) > 0

    # 8. "Export the complete topup history." -> EXCEL_FULL_EXPORT
    r7 = client.post("/api/company/chat", json={
        "message": "Export the complete topup history.",
        "session_id": session_id,
        "user_role": "EMPLOYEE"
    })
    assert r7.status_code == 200
    assert r7.json()["intent"] == "excel_full_export"
    assert len(r7.json().get("files", [])) > 0

    # 9. "Convert that result into Excel." -> EXCEL_EXPORT_RESULT
    # First ask a total calculation
    client.post("/api/company/chat", json={
        "message": "calculate total amount",
        "session_id": session_id,
        "user_role": "EMPLOYEE"
    })
    r8 = client.post("/api/company/chat", json={
        "message": "Convert that result into Excel.",
        "session_id": session_id,
        "user_role": "EMPLOYEE"
    })
    assert r8.status_code == 200
    assert r8.json()["intent"] == "excel_export_result"
    assert len(r8.json().get("files", [])) > 0


def test_multi_file_upload_comparison_and_chat_persistence(client):
    """Tests multi-file simultaneous upload (/upload-multiple),
    two-file reconciliation without re-uploading, and conversation persistence surviving refresh.
    """
    # Create File A (EBO)
    rows_a = [
        {"Unique_ID": "TXN_101", "Amount": 1000.0, "Status": "Authorised"},
        {"Unique_ID": "TXN_102", "Amount": 2000.0, "Status": "Authorised"},
        {"Unique_ID": "TXN_103", "Amount": 3000.0, "Status": "Authorised"},
    ]
    df_a = pd.DataFrame(rows_a)
    buf_a = io.BytesIO()
    df_a.to_excel(buf_a, index=False)

    # Create File B (UPI)
    rows_b = [
        {"Unique_ID": "TXN_101", "Amount": 1000.0, "Status": "Authorised"},
        {"Unique_ID": "TXN_102", "Amount": 2500.0, "Status": "Authorised"}, # Mismatch
        {"Unique_ID": "TXN_104", "Amount": 4000.0, "Status": "Authorised"}, # Missing in A
    ]
    df_b = pd.DataFrame(rows_b)
    buf_b = io.BytesIO()
    df_b.to_excel(buf_b, index=False)

    session_id = "test_multi_file_persist_session"
    conversation_context_manager.clear_state(session_id)

    # 1. Upload both files simultaneously
    upload_res = client.post(
        "/api/company/upload-multiple",
        files=[
            ("files", ("EBO TB Topup.xlsx", buf_a.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")),
            ("files", ("UPI QR Topup.xlsx", buf_b.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
        ],
        data={"session_id": session_id}
    )
    assert upload_res.status_code == 200
    assert upload_res.json()["count"] == 2

    # 2. "compare these two files" -> EXCEL_COMPARE
    r_comp = client.post("/api/company/chat", json={
        "message": "compare these two files",
        "session_id": session_id,
        "user_role": "EMPLOYEE"
    })
    assert r_comp.status_code == 200
    assert r_comp.json()["intent"] == "excel_compare"
    assert "reconcil" in r_comp.json()["answer"].lower() or "matched" in r_comp.json()["answer"].lower()

    # 3. Follow-up "show me the mismatches"
    r_mis = client.post("/api/company/chat", json={
        "message": "show me the mismatches",
        "session_id": session_id,
        "user_role": "EMPLOYEE"
    })
    assert r_mis.status_code == 200
    assert r_mis.json()["intent"] == "excel_compare"

    # 4. Verify conversation persistence via API
    conv_list = client.get("/api/company/conversations")
    assert conv_list.status_code == 200
    conv_items = conv_list.json()
    assert any(c["id"] == session_id for c in conv_items)

    # 5. Retrieve specific conversation details (simulating browser refresh restoration)
    conv_detail = client.get(f"/api/company/conversations/{session_id}")
    assert conv_detail.status_code == 200
    detail_data = conv_detail.json()
    assert len(detail_data.get("messages", [])) >= 4 # User + Assistant turns recorded
    assert detail_data.get("title") != session_id # Human-readable title, not UUID
