"""MYGPT AI Tender Consultant Package.

Provides professional-grade, evidence-grounded tender evaluation,
bid strategy, eligibility verification, risk analysis, and action roadmaps
strictly from uploaded tender documents.
"""

from .intelligence_schema import (
    TenderConsultantReport,
    TenderOverview,
    EligibilityAnalysis,
    TechnicalScopeAnalysis,
    TechnicalSpecificationAnalysis,
    OEMRequirementAnalysis,
    ItemWiseComplianceMatrix,
    CommercialFinancialAnalysis,
    ContractualLegalAnalysis,
    RiskContradictionAnalysis,
    BidStrategyAnalysis,
    ActionRoadmap,
    TenderEvidenceCitation,
    EvidenceClassification,
    RiskLevel,
    BidRecommendation,
    ComplianceStatus,
)
from .intelligence_engine import tender_intelligence_engine

__all__ = [
    "tender_intelligence_engine",
    "TenderConsultantReport",
    "TenderOverview",
    "EligibilityAnalysis",
    "TechnicalScopeAnalysis",
    "TechnicalSpecificationAnalysis",
    "OEMRequirementAnalysis",
    "ItemWiseComplianceMatrix",
    "CommercialFinancialAnalysis",
    "ContractualLegalAnalysis",
    "RiskContradictionAnalysis",
    "BidStrategyAnalysis",
    "ActionRoadmap",
    "TenderEvidenceCitation",
    "EvidenceClassification",
    "RiskLevel",
    "BidRecommendation",
    "ComplianceStatus",
]