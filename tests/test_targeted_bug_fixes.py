import io
import pytest
import pandas as pd
from starlette.testclient import TestClient
from backend.app.main import app
from backend.app.services.conversation_context_manager import conversation_context_manager

@pytest.fixture
def client():
    return TestClient(app)

def test_exact_user_scenarios(client):
    # -------------------------------------------------------------
    # TEST 1 — RESUME FOLLOW-UPS & PRONOUN/TYPO RESOLUTION
    # -------------------------------------------------------------
    resume_text = """
    SARAVANA KUMAR
    Senior Full Stack Developer
    Email: saravana@example.com | Phone: +91 9876543210
    
    PROFESSIONAL SUMMARY:
    Over 5 years of software engineering experience building scalable microservices and React web applications.
    
    WORK EXPERIENCE:
    Company A — Software Engineer (2019 - 2020)
    • Developed REST APIs in Node.js and PostgreSQL.
    
    Company B — Senior Engineer (2020 - 2023)
    • Architected cloud applications on AWS and Docker.
    
    TechCorp Inc — Lead Developer (2023 - Present)
    • Leading a team of 6 engineers on Next.js, Python, FastAPI and microservices.
    
    EDUCATION:
    B.E. Computer Science and Engineering — Anna University (2015 - 2019)
    
    SKILLS:
    Python, FastAPI, React, TypeScript, Node.js, Docker, Kubernetes, AWS, PostgreSQL, MongoDB
    
    CERTIFICATIONS:
    AWS Certified Solutions Architect Associate (2022)
    """
    
    session_id_resume = "test_conv_saravana_targeted_bug_fix"
    conversation_context_manager.clear_state(session_id_resume)
    
    # Upload Resume as text
    files = {"file": ("saravana resume new - Copy.txt", resume_text.encode("utf-8"), "text/plain")}
    upload_res = client.post("/api/company/upload", files=files, data={"session_id": session_id_resume})
    assert upload_res.status_code == 200
    doc_id = upload_res.json()["doc_id"]
    assert upload_res.json()["document_type"] == "RESUME"
    
    # 1. "give the summary of this resume"
    r1 = client.post("/api/company/chat", json={
        "message": "give the summary of this resume",
        "session_id": session_id_resume,
        "user_role": "HR_MANAGER"
    })
    assert r1.status_code == 200
    data1 = r1.json()
    assert data1["department"].upper() == "HR"
    assert "saravana" in data1["answer"].lower()
    
    # 2. "what is the experince of this candidate" (note typo 'experince')
    r2 = client.post("/api/company/chat", json={
        "message": "what is the experince of this candidate",
        "session_id": session_id_resume,
        "user_role": "HR_MANAGER"
    })
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["department"].upper() == "HR"
    assert "GENERAL" not in data2["department"].upper()
    assert ("Company A" in data2["answer"] or "TechCorp" in data2["answer"] or "Experience" in data2["answer"] or "software engineering" in data2["answer"].lower())
    
    # 3. "what is the educational details of this candidate"
    r3 = client.post("/api/company/chat", json={
        "message": "what is the educational details of this candidate",
        "session_id": session_id_resume,
        "user_role": "HR_MANAGER"
    })
    assert r3.status_code == 200
    data3 = r3.json()
    assert data3["department"].upper() == "HR"
    assert ("Anna University" in data3["answer"] or "Computer Science" in data3["answer"] or "Education" in data3["answer"])
    
    # 4. "what skills does he have?"
    r4 = client.post("/api/company/chat", json={
        "message": "what skills does he have?",
        "session_id": session_id_resume,
        "user_role": "HR_MANAGER"
    })
    assert r4.status_code == 200
    data4 = r4.json()
    assert data4["department"].upper() == "HR"
    assert ("Python" in data4["answer"] or "React" in data4["answer"] or "Skills" in data4["answer"])
    
    # 5. "tell me more"
    r5 = client.post("/api/company/chat", json={
        "message": "tell me more",
        "session_id": session_id_resume,
        "user_role": "HR_MANAGER"
    })
    assert r5.status_code == 200
    data5 = r5.json()
    assert data5["department"].upper() == "HR"
    assert "GENERAL" not in data5["department"].upper()
    
    # -------------------------------------------------------------
    # TEST 2 — EXCEL FOLLOW-UPS
    # -------------------------------------------------------------
    df_upi = pd.DataFrame({
        "RID": ["RID001", "RID002", "RID003"],
        "Transaction Date": ["2026-06-01", "2026-06-02", "2026-06-03"],
        "Amount": [500000.00, 519715.76, 500000.00],
        "Payer Name": ["Customer 1", "Customer 2", "Customer 3"],
        "Status": ["SUCCESS", "SUCCESS", "SUCCESS"]
    })
    buf = io.BytesIO()
    df_upi.to_excel(buf, index=False)
    upi_bytes = buf.getvalue()
    
    session_id_excel = "test_conv_upi_excel_targeted_bug_fix"
    conversation_context_manager.clear_state(session_id_excel)
    
    files_upi = {"file": ("UPI - QR FROM 31-5-26 TO 15-06-26 1.xlsx", upi_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    upload_res2 = client.post("/api/company/upload", files=files_upi, data={"session_id": session_id_excel})
    assert upload_res2.status_code == 200
    
    # 1. "calculate the total amount in the excel"
    r_ex1 = client.post("/api/company/chat", json={
        "message": "calculate the total amount in the excel",
        "session_id": session_id_excel,
        "user_role": "EMPLOYEE"
    })
    assert r_ex1.status_code == 200
    assert "15,19,715.76" in r_ex1.json()["answer"]
    
    # 2. "give me the names of the columns"
    r_ex2 = client.post("/api/company/chat", json={
        "message": "give me the names of the columns",
        "session_id": session_id_excel,
        "user_role": "EMPLOYEE"
    })
    assert r_ex2.status_code == 200
    assert ("RID" in r_ex2.json()["answer"] and "Amount" in r_ex2.json()["answer"])
    
    # 3. "how many transactions are there?"
    r_ex3 = client.post("/api/company/chat", json={
        "message": "how many transactions are there?",
        "session_id": session_id_excel,
        "user_role": "EMPLOYEE"
    })
    assert r_ex3.status_code == 200
    assert "3" in r_ex3.json()["answer"]
    
    # 4. "give me the RID as the Excel sheet"
    r_ex4 = client.post("/api/company/chat", json={
        "message": "give me the RID as the Excel sheet",
        "session_id": session_id_excel,
        "user_role": "EMPLOYEE"
    })
    assert r_ex4.status_code == 200
    assert len(r_ex4.json().get("files", [])) > 0 or "download" in r_ex4.json()["answer"].lower()

    # -------------------------------------------------------------
    # TEST 3 — TWO EXCEL FILES CONTEXT
    # -------------------------------------------------------------
    df_ebo = pd.DataFrame({
        "Reference No": ["RID001", "RID002", "RID999"],
        "Topup Date": ["2026-06-01", "2026-06-02", "2026-06-04"],
        "Net Amount": [500000.00, 519715.76, 25000.00],
        "Store": ["Store A", "Store B", "Store C"]
    })
    buf_ebo = io.BytesIO()
    df_ebo.to_excel(buf_ebo, index=False)
    ebo_bytes = buf_ebo.getvalue()
    
    session_id_compare = "test_conv_two_file_compare_targeted_bug_fix"
    conversation_context_manager.clear_state(session_id_compare)
    
    # Upload UPI
    client.post("/api/company/upload", files={"file": ("UPI - QR.xlsx", upi_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}, data={"session_id": session_id_compare})
    # Upload EBO
    client.post("/api/company/upload", files={"file": ("EBO TOPUP JUNE.xlsx", ebo_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}, data={"session_id": session_id_compare})
    
    # 1. "compare these two"
    r_cmp1 = client.post("/api/company/chat", json={
        "message": "compare these two",
        "session_id": session_id_compare,
        "user_role": "EMPLOYEE"
    })
    assert r_cmp1.status_code == 200
    assert "mismatch" in r_cmp1.json()["answer"].lower() or "reconciliation" in r_cmp1.json()["answer"].lower() or "matched" in r_cmp1.json()["answer"].lower()
    
    # 2. "show the mismatches"
    r_cmp2 = client.post("/api/company/chat", json={
        "message": "show the mismatches",
        "session_id": session_id_compare,
        "user_role": "EMPLOYEE"
    })
    assert r_cmp2.status_code == 200
    assert "mismatch" in r_cmp2.json()["answer"].lower() or "RID003" in r_cmp2.json()["answer"] or "RID999" in r_cmp2.json()["answer"]
    
    # 3. "give me that as Excel"
    r_cmp3 = client.post("/api/company/chat", json={
        "message": "give me that as Excel",
        "session_id": session_id_compare,
        "user_role": "EMPLOYEE"
    })
    assert r_cmp3.status_code == 200
    assert len(r_cmp3.json().get("files", [])) > 0 or "excel" in r_cmp3.json()["answer"].lower()
    
    # 4. "how many mismatches?"
    r_cmp4 = client.post("/api/company/chat", json={
        "message": "how many mismatches?",
        "session_id": session_id_compare,
        "user_role": "EMPLOYEE"
    })
    assert r_cmp4.status_code == 200
    assert "mismatch" in r_cmp4.json()["answer"].lower()


def test_ebo_topup_conversation_and_excel_preview(client):
    """Verifies PART 1-10 & PART 22 & 25 exact EBO Topup conversation flow."""
    # Create representative EBO Topup dataset with 1,419 rows
    rows = []
    for i in range(1, 1420):
        rows.append({
            "Transaction ID": f"TXN_{i:05d}",
            "Topup Date": "2026-06-17",
            "Store Code": f"STR_{100 + (i % 20)}",
            "Agent_name": f"Agent {i % 10}",
            "Unique_ID": f"EBO_{i:05d}",
            "Transaction Mode": "QR" if i % 2 == 0 else "UPI",
            "Status": "Authorised",
            "Amount": 1000.00 if i > 2 else (25000.00 if i == 1 else 1.00),
            "Settled_Amount": 1000.00 if i > 2 else (25000.00 if i == 1 else 1.00),
            "CRTD_DATE": "2026-06-17 10:00:00",
            "ATHRSD_DATE": "2026-06-17 10:01:00",
            "Remarks": "Topup processed"
        })

    df_ebo_full = pd.DataFrame(rows)
    buf = io.BytesIO()
    df_ebo_full.to_excel(buf, index=False)
    ebo_bytes = buf.getvalue()

    session_id = "test_ebo_topup_full_flow"
    conversation_context_manager.clear_state(session_id)

    # STEP 1: Upload EBO TB Topup_export_20260617_160221.xlsx
    upload_res = client.post(
        "/api/company/upload",
        files={"file": ("EBO TB Topup_export_20260617_160221.xlsx", ebo_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"session_id": session_id}
    )
    assert upload_res.status_code == 200
    uploaded_doc_id = upload_res.json()["doc_id"]

    # STEP 2a: Typo tolerance check "can u give me the full sumarry of the docuemt"
    r_typo = client.post("/api/company/chat", json={
        "message": "can u give me the full sumarry of the docuemt",
        "session_id": session_id,
        "user_role": "EMPLOYEE"
    })
    assert r_typo.status_code == 200
    assert "NoneType" not in r_typo.json()["answer"]
    assert "1,419" in r_typo.json()["answer"] or "Summary" in r_typo.json()["answer"] or "authorised" in r_typo.json()["answer"].lower()

    # STEP 2b: "give me the full summary of the document"
    r_sum = client.post("/api/company/chat", json={
        "message": "give me the full summary of the document",
        "session_id": session_id,
        "user_role": "EMPLOYEE"
    })
    assert r_sum.status_code == 200
    data_sum = r_sum.json()
    assert data_sum["intent"] == "excel_summary"
    assert "1,419" in data_sum["answer"]

    # STEP 3: "can u tell how many transaction id are there" / "how many transaction ids are there"
    r_cnt = client.post("/api/company/chat", json={
        "message": "can u tell how many transaction id are there",
        "session_id": session_id,
        "user_role": "EMPLOYEE"
    })
    assert r_cnt.status_code == 200
    data_cnt = r_cnt.json()
    assert data_cnt["intent"] == "excel_count"
    assert "1,419" in data_cnt["answer"]
    assert "NoneType" not in data_cnt["answer"]

    # STEP 4: "give me the transaction id column as excel"
    r_col = client.post("/api/company/chat", json={
        "message": "give me the transaction id column as excel",
        "session_id": session_id,
        "user_role": "EMPLOYEE"
    })
    assert r_col.status_code == 200
    data_col = r_col.json()
    assert data_col["intent"] == "excel_column_export"
    assert len(data_col.get("files", [])) > 0
    assert data_col["tool_results"]["record_count"] == 1419

    # STEP 5: "give me the full topup history as excel"
    r_full = client.post("/api/company/chat", json={
        "message": "give me the full topup history as excel",
        "session_id": session_id,
        "user_role": "EMPLOYEE"
    })
    assert r_full.status_code == 200
    data_full = r_full.json()
    assert data_full["intent"] == "excel_full_export"
    assert len(data_full.get("files", [])) > 0
    generated_file_id = data_full["files"][0]["file_id"]
    assert data_full["tool_results"]["record_count"] == 1419
    assert data_full["tool_results"]["column_count"] >= 10

    # STEP 6: Unknown column "export xyzabc column" -> NO empty file, clear helpful message
    r_bad_col = client.post("/api/company/chat", json={
        "message": "export xyzabc column",
        "session_id": session_id,
        "user_role": "EMPLOYEE"
    })
    assert r_bad_col.status_code == 200
    data_bad = r_bad_col.json()
    assert len(data_bad.get("files", [])) == 0  # Zero empty workbooks
    assert "couldn't identify" in data_bad["answer"].lower() or "available columns" in data_bad["answer"].lower()

    # STEP 7: "what happened" contextual inquiry
    r_wh = client.post("/api/company/chat", json={
        "message": "what happened",
        "session_id": session_id,
        "user_role": "EMPLOYEE"
    })
    assert r_wh.status_code == 200
    data_wh = r_wh.json()
    assert data_wh["intent"] == "what_happened"
    assert "EBO TB Topup_export" in data_wh["answer"] or "active" in data_wh["answer"].lower()

    # STEP 8: Verify Preview API endpoint GET /api/company/files/{file_id}/preview
    preview_res = client.get(f"/api/company/files/{generated_file_id}/preview")
    assert preview_res.status_code == 200
    preview_json = preview_res.json()
    assert preview_json["file_id"] == generated_file_id
    assert preview_json["row_count"] == 1419
    assert len(preview_json["preview_rows"]) > 0
    assert "Transaction ID" in preview_json["columns"]
    assert preview_json["preview_rows"][0]["Transaction ID"] == "TXN_00001"


def test_exact_latest_excel_conversation_and_context(client):
    """Verifies all 10 specific bug fixes requested:
    - Headings / Columns intent
    - Highest transaction (EXCEL_MAX with row details)
    - Total amount -> contextual 'give me as excel' (EXCEL_EXPORT_RESULT)
    - Full export
    - Contextual 'what happened'
    """
    rows = []
    for i in range(1, 1420):
        rows.append({
            "Transaction ID": f"TXN_{i:05d}",
            "Topup Date": "2026-06-17",
            "Store Code": f"STR_{100 + (i % 20)}",
            "Agent_name": f"Agent {i % 10}",
            "Unique_ID": f"EBO_{i:05d}",
            "Transaction Mode": "QR" if i % 2 == 0 else "UPI",
            "Status": "Authorised",
            "Amount": 1000.00 if i > 2 else (25000.00 if i == 1 else 1.00),
            "Settled_Amount": 1000.00 if i > 2 else (25000.00 if i == 1 else 1.00),
            "CRTD_DATE": "2026-06-17 10:00:00",
            "ATHRSD_DATE": "2026-06-17 10:01:00",
            "Remarks": "Topup processed"
        })

    df_ebo_full = pd.DataFrame(rows)
    buf = io.BytesIO()
    df_ebo_full.to_excel(buf, index=False)
    ebo_bytes = buf.getvalue()

    session_id = "test_latest_excel_conversation_context"
    conversation_context_manager.clear_state(session_id)

    # 1. Upload workbook
    upload_res = client.post(
        "/api/company/upload",
        files={"file": ("EBO TB Topup_export_20260617_160221.xlsx", ebo_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"session_id": session_id}
    )
    assert upload_res.status_code == 200

    # 2. "give me the full summary of this document" -> EXCEL_SUMMARY
    r_sum = client.post("/api/company/chat", json={
        "message": "give me the full summary of this document",
        "session_id": session_id,
        "user_role": "EMPLOYEE"
    })
    assert r_sum.status_code == 200
    assert r_sum.json()["intent"] == "excel_summary"
    assert "1,419" in r_sum.json()["answer"]

    # 3. "give me the headings of the excel" -> EXCEL_COLUMNS (excel_column_list)
    r_hd = client.post("/api/company/chat", json={
        "message": "give me the headings of the excel",
        "session_id": session_id,
        "user_role": "EMPLOYEE"
    })
    assert r_hd.status_code == 200
    assert r_hd.json()["intent"] == "excel_column_list"
    assert "Transaction ID" in r_hd.json()["answer"]
    assert "Amount" in r_hd.json()["answer"]

    # 4. "which is the highest transaction in the excel" -> EXCEL_MAX
    r_max1 = client.post("/api/company/chat", json={
        "message": "which is the highest transaction in the excel",
        "session_id": session_id,
        "user_role": "EMPLOYEE"
    })
    assert r_max1.status_code == 200
    assert r_max1.json()["intent"] == "excel_max"
    assert "25,000.00" in r_max1.json()["answer"]
    assert "TXN_00001" in r_max1.json()["answer"] or "TXN_00001" in str(r_max1.json().get("tool_results", {}))

    # 5. "what is the highest transaction in the excel" -> EXCEL_MAX
    r_max2 = client.post("/api/company/chat", json={
        "message": "what is the highest transaction in the excel",
        "session_id": session_id,
        "user_role": "EMPLOYEE"
    })
    assert r_max2.status_code == 200
    assert r_max2.json()["intent"] == "excel_max"
    assert "25,000.00" in r_max2.json()["answer"]

    # 6. "can u give me the biggest amount" -> EXCEL_MAX
    r_max3 = client.post("/api/company/chat", json={
        "message": "can u give me the biggest amount",
        "session_id": session_id,
        "user_role": "EMPLOYEE"
    })
    assert r_max3.status_code == 200
    assert r_max3.json()["intent"] == "excel_max"
    assert "25,000.00" in r_max3.json()["answer"]

    # 7. "give me the excel for the total amount" -> EXCEL_TOTAL
    r_tot = client.post("/api/company/chat", json={
        "message": "give me the excel for the total amount",
        "session_id": session_id,
        "user_role": "EMPLOYEE"
    })
    assert r_tot.status_code == 200
    assert r_tot.json()["intent"] == "excel_total"
    assert "25,12,180.76" in r_tot.json()["answer"] or "14,17,001.00" in r_tot.json()["answer"] or "Total Amount" in r_tot.json()["answer"]

    # 8. "give me as excel" -> EXCEL_EXPORT_RESULT (must export the previous total result)
    r_exp = client.post("/api/company/chat", json={
        "message": "give me as excel",
        "session_id": session_id,
        "user_role": "EMPLOYEE"
    })
    assert r_exp.status_code == 200
    data_exp = r_exp.json()
    assert data_exp["intent"] == "excel_export_result"
    assert len(data_exp.get("files", [])) > 0
    exported_file_id = data_exp["files"][0]["file_id"]

    # Verify preview of exported result
    preview_exp = client.get(f"/api/company/files/{exported_file_id}/preview")
    assert preview_exp.status_code == 200
    assert len(preview_exp.json()["preview_rows"]) > 0
    assert "Metric / Dimension" in preview_exp.json()["columns"]

    # 9. "give me the full topup history as excel" -> EXCEL_FULL_EXPORT
    r_full = client.post("/api/company/chat", json={
        "message": "give me the full topup history as excel",
        "session_id": session_id,
        "user_role": "EMPLOYEE"
    })
    assert r_full.status_code == 200
    assert r_full.json()["intent"] == "excel_full_export"
    assert len(r_full.json().get("files", [])) > 0

    # 10. "what happened" -> contextual explanation
    r_wh = client.post("/api/company/chat", json={
        "message": "what happened",
        "session_id": session_id,
        "user_role": "EMPLOYEE"
    })
    assert r_wh.status_code == 200
    assert r_wh.json()["intent"] == "what_happened"

