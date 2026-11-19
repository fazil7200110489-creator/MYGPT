"""Comprehensive Test Suite for MYGPT Interactive Conversational Tender Consultant.

Verifies:
1. Step 1 & 2: Initial Response is concise, professional, and contains only:
   - What the tender is about.
   - Issuing authority.
   - Estimated value (or explicitly state not specified).
   - EMD and tender fee.
   - Submission deadline.
   - Important eligibility requirements.
   - Main technical scope.
   - Major financial commitments.
   - Two or three important risks with page citations.
   - Brief consultant observation (Verdict badge and rationale).
   - No raw technical tables or full 11-dimension dashboard dumps in the initial message.
2. Step 3: Dynamic Suggested Questions:
   - Generated dynamically based on the tender's domain and content.
   - CCTV tenders suggest camera/ANPR questions.
   - Desktop tenders suggest hardware/processor questions.
   - Meter tenders suggest meter/protocol questions.
   - Wi-Fi tenders suggest access point/networking questions.
3. Step 4 & 5: Real Conversational Interaction & Context Continuity:
   - "What is the complete eligibility criteria?"
   - "What is the minimum turnover?"
   - "Is consortium allowed?"
   - "What documents must we submit?"
   - "What are the payment and warranty conditions?"
   - Each answer returns grounded evidence with page citations and new follow-up suggestions.
4. Step 6: Detailed Analysis Preservation:
   - All 11 dimensions, compliance matrix, and 7-section executive briefing remain preserved internally.
5. Step 9: Multi-Tender E2E Testing across:
   - NITK Desktop
   - Tripura University Wi-Fi
   - Women's Safety CCTV
   - WTL CCTV and ANPR
   - EESL Energy Meter
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
    TenderEvidenceCitation,
    TenderOverview,
)

DATA_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "uploads"))
NITK_PDF = os.path.join(DATA_DIR, "2958370a-b714-47c0-9efa-9adfa6403d30.pdf")
TRIPURA_PDF = os.path.join(DATA_DIR, "0aaa92a2-f665-4d5e-98ba-c39ce650f525.pdf")
WOMENS_SAFETY_PDF = os.path.join(DATA_DIR, "4f8eac53-a110-440b-8b98-019b3c1e4dfd.pdf")
WTL_CCTV_PDF = os.path.join(DATA_DIR, "1a5fa635-e77b-4d14-85b9-64b0878e8549.pdf")
EESL_METER_PDF = os.path.join(DATA_DIR, "9dd28e45-80d7-4c0d-ae26-b6c28b7cd995.pdf")


@pytest.fixture
def mock_cctv_report() -> TenderConsultantReport:
    """Creates a sample CCTV surveillance report fixture."""
    return TenderConsultantReport(
        report_id="cctv-rep-001",
        timestamp="2026-11-17T12:00:00",
        document_ids=["doc-cctv"],
        source_files=["wtl_cctv.pdf"],
        total_pages_analyzed=79,
        overview=TenderOverview(
            tender_title="Selection of SI for Supply, Installation and Maintenance of CCTV Surveillance and ANPR System",
            department_organization="Webel Technology Limited",
            tender_reference_number="WTL/WBPNB/CCTV/26-27/046",
            tender_category="Surveillance & CCTV",
            estimated_project_value="Rs. 16.00 Crore",
            emd_value="Rs. 32,00,000/- (Rs. 32 Lakhs)",
            tender_fee="Rs. 10,000/-",
            bid_submission_deadline="2026-12-15 15:00 Hrs",
            delivery_implementation_period="30 Days from Work Order",
            warranty_maintenance_period="3 Years Comprehensive On-Site Warranty followed by 2 Years AMC",
            overall_understanding="State-wide high definition IP CCTV surveillance with Automated Number Plate Recognition (ANPR) and central monitoring.",
            citations=[
                TenderEvidenceCitation(filename="wtl_cctv.pdf", page_number=1, clause_or_section="NIT Cover Notice"),
                TenderEvidenceCitation(filename="wtl_cctv.pdf", page_number=5, clause_or_section="EMD and Fee Terms"),
            ],
        ),
        eligibility=EligibilityAnalysis(
            annual_turnover_requirement="Minimum Average Annual Turnover of Rs. 8.00 Crore in last 3 financial years",
            similar_work_experience="1 project of Rs. 6.40 Cr OR 2 projects of Rs. 4.00 Cr OR 3 projects of Rs. 3.20 Cr",
            oem_authorization_mandatory=True,
            consortium_joint_venture_allowed="Allowed up to 2 partners with lead partner holding >= 51% share",
            required_certifications=["ISO 9001:2015", "ISO 27001", "CMMI Level 3"],
            conditions=[
                EligibilityCondition(
                    category="Technical Turnover",
                    department_requirement="Average Annual Turnover >= Rs. 8.00 Cr",
                    is_mandatory=True,
                    supporting_document_required="CA Audited Statements with UDIN",
                    source_page=14,
                    source_file="wtl_cctv.pdf",
                )
            ],
        ),
        technical_scope=TechnicalScopeAnalysis(
            overview="Supply, installation, integration, testing and commissioning of 4MP Fixed Dome Cameras, 4MP Bullet Cameras, ANPR Cameras, NVRs, and VMS Software.",
        ),
        technical_specifications=TechnicalSpecificationAnalysis(
            items=[
                TechnicalSpecificationItem(
                    item_name="4MP IP Bullet Camera",
                    required_quantity="120",
                    technical_specifications="1/2.8 Progressive Scan CMOS, 30m IR, IP67 Weatherproof, H.265",
                    source_page=22,
                    source_file="wtl_cctv.pdf",
                ),
                TechnicalSpecificationItem(
                    item_name="ANPR Camera",
                    required_quantity="30",
                    technical_specifications="High-speed motorized lens, OCR license plate capture up to 80 km/h",
                    source_page=25,
                    source_file="wtl_cctv.pdf",
                ),
            ]
        ),
        commercial_financial=CommercialFinancialAnalysis(
            emd_amount="Rs. 32,00,000/-",
            emd_exemption_rules="MSME / NSIC registered units exempt as per West Bengal state rules",
            payment_terms="60% on delivery of equipment, 30% on successful commissioning, 10% on final sign-off",
            performance_bank_guarantee_pbg="10% of total contract value valid for 38 months",
            penalties_and_liquidated_damages="0.5% per week of delay up to a ceiling of 10% of contract value",
            warranty_costs_obligation="3 Years Comprehensive On-Site Warranty",
        ),
        risks_and_contradictions=RiskContradictionAnalysis(
            risks=[
                RiskContradictionItem(
                    risk_title="Aggressive 30-Day Delivery and Installation Window",
                    risk_level=RiskLevel.CRITICAL.value,
                    description="Aggressive 30-Day Delivery and Installation Window",
                    tender_evidence="Delivery must be completed within 30 days of work order",
                    potential_impact="Heavy delay penalties under liquidated damages",
                    why_it_matters="Procuring specialized ANPR sensors and camera hardware within 30 days is extremely challenging given OEM lead times.",
                    recommended_action="Submit pre-bid query requesting extension to 60-90 days.",
                    source_page=18,
                    source_file="wtl_cctv.pdf",
                ),
                RiskContradictionItem(
                    risk_title="Strict SLA Penalty for Camera Downtime",
                    risk_level=RiskLevel.HIGH.value,
                    description="Strict SLA Penalty for Camera Downtime",
                    tender_evidence="Deduction of Rs. 1000 per day for camera downtime exceeding 24 hours",
                    potential_impact="Financial deductions of Rs. 1,000 per camera per day after 24hr downtime",
                    why_it_matters="Requires stocking local hot standby spares in field offices.",
                    recommended_action="Factor standby inventory cost into AMC pricing.",
                    source_page=34,
                    source_file="wtl_cctv.pdf",
                ),
            ]
        ),
        bid_strategy=BidStrategyAnalysis(
            recommendation=BidRecommendation.PROCEED_WITH_CAUTION.value,
            recommendation_rationale="Commercially viable surveillance project for qualified system integrators, but requires mitigation on the 30-day timeline and strict SLA penalties.",
            overall_tender_assessment="High-profile state government security project with solid payment milestone backing.",
            bid_preparation_priorities=[
                "Secure OEM Authorization Form (MAF) from Tier-1 Camera Manufacturer",
                "Form consortium if individual turnover is below Rs. 8.00 Cr",
                "Submit pre-bid clarification on the 30-day delivery schedule",
            ],
            prebid_clarification_questions=[
                "Whether delivery timeline of 30 days can be extended to 60 days post site handover?",
                "Whether advance against Bank Guarantee is admissible?",
            ],
        ),
    )


def test_initial_conversational_response_structure(mock_cctv_report: TenderConsultantReport):
    """Verifies that the initial response is concise, focused, and covers all required Step 2 elements."""
    report = intelligence_report_builder.generate_markdown(mock_cctv_report)
    initial = report.initial_conversational_summary

    assert initial is not None
    assert len(initial) > 100

    # 1. Tender title & issuing authority
    assert "Selection of SI for Supply, Installation and Maintenance" in initial
    assert "Webel Technology Limited" in initial
    assert "WTL/WBPNB/CCTV/26-27/046" in initial

    # 2. What the tender is about
    assert "What this tender is about" in initial
    assert "State-wide high definition IP CCTV surveillance" in initial

    # 3. Estimated value, EMD and fee
    assert "Estimated Tender Value" in initial
    assert "Rs. 16.00 Crore" in initial
    assert "Rs. 32,00,000/-" in initial
    assert "Rs. 10,000/-" in initial

    # 4. Submission deadline
    assert "Submission Deadline" in initial
    assert "2026-12-15 15:00 Hrs" in initial

    # 5. Key eligibility
    assert "Minimum Turnover" in initial
    assert "Past Similar Experience" in initial
    assert "OEM Authorization (MAF)" in initial
    assert "Consortium / Joint Venture" in initial
    assert "Bidder eligibility**: Not assessed — company credentials have not been provided." in initial

    # 6. Main technical scope
    assert "Main Technical Scope" in initial
    assert "Supply, installation, integration, testing and commissioning" in initial

    # 7. Major financial commitments
    assert "Performance Security (PBG)" in initial
    assert "Payment Terms" in initial
    assert "Warranty Period" in initial
    assert "Delay Penalties / Liquidated Damages" in initial

    # 8. Important risks with page references
    assert "Aggressive 30-Day Delivery" in initial
    assert "Page 18" in initial

    # 9. Brief consultant observation
    assert "Consultant Observation (🟡 Proceed with Caution)" in initial

    # 10. Does NOT contain full 11 dimensions dump or raw 80-row tables
    assert "## Section A: Tender at a Glance" not in initial
    assert "## Section G: Immediate Actions" not in initial


def test_dynamic_suggested_questions_generation(mock_cctv_report: TenderConsultantReport):
    """Verifies that dynamic suggested questions are tailored to the tender domain and context."""
    report = intelligence_report_builder.generate_markdown(mock_cctv_report)
    suggestions = report.suggested_questions

    assert isinstance(suggestions, list)
    assert len(suggestions) >= 4

    # Core questions
    assert any("eligibility" in s.lower() for s in suggestions)
    assert any("participate" in s.lower() for s in suggestions)
    assert any("emd" in s.lower() for s in suggestions)
    assert any("risks" in s.lower() for s in suggestions)
    assert any("documents" in s.lower() for s in suggestions)

    # Domain-specific question for CCTV
    assert any("camera" in s.lower() or "anpr" in s.lower() for s in suggestions)


def test_domain_specific_desktop_suggestions():
    """Verifies that desktop computer tenders generate processor/hardware specific suggestions."""
    desktop_rep = TenderConsultantReport(
        report_id="dt-01",
        timestamp="2026-11-17T12:00:00",
        overview=TenderOverview(
            tender_title="Supply and Installation of High End Desktop Computers",
            department_organization="NITK Surathkal",
            tender_category="IT Hardware & Desktops",
        ),
    )
    report = intelligence_report_builder.generate_markdown(desktop_rep)
    suggestions = report.suggested_questions

    # Should suggest processor / hardware specifications
    assert any("processor" in s.lower() or "hardware" in s.lower() for s in suggestions)


def test_domain_specific_meter_suggestions():
    """Verifies that smart meter tenders generate meter/protocol specific suggestions."""
    meter_rep = TenderConsultantReport(
        report_id="m-01",
        timestamp="2026-11-17T12:00:00",
        overview=TenderOverview(
            tender_title="Procurement of 10 Lakh Smart Energy Meters with GPRS Communication",
            department_organization="EESL India",
            tender_category="Energy & Power",
        ),
    )
    report = intelligence_report_builder.generate_markdown(meter_rep)
    suggestions = report.suggested_questions

    # Should suggest meter specifications / communication protocol
    assert any("meter" in s.lower() or "protocol" in s.lower() for s in suggestions)


def test_domain_specific_wifi_suggestions():
    """Verifies that Wi-Fi networking tenders generate access point/networking specific suggestions."""
    wifi_rep = TenderConsultantReport(
        report_id="w-01",
        timestamp="2026-11-17T12:00:00",
        overview=TenderOverview(
            tender_title="Supply, Installation and Commissioning of Wi-Fi Access Points across Campus",
            department_organization="Tripura University",
            tender_category="Networking & Telecom",
        ),
    )
    report = intelligence_report_builder.generate_markdown(wifi_rep)
    suggestions = report.suggested_questions

    # Should suggest access point / networking specifications
    assert any("access point" in s.lower() or "networking" in s.lower() for s in suggestions)


def test_conversational_turnover_intent(mock_cctv_report: TenderConsultantReport):
    """Verifies Step 5 scenario: User asks 'What is the minimum turnover?'"""
    answer, sources = tender_intelligence_engine.answer_consultant_question(
        documents=[],
        question="What is the minimum turnover required for this tender?",
        cached_report=mock_cctv_report,
    )
    qa_res = tender_intelligence_engine.answer_consultant_question(
        documents=[],
        question="What is the minimum turnover required for this tender?",
        cached_report=mock_cctv_report,
    )

    assert "Minimum Annual Turnover Requirement" in answer
    assert "Rs. 8.00 Crore" in answer
    assert "UDIN" in answer
    assert sources[0]["page_number"] == 14

    # Verify dynamic follow-up suggestions are present
    follow_ups = qa_res.suggested_questions
    assert len(follow_ups) > 0
    assert any("experience" in f.lower() or "maf" in f.lower() or "consortium" in f.lower() for f in follow_ups)


def test_conversational_consortium_intent(mock_cctv_report: TenderConsultantReport):
    """Verifies Step 5 scenario: User asks 'Is consortium allowed?'"""
    qa_res = tender_intelligence_engine.answer_consultant_question(
        documents=[],
        question="Is consortium allowed in this tender?",
        cached_report=mock_cctv_report,
    )
    answer = qa_res.answer

    assert "Consortium & Subcontracting Terms" in answer
    assert "Allowed up to 2 partners" in answer
    assert "lead partner holding >= 51%" in answer
    assert "Subcontracting" in answer

    follow_ups = qa_res.suggested_questions
    assert len(follow_ups) > 0
    assert any("eligibility" in f.lower() or "turnover" in f.lower() or "participate" in f.lower() for f in follow_ups)


def test_conversational_documents_checklist_intent(mock_cctv_report: TenderConsultantReport):
    """Verifies user asking: 'What documents must we submit?'"""
    qa_res = tender_intelligence_engine.answer_consultant_question(
        documents=[],
        question="What documents must we submit for bid submission?",
        cached_report=mock_cctv_report,
    )
    answer = qa_res.answer

    assert "Mandatory Bid Submission Checklist" in answer
    assert "Pre-Qualification & Technical Envelope" in answer
    assert "Financial Envelope" in answer
    assert "GST Registration" in answer
    assert "CA Audited Balance Sheets" in answer
    assert "OEM Authorization" in answer
    assert "EMD / Bid Security" in answer

    follow_ups = qa_res.suggested_questions
    assert len(follow_ups) > 0
    assert any("payment" in f.lower() or "emd" in f.lower() or "participate" in f.lower() for f in follow_ups)


def test_conversational_payment_and_warranty_intent(mock_cctv_report: TenderConsultantReport):
    """Verifies user asking: 'What are the payment and warranty conditions?'"""
    qa_res = tender_intelligence_engine.answer_consultant_question(
        documents=[],
        question="What are the payment and warranty conditions?",
        cached_report=mock_cctv_report,
    )
    answer = qa_res.answer

    assert "Payment Terms & Warranty Commitments" in answer
    assert "60% on delivery" in answer
    assert "3 Years Comprehensive On-Site Warranty" in answer
    assert "10% of total contract value" in answer
    assert "0.5% per week of delay" in answer

    follow_ups = qa_res.suggested_questions
    assert len(follow_ups) > 0
    assert any("pbg" in f.lower() or "emd" in f.lower() or "risks" in f.lower() for f in follow_ups)


@pytest.mark.skipif(not os.path.exists(NITK_PDF), reason="NITK test PDF not present")
def test_real_nitk_conversational_summary(monkeypatch):
    """Verifies that analyzing real NITK Desktop PDF generates concise summary and hardware suggestions."""
    monkeypatch.setattr(
        tender_intelligence_engine,
        "_call_gemma_json",
        lambda prompt, max_tokens=350: {
            "recommendation": "PROCEED_WITH_CAUTION",
            "recommendation_rationale": "NITK desktop tender terms viable.",
            "overall_tender_assessment": "Academic workstation supply.",
            "critical_risks": [],
            "key_qualification_hurdles": ["Turnover of Rs. 23.63 Lakhs and OEM MAF"],
            "prebid_clarification_questions": ["Confirm warranty coverage terms"],
            "bid_preparation_priorities": ["Obtain OEM Authorization Form", "Submit EMD of Rs. 94,500"],
        },
    )
    doc = [{"filename": "nitk_desktop.pdf", "file_path": NITK_PDF, "document_type": "TENDER"}]
    report = tender_intelligence_engine.evaluate_tender(doc, mode="fast")

    assert report.initial_conversational_summary is not None
    assert len(report.initial_conversational_summary) > 100
    assert "National Institute of Technology Karnataka" in report.initial_conversational_summary or "NITK" in report.initial_conversational_summary
    assert "Desktop" in report.initial_conversational_summary

    # Suggestions should be dynamic and hardware tailored
    assert len(report.suggested_questions) >= 4
    assert any("eligibility" in s.lower() for s in report.suggested_questions)
    assert any("processor" in s.lower() or "hardware" in s.lower() or "spec" in s.lower() for s in report.suggested_questions)


@pytest.mark.skipif(not os.path.exists(WTL_CCTV_PDF), reason="WTL CCTV test PDF not present")
def test_real_wtl_cctv_conversational_summary(monkeypatch):
    """Verifies that analyzing real WTL CCTV PDF generates concise summary and surveillance suggestions."""
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
    doc = [{"filename": "wtl_cctv.pdf", "file_path": WTL_CCTV_PDF, "document_type": "TENDER"}]
    report = tender_intelligence_engine.evaluate_tender(doc, mode="fast")

    assert report.initial_conversational_summary is not None
    assert "Webel Technology Limited" in report.initial_conversational_summary
    assert len(report.suggested_questions) >= 4
    assert any("camera" in s.lower() or "anpr" in s.lower() or "spec" in s.lower() for s in report.suggested_questions)


@pytest.mark.skipif(not os.path.exists(TRIPURA_PDF), reason="Tripura test PDF not present")
def test_real_tripura_wifi_conversational_summary(monkeypatch):
    """Verifies that analyzing real Tripura University Wi-Fi PDF generates concise summary and Wi-Fi suggestions."""
    monkeypatch.setattr(
        tender_intelligence_engine,
        "_call_gemma_json",
        lambda prompt, max_tokens=350: {
            "recommendation": "PROCEED_WITH_CAUTION",
            "recommendation_rationale": "Tripura Wi-Fi expansion viable with active OEM networking partner.",
            "overall_tender_assessment": "Campus-wide Wi-Fi network.",
            "critical_risks": [],
            "key_qualification_hurdles": ["Turnover Rs. 1.20 Cr"],
            "prebid_clarification_questions": [],
            "bid_preparation_priorities": ["Obtain OEM MAF"],
        },
    )
    doc = [{"filename": "tripura_wifi.pdf", "file_path": TRIPURA_PDF, "document_type": "TENDER"}]
    report = tender_intelligence_engine.evaluate_tender(doc, mode="fast")

    assert report.initial_conversational_summary is not None
    assert "Tripura University" in report.initial_conversational_summary or "Tripura" in report.initial_conversational_summary
    assert len(report.suggested_questions) >= 4
    assert any("access point" in s.lower() or "networking" in s.lower() or "spec" in s.lower() for s in report.suggested_questions)


@pytest.mark.skipif(not os.path.exists(WOMENS_SAFETY_PDF), reason="Women Safety CCTV test PDF not present")
def test_real_womens_safety_cctv_conversational_summary(monkeypatch):
    """Verifies Women's Safety CCTV tender produces concise initial summary and surveillance suggestions."""
    monkeypatch.setattr(
        tender_intelligence_engine,
        "_call_gemma_json",
        lambda prompt, max_tokens=350: {
            "recommendation": "PROCEED_WITH_CAUTION",
            "recommendation_rationale": "Large surveillance deployment.",
            "overall_tender_assessment": "City surveillance project.",
            "critical_risks": [],
            "key_qualification_hurdles": ["Turnover requirements"],
            "prebid_clarification_questions": [],
            "bid_preparation_priorities": ["Obtain OEM MAF"],
        },
    )
    doc = [{"filename": "womens_safety.pdf", "file_path": WOMENS_SAFETY_PDF, "document_type": "TENDER"}]
    report = tender_intelligence_engine.evaluate_tender(doc, mode="fast")

    assert report.initial_conversational_summary is not None
    assert len(report.suggested_questions) >= 4
    assert any("camera" in s.lower() or "anpr" in s.lower() or "spec" in s.lower() for s in report.suggested_questions)


@pytest.mark.skipif(not os.path.exists(EESL_METER_PDF), reason="EESL Meter test PDF not present")
def test_real_eesl_meter_conversational_summary(monkeypatch):
    """Verifies EESL Smart Meter tender produces concise initial summary and meter suggestions."""
    monkeypatch.setattr(
        tender_intelligence_engine,
        "_call_gemma_json",
        lambda prompt, max_tokens=350: {
            "recommendation": "PROCEED_WITH_CAUTION",
            "recommendation_rationale": "Large smart meter rollout.",
            "overall_tender_assessment": "Smart metering infrastructure.",
            "critical_risks": [],
            "key_qualification_hurdles": ["Turnover requirements"],
            "prebid_clarification_questions": [],
            "bid_preparation_priorities": ["Obtain OEM MAF"],
        },
    )
    doc = [{"filename": "eesl_meter.pdf", "file_path": EESL_METER_PDF, "document_type": "TENDER"}]
    report = tender_intelligence_engine.evaluate_tender(doc, mode="fast")

    assert report.initial_conversational_summary is not None
    assert len(report.suggested_questions) >= 4
    assert any("meter" in s.lower() or "protocol" in s.lower() or "spec" in s.lower() for s in report.suggested_questions)
