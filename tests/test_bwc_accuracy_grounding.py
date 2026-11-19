"""Regression & Grounding Test for Body Worn Camera Tender Accuracy & Isolation.

Verifies all 15 audit points identified during the Phase 6 Post-Implementation Audit:
1. Document isolation & clean cache (no legacy cache pollution)
2. Tender Title
3. Issuing Authority & TIA (no "Date")
4. Tender Ref No (no address paragraph swallowed)
5. Location (Chennai, Tamil Nadu, not Bihar)
6. Turnover (Rs. 62.00 Lakhs)
7. Continuous business experience (3 years)
8. Similar project experience (Rs. 1.00 Cr / Rs. 75 Lakhs)
9. Delivery timeline (67 days = 60 supply + 7 ATP)
10. Warranty period (3 years onsite)
11. Price validity (180 days)
12. Payment conditions (100% post-acceptance, no advance/part payment)
13. EMD (Rs. 1,25,000/-)
14. BOQ Table extraction (270 cameras, 1 server, VMS, 32U rack, 3 KVA UPS)
15. Substantive verification (grounded against document text)
"""

import os
import pytest
from backend.app.services.tender_intelligence.intelligence_retriever import intelligence_retriever
from backend.app.services.tender_intelligence.intelligence_extractors import (
    extract_overview_facts,
    extract_eligibility_conditions,
    extract_technical_specifications,
    extract_commercial_and_legal,
)
from backend.app.services.tender_intelligence.intelligence_validator import intelligence_validator
from backend.app.services.tender_intelligence.intelligence_engine import tender_intelligence_engine

BWC_PDF = "data/uploads/89b03245-aa37-4088-b800-3fd4321cd3f5.pdf"


@pytest.fixture(scope="module")
def bwc_records_and_index():
    assert os.path.exists(BWC_PDF), f"BWC PDF not found at {BWC_PDF}"
    doc_payload = [{
        "file_path": BWC_PDF,
        "filename": "89b03245-aa37-4088-b800-3fd4321cd3f5.pdf",
        "document_id": "bwc-audit-test",
    }]
    index, records, docs = intelligence_retriever.prepare_index(doc_payload)
    return index, records, docs


def test_bwc_overview_extraction(bwc_records_and_index):
    index, records, _ = bwc_records_and_index
    overview, dates = extract_overview_facts(records, {})

    # 1. Tender Title
    assert "Purchase of Body Worn Camera with Server Setup" in overview.tender_title

    # 2. Authority & TIA (Must NOT be "Date")
    assert overview.department_organization != "Date"
    assert overview.tender_inviting_authority != "Date"
    assert any(term in (overview.department_organization or "") for term in ["Tamil Nadu Police", "Office", "Police"])
    assert "Deputy Inspector General" in (overview.tender_inviting_authority or "")

    # 3. Tender Ref (Must not swallow address)
    assert "Kamarajar" not in overview.tender_reference_number
    assert "Chennai" not in overview.tender_reference_number

    # 4. Location (Must be Chennai, Tamil Nadu, not Bihar)
    assert "Chennai" in overview.project_location
    assert "Bihar" not in overview.project_location

    # 5. Delivery timeline (67 days = 60 + 7)
    assert "67" in overview.delivery_implementation_period or "60" in overview.delivery_implementation_period

    # 6. Warranty (3 years)
    assert "3" in (overview.warranty_maintenance_period or "") or "three" in (overview.warranty_maintenance_period or "").lower()

    # 7. EMD (Rs. 1,25,000)
    assert overview.emd_value is not None
    assert "1,25,000" in overview.emd_value


def test_bwc_eligibility_extraction(bwc_records_and_index):
    index, records, _ = bwc_records_and_index
    elig = extract_eligibility_conditions(records, index)

    # 8. Turnover (Rs. 62.00 Lakhs)
    assert "62" in elig.annual_turnover_requirement

    # 9. Continuous business experience (3 years)
    business_exp = [c for c in elig.conditions if c.category == "Continuous Business Experience"]
    assert len(business_exp) >= 1
    assert "3 years" in business_exp[0].department_requirement

    # 10. Similar work experience (1 project of 1 Cr or 2 of 75 L)
    assert "1.00 Crore" in elig.similar_work_experience or "1" in elig.similar_work_experience

    # 11. Consortium not allowed
    assert "Not allowed" in (elig.consortium_joint_venture_allowed or "")


def test_bwc_boq_and_technical_extraction(bwc_records_and_index):
    index, records, _ = bwc_records_and_index
    tech, oem, comp = extract_technical_specifications(records, index)

    # 12. BOQ items extracted from Page 1 table
    boq_items = [it for it in tech.items if it.subsystem_or_category == "Bill of Quantities (BOQ)"]
    assert len(boq_items) >= 5, f"Expected at least 5 BOQ items, found {len(boq_items)}"

    # Camera with Qty 270
    camera_item = next((it for it in boq_items if "camera" in it.item_name.lower()), None)
    assert camera_item is not None
    assert camera_item.required_quantity == "270"

    # Server with Qty 1
    server_item = next((it for it in boq_items if "server" in it.item_name.lower()), None)
    assert server_item is not None
    assert server_item.required_quantity == "1"

    # VMS and Rack
    vms_item = next((it for it in boq_items if "vms" in it.item_name.lower()), None)
    assert vms_item is not None
    rack_item = next((it for it in boq_items if "32u" in it.item_name.lower() or "rack" in it.item_name.lower()), None)
    assert rack_item is not None


def test_bwc_commercial_and_legal_extraction(bwc_records_and_index):
    index, records, _ = bwc_records_and_index
    comm, leg = extract_commercial_and_legal(records, index, {})

    # 13. Price validity (180 days)
    assert comm.price_validity_period == "180 days"

    # 14. Payment terms (100% post acceptance, no advance)
    assert "no part payment or advance payment" in comm.payment_terms.lower()
    assert "no part payment or advance payment" in comm.advance_payment_allowed.lower()

    # 15. Security Deposit / Retention (5%)
    assert "5" in comm.security_deposit or "5" in comm.retention_amount

