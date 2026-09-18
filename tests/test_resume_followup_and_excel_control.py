import io
import pytest
import pandas as pd
from starlette.testclient import TestClient
from backend.app.main import app
from backend.app.services.conversation_context_manager import conversation_context_manager

@pytest.fixture
def client():
    return TestClient(app)

def test_resume_followup_and_excel_control(client):
    resume_a = """
    PRIYA SHARMA
    Senior HR Specialist
    Email: priya.sharma@example.com | Phone: +91 9123456780
    
    PROFESSIONAL SUMMARY:
    HR Professional with 6 years of experience in Talent Acquisition, Employee Relations, and Payroll Compliance.
    
    WORK EXPERIENCE:
    ABC Global — Senior HR Generalist (2020 - Present)
    • Managed end-to-end recruitment for 150+ technical and non-technical roles.
    • Oversaw HR operations, compliance policies, and performance appraisals.
    
    DEF Corp — HR Executive (2018 - 2020)
    • Handled onboarding, attendance tracking, and benefits administration.
    
    EDUCATION:
    MBA in Human Resources — Symbiosis Institute (2016 - 2018)
    
    SKILLS:
    Talent Acquisition, Employee Relations, HR Operations, Payroll, Statutory Compliance, HRIS
    """

    resume_b = """
    ANANYA VERMA
    HR Associate
    Email: ananya.v@example.com | Phone: +91 9988776655
    
    PROFESSIONAL SUMMARY:
    Dedicated HR Associate with 2 years of experience in recruitment coordination and HR documentation.
    
    WORK EXPERIENCE:
    Startup Hub — HR Coordinator (2022 - Present)
    • Coordinated candidate interviews and screening calls.
    • Maintained employee personnel files and leave records.
    
    EDUCATION:
    BBA in Human Resource Management — Delhi University (2019 - 2022)
    
    SKILLS:
    Interview Scheduling, Sourcing, Screening, MS Excel, HR Administration
    """

    session_id = "test_resume_followup_excel_control_session"
    conversation_context_manager.clear_state(session_id)

    # -------------------------------------------------------------
    # SETUP: Upload 2 Resumes
    # -------------------------------------------------------------
    files_a = {"file": ("priya_sharma_hr_resume.txt", resume_a.encode("utf-8"), "text/plain")}
    up_a = client.post("/api/company/upload", files=files_a, data={"session_id": session_id})
    assert up_a.status_code == 200

    files_b = {"file": ("ananya_verma_hr_resume.txt", resume_b.encode("utf-8"), "text/plain")}
    up_b = client.post("/api/company/upload", files=files_b, data={"session_id": session_id})
    assert up_b.status_code == 200

    # -------------------------------------------------------------
    # TEST 1: "compare these two resumes for HR role"
    # Expected: Resume comparison, NO Excel (files list empty).
    # -------------------------------------------------------------
    res1 = client.post("/api/company/chat", json={
        "message": "compare these two resumes for HR role",
        "session_id": session_id,
        "user_role": "HR_MANAGER"
    })
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["department"] == "HR"
    assert data1["intent"] == "candidate_comparison"
    assert len(data1.get("files", [])) == 0, "TEST 1 FAILED: Generated Excel when user only asked for comparison!"
    assert "priya sharma" in data1["answer"].lower() or "ananya verma" in data1["answer"].lower()
    assert data1["tool_results"]["card_type"] == "resume_comparison"

    # -------------------------------------------------------------
    # TEST 2: "who is best for the HR position?"
    # Expected: Use previous comparison context, answer from actual comparison, NO generic dept message, NO Excel.
    # -------------------------------------------------------------
    res2 = client.post("/api/company/chat", json={
        "message": "who is best for the HR position?",
        "session_id": session_id,
        "user_role": "HR_MANAGER"
    })
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["department"] == "HR"
    assert data2["intent"] == "candidate_comparison"
    assert "priya sharma" in data2["answer"].lower(), "TEST 2 FAILED: Did not recommend Priya Sharma from verified comparison"
    assert len(data2.get("files", [])) == 0, "TEST 2 FAILED: Generated Excel when user only asked who is best!"
    assert "I can help you with HR policies" not in data2["answer"], "TEST 2 FAILED: Generic department message returned!"

    # -------------------------------------------------------------
    # TEST 3: "why?"
    # Expected: Explain comparison based on verified resume data, NO Excel.
    # -------------------------------------------------------------
    res3 = client.post("/api/company/chat", json={
        "message": "why?",
        "session_id": session_id,
        "user_role": "HR_MANAGER"
    })
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["department"] == "HR"
    assert data3["intent"] == "candidate_comparison"
    assert len(data3.get("files", [])) == 0, "TEST 3 FAILED: Generated Excel when user only asked why!"
    assert "priya sharma" in data3["answer"].lower() or "experience" in data3["answer"].lower()

    # -------------------------------------------------------------
    # TEST 4: "give me more details"
    # Expected: Detailed comparison, NO Excel.
    # -------------------------------------------------------------
    res4 = client.post("/api/company/chat", json={
        "message": "give me more details",
        "session_id": session_id,
        "user_role": "HR_MANAGER"
    })
    assert res4.status_code == 200
    data4 = res4.json()
    assert data4["department"] == "HR"
    assert data4["intent"] == "candidate_comparison"
    assert len(data4.get("files", [])) == 0, "TEST 4 FAILED: Generated Excel when user asked for more details!"

    # -------------------------------------------------------------
    # TEST 5: "give me the comparison in Excel"
    # Expected: Generate exactly one Excel file, show preview/download card.
    # -------------------------------------------------------------
    res5 = client.post("/api/company/chat", json={
        "message": "give me the comparison in Excel",
        "session_id": session_id,
        "user_role": "HR_MANAGER"
    })
    assert res5.status_code == 200
    data5 = res5.json()
    assert data5["department"] == "HR"
    assert len(data5.get("files", [])) == 1, "TEST 5 FAILED: Expected exactly 1 generated Excel report"
    assert data5["files"][0]["filename"].endswith(".xlsx")

    # -------------------------------------------------------------
    # TEST 6: "give me the summary"
    # Expected: Summary only, NO Excel.
    # -------------------------------------------------------------
    res6 = client.post("/api/company/chat", json={
        "message": "give me the summary",
        "session_id": session_id,
        "user_role": "HR_MANAGER"
    })
    assert res6.status_code == 200
    data6 = res6.json()
    assert len(data6.get("files", [])) == 0, "TEST 6 FAILED: Generated Excel on 'give me the summary'!"

    # -------------------------------------------------------------
    # TEST 7: Upload UPI Excel -> "give me the overall summary"
    # Expected: Summary only, NO Excel.
    # -------------------------------------------------------------
    session_id_excel = "test_excel_control_session_upi"
    conversation_context_manager.clear_state(session_id_excel)

    df_sample = pd.DataFrame([
        {"Transaction ID": "TXN1001", "Mode": "UPI", "Amount": 1500.0, "Status": "Success"},
        {"Transaction ID": "TXN1002", "Mode": "NEFT", "Amount": 25000.0, "Status": "Success"},
        {"Transaction ID": "TXN1003", "Mode": "UPI", "Amount": 300.0, "Status": "Success"},
        {"Transaction ID": "TXN1004", "Mode": "UPI", "Amount": 450.0, "Status": "Success"},
    ])
    buf = io.BytesIO()
    df_sample.to_excel(buf, index=False)
    buf.seek(0)

    files_excel = {"file": ("EBO TB Topup_sample.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    up_excel = client.post("/api/company/upload", files=files_excel, data={"session_id": session_id_excel})
    assert up_excel.status_code == 200

    res7 = client.post("/api/company/chat", json={
        "message": "give me the overall summary",
        "session_id": session_id_excel,
        "user_role": "FINANCE_MANAGER"
    })
    assert res7.status_code == 200
    data7 = res7.json()
    assert len(data7.get("files", [])) == 0, "TEST 7 FAILED: Generated Excel on 'give me the overall summary'!"
    assert "4" in data7["answer"] or "Total" in data7["answer"]

    # -------------------------------------------------------------
    # TEST 8: "calculate the total amount"
    # Expected: Total only, NO Excel.
    # -------------------------------------------------------------
    res8 = client.post("/api/company/chat", json={
        "message": "calculate the total amount",
        "session_id": session_id_excel,
        "user_role": "FINANCE_MANAGER"
    })
    assert res8.status_code == 200
    data8 = res8.json()
    assert len(data8.get("files", [])) == 0, "TEST 8 FAILED: Generated Excel on 'calculate the total amount'!"
    assert "27,250" in data8["answer"]

    # -------------------------------------------------------------
    # TEST 9: "give me that as Excel"
    # Expected: Export the previous verified result, exactly one Excel card.
    # -------------------------------------------------------------
    res9 = client.post("/api/company/chat", json={
        "message": "give me that as Excel",
        "session_id": session_id_excel,
        "user_role": "FINANCE_MANAGER"
    })
    assert res9.status_code == 200
    data9 = res9.json()
    assert len(data9.get("files", [])) == 1, "TEST 9 FAILED: Expected exactly 1 generated Excel export"
    assert data9["files"][0]["filename"].endswith(".xlsx")
