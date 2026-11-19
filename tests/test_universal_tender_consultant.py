"""Universal Professional AI Tender Consultant Test Suite.

Validates:
1. Multi-domain autonomous procurement classification across diverse industries and document roles.
2. Cross-section contradiction and ambiguity discovery with exact page citations.
3. Strict separation of tender criteria vs bidder assessment.
4. Universal multi-tier CVC experience parsing (80%/50%/40% tiers with disjunctive OR logic).
5. Fast hybrid evaluation with local Gemma strategic reasoning across tender packages.
"""

import os
import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.services.document_parser import document_parser
from backend.app.services.tender.tender_section_retriever import PageRecord, TenderDocumentIndex
from backend.app.services.tender_intelligence.universal_classifier import (
    universal_classifier,
    ProcurementCategory,
    ContractType,
    DocumentRole,
)
from backend.app.services.tender_intelligence.contradiction_engine import (
    contradiction_engine,
    ContradictionEngine,
)
from backend.app.services.tender_intelligence.intelligence_extractors import (
    extract_overview_facts,
    extract_eligibility_conditions,
    extract_technical_specifications,
    extract_commercial_and_legal,
)
from backend.app.services.tender_intelligence.intelligence_schema import (
    TenderOverview,
    EligibilityAnalysis,
    TechnicalSpecificationAnalysis,
    TechnicalSpecificationItem,
    CommercialFinancialAnalysis,
    ContractualLegalAnalysis,
)
from backend.app.services.tender_intelligence.intelligence_engine import tender_intelligence_engine


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
# Test 1: Multi-Domain Classification
# ---------------------------------------------------------------------------
def test_universal_domain_classification():
    # 1. NITK Desktop -> IT Hardware
    nitk_pdf = r"D:\MYGPT\data\uploads\2958370a-b714-47c0-9efa-9adfa6403d30.pdf"
    if os.path.exists(nitk_pdf):
        nitk_recs = _load_tender_records(nitk_pdf, "nitk", "NITK_Desktop.pdf")
        text_sample = "\n".join(r.text for r in nitk_recs[:10])
        profile = universal_classifier.classify_document(text_sample, "NITK_Desktop.pdf", len(nitk_recs))
        assert profile["primary_category"] == ProcurementCategory.IT_HARDWARE.value
        assert profile["contract_type"] in (ContractType.SUPPLY_GOODS.value, ContractType.HYBRID_SUPPLY_INSTALL.value)
        assert profile["document_role"] == DocumentRole.MAIN_TENDER.value

    # 2. Tripura Wi-Fi -> Networking & Telecom
    tripura_pdf = r"D:\MYGPT\data\uploads\0aaa92a2-f665-4d5e-98ba-c39ce650f525.pdf"
    if os.path.exists(tripura_pdf):
        tripura_recs = _load_tender_records(tripura_pdf, "tripura", "Tripura_WiFi.pdf")
        text_sample = "\n".join(r.text for r in tripura_recs[:10])
        profile = universal_classifier.classify_document(text_sample, "Tripura_WiFi.pdf", len(tripura_recs))
        assert profile["primary_category"] == ProcurementCategory.NETWORKING_TELECOM.value
        assert profile["contract_type"] in (ContractType.HYBRID_SUPPLY_INSTALL.value, ContractType.SUPPLY_GOODS.value)

    # 3. WTL CCTV / ANPR -> CCTV & Surveillance
    wtl_pdf = r"D:\MYGPT\data\uploads\1a5fa635-e77b-4d14-85b9-64b0878e8549.pdf"
    if os.path.exists(wtl_pdf):
        wtl_recs = _load_tender_records(wtl_pdf, "wtl", "WTL_CCTV.pdf")
        text_sample = "\n".join(r.text for r in wtl_recs[:10])
        profile = universal_classifier.classify_document(text_sample, "WTL_CCTV.pdf", len(wtl_recs))
        assert profile["primary_category"] == ProcurementCategory.CCTV_SURVEILLANCE.value
        assert profile["contract_type"] == ContractType.HYBRID_SUPPLY_INSTALL.value


# ---------------------------------------------------------------------------
# Test 2: Autonomous Cross-Section Contradiction Engine
# ---------------------------------------------------------------------------
def test_contradiction_engine_discovery():
    engine = ContradictionEngine()

    # Scenario A: Delivery timeline contradiction (30 days on P2 vs 60 days on P15)
    rec1 = PageRecord(filename="t.pdf", document_id="1", file_type="pdf", page_number=2, text="delivery period is 30 days from date of purchase order", file_hash="h")
    rec2 = PageRecord(filename="t.pdf", document_id="1", file_type="pdf", page_number=15, text="delivery schedule shall be within 60 days from award of contract", file_hash="h")
    ov = TenderOverview(delivery_implementation_period="30 days", warranty_maintenance_period="3 Years")
    el = EligibilityAnalysis()
    sp = TechnicalSpecificationAnalysis()
    cm = CommercialFinancialAnalysis(penalties_and_liquidated_damages="0.5% per week up to maximum 10%")
    lg = ContractualLegalAnalysis()

    findings = engine.analyze_contradictions(ov, el, sp, cm, lg, [rec1, rec2])
    assert any("Delivery Schedule Ambiguity" in f for f in findings)
    assert any("Page 2" in f and "Page 15" in f for f in findings)

    # Scenario B: Warranty conflict (Overview says 3 Years, but Item spec says 5 Years)
    sp_with_items = TechnicalSpecificationAnalysis(
        items=[
            TechnicalSpecificationItem(
                item_name="Core Industrial Switch",
                technical_specifications="10G SFP+ ports with 5 years warranty from OEM",
                source_page=22,
                source_file="t.pdf",
            )
        ]
    )
    findings_w = engine.analyze_contradictions(ov, el, sp_with_items, cm, lg, [rec1, rec2])
    assert any("Warranty Duration Conflict" in f for f in findings_w)
    assert any("Page 22" in f for f in findings_w)

    # Scenario C: MSME EMD exemption contradiction (Page 3 exempt vs Page 8 no exemption)
    rec_msme = PageRecord(filename="t.pdf", document_id="1", file_type="pdf", page_number=3, text="MSME registered bidders are exempted from payment of EMD as per Govt policy", file_hash="h")
    rec_no_msme = PageRecord(filename="t.pdf", document_id="1", file_type="pdf", page_number=8, text="No exemption on EMD shall be granted to any bidder under any circumstances", file_hash="h")
    findings_msme = engine.analyze_contradictions(ov, el, sp, cm, lg, [rec_msme, rec_no_msme])
    assert any("EMD Exemption Conflict for MSME" in f for f in findings_msme)
    assert any("Page 3" in f and "Page 8" in f for f in findings_msme)


# ---------------------------------------------------------------------------
# Test 3: Distinction Between Tender Criteria and Bidder Assessment
# ---------------------------------------------------------------------------
def test_criteria_vs_assessment_separation():
    tripura_pdf = r"D:\MYGPT\data\uploads\0aaa92a2-f665-4d5e-98ba-c39ce650f525.pdf"
    if os.path.exists(tripura_pdf):
        records = _load_tender_records(tripura_pdf, "tripura_01", "Tripura_WiFi.pdf")
        eligibility = extract_eligibility_conditions(records, None)
        specs, oem, compliance = extract_technical_specifications(records, None)

        # 1. Eligibility summary assessment must explicitly state bidder profile required
        assert "BIDDER ELIGIBILITY NOT ASSESSED — COMPANY PROFILE REQUIRED" in eligibility.summary_assessment
        assert "Conditions define mandatory requirements set by the issuing department" in eligibility.summary_assessment

        # 2. Compliance matrix must clearly state assessment pending bidder proposal
        assert "COMPLIANCE ASSESSMENT PENDING — BIDDER PROPOSAL REQUIRED" in compliance.compliance_summary


# ---------------------------------------------------------------------------
# Test 4: Universal Multi-Tier CVC Experience Parsing (OR logic)
# ---------------------------------------------------------------------------
def test_universal_cvc_experience_parsing():
    wtl_pdf = r"D:\MYGPT\data\uploads\1a5fa635-e77b-4d14-85b9-64b0878e8549.pdf"
    if os.path.exists(wtl_pdf):
        records = _load_tender_records(wtl_pdf, "wtl_01", "WTL_CCTV.pdf")
        eligibility = extract_eligibility_conditions(records, None)
        exp = eligibility.similar_work_experience

        # Must preserve the 3 distinct financial tiers with OR logic
        assert "6.40" in exp
        assert "4.00" in exp
        assert "3.20" in exp
        assert "OR" in exp
        # Must not collapse into a hardcoded "minimum two projects"
        assert "minimum two projects" not in exp.lower()


# ---------------------------------------------------------------------------
# Test 5: End-to-End Evaluation with Engine & Profile Injection
# ---------------------------------------------------------------------------
def test_universal_engine_evaluation_and_grounding(monkeypatch):
    nitk_pdf = r"D:\MYGPT\data\uploads\2958370a-b714-47c0-9efa-9adfa6403d30.pdf"
    if not os.path.exists(nitk_pdf):
        pytest.skip("NITK PDF not available")

    monkeypatch.setattr(
        tender_intelligence_engine,
        "_call_gemma_json",
        lambda prompt, max_tokens=350: {
            "recommendation": "PROCEED_WITH_CAUTION",
            "recommendation_rationale": "NITK tender terms viable.",
            "critical_risks": [],
            "strategic_recommendations": ["[CONSULTANT RECOMMENDATION] Conduct OEM Compatibility Audit"],
        },
    )

    doc_info = {
        "document_id": "nitk_universal_test",
        "id": "nitk_universal_test",
        "filename": "NITK_Desktop.pdf",
        "file_path": nitk_pdf,
    }

    report = tender_intelligence_engine.evaluate_tender([doc_info], mode="fast", force_refresh=True)

    # 1. Category and contract type populated
    assert report.overview.tender_category == ProcurementCategory.IT_HARDWARE.value
    assert report.overview.contract_type in (ContractType.SUPPLY_GOODS.value, ContractType.HYBRID_SUPPLY_INSTALL.value)

    # 2. Roadmap has distinct pages
    roadmap_pages = [s.relevant_tender_page for s in report.action_roadmap.checklist if s.relevant_tender_page is not None]
    assert len(roadmap_pages) >= 3
    assert len(set(roadmap_pages)) > 1

    # 3. Factual Grounding
    assert "National Institute of Technology Karnataka" in report.overview.department_organization
    assert "High End Desktop" in report.overview.tender_title
    assert "94,500" in (report.overview.emd_value or "")

    # 4. Latency breakdown
    assert "extraction_seconds" in report.processing_latency_breakdown
    assert "gemma_inference_seconds" in report.processing_latency_breakdown
    assert report.elapsed_seconds > 0

