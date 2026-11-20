"""Typed Pydantic Schemas for MYGPT AI Tender Consultant."""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class EvidenceClassification(str, Enum):
    """Mandatory evidence tags to strictly enforce truth boundaries."""

    TENDER_REQUIREMENT = "[ TENDER REQUIREMENT ]"
    CONSULTANT_RECOMMENDATION = "[ CONSULTANT RECOMMENDATION ]"
    ASSUMPTION_CAVEAT = "[ ASSUMPTION / CAVEAT ]"
    NOT_SPECIFIED_IN_TENDER = "[ NOT SPECIFIED IN TENDER ]"
    NEEDS_CLARIFICATION = "[ NEEDS CLARIFICATION ]"


class RiskLevel(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class BidRecommendation(str, Enum):
    PROCEED = "Proceed"
    PROCEED_WITH_CAUTION = "Proceed with caution"
    HIGH_RISK = "High risk"
    HIGH_RISK_RECONSIDER = "High risk / reconsider participation"
    REQUIRES_CLARIFICATION = "Requires clarification before proceeding"
    NOT_RECOMMENDED = "Not recommended"
    DEADLINE_PASSED = "Deadline passed"
    INSUFFICIENT_INFORMATION = "Insufficient information"


class ComplianceStatus(str, Enum):
    CLEARLY_SPECIFIED = "Requirement clearly specified"
    PARTIALLY_SPECIFIED = "Requirement partially specified"
    UNCLEAR = "Requirement unclear"
    NOT_FOUND = "Requirement not found"
    CANNOT_VERIFY = "Cannot be verified from the tender"


class RequirementCategory(str, Enum):
    TECHNICAL = "Technical"
    ADMINISTRATIVE = "Administrative"
    STATUTORY = "Statutory"
    ELIGIBILITY = "Eligibility"
    OEM = "OEM"
    COMMERCIAL = "Commercial"


class IntelligentComplianceStatus(str, Enum):
    PENDING = "PENDING"
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class TenderEvidenceCitation(BaseModel):
    """Explicit source citation for any finding or condition."""

    filename: str
    page_number: int
    document_id: Optional[str] = None
    clause_or_section: Optional[str] = None
    source_text: Optional[str] = None
    classification: str = EvidenceClassification.TENDER_REQUIREMENT.value
    verification_status: str = "VERIFIED"


# ============================================================================
# Section A: Tender Overview
# ============================================================================

class TenderOverview(BaseModel):
    department_organization: str = Field(default="Not specified")
    sub_department_consignee: Optional[str] = None
    tender_inviting_authority: Optional[str] = None
    end_user_beneficiary: Optional[str] = None
    tender_title: str = Field(default="Not specified")
    tender_reference_number: str = Field(default="Not specified")
    project_name: Optional[str] = None
    tender_category: Optional[str] = None
    contract_type: Optional[str] = None
    tender_publishing_date: Optional[str] = None
    tender_publishing_date_page: Optional[int] = None
    bid_submission_deadline: Optional[str] = None
    bid_submission_deadline_page: Optional[int] = None
    bid_opening_date: Optional[str] = None
    bid_opening_date_page: Optional[int] = None
    financial_bid_opening_date: Optional[str] = None
    financial_bid_opening_page: Optional[int] = None
    estimated_project_value: Optional[str] = None
    estimated_project_value_page: Optional[int] = None
    emd_value: Optional[str] = None
    emd_page: Optional[int] = None
    tender_fee: Optional[str] = None
    tender_fee_page: Optional[int] = None
    project_location: Optional[str] = None
    scope_of_work_summary: str = Field(default="")
    delivery_implementation_period: Optional[str] = None
    contract_duration: Optional[str] = None
    warranty_maintenance_period: Optional[str] = None
    overall_understanding: str = Field(default="")
    citations: List[TenderEvidenceCitation] = Field(default_factory=list)


# ============================================================================
# Section B: Bidder Eligibility and Pre-Qualification
# ============================================================================

class EligibilityCondition(BaseModel):
    category: str  # Turnover, Past Experience, Technical Cert, Registration, OEM Auth, etc.
    department_requirement: str
    entity_role: str = "Main Bidder"  # Main Bidder, OEM, Consortium Member, Subcontractor / CSP, etc.
    clause_heading: Optional[str] = None
    verbatim_evidence: Optional[str] = None
    is_mandatory: bool = True
    supporting_document_required: str
    disqualification_effect: str = "Disqualification in Pre-Qualification / Technical stage"
    ambiguity_or_clarification: Optional[str] = None
    source_page: int
    source_file: str
    document_id: Optional[str] = None
    classification: str = EvidenceClassification.TENDER_REQUIREMENT.value


class EligibilityAnalysis(BaseModel):
    annual_turnover_requirement: Optional[str] = None
    annual_turnover_page: Optional[int] = None
    average_turnover_requirement: Optional[str] = None
    main_bidder_turnover: Optional[str] = None
    consortium_member_turnover: Optional[str] = None
    oem_turnover: Optional[str] = None
    subcontractor_partner_turnover: Optional[str] = None
    turnover_entity_breakdown: List[Dict[str, Any]] = Field(default_factory=list)
    similar_work_experience: Optional[str] = None
    similar_work_page: Optional[int] = None
    financial_eligibility_page: Optional[int] = None
    minimum_project_value: Optional[str] = None
    completed_projects_count: Optional[str] = None
    government_project_experience: Optional[str] = None
    required_certifications: List[str] = Field(default_factory=list)
    company_registration_requirements: Optional[str] = None
    gst_and_pan_requirements: Optional[str] = None
    oem_authorization_mandatory: bool = False
    consortium_joint_venture_allowed: Optional[str] = None
    conditions: List[EligibilityCondition] = Field(default_factory=list)
    summary_assessment: str = Field(default="")


# ============================================================================
# Section C: Technical Scope Analysis
# ============================================================================

class TechnicalScopeItem(BaseModel):
    area: str  # Hardware, Software, Networking, Infrastructure, Integration, Training, SLA, etc.
    description: str
    purpose: str
    mandatory_standards: Optional[str] = None
    source_page: int
    source_file: str
    document_id: Optional[str] = None


class TechnicalScopeAnalysis(BaseModel):
    overview: str = Field(default="")
    scope_items: List[TechnicalScopeItem] = Field(default_factory=list)
    testing_and_commissioning_obligations: Optional[str] = None
    training_obligations: Optional[str] = None
    maintenance_and_amc_obligations: Optional[str] = None
    sla_requirements: Optional[str] = None


# ============================================================================
# Section D: Technical Specification Analysis
# ============================================================================

class TechnicalSpecificationItem(BaseModel):
    item_name: str
    item_number: Optional[str] = None
    required_quantity: Optional[str] = None
    unit_of_measurement: Optional[str] = None
    technical_specifications: str
    clause_heading: Optional[str] = None
    table_source: Optional[str] = None
    subsystem_or_category: Optional[str] = None
    table_columns: Optional[List[str]] = None
    table_row_data: Optional[Dict[str, str]] = None
    is_inherited_header: bool = False
    raw_table_row: Optional[str] = None
    verbatim_evidence: Optional[str] = None
    minimum_performance: Optional[str] = None
    mandatory_standards: Optional[str] = None
    required_certifications: Optional[str] = None
    oem_brand_model_mentioned: Optional[str] = None
    compatibility_requirements: Optional[str] = None
    installation_support_obligations: Optional[str] = None
    source_page: int
    source_file: str
    document_id: Optional[str] = None


class TechnicalSpecificationAnalysis(BaseModel):
    items: List[TechnicalSpecificationItem] = Field(default_factory=list)
    subsystems: List[str] = Field(default_factory=list)
    structured_tables_count: int = 0
    overall_spec_evaluation: str = Field(default="")


# ============================================================================
# Section E: OEM and Product Requirement Analysis
# ============================================================================

class OEMRequirementItem(BaseModel):
    requirement_name: str
    is_mandatory: bool = True
    details: str
    specific_brands_mentioned: Optional[str] = None
    authorization_form_required: bool = True
    warranty_support_conditions: Optional[str] = None
    source_page: int
    source_file: str
    document_id: Optional[str] = None
    classification: str = EvidenceClassification.TENDER_REQUIREMENT.value


class OEMRequirementAnalysis(BaseModel):
    has_oem_conditions: bool = False
    oem_authorization_required: bool = False
    specific_brands_in_tender: List[str] = Field(default_factory=list)
    oem_requirements: List[OEMRequirementItem] = Field(default_factory=list)
    consultant_notes: str = Field(default="")


# ============================================================================
# Section F: Item-Wise Compliance Analysis Matrix & Bidder Readiness
# ============================================================================

class RequiredBidderDocument(BaseModel):
    document_name: str
    category: str = "Administrative"  # Technical, Administrative, Statutory, Eligibility, OEM, Commercial
    is_mandatory: bool = True
    submission_format: Optional[str] = None  # e.g., "Original on Stamp Paper", "CA Audited Copy with UDIN", "OEM Letterhead"
    tender_reference: Optional[str] = None
    source_page: Optional[int] = None
    source_file: Optional[str] = None
    document_id: Optional[str] = None
    notes: Optional[str] = None


class CategoryReadiness(BaseModel):
    category: str
    total_requirements: int = 0
    mandatory_count: int = 0
    pending_count: int = 0
    compliant_count: int = 0
    non_compliant_count: int = 0
    needs_review_count: int = 0
    readiness_percentage: float = 0.0


class BidderReadinessSummary(BaseModel):
    total_requirements: int = 0
    mandatory_requirements: int = 0
    pending_count: int = 0
    compliant_count: int = 0
    non_compliant_count: int = 0
    needs_review_count: int = 0
    overall_readiness_percentage: float = 0.0
    critical_unresolved_count: int = 0
    critical_blockers: List[str] = Field(default_factory=list)
    missing_documents_count: int = 0
    categories: Dict[str, CategoryReadiness] = Field(default_factory=dict)


class ComplianceMatrixItem(BaseModel):
    item: str
    tender_requirement: str
    mandatory_specification: str
    tender_reference: str  # e.g., "Tendernotice.pdf | Page 14"
    compliance_assessment: str = "PENDING"  # one of ComplianceStatus or IntelligentComplianceStatus
    remarks: str = ""
    document_id: Optional[str] = None

    # Enhanced Stage 2 Fields
    requirement_id: str = ""
    category: str = "Technical"  # Technical, Administrative, Statutory, Eligibility, OEM, Commercial
    is_mandatory: bool = True
    compliance_status: str = "PENDING"  # PENDING, COMPLIANT, NON_COMPLIANT, NEEDS_REVIEW, NOT_APPLICABLE
    bidder_evidence: Optional[str] = None
    source_page: Optional[int] = None
    source_file: Optional[str] = None
    clause_reference: Optional[str] = None
    required_document_type: Optional[str] = None
    validation_status: str = "VERIFIED"


class ItemWiseComplianceMatrix(BaseModel):
    items: List[ComplianceMatrixItem] = Field(default_factory=list)
    compliance_summary: str = Field(default="")
    required_documents: List[RequiredBidderDocument] = Field(default_factory=list)
    readiness_summary: Optional[BidderReadinessSummary] = None


# ============================================================================
# Section G: Commercial and Financial Analysis
# ============================================================================

class CommercialFinancialAnalysis(BaseModel):
    estimated_value: Optional[str] = None
    estimated_value_page: Optional[int] = None
    emd_amount: Optional[str] = None
    emd_page: Optional[int] = None
    emd_exemption_rules: Optional[str] = None
    emd_amount_and_mode: Optional[str] = None
    tender_fee: Optional[str] = None
    tender_fee_details: Optional[str] = None
    tender_fee_page: Optional[int] = None
    financial_bid_opening_date: Optional[str] = None
    financial_bid_opening_page: Optional[int] = None
    payment_terms: str = Field(default="Not specified")
    payment_terms_page: Optional[int] = None
    advance_payment_allowed: Optional[str] = None
    milestone_payments: Optional[str] = None
    retention_amount: Optional[str] = None
    performance_bank_guarantee_pbg: Optional[str] = None
    security_deposit: Optional[str] = None
    security_deposit_page: Optional[int] = None
    taxes_and_duties_terms: Optional[str] = None
    price_validity_period: Optional[str] = None
    price_escalation_clause: Optional[str] = None
    penalties_and_liquidated_damages: str = Field(default="Not specified")
    penalties_and_liquidated_damages_page: Optional[int] = None
    warranty_costs_obligation: Optional[str] = None
    amc_maintenance_costs_obligation: Optional[str] = None
    bidder_impact_analysis: str = Field(default="")
    citations: List[TenderEvidenceCitation] = Field(default_factory=list)


# ============================================================================
# Section H: Contractual and Legal Conditions
# ============================================================================

class ContractualClauseItem(BaseModel):
    clause_type: str  # Agreement, Delivery, Penalty, Indemnity, Termination, Dispute, Force Majeure
    summary: str
    clause_heading: Optional[str] = None
    verbatim_evidence: Optional[str] = None
    risk_level: str = RiskLevel.MEDIUM.value
    source_page: int
    source_file: str
    document_id: Optional[str] = None


class ContractualLegalAnalysis(BaseModel):
    agreement_requirements: Optional[str] = None
    contract_duration: Optional[str] = None
    delivery_obligations: Optional[str] = None
    delay_penalties: Optional[str] = None
    indemnity_and_liability: Optional[str] = None
    insurance_requirements: Optional[str] = None
    confidentiality: Optional[str] = None
    termination_conditions: Optional[str] = None
    dispute_resolution_and_jurisdiction: Optional[str] = None
    force_majeure: Optional[str] = None
    significant_risk_clauses: List[ContractualClauseItem] = Field(default_factory=list)


# ============================================================================
# Section I: Risk and Contradiction Analysis
# ============================================================================

class RiskContradictionItem(BaseModel):
    risk_title: str
    risk_level: str = RiskLevel.HIGH.value  # Critical, High, Medium, Low
    description: str
    tender_evidence: str
    source_page: int
    source_file: str
    document_id: Optional[str] = None
    why_it_matters: str
    potential_impact: str
    recommended_action: str


class RiskContradictionAnalysis(BaseModel):
    critical_risks_count: int = 0
    high_risks_count: int = 0
    medium_risks_count: int = 0
    low_risks_count: int = 0
    risks: List[RiskContradictionItem] = Field(default_factory=list)
    contradictions_found: List[str] = Field(default_factory=list)
    missing_technical_information: List[str] = Field(default_factory=list)
    overall_risk_verdict: str = Field(default="")


# ============================================================================
# Section J: Bid Strategy and Consultant Recommendations
# ============================================================================

class BidStrategyAnalysis(BaseModel):
    recommendation: str = BidRecommendation.PROCEED_WITH_CAUTION.value
    recommendation_rationale: str = Field(default="")
    overall_tender_assessment: str = Field(default="")
    key_qualification_hurdles: List[str] = Field(default_factory=list)
    technical_preparation_strategy: str = Field(default="")
    required_oem_documents: List[str] = Field(default_factory=list)
    required_financial_documents: List[str] = Field(default_factory=list)
    required_supporting_certificates: List[str] = Field(default_factory=list)
    prebid_clarification_questions: List[str] = Field(default_factory=list)
    major_risks_to_resolve_before_submission: List[str] = Field(default_factory=list)
    bid_preparation_priorities: List[str] = Field(default_factory=list)
    recommended_next_steps: List[str] = Field(default_factory=list)


# ============================================================================
# Section K: Final Action Roadmap
# ============================================================================

class ActionRoadmapItem(BaseModel):
    step_number: int
    activity: str
    reason: str
    relevant_tender_page: Optional[int] = None
    source_file: Optional[str] = None
    document_id: Optional[str] = None
    priority: str = "High"  # High, Medium, Low
    deadline_or_stage: Optional[str] = None


class ActionRoadmap(BaseModel):
    checklist: List[ActionRoadmapItem] = Field(default_factory=list)
    timeline_summary: str = Field(default="")


# ============================================================================
# Complete Master Report
# ============================================================================

class TenderConsultantReport(BaseModel):
    """Unified master dossier from MYGPT AI Tender Consultant."""

    report_id: str
    timestamp: str
    document_ids: List[str] = Field(default_factory=list)
    source_files: List[str] = Field(default_factory=list)
    file_hashes: List[str] = Field(default_factory=list)
    total_pages_analyzed: int = 0
    is_multi_document_package: bool = False
    package_name: Optional[str] = None
    model_used: str = "Gemma-4-E2B-It-Q4_K_M"

    # 11 Consultant Dimensions
    overview: TenderOverview = Field(default_factory=TenderOverview)
    eligibility: EligibilityAnalysis = Field(default_factory=EligibilityAnalysis)
    technical_scope: TechnicalScopeAnalysis = Field(default_factory=TechnicalScopeAnalysis)
    technical_specifications: TechnicalSpecificationAnalysis = Field(default_factory=TechnicalSpecificationAnalysis)
    oem_requirements: OEMRequirementAnalysis = Field(default_factory=OEMRequirementAnalysis)
    compliance_matrix: ItemWiseComplianceMatrix = Field(default_factory=ItemWiseComplianceMatrix)
    commercial_financial: CommercialFinancialAnalysis = Field(default_factory=CommercialFinancialAnalysis)
    contractual_legal: ContractualLegalAnalysis = Field(default_factory=ContractualLegalAnalysis)
    risks_and_contradictions: RiskContradictionAnalysis = Field(default_factory=RiskContradictionAnalysis)
    bid_strategy: BidStrategyAnalysis = Field(default_factory=BidStrategyAnalysis)
    action_roadmap: ActionRoadmap = Field(default_factory=ActionRoadmap)

    # Presentation / Markdown export
    initial_conversational_summary: str = ""
    suggested_questions: List[str] = Field(default_factory=list)
    consultant_briefing_markdown: str = ""
    executive_summary_markdown: str = ""
    full_report_markdown: str = ""

    # Metadata & Quality Control
    validation_status: str = "VERIFIED"
    verification_notes: List[str] = Field(default_factory=list)
    unreadable_pages: List[int] = Field(default_factory=list)
    cache_hit: bool = False
    stages_invoking_gemma: List[str] = Field(default_factory=list)
    elapsed_seconds: float = 0.0
    processing_latency_breakdown: Dict[str, float] = Field(default_factory=dict)
