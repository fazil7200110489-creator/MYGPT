import os
import pytest
from backend.app.services.tender_intelligence.intelligence_retriever import intelligence_retriever
from backend.app.services.tender_intelligence.intelligence_extractors import (
    extract_overview_facts,
    extract_eligibility_conditions,
    extract_commercial_and_legal,
    extract_technical_specifications,
)

PDF_PATH = "data/uploads/1a5fa635-e77b-4d14-85b9-64b0878e8549.pdf"

@pytest.fixture(scope="module")
def wtl_data():
    if not os.path.exists(PDF_PATH):
        pytest.skip(f"WTL tender PDF not found at {PDF_PATH}")
    
    doc_info = {
        "document_id": "wtl_cctv_01",
        "id": "wtl_cctv_01",
        "filename": "1a5fa635-e77b-4d14-85b9-64b0878e8549.pdf",
        "path": PDF_PATH,
    }
    index, records, enriched = intelligence_retriever.prepare_index([doc_info])
    anchors = {
        "estimated_value": "Not specified",
        "emd_value": "Rs. 5,00,000/-",
        "submission_deadline": "17-11-2026",
        "title": "ANPR CCTV",
    }
    overview, scope = extract_overview_facts(records, anchors)
    eligibility = extract_eligibility_conditions(records, index)
    commercial, legal = extract_commercial_and_legal(records, index, anchors)
    spec, oem, compliance = extract_technical_specifications(records, index)
    
    return {
        "index": index,
        "records": records,
        "overview": overview,
        "scope": scope,
        "eligibility": eligibility,
        "commercial": commercial,
        "legal": legal,
        "spec": spec,
        "oem": oem,
        "compliance": compliance,
    }


def test_wtl_authorities_and_entities(wtl_data):
    ov = wtl_data["overview"]
    # 1. Issuing / Execution Authority
    assert "webel technology limited" in ov.department_organization.lower()
    assert "Date" not in ov.department_organization
    assert "Section" not in ov.department_organization
    # 2. Tender Inviting Authority
    assert "webel technology limited" in ov.tender_inviting_authority.lower()
    # 3. Execution Authority / Sub-department
    assert "webel technology limited" in ov.sub_department_consignee.lower()
    # 4. End User / Beneficiary
    assert "Inspector General of Police" in ov.end_user_beneficiary
    assert "North Bengal" in ov.end_user_beneficiary


def test_wtl_similar_work_experience_multi_tier(wtl_data):
    el = wtl_data["eligibility"]
    exp = el.similar_work_experience
    # Must preserve the 3 distinct financial tiers with OR logic
    assert "6.40" in exp
    assert "4.00" in exp
    assert "3.20" in exp
    assert " OR " in exp or "\nOR" in exp or " OR\n" in exp
    # Turnover
    assert "12.00" in el.main_bidder_turnover


def test_wtl_payment_terms_and_advance(wtl_data):
    comm = wtl_data["commercial"]
    # Back to back
    assert "back-to-back" in comm.payment_terms.lower()
    # 25% advance
    assert "25%" in comm.payment_terms
    assert "Mobilization Advance" in comm.payment_terms
    assert "25%" in comm.advance_payment_allowed
    # 60% on delivery for ANPR & CCTV
    assert "60%" in comm.payment_terms
    # 75% for BWC & Night Vision
    assert "75%" in comm.payment_terms
    # 15% on commissioning
    assert "15%" in comm.payment_terms


def test_wtl_product_specific_warranty(wtl_data):
    ov = wtl_data["overview"]
    warr = ov.warranty_maintenance_period
    # ANPR & CCTV: 3 Years
    assert "3 Years" in warr
    assert "ANPR & CCTV" in warr
    # Body Worn Camera: 1 Year
    assert "1 Year" in warr
    assert "Body Worn Camera" in warr
    assert "Night Vision" in warr


def test_wtl_delivery_implementation_timelines(wtl_data):
    ov = wtl_data["overview"]
    deliv = ov.delivery_implementation_period
    assert "60 days" in deliv
    assert "90 days" in deliv
    assert "180 Days" in deliv


def test_wtl_pbg_and_liquidated_damages(wtl_data):
    comm = wtl_data["commercial"]
    # PBG: 10%, 3 weeks, 6 months beyond warranty
    assert "10%" in comm.performance_bank_guarantee_pbg
    assert "3 weeks" in comm.performance_bank_guarantee_pbg.lower() or "three weeks" in comm.performance_bank_guarantee_pbg.lower()
    assert "6 month" in comm.performance_bank_guarantee_pbg.lower() or "six month" in comm.performance_bank_guarantee_pbg.lower()
    # LD: 0.5% per 7 days, max 5% SLA cap, 6-month continuous failure
    ld = comm.penalties_and_liquidated_damages
    assert "0.5%" in ld
    assert "7 days" in ld
    assert "5%" in ld
    assert "6 continuous months" in ld or "continuous" in ld


def test_wtl_boq_and_technical_extraction(wtl_data):
    spec = wtl_data["spec"]
    items = spec.items
    assert len(items) >= 34
    
    # Filter for Total BOQ items (Section I Pages 37-38)
    boq_items = [it for it in items if it.source_page in (37, 38)]
    assert len(boq_items) == 34, f"Expected 34 BOQ items from Pages 37-38, got {len(boq_items)}"
    
    # Item 1: 4MP Bullet Camera (617 PCS)
    item1 = boq_items[0]
    assert "bullet" in item1.item_name.lower() or "camera" in item1.item_name.lower()
    assert "617" in (item1.required_quantity or "")
    
    # Item 4: ANPR Camera (128 PCS)
    item4 = next((it for it in boq_items if "anpr" in it.item_name.lower()), None)
    assert item4 is not None
    assert "128" in (item4.required_quantity or "")
    
    # Item 33: Body Worn Camera (493 PCS)
    bwc = next((it for it in boq_items if "body worn" in it.item_name.lower()), None)
    assert bwc is not None
    assert "493" in (bwc.required_quantity or "")
    
    # Item 34: Night Vision Binoculars (44 PCS)
    nv = next((it for it in boq_items if "binocular" in it.item_name.lower() or "night vision" in it.item_name.lower()), None)
    assert nv is not None
    assert "44" in (nv.required_quantity or "")
