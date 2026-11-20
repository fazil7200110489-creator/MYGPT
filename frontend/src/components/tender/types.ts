/**
 * TypeScript Schema Definitions for MYGPT AI Tender Consultant
 * Strictly preserves backend schema defined in backend/app/services/tender_intelligence/intelligence_schema.py
 */

export type VerificationStatusType =
  | 'VERIFIED'
  | 'PARTIALLY VERIFIED'
  | 'CONFLICT DETECTED'
  | 'CONFLICT DETECTED — VERIFICATION REQUIRED'
  | 'NOT FOUND'
  | 'NOT FOUND IN SOURCE'
  | 'NOT APPLICABLE'
  | 'NEEDS REVIEW'
  | 'REQUIREMENT EXTRACTED'
  | 'VERIFICATION REQUIRED'
  | 'BIDDER INFORMATION REQUIRED'
  | 'NOT EVALUATED'
  | 'SUBMISSION DEADLINE PASSED'

export type ComplianceEvaluationStatus =
  | 'REQUIREMENT EXTRACTED'
  | 'COMPLIANT'
  | 'NON-COMPLIANT'
  | 'PARTIALLY COMPLIANT'
  | 'VERIFICATION REQUIRED'
  | 'NOT EVALUATED'

export type BidderEligibilityStatus =
  | 'MET'
  | 'NOT MET'
  | 'UNKNOWN'
  | 'VERIFICATION REQUIRED'

export type BidVerdictType =
  | 'Proceed'
  | 'Proceed with Caution'
  | 'Do Not Proceed'
  | 'Needs Manual Review'

export interface TenderEvidenceCitation {
  filename: string
  page_number: number
  document_id?: string
  clause_or_section?: string
  source_text?: string
  classification?: string
}

export interface TenderOverviewData {
  department_organization: string
  sub_department_consignee?: string
  tender_inviting_authority?: string
  end_user_beneficiary?: string
  tender_title: string
  tender_reference_number: string
  project_name?: string
  tender_category?: string
  contract_type?: string
  tender_publishing_date?: string
  bid_submission_deadline?: string
  bid_opening_date?: string
  estimated_project_value?: string
  emd_value?: string
  tender_fee?: string
  project_location?: string
  scope_of_work_summary: string
  delivery_implementation_period?: string
  contract_duration?: string
  warranty_maintenance_period?: string
  overall_understanding: string
  citations?: TenderEvidenceCitation[]
}

export interface EligibilityConditionItem {
  category: string
  department_requirement: string
  entity_role?: string
  clause_heading?: string
  verbatim_evidence?: string
  is_mandatory: boolean
  supporting_document_required: string
  disqualification_effect: string
  ambiguity_or_clarification?: string
  source_page: number
  source_file: string
  document_id?: string
  classification?: string
}

export interface EligibilityData {
  annual_turnover_requirement?: string
  average_turnover_requirement?: string
  main_bidder_turnover?: string
  consortium_member_turnover?: string
  oem_turnover?: string
  subcontractor_partner_turnover?: string
  turnover_entity_breakdown?: Array<Record<string, any>>
  similar_work_experience?: string
  minimum_project_value?: string
  completed_projects_count?: string
  government_project_experience?: string
  required_certifications: string[]
  company_registration_requirements?: string
  gst_and_pan_requirements?: string
  oem_authorization_mandatory: boolean
  consortium_joint_venture_allowed?: string
  conditions: EligibilityConditionItem[]
  summary_assessment: string
}

export interface TechnicalScopeItem {
  area: string
  description: string
  purpose: string
  mandatory_standards?: string
  source_page: number
  source_file: string
  document_id?: string
}

export interface TechnicalScopeData {
  overview: string
  scope_items: TechnicalScopeItem[]
  testing_and_commissioning_obligations?: string
  training_obligations?: string
  maintenance_and_amc_obligations?: string
  sla_requirements?: string
}

export interface TechnicalSpecificationItem {
  item_name: string
  category?: string
  required_quantity?: string
  unit_of_measurement?: string
  technical_specifications: string
  clause_heading?: string
  table_source?: string
  subsystem_or_category?: string
  table_columns?: string[]
  table_row_data?: Record<string, string>
  is_inherited_header?: boolean
  raw_table_row?: string
  verbatim_evidence?: string
  minimum_performance?: string
  mandatory_standards?: string
  required_certifications?: string
  oem_brand_model_mentioned?: string
  compatibility_requirements?: string
  installation_support_obligations?: string
  source_page: number
  source_file: string
  document_id?: string
}

export interface TechnicalSpecificationsData {
  items: TechnicalSpecificationItem[]
  subsystems: string[]
  structured_tables_count?: number
  overall_spec_evaluation: string
}

export interface OEMRequirementItem {
  requirement_name: string
  is_mandatory: boolean
  details: string
  specific_brands_mentioned?: string
  authorization_form_required: boolean
  warranty_support_conditions?: string
  source_page: number
  source_file: string
  document_id?: string
}

export interface OEMRequirementsData {
  has_oem_conditions?: boolean
  oem_authorization_required: boolean
  specific_brands_in_tender: string[]
  oem_requirements: OEMRequirementItem[]
  consultant_notes: string
}

export interface RequiredBidderDocument {
  document_name: string
  category?: string
  is_mandatory?: boolean
  submission_format?: string
  tender_reference?: string
  source_page?: number
  source_file?: string
  document_id?: string
  notes?: string
}

export interface CategoryReadiness {
  category: string
  total_requirements: number
  mandatory_count: number
  pending_count: number
  compliant_count: number
  non_compliant_count: number
  needs_review_count: number
  readiness_percentage: number
}

export interface BidderReadinessSummary {
  total_requirements: number
  mandatory_requirements: number
  pending_count: number
  compliant_count: number
  non_compliant_count: number
  needs_review_count: number
  overall_readiness_percentage: number
  critical_unresolved_count: number
  critical_blockers?: string[]
  missing_documents_count?: number
  categories?: Record<string, CategoryReadiness>
}

export interface ComplianceMatrixItem {
  item: string
  tender_requirement: string
  mandatory_specification: string
  tender_reference: string
  compliance_assessment: string
  remarks: string
  document_id?: string

  // Enhanced Stage 2 Fields
  requirement_id?: string
  category?: string
  is_mandatory?: boolean
  compliance_status?: string
  bidder_evidence?: string
  source_page?: number
  source_file?: string
  clause_reference?: string
  required_document_type?: string
  validation_status?: string
}

export interface ComplianceMatrixData {
  items: ComplianceMatrixItem[]
  compliance_summary: string
  required_documents?: RequiredBidderDocument[]
  readiness_summary?: BidderReadinessSummary
}

export interface CommercialFinancialData {
  estimated_value?: string
  emd_amount?: string
  emd_exemption_rules?: string
  emd_amount_and_mode?: string
  tender_fee_details?: string
  payment_terms: string
  advance_payment_allowed?: string
  milestone_payments?: string
  retention_amount?: string
  performance_bank_guarantee_pbg?: string
  security_deposit?: string
  taxes_and_duties_terms?: string
  price_validity_period?: string
  price_escalation_clause?: string
  penalties_and_liquidated_damages: string
  warranty_costs_obligation?: string
  amc_maintenance_costs_obligation?: string
  bidder_impact_analysis: string
  citations?: TenderEvidenceCitation[]
}

export interface ContractualClauseItem {
  clause_type: string
  summary: string
  clause_heading?: string
  verbatim_evidence?: string
  risk_level: string
  source_page: number
  source_file: string
  document_id?: string
}

export interface ContractualLegalData {
  agreement_requirements?: string
  contract_duration?: string
  delivery_obligations?: string
  delay_penalties?: string
  indemnity_and_liability?: string
  insurance_requirements?: string
  confidentiality?: string
  termination_conditions?: string
  dispute_resolution_and_jurisdiction?: string
  force_majeure?: string
  significant_risk_clauses: ContractualClauseItem[]
}

export interface RiskItem {
  risk_title: string
  risk_level: 'Critical' | 'High' | 'Medium' | 'Low' | string
  description?: string
  tender_evidence: string
  source_page: number
  source_file: string
  document_id?: string
  why_it_matters: string
  potential_impact: string
  recommended_action: string
}

export interface RisksAndContradictionsData {
  critical_risks_count: number
  high_risks_count: number
  medium_risks_count: number
  low_risks_count: number
  risks: RiskItem[]
  contradictions_found: string[]
  missing_technical_information?: string[]
  overall_risk_verdict: string
}

export interface BidStrategyData {
  recommendation: string
  recommendation_rationale: string
  overall_tender_assessment: string
  key_qualification_hurdles: string[]
  technical_preparation_strategy: string
  required_oem_documents: string[]
  required_financial_documents: string[]
  required_supporting_certificates: string[]
  prebid_clarification_questions: string[]
  major_risks_to_resolve_before_submission?: string[]
  bid_preparation_priorities: string[]
  recommended_next_steps: string[]
}

export interface ActionRoadmapItem {
  step_number: number
  activity: string
  reason: string
  relevant_tender_page?: number
  source_file?: string
  document_id?: string
  priority: 'High' | 'Medium' | 'Low' | string
  deadline_or_stage?: string
}

export interface ActionRoadmapData {
  checklist: ActionRoadmapItem[]
  timeline_summary: string
}

export interface MasterTenderReport {
  report_id: string
  timestamp: string
  document_ids: string[]
  source_files: string[]
  file_hashes?: string[]
  total_pages_analyzed: number
  is_multi_document_package?: boolean
  package_name?: string
  model_used: string

  overview: TenderOverviewData
  eligibility: EligibilityData
  technical_scope: TechnicalScopeData
  technical_specifications: TechnicalSpecificationsData
  oem_requirements: OEMRequirementsData
  compliance_matrix: ComplianceMatrixData
  commercial_financial: CommercialFinancialData
  contractual_legal: ContractualLegalData
  risks_and_contradictions: RisksAndContradictionsData
  bid_strategy: BidStrategyData
  action_roadmap: ActionRoadmapData

  consultant_briefing_markdown?: string
  executive_summary_markdown?: string
  full_report_markdown?: string

  validation_status: string
  verification_notes?: string[]
  unreadable_pages?: number[]
  cache_hit?: boolean
  elapsed_seconds?: number
  processing_latency_breakdown?: Record<string, number>
}

