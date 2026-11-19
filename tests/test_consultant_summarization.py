"""Comprehensive Unit and Integration Tests for MYGPT AI Tender Consultant Summarization.

Verifies:
1. 7-Section Executive Briefing structure (Sections A through G).
2. Category-level grouping of technical specifications (no raw table dumps).
3. Grounded truth boundaries & mandatory bidder non-assessment notices:
   - "Bidder eligibility: Not assessed — company credentials have not been provided."
   - "Bidder compliance: Not assessed — product proposal or OEM datasheets have not been provided."
4. Direct, intent-specific Q&A responses for common consultant queries:
   - What is the EMD?
   - What is the eligibility?
   - Can we participate?
   - What are the technical specifications?
   - What are the risks?
   - Should we bid?
5. Multi-tender validation across NITK Desktop, WTL CCTV, and Tripura Wi-Fi.
"""

import os
import pytest
from typing import Any, Dict, List

from backend.app.services.tender_intelligence.intelligence_engine import tender_intelligence_engine
from backend.app.services.tender_intelligence.intelligence_report_builder import intelligence_report_builder
from backend.app.services.tender_intelligence.intelligence_schema import (
    BidRecommendation,
    BidStrategyAnalysis,
    CommercialFinancialAnalysis,
    EligibilityAnalysis,
    EligibilityCondition,
    RiskContradictionAnalysis,
    RiskContradictionItem,
    RiskLevel,
    TechnicalScopeAnalysis,
    TechnicalSpecificationAnalysis,
    TechnicalSpecificationItem,
    TenderConsultantReport,
    TenderOverview,
)

DATA_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "uploads"))
NITK_PDF = os.path.join(DATA_DIR, "2958370a-b714-47c0-9efa-9adfa6403d30.pdf")
TRIPURA_PDF = os.path.join(DATA_DIR, "0aaa92a2-f665-4d5e-98ba-c39ce650f525.pdf")
WTL_CCTV_PDF = os.path.join(DATA_DIR, "1a5fa635-e77b-4d14-85b9-64b0878e8549.pdf")


@pytest.fixture
def sample_report() -> TenderConsultantReport:
    """Creates a sample structured report to test report builder methods deterministically."""
    items = [
        TechnicalSpecificationItem(
            item_name="Processor",
            required_quantity="250",
            technical_specifications="Intel Core i7 13th Gen or AMD Ryzen 7",
            source_page=12,
            source_file="tender.pdf",
        ),
        TechnicalSpecificationItem(
            item_name="Memory (RAM)",
            required_quantity="250",
            technical_specifications="16 GB DDR4 3200 MHz RAM expandable to 64 GB",
            source_page=12,
            source_file="tender.pdf",
        ),
        TechnicalSpecificationItem(
            item_name="Storage (SSD)",
            required_quantity="250",
            technical_specifications="512 GB M.2 NVMe PCIe SSD",
            source_page=12,
            source_file="tender.pdf",
        ),
        TechnicalSpecificationItem(
            item_name="Display Monitor",
            required_quantity="250",
            technical_specifications='23.8" Full HD IPS Display 1920x1080',
            source_page=13,
            source_file="tender.pdf",
        ),
        TechnicalSpecificationItem(
            item_name="Operating System",
            required_quantity="250",
            technical_specifications="Windows 11 Professional 64-bit Preloaded",
            source_page=13,
            source_file="tender.pdf",
        ),
        TechnicalSpecificationItem(
            item_name="Warranty",
            required_quantity="250",
            technical_specifications="3 Years Comprehensive On-Site OEM Warranty",
            source_page=14,
            source_file="tender.pdf",
        ),
    ]

    report = TenderConsultantReport(
        report_id="test-rep-001",
        timestamp="2026-11-17T12:00:00",
        document_ids=["doc-001"],
        source_files=["desktop_tender.pdf"],
        total_pages_analyzed=41,
        overview=TenderOverview(
            tender_title="Procurement of Desktop Computers for Central Computing Facility",
            department_organization="National Institute of Technology Karnataka, Surathkal",
            tender_reference_number="NITK/CCC/2026/042",
            estimated_project_value="Rs. 1,50,00,000",
            emd_value="Rs. 3,00,000",
            tender_fee="Rs. 1,180",
            bid_submission_deadline="15-12-2026 15:00",
            bid_opening_date="16-12-2026 15:30",
            delivery_implementation_period="60 Days from Work Order",
            contract_duration="3 Years",
            warranty_maintenance_period="3 Years Comprehensive Onsite",
            overall_understanding="Supply and installation of 250 enterprise desktop computers.",
        ),
        eligibility=EligibilityAnalysis(
            annual_turnover_requirement="Minimum Rs. 5.00 Crore average turnover in last 3 financial years",
            similar_work_experience="Completed at least one similar supply of Rs. 1.20 Crore or two of Rs. 80 Lakhs",
            oem_authorization_mandatory=True,
            required_certifications=["ISO 9001:2015", "RoHS", "BIS"],
            conditions=[
                EligibilityCondition(
                    category="Turnover",
                    department_requirement="Rs. 5.00 Crore average turnover",
                    supporting_document_required="CA Audited Balance Sheets and Turnover Certificate with UDIN",
                    is_mandatory=True,
                    source_page=5,
                    source_file="desktop_tender.pdf",
                )
            ],
        ),
        technical_scope=TechnicalScopeAnalysis(
            overview="Supply, testing, and commissioning of desktop systems."
        ),
        technical_specifications=TechnicalSpecificationAnalysis(
            items=items,
            subsystems=["Desktop Computers"],
        ),
        commercial_financial=CommercialFinancialAnalysis(
            payment_terms="90% on delivery and installation, 10% after 30 days of satisfactory run",
            performance_bank_guarantee_pbg="5% of contract value valid for 38 months",
            penalties_and_liquidated_damages="0.5% per week subject to maximum of 10%",
            emd_exemption_rules="Exemption permitted for valid MSME / NSIC registered firms",
        ),
        risks_and_contradictions=RiskContradictionAnalysis(
            risks=[
                RiskContradictionItem(
                    risk_title="Aggressive Delivery Timeline",
                    risk_level=RiskLevel.HIGH.value,
                    description="Short delivery window of 60 days",
                    tender_evidence="All 250 units must be delivered within 60 days of Work Order",
                    source_page=7,
                    source_file="desktop_tender.pdf",
                    why_it_matters="Supply chain delay risks penalty deduction from invoice",
                    potential_impact="Financial liquidated damages deduction",
                    recommended_action="Obtain written supply confirmation from OEM prior to bidding",
                )
            ],
            critical_risks_count=0,
            high_risks_count=1,
        ),
        bid_strategy=BidStrategyAnalysis(
            recommendation=BidRecommendation.PROCEED_WITH_CAUTION.value,
            recommendation_rationale="Favorable commercial terms, but OEM MAF and strict 60-day delivery require advance coordination.",
            overall_tender_assessment="Feasible project for tier-1 IT hardware distributors.",
            bid_preparation_priorities=[
                "Obtain OEM Manufacturer Authorization Form (MAF)",
                "Secure MSME certificate for EMD exemption",
                "Verify stock availability for delivery within 60 days",
            ],
        ),
    )
    return report


def test_group_technical_specifications(sample_report: TenderConsultantReport):
    """Verifies that technical specifications are clustered into logical functional categories."""
    grouped = intelligence_report_builder._group_technical_specifications(sample_report.technical_specifications.items)
    
    assert isinstance(grouped, dict)
    assert len(grouped) > 0
    
    # Check that Computing Core and Display & Visuals categories exist
    assert "Computing & Processing Core" in grouped
    assert "Display, Graphics & Peripherals" in grouped
    assert "Software, Operating System & Security" in grouped
    assert "Warranty, AMC & Support Services" in grouped

    # Check items are appropriately placed
    comp_items = [it.item_name for it in grouped["Computing & Processing Core"]]
    assert "Processor" in comp_items or "Memory (RAM)" in comp_items


def test_consultant_briefing_sections_a_to_g(sample_report: TenderConsultantReport):
    """Verifies that the generated consultant briefing contains all Sections A through G."""
    report = intelligence_report_builder.generate_markdown(sample_report)
    briefing = report.consultant_briefing_markdown

    assert briefing is not None
    assert len(briefing) > 200

    # Section headers check
    assert "## Section A: Tender at a Glance" in briefing
    assert "## Section B: Most Important Requirements (Pre-Qualification & Eligibility)" in briefing
    assert "## Section C: Important Technical Scope & Key Specifications" in briefing
    assert "## Section D: Financial & Contractual Obligations" in briefing
    assert "## Section E: Major Risks & Critical Concerns" in briefing
    assert "## Section F: Consultant Recommendation & Strategic Verdict" in briefing
    assert "## Section G: Immediate Actions & Next Steps" in briefing


def test_mandatory_non_assessment_notices(sample_report: TenderConsultantReport):
    """Verifies that mandatory bidder eligibility and compliance notices are explicitly included."""
    report = intelligence_report_builder.generate_markdown(sample_report)
    briefing = report.consultant_briefing_markdown

    # Section B notice:
    assert "**Bidder eligibility**: Not assessed — company credentials have not been provided." in briefing

    # Section C notice:
    assert "**Bidder compliance**: Not assessed — product proposal or OEM datasheets have not been provided." in briefing


def test_answer_consultant_question_emd(sample_report: TenderConsultantReport):
    """Verifies that asking about EMD returns a direct, authoritative summary with page citation."""
    answer, sources = tender_intelligence_engine.answer_consultant_question(
        documents=[],
        question="What is the EMD for this tender?",
        cached_report=sample_report,
    )

    assert "Earnest Money Deposit (EMD)" in answer
    assert "Rs. 3,00,000" in answer
    assert "MSME / Exemption" in answer
    assert "[ TENDER REQUIREMENT ]" in answer


def test_answer_consultant_question_eligibility(sample_report: TenderConsultantReport):
    """Verifies that asking about eligibility returns mandatory turnover, experience, MAF and notice."""
    answer, sources = tender_intelligence_engine.answer_consultant_question(
        documents=[],
        question="What are the eligibility criteria?",
        cached_report=sample_report,
    )

    assert "Mandatory Bidder Eligibility" in answer
    assert "Rs. 5.00 Crore" in answer
    assert "MAF" in answer
    assert "**Bidder eligibility**: Not assessed — company credentials have not been provided." in answer


def test_answer_consultant_question_can_we_participate(sample_report: TenderConsultantReport):
    """Verifies that asking 'Can we participate?' distinguishes criteria from bidder credentials."""
    answer, sources = tender_intelligence_engine.answer_consultant_question(
        documents=[],
        question="Can we participate in this tender?",
        cached_report=sample_report,
    )

    assert "Participation Feasibility Assessment" in answer
    assert "Turnover Threshold" in answer
    assert "**Bidder eligibility**: Not assessed — company credentials have not been provided." in answer


def test_answer_consultant_question_specs(sample_report: TenderConsultantReport):
    """Verifies that asking about specs provides grouped functional categories and compliance notice."""
    answer, sources = tender_intelligence_engine.answer_consultant_question(
        documents=[],
        question="What are the technical specifications?",
        cached_report=sample_report,
    )

    assert "Key Technical Scope & Specifications" in answer
    assert "Computing & Processing Core" in answer or "Processor" in answer
    assert "**Bidder compliance**: Not assessed — product proposal or OEM datasheets have not been provided." in answer


def test_answer_consultant_question_risks(sample_report: TenderConsultantReport):
    """Verifies that asking about risks returns material concerns and citations."""
    answer, sources = tender_intelligence_engine.answer_consultant_question(
        documents=[],
        question="What are the major risks in this tender?",
        cached_report=sample_report,
    )

    assert "Identified Tender Risks & Concerns" in answer
    assert "Aggressive Delivery Timeline" in answer
    assert "Page 7" in answer


def test_answer_consultant_question_recommendation(sample_report: TenderConsultantReport):
    """Verifies that asking 'Should we bid?' returns consultant verdict and strategic advice."""
    answer, sources = tender_intelligence_engine.answer_consultant_question(
        documents=[],
        question="Should we bid on this project?",
        cached_report=sample_report,
    )

    assert "Consultant Verdict" in answer
    assert "PROCEED WITH CAUTION" in answer
    assert "Key Pre-Bid Priorities" in answer


@pytest.mark.skipif(not os.path.exists(NITK_PDF), reason="NITK test PDF not present")
def test_real_tender_briefing_nitk(monkeypatch):
    """Verifies executive briefing generation on real NITK Desktop tender PDF."""
    monkeypatch.setattr(
        tender_intelligence_engine,
        "_call_gemma_json",
        lambda prompt, max_tokens=350: {
            "recommendation": "PROCEED_WITH_CAUTION",
            "recommendation_rationale": "NITK desktop tender terms viable.",
            "overall_tender_assessment": "Standard academic computer lab procurement.",
            "critical_risks": [],
            "key_qualification_hurdles": ["Turnover of Rs. 23.63 Lakhs and OEM MAF"],
            "prebid_clarification_questions": ["Confirm warranty coverage terms"],
            "bid_preparation_priorities": ["Obtain OEM Authorization Form", "Submit EMD of Rs. 94,500"],
        },
    )

    doc_info = {
        "document_id": "nitk_briefing_test",
        "id": "nitk_briefing_test",
        "filename": "nitk_desktop.pdf",
        "file_path": NITK_PDF,
    }
    report = tender_intelligence_engine.evaluate_tender([doc_info], mode="fast", force_refresh=True)

    briefing = report.consultant_briefing_markdown
    assert briefing is not None
    assert "Section A: Tender at a Glance" in briefing
    assert "High End Desktop" in briefing or "NITK" in briefing
    assert "Section B: Most Important Requirements" in briefing
    assert "**Bidder eligibility**: Not assessed" in briefing
    assert "Section C: Important Technical Scope" in briefing
    assert "**Bidder compliance**: Not assessed" in briefing
    assert "Section D: Financial & Contractual Obligations" in briefing
    assert "Section E: Major Risks & Critical Concerns" in briefing
    assert "Section F: Consultant Recommendation & Strategic Verdict" in briefing
    assert "Section G: Immediate Actions & Next Steps" in briefing


@pytest.mark.skipif(not os.path.exists(WTL_CCTV_PDF), reason="WTL CCTV test PDF not present")
def test_real_tender_briefing_wtl_cctv(monkeypatch):
    """Verifies executive briefing generation on real WTL ANPR & CCTV tender PDF."""
    monkeypatch.setattr(
        tender_intelligence_engine,
        "_call_gemma_json",
        lambda prompt, max_tokens=350: {
            "recommendation": "PROCEED_WITH_CAUTION",
            "recommendation_rationale": "WTL surveillance tender viable with consortium or direct OEM support.",
            "overall_tender_assessment": "Major state-wide ANPR and IP surveillance deployment.",
            "critical_risks": [],
            "key_qualification_hurdles": ["Turnover Rs. 8.00 Cr and Past 3-tier experience"],
            "prebid_clarification_questions": ["Clarify 30-day camera installation milestone"],
            "bid_preparation_priorities": ["Secure CCTV OEM MAFs", "Assemble audited financials"],
        },
    )

    doc_info = {
        "document_id": "wtl_briefing_test",
        "id": "wtl_briefing_test",
        "filename": "wtl_cctv.pdf",
        "file_path": WTL_CCTV_PDF,
    }
    report = tender_intelligence_engine.evaluate_tender([doc_info], mode="fast", force_refresh=True)

    briefing = report.consultant_briefing_markdown
    assert briefing is not None
    assert "Section A: Tender at a Glance" in briefing
    assert "WEBEL TECHNOLOGY LIMITED" in briefing.upper()
    assert "Section B: Most Important Requirements" in briefing
    assert "**Bidder eligibility**: Not assessed" in briefing
    assert "Section F: Consultant Recommendation" in briefing
    assert "Section G: Immediate Actions" in briefing
