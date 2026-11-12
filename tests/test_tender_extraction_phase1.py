"""Phase 1 Tender Information Extraction & QA End-to-End Test Suite."""

import io
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import fitz
import pytest
from PIL import Image, ImageDraw, ImageFont
import docx
import openpyxl
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.main import app
from backend.app.schemas.company_ai import CompanyAIChatRequest
from backend.app.services.company_ai_service import company_ai_service
from backend.app.services.conversation_context_manager import conversation_context_manager
from backend.app.services.document_parser import document_parser
from backend.app.services.tender.tender_extractor import tender_extractor
from backend.app.services.tender.tender_schema import ALL_TENDER_FIELD_NAMES

REAL_TENDER_1 = ROOT_DIR / "data" / "uploads" / "44ab4ecc-f6a6-407d-829f-809c547be6c4.pdf"
REAL_TENDER_2 = ROOT_DIR / "data" / "uploads" / "6b8939a2-0379-44ba-8ab5-1fdf791d4da6.pdf"


def _render_lines_image(lines: List[str], width: int = 1200, height: int = 900) -> Image.Image:
    """Renders crisp black text onto a white image for realistic scanned OCR tests."""
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    font = None
    for font_candidate in (
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
    ):
        if os.path.exists(font_candidate):
            font = ImageFont.truetype(font_candidate, 24)
            break
    if font is None:
        font = ImageFont.load_default()

    y = 40
    for line in lines:
        draw.text((40, y), line, fill="black", font=font)
        y += 42
    return img


def _make_text_pdf_bytes(pages_lines: List[List[str]]) -> bytes:
    doc = fitz.open()
    for lines in pages_lines:
        page = doc.new_page(width=595, height=842)
        y = 50
        for ln in lines:
            page.insert_text((45, y), ln, fontsize=11)
            y += 20
    data = doc.tobytes()
    doc.close()
    return data


def _make_scanned_pdf_bytes(pages_lines: List[List[str]]) -> bytes:
    doc = fitz.open()
    for lines in pages_lines:
        img = _render_lines_image(lines)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        page = doc.new_page(width=612, height=792)
        page.insert_image(page.rect, stream=buf.getvalue())
    data = doc.tobytes()
    doc.close()
    return data


def test_real_tender_1_79_pages_complete_extraction():
    """Verify full 79-page Tendernotice_1 extraction without truncation or hallucinations."""
    if not REAL_TENDER_1.exists():
        pytest.skip("Tendernotice_1 PDF not present in data/uploads")

    parsed = document_parser.parse(str(REAL_TENDER_1))
    assert parsed["total_pages"] == 79
    doc = {
        "document_id": "t1_real",
        "filename": "Tendernotice_1 (1).pdf",
        "file_type": ".pdf",
        "pages": parsed["pages"],
        "extracted_text": parsed["text"],
        "total_pages": parsed["total_pages"],
    }
    res = tender_extractor.extract_from_documents([doc], nas_path=None, use_llm=False)
    flat = res.all_fields_flat()

    assert set(flat.keys()) == set(ALL_TENDER_FIELD_NAMES)
    assert len(flat) == 25
    assert flat["tender_id"].value == "WTL/WBPNB/CCTV/26-27/046"
    assert "WEBEL TECHNOLOGY LIMITED" in flat["department_organization"].value
    assert flat["state"].value == "West Bengal"
    assert flat["customer_phone"].value == "033-23673403-06"
    assert flat["tender_portal_url"].value == "https://wbtenders.gov.in"
    assert "16,00,000" in flat["bid_emd_value"].value
    assert flat["estimated_tender_value"].value == "NOT_FOUND"
    assert flat["nas_path"].value == "NOT_FOUND"
    assert "07-09-26" in flat["prebid_query_end"].value
    assert "08-09-2026" in flat["prebid_meeting_date"].value
    assert "15-09-2026" in flat["bid_submission_start"].value
    assert "22-09-2026" in flat["bid_submission_end"].value
    assert "24-09-2026" in flat["technical_bid_opening_date"].value
    # Same-date 2-digit vs 4-digit year must NOT trigger false ambiguity
    assert flat["bid_submission_end"].status == "VERIFIED"
    assert flat["technical_bid_opening_date"].status == "VERIFIED"


def test_real_tender_2_33_pages_no_hallucinated_estimated_value():
    """Verify 33-page Tendernotice_2 extraction and rejection of eligibility values as tender value."""
    if not REAL_TENDER_2.exists():
        pytest.skip("Tendernotice_2 PDF not present in data/uploads")

    parsed = document_parser.parse(str(REAL_TENDER_2))
    assert parsed["total_pages"] == 33
    doc = {
        "document_id": "t2_real",
        "filename": "Tendernotice_2 (5).pdf",
        "file_type": ".pdf",
        "pages": parsed["pages"],
        "extracted_text": parsed["text"],
        "total_pages": parsed["total_pages"],
    }
    res = tender_extractor.extract_from_documents([doc], nas_path=None, use_llm=False)
    flat = res.all_fields_flat()

    assert len(flat) == 25
    assert "No.F.TU/FIN/Wi-Fi/Vol-I/2025" in flat["tender_id"].value
    assert "TRIPURA UNIVERSITY" in flat["department_organization"].value
    assert flat["state"].value == "Tripura"
    assert "Wi-Fi Network" in flat["bid_title"].value
    assert flat["tender_portal_url"].value == "https://eprocure.gov.in/eprocure/app"
    # Page 8 mentions Rs. 45.00 Lakh (similar project requirement) & Rs. 10.00 Crore (turnover) -> NOT estimated tender value!
    assert flat["estimated_tender_value"].value == "NOT_FOUND"
    assert "5,00,000" in flat["bid_emd_value"].value
    assert flat["bid_emd_value"].source_page == 15
    assert "22-10-2026" in flat["tender_publication_date"].value
    assert "12-11-2026" in flat["prebid_meeting_date"].value
    assert "17-11-2026" in flat["bid_submission_end"].value
    assert "18-11-2026" in flat["technical_bid_opening_date"].value
    assert "19-11-2026" in flat["financial_bid_opening_date"].value
    assert flat["nas_path"].value == "NOT_FOUND"


def test_scanned_pdf_and_image_ocr_extraction(tmp_path: Path):
    """Verify local WinRT OCR handles image-only scanned PDFs & PNGs and preserves page numbers."""
    pdf_bytes = _make_scanned_pdf_bytes([
        [
            "GOVERNMENT OF KARNATAKA",
            "NOTICE INVITING e-TENDER",
            "Tender ID: KSP/SCAN/2026/101",
            "Name of Work: Supply of Forensic Lab Workstations",
            "Department: Karnataka State Police",
            "Tender Portal URL: https://eproc.karnataka.gov.in",
        ],
        [
            "SCHEDULE OF IMPORTANT DATES & EMD",
            "Estimated Tender Value: INR 25000000",
            "Earnest Money Deposit: INR 500000",
            "Tender Publication Date: 02-11-2026",
            "Bid Submission End: 25-11-2026 at 5 PM",
            "Technical Bid Opening Date: 27-11-2026 at 11 AM",
        ],
    ])
    pdf_path = tmp_path / "scanned_tender.pdf"
    pdf_path.write_bytes(pdf_bytes)

    parsed = document_parser.parse(str(pdf_path))
    assert parsed["total_pages"] == 2
    assert parsed["ocr_pages"] == [1, 2]

    doc = {
        "document_id": "scan1",
        "filename": "scanned_tender.pdf",
        "file_type": ".pdf",
        "pages": parsed["pages"],
        "extracted_text": parsed["text"],
        "total_pages": parsed["total_pages"],
    }
    res = tender_extractor.extract_from_documents([doc], use_llm=False)
    flat = res.all_fields_flat()
    assert "KSP/SCAN/2026/101" in flat["tender_id"].value
    assert flat["state"].value == "Karnataka"
    assert "500000" in flat["bid_emd_value"].value
    assert "25000000" in flat["estimated_tender_value"].value
    assert flat["bid_emd_value"].source_page == 2
    assert "25-11-2026" in flat["bid_submission_end"].value

    # Readable PNG tender image must also OCR and extract fields cleanly
    img_tender = _render_lines_image([
        "GOVERNMENT OF KERALA",
        "Tender ID: KEL/IMG/2026/404",
        "Name of Work: Supply of Network Switches",
        "Earnest Money Deposit: INR 250000",
        "Bid Submission End: 18-12-2026",
    ])
    img_tender_path = tmp_path / "tender_notice.png"
    img_tender.save(img_tender_path)
    img_tender_parsed = document_parser.parse(str(img_tender_path))
    assert img_tender_parsed["ocr_pages"] == [1]
    res_img = tender_extractor.extract_from_documents([{
        "document_id": "img1",
        "filename": "tender_notice.png",
        "file_type": ".png",
        "pages": img_tender_parsed["pages"],
        "extracted_text": img_tender_parsed["text"],
        "total_pages": img_tender_parsed["total_pages"],
    }], use_llm=False)
    flat_img = res_img.all_fields_flat()
    assert "KEL/IMG/2026/404" in flat_img["tender_id"].value
    assert "250000" in flat_img["bid_emd_value"].value

    # Blank unreadable image must report unreadable diagnostic instead of fake dummy text
    blank = Image.new("RGB", (400, 200), "white")
    blank_path = tmp_path / "blank_invoice.png"
    blank.save(blank_path)
    img_parsed = document_parser.parse(str(blank_path))
    assert img_parsed["unreadable_pages"] == [1]
    assert "Mohamed Fazil" not in img_parsed["text"]


def test_mixed_scanned_and_text_pdf(tmp_path: Path):
    """Verify mixed PDF OCRs only scanned page(s) while preserving native text pages."""
    doc = fitz.open()
    p1 = doc.new_page(width=595, height=842)
    p1.insert_text((45, 60), "NOTICE INVITING TENDER\nTender ID: MIX/2026/009\nDepartment: Smart City Mission Ltd\nState: Gujarat", fontsize=12)

    img = _render_lines_image([
        "FINANCIAL AND CRITICAL DATES SCHEDULE",
        "Estimated Tender Value: INR 8000000",
        "Earnest Money Deposit: INR 160000",
        "Bid Submission End: 30-11-2026",
        "Technical Bid Opening Date: 02-12-2026",
    ])
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    p2 = doc.new_page(width=612, height=792)
    p2.insert_image(p2.rect, stream=buf.getvalue())

    mixed_path = tmp_path / "mixed_tender.pdf"
    doc.save(str(mixed_path))
    doc.close()

    parsed = document_parser.parse(str(mixed_path))
    assert parsed["total_pages"] == 2
    assert parsed["ocr_pages"] == [2]

    doc_rec = {
        "document_id": "mix1",
        "filename": "mixed_tender.pdf",
        "file_type": ".pdf",
        "pages": parsed["pages"],
        "extracted_text": parsed["text"],
        "total_pages": parsed["total_pages"],
    }
    res = tender_extractor.extract_from_documents([doc_rec], use_llm=False)
    flat = res.all_fields_flat()
    assert flat["tender_id"].value == "MIX/2026/009"
    assert flat["state"].value == "Gujarat"
    assert "160000" in flat["bid_emd_value"].value
    assert flat["bid_emd_value"].source_page == 2


def test_docx_and_xlsx_tender_extraction_with_headers_and_sheets(tmp_path: Path):
    """Verify DOCX header/table extraction & XLSX multi-sheet dynamic header extraction."""
    d = docx.Document()
    d.sections[0].header.paragraphs[0].text = "Maharashtra State IT Corporation Ltd"
    d.add_paragraph("NOTICE INVITING TENDER")
    tbl = d.add_table(rows=6, cols=2)
    rows = [
        ("Tender ID", "MHIT/2026/DOCX-77"),
        ("Name of Work", "Cloud Disaster Recovery & Managed Security Services"),
        ("Estimated Tender Value", "Rs. 4,50,00,000"),
        ("Earnest Money Deposit", "Rs. 9,00,000"),
        ("Bid Submission End", "14-12-2026 at 4 PM"),
        ("Financial Bid Opening Date", "21-12-2026 at 11 AM"),
    ]
    for r_idx, (k, v) in enumerate(rows):
        tbl.rows[r_idx].cells[0].text = k
        tbl.rows[r_idx].cells[1].text = v
    docx_path = tmp_path / "tender_notice.docx"
    d.save(docx_path)

    parsed_docx = document_parser.parse(str(docx_path))
    res_docx = tender_extractor.extract_from_documents([{
        "document_id": "d1",
        "filename": "tender_notice.docx",
        "file_type": ".docx",
        "pages": parsed_docx["pages"],
        "extracted_text": parsed_docx["text"],
        "total_pages": parsed_docx["total_pages"],
    }], nas_path=r"\\nas\tenders\MHIT_2026", use_llm=False)
    flat_docx = res_docx.all_fields_flat()
    assert flat_docx["tender_id"].value == "MHIT/2026/DOCX-77"
    assert "Maharashtra" in flat_docx["department_organization"].value
    assert "9,00,000" in flat_docx["bid_emd_value"].value
    assert flat_docx["nas_path"].value == r"\\nas\tenders\MHIT_2026"

    # XLSX multi-sheet with banner rows above real column headers
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "Tender_Summary"
    ws1.append(["GOVERNMENT TENDER SCHEDULE"])
    ws1.append(["Field", "Details"])
    ws1.append(["Tender ID", "XLSX/BOQ/2026/12"])
    ws1.append(["Department", "Tamil Nadu E-Governance Agency"])
    ws1.append(["Earnest Money Deposit", "Rs. 2,50,000"])
    ws2 = wb.create_sheet("BOQ_Financial")
    ws2.append(["Bill of Quantities - Server Hardware"])
    ws2.append(["S.No", "Item", "Qty", "Estimated Cost"])
    ws2.append([1, "Rack Server", 10, "Rs. 1,25,00,000"])
    xlsx_path = tmp_path / "tender_boq.xlsx"
    wb.save(xlsx_path)

    parsed_xlsx = document_parser.parse(str(xlsx_path))
    assert parsed_xlsx["sheets"] == ["Tender_Summary", "BOQ_Financial"]
    res_xlsx = tender_extractor.extract_from_documents([{
        "document_id": "x1",
        "filename": "tender_boq.xlsx",
        "file_type": ".xlsx",
        "pages": parsed_xlsx["pages"],
        "extracted_text": parsed_xlsx["text"],
        "total_pages": parsed_xlsx["total_pages"],
    }], use_llm=False)
    flat_xlsx = res_xlsx.all_fields_flat()
    assert flat_xlsx["tender_id"].value == "XLSX/BOQ/2026/12"
    assert "2,50,000" in flat_xlsx["bid_emd_value"].value
    assert flat_xlsx["bid_emd_value"].source_sheet == "Tender_Summary"
    assert "1,25,00,000" in flat_xlsx["estimated_tender_value"].value
    assert flat_xlsx["estimated_tender_value"].source_sheet == "BOQ_Financial"


def test_legacy_doc_xls_honest_rejection(tmp_path: Path):
    """Legacy .doc / .xls without converter/xlrd must raise explicit errors, not parse binary garbage."""
    fake_doc = tmp_path / "legacy_tender.doc"
    fake_doc.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1LegacyBinaryDOC")
    with pytest.raises(ValueError, match=r"\.doc"):
        document_parser.parse(str(fake_doc))

    fake_xls = tmp_path / "legacy_boq.xls"
    fake_xls.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1LegacyBinaryXLS")
    with pytest.raises(ValueError, match=r"\.xls"):
        document_parser.parse(str(fake_xls))


def test_multifile_bundle_and_corrigendum_conflict(tmp_path: Path):
    """Verify multi-file NIT + BOQ XLSX + Corrigendum bundle & conflict provenance tracking."""
    main_pdf = _make_text_pdf_bytes([[
        "NOTICE INVITING TENDER",
        "Department: State Power Utility",
        "State: Odisha",
        "Tender ID: ODISHA/PWR/2026/44",
        "Name of Work: Substation Automation System",
        "Earnest Money Deposit: Rs. 10,00,000",
        "Bid Submission End: 10-12-2026 at 3 PM",
    ]])
    corr_pdf = _make_text_pdf_bytes([[
        "CORRIGENDUM - 1",
        "Reference Tender ID: ODISHA/PWR/2026/44",
        "Revised Corrigendum Bid Submission End Date: 20-12-2026 at 5 PM",
        "Earnest Money Deposit: Rs. 12,00,000",
    ]])

    p_main = tmp_path / "Main_NIT.pdf"
    p_corr = tmp_path / "Corrigendum_1.pdf"
    p_main.write_bytes(main_pdf)
    p_corr.write_bytes(corr_pdf)

    docs = []
    for did, p in [("m1", p_main), ("c1", p_corr)]:
        parsed = document_parser.parse(str(p))
        docs.append({
            "document_id": did,
            "filename": p.name,
            "file_type": ".pdf",
            "pages": parsed["pages"],
            "extracted_text": parsed["text"],
            "total_pages": parsed["total_pages"],
        })

    res = tender_extractor.extract_from_documents(docs, use_llm=False)
    flat = res.all_fields_flat()
    assert "20-12-2026" in flat["bid_submission_end"].value
    assert flat["bid_submission_end"].source_file == "Corrigendum_1.pdf"
    assert len(flat["bid_submission_end"].alternatives) >= 1
    assert "10-12-2026" in flat["bid_submission_end"].alternatives[0].value
    assert "12,00,000" in flat["bid_emd_value"].value
    assert len(flat["bid_emd_value"].alternatives) >= 1
    assert res.fields_ambiguous_count >= 2


def test_e2e_api_upload_auto_extraction_followup_and_isolation():
    """Verify /upload -> auto extraction via Gemma 4 -> tender QA -> unrelated query isolation."""
    client = TestClient(app)
    session_id = "test_tender_e2e_session"
    conversation_context_manager.clear_state(session_id)

    sample_pdf = _make_text_pdf_bytes([
        [
            "ABC INFRASTRUCTURE AUTHORITY",
            "NOTICE INVITING e-TENDER",
            "Tender ID: AIA/IT/2026/888",
            "Name of Work: Supply and Installation of Campus Fiber Network",
            "State: Kerala",
            "Tender Portal URL: https://etenders.kerala.gov.in",
        ],
        [
            "Section 2: Financial & Dates Schedule",
            "Earnest Money Deposit: Rs. 3,50,000",
            "Bid Submission Start: 05-11-2026 at 10 AM",
            "Bid Submission End: 28-11-2026 at 4 PM",
            "Technical Bid Opening Date: 30-11-2026 at 11 AM",
            "Section 4 Eligibility Criteria: Minimum 5 years IT networking experience and Rs. 2.00 Crore turnover.",
        ],
    ])

    up_resp = client.post(
        "/api/company/upload",
        data={"session_id": session_id, "user_role": "EMPLOYEE", "user_id": "test_user"},
        files={"file": ("tender_fiber_network.pdf", sample_pdf, "application/pdf")},
    )
    assert up_resp.status_code == 200
    up_data = up_resp.json()
    assert up_data["document_type"] == "TENDER"
    doc_id = up_data["doc_id"]

    # 1. Automatic extraction triggered by upload announcement
    chat_res = company_ai_service.process_chat(
        CompanyAIChatRequest(
            message="Uploaded tender_fiber_network.pdf",
            conversation_id=session_id,
            document_id=doc_id,
        )
    )
    assert chat_res.answer_type == "tender_extraction"
    te = (chat_res.structured_data or {}).get("tender_extraction")
    assert te is not None
    assert te["basic_information"]["tender_id"]["value"] == "AIA/IT/2026/888"
    assert "3,50,000" in te["financial_information"]["bid_emd_value"]["value"]
    # Estimated value wasn't provided -> MUST remain NOT_FOUND even after Gemma 4 run!
    assert te["financial_information"]["estimated_tender_value"]["value"] == "NOT_FOUND"
    assert te["additional_information"]["nas_path"]["value"] == "NOT_FOUND"
    assert chat_res.capability == "DOCUMENT"

    # 2. Follow-up QA (EMD, Deadline, Eligibility) — must NOT route to HR/candidate!
    emd_res = company_ai_service.process_chat(
        CompanyAIChatRequest(
            message="What is the EMD?",
            conversation_id=session_id,
            document_id=doc_id,
        )
    )
    assert emd_res.capability == "DOCUMENT"
    assert "3,50,000" in emd_res.answer

    elig_res = company_ai_service.process_chat(
        CompanyAIChatRequest(
            message="What are the eligibility criteria and Section 4 requirements?",
            conversation_id=session_id,
            document_id=doc_id,
        )
    )
    assert elig_res.capability == "DOCUMENT"
    assert "HR" not in elig_res.intent.upper()
    assert "2.00 Crore" in elig_res.answer or "5 years" in elig_res.answer

    # 3. Unrelated question with active document_id sent by UI MUST isolate cleanly!
    gen_res = company_ai_service.process_chat(
        CompanyAIChatRequest(
            message="What is the capital of France?",
            conversation_id=session_id,
            document_id=doc_id,
        )
    )
    assert gen_res.capability == "GENERAL"
    assert "paris" in gen_res.answer.lower()
    assert "AIA/IT/2026/888" not in gen_res.answer
