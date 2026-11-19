"""Cross-Section Contradiction & Ambiguity Engine for MYGPT AI Tender Consultant.

Autonomously identifies conflicting conditions, timeline discrepancies, differing
commercial thresholds, and ambiguous requirements across tender document sections.
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple
from loguru import logger

from backend.app.services.tender.tender_section_retriever import PageRecord
from .intelligence_schema import (
    CommercialFinancialAnalysis,
    ContractualLegalAnalysis,
    EligibilityAnalysis,
    TechnicalSpecificationAnalysis,
    TenderOverview,
)


class ContradictionEngine:
    """Discovers cross-section inconsistencies and ambiguous stipulations in tender documents."""

    def __init__(self) -> None:
        pass

    def analyze_contradictions(
        self,
        overview: TenderOverview,
        eligibility: EligibilityAnalysis,
        specs: TechnicalSpecificationAnalysis,
        commercial: CommercialFinancialAnalysis,
        legal: ContractualLegalAnalysis,
        records: List[PageRecord],
    ) -> List[str]:
        """Detects contradictions between document sections, returning human-readable findings."""
        contradictions: List[str] = []

        if not records:
            return contradictions

        # 1. Warranty Period Discrepancies (Commercial / Overview vs Specific Item Specs)
        w_contradictions = self._check_warranty_contradictions(overview, specs, records)
        contradictions.extend(w_contradictions)

        # 2. Delivery / Implementation Timeline Discrepancies
        d_contradictions = self._check_delivery_contradictions(overview, legal, records)
        contradictions.extend(d_contradictions)

        # 3. EMD & MSME Exemption Ambiguities
        emd_contradictions = self._check_emd_msme_contradictions(commercial, records)
        contradictions.extend(emd_contradictions)

        # 4. Consortium / Joint Venture Policy Inconsistencies
        jv_contradictions = self._check_consortium_contradictions(eligibility, records)
        contradictions.extend(jv_contradictions)

        # 5. Liquidated Damages / Penalty Cap Discrepancies (e.g. GCC 10% vs SCC 5%)
        ld_contradictions = self._check_liquidated_damages_contradictions(commercial, records)
        contradictions.extend(ld_contradictions)

        logger.info(f"[CONTRADICTION_ENGINE] Discovered {len(contradictions)} cross-section contradiction(s).")
        return contradictions

    def _check_warranty_contradictions(
        self,
        overview: TenderOverview,
        specs: TechnicalSpecificationAnalysis,
        records: List[PageRecord],
    ) -> List[str]:
        findings: List[str] = []
        ov_warranty = overview.warranty_maintenance_period
        if not ov_warranty or ov_warranty in ("NOT FOUND", "Not specified"):
            return findings

        # Extract numeric year from overview warranty (e.g. "3 Years")
        m_ov_yr = re.search(r"(\d+)\s*(?:years?|yrs?|months?|mths?)", ov_warranty, re.I)
        if not m_ov_yr:
            return findings

        ov_dur_str = m_ov_yr.group(0).lower()

        # Check item specifications for conflicting warranty durations
        for it in specs.items:
            spec_txt = it.technical_specifications.lower()
            if "warranty" in spec_txt:
                m_it_yr = re.search(r"(\d+)\s*(?:years?|yrs?|months?|mths?)\s*warranty", spec_txt, re.I)
                if m_it_yr:
                    it_dur_str = m_it_yr.group(0).lower()
                    if it_dur_str != ov_dur_str and m_it_yr.group(1) != m_ov_yr.group(1):
                        findings.append(
                            f"[Warranty Duration Conflict] General overview/commercial specifies '{ov_warranty}' "
                            f"(Source Page {overview.citations[0].page_number if overview.citations else 1}), but "
                            f"item '{it.item_name}' specifies '{m_it_yr.group(0)}' (Source Page {it.source_page}). "
                            "Pre-bid clarification required to confirm whether item-specific or overall warranty governs."
                        )
                        break

        # Check if GCC/SCC text has a different warranty statement
        for rec in records:
            if any(k in rec.text.lower() for k in ["general conditions", "special conditions", "scc", "gcc"]):
                m_txt_yr = re.search(r"warranty[^\n\r.:]*?(?:shall be for a period of|period of)?\s*(\d+\s*(?:years?|months?))", rec.text, re.I)
                if m_txt_yr:
                    found_w = m_txt_yr.group(1).lower()
                    if m_txt_yr.group(1).split()[0] != m_ov_yr.group(1):
                        findings.append(
                            f"[Warranty Clause Inconsistency] Contract terms state warranty period of '{m_txt_yr.group(1)}' "
                            f"on Page {rec.page_number}, which differs from '{ov_warranty}' cited in the tender summary. "
                            "Clarify required warranty duration during pre-bid stage."
                        )
                        break
        return findings

    def _check_delivery_contradictions(
        self,
        overview: TenderOverview,
        legal: ContractualLegalAnalysis,
        records: List[PageRecord],
    ) -> List[str]:
        findings: List[str] = []
        ov_del = overview.delivery_implementation_period
        if not ov_del or ov_del in ("NOT FOUND", "Not specified"):
            return findings

        # Check for multiple differing delivery clauses (e.g. 30 days vs 60 days vs 4 weeks)
        del_mentions: List[Tuple[int, str]] = []
        for rec in records:
            matches = re.finditer(
                r"(?:delivery|completion|implementation)\s+(?:period|schedule|timeline|time)[^\n\r.:]*?(?:within|is|shall be)?\s*(\d+\s*(?:days?|weeks?|months?))",
                rec.text,
                re.I,
            )
            for m in matches:
                span_text = m.group(1).strip().lower()
                if not any(span_text == d[1] for d in del_mentions):
                    del_mentions.append((rec.page_number, span_text))

        if len(del_mentions) >= 2:
            # Check if numbers conflict (e.g., "30 days" vs "60 days" or "4 weeks" vs "8 weeks")
            first_p, first_val = del_mentions[0]
            for p, val in del_mentions[1:]:
                # If distinct numbers
                n1 = re.findall(r"\d+", first_val)
                n2 = re.findall(r"\d+", val)
                if n1 and n2 and n1[0] != n2[0]:
                    findings.append(
                        f"[Delivery Schedule Ambiguity] Delivery timeline stated as '{first_val}' on Page {first_p}, "
                        f"whereas Page {p} specifies '{val}'. Clarify precise milestone delivery schedule before submission."
                    )
                    break
        return findings

    def _check_emd_msme_contradictions(
        self,
        commercial: CommercialFinancialAnalysis,
        records: List[PageRecord],
    ) -> List[str]:
        findings: List[str] = []
        has_msme_exempt = False
        has_no_exempt = False
        msme_page = 1
        no_exempt_page = 1

        for rec in records:
            txt_low = rec.text.lower()
            if any(k in txt_low for k in ["msme", "nsic", "micro and small", "start-up", "startup"]):
                if any(k in txt_low for k in ["exempted from payment of emd", "emd exemption", "exemption from emd", "shall be exempt"]):
                    has_msme_exempt = True
                    msme_page = rec.page_number
            if any(k in txt_low for k in ["no exemption", "exemption will not be", "exemption not allowed", "all bidders must submit emd", "no exemption on emd"]):
                if any(k in txt_low for k in ["emd", "earnest money"]):
                    has_no_exempt = True
                    no_exempt_page = rec.page_number

        if has_msme_exempt and has_no_exempt and msme_page != no_exempt_page:
            findings.append(
                f"[EMD Exemption Conflict for MSME] Page {msme_page} indicates EMD exemption for registered MSME/NSIC units, "
                f"while Page {no_exempt_page} states no exemption from EMD is permitted. "
                "Immediate clarification required to prevent wrongful disqualification."
            )

        return findings

    def _check_consortium_contradictions(
        self,
        eligibility: EligibilityAnalysis,
        records: List[PageRecord],
    ) -> List[str]:
        findings: List[str] = []
        consort_status = eligibility.consortium_joint_venture_allowed
        if not consort_status or consort_status in ("NOT FOUND", "Not specified"):
            return findings

        # If consortium prohibited, check if subcontracting or consortium clauses appear elsewhere
        if "not allowed" in consort_status.lower() or "not permitted" in consort_status.lower():
            for rec in records:
                if "lead bidder" in rec.text.lower() and "consortium partner" in rec.text.lower():
                    findings.append(
                        f"[Consortium Clause Inconsistency] Eligibility criteria on Page {eligibility.conditions[0].source_page if eligibility.conditions else 1} "
                        f"states consortium is not permitted, but Page {rec.page_number} references 'Lead Bidder' and consortium member obligations. "
                        "Clarify whether consortium / joint venture bidding is officially allowed."
                    )
                    break
        return findings

    def _check_liquidated_damages_contradictions(
        self,
        commercial: CommercialFinancialAnalysis,
        records: List[PageRecord],
    ) -> List[str]:
        findings: List[str] = []
        ld_text = commercial.penalties_and_liquidated_damages
        if not ld_text or ld_text in ("NOT FOUND", "Not specified"):
            return findings

        # Check if multiple maximum penalty caps are mentioned (e.g. 5% vs 10%)
        caps_found: List[Tuple[int, str]] = []
        for rec in records:
            m = re.search(r"maximum\s+(?:deduction\s+)?(?:of\s+)?(\d+(?:\.\d+)?%)\s*(?:of\s+the\s+contract|of\s+total\s+value|of\s+order)?", rec.text, re.I)
            if m:
                cap_pct = m.group(1)
                if not any(cap_pct == c[1] for c in caps_found):
                    caps_found.append((rec.page_number, cap_pct))

        if len(caps_found) >= 2:
            p1, c1 = caps_found[0]
            p2, c2 = caps_found[1]
            if c1 != c2:
                findings.append(
                    f"[Liquidated Damages Cap Discrepancy] Maximum LD penalty cap is stated as {c1} on Page {p1}, "
                    f"but specifies {c2} on Page {p2}. Confirm the applicable maximum liability ceiling in pre-bid queries."
                )
        return findings


contradiction_engine = ContradictionEngine()

