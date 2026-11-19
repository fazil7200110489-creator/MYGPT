"""Intelligence Retriever for MYGPT AI Tender Consultant.

Extracts domain-specific page groups from TenderDocumentIndex and PageRecord
structures, providing precise, page-grounded evidence blocks for each
consulting analysis dimension within Gemma's context budget.
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple
from loguru import logger

from backend.app.services.tender.tender_section_retriever import (
    PageRecord,
    TenderDocumentIndex,
    collect_page_records,
    get_or_build_index,
)

# ---------------------------------------------------------------------------
# Dimension Keyword Profiles
# ---------------------------------------------------------------------------

DIMENSION_KEYWORDS: Dict[str, List[str]] = {
    "overview": [
        "notice inviting", "e-tender", "nit no", "tender no", "scope of work",
        "name of work", "project title", "issuing authority", "submission deadline",
        "opening date", "contract period", "delivery period", "completion time",
        "estimated cost", "earnest money", "emd", "tender fee", "location",
    ],
    "eligibility": [
        "eligibility criteria", "qualifying criteria", "pre-qualification", "pq criteria",
        "annual turnover", "average turnover", "audited balance sheet", "ca certificate",
        "similar work", "experience", "past performance", "completed projects",
        "government", "central government", "state government", "psu", "autonomous",
        "registration", "incorporation", "gst", "pan", "oem authorization", "maf",
        "joint venture", "consortium", "blacklisted", "debarred", "net worth",
    ],
    "scope": [
        "scope of work", "schedule of requirements", "detailed scope", "deliverables",
        "supply", "installation", "testing", "commissioning", "implementation",
        "configuration", "cabling", "integration", "training", "amc", "maintenance",
        "comprehensive maintenance", "service level", "sla", "uptime", "handover",
    ],
    "specifications": [
        "technical specification", "specifications", "technical parameters",
        "bill of quantities", "boq", "schedule of items", "make", "model",
        "minimum requirements", "standards", "is code", "iec", "ieee", "iso",
        "dimensions", "capacity", "rating", "datasheet", "features",
    ],
    "oem": [
        "oem", "original equipment manufacturer", "manufacturer authorization",
        "maf", "manufacturer's authorization form", "authorization letter",
        "oem warranty", "tier 1", "tier-1", "gartner", "direct support",
        "back to back", "end of life", "end of support", "brand",
    ],
    "commercial": [
        "payment terms", "schedule of payment", "advance payment", "milestone",
        "retention money", "performance security", "performance bank guarantee",
        "pbg", "security deposit", "earnest money deposit", "emd", "price validity",
        "price escalation", "firm price", "liquidated damages", "penalty",
        "delay penalty", "taxes", "duties", "gst extra", "deduction",
    ],
    "legal": [
        "agreement", "contract agreement", "indemnity", "liability", "limitation of liability",
        "insurance", "confidentiality", "termination", "default", "breach",
        "dispute resolution", "arbitration", "jurisdiction", "force majeure",
        "governing law", "sub-contracting", "intellectual property",
    ],
    "risks": [
        "rejection of bid", "disqualification", "forfeiture", "risk and cost",
        "termination for default", "liquidated damages", "strict penalty",
        "unrealistic", "short notice", "non-refundable", "deviations not permitted",
        "sole discretion", "corrigendum", "amendment", "conflict",
    ],
}


class IntelligenceRetriever:
    """Domain-guided retrieval engine operating over TenderDocumentIndex."""

    def __init__(self) -> None:
        pass

    def prepare_index(
        self, documents: List[Dict[str, Any]]
    ) -> Tuple[TenderDocumentIndex, List[PageRecord], List[Dict[str, Any]]]:
        """Ensures documents are parsed and converts them to index + records + enriched docs."""
        records = collect_page_records(documents)
        enriched_docs = list(documents)
        if not records or any(d.get("file_path") and not d.get("pages") for d in documents):
            from backend.app.services.document_parser import document_parser

            enriched: List[Dict[str, Any]] = []
            for doc in documents:
                fpath = doc.get("file_path") or doc.get("path")
                if fpath and not doc.get("pages"):
                    try:
                        parsed = document_parser.parse(fpath)
                        enriched.append({**doc, **parsed})
                    except Exception as e:
                        logger.warning(f"Failed parsing file {fpath}: {e}")
                        enriched.append(doc)
                else:
                    enriched.append(doc)
            records = collect_page_records(enriched)
            enriched_docs = enriched

        index, _ = get_or_build_index(enriched_docs)
        return index, records, enriched_docs

    def retrieve_dimension_pages(
        self,
        index: TenderDocumentIndex,
        dimension_key: str,
        max_pages: int = 4,
        max_chars: int = 4000,
    ) -> List[Tuple[PageRecord, float, List[str]]]:
        """Returns top PageRecord objects scoring highest for the given dimension."""
        terms = DIMENSION_KEYWORDS.get(dimension_key, [])
        if not terms or not index.records:
            return []

        scored_pages: List[Tuple[int, float, List[str]]] = []
        for p_idx, lower_txt in enumerate(index.lower_texts):
            score = 0.0
            matched_terms: List[str] = []
            for term in terms:
                count = lower_txt.count(term)
                if count > 0:
                    matched_terms.append(term)
                    # logarithmic weight for term count
                    score += 1.0 + min(count - 1, 4) * 0.5
            if score > 0:
                scored_pages.append((p_idx, score, matched_terms))

        # Sort descending by relevance score
        scored_pages.sort(key=lambda x: x[1], reverse=True)

        selected: List[Tuple[PageRecord, float, List[str]]] = []
        total_chars = 0
        for p_idx, score, matched in scored_pages[:max_pages]:
            rec = index.records[p_idx]
            rec_len = len(rec.text)
            if total_chars + min(rec_len, 1500) > max_chars and selected:
                break
            selected.append((rec, score, matched))
            total_chars += rec_len

        # If keyword search was too sparse, pick early introductory pages as fallback
        if not selected and index.records:
            for rec in index.records[:2]:
                selected.append((rec, 1.0, ["introductory_fallback"]))

        return selected

    def format_dimension_context(
        self,
        scored_pages: List[Tuple[PageRecord, float, List[str]]],
        char_cap: int = 3500,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Formats scored pages into a grounded prompt snippet block with source citations."""
        blocks: List[str] = []
        sources: List[Dict[str, Any]] = []
        remaining_chars = char_cap

        for rec, score, matched in scored_pages:
            loc = rec.location_label()
            sources.append({
                "filename": rec.filename,
                "page_number": rec.page_number,
                "sheet_name": rec.sheet_name,
                "score": round(score, 2),
                "matched_terms": matched[:5],
            })

            clean_text = rec.text.strip()
            if len(clean_text) > remaining_chars:
                clean_text = clean_text[:remaining_chars] + "\n... [TRUNCATED FOR CONTEXT BUDGET]"

            block = (
                f"=== TENDER SOURCE EVIDENCE: {loc} ===\n"
                f"{clean_text}\n"
                f"=== END OF PAGE {rec.page_number} ==="
            )
            blocks.append(block)
            remaining_chars -= len(clean_text)
            if remaining_chars <= 200:
                break

        return "\n\n".join(blocks), sources

    def extract_boq_and_specs(
        self, index: TenderDocumentIndex, max_chars: int = 3000
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Finds tables, BOQ sections, and technical specification clauses."""
        spec_pages = self.retrieve_dimension_pages(index, "specifications", max_pages=3, max_chars=max_chars)
        return self.format_dimension_context(spec_pages, char_cap=max_chars)


intelligence_retriever = IntelligenceRetriever()

