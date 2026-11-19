"""
Test Suite: MYGPT AI Tender Consultant - Full 11-Dimension Export & Print Dossier Verification
Ensures that exporting or printing the report:
1. Exposes all 11 dimensions and complete tender intelligence (not just current tab/page).
2. Formats all sections cleanly without raw unformatted placeholders.
3. Contains full tables, citations, and strategic consultant recommendations.
"""

import pytest
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
    OEMRequirementItem,
    ItemWiseComplianceMatrix,
    ComplianceMatrixItem,
    CommercialFinancialAnalysis,
    ContractualLegalAnalysis,
    ContractualClauseItem,
    RiskContradictionAnalysis,
    RiskContradictionItem,
    BidStrategyAnalysis,
    ActionRoadmap,
    ActionRoadmapItem,
    RiskLevel,
    BidRecommendation,
)


@pytest.fixture
def mock_consultant_report() -> TenderConsultantReport:
    """Constructs a fully populated TenderConsultantReport with authentic data across all 11 dimensions."""
    report = TenderConsultantReport(
        report_id="RPT_WTL_TEST_001",
        timestamp="2026-11-18T10:00:00",
        source_files=["WTL_CCTV_Tender.pdf"],
        total_pages_analyzed=45,
        model_used="Gemma 4 E2B Local",
        overview=TenderOverview(
            department_organization="Webel Technology Limited (WTL)",
            end_user_beneficiary="Aliah University, New Town Campus, Kolkata",
            tender_title="Selection of SI for Supply, Installation & Maintenance of CCTV System",
            tender_reference_number="WTL/CC/2026/042",
            bid_submission_deadline="15-12-2026 15:00 HRS",
            estimated_project_value=None,
            emd_value="Rs. 1,00,000/- via online portal",
            tender_fee="Rs. 1,000/- non-refundable",
            project_location="Kolkata, West Bengal",
            scope_of_work_summary="Supply, installation, commissioning and 3 years maintenance of IP CCTV cameras.",
            overall_understanding="Enterprise surveillance system deployment across university campus."
        ),
        eligibility=EligibilityAnalysis(
            annual_turnover_requirement="Minimum Rs. 50 Lakhs in each of last 3 FYs",
            similar_work_experience="At least 1 completed project of Rs. 40 Lakhs or 2 of Rs. 25 Lakhs",
            required_certifications=["ISO 9001:2015", "ISO 27001"],
            oem_authorization_mandatory=True,
            conditions=[
                EligibilityCondition(
                    category="Financial",
                    department_requirement="Average Annual Turnover >= 50 Lakhs",
                    is_mandatory=True,
                    supporting_document_required="CA Audited Balance Sheets with UDIN",
                    disqualification_effect="Direct rejection",
                    source_page=12,
                    source_file="WTL_CCTV_Tender.pdf"
                )
            ],
            summary_assessment="Bidder must comply with strict turnover and past performance thresholds."
        ),
        technical_scope=TechnicalScopeAnalysis(
            overview="Supply and installation of 120 IP cameras, NVRs, PoE switches and monitoring workstations."
        ),
        technical_specifications=TechnicalSpecificationAnalysis(
            items=[
                TechnicalSpecificationItem(
                    item_name="4MP Fixed Dome IP Camera",
                    required_quantity="80 Nos",
                    technical_specifications="1/3 CMOS, 30fps @ 4MP, H.265+, 30m IR, IP67, IK10",
                    mandatory_standards="UL, CE, FCC, BIS",
                    oem_brand_model_mentioned="Honeywell / Hikvision / CP Plus or equivalent",
                    source_page=22,
                    source_file="WTL_CCTV_Tender.pdf"
                )
            ],
            subsystems=["Camera Subsystem", "Recording Subsystem"],
            overall_spec_evaluation="Enterprise grade surveillance hardware requiring OEM technical backing."
        ),
        oem_requirements=OEMRequirementAnalysis(
            oem_authorization_required=True,
            specific_brands_in_tender=["Honeywell", "Hikvision"],
            oem_requirements=[
                OEMRequirementItem(
                    requirement_name="Tender Specific MAF",
                    is_mandatory=True,
                    details="OEM must guarantee 3-year warranty and spares supply",
                    source_page=14,
                    source_file="WTL_CCTV_Tender.pdf"
                )
            ],
            consultant_notes="Mandatory manufacturer authorization required for all active camera items."
        ),
        compliance_matrix=ItemWiseComplianceMatrix(
            items=[
                ComplianceMatrixItem(
                    item="Camera Resolution",
                    tender_requirement="Minimum 4 Megapixels with 30fps real time streaming",
                    mandatory_specification="4MP True WDR >= 120dB",
                    tender_reference="Clause 4.1.2, Page 23",
                    compliance_assessment="CLEARLY SPECIFIED",
                    remarks="Directly compliant with proposed Tier-1 camera models"
                )
            ],
            compliance_summary="100% compliance mandatory across all technical specifications."
        ),
        commercial_financial=CommercialFinancialAnalysis(
            estimated_value=None,
            emd_amount="Rs. 1,00,000/-",
            emd_exemption_rules="MSME / NSIC valid certificate holders exempt from EMD",
            performance_bank_guarantee_pbg="3% of contract value valid for 39 months",
            payment_terms="70% on delivery, 20% on installation and SAT sign-off, 10% after 90 days of smooth operation",
            penalties_and_liquidated_damages="0.5% per week of delay subject to a ceiling of 10% of total order value",
            bidder_impact_analysis="Ensure liquidity for 3% PBG and 30-day working capital cycle."
        ),
        contractual_legal=ContractualLegalAnalysis(
            contract_duration="3 Years from commissioning sign-off",
            termination_conditions="30 days written notice for default or non-performance",
            dispute_resolution_and_jurisdiction="Arbitration in Kolkata under Indian Arbitration Act",
            indemnity_and_liability="Bidder indemnifies WTL against all third-party intellectual property infringement claims",
            significant_risk_clauses=[
                ContractualClauseItem(
                    clause_type="Liquidated Damages",
                    summary="Delay penalty of 0.5% per week capped at 10%",
                    risk_level="High",
                    source_page=31,
                    source_file="WTL_CCTV_Tender.pdf"
                )
            ]
        ),
        risks_and_contradictions=RiskContradictionAnalysis(
            critical_risks_count=0,
            high_risks_count=1,
            medium_risks_count=2,
            low_risks_count=0,
            risks=[
                RiskContradictionItem(
                    risk_title="Strict SLA Penalty Ceiling",
                    description="Delay penalty risk capped at 10%",
                    risk_level=RiskLevel.HIGH,
                    tender_evidence="Liquidated damages of 0.5% per week up to 10% total value",
                    source_page=31,
                    source_file="WTL_CCTV_Tender.pdf",
                    why_it_matters="Tight installation deadline makes delays financially punitive",
                    potential_impact="Direct deduction from progressive milestone invoices",
                    recommended_action="Confirm camera supply timelines with OEM before bid submission"
                )
            ],
            contradictions_found=[
                "Section 2 stipulates 30 days implementation, while BOQ delivery notes 45 days."
            ],
            overall_risk_verdict="Manageable operational risk with clear mitigation path via pre-bid query."
        ),
        bid_strategy=BidStrategyAnalysis(
            recommendation=BidRecommendation.PROCEED_WITH_CAUTION,
            recommendation_rationale="Bidder meets turnover threshold; must resolve 30 vs 45 day timeline contradiction in pre-bid meeting.",
            overall_tender_assessment="Strong commercial opportunity for qualified surveillance systems integrators.",
            key_qualification_hurdles=["Turnover >= 50L", "Valid OEM MAF"],
            technical_preparation_strategy="Finalize camera datasheets matching 4MP True WDR specifications.",
            required_oem_documents=["Tender Specific MAF", "Spares Availability Guarantee"],
            required_financial_documents=["Audited Balance Sheets 2023-2026", "CA Turnover Certificate"],
            required_supporting_certificates=["ISO 9001:2015", "GST Registration"],
            prebid_clarification_questions=[
                "Clause 3.1 vs BOQ Note: Please clarify whether project delivery period is 30 calendar days or 45 days."
            ],
            bid_preparation_priorities=["Procure OEM MAF", "Submit Pre-Bid Query on Timeline", "Draft Technical Compliance Matrix"],
            recommended_next_steps=["Submit pre-bid clarification on delivery timeline."]
        ),
        action_roadmap=ActionRoadmap(
            checklist=[
                ActionRoadmapItem(
                    step_number=1,
                    activity="Submit Pre-Bid Query on Timeline Contradiction",
                    reason="Clarify 30 vs 45 days implementation period before bid submission",
                    relevant_tender_page=14,
                    source_file="WTL_CCTV_Tender.pdf",
                    priority="High"
                )
            ],
            timeline_summary="Execute step 1 before pre-bid cutoff date."
        ),
        validation_status="VERIFIED"
    )

    report.full_report_markdown = intelligence_report_builder._build_full_dossier(report)
    return report


def test_full_dossier_markdown_includes_all_11_dimensions(mock_consultant_report):
    """Verify that full_report_markdown covers all 11 dimensions with zero raw 'NOT_FOUND' leaks."""
    md = mock_consultant_report.full_report_markdown
    assert md is not None and len(md) > 500

    # Verify all 11 dimension headers exist
    for dim_num in range(1, 12):
        assert f"## {dim_num}." in md, f"Dimension {dim_num} missing from full dossier markdown!"

    # Verify key evidence items are included
    assert "Webel Technology Limited (WTL)" in md
    assert "WTL/CC/2026/042" in md
    assert "Minimum Rs. 50 Lakhs" in md
    assert "4MP Fixed Dome IP Camera" in md
    assert "Tender Specific MAF" in md
    assert "Strict SLA Penalty Ceiling" in md
    assert "Submit Pre-Bid Query on Timeline Contradiction" in md

    # Ensure no raw unformatted placeholder leaks
    assert "NOT_FOUND" not in md
    assert "[ NOT SPECIFIED IN TENDER ]" not in md


def test_export_includes_contradictions_and_prebid_queries(mock_consultant_report):
    """Ensure pre-bid queries and identified contradictions are preserved in the export."""
    md = mock_consultant_report.full_report_markdown
    assert "Section 2 stipulates 30 days implementation" in md
    assert "Clause 3.1 vs BOQ Note: Please clarify whether project delivery period is 30 calendar days or 45 days." in md
