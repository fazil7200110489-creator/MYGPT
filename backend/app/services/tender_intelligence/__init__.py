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
from .evaluation_lock import tender_evaluation_lock, TenderEvaluationBusyError
from .resource_monitor import resource_monitor

__all__ = [
    "tender_intelligence_engine",
    "tender_evaluation_lock",
    "TenderEvaluationBusyError",
    "resource_monitor",
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