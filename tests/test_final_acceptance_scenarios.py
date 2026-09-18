"""End-to-End Acceptance Tests for MYGPT Company AI Final Corrections.

Validates:
1. Two-file reconciliation key discovery: Rejects categorical columns (BRANCH_CODE, STORE_ID) and picks high-cardinality unique IDs (RID).
2. Multi-document summary ("these 2"): Returns rich Markdown + UI card report with Highest Txn, Mismatches, Bank Names, and NO Excel file attached.
3. Strict Excel output control: Excel is generated ONLY when explicitly requested.
4. Contextual Excel export: "give me that as Excel" exports the exact previous result.
5. Single metric query ("what is the highest transaction") + follow-up export.
"""

import os
import pytest
import pandas as pd
from starlette.testclient import TestClient
from backend.app.main import app
from backend.app.services.excel.excel_comparator import excel_comparator
from backend.app.services.conversation_context_manager import conversation_context_manager


@pytest.fixture
def client():
    return TestClient(app)


def create_test_transaction_workbook_a(path: str):
    """Creates a sample EBO Topup workbook with RID, Agent_name, Amount, Mode, Date, Status."""
    data = {
        "RID": [f"EBO_{1000 + i}" for i in range(20)],
        "Agent_name": [f"Agent_{i % 3}" for i in range(20)],
        "Amount": [100.0 * (i + 1) for i in range(19)] + [25000.0],  # max 25000
        "Transaction Mode": ["QR" if i % 2 == 0 else "UPI" for i in range(20)],
        "CRTD_DATE": ["2026-06-17 10:00:00" for _ in range(20)],
        "Status": ["Authorised" for _ in range(20)],
        "BRANCH_CODE": ["BR_001" for _ in range(20)]  # Categorical column (low uniqueness)
    }
    df = pd.DataFrame(data)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Topup_Data")


def create_test_transaction_workbook_b(path: str):
    """Creates a sample UPI QR workbook with matching RIDs, some missing, and some amount differences."""
    data = {
        "RID": [f"EBO_{1000 + i}" for i in range(5, 25)],  # 5..19 overlap with A, 20..24 missing in A
        "Merchant_ID": [f"M_{i}" for i in range(20)],
        "Amount": [100.0 * (i + 1) if i != 10 else 999.0 for i in range(5, 25)],  # i=10 has amount diff
        "Payment_Channel": ["UPI" for _ in range(20)],
        "Txn_Date": ["2026-06-17 10:05:00" for _ in range(20)],
        "Status": ["Authorised" for _ in range(20)],
        "BRANCH_CODE": ["BR_001" for _ in range(20)]  # Shared categorical column
    }
    df = pd.DataFrame(data)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="UPI_Settlement")


@pytest.fixture
def setup_test_workbooks(tmp_path):
    file_a = str(tmp_path / "EBO_Topup_Test.xlsx")
    file_b = str(tmp_path / "UPI_QR_Test.xlsx")
    create_test_transaction_workbook_a(file_a)
    create_test_transaction_workbook_b(file_b)
    return file_a, file_b


def test_key_discovery_rejects_categorical_columns(setup_test_workbooks):
    """Verifies that discover_matching_keys rejects BRANCH_CODE and selects RID."""
    file_a, file_b = setup_test_workbooks
    key_res = excel_comparator.discover_matching_keys(file_a, file_b)
    assert key_res.get("found") is True
    assert key_res.get("key_a") == "RID", f"Expected RID but got {key_res.get('key_a')}"
    assert key_res.get("key_b") == "RID", f"Expected RID but got {key_res.get('key_b')}"
    assert key_res.get("key_a") != "BRANCH_CODE"


def test_multi_document_summary_and_export_flow(client, setup_test_workbooks):
    """Tests the full multi-document summary request and subsequent export."""
    file_a, file_b = setup_test_workbooks
    session_id = "test_multi_doc_acceptance_session"
    conversation_context_manager.clear_state(session_id)

    # 1. Upload Document A
    with open(file_a, "rb") as f:
        up_a = client.post("/api/company/upload", files={"file": ("EBO_Topup_Test.xlsx", f.read(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}, data={"session_id": session_id})
    assert up_a.status_code == 200

    # 2. Upload Document B
    with open(file_b, "rb") as f:
        up_b = client.post("/api/company/upload", files={"file": ("UPI_QR_Test.xlsx", f.read(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}, data={"session_id": session_id})
    assert up_b.status_code == 200

    # 3. User asks for multi-doc summary
    query_1 = "give me a summary report for this 2 the summary should contain highest transaction, what are the mismatch, what are the bank names"
    res1 = client.post("/api/company/chat", json={
        "message": query_1,
        "session_id": session_id,
        "user_role": "EMPLOYEE"
    })
    assert res1.status_code == 200
    data1 = res1.json()

    assert data1["intent"] == "excel_multi_document_summary"
    # Strict output control: NO file should be generated or attached for summary
    assert len(data1.get("files", [])) == 0, f"Expected 0 files attached by default but got {len(data1.get('files', []))}"
    
    # Check tool results & card type
    assert data1["tool_results"]["card_type"] == "multi_document_summary"
    assert data1["tool_results"]["highest_transaction"] == "₹25,000.00"
    assert data1["tool_results"]["reconciliation_key"] == "RID ↔ RID"
    assert data1["tool_results"]["total_mismatches"] > 0

    # Check findings content
    answer_text = data1.get("answer", "")
    assert "Highest Transaction" in answer_text
    assert "Discrepancies" in answer_text or "Reconciliation" in answer_text
    assert "Bank" in answer_text
    assert "25,000" in answer_text

    # 4. User asks "give me that as Excel"
    query_2 = "give me that as Excel"
    res2 = client.post("/api/company/chat", json={
        "message": query_2,
        "session_id": session_id,
        "user_role": "EMPLOYEE"
    })
    assert res2.status_code == 200
    data2 = res2.json()

    assert data2["intent"] == "excel_export_result"
    assert len(data2.get("files", [])) == 1, f"Expected 1 file attached on explicit Excel request but got {len(data2.get('files', []))}"
    exported_file = data2["files"][0]
    assert exported_file["filename"].endswith(".xlsx")
    assert "Multi_Document_Summary_Report" in exported_file["filename"] or "Summary" in exported_file["filename"]


def test_single_metric_and_export_flow(client, setup_test_workbooks):
    """Tests single metric question ('what is the highest transaction in the excel') and follow-up export."""
    file_a, _ = setup_test_workbooks
    session_id = "test_single_metric_session"
    conversation_context_manager.clear_state(session_id)

    with open(file_a, "rb") as f:
        up_a = client.post("/api/company/upload", files={"file": ("EBO_Topup_Test.xlsx", f.read(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}, data={"session_id": session_id})
    assert up_a.status_code == 200

    # 1. User asks "what is the highest transaction in the excel"
    query_1 = "what is the highest transaction in the excel"
    res1 = client.post("/api/company/chat", json={
        "message": query_1,
        "session_id": session_id,
        "user_role": "EMPLOYEE"
    })
    assert res1.status_code == 200
    data1 = res1.json()

    assert data1["intent"] == "excel_max"
    assert len(data1.get("files", [])) == 0  # No file attached by default
    assert "25,000" in data1.get("answer", "")
    assert data1["tool_results"]["primary_value"] == "₹25,000.00"

    # 2. User asks "give me this as Excel"
    query_2 = "give me this as Excel"
    res2 = client.post("/api/company/chat", json={
        "message": query_2,
        "session_id": session_id,
        "user_role": "EMPLOYEE"
    })
    assert res2.status_code == 200
    data2 = res2.json()

    assert data2["intent"] == "excel_export_result"
    assert len(data2.get("files", [])) == 1
    assert data2["files"][0]["filename"].endswith(".xlsx")
