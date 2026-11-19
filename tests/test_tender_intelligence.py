"""Comprehensive Test Suite for MYGPT AI Tender Consultant.

Validates schema serialization, evidence classifications, domain retrieval,
truth boundary validator, report formatting, disk caching, end-to-end evaluation
on real tender PDF, follow-up QA, and API backward compatibility.
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.main import app
from backend.app.services.document_parser import document_parser
from backend.app.services.tender.tender_section_retriever import PageRecord, TenderDocumentIndex
from backend.app.services.tender_intelligence import (
    ActionRoadmap,
    BidRecommendation,
    BidStrategyAnalysis,
    CommercialFinancialAnalysis,
    ComplianceStatus,
    EligibilityAnalysis,
    EvidenceClassification,
    ItemWiseComplianceMatrix,
    OEMRequirementAnalysis,
    RiskContradictionAnalysis,
    RiskLevel,
    TechnicalScopeAnalysis,
    TechnicalSpecificationAnalysis,
    TenderConsultantReport,
    TenderEvidenceCitation,
    TenderOverview,
    tender_intelligence_engine,
)
from backend.app.services.tender_intelligence.intelligence_report_builder import (
    intelligence_report_builder,
)
from backend.app.services.tender_intelligence.intelligence_retriever import (
    intelligence_retriever,
)
from backend.app.services.tender_intelligence.intelligence_validator import (
    intelligence_validator,
)

SAMPLE_TENDER_PDF = ROOT_DIR / "gemma_tender_manual_test" / "uploads" / "265f816f_Tendernotice_2 (5).pdf"


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Test 1: Schema Integrity & Serialization
# ---------------------------------------------------------------------------

def test_schema_integrity_and_serialization():
    """Verifies that all 11 consultant dimensions initialize and serialize without error."""
    report = TenderConsultantReport(
        report_id="test_rep_001",
        timestamp="2026-11-14 12:00:00",
        document_ids=["doc_test_1"],
        source_files=["test_tender.pdf"],
        total_pages_analyzed=10,
        overview=TenderOverview(
            department_organization="Tripura University",
            tender_title="Campus Wi-Fi Implementation",
            tender_reference_number="TU/WIFI/2026",
            estimated_project_value="INR 1,20,00,000",
            emd_value="INR 2,40,000",
            bid_submission_deadline="2026-12-01 15:00",
        ),
        eligibility=EligibilityAnalysis(
            annual_turnover_requirement="Minimum 5 Crores in last 3 financial years",
            similar_work_experience="3 completed works of 40 Lakhs or 1 of 80 Lakhs",
            oem_authorization_mandatory=True,
        ),
        risks_and_contradictions=RiskContradictionAnalysis(
            critical_risks_count=1,
            high_risks_count=2,
            risks=[],
        ),
        bid_strategy=BidStrategyAnalysis(
            recommendation=BidRecommendation.PROCEED_WITH_CAUTION.value,
            recommendation_rationale="Commercially viable subject to OEM MAF confirmation",
        ),
        action_roadmap=ActionRoadmap(
            checklist=[],
        ),
    )

    data = report.model_dump()
    assert data["report_id"] == "test_rep_001"
    assert data["overview"]["department_organization"] == "Tripura University"
    assert data["eligibility"]["oem_authorization_mandatory"] is True
    assert data["bid_strategy"]["recommendation"] == "Proceed with caution"

    # Roundtrip json test
    json_str = report.model_dump_json()
    reconstructed = TenderConsultantReport.model_validate_json(json_str)
    assert reconstructed.report_id == report.report_id
    assert reconstructed.overview.tender_reference_number == "TU/WIFI/2026"


# ---------------------------------------------------------------------------
# Test 2: Mandatory Evidence Classification Tags
# ---------------------------------------------------------------------------

def test_evidence_classification_tags():
    """Ensures exact truth boundary classification enum tags exist."""
    assert EvidenceClassification.TENDER_REQUIREMENT.value == "[ TENDER REQUIREMENT ]"
    assert EvidenceClassification.CONSULTANT_RECOMMENDATION.value == "[ CONSULTANT RECOMMENDATION ]"
    assert EvidenceClassification.ASSUMPTION_CAVEAT.value == "[ ASSUMPTION / CAVEAT ]"
    assert EvidenceClassification.NOT_SPECIFIED_IN_TENDER.value == "[ NOT SPECIFIED IN TENDER ]"
    assert EvidenceClassification.NEEDS_CLARIFICATION.value == "[ NEEDS CLARIFICATION ]"


# ---------------------------------------------------------------------------
# Test 3: Domain Retrieval & Index Scoring
# ---------------------------------------------------------------------------

def test_domain_retrieval_scoring():
    """Verifies that intelligence_retriever accurately scores domain pages."""
    records = [
        PageRecord(
            filename="tender.pdf",
            document_id="doc_1",
            file_type=".pdf",
            page_number=1,
            text="Notice Inviting E-Tender No TU/WIFI/2026. Estimated Cost INR 1 Crore. EMD INR 2 Lakhs. Submission deadline 2026-11-30.",
        ),
        PageRecord(
            filename="tender.pdf",
            document_id="doc_1",
            file_type=".pdf",
            page_number=2,
            text="Eligibility Criteria: Minimum annual turnover shall be 5 Crores. Prior similar work experience with Government/PSU mandatory. MAF required.",
        ),
        PageRecord(
            filename="tender.pdf",
            document_id="doc_1",
            file_type=".pdf",
            page_number=3,
            text="Technical Specifications: Wi-Fi 6 Access Points, IEEE 802.11ax, dual band, PoE+ compliant with 5 years warranty.",
        ),
        PageRecord(
            filename="tender.pdf",
            document_id="doc_1",
            file_type=".pdf",
            page_number=4,
            text="Commercial Terms: Payment 80% on delivery, 20% on commissioning. Liquidated damages 0.5% per week up to 10% maximum penalty for delay.",
        ),
    ]

    index = TenderDocumentIndex(signature="sig_test_1", records=records)

    # Overview retrieval
    ov_pages = intelligence_retriever.retrieve_dimension_pages(index, "overview", max_pages=2)
    assert len(ov_pages) > 0
    assert ov_pages[0][0].page_number == 1

    # Eligibility retrieval
    el_pages = intelligence_retriever.retrieve_dimension_pages(index, "eligibility", max_pages=2)
    assert len(el_pages) > 0
    assert el_pages[0][0].page_number == 2

    # Specifications retrieval
    sp_pages = intelligence_retriever.retrieve_dimension_pages(index, "specifications", max_pages=2)
    assert len(sp_pages) > 0
    assert sp_pages[0][0].page_number == 3

    # Commercial retrieval
    cm_pages = intelligence_retriever.retrieve_dimension_pages(index, "commercial", max_pages=2)
    assert len(cm_pages) > 0
    assert cm_pages[0][0].page_number == 4


# ---------------------------------------------------------------------------
# Test 4: Truth Boundary & Citation Validator
# ---------------------------------------------------------------------------

def test_intelligence_validator_bounds():
    """Verifies that the validator clamps invalid pages and normalizes recommendations."""
    records = [
        PageRecord(filename="tender.pdf", document_id="doc_1", file_type=".pdf", page_number=1, text="Tender Intro"),
        PageRecord(filename="tender.pdf", document_id="doc_1", file_type=".pdf", page_number=2, text="Eligibility clauses"),
    ]

    report = TenderConsultantReport(
        report_id="rep_val_1",
        timestamp="2026-11-14",
        total_pages_analyzed=2,
        overview=TenderOverview(
            citations=[
                TenderEvidenceCitation(filename="tender.pdf", page_number=99),  # Invalid page!
            ]
        ),
        bid_strategy=BidStrategyAnalysis(
            recommendation="PROCEED_WITH_CAUTION_SOMETHING_ELSE",  # Unnormalized
        ),
    )

    validated = intelligence_validator.validate_report(report, records)
    assert validated.overview.citations[0].page_number == 2  # Clamped to max page
    assert validated.bid_strategy.recommendation == BidRecommendation.PROCEED_WITH_CAUTION.value
    assert len(validated.verification_notes) > 0


# ---------------------------------------------------------------------------
# Test 5: Report Builder & Markdown Dossier
# ---------------------------------------------------------------------------

def test_report_builder_markdown():
    """Verifies generation of both executive summary and full dossier markdown."""
    report = TenderConsultantReport(
        report_id="rep_md_1",
        timestamp="2026-11-14",
        source_files=["campus_wifi.pdf"],
        total_pages_analyzed=15,
        overview=TenderOverview(
            department_organization="Tripura University",
            tender_title="Campus Wi-Fi Network",
            tender_reference_number="TU/WIFI/2026",
            estimated_project_value="INR 1,20,00,000",
            emd_value="INR 2,40,000",
            bid_submission_deadline="2026-12-01",
        ),
        bid_strategy=BidStrategyAnalysis(
            recommendation=BidRecommendation.PROCEED_WITH_CAUTION.value,
            recommendation_rationale="Terms are viable but penalty cap is 10%.",
        ),
    )

    formatted = intelligence_report_builder.generate_markdown(report)
    assert "# 📋 Tender Consultant Executive Briefing" in formatted.executive_summary_markdown
    assert "Tripura University" in formatted.executive_summary_markdown
    assert "PROCEED WITH CAUTION" in formatted.executive_summary_markdown
    assert "## 1. 🏢 Tender Overview" in formatted.full_report_markdown
    assert "## 2. 🎯 Bidder Eligibility" in formatted.full_report_markdown
    assert "## 9. ⚠️ Risk and Contradiction Analysis" in formatted.full_report_markdown
    assert "## 11. 🚀 Final Action Roadmap" in formatted.full_report_markdown


# ---------------------------------------------------------------------------
# Test 6: End-to-End Real Tender Evaluation
# ---------------------------------------------------------------------------

def test_end_to_end_real_tender_evaluation():
    """Evaluates real tender PDF (Tendernotice_2 (5).pdf) using the full consultant engine."""
    assert SAMPLE_TENDER_PDF.exists(), f"Sample tender PDF not found: {SAMPLE_TENDER_PDF}"

    mock_doc = {
        "id": "doc_real_test",
        "document_id": "doc_real_test",
        "filename": "Tendernotice_2 (5).pdf",
        "file_path": str(SAMPLE_TENDER_PDF),
        "file_type": ".pdf",
    }

    start_t = time.time()
    report = tender_intelligence_engine.evaluate_tender([mock_doc], force_refresh=False)
    elapsed = time.time() - start_t

    print(f"\n[E2E_EVALUATION] Completed in {elapsed:.2f}s")
    print(f"[E2E_EVALUATION] Authority: {report.overview.department_organization}")
    print(f"[E2E_EVALUATION] Title: {report.overview.tender_title}")
    print(f"[E2E_EVALUATION] Verdict: {report.bid_strategy.recommendation}")
    print(f"[E2E_EVALUATION] Total Pages: {report.total_pages_analyzed}")

    # Core verifications
    assert report.total_pages_analyzed == 33
    assert "Tripura University" in (report.overview.department_organization or "") or "Tripura" in (report.overview.tender_title or "")
    assert len(report.eligibility.conditions) > 0
    assert len(report.technical_scope.scope_items) > 0
    assert len(report.risks_and_contradictions.risks) > 0
    assert len(report.action_roadmap.checklist) > 0
    assert report.executive_summary_markdown != ""
    assert report.full_report_markdown != ""

    # Second run should be an instant cache hit
    cached_report = tender_intelligence_engine.evaluate_tender([mock_doc], force_refresh=False)
    assert cached_report.cache_hit is True
    print(f"[E2E_EVALUATION] Cache hit verified! ({cached_report.elapsed_seconds}s)")


# ---------------------------------------------------------------------------
# Test 7: Follow-Up Conversational Q&A
# ---------------------------------------------------------------------------

def test_consultant_followup_qa():
    """Verifies that follow-up questions are answered using tender evidence."""
    mock_doc = {
        "id": "doc_real_test",
        "document_id": "doc_real_test",
        "filename": "Tendernotice_2 (5).pdf",
        "file_path": str(SAMPLE_TENDER_PDF),
        "file_type": ".pdf",
    }

    # Ask about eligibility
    answer, sources = tender_intelligence_engine.answer_consultant_question(
        [mock_doc], "What are the eligibility criteria for bidders?"
    )

    print(f"\n[FOLLOWUP_QA] Answer snippet:\n{answer[:250]}")
    print(f"[FOLLOWUP_QA] Cited sources: {sources}")

    assert len(sources) > 0
    assert len(answer) > 20
    assert any(s["page_number"] in (4, 8, 10, 20, 1) for s in sources)


# ---------------------------------------------------------------------------
# Test 8: API Endpoints & Backward Compatibility
# ---------------------------------------------------------------------------

def test_api_endpoints_backward_compatibility(client):
    """Verifies POST /api/company/tender/consultant and preservation of extraction endpoints."""
    # 1. Test consultant endpoint with invalid payload (404 when no docs)
    res_consultant = client.post(
        "/api/company/tender/consultant",
        json={"document_ids": ["non_existent_doc_id"]},
    )
    assert res_consultant.status_code == 404

    # 2. Test existing extraction endpoint is preserved
    res_extract = client.post(
        "/api/company/tender/extract",
        params={"document_ids": ["non_existent_doc_id"]},
    )
    assert res_extract.status_code == 404  # Preserved contract
