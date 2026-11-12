"""Typed 25-field Tender Extraction Schema for MYGPT Phase 1."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

FieldStatus = Literal["VERIFIED", "NEEDS_REVIEW", "NOT_FOUND", "AMBIGUOUS", "UNREADABLE"]

BASIC_INFO_FIELDS: List[str] = [
    "bid_title",
    "department_organization",
    "state",
    "customer_name",
    "customer_phone",
    "customer_address",
    "category",
    "tender_portal_url",
    "tender_id",
]

FINANCIAL_FIELDS: List[str] = [
    "estimated_tender_value",
    "bid_emd_value",
]

IMPORTANT_DATE_FIELDS: List[str] = [
    "tender_publication_date",
    "document_download_start",
    "document_download_end",
    "prebid_query_start",
    "prebid_query_end",
    "prebid_meeting_date",
    "prebid_response_date",
    "bid_submission_start",
    "bid_submission_end",
    "pq_bid_opening_date",
    "technical_bid_opening_date",
    "financial_bid_opening_date",
]

ADDITIONAL_FIELDS: List[str] = [
    "keywords_for_summary",
    "nas_path",
]

ALL_TENDER_FIELD_NAMES: List[str] = (
    BASIC_INFO_FIELDS
    + FINANCIAL_FIELDS
    + IMPORTANT_DATE_FIELDS
    + ADDITIONAL_FIELDS
)

FIELD_DISPLAY_LABELS: Dict[str, str] = {
    "bid_title": "Bid Title",
    "department_organization": "Department / Organization",
    "state": "State",
    "customer_name": "Customer Name",
    "customer_phone": "Customer Phone",
    "customer_address": "Customer Address",
    "category": "Category",
    "tender_portal_url": "Tender Portal URL",
    "tender_id": "Tender ID",
    "estimated_tender_value": "Estimated Tender Value",
    "bid_emd_value": "Bid EMD Value",
    "tender_publication_date": "Tender Publication Date",
    "document_download_start": "Document Sale / Download Start",
    "document_download_end": "Document Sale / Download End",
    "prebid_query_start": "Pre-Bid Clarification / Query Start",
    "prebid_query_end": "Pre-Bid Clarification / Query End",
    "prebid_meeting_date": "Pre-Bid Meeting",
    "prebid_response_date": "Pre-Bid Response / Clarification",
    "bid_submission_start": "Bid Submission Start",
    "bid_submission_end": "Bid Submission End / Deadline",
    "pq_bid_opening_date": "Pre-Qualification (PQ) Bid Opening",
    "technical_bid_opening_date": "Technical Bid Opening Date",
    "financial_bid_opening_date": "Financial / Commercial Bid Opening",
    "keywords_for_summary": "Keywords for Summary",
    "nas_path": "NAS Path",
}


class TenderConflictAlternative(BaseModel):
    """Alternative candidate observed on another page, sheet, or corrigendum."""

    value: str
    source_file: Optional[str] = None
    source_page: Optional[int] = None
    source_sheet: Optional[str] = None
    source_text: Optional[str] = None
    reason: Optional[str] = None


class TenderFieldEvidence(BaseModel):
    """Standardized extraction envelope for a single tender schema field."""

    field_name: str
    label: str
    section: Literal["basic_information", "financial_information", "important_dates", "additional_information"]
    value: str = "NOT_FOUND"
    source_file: Optional[str] = None
    source_page: Optional[int] = None
    source_sheet: Optional[str] = None
    source_text: Optional[str] = None
    confidence: float = 0.0
    status: FieldStatus = "NOT_FOUND"
    notes: Optional[str] = None
    alternatives: List[TenderConflictAlternative] = Field(default_factory=list)


class TenderFileCoverage(BaseModel):
    """Per-file parsing and OCR coverage details."""

    filename: str
    document_id: Optional[str] = None
    file_type: str = ""
    total_pages: int = 0
    extracted_pages: int = 0
    ocr_pages: List[int] = Field(default_factory=list)
    unreadable_pages: List[int] = Field(default_factory=list)
    sheets: List[str] = Field(default_factory=list)
    ocr_engine: Optional[str] = None
    error: Optional[str] = None


class TenderExtractionResult(BaseModel):
    """Complete fixed-schema extraction payload for one or more uploaded tender files."""

    document_ids: List[str] = Field(default_factory=list)
    source_files: List[str] = Field(default_factory=list)
    nas_path_provided: Optional[str] = None

    basic_information: Dict[str, TenderFieldEvidence] = Field(default_factory=dict)
    financial_information: Dict[str, TenderFieldEvidence] = Field(default_factory=dict)
    important_dates: Dict[str, TenderFieldEvidence] = Field(default_factory=dict)
    additional_information: Dict[str, TenderFieldEvidence] = Field(default_factory=dict)

    missing_fields: List[str] = Field(default_factory=list)
    conflicting_fields: List[Dict[str, Any]] = Field(default_factory=list)
    unreadable_fields: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    detailed_summary: str = ""
    summary_sources: List[Dict[str, Any]] = Field(default_factory=list)

    file_coverage: List[TenderFileCoverage] = Field(default_factory=list)
    total_pages: int = 0
    ocr_pages_count: int = 0
    unreadable_pages_count: int = 0
    fields_found_count: int = 0
    fields_not_found_count: int = 0
    fields_ambiguous_count: int = 0
    model_used: str = "Gemma-4-E2B-It-Q4_K_M"
    elapsed_seconds: float = 0.0
    cache_hit: bool = False
    stage_timings: Dict[str, Any] = Field(default_factory=dict)

    def all_fields_flat(self) -> Dict[str, TenderFieldEvidence]:
        """Returns a deterministic 25-key dict covering every required schema field."""
        flat: Dict[str, TenderFieldEvidence] = {}
        for group in (
            self.basic_information,
            self.financial_information,
            self.important_dates,
            self.additional_information,
        ):
            flat.update(group)
        return flat

