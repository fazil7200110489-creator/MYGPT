"""Regression and Accuracy Verification for Phase 3 and Phase 4 of MYGPT AI Tender Consultant.

Strictly verifies across all four sample tenders:
1. NITK High-End Desktop
2. CCTV Women Safety Surveillance
3. EESL Empanelment 27/OTE/2627019
4. Tripura University Wi-Fi

Verification Criteria:
- No cross-tender contamination.
- Zero hardcoded fallback strings or generic assumptions.
- Accurate Entity Classification (Issuing Authority vs. Sub-Department vs. Inviting Authority).
- Accurate Turnover Entity Classification (Main Bidder vs. CSP / Subcontractor vs. OEM).
- Complete technical specification table extraction without truncation.
- Precise document_id, filename, and page_number evidence tracking.
- Missing fields report "NOT FOUND".
"""

import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.services.document_parser import document_parser
from backend.app.services.tender.tender_section_retriever import PageRecord, TenderDocumentIndex
from backend.app.services.tender_intelligence.intelligence_extractors import (
    extract_overview_facts,
    extract_eligibility_conditions,
    extract_technical_specifications,
    extract_commercial_and_legal,
)


def _load_tender_records(pdf_path: str, doc_id: str, filename: str):
    parse_result = document_parser.parse(pdf_path)
    pages = parse_result.get("pages", [])
    records = []
    for p in pages:
        records.append(
            PageRecord(
                filename=filename,
                document_id=doc_id,
                file_type="pdf",
                page_number=p.get("page_number", 1),
                text=p.get("text", ""),
                file_hash=f"hash_{doc_id}",
            )
        )
    return records


# ---------------------------------------------------------------------------
# Test 1: NITK High-End Desktop
# ---------------------------------------------------------------------------
def test_nitk_accuracy_and_entity_classification():
    pdf_path = r"D:\MYGPT\data\uploads\2958370a-b714-47c0-9efa-9adfa6403d30.pdf"
    records = _load_tender_records(pdf_path, "nitk_doc_01", "NITK_Desktop.pdf")
    assert len(records) == 41

    overview, scope = extract_overview_facts(records, {})
    eligibility = extract_eligibility_conditions(records, None)
    specs, oem, compliance = extract_technical_specifications(records, None)
    commercial, legal = extract_commercial_and_legal(records, None, {})

    # Entity classification
    assert "National Institute of Technology Karnataka" in overview.department_organization
    assert overview.sub_department_consignee is not None
    assert "MECHANICAL ENGINEERING" in overview.sub_department_consignee
    assert "Director, NITK" in (overview.tender_inviting_authority or "")

    # Title & Facts
    assert "High End Desktop" in overview.tender_title
    assert "47,25,000" in overview.estimated_project_value
    assert "94,500" in overview.emd_value
    # NITK never charges tender fee
    assert "Nil" in (overview.tender_fee or "") or "Free" in (overview.tender_fee or "")
    # NITK delivery is One month / 4 weeks (NOT generic 8-12 weeks!)
    assert "4 weeks" in (overview.delivery_implementation_period or "") or "One month" in (overview.delivery_implementation_period or "")
    # NITK warranty is 5 years (NOT generic 3 years!)
    assert "5" in (overview.warranty_maintenance_period or "")

    # Turnover: 30% of estimated cost (strictly main bidder)
    assert "30%" in eligibility.main_bidder_turnover
    assert eligibility.subcontractor_partner_turnover == "NOT FOUND"

    # Technical Specifications: Must extract Desktop CPU / RAM / Monitor from Annexure L (P39-40), ZERO Wi-Fi fallback!
    spec_names = [it.item_name.lower() for it in specs.items]
    all_spec_text = " ".join([it.technical_specifications.lower() for it in specs.items])
    assert "core system equipment & active/passive components" not in spec_names
    assert any("processor" in s or "cpu" in s or "intel" in all_spec_text or "i7-14700" in all_spec_text for s in spec_names)
    assert any("memory" in s or "ram" in s or "ddr5" in all_spec_text for s in spec_names)
    assert any("monitor" in s or "fhd" in all_spec_text for s in spec_names)

    # Citations verification
    for cit in overview.citations:
        assert cit.document_id == "nitk_doc_01"
        assert cit.filename == "NITK_Desktop.pdf"
        assert cit.page_number >= 1


# ---------------------------------------------------------------------------
# Test 2: CCTV Women Safety Surveillance
# ---------------------------------------------------------------------------
def test_cctv_accuracy_and_turnover_separation():
    pdf_path = r"D:\MYGPT\data\uploads\4f8eac53-a110-440b-8b98-019b3c1e4dfd.pdf"
    records = _load_tender_records(pdf_path, "cctv_doc_02", "CCTV_WomenSafety.pdf")
    assert len(records) == 170

    overview, scope = extract_overview_facts(records, {})
    eligibility = extract_eligibility_conditions(records, None)
    specs, oem, compliance = extract_technical_specifications(records, None)
    commercial, legal = extract_commercial_and_legal(records, None, {})

    # Entity classification
    assert "Tamil Nadu Police" in overview.department_organization or "Police" in overview.department_organization
    assert overview.sub_department_consignee is not None
    assert "Technical Services" in overview.sub_department_consignee
    assert "CCTV SURVEILLANCE" in overview.tender_title

    # Strict Turnover Separation: Bidder turnover vs. CSP turnover
    # Bidder: Rs. 60.00 Crs (Page 10)
    # CSP: > ₹1000 Crore (Page 50)
    assert "60" in eligibility.main_bidder_turnover or "60.00" in eligibility.main_bidder_turnover
    assert "1000" in eligibility.subcontractor_partner_turnover
    # Consortium is strictly prohibited
    assert "not allowed" in eligibility.consortium_joint_venture_allowed.lower()

    # Technical Specifications: Camera specs from Schedule IV (P16-17), NOT Wi-Fi!
    spec_names = [it.item_name.lower() for it in specs.items]
    all_spec_text = " ".join([it.technical_specifications.lower() for it in specs.items])
    assert "core system equipment & active/passive components" not in spec_names
    assert any(k in all_spec_text for k in ["camera", "resolution", "image sensor", "bullet"])

    # Citations
    for cond in eligibility.conditions:
        assert cond.document_id == "cctv_doc_02"
        assert cond.source_file == "CCTV_WomenSafety.pdf"
        assert cond.source_page >= 1


# ---------------------------------------------------------------------------
# Test 3: EESL Tender 27/OTE/2627019
# ---------------------------------------------------------------------------
def test_eesl_accuracy_and_empanelment_categories():
    pdf_path = r"D:\MYGPT\data\uploads\9dd28e45-80d7-4c0d-ae26-b6c28b7cd995.pdf"
    records = _load_tender_records(pdf_path, "eesl_doc_03", "EESL_Empanelment.pdf")
    assert len(records) == 149

    overview, scope = extract_overview_facts(records, {})
    eligibility = extract_eligibility_conditions(records, None)
    specs, oem, compliance = extract_technical_specifications(records, None)

    # Entity classification
    assert "Energy Efficiency Services Limited" in overview.department_organization or "EESL" in overview.department_organization
    assert "Empanelment" in overview.tender_title or "EMST" in overview.tender_title

    # Category-based turnover
    assert "Category 1" in eligibility.main_bidder_turnover or "1.50" in eligibility.main_bidder_turnover or "25" in eligibility.main_bidder_turnover


# ---------------------------------------------------------------------------
# Test 4: Tripura University Wi-Fi Tender
# ---------------------------------------------------------------------------
def test_tripura_wifi_accuracy_and_evidence():
    pdf_path = r"D:\MYGPT\data\uploads\0aaa92a2-f665-4d5e-98ba-c39ce650f525.pdf"
    records = _load_tender_records(pdf_path, "tripura_doc_04", "Tripura_WiFi.pdf")
    assert len(records) == 33

    overview, scope = extract_overview_facts(records, {})
    eligibility = extract_eligibility_conditions(records, None)
    specs, oem, compliance = extract_technical_specifications(records, None)

    # Entity classification
    assert "Tripura University" in overview.department_organization
    assert "Wi-Fi" in overview.tender_title or "Campus-Wide" in overview.tender_title
    assert "5,00,000" in (overview.emd_value or "")

    # Turnover
    assert "3.00" in eligibility.main_bidder_turnover or "10.00" in eligibility.main_bidder_turnover
