"""
Test suite validating:
1. No raw JSON is ever returned for Performance Security (PBG) or any follow-up question.
2. Every consultant Q&A answer is normalized into the 4 standard sections:
   - ### 📌 Answer
   - ### 📄 Tender Evidence
   - ### 💡 Consultant Interpretation
   - ### 🎯 Recommended Action
3. Initial tender opening briefing is conversational, readable, and well-structured without repetitive inline citations.
4. Detailed 11-dimension analysis dossier provides genuine consultant evaluations and eliminates repeated [ NOT SPECIFIED IN TENDER ].
"""

import json
import pytest
from backend.app.services.tender_intelligence.intelligence_engine import tender_intelligence_engine
from backend.app.services.tender_intelligence.intelligence_report_builder import intelligence_report_builder
from backend.app.services.tender_intelligence.intelligence_schema import (
    TenderConsultantReport,
    TenderOverview,
    EligibilityAnalysis,
    EligibilityCondition,
    TechnicalScopeAnalysis,
    TechnicalSpecificationAnalysis,
    TechnicalSpecificationItem,
    OEMRequirementAnalysis,
    ItemWiseComplianceMatrix,
    CommercialFinancialAnalysis,
    ContractualLegalAnalysis,
    RiskContradictionAnalysis,
    RiskContradictionItem,
    BidStrategyAnalysis,
    ActionRoadmap,
    ActionRoadmapItem,
    RiskLevel,
    BidRecommendation,
)


@pytest.fixture
def sample_consultant_report():
    """Builds a realistic mock TenderConsultantReport representing a CCTV tender."""
    return TenderConsultantReport(
        report_id="test_rpt_001",
        timestamp="2026-11-18T10:00:00",
        overview=TenderOverview(
            tender_title="Supply, Installation and Commissioning of CCTV Surveillance System",
            tender_reference_number="WTL/CCTV/2026/01",
            department_organization="Webel Technology Limited",
            end_user_beneficiary="Department of Health & Family Welfare",
            project_name="Hospital CCTV Infrastructure",
            project_location="West Bengal",
            tender_publishing_date="01-11-2026",
            bid_submission_deadline="25-11-2026 15:00",
            bid_opening_date="26-11-2026 15:30",
            estimated_project_value="None",  # Test fallback handling
            emd_value="Rs. 2,50,000/-",
            tender_fee="Rs. 5,000/-",
            contract_duration="3 Years",
            warranty_maintenance_period="3 Years Comprehensive On-site OEM Warranty",
            delivery_implementation_period="60 Days from Work Order",
            scope_of_work_summary="Supply, installation, cabling, testing, and commissioning of IP CCTV cameras with 3-year AMC.",
            overall_understanding="Strategic procurement aimed at upgrading hospital perimeter and ward security monitoring.",
            citations=[],
        ),
        eligibility=EligibilityAnalysis(
            annual_turnover_requirement="Rs. 5.0 Crores per annum in last 3 financial years",
            similar_work_experience="Completed at least 1 similar CCTV work order of Rs. 2.0 Crores or 2 of Rs. 1.25 Crores",
            oem_authorization_mandatory=True,
            consortium_joint_venture_allowed="Not permitted — Single bidder only",
            required_certifications=["ISO 9001:2015", "ISO 27001", "CMMI Level 3"],
            company_registration_requirements="Certificate of Incorporation, GST, PAN",
            conditions=[
                EligibilityCondition(
                    category="Financial Turnover",
                    department_requirement="Average Annual Turnover of Rs. 5.0 Crores",
                    supporting_document_required="CA Audited Balance Sheets with UDIN",
                    source_page=4,
                    source_file="WTL_CCTV_Tender.pdf",
                    is_mandatory=True,
                    disqualification_effect="Direct rejection at pre-qualification stage",
                )
            ],
            summary_assessment="Strict pre-qualification threshold requiring verifiable audited credentials and OEM MAF.",
        ),
        technical_scope=TechnicalScopeAnalysis(
            overview="Procurement and turnkey commissioning of 350+ IP dome and bullet cameras with NVR and storage.",
            scope_items=[],
        ),
        technical_specifications=TechnicalSpecificationAnalysis(
            items=[
                TechnicalSpecificationItem(
                    item_name="4MP IP Bullet Camera",
                    required_quantity="150 Nos",
                    technical_specifications="4MP CMOS sensor, 30m IR, IP67 weatherproof, H.265 compression, PoE supported",
                    mandatory_standards="UL, CE, FCC, BIS",
                    source_page=12,
                    source_file="WTL_CCTV_Tender.pdf",
                )
            ]
        ),
        oem_requirements=OEMRequirementAnalysis(
            oem_authorization_required=True,
            specific_brands_in_tender=[],
            oem_requirements=[],
            consultant_notes="Mandatory MAF on OEM letterhead required for both cameras and active switching hardware.",
        ),
        compliance_matrix=ItemWiseComplianceMatrix(items=[]),
        commercial_financial=CommercialFinancialAnalysis(
            payment_terms="70% against delivery, 20% on successful commissioning, 10% against PBG",
            advance_payment_allowed="Nil / Not Permitted",
            performance_bank_guarantee_pbg="10% of total contract value within 15 days of LOA",
            security_deposit="Covered under PBG",
            penalties_and_liquidated_damages="0.5% per week of delay up to a maximum cap of 10%",
            price_validity_period="180 Days",
            bidder_impact_analysis="Cash flow requires funding 20% commissioning gap before second milestone disbursement.",
        ),
        contractual_legal=ContractualLegalAnalysis(
            contract_duration="3 Years",
            termination_conditions="Termination for default, insolvency, or prolonged failure to deploy within 30 days.",
            dispute_resolution_and_jurisdiction="High Court at Calcutta",
        ),
        risks_and_contradictions=RiskContradictionAnalysis(
            risks=[
                RiskContradictionItem(
                    risk_title="Aggressive 60-Day Turnkey Delivery",
                    risk_level=RiskLevel.HIGH.value,
                    description="All cameras and passive cabling must be commissioned within 60 days.",
                    tender_evidence="All cameras and passive cabling must be commissioned within 60 days of LOA.",
                    source_page=8,
                    source_file="WTL_CCTV_Tender.pdf",
                    why_it_matters="OEM lead times typically run 4-6 weeks, leaving narrow window for civil conduit installation.",
                    potential_impact="Risk of 0.5% weekly liquidated damages.",
                    recommended_action="Secure supply commitment and pre-order confirmation with camera OEM immediately.",
                )
            ],
            contradictions_found=["Warranty section states 5 years on page 24 while overview mentions 3 years on page 3."],
            critical_risks_count=0,
            high_risks_count=1,
            medium_risks_count=0,
            low_risks_count=0,
        ),
        bid_strategy=BidStrategyAnalysis(
            recommendation=BidRecommendation.PROCEED.value,
            recommendation_rationale="Commercially viable opportunity with standard milestone payment terms and clear scope.",
            bid_preparation_priorities=["Secure OEM MAF for 4MP cameras", "Prepare CA turnover certificate with UDIN"],
            prebid_clarification_questions=["Clarify warranty period discrepancy between Page 3 (3 Years) and Page 24 (5 Years)."],
        ),
        action_roadmap=ActionRoadmap(
            checklist=[
                ActionRoadmapItem(
                    step_number=1,
                    activity="Procure OEM Manufacturer Authorization Form (MAF)",
                    reason="Mandatory pre-qualification condition",
                    priority="CRITICAL",
                )
            ]
        ),
        source_files=["WTL_CCTV_Tender.pdf"],
        total_pages_analyzed=42,
    )


def test_performance_security_qa_no_raw_json(sample_consultant_report):
    """Verifies that asking for PBG/Performance Security returns formatted Markdown, NOT raw JSON."""
    result = tender_intelligence_engine.answer_consultant_question(
        question="What is the Performance Security requirement?",
        cached_report=sample_consultant_report,
        documents=[],
    )

    ans = result.answer
    assert "{" not in ans and "}" not in ans, f"Answer must not contain raw JSON braces! Got: {ans}"
    assert "### 📌 Answer" in ans
    assert "### 📄 Tender Evidence" in ans
    assert "### 💡 Consultant Interpretation" in ans
    assert "### 🎯 Recommended Action" in ans
    assert "10%" in ans or "Performance Bank Guarantee" in ans
    assert result.timing_metrics["total_seconds"] < 1.0


def test_emd_qa_consistency(sample_consultant_report):
    """Verifies that asking for EMD produces the consistent 4-section structure."""
    result = tender_intelligence_engine.answer_consultant_question(
        question="What is the EMD value?",
        cached_report=sample_consultant_report,
        documents=[],
    )

    ans = result.answer
    assert "{" not in ans and "}" not in ans
    assert "### 📌 Answer" in ans
    assert "### 📄 Tender Evidence" in ans
    assert "### 💡 Consultant Interpretation" in ans
    assert "### 🎯 Recommended Action" in ans
    assert "2,50,000" in ans


def test_raw_json_normalization_safety():
    """Verifies that _normalize_consultant_answer correctly parses raw JSON / dict strings."""
    raw_gemma_json = json.dumps({
        "performance_security_requirement": "10% of contract value payable as Bank Guarantee within 15 days",
        "evidence": "Clause 8.2, Page 14",
        "implication": "Ties up credit limit for 3 years",
        "action": "Contact issuing bank early",
    })

    normalized = tender_intelligence_engine._normalize_consultant_answer(
        raw_answer=raw_gemma_json,
        question="What is PBG?",
        sources=[{"page_number": 14, "filename": "Tender.pdf"}],
    )

    assert "{" not in normalized and "}" not in normalized
    assert "### 📌 Answer" in normalized
    assert "10% of contract value" in normalized
    assert "### 📄 Tender Evidence" in normalized
    assert "### 💡 Consultant Interpretation" in normalized
    assert "### 🎯 Recommended Action" in normalized


def test_initial_conversational_response_quality(sample_consultant_report):
    """Verifies initial response is conversational, readable, and without ugly placeholders."""
    summary = intelligence_report_builder._build_initial_conversational_response(sample_consultant_report)

    assert "[ NOT SPECIFIED IN TENDER ]" not in summary
    assert "### 📋 Tender Briefing:" in summary
    assert "#### 🏛️ What This Tender Is About" in summary
    assert "#### ⚙️ Procurement Opportunity & Scope" in summary
    assert "#### 🎯 Key Eligibility Requirements" in summary
    assert "#### 💳 Key Financial Commitments" in summary
    assert "#### ⚠️ Critical Risks & Watchouts" in summary
    assert "#### 🎯 Preliminary Bid Recommendation:" in summary
    assert "Rs. 2,50,000/-" in summary
    assert "Rs. 5.0 Crores" in summary


def test_11_dimension_dossier_quality(sample_consultant_report):
    """Verifies detailed 11-dimension dossier contains consultant analysis sections and no raw empty dumps."""
    dossier = intelligence_report_builder._build_full_dossier(sample_consultant_report)

    assert "[ NOT SPECIFIED IN TENDER ]" not in dossier
    assert "## 1. 🏢 Tender Overview & Project Understanding" in dossier
    assert "## 2. 🎯 Bidder Eligibility & Pre-Qualification (PQ)" in dossier
    assert "## 7. 💰 Commercial & Financial Analysis" in dossier
    assert "### 📌 Requirement Summary" in dossier
    assert "### 🔍 Key Findings & Verified Evidence" in dossier
    assert "### 💡 Strategic Bidder Implications" in dossier
    assert "### 🎯 Consultant Recommendations" in dossier
