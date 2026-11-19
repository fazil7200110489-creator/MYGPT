"""Validation and Grounding Guard for MYGPT AI Tender Consultant.

Verifies page references against actual PageRecord slices with substantive
text substring cross-checking, detects hallucinations, ensures valid risk levels
and recommendations, and records verification notes.
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple
from loguru import logger

from backend.app.services.tender.tender_section_retriever import PageRecord
from .intelligence_schema import (
    BidRecommendation,
    RiskLevel,
    TenderConsultantReport,
    TenderEvidenceCitation,
)


class IntelligenceValidator:
    """Grounding and citation auditor for consultant reports."""

    def __init__(self) -> None:
        pass

    def validate_report(
        self,
        report: TenderConsultantReport,
        records: List[PageRecord],
    ) -> TenderConsultantReport:
        """Validates all findings against source PageRecord texts using substantive substring cross-checking."""
        notes: List[str] = []
        page_count = len(records)
        record_by_page: Dict[int, PageRecord] = {r.page_number: r for r in records}

        verified_citations_count = 0
        total_citations_count = 0
        conflicts_count = 0
        ungrounded_critical_fields = 0

        # 1. Substantive verification of Overview citations
        for cit in report.overview.citations:
            total_citations_count += 1
            status, note = self._verify_substantive_citation(cit, record_by_page, page_count)
            if status == "VERIFIED":
                verified_citations_count += 1
            elif status == "CONFLICT_DETECTED":
                conflicts_count += 1
                notes.append(note)
            else:
                notes.append(note)

        # Check critical overview facts grounding
        crit_overview = [
            ("Issuing Authority", report.overview.department_organization),
            ("Tender Title", report.overview.tender_title),
            ("Delivery Period", report.overview.delivery_implementation_period),
            ("Warranty Period", report.overview.warranty_maintenance_period),
        ]
        for label, val in crit_overview:
            if not val or val in ("NOT FOUND", "Not specified", "NOT SPECIFIED IN TENDER"):
                continue
            # Check if this fact appears anywhere in records
            val_clean = " ".join(val.split()[:4]).lower()
            if len(val_clean) > 4:
                found = any(val_clean in r.text.lower() for r in records)
                if not found:
                    notes.append(f"Grounding notice: {label} '{val[:40]}' could not be directly substantiated in document text.")
                    ungrounded_critical_fields += 1

        # 2. Substantive verification of Eligibility conditions
        for cond in report.eligibility.conditions:
            if cond.source_page:
                rec = record_by_page.get(cond.source_page)
                if not rec:
                    notes.append(
                        f"Warning: Eligibility condition '{cond.category}' references non-existent Page {cond.source_page} (Total pages: {page_count})."
                    )
                    ungrounded_critical_fields += 1
                else:
                    rec_low = rec.text.lower()
                    # Check numbers (e.g. 62.00, 1.00, 3)
                    nums = re.findall(r"\b\d+(?:\.\d+)?\b", cond.department_requirement)
                    if nums:
                        num_found = any(n in rec.text for n in nums)
                        if not num_found:
                            notes.append(
                                f"Audit notice: Numeric threshold in '{cond.category}' ({nums}) not found on cited Page {cond.source_page}."
                            )
                            conflicts_count += 1
                    # Substantive check on verbatim evidence if provided
                    if cond.verbatim_evidence and len(cond.verbatim_evidence) > 10:
                        ev_snippet = cond.verbatim_evidence[:60].strip().lower()
                        if ev_snippet not in rec_low:
                            # Soft fallback check on word overlap
                            words = [w.lower() for w in cond.department_requirement.split() if len(w) > 4]
                            if words and not any(w in rec_low for w in words[:4]):
                                notes.append(
                                    f"Audit notice: Eligibility requirement for '{cond.category}' on Page {cond.source_page} has weak textual match with page content."
                                )

        # 3. Substantive verification of Technical Specification items
        for item in report.technical_specifications.items:
            if item.source_page:
                if item.source_page > page_count or item.source_page < 1:
                    notes.append(
                        f"Warning: Technical item '{item.item_name}' references invalid Page {item.source_page}."
                    )
                    item.source_page = min(max(item.source_page, 1), page_count)
                else:
                    rec = record_by_page.get(item.source_page)
                    if rec and len(item.item_name) > 3:
                        # Cross-check item name in page text
                        clean_item_name = re.sub(r"[^a-zA-Z0-9\s]", "", item.item_name).lower().strip()
                        clean_page_text = re.sub(r"[^a-zA-Z0-9\s]", "", rec.text).lower()
                        if clean_item_name[:25] not in clean_page_text:
                            # Try sub-words
                            subwords = [w for w in clean_item_name.split() if len(w) > 3]
                            if subwords and not any(w in clean_page_text for w in subwords[:2]):
                                notes.append(
                                    f"Grounding notice: Specification item '{item.item_name[:35]}' weak match on Page {item.source_page}."
                                )

        # 4. Validate Risks and ensure normalized risk levels
        valid_risk_levels = {r.value for r in RiskLevel}
        crit_c = high_c = med_c = low_c = 0
        for r in report.risks_and_contradictions.risks:
            norm_level = RiskLevel.MEDIUM.value
            for candidate in valid_risk_levels:
                if candidate.lower() in (r.risk_level or "").lower():
                    norm_level = candidate
                    break
            r.risk_level = norm_level

            if norm_level == RiskLevel.CRITICAL.value:
                crit_c += 1
            elif norm_level == RiskLevel.HIGH.value:
                high_c += 1
            elif norm_level == RiskLevel.MEDIUM.value:
                med_c += 1
            else:
                low_c += 1

            if r.source_page and (r.source_page > page_count or r.source_page < 1):
                notes.append(
                    f"Notice: Risk '{r.risk_title}' referenced Page {r.source_page}, clipped to document range."
                )
                r.source_page = min(max(r.source_page, 1), page_count)

        report.risks_and_contradictions.critical_risks_count = crit_c
        report.risks_and_contradictions.high_risks_count = high_c
        report.risks_and_contradictions.medium_risks_count = med_c
        report.risks_and_contradictions.low_risks_count = low_c

        # 5. Validate Bid Recommendation
        valid_recs = sorted([b.value for b in BidRecommendation], key=len, reverse=True)
        norm_rec = BidRecommendation.PROCEED_WITH_CAUTION.value
        rec_text = (report.bid_strategy.recommendation or "").replace("_", " ").replace("-", " ").lower()
        for candidate in valid_recs:
            if candidate.lower() in rec_text:
                norm_rec = candidate
                break
        report.bid_strategy.recommendation = norm_rec

        # 6. Validate Action Roadmap checklist citations
        roadmap_pages = set()
        for step in report.action_roadmap.checklist:
            if step.relevant_tender_page is not None:
                if step.relevant_tender_page > page_count or step.relevant_tender_page < 1:
                    notes.append(
                        f"Roadmap notice: Step {step.step_number} ('{step.activity[:30]}') cited non-existent Page {step.relevant_tender_page} (Clipped to range 1..{page_count})."
                    )
                    step.relevant_tender_page = min(max(step.relevant_tender_page, 1), page_count)
                roadmap_pages.add(step.relevant_tender_page)

        if len(report.action_roadmap.checklist) >= 3 and len(roadmap_pages) == 1 and page_count > 5:
            notes.append(
                f"Roadmap audit notice: Multiple roadmap steps share identical Page {next(iter(roadmap_pages))}. Verify individual step citations."
            )

        # 7. Substantive overall validation status determination
        # Status hierarchy: CONFLICT_DETECTED > PARTIALLY_VERIFIED > VERIFIED
        if conflicts_count > 0:
            report.validation_status = "CONFLICT_DETECTED"
        elif any("non-existent" in n for n in notes) or ungrounded_critical_fields > 1:
            report.validation_status = "PARTIALLY_VERIFIED"
        elif ungrounded_critical_fields == 1 or any("weak textual match" in n for n in notes):
            report.validation_status = "PARTIALLY_VERIFIED"
        elif page_count > 0 and len(report.technical_specifications.items) > 0:
            report.validation_status = "VERIFIED"
        else:
            report.validation_status = "PARTIALLY_VERIFIED"

        report.verification_notes = notes
        return report

    def _verify_substantive_citation(
        self,
        cit: TenderEvidenceCitation,
        record_by_page: Dict[int, PageRecord],
        page_count: int,
    ) -> Tuple[str, str]:
        if cit.page_number < 1 or cit.page_number > page_count:
            cit.page_number = min(max(cit.page_number, 1), page_count)
            return "NOT_FOUND", f"Invalid citation page {cit.page_number} for file '{cit.filename}' (Doc pages: {page_count})."

        rec = record_by_page.get(cit.page_number)
        if not rec:
            return "NOT_FOUND", f"Citation references non-existent Page {cit.page_number}."

        snip = getattr(cit, "source_text", None) or getattr(cit, "verbatim_snippet", "")
        if not snip or len(snip.strip()) < 5:
            return "PARTIALLY_VERIFIED", f"Citation on Page {cit.page_number} has empty verbatim snippet."

        clean_snip = " ".join(snip.split()).lower()
        clean_page = " ".join(rec.text.split()).lower()

        if clean_snip in clean_page:
            return "VERIFIED", f"Page {cit.page_number} citation confirmed verbatim."

        # Partial match
        words = [w for w in clean_snip.split() if len(w) > 4]
        if words and any(w in clean_page for w in words[:3]):
            return "PARTIALLY_VERIFIED", f"Page {cit.page_number} confirmed by key token overlap."

        return "CONFLICT_DETECTED", f"Citation snippet '{snip[:40]}' not substantiated on Page {cit.page_number}."


intelligence_validator = IntelligenceValidator()
