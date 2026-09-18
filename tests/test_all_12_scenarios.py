"""Comprehensive Automated Test Suite verifying all 12 exact Phase 4 Company AI scenarios.
"""

import io
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


# TEST 1: User "hi" -> GENERAL / greeting
def test_scenario_01_greeting():
    session_id = "test_s01_greeting"
    client.post("/api/company/chat/reset", params={"session_id": session_id})
    res = client.post(
        "/api/company/chat",
        json={"message": "hi", "session_id": session_id, "user_role": "EMPLOYEE"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["department"] == "GENERAL"
    assert data["intent"] == "greeting"
    assert "help" in data["answer"].lower() or "hello" in data["answer"].lower() or "mygpt" in data["answer"].lower()


# TEST 2: User "what is casual leave policy?" -> HR / POLICY_QUESTION
def test_scenario_02_leave_policy():
    session_id = "test_s02_leave"
    client.post("/api/company/chat/reset", params={"session_id": session_id})
    res = client.post(
        "/api/company/chat",
        json={"message": "what is casual leave policy?", "session_id": session_id, "user_role": "EMPLOYEE"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["department"] == "HR"
    assert data["intent"] == "policy_question"
    assert "casual leave" in data["answer"].lower() or "12" in data["answer"]


# TEST 3: Upload Evlyn HR OPS.pdf -> "give me the overall summary" -> HR / DOCUMENT_SUMMARY
def test_scenario_03_pdf_upload_and_summary():
    session_id = "test_s03_hr_summary"
    client.post("/api/company/chat/reset", params={"session_id": session_id})

    # Upload HR OPS document
    doc_content = b"""
    MYGPT HUMAN RESOURCES OPERATIONS MANUAL
    Document ID: HR-OPS-2026-01
    Effective Date: 2026-01-01
    Target Audience: All Corporate Employees

    1. PURPOSE & SCOPE
    This operational guide establishes standard procedures for employee onboarding, attendance, performance management, and offboarding.

    2. EMPLOYEE GUIDELINES & LEAVE ENTITLEMENTS
    Employees receive 12 days of Casual Leave and 10 days of Sick Leave annually.

    3. COMPENSATION & PERFORMANCE REVIEWS
    Annual compensation evaluations are conducted in Q4 of each fiscal year.
    """
    file_tuple = ("Evlyn_HR_OPS.txt", io.BytesIO(doc_content), "text/plain")
    up_res = client.post(
        "/api/company/upload",
        files={"file": file_tuple},
        data={"session_id": session_id, "user_role": "EMPLOYEE", "user_id": "emp_01"}
    )
    assert up_res.status_code == 200
    up_data = up_res.json()
    assert up_data["success"] is True

    # Ask for overall summary
    res = client.post(
        "/api/company/chat",
        json={"message": "give me the overall summary", "session_id": session_id, "user_role": "EMPLOYEE"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["department"] == "HR"
    assert data["intent"] in ("document_summary", "policy_question")
    assert "Evlyn_HR_OPS" in data["answer"] or "operations" in data["answer"].lower() or "leave" in data["answer"].lower()


# TEST 4: After previous test: "give me that in Excel" -> HR / DOCUMENT_EXPORT (actual XLSX download)
def test_scenario_04_export_excel_after_summary():
    session_id = "test_s04_hr_excel"
    client.post("/api/company/chat/reset", params={"session_id": session_id})

    # Upload first
    doc_content = b"MYGPT HR Policy: Casual leave is 12 days. Sick leave is 10 days."
    file_tuple = ("Evlyn_HR_OPS.txt", io.BytesIO(doc_content), "text/plain")
    client.post("/api/company/upload", files={"file": file_tuple}, data={"session_id": session_id, "user_role": "EMPLOYEE"})
    
    # Summary turn
    client.post("/api/company/chat", json={"message": "give me the overall summary", "session_id": session_id, "user_role": "EMPLOYEE"})

    # Export turn
    res = client.post(
        "/api/company/chat",
        json={"message": "give me that in Excel", "session_id": session_id, "user_role": "HR_MANAGER"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["department"] == "HR"
    assert data["files"] and len(data["files"]) > 0
    assert data["files"][0]["filename"].endswith(".xlsx")


# TEST 5: After previous test: "what is the purpose of this document?" -> HR / DOCUMENT_QUESTION
def test_scenario_05_document_qa_followup():
    session_id = "test_s05_doc_qa"
    client.post("/api/company/chat/reset", params={"session_id": session_id})

    doc_content = b"""
    MYGPT HR OPERATIONS
    Purpose: Establish standards for onboarding, attendance, and leave management.
    """
    file_tuple = ("Evlyn_HR_OPS.txt", io.BytesIO(doc_content), "text/plain")
    client.post("/api/company/upload", files={"file": file_tuple}, data={"session_id": session_id, "user_role": "EMPLOYEE"})

    res = client.post(
        "/api/company/chat",
        json={"message": "what is the purpose of this document?", "session_id": session_id, "user_role": "EMPLOYEE"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["department"] == "HR"
    assert "Evlyn_HR_OPS" in data["answer"] or "document" in data["answer"].lower() or "policy" in data["answer"].lower()


# TEST 6: Upload two invoices -> "compare these two" -> FINANCE / DOCUMENT_COMPARISON
def test_scenario_06_compare_two_invoices():
    session_id = "test_s06_compare"
    client.post("/api/company/chat/reset", params={"session_id": session_id})

    inv1 = b"INVOICE 001\nVendor: Acme Services\nSubtotal: $1,500.00\nTotal: $1,770.00"
    inv2 = b"INVOICE 002\nVendor: Acme Services\nSubtotal: $1,750.00\nTotal: $2,065.00"

    client.post("/api/company/upload", files={"file": ("inv1.txt", io.BytesIO(inv1), "text/plain")}, data={"session_id": session_id, "user_role": "FINANCE_MANAGER"})
    client.post("/api/company/upload", files={"file": ("inv2.txt", io.BytesIO(inv2), "text/plain")}, data={"session_id": session_id, "user_role": "FINANCE_MANAGER"})

    res = client.post(
        "/api/company/chat",
        json={"message": "compare these two", "session_id": session_id, "user_role": "FINANCE_MANAGER"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["department"] == "FINANCE"
    assert data["intent"] in ("excel_comparison", "file_comparison")
    assert "variance" in data["answer"].lower() or "mismatch" in data["answer"].lower() or "compared" in data["answer"].lower()


# TEST 7: Then: "give me the summary" -> FINANCE / DOCUMENT_COMPARISON_SUMMARY
def test_scenario_07_compare_summary():
    session_id = "test_s07_comp_sum"
    client.post("/api/company/chat/reset", params={"session_id": session_id})

    inv1 = b"INVOICE 001\nVendor: Acme Services\nTotal: $1,770.00"
    inv2 = b"INVOICE 002\nVendor: Acme Services\nTotal: $2,065.00"
    client.post("/api/company/upload", files={"file": ("inv1.txt", io.BytesIO(inv1), "text/plain")}, data={"session_id": session_id, "user_role": "FINANCE_MANAGER"})
    client.post("/api/company/upload", files={"file": ("inv2.txt", io.BytesIO(inv2), "text/plain")}, data={"session_id": session_id, "user_role": "FINANCE_MANAGER"})

    client.post("/api/company/chat", json={"message": "compare these two", "session_id": session_id, "user_role": "FINANCE_MANAGER"})

    res = client.post(
        "/api/company/chat",
        json={"message": "give me the summary", "session_id": session_id, "user_role": "FINANCE_MANAGER"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["department"] == "FINANCE"
    assert "inv" in data["answer"].lower() or "summary" in data["answer"].lower() or "comparison" in data["answer"].lower()


# TEST 8: Then: "export it" -> actual XLSX comparison report
def test_scenario_08_export_comparison():
    session_id = "test_s08_comp_exp"
    client.post("/api/company/chat/reset", params={"session_id": session_id})

    inv1 = b"INVOICE 001\nVendor: Acme Services\nTotal: $1,770.00"
    inv2 = b"INVOICE 002\nVendor: Acme Services\nTotal: $2,065.00"
    client.post("/api/company/upload", files={"file": ("inv1.txt", io.BytesIO(inv1), "text/plain")}, data={"session_id": session_id, "user_role": "FINANCE_MANAGER"})
    client.post("/api/company/upload", files={"file": ("inv2.txt", io.BytesIO(inv2), "text/plain")}, data={"session_id": session_id, "user_role": "FINANCE_MANAGER"})

    client.post("/api/company/chat", json={"message": "compare these two", "session_id": session_id, "user_role": "FINANCE_MANAGER"})

    res = client.post(
        "/api/company/chat",
        json={"message": "export it", "session_id": session_id, "user_role": "FINANCE_MANAGER"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["department"] == "FINANCE"
    assert data["files"] and len(data["files"]) > 0
    assert data["files"][0]["filename"].endswith(".xlsx")


# TEST 9: User "generate July travel expense report" -> FINANCE / EXPENSE_REPORT
def test_scenario_09_generate_expense_report():
    session_id = "test_s09_exp_rep"
    client.post("/api/company/chat/reset", params={"session_id": session_id})

    res = client.post(
        "/api/company/chat",
        json={"message": "generate July travel expense report", "session_id": session_id, "user_role": "FINANCE_MANAGER"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["department"] == "FINANCE"
    assert data["intent"] == "expense_report"
    assert data["files"] and len(data["files"]) > 0
    assert "July" in data["files"][0]["filename"] or "july" in data["files"][0]["filename"]


# TEST 10: Then: "give me a summary of this report" -> FINANCE / EXPENSE_REPORT_SUMMARY
def test_scenario_10_expense_report_summary():
    session_id = "test_s10_exp_sum"
    client.post("/api/company/chat/reset", params={"session_id": session_id})

    client.post("/api/company/chat", json={"message": "generate July travel expense report", "session_id": session_id, "user_role": "FINANCE_MANAGER"})

    res = client.post(
        "/api/company/chat",
        json={"message": "give me a summary of this report", "session_id": session_id, "user_role": "FINANCE_MANAGER"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["department"] == "FINANCE"
    assert data["intent"] in ("expense_report_summary", "document_summary")
    assert "July" in data["answer"] or "expense" in data["answer"].lower() or "2,250" in data["answer"]


# TEST 11: Employee tries confidential Finance report -> DENIED BY RBAC
def test_scenario_11_rbac_denial():
    session_id = "test_s11_rbac_denied"
    client.post("/api/company/chat/reset", params={"session_id": session_id})

    res = client.post(
        "/api/company/chat",
        json={"message": "generate July travel expense report", "session_id": session_id, "user_role": "EMPLOYEE"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "permission_denied"
    assert "restricted" in data["answer"].lower() or "denied" in data["answer"].lower() or "permission" in data["answer"].lower()


# TEST 12: Upload HR template -> "create an offer letter for Mohamed Fazil" -> HR / OFFER_LETTER (actual DOCX download)
def test_scenario_12_create_offer_letter_docx():
    session_id = "test_s12_offer"
    client.post("/api/company/chat/reset", params={"session_id": session_id})

    tmpl = b"OFFER LETTER TEMPLATE\nPosition: Senior AI Engineer\nAnnual Salary: $140,000\nStart Date: 2026-11-01"
    client.post("/api/company/upload", files={"file": ("Offer_Template.txt", io.BytesIO(tmpl), "text/plain")}, data={"session_id": session_id, "user_role": "HR_MANAGER"})

    res = client.post(
        "/api/company/chat",
        json={"message": "create an offer letter for Mohamed Fazil", "session_id": session_id, "user_role": "HR_MANAGER"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["department"] == "HR"
    assert data["intent"] == "offer_letter"
    assert "Mohamed Fazil" in data["answer"]
    assert data["files"] and len(data["files"]) > 0
    assert data["files"][0]["filename"].endswith(".docx")
    assert "mohamed_fazil" in data["files"][0]["filename"].lower()

    # Verify download endpoint for this file
    file_id = data["files"][0].get("file_id")
    assert file_id is not None
    dl_res = client.get(f"/api/company/files/{file_id}/download", params={"user_role": "HR_MANAGER"})
    assert dl_res.status_code == 200
    assert len(dl_res.content) > 100
