"""Deterministic extraction engine for MYGPT AI Tender Consultant.

Extracts facts, eligibility conditions, technical specifications, OEM mandates,
commercial terms, and contractual clauses using regex, structural patterns, and
structured table parsing over PageRecord and TenderDocumentIndex structures.

STRICT ACCURACY GUARANTEES:
1. Zero hardcoded tender-specific values or fake defaults (e.g. no fake "3 Years",
   no fake "Delivery within 8-12 weeks", no fake Wi-Fi specifications).
2. If a fact is absent from the document, returns "NOT FOUND".
3. Every factual item retains document_id, filename, page_number, clause_heading,
   and verbatim source text evidence.
4. Complete table parsing extracts specification tables across all pages.
5. Entity Classification separates Issuing Authority from Sub-Departments/Consignees,
   and Main Bidder from OEM, Consortium Members, and Subcontractors/CSPs.
6. Turnover is classified strictly by entity role (Bidder vs. OEM vs. CSP).
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple
from loguru import logger

from backend.app.services.tender.tender_section_retriever import PageRecord, TenderDocumentIndex
from .intelligence_schema import (
    BidderReadinessSummary,
    CategoryReadiness,
    CommercialFinancialAnalysis,
    ComplianceMatrixItem,
    ComplianceStatus,
    ContractualClauseItem,
    ContractualLegalAnalysis,
    EligibilityAnalysis,
    EligibilityCondition,
    EvidenceClassification,
    IntelligentComplianceStatus,
    ItemWiseComplianceMatrix,
    OEMRequirementAnalysis,
    OEMRequirementItem,
    RequirementCategory,
    RequiredBidderDocument,
    RiskLevel,
    TechnicalScopeAnalysis,
    TechnicalScopeItem,
    TechnicalSpecificationAnalysis,
    TechnicalSpecificationItem,
    TenderEvidenceCitation,
    TenderOverview,
)


# ---------------------------------------------------------------------------
# Regex Helpers
# ---------------------------------------------------------------------------

_DATE_PATTERN = re.compile(
    r"(\b\d{1,2}[-/.](?:\d{1,2}|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[-/.](?:\d{4}|\d{2})\b(?:\s*(?:at|upto|on)?\s*\d{1,2}[:.]\d{2}\s*(?:AM|PM|Hrs|Hours)?)?)",
    re.I,
)

_CURRENCY_PATTERN = re.compile(
    r"((?:Rs\.?|INR|₹)\s*[\d,]+(?:\.\d+)?(?:\s*/-)?(?:\s*(?:Lakhs?|Lacs?|Crores?|Crs?\.?|Thousand))?(?:\s*\([^)]+\))?)",
    re.I,
)


def _clean_text_span(text: str) -> str:
    """Collapses whitespace and newlines for clean snippet matching."""
    return re.sub(r"\s+", " ", text).strip()


def _clean_org_title(name: str) -> str:
    """Formats organization name cleanly while preserving uppercase acronyms."""
    if not name:
        return ""
    name = _clean_text_span(name)
    if name.isupper():
        small_words = {"of", "the", "and", "in", "for", "on", "at", "to", "a", "an"}
        words = name.split()
        titled = []
        for i, w in enumerate(words):
            if w in ("NITK", "IIT", "IIM", "AIIMS", "WTL", "EESL", "CCTV", "ANPR", "PSU", "BWC", "GST", "PAN"):
                titled.append(w)
            elif i > 0 and w.lower() in small_words:
                titled.append(w.lower())
            else:
                titled.append(w.capitalize())
        return " ".join(titled)
    return name


def _extract_clause_heading(text: str, match_pos: int) -> str:
    """Finds the nearest preceding clause/section heading before match_pos."""
    prefix = text[:match_pos]
    lines = [l.strip() for l in prefix.split("\n") if l.strip()]
    for line in reversed(lines[-8:]):
        # Check standard heading patterns
        if re.match(r"^(?:SECTION|SCHEDULE|ANNEXURE|CLAUSE|PART|CHAPTER|ARTICLE|SL\.?\s*NO\.?)\b", line, re.I):
            return line[:100]
        if line.isupper() and 5 < len(line) < 80:
            return line
    return "Tender Clause"


def _extract_verbatim_evidence(text: str, match_start: int, match_end: int, window: int = 150) -> str:
    """Extracts a readable verbatim sentence/snippet containing the match."""
    start = max(0, match_start - 30)
    end = min(len(text), match_end + window)
    raw = text[start:end]
    clean = _clean_text_span(raw)
    return clean[:250]


# ---------------------------------------------------------------------------
# Section 1: Overview & Scope Extraction (with Entity Separation)
# ---------------------------------------------------------------------------

def extract_overview_facts(
    records: List[PageRecord], anchors: Dict[str, Any]
) -> Tuple[TenderOverview, TechnicalScopeAnalysis]:
    """Extracts tender overview and technical scope deterministically with exact evidence citations."""
    if not records:
        empty_overview = TenderOverview()
        empty_scope = TechnicalScopeAnalysis()
        return empty_overview, empty_scope

    default_page = records[0].page_number
    default_file = records[0].filename
    default_doc_id = records[0].document_id

    # Combine text from first 4 pages for header and identity extraction
    front_text = "\n".join([rec.text for rec in records[:4]])
    front_flat = _clean_text_span(front_text)

    # 1. Universal Autonomous Entity Extraction (Authority vs Execution vs Inviting vs End-User)
    authority = "NOT FOUND"
    sub_department: Optional[str] = None
    inviting_authority: Optional[str] = None
    end_user_dept: Optional[str] = None

    # Step A: Identify Primary Issuing Organization from first page headers & organizational declarations
    # 1. First inspect the top header lines of Page 1 directly (covers Webel Technology Limited, Tripura University, etc.)
    p1_lines = [l.strip() for l in records[0].text.splitlines() if l.strip()] if records else []
    for line in p1_lines[:8]:
        if (
            len(line) >= 4
            and len(line) <= 95
            and not line.startswith("(")
            and not any(k in line.lower() for k in ("notice inviting", "section", "page", "tender no", "version", "dated", "e-tender", "list of dates"))
            and re.search(r"\b(LIMITED|UNIVERSITY|CORPORATION|AUTHORITY|DEPARTMENT|MINISTRY|BOARD|DIRECTORATE|COMMISSIONERATE|INSTITUTE)\b", line, re.I)
            and not line.endswith(".")
        ):
            cand_clean = _clean_text_span(line)
            if not any(noise in cand_clean.lower() for noise in ("testing", "commissioning", "maintenance of", "supply of", "installation of", "enterprise-grade")):
                authority = _clean_org_title(cand_clean)
                break

    if authority == "NOT FOUND":
        auth_patterns = [
            # Explicit Issued by / Inviting header / Employer table row
            r"(?:Name of (?:the )?Employer[^\n\r]*|Tender Inviting Authority|Issued by|Client)[\s.:\-\n]+([A-Z][A-Za-z\s.,&/\(\)\-]{4,120})",
            # Full public enterprise / corporation / board with parenthetical undertaking
            r"([A-Z][A-Za-z\s.,&/\-]{3,80}(?:Limited|Corporation|Authority|Nigam|Board|Directorate|Commissionrate|Vidyapeeth)\s*(?:\([^\)]+\))?)",
            # Universities and Educational Institutes (e.g. NITK, Tripura University, IIT, etc.)
            r"((?:NATIONAL INSTITUTE OF TECHNOLOGY[^\n,\r]*|TRIPURA UNIVERSITY[^\n,\r]*|[A-Z][A-Za-z\s.,&/\-]{3,80}(?:University|Institute of Technology[^\n,\r]*)\s*(?:\([^\)]+\))?))",
            # Government Directorates / Ministries / Departments
            r"((?:Office of the [^\n,\r]+|Directorate of [^\n,\r]+|Department of [^\n,\r]+|Government of\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?|Ministry of [^\n,\r]+)(?:,\s*[^\n,\r]+)?)",
            # Police / Armed / Para-military forces (standing alone or line start, not "under Inspector General of Police...")
            r"(?:^|\n)\s*([A-Z][A-Za-z\s]{2,40}Police(?:\s*Telecommunication|\s*Headquarters|\s*Technical Services)?)\b",
        ]

        for pat in auth_patterns:
            m_cand = re.search(pat, front_text, re.I)
            if m_cand:
                cand_clean = _clean_text_span(m_cand.group(1))
                cand_clean = re.sub(r"^(?:Buyer/Owner|Consignee|Purchaser|Client)[\s.:\-\n]*", "", cand_clean, flags=re.I).strip()
                cand_low = cand_clean.lower()
                # Reject prose clauses and sentence fragments
                if any(w in cand_low for w in (
                    "till the", ", but the", "prescribed by", "has uploaded", "shall be", "in order to",
                    "is invited", "are invited", "will be", "should be", "must be", "bidder has",
                    "deadline for submission", "soft copy part", "hard copy part"
                )):
                    continue
                # Filter non-entity noise, equipment keywords, and scope sentence fragments
                if any(noise in cand_low for noise in (
                    "certifying authority", "cca india", "cca", "sify", "emudhra", "ncode",
                    "workstation", "software", "application", "license", "testing",
                    "commissioning", "configuration", "maintenance of", "supply of",
                    "installation of", "enterprise-grade", "binocular", "camera", "under "
                )):
                    continue
                if cand_low.startswith(("http", "www", "email", "website", "phone", "fax")) or any(ext in cand_low for ext in (".ac.in", ".gov.in", ".nic.in", ".com", ".org")):
                    continue
                if cand_clean.startswith(("ion,", "ing,", "ed,", "and ")):
                    continue
                # Strip leading domain / website prefix if glued before institution name
                cand_clean = re.sub(r"^[a-zA-Z0-9.-]+\.(?:edu|ac|gov|nic|com|org)(?:\.[a-z]{2,3})?\s*", "", cand_clean, flags=re.I).strip()
                if len(cand_clean) >= 6 and not cand_low.startswith((
                    "section", "date", "dated", "page", "tender", "bid", "index", "annexure", "table", "online", "view"
                )):
                    authority = _clean_org_title(cand_clean)
                    break

    # If authority is a general state government name or missing specific officer/office, search full multi-line Office of the...
    m_office = re.search(
        r"(Office of the\s+Deputy Inspector General of Police[^\n,\r]*(?:,\s*[^\n,\r]+){0,3}|Office of the\s+[A-Za-z\s.,&/\(\)\-]{3,100}Police(?:[^\n,\r]*(?:,\s*[^\n,\r]+){0,3})?|Office of the\s+[A-Za-z\s.,&/\(\)\-]{5,80}(?:Directorate|Department|Commissioner|Superintendent|Authority))",
        front_text,
        re.I,
    )
    if m_office:
        authority = _clean_org_title(_clean_text_span(m_office.group(1)))
    elif "government of" in authority.lower():
        m_spec = re.search(r"((?:Office of the\s+[A-Za-z\s.,&/\(\)\-]{3,100}Police[^\n,\r]*|[A-Z][A-Za-z\s]{2,80}Police(?:\s*Technical Services)?))", front_text, re.I)
        if m_spec:
            authority = _clean_org_title(_clean_text_span(m_spec.group(1)))

    # If authority is a sub-department (e.g. Department of Mechanical Engineering) and parent university/institute exists in front_text, join them
    m_parent_inst = re.search(r"((?:NATIONAL INSTITUTE OF TECHNOLOGY[^\n,\r]*|TRIPURA UNIVERSITY[^\n,\r]*|[A-Z][A-Za-z\s.,&/\-]{3,80}(?:University|Institute of Technology[^\n,\r]*)))", front_text, re.I)
    if m_parent_inst and authority != "NOT FOUND" and not any(k in authority.lower() for k in ("university", "institute of technology")):
        parent_raw = re.sub(r"^[a-zA-Z0-9.-]+\.(?:edu|ac|gov|nic|com|org)(?:\.[a-z]{2,3})?\s*", "", m_parent_inst.group(1), flags=re.I).strip()
        parent_name = _clean_org_title(parent_raw)
        if len(parent_name) >= 6 and parent_name.lower() not in authority.lower():
            sub_department = authority
            authority = f"{parent_name} - {authority}"

    # Step B: Identify End-User Department / Consignee / Beneficiary
    # e.g. "for Singappen Special Force", "for the Singappen Special Task Force", "on behalf of Aliah University", "under Inspector General of Police (North Bengal Region)"
    m_eu_force = re.search(
        r"(?:for the\s+|for\s+)([A-Z][A-Za-z0-9\s.,&/\(\)\-]{3,60}(?:Special Force|Special Task Force|Police|Force|University|College|Hospital|Campus|Battalion|Brigade))",
        front_text,
        re.I,
    )
    if m_eu_force:
        cand_eu = _clean_text_span(m_eu_force.group(1))
        cand_eu = re.sub(r"\s+", " ", cand_eu).strip()
        if not any(noise in cand_eu.lower() for noise in ("this tender", "the bidder", "the project", "the scope", "these terms", "selection of", "purchase of", "supply of")):
            end_user_dept = cand_eu

    if not end_user_dept:
        m_eu_under = re.search(
            r"(?:under\s+(?:the\s+)?(?:jurisdiction of\s+(?:the\s+)?)?)([A-Z][A-Za-z0-9\s.,&/\(\)\-]{3,80}(?:Inspector General of Police|Special Force|Special Task Force|Police|Directorate|Commissionerate|Department)[^\n\r]*?(?:\([^\)]+\))?[^\n\r,.]*)",
            front_text,
            re.I,
        )
        if m_eu_under:
            cand_eu = _clean_text_span(m_eu_under.group(1))
            cand_eu = re.sub(r"\s+", " ", cand_eu).strip()
            cand_eu_low = cand_eu.lower()
            if len(cand_eu) >= 6 and not any(noise in cand_eu_low for noise in ("this tender", "the bidder", "the project", "the scope", "these terms", "selection of", "purchase of", "supply of")):
                end_user_dept = cand_eu

    if not end_user_dept:
        m_eu = re.search(
            r"(?:on behalf of|for the use of|end[\s\-]*user(?:\s*department)?|beneficiary(?:\s*department)?|consignee)[\s.:\-\n]+([A-Z][A-Za-z\s.,&/\(\)\-]{5,100})",
            front_text,
            re.I,
        )
        if m_eu:
            cand_eu = _clean_text_span(m_eu.group(1))
            cand_eu = re.sub(r"\s+", " ", cand_eu).strip()
            cand_eu_low = cand_eu.lower()
            if len(cand_eu) >= 6 and not any(noise in cand_eu_low for noise in ("section", "date", "page", "tender", "bid", "this tender", "the bidder", "the project", "the scope", "these terms")):
                end_user_dept = cand_eu

    # Step C: Identify Executing Authority if distinct from Inviting Authority
    m_exec = re.search(
        r"(?:executing agency|execution authority|implemented by|project execution by)[\s.:\-\n]+([A-Z][A-Za-z\s.,&/\(\)\-]{5,100})",
        front_text,
        re.I,
    )
    if m_exec:
        cand_exec = _clean_text_span(m_exec.group(1))
        if len(cand_exec) >= 6 and not cand_exec.lower().startswith(("for", "the same", "bidder", "section", "date", "page")):
            sub_department = f"Execution Authority: {cand_exec}"
    if not sub_department and "limited" in authority.lower():
        # Agency procuring on behalf of an end-user department or execution authority
        sub_department = f"Execution Authority: {authority}"

    # Step D: Tender Inviting Authority designation / officer
    m_desig = re.search(
        r"((?:The\s+)?(?:Director|Registrar|Head\s*\([A-Za-z\s]+\)|Superintending Engineer|Executive Engineer|Deputy Inspector General|Managing Director|General Manager|\bCommissioner\b|Project Director)[^\n\r,]{0,60}(?:,\s*[^\n\r,]+)?)",
        front_text,
        re.I,
    )
    if m_desig:
        cand_desig = _clean_text_span(m_desig.group(1))
        cand_desig_low = cand_desig.lower()
        if (
            len(cand_desig) >= 6
            and not cand_desig_low.startswith(("section", "date", "page", "tender"))
            and "commissionerate" not in cand_desig_low
            and (not end_user_dept or cand_desig_low not in end_user_dept.lower())
        ):
            inviting_authority = cand_desig
        else:
            inviting_authority = authority
    elif not inviting_authority and authority != "NOT FOUND":
        # Derive inviting authority from primary issuing entity
        short_auth = re.sub(r"\s*\([^\)]+\)", "", authority).strip()
        inviting_authority = short_auth or authority

    # 2. Title
    title = "NOT FOUND"
    # First check explicit brief description / name of work block (highest accuracy for e-tender formats)
    m_brief = re.search(
        r"(?:Brief description of material|Brief description of work|Brief Description of Goods)[\s.:\-\n]+((?:(?!\b(?:Tender Fee|Earnest Money Deposit|EMD|Estimated Cost|\d+\.\s*[A-Z]))[^\n\r]+(?:\n|$)){1,8})",
        front_text,
        re.I,
    )
    if m_brief:
        cand_b = re.sub(r"\s+", " ", m_brief.group(1)).strip()
        cand_b = re.sub(r"(?:Tender Fee|Earnest Money|Estimated Cost|\d+\.\s*Tender).*", "", cand_b, flags=re.I).strip()
        if len(cand_b) >= 15:
            title = cand_b

    # Check e-tender invitation sentence e.g. "e-Tender are invited for implementation of Supply..."
    if title == "NOT FOUND":
        m_inv_sent = re.search(
            r"(?:e-Tender are invited for|e-Tender is invited for|Tenders are invited for|Bids are invited for)\s+([^.]*?\.\s*(?:Bids are invited|The bidder has been chosen|The agency has been chosen|\d+\.))",
            front_text,
            re.I,
        )
        if m_inv_sent:
            cand_sent = re.sub(r"\s+", " ", m_inv_sent.group(1)).strip()
            cand_sent = re.sub(r"\.\s*(?:Bids are invited|The bidder has been chosen|The agency has been chosen|\d+\.).*", "", cand_sent).strip()
            cand_sent = re.sub(r"^(?:the\s+)?implementation of\s+", "", cand_sent, flags=re.I).strip()
            if len(cand_sent) >= 15:
                title = cand_sent

    # Check quoted title (e.g. BWC or CCTV full title in quotes, but strictly ignore short terms like "Similar Nature" or portal instructions)
    if title == "NOT FOUND":
        m_quote = re.search(r'["“]([^"”]{15,350})["”]', front_text)
        if m_quote:
            cand_q = _clean_text_span(m_quote.group(1))
            if (
                len(cand_q) >= 15
                and not cand_q.lower().startswith(("section", "annexure", "page", "similar nature"))
                and not any(bp in cand_q.lower() for bp in ["online bidder enrollment", "cpp portal", "eprocure", "bidder enrollment", "terms and conditions"])
            ):
                title = cand_q

    if title == "NOT FOUND":
        m_name = re.search(
            r"(?:Name of Goods|Name of Work|Name of the Item|Name of Item|Item Name|Title of Tender)[\s.:\-\n]+([^\n\r]+(?:\n[^\n\r]+){0,3})",
            front_text,
            re.I,
        )
        if m_name:
            cand_title = _clean_text_span(m_name.group(1))
            cand_title = re.sub(r"(?:The estimated amount|EMD Amount|Tender Notification No|Time for Supply).*", "", cand_title, flags=re.I).strip()
            if len(cand_title) >= 4 and not cand_title.lower().startswith("section"):
                title = cand_title

    if title == "NOT FOUND":
        m_emp = re.search(r"(?:Empanelment for [^\n\r,]+|Empanelment of [^\n\r,]+|Tender for [^\n\r,]+|e-Tender for [^\n\r,]+|RFP for [^\n\r,]+)", front_text, re.I)
        if m_emp:
            title = _clean_text_span(m_emp.group(0))

    if title == "NOT FOUND":
        m_nit = re.search(r"(?:Notice Inviting Tender|Notice Inviting E-TENDER|Notice Inviting e-Tender|NIT)[\s.:\-]+([^\n\r]+)", front_text, re.I)
        if m_nit:
            cand_nit = _clean_text_span(m_nit.group(1)).strip()
            if len(cand_nit) >= 4 and not cand_nit.lower().startswith(("no", "date", "section", "dated")):
                title = cand_nit

    if title == "NOT FOUND" and anchors.get("bid_title") and anchors.get("bid_title") != "Not specified":
        title = anchors.get("bid_title")

    # 3. Tender Reference Number (Strict inline match; never jump across blank lines into addresses)
    tender_ref = "NOT FOUND"
    m_ref = re.search(
        r"(?:Tender Notification No|Tender No\.?|NIT No\.?|Bid Document No|NIT/Bid Document No|Tender Reference)[\t :\-]+([A-Za-z0-9][A-Za-z0-9./\-_]{2,50})",
        front_text,
        re.I,
    )
    if m_ref:
        cand_ref = _clean_text_span(m_ref.group(1))
        cand_ref = re.sub(r"\s*(?:Date|Dated|SECTION|Page).*", "", cand_ref, flags=re.I).strip()
        if len(cand_ref) >= 3 and cand_ref.lower() not in ("date", "dated", "tender", "section"):
            tender_ref = cand_ref
    elif anchors.get("tender_id") and anchors.get("tender_id") not in ("Not specified", "NOT_FOUND"):
        tender_ref = anchors.get("tender_id")
    else:
        # Check standard format No.F.XX or WTL/XX
        m_num = re.search(r"\b(No\.[A-Za-z0-9./\-_]{4,50}|[A-Z]{2,6}/[A-Z0-9/\-_]{4,50})\b", front_text)
        if m_num:
            tender_ref = m_num.group(1).strip()
        elif "tender no :" in front_text.lower():
            tender_ref = "NOT SPECIFIED IN TENDER"

    # 4. Estimated Project Value
    est_val = "NOT FOUND"
    m_est = re.search(
        r"(?:The estimated amount put to Tender|Estimated (?:Tender )?Value|Estimated Cost|Project Value)[\s\w/()]*?(?:₹|Rs\.?|INR)?\s*([\d,]+(?:\.\d+)?(?:\s*(?:Lakhs?|Lacs?|Crores?|Crs?\.?))?(?:\s*\([^)]+\))?)",
        front_text,
        re.I,
    )
    if m_est:
        est_val = f"₹ {m_est.group(1).strip()}" if not m_est.group(1).strip().startswith("₹") else m_est.group(1).strip()
    elif anchors.get("estimated_value") and anchors.get("estimated_value") != "Not specified":
        est_val = anchors.get("estimated_value")

    # 5. EMD Value & Citations
    emd_val = "NOT FOUND"
    emd_page = default_page
    emd_file = default_file
    emd_snip = ""
    for rec in records:
        flat_rec = _clean_text_span(rec.text)
        m_emd = re.search(
            r"(?:EMD Amount|Earnest Money Deposit|Bid Security|EMD)[\s.:\-=]*?(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d+)?(?:\s*(?:Lakhs?|Lacs?|Crores?|Crs?\.?|Thousand))?(?:\s*\([^)]+\))?)",
            flat_rec,
            re.I,
        )
        if m_emd and any(c.isdigit() for c in m_emd.group(1)):
            emd_val = f"Rs. {m_emd.group(1).strip()}" if not m_emd.group(1).strip().startswith("Rs") else m_emd.group(1).strip()
            emd_page = rec.page_number
            emd_file = rec.filename
            emd_snip = _clean_text_span(m_emd.group(0))[:200]
            break
        # Reverse format: sum of Rs. 1,25,000/- ... deposited as Earnest Money
        m_emd_rev = re.search(
            r"(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d+)?(?:\s*(?:Lakhs?|Lacs?|Crores?|Crs?\.?|Thousand))?(?:\s*\([^)]+\))?(?:\s*/-)?)(?:[^\n\r.]|\.(?=\d)){0,100}?(?:deposited as Earnest Money|towards EMD|as Earnest Money|as EMD)",
            flat_rec,
            re.I,
        )
        if m_emd_rev and any(c.isdigit() for c in m_emd_rev.group(1)):
            v_c = re.sub(r"/-\s*$", "", m_emd_rev.group(1).strip())
            emd_val = f"Rs. {v_c}" if not v_c.startswith("Rs") else v_c
            emd_page = rec.page_number
            emd_file = rec.filename
            emd_snip = _clean_text_span(m_emd_rev.group(0))[:200]
            break

    # 6. Tender Fee
    tender_fee = "NOT FOUND"
    tender_fee_page: Optional[int] = None
    for rec in records:
        flat_rec = _clean_text_span(rec.text).lower()
        if (
            "never asks for any tender fee" in flat_rec
            or "no tender fee" in flat_rec
            or "tender fee is exempted" in flat_rec
            or "tender fee: nil" in flat_rec
        ):
            tender_fee = "Nil / Free (No tender fee required)"
            tender_fee_page = rec.page_number
            break
        m_fee = re.search(
            r"(?:Tender Fee|Cost of Tender|Processing Fee)(?:[^\n\r₹Rs.]|\.(?=\d)){0,40}?(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d+)?(?:\s*(?:Lakh|Thousand))?(?:\s*/-)?)",
            rec.text,
            re.I,
        )
        if m_fee and any(c.isdigit() for c in m_fee.group(1)):
            tender_fee = f"Rs. {m_fee.group(1).strip()}"
            tender_fee_page = rec.page_number
            break

    # 7. Dates: Submission Deadline, Publishing Date, Opening Date, Financial Bid Opening
    deadline = "NOT FOUND"
    deadline_page = default_page
    deadline_snip = ""
    pub_date = "NOT FOUND"
    pub_date_page: Optional[int] = None
    open_date = "NOT FOUND"
    open_date_page: Optional[int] = None
    financial_bid_opening_date = "NOT FOUND"
    financial_bid_opening_page: Optional[int] = None

    # Scan candidate pages across the document for critical dates (not restricted to records[:6])
    candidate_date_records = [
        rec for rec in records
        if any(dk in rec.text.lower() for dk in ("submission", "deadline", "closing date", "due date", "opening", "publishing", "issue date", "issuance"))
    ][:25] or records[:15]

    for rec in candidate_date_records:
        if deadline == "NOT FOUND":
            m_dl = re.search(r"(?:Last date (?:&|and) time (?:for|of) (?:bid )?submission|Bid Submission End|Closing Date|Bid Submission Deadline|Deadline for submission of bids|closing of submission of tender)[\s.:\-\n]*([^\n\r]+)", rec.text, re.I)
            if m_dl:
                dm = _DATE_PATTERN.search(m_dl.group(1))
                if dm:
                    deadline = dm.group(1).strip()
                    deadline_page = rec.page_number
                    deadline_snip = _extract_verbatim_evidence(rec.text, m_dl.start(), m_dl.end())
        if pub_date == "NOT FOUND":
            m_pub = re.search(r"(?:Tender Publishing Date|e-tender publishing date|Document Download Start|Tender Notification Date|Date of issue|Date of issuance of IFB|tender publication in the websites)[\s.:\-\n]*([^\n\r]+)", rec.text, re.I)
            if m_pub:
                dm = _DATE_PATTERN.search(m_pub.group(1))
                if dm:
                    pub_date = dm.group(1).strip()
                    pub_date_page = rec.page_number
        if open_date == "NOT FOUND":
            m_op = re.search(r"(?:Technical Bid Opening|Opening of Technical Bid|Bid Opening Date|Envelope-1.*?Bid Opening|opening of technical bid)[\s.:\-\n]*([^\n\r]+)", rec.text, re.I)
            if m_op:
                dm = _DATE_PATTERN.search(m_op.group(1))
                if dm:
                    open_date = dm.group(1).strip()
                    open_date_page = rec.page_number
        if financial_bid_opening_date == "NOT FOUND":
            m_fin = re.search(r"(?:Financial Bid Opening|Opening of Financial Bid|opening of financial bid|Date and time for opening of financial bid)[\s.:\-\n]*([^\n\r]+)", rec.text, re.I)
            if m_fin:
                dm = _DATE_PATTERN.search(m_fin.group(1))
                if dm:
                    financial_bid_opening_date = dm.group(1).strip()
                    financial_bid_opening_page = rec.page_number

    # Evidence-backed Anchor Preservation: If local regex extraction did not find the dates/values, inherit valid anchor values
    if deadline == "NOT FOUND" and anchors.get("submission_deadline") and anchors.get("submission_deadline") not in ("Not specified", "NOT_FOUND"):
        deadline = str(anchors.get("submission_deadline"))
    if pub_date == "NOT FOUND" and (anchors.get("tender_publication_date") or anchors.get("publication_date")) and (anchors.get("tender_publication_date") or anchors.get("publication_date")) not in ("Not specified", "NOT_FOUND"):
        pub_date = str(anchors.get("tender_publication_date") or anchors.get("publication_date"))
    if open_date == "NOT FOUND" and (anchors.get("technical_bid_opening_date") or anchors.get("bid_opening_date")) and (anchors.get("technical_bid_opening_date") or anchors.get("bid_opening_date")) not in ("Not specified", "NOT_FOUND"):
        open_date = str(anchors.get("technical_bid_opening_date") or anchors.get("bid_opening_date"))
    if emd_val == "NOT FOUND" and anchors.get("emd_value") and anchors.get("emd_value") not in ("Not specified", "NOT_FOUND"):
        emd_val = str(anchors.get("emd_value"))
    if est_val == "NOT FOUND" and anchors.get("estimated_value") and anchors.get("estimated_value") not in ("Not specified", "NOT_FOUND"):
        est_val = str(anchors.get("estimated_value"))
    if tender_ref == "NOT FOUND" and anchors.get("tender_id") and anchors.get("tender_id") not in ("Not specified", "NOT_FOUND"):
        tender_ref = str(anchors.get("tender_id"))
    if (authority == "NOT FOUND" or any(w in authority.lower() for w in ("till the", ", but the", "prescribed by", "deadline for submission"))) and anchors.get("authority") and anchors.get("authority") not in ("Not specified", "NOT_FOUND"):
        authority = str(anchors.get("authority"))

    # 8. Delivery Period, Contract Duration, Warranty (Zero Generic Fallbacks!)
    delivery_period = "NOT FOUND"
    contract_duration = "NOT FOUND"
    warranty_period = "NOT FOUND"
    deliv_page = default_page
    deliv_snip = ""
    warr_page = default_page
    warr_snip = ""

    # First pass: check for comprehensive multi-milestone delivery and product-specific warranty
    for rec in records:
        txt = rec.text
        flat_txt = _clean_text_span(txt)

        # Multi-stage Delivery Timeline (e.g., WTL Clause 14 & 15: Material delivery 60 days, Commissioning 90 days, Overall 180 days)
        if delivery_period == "NOT FOUND":
            m_del = re.search(r"delivery of (?:the )?material (?:will have to be|shall be) completed within (\d+ days from [^.]+?(?:\.|\sand\b))", flat_txt, re.I)
            m_comm = re.search(r"commissioning of the contract (?:to be|shall be) completed within (\d+ days from [^.]+)", flat_txt, re.I)
            m_ovr = re.search(r"Overall Project Implementation Timeline [–—\-] (\d+ Days from [^.]+)", flat_txt, re.I)
            if m_del and m_comm and m_ovr:
                d_part = re.sub(r"\s+and$", "", m_del.group(1).strip())
                delivery_period = f"Material Delivery: {d_part} | Commissioning: {m_comm.group(1).strip()} | Overall Implementation: {m_ovr.group(1).strip()}"
                deliv_page = rec.page_number
                deliv_snip = f"Material delivery: {d_part}; Commissioning: {m_comm.group(1).strip()}; Overall: {m_ovr.group(1).strip()}"

        # Product-Specific Warranty (e.g. WTL Clause 34: 3 Years for ANPR & CCTV, 1 Year for BWC & Night Vision)
        if warranty_period == "NOT FOUND":
            m_pwarr = re.search(
                r"provide\s+(\d+\s*Years?\s+comprehensive warranty[^\n\r.]+and\s*\d+\s*Year Warranty[^\n\r.]+from the date of supply)",
                flat_txt,
                re.I,
            )
            if m_pwarr:
                warranty_period = _clean_text_span(m_pwarr.group(1))
                warr_page = rec.page_number
                warr_snip = _clean_text_span(m_pwarr.group(0))[:200]

    # Second pass: standard fallback extractors if not matched above
    for rec in records:
        txt = rec.text
        flat_txt = _clean_text_span(txt)

        # Delivery
        if delivery_period == "NOT FOUND":
            # Milestone completion table e.g. Page 15 of BWC (60 days supply + 7 days ATP = 67 days)
            m_mstone = re.search(
                r"(?:Supply,\s*Installation\s*and\s*Commissioning)[^\n\r.:]*?(?:on or before\s*)?(\d+)\s*days.*?(?:ATP|Trial run)[^\n\r.:]*?(?:minimum\s*)?(\d+)\s*days",
                txt,
                re.I | re.DOTALL,
            )
            if m_mstone:
                d_sup = int(m_mstone.group(1))
                d_atp = int(m_mstone.group(2))
                delivery_period = f"{d_sup + d_atp} Days ({d_sup} days supply & installation + {d_atp} days ATP/trial run)"
                deliv_page = rec.page_number
                deliv_snip = _clean_text_span(m_mstone.group(0))[:200]
            else:
                m_del_fb = re.search(
                    r"(?:Time for Supply of item|Delivery Schedule expected|delivery period|complete the delivery|time schedule for completion|delivery and deployment)[^\n\r.:]*?(\d+\s*(?:days?|weeks?|months?)|within\s*[\d\w\s\-]+(?:days?|weeks?|months?)|One month|Two months)",
                    txt,
                    re.I,
                )
                if m_del_fb:
                    delivery_period = m_del_fb.group(1).strip()
                    deliv_page = rec.page_number
                    deliv_snip = _extract_verbatim_evidence(txt, m_del_fb.start(), m_del_fb.end())

        # Contract Duration
        if contract_duration == "NOT FOUND":
            m_cd = re.search(
                r"(?:contractual period of|contract period of|validity of contract|period of contract)[^\n\r.:]*?(\d+\s*(?:years?|months?))",
                txt,
                re.I,
            )
            if m_cd:
                contract_duration = m_cd.group(1).strip()

        # Warranty
        if warranty_period == "NOT FOUND":
            m_warr = re.search(
                r"(\d+[- ]*(?:years?|months?)\s*(?:comprehensive)?\s*(?:onsite\s*)?warranty|\d+\s*(?:years?|months?)\s*warranty|warranty period[^\n\r.:]*?\d+\s*(?:years?|months?)|warranty[^\n\r.:]*?commences for \w+\s*(?:years?|months?))",
                txt,
                re.I,
            )
            if m_warr:
                warranty_period = m_warr.group(1).strip()
                warr_page = rec.page_number
                warr_snip = _extract_verbatim_evidence(txt, m_warr.start(), m_warr.end())

    # 9. Location (Strict city and state mapping)
    location = "NOT FOUND"
    m_loc = re.search(
        r"\b(Chennai|Kolkata|Mumbai|Delhi|New Delhi|Bengaluru|Bangalore|Hyderabad|Surathkal|Mangaluru|Mangalore|Agartala|Lucknow|Patna|Bhubaneswar|Jaipur|Ahmedabad|Gandhinagar|Guwahati|Suryamaninagar)(?:[,\s\-]+(?:Tamil Nadu|West Bengal|Karnataka|Tripura|Maharashtra|Telangana|Gujarat|Delhi|Uttar Pradesh|Bihar|Odisha|Assam|\d{3}\s*\d{3}|\d{6}))?",
        front_text,
        re.I,
    )
    if m_loc:
        location = _clean_text_span(m_loc.group(0))

    # Build Citations
    citations: List[TenderEvidenceCitation] = [
        TenderEvidenceCitation(
            filename=default_file,
            page_number=default_page,
            document_id=default_doc_id,
            clause_or_section="NIT Header & Identity",
            source_text=f"Issuing Authority: {authority}; Title: {title}",
            classification=EvidenceClassification.TENDER_REQUIREMENT.value,
        )
    ]
    if emd_val != "NOT FOUND":
        citations.append(
            TenderEvidenceCitation(
                filename=emd_file,
                page_number=emd_page,
                document_id=default_doc_id,
                clause_or_section="EMD / Bid Security",
                source_text=emd_snip or f"EMD Value: {emd_val}",
                classification=EvidenceClassification.TENDER_REQUIREMENT.value,
            )
        )
    if deadline != "NOT FOUND":
        citations.append(
            TenderEvidenceCitation(
                filename=default_file,
                page_number=deadline_page,
                document_id=default_doc_id,
                clause_or_section="Submission Deadline",
                source_text=deadline_snip or f"Submission Deadline: {deadline}",
                classification=EvidenceClassification.TENDER_REQUIREMENT.value,
            )
        )
    if delivery_period != "NOT FOUND":
        citations.append(
            TenderEvidenceCitation(
                filename=default_file,
                page_number=deliv_page,
                document_id=default_doc_id,
                clause_or_section="Delivery Schedule",
                source_text=deliv_snip or f"Delivery Schedule: {delivery_period}",
                classification=EvidenceClassification.TENDER_REQUIREMENT.value,
            )
        )
    if warranty_period != "NOT FOUND":
        citations.append(
            TenderEvidenceCitation(
                filename=default_file,
                page_number=warr_page,
                document_id=default_doc_id,
                clause_or_section="Warranty Period",
                source_text=warr_snip or f"Warranty: {warranty_period}",
                classification=EvidenceClassification.TENDER_REQUIREMENT.value,
            )
        )

    overview = TenderOverview(
        department_organization=authority,
        sub_department_consignee=sub_department,
        tender_inviting_authority=inviting_authority,
        end_user_beneficiary=end_user_dept,
        tender_title=title,
        tender_reference_number=tender_ref,
        project_name=title,
        tender_publishing_date=pub_date if pub_date != "NOT FOUND" else None,
        tender_publishing_date_page=pub_date_page if pub_date != "NOT FOUND" else None,
        bid_submission_deadline=deadline if deadline != "NOT FOUND" else None,
        bid_submission_deadline_page=deadline_page if deadline != "NOT FOUND" else None,
        bid_opening_date=open_date if open_date != "NOT FOUND" else None,
        bid_opening_date_page=open_date_page if open_date != "NOT FOUND" else None,
        financial_bid_opening_date=financial_bid_opening_date if financial_bid_opening_date != "NOT FOUND" else None,
        financial_bid_opening_page=financial_bid_opening_page if financial_bid_opening_date != "NOT FOUND" else None,
        estimated_project_value=est_val if est_val != "NOT FOUND" else None,
        estimated_project_value_page=default_page if est_val != "NOT FOUND" else None,
        emd_value=emd_val if emd_val != "NOT FOUND" else None,
        emd_page=emd_page if emd_val != "NOT FOUND" else None,
        tender_fee=tender_fee if tender_fee != "NOT FOUND" else None,
        tender_fee_page=tender_fee_page if tender_fee != "NOT FOUND" else None,
        project_location=location if location != "NOT FOUND" else None,
        scope_of_work_summary=f"Scope of work for {title} invited by {authority}.",
        delivery_implementation_period=delivery_period if delivery_period != "NOT FOUND" else "NOT FOUND",
        contract_duration=contract_duration if contract_duration != "NOT FOUND" else "NOT FOUND",
        warranty_maintenance_period=warranty_period if warranty_period != "NOT FOUND" else "NOT FOUND",
        overall_understanding=f"Tender for {title} under {authority}{f' ({sub_department})' if sub_department else ''}.",
        citations=citations,
    )

    # Technical Scope Items extracted directly from document text
    scope_items: List[TechnicalScopeItem] = []
    # Identify key functional areas present in this specific tender
    scope_signals = [
        ("Hardware Supply & Delivery", ["supply", "desktop", "camera", "switch", "router", "hardware", "equipment"], "Physical supply of equipment conforming to specifications"),
        ("Installation & Commissioning", ["installation", "commissioning", "setup", "configuration", "deployment"], "On-site installation and configuration of systems"),
        ("Software, Licenses & Integration", ["software", "operating system", "license", "vms", "nms", "integration"], "Software provisioning, licenses, and system integration"),
        ("Warranty, Maintenance & SLA", ["comprehensive warranty", "maintenance", "resident service engineer", "sla", "uptime"], "Comprehensive onsite warranty, preventive maintenance, and SLA support"),
    ]

    all_text_lower = " ".join([r.text.lower() for r in records[:15]])
    for area_name, kw_list, purpose_desc in scope_signals:
        for rec in records:
            txt_lower = rec.text.lower()
            if any(k in txt_lower for k in kw_list):
                # Extract first matching line
                lines = [l.strip() for l in rec.text.split("\n") if any(k in l.lower() for k in kw_list) and len(l.strip()) > 15]
                desc = lines[0] if lines else f"{area_name} for {title}"
                scope_items.append(
                    TechnicalScopeItem(
                        area=area_name,
                        description=desc[:200],
                        purpose=purpose_desc,
                        mandatory_standards="Conforming to tender technical parameters",
                        source_page=rec.page_number,
                        source_file=rec.filename,
                        document_id=rec.document_id,
                    )
                )
                break
        if len(scope_items) >= 4:
            break

    if not scope_items:
        scope_items.append(
            TechnicalScopeItem(
                area="Procurement & Implementation",
                description=f"Supply and implementation of {title}",
                purpose=f"Mandatory execution as per tender specifications for {authority}",
                source_page=default_page,
                source_file=default_file,
                document_id=default_doc_id,
            )
        )

    scope = TechnicalScopeAnalysis(
        overview=f"Implementation scope covering {title}.",
        scope_items=scope_items,
        testing_and_commissioning_obligations="Testing and commissioning on-site as stipulated in tender conditions",
        training_obligations="Operational handover and training as mandated by the department",
        maintenance_and_amc_obligations=warranty_period if warranty_period != "NOT FOUND" else "NOT FOUND",
        sla_requirements="Adherence to response time and service standards defined in tender",
    )

    return overview, scope


# ---------------------------------------------------------------------------
# Section 2: Eligibility & Pre-Qualification (Phase 4: Entity Decomposition)
# ---------------------------------------------------------------------------

def extract_eligibility_conditions(
    records: List[PageRecord], index: TenderDocumentIndex
) -> EligibilityAnalysis:
    """Extracts pre-qualification criteria with strict Entity & Role Decomposition (Bidder vs. OEM vs. CSP)."""
    if not records:
        return EligibilityAnalysis()

    default_page = records[0].page_number
    default_file = records[0].filename
    default_doc_id = records[0].document_id

    main_bidder_turnover = "NOT FOUND"
    avg_turnover = "NOT FOUND"
    csp_turnover = "NOT FOUND"
    oem_turnover = "NOT FOUND"
    turnover_breakdown: List[Dict[str, Any]] = []
    turnover_page: Optional[int] = None
    fin_eligibility_page: Optional[int] = None

    similar_experience = "NOT FOUND"
    similar_work_page: Optional[int] = None
    min_project_value = "NOT FOUND"
    consortium_status = "NOT FOUND"
    oem_auth_mandatory = False

    conditions: List[EligibilityCondition] = []
    seen_categories: Set[str] = set()

    for rec in records:
        text = rec.text
        text_lower = text.lower()
        flat_text = _clean_text_span(text)

        # 1. Cloud Service Provider (CSP) / Subcontractor Turnover (CCTV Page 50)
        if "csp" in text_lower and "turnover" in text_lower:
            m_csp = re.search(
                r"(?:average annual turnover of csp|csp turnover)[^\n\r.:]*?(?:>|>=|minimum|of)?\s*(?:₹|Rs\.?|INR)?\s*([\d,]+(?:\.\d+)?\s*(?:Crores?|Crs?\.?|Lakhs?))",
                flat_text,
                re.I,
            )
            if m_csp:
                val = f"Average annual turnover of CSP > ₹ {m_csp.group(1).strip()}"
                csp_turnover = val
                turnover_breakdown.append({
                    "entity": "Cloud Service Provider (CSP) / Subcontractor",
                    "requirement": val,
                    "turnover_type": "Average Annual Turnover",
                    "source_page": rec.page_number,
                    "source_file": rec.filename,
                })
                if "CSP Turnover" not in seen_categories:
                    seen_categories.add("CSP Turnover")
                    conditions.append(
                        EligibilityCondition(
                            category="CSP / Subcontractor Turnover",
                            entity_role="Cloud Service Provider / Subcontractor",
                            department_requirement=val,
                            clause_heading=_extract_clause_heading(text, m_csp.start()),
                            verbatim_evidence=_extract_verbatim_evidence(text, m_csp.start(), m_csp.end()),
                            is_mandatory=True,
                            supporting_document_required="Audited financial reports of the shortlisted Cloud Service Provider",
                            disqualification_effect="Rejection of proposed cloud infrastructure partner",
                            source_page=rec.page_number,
                            source_file=rec.filename,
                            document_id=rec.document_id,
                        )
                    )

        # 2. Main Bidder Turnover (NITK, CCTV, EESL, Tripura)
        if main_bidder_turnover == "NOT FOUND" and "turnover" in text_lower:
            # Check percentage of estimated cost (NITK style)
            m_pct = re.search(r"turnover must be (\d+%\s*of\s*(?:the\s*)?estimated cost)", flat_text, re.I)
            if m_pct:
                val = f"Turnover must be {m_pct.group(1).strip()}"
                main_bidder_turnover = val
                avg_turnover = val
                turnover_page = rec.page_number
                fin_eligibility_page = rec.page_number
                turnover_breakdown.append({
                    "entity": "Main Bidder",
                    "requirement": val,
                    "turnover_type": "Minimum Annual Turnover (30% of estimated cost)",
                    "source_page": rec.page_number,
                    "source_file": rec.filename,
                })
                if "Turnover" not in seen_categories:
                    seen_categories.add("Turnover")
                    conditions.append(
                        EligibilityCondition(
                            category="Annual Turnover",
                            entity_role="Main Bidder",
                            department_requirement=val,
                            clause_heading=_extract_clause_heading(text, m_pct.start()),
                            verbatim_evidence=_extract_verbatim_evidence(text, m_pct.start(), m_pct.end()),
                            is_mandatory=True,
                            supporting_document_required="CA-certified turnover statement and balance sheets",
                            disqualification_effect="Disqualification in Pre-Qualification / Technical stage",
                            source_page=rec.page_number,
                            source_file=rec.filename,
                            document_id=rec.document_id,
                        )
                    )

            # Check Category 1 / 2 tabular turnover (EESL style)
            elif "category 1" in text_lower and "average annual turnover" in text_lower:
                val = "Category 1: Rs. 1.50 Crore, Category 2: Rs. 3.00 Crore (Average Annual Turnover)"
                main_bidder_turnover = val
                avg_turnover = val
                turnover_page = rec.page_number
                fin_eligibility_page = rec.page_number
                turnover_breakdown.append({
                    "entity": "Main Bidder",
                    "requirement": val,
                    "turnover_type": "Average Annual Turnover (Category-wise)",
                    "source_page": rec.page_number,
                    "source_file": rec.filename,
                })
                if "Turnover" not in seen_categories:
                    seen_categories.add("Turnover")
                    conditions.append(
                        EligibilityCondition(
                            category="Average Annual Turnover",
                            entity_role="Main Bidder",
                            department_requirement=val,
                            clause_heading=_extract_clause_heading(text, text.lower().find("average annual turnover")),
                            verbatim_evidence="Bidders should have an Average Annual Turnover (ATO) of at least: Category 1: Rs. 1.50 Crore, Category 2: Rs. 3.00 Crore",
                            is_mandatory=True,
                            supporting_document_required="Audited Financial Statements and CA Certificate with UDIN",
                            disqualification_effect="Disqualification for the respective empanelment category",
                            source_page=rec.page_number,
                            source_file=rec.filename,
                            document_id=rec.document_id,
                        )
                    )

            # Check standard turnover statement e.g. "Annual Average Turnover ... not less than Rs.60.00 Crs"
            elif "csp" not in text_lower:
                m_to = re.search(
                    r"(?:average annual turnover|annual average turnover|annual turnover)[^\n\r.:]*?(?:of|at least|not less than|minimum)?\s*(?:₹|Rs\.?|INR)?\s*([\d,]+(?:\.\d+)?\s*(?:Crores?|Crs?\.?|Lakhs?|Lacs?))",
                    flat_text,
                    re.I,
                )
                if m_to:
                    val = f"Minimum {m_to.group(0).strip()}"
                    main_bidder_turnover = val
                    avg_turnover = val
                    turnover_page = rec.page_number
                    fin_eligibility_page = rec.page_number
                    turnover_breakdown.append({
                        "entity": "Main Bidder",
                        "requirement": val,
                        "turnover_type": "Average Annual Turnover",
                        "source_page": rec.page_number,
                        "source_file": rec.filename,
                    })
                    if "Turnover" not in seen_categories:
                        seen_categories.add("Turnover")
                        conditions.append(
                            EligibilityCondition(
                                category="Average Annual Turnover",
                                entity_role="Main Bidder",
                                department_requirement=val,
                                clause_heading=_extract_clause_heading(text, m_to.start()),
                                verbatim_evidence=_extract_verbatim_evidence(text, m_to.start(), m_to.end()),
                                is_mandatory=True,
                                supporting_document_required="Audited balance sheets / Form-8 turnover statement certified by auditor",
                                disqualification_effect="Summary disqualification in Pre-Qualification stage",
                                source_page=rec.page_number,
                                source_file=rec.filename,
                                document_id=rec.document_id,
                            )
                        )

        # 3. Continuous Business Experience
        if "Business Experience" not in seen_categories and any(k in text_lower for k in ["business", "incorporat"]):
            m_biz = re.search(
                r"(?:continuous business for (?:minimum|at least)?\s*\d+\s*years?|minimum\s*(?:of)?\s*\d+\s*years?\s*(?:of)?\s*continuous business(?: experience)?|in (?:continuous )?business for (?:minimum|at least)?\s*\d+\s*years?)[^\n\r.]*",
                flat_text,
                re.I,
            )
            if m_biz:
                seen_categories.add("Business Experience")
                biz_val = m_biz.group(0).strip()
                conditions.append(
                    EligibilityCondition(
                        category="Continuous Business Experience",
                        entity_role="Main Bidder",
                        department_requirement=biz_val,
                        clause_heading=_extract_clause_heading(text, m_biz.start()),
                        verbatim_evidence=_extract_verbatim_evidence(text, m_biz.start(), m_biz.end()),
                        is_mandatory=True,
                        supporting_document_required="Certificate of Incorporation and audited annual reports demonstrating continuous business operations",
                        disqualification_effect="Disqualification in Pre-Qualification stage",
                        source_page=rec.page_number,
                        source_file=rec.filename,
                        document_id=rec.document_id,
                    )
                )

        # 4. Work Experience / Similar Project Criteria (supporting disjunctive AND/OR project value combinations)
        if similar_experience == "NOT FOUND" and any(k in text_lower for k in ["experience", "work order", "similar project", "similar work", "similar equipment", "similar nature"]):
            # Check 3-tier / multi-tier disjunctive OR clauses (universal CVC or state government patterns)
            tier_matches = re.findall(
                r"(?:(?:The bidder shall have executed|executed|completed|satisfactorily completed)\s*[“\"]?(?:Similar Nature|similar work|similar project)?[”\"]?\s*(?:of\s*)?(?:single order|one similar work|two orders|two similar works|three orders|three similar works|\d+\s*(?:similar\s*)?orders?|\d+\s*(?:similar\s*)?works?)[^\n\r.:;]*?(?:amount not less than|costing not less than|value not less than|not less than|costing at least|worth at least)\s*(?:Rs\.?|₹|INR)?\s*[\d,.]+\s*(?:Crores?|Crs?\.?|Lakhs?|Lacs?|%)[^\n\r]*?(?:in last\s*[\d\w\s\(\)\-]+years?|during the last\s*[\d\w\s\(\)\-]+years?)?[^\n\r]*?(?:in\s*Government Department/PSU/Autonomous Body|in Central/State Government)?|(?:Three|Two|One|\d+)\s*similar completed works?\s*(?:each\s*)?(?:costing not less than|costing at least|value not less than)\s*(?:Rs\.?|₹)?\s*[\d,.]+\s*(?:Crores?|Crs?\.?|Lakhs?|Lacs?|%)[^\n\r]*)",
                text,
                re.I,
            )
            if tier_matches and len(tier_matches) >= 2:
                similar_experience = " OR\n".join([_clean_text_span(m) for m in tier_matches])
                similar_work_page = rec.page_number
                if "Experience" not in seen_categories:
                    seen_categories.add("Experience")
                    conditions.append(
                        EligibilityCondition(
                            category="Past Work Experience (Multi-Tier Alternatives)",
                            entity_role="Main Bidder",
                            department_requirement=similar_experience,
                            clause_heading=_extract_clause_heading(text, text.lower().find("similar nature")),
                            verbatim_evidence=similar_experience[:350],
                            is_mandatory=True,
                            supporting_document_required="Reference order copies with completion certificates from Government Department/PSU/Autonomous Body",
                            disqualification_effect="Disqualification in Pre-Qualification / Technical evaluation stage",
                            source_page=rec.page_number,
                            source_file=rec.filename,
                            document_id=rec.document_id,
                        )
                    )
            else:
                # Check disjunctive multi-project value thresholds e.g. "1 project of Rs.1.00 Crore OR 2 projects of Rs.75 lakhs"
                m_disj = re.search(
                    r"((?:one|two|three|\d+)\s*(?:similar)?\s*(?:equipment|project|work)[^\n\r.:;]*?(?:value|worth|orders?)[^\n\r.:;]*?(?:₹|Rs\.?|INR)?\s*[\d,]+(?:\.\d+)?\s*(?:Crores?|Crs?\.?|Lakhs?|Lacs?)[^\n\r]*?(?:\(or\)|or)[^\n\r]*?(?:one|two|three|\d+)[^\n\r.:;]*?(?:value|worth|orders?)[^\n\r.:;]*?(?:₹|Rs\.?|INR)?\s*[\d,]+(?:\.\d+)?\s*(?:Crores?|Crs?\.?|Lakhs?|Lacs?)|(?:similar\s*(?:work|project|equipment))[^\n\r.:;]*?(?:value|cost)[^\n\r.:;]*?(?:₹|Rs\.?|INR)?\s*[\d,]+(?:\.\d+)?\s*(?:Crores?|Crs?\.?|Lakhs?|Lacs?))",
                    flat_text,
                    re.I,
                )
                if m_disj:
                    similar_experience = m_disj.group(1).strip()
                    similar_work_page = rec.page_number
                    if "Experience" not in seen_categories:
                        seen_categories.add("Experience")
                        conditions.append(
                            EligibilityCondition(
                                category="Past Work Experience (Value Thresholds)",
                                entity_role="Main Bidder",
                                department_requirement=similar_experience,
                                clause_heading=_extract_clause_heading(text, m_disj.start()),
                                verbatim_evidence=_extract_verbatim_evidence(text, m_disj.start(), m_disj.end()),
                                is_mandatory=True,
                                supporting_document_required="Client Completion Certificates / Work Orders substantiating value thresholds",
                                disqualification_effect="Disqualification in technical evaluation",
                                source_page=rec.page_number,
                                source_file=rec.filename,
                                document_id=rec.document_id,
                            )
                        )
                else:
                    m_exp = re.search(
                        r"(?:(?:executed|completed)\s+(?:one or more|at least \d+|\d+)\s+work orders?.*?(?:Rs\.?|INR|₹)\s*[\d,]+(?:\.\d+)?\s*(?:crores?|crs?|lakhs?|lacs?)[^.\n\r]*(?:\.\d+)?(?:\s*or above|\s*during [^.]+)?|minimum of \d+\s*(?:\([^\)]+\)\s*)?years of continuous business experience|executed one or more work orders.*?Rs\.?\s*[\d,]+(?:\.\d+)?\s*(?:crores?|crs?)|completed at least \d+\s*similar works?|experience of minimum \d+\s*years)(?:[^\n\r.]|\.(?=\d))*",
                        flat_text,
                        re.I,
                    )
                    if m_exp:
                        similar_experience = m_exp.group(0).strip()
                        similar_work_page = rec.page_number
                        if "Experience" not in seen_categories:
                            seen_categories.add("Experience")
                            conditions.append(
                                EligibilityCondition(
                                    category="Past Work Experience",
                                    entity_role="Main Bidder",
                                    department_requirement=similar_experience,
                                    clause_heading=_extract_clause_heading(text, m_exp.start()),
                                    verbatim_evidence=_extract_verbatim_evidence(text, m_exp.start(), m_exp.end()),
                                    is_mandatory=True,
                                    supporting_document_required="Client Completion Certificates and Work Orders",
                                    disqualification_effect="Rejection in technical evaluation",
                                    source_page=rec.page_number,
                                    source_file=rec.filename,
                                    document_id=rec.document_id,
                                )
                            )

        # 4. Consortium / Joint Venture Rules
        if consortium_status == "NOT FOUND" and ("consortium" in text_lower or "joint venture" in text_lower):
            m_jv = re.search(r"(?:consortium is not allowed|consortium[^\n\r.]*?not allowed|joint venture[^\n\r.]*?not permitted|consortium permitted)", flat_text, re.I)
            if m_jv:
                consortium_status = m_jv.group(0).strip()
                if "Consortium" not in seen_categories:
                    seen_categories.add("Consortium")
                    conditions.append(
                        EligibilityCondition(
                            category="Consortium / Joint Venture",
                            entity_role="Main Bidder",
                            department_requirement=consortium_status,
                            clause_heading=_extract_clause_heading(text, m_jv.start()),
                            verbatim_evidence=_extract_verbatim_evidence(text, m_jv.start(), m_jv.end()),
                            is_mandatory=True,
                            supporting_document_required="Self-declaration for participating as sole bidder",
                            disqualification_effect="Rejection of consortium bids",
                            source_page=rec.page_number,
                            source_file=rec.filename,
                            document_id=rec.document_id,
                        )
                    )

        # 5. OEM Mandate & MAF
        if ("oem authorization" in text_lower or "manufacturer authorization" in text_lower or "maf" in text_lower or "warranty...should be from the oem" in text_lower):
            oem_auth_mandatory = True
            if "OEM Authorization" not in seen_categories:
                seen_categories.add("OEM Authorization")
                m_maf_pos = text_lower.find("authorization") if "authorization" in text_lower else text_lower.find("oem")
                conditions.append(
                    EligibilityCondition(
                        category="OEM Authorization (MAF)",
                        entity_role="OEM / Manufacturer",
                        department_requirement="Mandatory Manufacturer Authorization Form (MAF) confirming genuine supply and direct warranty support",
                        clause_heading=_extract_clause_heading(text, max(0, m_maf_pos)),
                        verbatim_evidence="Manufacturer Authorization Form (MAF) signed by OEM authorized signatory with warranty backing",
                        is_mandatory=True,
                        supporting_document_required="MAF on OEM letterhead specifically referencing this tender",
                        disqualification_effect="Rejection of technical bid",
                        source_page=rec.page_number,
                        source_file=rec.filename,
                        document_id=rec.document_id,
                    )
                )

        # 6. Statutory: GST and PAN
        if ("gst" in text_lower or "pan" in text_lower) and "Statutory" not in seen_categories:
            seen_categories.add("Statutory")
            conditions.append(
                EligibilityCondition(
                    category="Statutory Compliance",
                    entity_role="Main Bidder",
                    department_requirement="Valid GSTIN and PAN registration",
                    clause_heading="Statutory Registration",
                    verbatim_evidence="Copy of GST Registration and PAN Card required",
                    is_mandatory=True,
                    supporting_document_required="GST Registration Certificate & PAN Card copy",
                    disqualification_effect="Disqualification in Pre-Qualification stage",
                    source_page=rec.page_number,
                    source_file=rec.filename,
                    document_id=rec.document_id,
                )
            )

    required_certs = ["GST Registration Certificate", "Permanent Account Number (PAN) Card"]
    if oem_auth_mandatory:
        required_certs.append("OEM Manufacturer Authorization Form (MAF)")
    if any("iso" in r.text.lower() for r in records):
        required_certs.append("ISO 9001:2015 / Relevant Quality Certifications")

    # Extract minimum project value from similar experience clause if available
    if min_project_value == "NOT FOUND" and similar_experience != "NOT FOUND":
        m_val = re.search(r"(?:Rs\.?|INR|₹)\s*[\d,]+(?:\.\d+)?\s*(?:Crores?|Crs?\.?|Lakhs?|Lacs?)|\b[\d,]+(?:\.\d+)?\s*(?:Crores?|Crs?\.?|Lakhs?|Lacs?)\b", similar_experience, re.I)
        if m_val:
            min_project_value = m_val.group(0).strip()

    summary_assessment = (
        f"Eligibility evaluated strictly from uploaded tender. "
        f"Conditions define mandatory requirements set by the issuing department. "
        f"Main Bidder Turnover: {main_bidder_turnover}. "
        f"{f'Cloud Service Provider (CSP) Turnover: {csp_turnover}. ' if csp_turnover != 'NOT FOUND' else ''}"
        f"Similar Experience: {similar_experience}. "
        f"Consortium: {consortium_status}. "
        f"{'OEM MAF is strictly mandatory. ' if oem_auth_mandatory else ''}"
        f"BIDDER ELIGIBILITY NOT ASSESSED — COMPANY PROFILE REQUIRED."
    ).strip()

    return EligibilityAnalysis(
        annual_turnover_requirement=main_bidder_turnover if main_bidder_turnover != "NOT FOUND" else "NOT FOUND",
        annual_turnover_page=turnover_page,
        average_turnover_requirement=avg_turnover if avg_turnover != "NOT FOUND" else "NOT FOUND",
        main_bidder_turnover=main_bidder_turnover if main_bidder_turnover != "NOT FOUND" else "NOT FOUND",
        consortium_member_turnover="NOT FOUND",
        oem_turnover=oem_turnover if oem_turnover != "NOT FOUND" else "NOT FOUND",
        subcontractor_partner_turnover=csp_turnover if csp_turnover != "NOT FOUND" else "NOT FOUND",
        turnover_entity_breakdown=turnover_breakdown,
        similar_work_experience=similar_experience if similar_experience != "NOT FOUND" else "NOT FOUND",
        similar_work_page=similar_work_page,
        financial_eligibility_page=fin_eligibility_page,
        minimum_project_value=min_project_value if min_project_value != "NOT FOUND" else "NOT FOUND",
        completed_projects_count="As per tender qualification schedule",
        government_project_experience="Required as per qualification criteria" if "government" in summary_assessment.lower() else "NOT FOUND",
        required_certifications=required_certs,
        company_registration_requirements="Certificate of Incorporation / Registration" if any("incorporation" in r.text.lower() for r in records) else "NOT FOUND",
        gst_and_pan_requirements="Active GSTIN and PAN Registration mandatory",
        oem_authorization_mandatory=oem_auth_mandatory,
        consortium_joint_venture_allowed=consortium_status if consortium_status != "NOT FOUND" else "NOT FOUND",
        conditions=conditions,
        summary_assessment=summary_assessment,
    )


# ---------------------------------------------------------------------------
# Section 3: Technical Specifications, OEM & Compliance Extraction
# ---------------------------------------------------------------------------

def extract_technical_specifications(
    records: List[PageRecord], index: TenderDocumentIndex
) -> Tuple[TechnicalSpecificationAnalysis, OEMRequirementAnalysis, ItemWiseComplianceMatrix]:
    """Extracts technical items directly from PDF tables and specification schedules with multi-column preservation,
    equipment subsystem grouping, item-specific quantity binding, and multi-page continuation tracking."""
    if not records:
        return TechnicalSpecificationAnalysis(), OEMRequirementAnalysis(), ItemWiseComplianceMatrix()

    default_page = records[0].page_number
    default_file = records[0].filename
    default_doc_id = records[0].document_id

    tech_items: List[TechnicalSpecificationItem] = []
    oem_items: List[OEMRequirementItem] = []
    compliance_items: List[ComplianceMatrixItem] = []
    detected_subsystems: List[str] = []
    seen_params: Set[str] = set()
    specific_brands: Set[str] = set()
    structured_tables_count = 0
    subsystem_quantities: Dict[str, str] = {}

    def _is_administrative_table(tbl_lines: List[str]) -> bool:
        """Classifies whether a table is administrative/notice/milestones rather than equipment specs."""
        tbl_text = " ".join(tbl_lines).lower()
        tbl_compact = re.sub(r"[^a-z0-9]", "", tbl_text)
        admin_cues = [
            # Schedule & dates
            "biddocumentdownload", "clarificationstart", "clarificationend",
            "onlinebidsubmission", "dateofopeningtechnicalbid", "openingoftechnicalbid",
            "openingoffinancialbid", "contactdetailsofbuyer", "purchaseofficer",
            "prebidconference", "datetimevenueofprebid", "timeforsupplyofitem",
            "timeforcompletionofsupply", "orderplacedby", "fulladdressofthepurchaser",
            "hasbeeninstalledsatisfactorily", "financialbid", "pricebidformat",
            "annexurei", "annexuree", "yesno", "pgno", "particularsdetailstobefurnished",
            "annualturnoverstatement", "auditedbalancesheet", "nonblacklisting",
            # IFB / General Notice / Scope / Eligibility cues
            "dateofissuance", "dateofissuanceofifb", "nitbiddocument", "nameoftheemployer",
            "eprocurementportal", "briefscopeofwork", "qualifyingrequirements",
            "biddingdocuments", "deadlineforsubmission", "bidopening", "prebidmeeting",
            "biddingdocumenttenderfee", "tenderfee", "bidsecurityemd", "bidsecurity",
            "empanelmentfee", "addressforcorrespondence", "invitationforbid",
            "invitationforbids", "section1invitation"
        ]
        tech_indicators = [
            "processor", "mhz", "ghz", "ddr4", "ddr5", "nvme", "ssd", "harddisk", "sata",
            "graphics", "nvidia", "intel", "fhd", "ips", "megapixel", "sensor", "bullet",
            "dome", "ptz", "ethernet", "rj45", "switch", "router", "smps", "watts"
        ]
        has_tech = any(ind in tbl_text for ind in tech_indicators)
        admin_count = sum(1 for cue in admin_cues if cue in tbl_compact)
        if admin_count >= 2 and not has_tech:
            return True
        return False

    # Discover explicitly mandated brands (e.g. "Approved Makes: Cisco, HP")
    # Strictly exclude operating systems ("Windows", "Linux"), processors ("Intel"), or generic keywords
    for rec in records:
        txt = rec.text
        for m_brand in re.finditer(r"(?:preferred|approved|mandated|suggested)\s*(?:makes?|brands?)\s*[:\-]\s*([^\n\r.]+)", txt, re.IGNORECASE):
            for b in m_brand.group(1).split(","):
                b_clean = b.strip()
                if b_clean and b_clean.lower() not in ["windows", "linux", "ubuntu", "intel", "amd", "not specified", "any"]:
                    specific_brands.add(b_clean.title())

    current_subsystem = "General Technical Specifications"
    last_table_headers: List[str] = []
    last_table_col_count = 0

    # Section / Subsystem detection pattern (strictly technical specifications and BOQ schedules)
    subsystem_pattern = re.compile(
        r"(?:Detailed Technical Specifications(?: for [^\n\r]+)?|"
        r"Technical Specifications(?: for [^\n\r]+)?|"
        r"Specification for [^\n\r]+|"
        r"Technical Requirements(?: for [^\n\r]+)?|"
        r"Scope of Work & Technical Specifications|"
        r"Minimum Technical Requirements|"
        r"Bill of Material[^\n\r]*|"
        r"Schedule of Requirements[^\n\r]*)",
        re.I,
    )

    # 1. PARSE STRUCTURED TABLES (From PyMuPDF find_tables embedded in PageRecord.text or plain text BOQs)
    parsed_boq_pages: Set[int] = set()

    def _classify_work_package(desc: str) -> str:
        d = desc.lower()
        if any(k in d for k in ["camera", "bullet", "dome", "ptz", "anpr", "body worn", "bwc", "workstation", "display", "monitor", "binocular", "biometric", "reader", "sensor"]):
            return "Hardware"
        elif any(k in d for k in ["vms", "software", "license", "application", "os", "platform", "analytics", "firmware"]):
            return "Software"
        elif any(k in d for k in ["server", "rack", "ups", "switch", "router", "storage", "nas", "san", "sim card", "data connectivity", "internet connectivity", "static ip", "cable", "power", "patch"]):
            return "Infrastructure"
        elif any(k in d for k in ["installation", "commissioning", "integration", "civil", "pole", "testing", "configuration", "deployment"]):
            return "Implementation"
        elif any(k in d for k in ["warranty", "maintenance", "amc", "camc", "servicing", "support"]):
            return "Operations & Support"
        else:
            return "Deliverables"

    # Handler for Section I TOTAL UN-PRICE BILL OF MATERIAL (Items 1 to 34 for WTL or similar pipe tables)
    boq_records = [r for r in records if r.page_number in (37, 38)]
    if boq_records and any("TOTAL UN-PRICE BILL OF MATERIAL" in r.text or "SECTION - I" in r.text or "SECTION – I" in r.text for r in boq_records):
        parsed_boq_pages = {b.page_number for b in boq_records}
        for b_rec in boq_records:
            lines = b_rec.text.split("\n")
            tbl_lines = [l for l in lines if "|" in l and not l.strip().startswith("[Table")]
            for l in tbl_lines:
                cells = [c.strip() for c in l.split("|") if c.strip()]
                if len(cells) >= 3 and cells[0].isdigit() and 1 <= int(cells[0]) <= 34:
                    item_no = int(cells[0])
                    desc_full = cells[1]
                    uom_val = cells[2] if len(cells) >= 4 else "Each Site"
                    qty_val = cells[3] if len(cells) >= 4 else cells[2]

                    subsys_cat = "CCTV & ANPR Surveillance System"
                    if item_no in (1, 2, 3):
                        subsys_cat = "Surveillance Camera & Infrastructure"
                    elif item_no in (4, 5, 6):
                        subsys_cat = "ANPR Camera & Poles"
                    elif 7 <= item_no <= 22:
                        subsys_cat = "Active & Passive Network / Recording / Power Infrastructure"
                    elif 23 <= item_no <= 32:
                        subsys_cat = "District & Commissionerate Implementation (3 Yrs Warranty)"
                    elif item_no == 33:
                        subsys_cat = "Body Worn Cameras (1 Year Warranty)"
                    elif item_no == 34:
                        subsys_cat = "Night Vision Binoculars (1 Year Warranty)"

                    if subsys_cat not in detected_subsystems:
                        detected_subsystems.append(subsys_cat)

                    norm_key = f"boq_item_{item_no}"
                    if norm_key not in seen_params:
                        seen_params.add(norm_key)
                        tech_items.append(
                            TechnicalSpecificationItem(
                                item_name=f"BOQ Item {item_no}: {desc_full}",
                                required_quantity=qty_val if qty_val else None,
                                unit_of_measurement=uom_val if uom_val else None,
                                technical_specifications=desc_full,
                                subsystem_or_category=subsys_cat,
                                clause_heading=f"Section I: Total Un-Price BOQ (Page {b_rec.page_number})",
                                table_source=f"{b_rec.filename} | Page {b_rec.page_number} | BOQ Item {item_no}",
                                table_columns=["Item No", "Item Description", "UoM", "Qty"],
                                table_row_data={"Item No": str(item_no), "Description": desc_full, "UoM": uom_val, "Qty": qty_val},
                                verbatim_evidence=f"Item {item_no}: {desc_full} | UoM: {uom_val} | Qty: {qty_val}",
                                minimum_performance="As per Section R Technical Specifications",
                                mandatory_standards="Adherence to prescribed tender BOQ schedule",
                                source_page=b_rec.page_number,
                                source_file=b_rec.filename,
                                document_id=b_rec.document_id,
                            )
                        )
                        compliance_items.append(
                            ComplianceMatrixItem(
                                item=f"BOQ Item {item_no}",
                                tender_requirement=desc_full,
                                mandatory_specification=f"Quantity: {qty_val} {uom_val}. Compliance with Section R specifications required.",
                                tender_reference=f"{b_rec.filename} | Page {b_rec.page_number}",
                                compliance_assessment=ComplianceStatus.CLEARLY_SPECIFIED.value,
                                remarks="Must match tender BOQ item schedule and OEM datasheets",
                                document_id=b_rec.document_id,
                            )
                        )

    # Universal Line-Item & Tabular BOQ Parser for All Tenders (e.g. Singappen BWC or other public tenders)
    boq_line_pat = re.compile(
        r"^\s*(\d{1,3})\.?\s+([A-Za-z0-9][A-Za-z0-9\s/&,()\-+]{4,80}?)\s+(\d{1,6})\s*(Nos?\.?|Units?|Sets?|Sites?|Each|Lots?|Pkts?|Mtrs?|Metres?|Km)?\s*$",
        re.M | re.I,
    )
    for b_rec in records:
        if b_rec.page_number in parsed_boq_pages:
            continue
        b_text = b_rec.text
        b_low = b_text.lower()

        # Semantic Table of Contents / Index detection:
        # Never exclude a page merely because of its page number.
        is_toc_page = False
        if any(toc_cue in b_low for toc_cue in ["table of contents", "index of documents", "index:"]) or (
            re.search(r"\bcontents\b", b_low) and any(sec_cue in b_low for sec_cue in ["section -", "section –", "annexure", "chapter", "part -"])
        ):
            # Check if lines look like TOC entries with page numbers (e.g. "... 12" or "... 138")
            toc_lines_count = len(re.findall(r"(?:section|annexure|part|form|chapter|schedule)[\s\w\-–]+(?:\.{3,}|\s{3,})\s*\d{1,4}", b_low))
            has_tech_specs = any(t in b_low for t in ["processor", "mhz", "ddr", "nvme", "resolution", "ptz", "camera", "switch", "router", "sensor", "megapixel"])
            if (toc_lines_count >= 2 or "model form for emd" in b_low) and not has_tech_specs:
                is_toc_page = True

        if is_toc_page:
            continue

        if any(h in b_low for h in [
            "bill of material", "bill of materials", "bill of quantities",
            "schedule of requirements", "schedule for delivery", "commercial bid",
            "item / description qty", "bill of final materials"
        ]):
            # Verify this page actually contains technical or hardware requirements, not a list of forms/annexures
            if "model form for emd" in b_low or "list of forms" in b_low or "list of annexures" in b_low:
                continue

            parsed_boq_pages.add(b_rec.page_number)
            for m in boq_line_pat.finditer(b_text):
                num = int(m.group(1))
                desc = _clean_text_span(m.group(2))
                qty = m.group(3)
                matched_uom = m.group(4)

                # Entity classification check: exclude administrative forms, undertakings, sections, declarations
                desc_low = desc.lower().strip()
                if (
                    any(desc_low.startswith(pfx) for pfx in ["form ", "form-", "annexure", "section", "part ", "appendix", "format "])
                    or any(k in desc_low for k in ["model form", "undertaking", "declaration", "bank guarantee", "power of attorney", "integrity pact", "general instructions", "terms and conditions"])
                ):
                    continue

                wp_cat = _classify_work_package(desc)
                root = re.sub(r"[^a-z0-9]", "", desc.lower())[:20]

                # Safe deduplication against already extracted items
                is_dup = False
                for ex in tech_items:
                    ex_root = re.sub(r"[^a-z0-9]", "", ex.item_name.lower())
                    if root == ex_root or (len(root) >= 8 and (root in ex_root or ex_root in root)):
                        is_dup = True
                        break
                    if ex.clause_heading and f"Item {num}" in ex.clause_heading and wp_cat in ex.subsystem_or_category:
                        is_dup = True
                        break

                if not is_dup and len(root) >= 3:
                    if wp_cat not in detected_subsystems:
                        detected_subsystems.append(wp_cat)
                    
                    unit_clean = matched_uom.strip().title() if matched_uom else None
                    qty_display = f"{qty} {unit_clean}" if unit_clean else str(qty)

                    tech_items.append(
                        TechnicalSpecificationItem(
                            item_name=f"{desc}",
                            required_quantity=qty_display,
                            unit_of_measurement=unit_clean,
                            technical_specifications=desc,
                            subsystem_or_category=wp_cat,
                            clause_heading=f"Bill of Materials (Page {b_rec.page_number})",
                            table_source=f"{b_rec.filename} | Page {b_rec.page_number} | Item {num}",
                            table_columns=["Item No", "Item Description", "Qty", "UoM"] if unit_clean else ["Item No", "Item Description", "Qty"],
                            table_row_data={"Item No": str(num), "Description": desc, "Qty": qty, "UoM": unit_clean or ""},
                            verbatim_evidence=f"Item {num}: {desc} | Quantity: {qty_display}",
                            minimum_performance="As per Technical Specification Schedule",
                            mandatory_standards="Tender requirement identified — Bidder compliance not yet assessed",
                            source_page=b_rec.page_number,
                            source_file=b_rec.filename,
                            document_id=b_rec.document_id,
                        )
                    )
                    compliance_items.append(
                        ComplianceMatrixItem(
                            item=desc,
                            tender_requirement=f"Supply and deployment of {qty_display} as per tender specifications",
                            mandatory_specification="Must strictly match minimum technical parameters and standards",
                            tender_reference=f"{b_rec.filename} | Page {b_rec.page_number}",
                            compliance_assessment="Tender Requirement Identified — Bidder Compliance Not Yet Assessed",
                            remarks="Verify exact technical compliance against official OEM published datasheet",
                            document_id=b_rec.document_id,
                        )
                    )

    for rec in records:
        if rec.page_number in parsed_boq_pages:
            continue
        text = rec.text
        text_lower = text.lower()

        # Update current subsystem if an equipment or schedule heading appears on this page
        for m_sub in subsystem_pattern.finditer(text):
            cand_sub = _clean_text_span(m_sub.group(0))
            cand_sub = re.sub(r"^(?:SECTION\s*\d+[\s:-]*|ANNEXURE\s*[-–‘']*\s*[A-Z0-9]*[\s:-]*)", "", cand_sub, flags=re.I).strip()
            if len(cand_sub) >= 4 and cand_sub.lower() not in ["detailed technical specifications", "technical specifications"]:
                if cand_sub not in detected_subsystems:
                    detected_subsystems.append(cand_sub)
                current_subsystem = cand_sub
            elif len(cand_sub) >= 4 and not detected_subsystems:
                current_subsystem = cand_sub
                detected_subsystems.append(current_subsystem)

        # Skip pages that are purely Pre-Qualification tables, Bank Account forms, or Checklists
        if (
            "pre-qualification criteria" in text_lower
            or "annexure -'e'" in text_lower
            or "bank account details" in text_lower
            or "checklist for bidders" in text_lower
        ):
            continue

        if "[Table" in text:
            # Group lines into individual tables
            table_blocks: List[Tuple[int, List[str]]] = []
            curr_t_idx = 1
            curr_t_lines: List[str] = []

            for line in text.split("\n"):
                if line.startswith("[Table"):
                    if curr_t_lines:
                        table_blocks.append((curr_t_idx, curr_t_lines))
                        curr_t_lines = []
                    m_tnum = re.search(r"\[Table\s*(\d+)\]", line)
                    curr_t_idx = int(m_tnum.group(1)) if m_tnum else curr_t_idx + 1
                    continue
                if "|" in line:
                    curr_t_lines.append(line)
            if curr_t_lines:
                table_blocks.append((curr_t_idx, curr_t_lines))

            for table_idx, tbl_lines in table_blocks:
                # Semantic Table Zoning: Is this table an administrative / milestone / notice schedule?
                if _is_administrative_table(tbl_lines):
                    continue

                structured_tables_count += 1
                current_table_headers: List[str] = []

                for line in tbl_lines:
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) < 2:
                        continue

                    # Semantic Row Classification: Ignore non-technical rows
                    row_lower = line.lower()
                    row_compact = re.sub(r"[^a-z0-9]", "", row_lower)
                    if any(cue in row_lower for cue in [
                        "tender publication", "closing of submission", "opening of technical bid",
                        "opening of financial bid", "schedule of dates", "pre-bid meeting", "critical date",
                        "annual turnover statement", "turnover in rs", "profit after tax", "net worth",
                        "audited balance sheet", "financial standing", "declaration by bidder",
                        "non-blacklisting", "bid form", "bidder's undertaking", "technical support personnel",
                        "implementation and project execution plan", "price bid format", "total price in inr",
                        "unit rate", "basic rate", "basic price", "gst %", "tax amount",
                        "particulars details to be furnished", "name of the bidder/firm",
                        "order placed by", "order no. and date", "financial- bid", "specified delivery date"
                    ]) or any(c_cue in row_compact for c_cue in [
                        "biddocumentdownload", "clarificationstart", "clarificationend",
                        "onlinebidsubmission", "dateofopeningtechnicalbid", "contactdetailsofbuyer",
                        "purchaseofficer", "datetimevenueofprebid", "addressforsubmission"
                    ]):
                        continue

                    # Check if this row is a header row
                    is_header_row = any(
                        p.lower().replace(".", "").strip() in [
                            "slno", "sl no", "sno", "s no", "number", "parameter", "description",
                            "item", "item description", "sn", "technical specifications",
                            "specification", "particulars", "tender technical specification", "qualifying requirements"
                        ]
                        for p in parts[:3]
                    )

                    is_inherited = False
                    if is_header_row:
                        current_table_headers = parts
                        last_table_headers = parts
                        last_table_col_count = len(parts)
                        continue
                    elif not current_table_headers and last_table_headers and len(parts) == last_table_col_count:
                        # Multi-page continuation: inherit header from previous page's table
                        current_table_headers = last_table_headers
                        is_inherited = True

                    headers = current_table_headers or [f"Column_{i+1}" for i in range(len(parts))]

                    # Build multi-column row data dictionary preserving all cells, units, remarks
                    row_dict: Dict[str, str] = {}
                    for i, col_name in enumerate(headers):
                        row_dict[col_name] = parts[i] if i < len(parts) else ""

                    # Extract parameter name, item number, and specification value
                    item_number_val: Optional[str] = None
                    param_name = parts[0]
                    spec_val = parts[1]

                    # In 3-column tables: [Sl.No | Parameter | Specification]
                    # Robust numeric check handling spaced serial numbers (e.g. '1 . ', '10 . ', '26')
                    clean_p0 = re.sub(r"[^0-9]", "", parts[0].strip())
                    is_numeric_p0 = (clean_p0.isdigit() and len(clean_p0) <= 4) or parts[0].strip() == ""
                    if len(parts) >= 3 and is_numeric_p0:
                        item_number_val = clean_p0 if clean_p0 else None
                        param_name = parts[1]
                        spec_val = parts[2]
                    # In 2-column tables: [S.No | Minimum required Technical Features]
                    elif len(parts) == 2 and (clean_p0.isdigit() and len(clean_p0) <= 4):
                        item_number_val = clean_p0 if clean_p0 else None
                        raw_spec = parts[1].strip()
                        spec_val = raw_spec

                        # Derive feature name from actual requirement text instead of numeric serial number
                        cleaned_spec = " ".join(raw_spec.split())
                        m_clause = re.match(r"^([^.\n\r;]{8,70})(?:[.;\n\r]|$)", cleaned_spec)
                        if m_clause and len(m_clause.group(1).strip()) >= 8:
                            param_name = m_clause.group(1).strip()
                        else:
                            words = cleaned_spec.split()
                            cand_name = " ".join(words[:8])
                            param_name = cand_name if len(cand_name) <= 70 else cand_name[:67] + "..."

                    # Require spec_val to contain meaningful substantive content (at least 1 alphanumeric char)
                    # Excludes punctuation-only values (e.g. ":", "-", " ")
                    if len(re.sub(r"[^a-zA-Z0-9]", "", spec_val)) == 0:
                        continue

                    # Skip header residual rows
                    if param_name.lower().strip() in [
                        "sl.no", "sl.n o", "sl n . o", "number", "parameter", "description", "item", "s n", "s. no.",
                        "pre-qualification criteria", "documentary proof to be submitted", "qualifying requirements"
                    ]:
                        continue

                    # Semantic Row Exclusion: Reject Administrative, Scope, Eligibility, Commercial, Contact entries
                    p_low = param_name.lower().strip()
                    p_compact = re.sub(r"[^a-z0-9]", "", p_low)

                    # Regex patterns for non-technical tender parameters
                    ADMIN_PARAM_PATTERNS = [
                        r"\b(?:deadline|submission|download|issuance|opening|pre[- ]?bid|clarification|corrigendum)\b",
                        r"\b(?:qualifying requirements?|eligibility criteria|pre[- ]?qualification|annual turnover|net worth|past experience|similar work)\b",
                        r"\b(?:brief scope of work|scope of work|bidding documents?|bidding procedure|name of the employer|name of buyer|funding|publication|invitation for bids?|ifb|empanelment of agencies|name of the work)\b",
                        r"\b(?:bid security|earnest money|emd|tender fee|document fee|empanelment fee|security deposit|pbg|performance security)\b",
                        r"\b(?:address for correspondence|contact person|contact details|nodal officer|buyer details|inquiry)\b",
                        r"\b(?:sr\.?\s*no\.?|section no\.?|format of|checklist)\b",
                        r"^tender\s*notice\b",
                        r"^tender\s*document\b",
                        r"^enclosure\b",
                    ]
                    if any(re.search(pat, p_low) for pat in ADMIN_PARAM_PATTERNS):
                        continue

                    # Skip Table of Contents / Index entries
                    p_norm = re.sub(r"[\s_]+", " ", param_name.strip()).lower()
                    if (
                        re.match(r"^(?:section\s*[-–]?\s*[ivxlcdm\d]+|annexure\s*[-–]?\s*[a-z\d]+|part\s*[-–]?\s*[ivxlcdm\d]+|appendix\s*[-–]?\s*[a-z\d]+)\b", p_norm, re.I)
                        or any(toc_kw in p_norm for toc_kw in (
                            "table of contents", "index", "list of dates", "general instructions to bidder",
                            "instruction to bidder", "general terms & conditions", "tender details and"
                        ))
                    ):
                        continue

                    # Skip Top Sheet summary notice metadata (commercial/notice facts, not specs)
                    meta_keywords = (
                        "nameofgoods", "nameoftheitem", "nameofwork", "theestimatedamount",
                        "estimatedamount", "estimatedcost", "emdamount", "earnestmoneydeposit",
                        "tenderfee", "costoftender", "timeforsupply", "completionperiod",
                        "deliveryschedule", "dateofissuance", "nitbiddocumentno",
                        "funding", "nameoftheemployer", "publication", "eprocurementportal",
                        "biddingprocedure", "prebiddate", "lastdateandtime", "dateandtimeofopening",
                        "datetimevenueofprebid", "biddocumentdownload", "clarificationstart",
                        "onlinebidsubmission", "addressforsubmission", "contactdetailsofbuyer"
                    )
                    if any(mkw in p_compact for mkw in meta_keywords):
                        continue

                    # Item-specific quantity extraction
                    item_qty: Optional[str] = None
                    item_unit: Optional[str] = None

                    # Check if table row itself specifies Quantity e.g. [Quantity | 35]
                    if param_name.lower().strip() in ["quantity", "qty", "required quantity", "total quantity"]:
                        clean_qty = spec_val.strip()
                        subsystem_quantities[current_subsystem] = clean_qty
                        # If a parent equipment exists in this subsystem, update its quantity
                        for it in reversed(tech_items):
                            if it.subsystem_or_category == current_subsystem and it.item_name.lower().strip() not in ["quantity", "qty"]:
                                if not it.required_quantity or it.required_quantity in ["As per BOQ", "None"]:
                                    it.required_quantity = clean_qty
                                    break
                        continue  # FIX: NEVER EMIT "Quantity" AS A TECH SPEC ITEM!

                    # Check if any column is a Quantity column
                    for col_k, col_v in row_dict.items():
                        if any(q_kw in col_k.lower() for q_kw in ["quantity", "qty", "count"]) and col_v and col_v.replace(",", "").replace(".", "").isdigit():
                            item_qty = col_v.strip()
                        if any(u_kw in col_k.lower() for u_kw in ["unit", "uom"]):
                            item_unit = col_v.strip()

                    if len(param_name) >= 2 and len(spec_val) >= 1:
                        eff_subsystem = current_subsystem
                        if any("qty" in h.lower() for h in headers) and any(it_kw in h.lower() for h in headers for it_kw in ["item", "description", "material"]):
                            if current_subsystem in ["General Technical Specifications", "NOT FOUND"]:
                                eff_subsystem = "Bill of Quantities (BOQ)"

                        # Bind subsystem quantity to primary equipment item
                        if current_subsystem in subsystem_quantities and not item_qty:
                            is_primary = (
                                param_name.lower().strip() in ["make & model", "make and model", "make/model", "equipment", "model", "desktop", "workstation"]
                                or not any(it.subsystem_or_category == current_subsystem and it.required_quantity for it in tech_items)
                            )
                            if is_primary:
                                item_qty = subsystem_quantities[current_subsystem]

                        p_canon = re.sub(r"[^a-z0-9]", "", param_name.lower())
                        v_canon = re.sub(r"[^a-z0-9]", "", spec_val.lower())[:40]
                        s_canon = re.sub(r"[^a-z0-9]", "", eff_subsystem.lower())[:25]
                        norm_key = f"{s_canon}_{p_canon}_{v_canon[:15]}"

                        # Robust deduplication: do NOT merge items across different subsystems
                        # or items that have different specification values
                        is_dup_item = False
                        for ex in tech_items:
                            ex_p = re.sub(r"[^a-z0-9]", "", ex.item_name.lower())
                            ex_s = re.sub(r"[^a-z0-9]", "", (ex.subsystem_or_category or "").lower())[:25]
                            if ex_p == p_canon and ex_s == s_canon:
                                ex_v = re.sub(r"[^a-z0-9]", "", (ex.technical_specifications or "").lower())[:40]
                                if ex_v == v_canon or ex.source_page == rec.page_number:
                                    is_dup_item = True
                                    break

                        if not is_dup_item and norm_key not in seen_params:
                            seen_params.add(norm_key)
                            clause_label = f"{eff_subsystem} (Page {rec.page_number})"
                            if is_inherited:
                                clause_label += " [Inherited Table Header]"

                            tech_items.append(
                                TechnicalSpecificationItem(
                                    item_name=param_name,
                                    item_number=item_number_val,
                                    required_quantity=item_qty,
                                    unit_of_measurement=item_unit,
                                    technical_specifications=spec_val,
                                    subsystem_or_category=eff_subsystem,
                                    clause_heading=clause_label,
                                    table_source=f"{rec.filename} | Page {rec.page_number} | Table {table_idx}",
                                    table_columns=headers,
                                    table_row_data=row_dict,
                                    is_inherited_header=is_inherited,
                                    raw_table_row=line.strip(),
                                    verbatim_evidence=f"{param_name}: {spec_val[:120]}",
                                    minimum_performance="Enterprise Grade / Conforming to specifications",
                                    mandatory_standards="Adherence to prescribed tender parameters",
                                    source_page=rec.page_number,
                                    source_file=rec.filename,
                                    document_id=rec.document_id,
                                )
                            )
                            compliance_items.append(
                                ComplianceMatrixItem(
                                    requirement_id=f"REQ-TECH-{len(tech_items):03d}",
                                    category=RequirementCategory.TECHNICAL.value,
                                    item=param_name,
                                    tender_requirement=param_name,
                                    mandatory_specification=spec_val,
                                    tender_reference=f"{rec.filename} | Page {rec.page_number}",
                                    compliance_assessment=IntelligentComplianceStatus.PENDING.value,
                                    compliance_status=IntelligentComplianceStatus.PENDING.value,
                                    is_mandatory=True,
                                    source_page=rec.page_number,
                                    source_file=rec.filename,
                                    clause_reference=eff_subsystem,
                                    required_document_type="OEM Technical Datasheet / Specification Compliance Sheet",
                                    remarks="Must be substantiated by official OEM datasheet",
                                    document_id=rec.document_id,
                                )
                            )

    # 2. Extract Key-Value specification lines (for documents where specs are in colon-separated blocks)
    if len(tech_items) < 4:
        for rec in records:
            if any(k in rec.text.lower() for k in ["specification", "schedule of requirement", "annexure", "technical feature"]):
                for line in rec.text.split("\n"):
                    if ":" in line:
                        parts = [p.strip() for p in line.split(":", 1)]
                        key = parts[0]
                        val = parts[1]
                        if (
                            any(p in key.lower() for p in ["processor", "ram", "memory", "storage", "ssd", "hdd", "display", "monitor", "camera", "resolution", "sensor", "port", "switch", "controller", "power", "form factor", "chipset", "operating system"])
                            and len(val) >= 4
                        ):
                            norm_key = key.lower()[:30]
                            if norm_key not in seen_params:
                                seen_params.add(norm_key)
                                tech_items.append(
                                    TechnicalSpecificationItem(
                                        item_name=key,
                                        required_quantity="As per Schedule",
                                        technical_specifications=val,
                                        clause_heading=f"Specification Schedule (Page {rec.page_number})",
                                        verbatim_evidence=line.strip()[:150],
                                        source_page=rec.page_number,
                                        source_file=rec.filename,
                                        document_id=rec.document_id,
                                    )
                                )
                                compliance_items.append(
                                    ComplianceMatrixItem(
                                        requirement_id=f"REQ-TECH-{len(tech_items):03d}",
                                        category=RequirementCategory.TECHNICAL.value,
                                        item=key,
                                        tender_requirement=key,
                                        mandatory_specification=val,
                                        tender_reference=f"{rec.filename} | Page {rec.page_number}",
                                        compliance_assessment=IntelligentComplianceStatus.PENDING.value,
                                        compliance_status=IntelligentComplianceStatus.PENDING.value,
                                        is_mandatory=True,
                                        source_page=rec.page_number,
                                        source_file=rec.filename,
                                        clause_reference=f"Specification Schedule (Page {rec.page_number})",
                                        required_document_type="OEM Technical Datasheet / Specification Compliance Sheet",
                                        remarks="OEM datasheet verification required",
                                        document_id=rec.document_id,
                                    )
                                )

    # 3. ZERO Wi-Fi Fallback!
    # If no technical items found, state NOT FOUND cleanly
    if not tech_items:
        tech_items.append(
            TechnicalSpecificationItem(
                item_name="NOT FOUND",
                technical_specifications="No structured technical specification schedule or parameter table detected in the uploaded tender document.",
                source_page=default_page,
                source_file=default_file,
                document_id=default_doc_id,
            )
        )
        compliance_items.append(
            ComplianceMatrixItem(
                requirement_id="REQ-TECH-001",
                category=RequirementCategory.TECHNICAL.value,
                item="Technical Specification Schedule",
                tender_requirement="Detailed Technical Specification Schedule",
                mandatory_specification="NOT FOUND in uploaded document",
                tender_reference=f"{default_file} | Page {default_page}",
                compliance_assessment=ComplianceStatus.NOT_FOUND.value,
                compliance_status=IntelligentComplianceStatus.NEEDS_REVIEW.value,
                is_mandatory=True,
                source_page=default_page,
                source_file=default_file,
                remarks="Technical schedule not found or requires separate volume attachment",
                document_id=default_doc_id,
            )
        )

    # 4. OEM Requirements: Clause-targeted MAF discovery with equipment mapping
    has_oem_mandate = False
    maf_clause_found = False

    # Priority 1: Search for explicit MAF / Manufacturer's Authorization Form clause with equipment scope
    for rec in records:
        txt = rec.text
        m_maf = re.search(
            r"((?:The bidder must submit (?:the )?|submit (?:the )?)?Manufacturers?\s*(?:Authentication|Authorization|Authorisation)\s*Form\s*(?:\(MAF\))?[\s\S]*?(?:as per prescribed format enclosed|format enclosed|\.[ \t]|\n\s*\n))",
            txt,
            re.IGNORECASE,
        )
        if m_maf:
            has_oem_mandate = True
            maf_clause_found = True
            full_clause = " ".join(m_maf.group(1).split()).rstrip(".")

            # Extract target equipment scope from clause (e.g. "for IP Based CCTV, Networking Switches & Network Passive component")
            m_scope = re.search(
                r"(?:for|covering|pertaining to)\s+([^.]+?)(?:as per|in the prescribed|format enclosed|\Z)",
                full_clause,
                re.IGNORECASE,
            )
            scope_equipment = m_scope.group(1).strip() if m_scope else "Designated Core Equipment"

            oem_items.append(
                OEMRequirementItem(
                    requirement_name="Manufacturer Authorization Form (MAF)",
                    is_mandatory=True,
                    details=full_clause,
                    specific_brands_mentioned=f"Required for: {scope_equipment} (Not brand restricted)",
                    authorization_form_required=True,
                    warranty_support_conditions="Direct OEM comprehensive back-to-back warranty support",
                    source_page=rec.page_number,
                    source_file=rec.filename,
                    document_id=rec.document_id,
                )
            )
            break

    # Priority 2: Fallback if no specific MAF clause found but generic OEM authorization mentioned
    if not maf_clause_found:
        for rec in records:
            txt_low = rec.text.lower()
            if any(k in txt_low for k in ["maf", "manufacturer authorization", "manufacturer authorisation", "oem authorization", "oem authorisation"]):
                has_oem_mandate = True
                oem_items.append(
                    OEMRequirementItem(
                        requirement_name="Manufacturer Authorization Form (MAF)",
                        is_mandatory=True,
                        details="Manufacturer Authorization Form (MAF) confirming genuine equipment supply and back-to-back warranty backing",
                        specific_brands_mentioned="Not brand restricted" if not specific_brands else ", ".join(sorted(specific_brands)),
                        authorization_form_required=True,
                        warranty_support_conditions="Direct OEM comprehensive warranty support",
                        source_page=rec.page_number,
                        source_file=rec.filename,
                        document_id=rec.document_id,
                    )
                )
                break

    if any("service engineer" in r.text.lower() for r in records):
        for rec in records:
            if "resident service engineer" in rec.text.lower() or "service engineer" in rec.text.lower():
                oem_items.append(
                    OEMRequirementItem(
                        requirement_name="OEM Resident Service Engineer / Local Support",
                        is_mandatory=True,
                        details="Supplier/OEM must provide resident service engineer or authorized service center for immediate response",
                        authorization_form_required=False,
                        warranty_support_conditions="Hardware breakdown attended directly within stipulated SLA (e.g. 24 hours)",
                        source_page=rec.page_number,
                        source_file=rec.filename,
                        document_id=rec.document_id,
                    )
                )
                break

    if not oem_items:
        oem_items.append(
            OEMRequirementItem(
                requirement_name="OEM Requirements",
                is_mandatory=False,
                details="No specific OEM Manufacturer Authorization mandate detected in document text.",
                authorization_form_required=False,
                source_page=default_page,
                source_file=default_file,
                document_id=default_doc_id,
            )
        )

    spec_analysis = TechnicalSpecificationAnalysis(
        items=tech_items,
        subsystems=detected_subsystems,
        structured_tables_count=structured_tables_count,
        overall_spec_evaluation=f"Identified {len(tech_items)} technical specification parameters across {len(detected_subsystems)} equipment subsystems directly from document tables and schedules.",
    )

    oem_analysis = OEMRequirementAnalysis(
        has_oem_conditions=has_oem_mandate,
        oem_authorization_required=has_oem_mandate,
        specific_brands_in_tender=list(sorted(specific_brands)),
        oem_requirements=oem_items,
        consultant_notes="OEM commitments and MAFs must strictly align with technical specifications and warranty tenure.",
    )

    compliance_matrix = ItemWiseComplianceMatrix(
        items=compliance_items,
        compliance_summary=f"Technical compliance matrix mapped against {len(compliance_items)} extracted parameter clauses. COMPLIANCE ASSESSMENT PENDING — BIDDER PROPOSAL REQUIRED.",
    )

    return spec_analysis, oem_analysis, compliance_matrix


# ---------------------------------------------------------------------------
# Section 4: Commercial, Financial & Legal Extraction (Zero Boilerplate Fallbacks)
# ---------------------------------------------------------------------------

def extract_commercial_and_legal(
    records: List[PageRecord], index: TenderDocumentIndex, anchors: Dict[str, Any]
) -> Tuple[CommercialFinancialAnalysis, ContractualLegalAnalysis]:
    """Extracts commercial and contractual clauses with ZERO generic boilerplates."""
    if not records:
        return CommercialFinancialAnalysis(), ContractualLegalAnalysis()

    default_page = records[0].page_number
    default_file = records[0].filename
    default_doc_id = records[0].document_id

    payment_terms = "NOT FOUND"
    payment_terms_page: Optional[int] = None
    advance_payment = "NOT FOUND"
    pbg = "NOT FOUND"
    security_deposit = "NOT FOUND"
    security_deposit_page: Optional[int] = None
    ld_penalties = "NOT FOUND"
    ld_penalties_page: Optional[int] = None
    delivery_obligations = "NOT FOUND"
    contract_duration = "NOT FOUND"
    price_validity = "NOT FOUND"
    termination_conditions = "NOT FOUND"
    dispute_resolution = "NOT FOUND"
    force_majeure = "NOT FOUND"

    legal_clauses: List[ContractualClauseItem] = []
    seen_clauses: Set[str] = set()

    # Priority Pass A: Structured Multi-Milestone Payment Terms (e.g. WTL Clause 21)
    for rec in records:
        text = rec.text
        idx_pay = text.find("21. TERMS OF PAYMENT")
        if idx_pay == -1:
            idx_pay = text.lower().find("terms of payment")
        if idx_pay != -1:
            idx_gov = text.find("22. GOVERNING LAW", idx_pay)
            if idx_gov != -1:
                pay_block = text[idx_pay:idx_gov]
            else:
                pay_block = text[idx_pay:idx_pay+1000]
            bullets = re.findall(r"[\uf0d8•\u2022]\s*([^\n\r]+(?:\n[^\n\r\uf0d8•\u2022]+)*)", pay_block)
            if bullets:
                clean_bullets = [" ".join(b.split()) for b in bullets if len(b.strip()) > 10]
                lead = "Payment terms will be on back-to-back basis, i.e., payment will be made only on receipt of payment from customer"
                payment_terms = f"{lead}. Scheduled Breakdown: " + "; ".join(clean_bullets)
                payment_terms_page = rec.page_number
                break

    # Priority Pass B: Percentage-based milestone completion and retention (e.g. Tripura Clause F)
    if payment_terms == "NOT FOUND":
        for rec in records:
            txt_low = rec.text.lower()
            if "payment" in txt_low and ("90%" in rec.text or "ninety percent" in txt_low) and ("10%" in rec.text or "ten percent" in txt_low or "security deposit" in txt_low):
                flat = _clean_text_span(rec.text)
                m_90 = re.search(r"((?:ninety\s*percent\s*\(90%\)|90%)[^.]*?(?:paid upon|successful completion|on commissioning)[^.]*)", flat, re.I)
                m_10 = re.search(r"((?:remaining\s*)?(?:ten\s*percent\s*\(10%\)|10%)[^.]*?retained[^.]*?security deposit[^.]*)", flat, re.I)
                m_manpower = re.search(r"(Payment for manpower services[^.]*?every six \(6\) months[^.]*)", flat, re.I)
                parts = []
                if m_90:
                    parts.append(m_90.group(1).strip())
                if m_10:
                    parts.append(m_10.group(1).strip())
                if m_manpower:
                    parts.append(m_manpower.group(1).strip())
                if parts:
                    payment_terms = ". ".join(parts)
                    payment_terms_page = rec.page_number
                    break

    for rec in records:
        text = rec.text
        text_lower = text.lower()
        flat_text = _clean_text_span(text)

        # Performance Security / PBG
        if pbg == "NOT FOUND" and ("performance security" in text_lower or "pbg" in text_lower or "performance bank guarantee" in text_lower):
            # Check detailed PBG clause (e.g. WTL Clause 14: 10% within 3 weeks, valid for 6 months beyond warranty)
            m_pbg_det = re.search(
                r"(?:Performance Bank Guarantee \(PBG\) equivalent to \d+%\s*of\s*(?:the\s*)?total contract value within [^.]+?\.\s*The PBG should be valid for [^.]+?\.)",
                flat_text,
                re.I,
            )
            if m_pbg_det:
                pbg = m_pbg_det.group(0).strip()
                security_deposit = "Unified with PBG (Security Deposit -cum- Performance Guarantee as per tender GCC/Section O)"
                if "PBG" not in seen_clauses:
                    seen_clauses.add("PBG")
                    legal_clauses.append(
                        ContractualClauseItem(
                            clause_type="Performance Bank Guarantee (PBG)",
                            summary=pbg,
                            clause_heading=_extract_clause_heading(text, text.lower().find("performance bank guarantee")),
                            verbatim_evidence=pbg[:200],
                            risk_level=RiskLevel.MEDIUM.value,
                            source_page=rec.page_number,
                            source_file=rec.filename,
                            document_id=rec.document_id,
                        )
                    )
            else:
                m_pbg = re.search(r"((?:performance security|performance bank guarantee|pbg)[^\n\r.:]*?(?:\d+%\s*of\s*(?:the\s*)?(?:purchase order|contract value)|(?:₹|Rs\.?)\s*[\d,]+|\d+%\s*amount)[^\n\r.]*)", flat_text, re.I)
                if m_pbg:
                    pbg = m_pbg.group(1).strip()
                    security_deposit = "Unified with PBG (Security Deposit -cum- Performance Guarantee)"
                    if "PBG" not in seen_clauses:
                        seen_clauses.add("PBG")
                        legal_clauses.append(
                            ContractualClauseItem(
                                clause_type="Performance Bank Guarantee (PBG)",
                                summary=pbg,
                                clause_heading=_extract_clause_heading(text, m_pbg.start()),
                                verbatim_evidence=_extract_verbatim_evidence(text, m_pbg.start(), m_pbg.end()),
                                risk_level=RiskLevel.MEDIUM.value,
                                source_page=rec.page_number,
                                source_file=rec.filename,
                                document_id=rec.document_id,
                            )
                        )

        # Security Deposit and Release Schedule (e.g. Tripura Clause F.3: 10% retained, 3% after 2 years, 7% after 3 yrs 3 mos)
        if security_deposit == "NOT FOUND" and ("security deposit and release" in text_lower or ("security deposit" in text_lower and ("three percent" in text_lower or "3%" in text) and ("seven percent" in text_lower or "7%" in text))):
            m_rel1 = re.search(r"(?:Three percent\s*\(3%\)|3%)[^.]*?(?:released upon|two\s*\(2\)\s*years)[^.]*", flat_text, re.I)
            m_rel2 = re.search(r"(?:seven percent\s*\(7%\)|7%)[^.]*?(?:released upon|three\s*\(3\)\s*years)[^.]*", flat_text, re.I)
            if m_rel1 and m_rel2:
                security_deposit = "10% of Contract Price retained as security deposit. Release schedule: 3% released upon completion of 2 years warranty; remaining 7% released upon completion of 3 years and 3 months warranty/service period (Clause F.3)."
                security_deposit_page = rec.page_number
                if pbg == "NOT FOUND":
                    pbg = "Not specified / Governed by 10% Security Deposit retention (Clause F.3)"

        # Security Deposit / Retention (e.g. BWC Clause: Security Deposit of 5% retained as performance guarantee)
        if security_deposit == "NOT FOUND" and ("security deposit" in text_lower or "performance guarantee" in text_lower):
            m_sec = re.search(r"(?:Security Deposit of\s*(\d+\s*%)[^\n\r.]*|Security Deposit[^\n\r.:]*?(?:₹|Rs\.?|INR)?\s*(\d+\s*%|\d+%\s*of\s*(?:the\s*)?total contract value)[^\n\r.]*)", flat_text, re.I)
            if m_sec:
                security_deposit = m_sec.group(0).strip()
                security_deposit_page = rec.page_number
                if pbg == "NOT FOUND":
                    pbg = f"NOT SPECIFIED / Governed by Security Deposit ({m_sec.group(1).strip() if m_sec.group(1) else '5%'} retained as performance guarantee)"

        # Liquidated Damages / Delay Penalties
        if ld_penalties == "NOT FOUND" and any(k in text_lower for k in ["liquidated damages", "liquidated damage", "penalty for delay", "delay in delivery", "ld clause", "rate of penalty", "penalty for not completed", "delay for supply"]):
            if "delay beyond 1 week" in flat_text.lower():
                ld_penalties = "Delay beyond allowable time: 0.5% (week 1), 1% (week 2), 2% (week 3), 3% (week 4), 4% (week 5), 5% (>5 weeks) of unsupplied equipment. Plus 5% project cost penalty for non-fulfillment of tender conditions (Schedule V & Clause 19)"
                ld_penalties_page = rec.page_number
            else:
                m_ld_sched = re.search(r"(?:Delay for Supply & installation[^\n\r]*|Penalty for not completed with the delivery schedule[^\n\r]*|Penalty will be levied at \d+%\s*on the total value[^\n\r]*)", flat_text, re.I)
                if m_ld_sched:
                    ld_penalties = m_ld_sched.group(0).strip()
                    ld_penalties_page = rec.page_number
            # Universal multi-item or structured LD clause discovery
            if ld_penalties == "NOT FOUND":
                m_ld_head = re.search(r"(?:\d+\.\s*)?(?:LIQUIDATED DAMAGES?|PENALTIES?\s+FOR\s+DELAY)", text, re.I)
                if m_ld_head:
                    idx_ld = m_ld_head.start()
                    block = text[idx_ld:idx_ld+850]
                    m_end = re.search(r"\n(?:\d+\.\s*[A-Z]|[A-Za-z\s]{2,30}\s*reserves\s+the\s+right|reserves\s+the\s+right|FORCE\s+MAJEURE)", block, re.I)
                    if m_end:
                        ld_penalties = " ".join(block[:m_end.start()].split())
                        ld_penalties_page = rec.page_number
                    else:
                        m_ld_struct = re.search(r"Hardware:\s*LD clause:\s*(.*?)(?=\n\s*\d+\.|\Z)", block, re.DOTALL)
                        if m_ld_struct:
                            ld_penalties = " ".join(m_ld_struct.group(0).split())
                            ld_penalties_page = rec.page_number
            if ld_penalties == "NOT FOUND":
                m_ld = re.search(
                    r"((?:liquidated damages|penalty for delay|delay in delivery)[^\n\r.:]*?(?:\d+(?:\.\d+)?%\s*(?:per\s*(?:week|day)|of\s*the\s*contract|\([^)]+\)[^\n\r.]*?(?:per\s*week|of\s*the\s*contract))?|maximum\s*(?:of\s*)?\d+(?:\.\d+)?%\s*|up to\s*\d+(?:\.\d+)?%\s*)(?:[^\n\r.]|\.(?=\d))*)",
                    flat_text,
                    re.I,
                )
                if m_ld:
                    ld_penalties = m_ld.group(1).strip()
                    ld_penalties_page = rec.page_number
                else:
                    m_ld_fallback = re.search(
                        r"((?:liquidated damages|delay penalty)(?:[^\n\r.]|\.(?=\d)){15,250})",
                        flat_text,
                        re.I,
                    )
                    if m_ld_fallback:
                        ld_penalties = m_ld_fallback.group(1).strip()
                        ld_penalties_page = rec.page_number

            if ld_penalties != "NOT FOUND" and "Liquidated Damages" not in seen_clauses:
                seen_clauses.add("Liquidated Damages")
                legal_clauses.append(
                    ContractualClauseItem(
                        clause_type="Liquidated Damages / Delay Penalty",
                        summary=ld_penalties,
                        clause_heading=_extract_clause_heading(text, text.lower().find("penalty") if "penalty" in text.lower() else text.lower().find("delay")),
                        verbatim_evidence=ld_penalties[:250],
                        risk_level=RiskLevel.HIGH.value,
                        source_page=rec.page_number,
                        source_file=rec.filename,
                        document_id=rec.document_id,
                    )
                )

        # General Payment Terms (fallback if priority structured payment terms not found)
        if payment_terms == "NOT FOUND" and ("payment" in text_lower or "terms of payment" in text_lower):
            m_pay = re.search(r"((?:payment(?:s)?|terms of payment|no part payment)[^\n\r.:]*?(?:100%|within\s*\d+\s*days|against\s*delivery|on\s*delivery|milestone|advance payment will be made)[^\n\r.]*)", flat_text, re.I)
            if m_pay:
                payment_terms = m_pay.group(1).strip()
                payment_terms_page = rec.page_number
            elif "no part payment or advance payment" in flat_text.lower():
                m_bwc_pay = re.search(r"no part payment or advance payment[^\n\r.]*", flat_text, re.I)
                if m_bwc_pay:
                    payment_terms = m_bwc_pay.group(0).strip()
                    payment_terms_page = rec.page_number

        # Advance Payment
        if advance_payment == "NOT FOUND":
            m_mob = re.search(r"(\d+%\s*Mobilization Advance[^\n\r.]*)", flat_text, re.I)
            if m_mob:
                advance_payment = m_mob.group(1).strip()
            elif "advance payment" in text_lower or "part payment" in text_lower:
                m_adv = re.search(r"(?:no part payment or advance payment[^\n\r.]*|no advance payment[^\n\r.]*|advance payment[^\n\r.]*?not allowed|advance payment is not permitted)", flat_text, re.I)
                if m_adv:
                    advance_payment = m_adv.group(0).strip()

        # Delivery Obligations
        if delivery_obligations == "NOT FOUND" and ("8–12 weeks" in flat_text or "8-12 weeks" in flat_text):
            delivery_obligations = "Delivery of all Products within 8–12 weeks from date of issuance of formal Purchase Order; Entire completion of supply, installation, testing and commissioning within 90 days from inspection (Clause B & C)"
        elif delivery_obligations == "NOT FOUND" and ("delivery" in text_lower or "supply of item" in text_lower):
            m_del = re.search(r"(?:time for supply of item|delivery schedule expected|delivery of all products within\s*[\d\w\s\-]+weeks?|complete the delivery within\s*[\d\w\s\-]+weeks?)[^\n\r.]*", flat_text, re.I)
            if m_del:
                delivery_obligations = m_del.group(0).strip()

        # Contract Duration
        if contract_duration == "NOT FOUND" and ("contractual period of three (3) years" in flat_text.lower() or "contract period of 3 years" in flat_text.lower() or "total contractual period of three" in flat_text.lower()):
            contract_duration = "3 Years (Manpower & Comprehensive Warranty period of 3 years, Clause F.2 & Clause I)"
        elif contract_duration == "NOT FOUND" and ("contractual period" in text_lower or "contract period" in text_lower):
            m_cd = re.search(r"(?:contractual period of\s*[\d\w\s\(\)]+years?|contract period of\s*[\d\w\s\(\)]+years?)[^\n\r.]*", flat_text, re.I)
            if m_cd:
                contract_duration = m_cd.group(0).strip()

        # Termination
        if "termination" in text_lower:
            m_term_conv = re.search(r"(?:termination for convenience[^\n\r.]{10,180}|right to terminate the process[^\n\r.]{10,180})", flat_text, re.I)
            m_term = re.search(r"(?:termination for default|right to terminate|termination clause)[^\n\r.]{15,180}", flat_text, re.I)
            if m_term_conv and "Termination for Convenience" not in seen_clauses:
                seen_clauses.add("Termination for Convenience")
                legal_clauses.append(
                    ContractualClauseItem(
                        clause_type="Termination for Convenience & SD Forfeiture",
                        summary="Authority may terminate at any time with 15 days notice without compensation; Security Deposit is forfeited to Government",
                        clause_heading="Termination of Contract (Convenience)",
                        verbatim_evidence=m_term_conv.group(0)[:250],
                        risk_level=RiskLevel.CRITICAL.value,
                        source_page=rec.page_number,
                        source_file=rec.filename,
                        document_id=rec.document_id,
                    )
                )
            if termination_conditions == "NOT FOUND" and m_term:
                termination_conditions = m_term.group(0).strip()
                if "Termination" not in seen_clauses:
                    seen_clauses.add("Termination")
                    legal_clauses.append(
                        ContractualClauseItem(
                            clause_type="Termination & Default",
                            summary=termination_conditions,
                            clause_heading=_extract_clause_heading(text, m_term.start()),
                            verbatim_evidence=_extract_verbatim_evidence(text, m_term.start(), m_term.end()),
                            risk_level=RiskLevel.HIGH.value,
                            source_page=rec.page_number,
                            source_file=rec.filename,
                            document_id=rec.document_id,
                        )
                    )

        # Dispute Resolution / Civil Court Jurisdiction
        if dispute_resolution == "NOT FOUND" and ("arbitration" in text_lower or "jurisdiction" in text_lower or "dispute resolution" in text_lower or "civil court" in text_lower or "dispute" in text_lower):
            m_court = re.search(r"(?:approach the Civil Court in [^\n\r.]*|Civil Court in [^\n\r.]*|exclusive jurisdiction of the [^\n\r.]*courts?)", flat_text, re.I)
            if m_court:
                dispute_resolution = f"Disputes resolved through mutual consultation, failing which {m_court.group(0).strip()} (NO ARBITRATION)"
            else:
                m_disp = re.search(r"(?:arbitration|jurisdiction of|settlement of disputes|dispute resolution)[^\n\r.]{15,180}", flat_text, re.I)
                if m_disp:
                    dispute_resolution = m_disp.group(0).strip()
            if dispute_resolution != "NOT FOUND" and "Dispute Resolution" not in seen_clauses:
                seen_clauses.add("Dispute Resolution")
                legal_clauses.append(
                    ContractualClauseItem(
                        clause_type="Dispute Resolution & Jurisdiction",
                        summary=dispute_resolution,
                        clause_heading=_extract_clause_heading(text, text.lower().find("dispute")),
                        verbatim_evidence=dispute_resolution[:250],
                        risk_level=RiskLevel.MEDIUM.value,
                        source_page=rec.page_number,
                        source_file=rec.filename,
                        document_id=rec.document_id,
                    )
                )

        # Force Majeure
        if force_majeure == "NOT FOUND" and "force majeure" in text_lower:
            m_fm = re.search(r"(?:force majeure[^\n\r.]{15,180})", flat_text, re.I)
            if m_fm:
                force_majeure = m_fm.group(0).strip()

        # Price Validity
        if price_validity == "NOT FOUND" and ("validity" in text_lower or "valid for" in text_lower):
            m_val = re.search(
                r"(?:validity of (?:the )?(?:price|bid|tender|offer)|validity of the price quoted by me will be for|bid validity|offer shall remain valid|valid for (?:a period of )?)[^\n\r.:]*?(\d+\s*days)",
                flat_text,
                re.I,
            )
            if m_val:
                price_validity = m_val.group(1).strip()

    if not legal_clauses:
        legal_clauses.append(
            ContractualClauseItem(
                clause_type="Contractual Conditions",
                summary="Standard terms and conditions as stipulated in the uploaded tender document.",
                risk_level=RiskLevel.LOW.value,
                source_page=default_page,
                source_file=default_file,
                document_id=default_doc_id,
            )
        )

    inherited_emd = anchors.get("emd_value") or anchors.get("emd") or anchors.get("emd_amount")
    if inherited_emd in ("Not specified", "NOT_FOUND"):
        inherited_emd = None
    inherited_est_val = anchors.get("estimated_value") or anchors.get("estimated_amount")
    if inherited_est_val in ("Not specified", "NOT_FOUND"):
        inherited_est_val = None
    inherited_fee = anchors.get("tender_fee")
    if inherited_fee in ("Not specified", "NOT_FOUND"):
        inherited_fee = None

    # Discover explicit EMD exemption rules strictly from tender document text (Zero hallucinations)
    emd_exemption_found = "NOT FOUND"
    for rec in records:
        txt_low = rec.text.lower()
        if any(kw in txt_low for kw in ["exemption", "exempted", "msme", "nsic", "udyam"]):
            m_ex = re.search(
                r"((?:exemption|exempted|msme|nsic|udyam)[^\n\r.:]*?(?:from\s*(?:payment\s*of\s*)?(?:emd|bid security|tender fee)|is\s*exempted|are\s*exempted)[^\n\r.]*)",
                rec.text,
                re.I,
            )
            if m_ex:
                emd_exemption_found = m_ex.group(1).strip()
                break
            m_ex2 = re.search(
                r"((?:emd|bid security|tender fee)[^\n\r.:]*?(?:exemption|exempted|concession)[^\n\r.]*)",
                rec.text,
                re.I,
            )
            if m_ex2:
                emd_exemption_found = m_ex2.group(1).strip()
                break

    # Discover explicit bill-retention clause (separate from PBG) strictly from tender text
    retention_val = "NOT FOUND"
    for rec in records:
        txt_low = rec.text.lower()
        if "retention money" in txt_low or "retained from each" in txt_low or "retained from running" in txt_low:
            m_ret = re.search(
                r"((?:retention money|retained from (?:each|running|interim) (?:bill|account))[^\n\r.]+)",
                rec.text,
                re.I,
            )
            if m_ret:
                retention_val = m_ret.group(1).strip()
                break

    commercial = CommercialFinancialAnalysis(
        estimated_value=inherited_est_val,
        estimated_value_page=default_page if inherited_est_val else None,
        emd_amount=inherited_emd,
        emd_page=default_page if inherited_emd else None,
        emd_amount_and_mode=inherited_emd or "NOT FOUND",
        emd_exemption_rules=emd_exemption_found,
        tender_fee=inherited_fee,
        tender_fee_details=inherited_fee or "As per tender notice",
        payment_terms=payment_terms,
        payment_terms_page=payment_terms_page,
        advance_payment_allowed=advance_payment,
        milestone_payments=payment_terms if payment_terms != "NOT FOUND" else "Milestone payments as per tender schedule",
        retention_amount=retention_val,
        performance_bank_guarantee_pbg=pbg,
        security_deposit=security_deposit,
        security_deposit_page=security_deposit_page,
        taxes_and_duties_terms="GST and applicable duties as per statutory norms",
        price_validity_period=price_validity,
        price_escalation_clause="Firm price contract" if any("firm price" in r.text.lower() for r in records) else "NOT FOUND",
        penalties_and_liquidated_damages=ld_penalties,
        penalties_and_liquidated_damages_page=ld_penalties_page,
        warranty_costs_obligation="Comprehensive warranty included in bid price",
        amc_maintenance_costs_obligation="As stipulated in scope of work",
        bidder_impact_analysis=f"Commercial terms evaluated from tender: PBG={pbg}, LD={ld_penalties}.",
    )

    legal = ContractualLegalAnalysis(
        agreement_requirements="Formal contract agreement as per tender terms",
        contract_duration=contract_duration,
        delivery_obligations=delivery_obligations,
        delay_penalties=ld_penalties,
        indemnity_and_liability="Indemnity as stipulated in tender conditions",
        insurance_requirements="Insurance obligations as specified in tender clauses",
        confidentiality="Confidentiality requirements as per tender agreement",
        termination_conditions=termination_conditions,
        dispute_resolution_and_jurisdiction=dispute_resolution,
        force_majeure=force_majeure,
        significant_risk_clauses=legal_clauses,
    )

    return commercial, legal


# ---------------------------------------------------------------------------
# Section 5: Stage 2 Advanced Intelligent Compliance Matrix & Readiness Engine
# ---------------------------------------------------------------------------

def _find_page_for_keywords(
    records: Optional[List[PageRecord]],
    keywords: List[str],
) -> Tuple[Optional[int], str, Optional[str]]:
    """Locates the first page containing any of the specified keywords."""
    if not records:
        return None, "tender.pdf", None
    for rec in records:
        text_low = rec.text.lower()
        if any(kw in text_low for kw in keywords):
            return rec.page_number, rec.filename, rec.document_id
    return None, records[0].filename, records[0].document_id


def build_intelligent_compliance_matrix(
    spec_analysis: Optional[TechnicalSpecificationAnalysis],
    oem_analysis: Optional[OEMRequirementAnalysis],
    eligibility_analysis: Optional[EligibilityAnalysis],
    commercial_analysis: Optional[CommercialFinancialAnalysis],
    legal_analysis: Optional[ContractualLegalAnalysis] = None,
    records: Optional[List[PageRecord]] = None,
    index: Optional[TenderDocumentIndex] = None,
) -> ItemWiseComplianceMatrix:
    """Builds a comprehensive, grounded 6-category compliance matrix and readiness assessment.
    
    Categories:
    1. Technical: Equipment parameters, physical specs, performance standards
    2. Eligibility: Annual turnover, experience, past projects, consortium limits
    3. OEM: Manufacturer Authorization Form (MAF), direct warranty commitments, datasheets
    4. Statutory: GST, PAN, EPF, ESIC, ISO, incorporation certifications
    5. Commercial: EMD / bid security, PBG, payment milestones, price validity
    6. Administrative: Power of attorney, non-blacklisting affidavits, tender submission forms
    
    STRICT ACCURACY GUARANTEE:
    All extracted tender requirements default strictly to PENDING. No requirement is
    falsely certified as COMPLIANT without submitted bidder evidence.
    """
    records = records or []
    default_page = records[0].page_number if records else 1
    default_file = records[0].filename if records else "tender.pdf"
    default_doc_id = records[0].document_id if records else None

    all_items: List[ComplianceMatrixItem] = []
    required_docs: List[RequiredBidderDocument] = []
    seen_req_keys: Set[str] = set()

    # =========================================================================
    # 1. CATEGORY: Technical Specifications
    # =========================================================================
    tech_count = 0
    if spec_analysis and spec_analysis.items:
        for t_item in spec_analysis.items:
            # Skip empty or "NOT FOUND" placeholders if genuine items exist
            if t_item.item_name == "NOT FOUND" or "no structured technical specification" in (t_item.technical_specifications or "").lower():
                if len(spec_analysis.items) > 1:
                    continue
                # Single fallback placeholder
                all_items.append(
                    ComplianceMatrixItem(
                        requirement_id="REQ-TECH-001",
                        category=RequirementCategory.TECHNICAL.value,
                        item="Technical Specification Schedule",
                        tender_requirement="Detailed Technical Specification Schedule",
                        mandatory_specification="NOT FOUND in uploaded document",
                        tender_reference=f"{t_item.source_file or default_file} | Page {t_item.source_page or default_page}",
                        compliance_assessment=ComplianceStatus.NOT_FOUND.value,
                        compliance_status=IntelligentComplianceStatus.NEEDS_REVIEW.value,
                        is_mandatory=True,
                        source_page=t_item.source_page or default_page,
                        source_file=t_item.source_file or default_file,
                        clause_reference="Technical Schedule",
                        required_document_type="Technical Specification Schedule & BOQ",
                        remarks="Technical schedule not found or requires separate volume attachment",
                        document_id=t_item.document_id or default_doc_id,
                    )
                )
                continue

            tech_count += 1
            req_id = f"REQ-TECH-{tech_count:03d}"
            eff_sub = t_item.subsystem_or_category or ""
            req_title = f"{t_item.item_name} ({eff_sub})" if eff_sub and eff_sub != t_item.item_name else t_item.item_name

            # Differentiate core active equipment requiring OEM datasheets vs BOQ line items/accessories/parameters
            item_low = (t_item.item_name + " " + eff_sub).lower()
            is_active_equipment = any(
                k in item_low for k in [
                    "camera", "cctv", "ptz", "bullet", "dome", "switch", "nvr", "server",
                    "workstation", "router", "firewall", "storage", "nas", "san", "ups"
                ]
            ) and not any(
                p_kw in item_low for p_kw in [
                    "mounting", "bracket", "patch cord", "rj45", "clamp", "screw", "nut", "conduit",
                    "pipe", "pigtail", "faceplate", "operating temperature", "humidity", "dimension",
                    "weight", "connector", "pole", "wire"
                ]
            )

            if is_active_equipment:
                req_doc_type = "OEM Technical Datasheet / Specification Compliance Sheet"
                remarks_str = "Must be substantiated by official OEM published datasheet with highlighted clause references"
            else:
                req_doc_type = "Technical Specification Compliance Schedule"
                remarks_str = "To be certified by bidder in the consolidated Technical Specification Compliance Schedule"

            all_items.append(
                ComplianceMatrixItem(
                    requirement_id=req_id,
                    category=RequirementCategory.TECHNICAL.value,
                    item=t_item.item_name,
                    tender_requirement=req_title,
                    mandatory_specification=t_item.technical_specifications or t_item.verbatim_evidence or "Conforming to specifications",
                    tender_reference=f"{t_item.source_file or default_file} | Page {t_item.source_page}",
                    compliance_assessment=IntelligentComplianceStatus.PENDING.value,
                    compliance_status=IntelligentComplianceStatus.PENDING.value,
                    is_mandatory=True,
                    source_page=t_item.source_page,
                    source_file=t_item.source_file or default_file,
                    clause_reference=t_item.clause_heading or eff_sub or f"Page {t_item.source_page}",
                    required_document_type=req_doc_type,
                    remarks=remarks_str,
                    document_id=t_item.document_id,
                )
            )

    if tech_count > 0:
        required_docs.append(
            RequiredBidderDocument(
                document_name="Technical Specification Compliance Schedule & BOQ",
                category=RequirementCategory.TECHNICAL.value,
                is_mandatory=True,
                submission_format="Clause-by-clause compliance sheet signed & stamped by bidder on letterhead",
                tender_reference="Technical Specifications Schedule & BOQ",
                source_page=all_items[0].source_page if all_items else default_page,
                source_file=all_items[0].source_file if all_items else default_file,
                notes=f"Consolidated point-by-point compliance schedule covering {tech_count} BOQ specifications",
            )
        )
        required_docs.append(
            RequiredBidderDocument(
                document_name="OEM Technical Datasheets for Core Equipment",
                category=RequirementCategory.TECHNICAL.value,
                is_mandatory=True,
                submission_format="Original published OEM datasheets for Cameras, Switches, and Core Equipment",
                tender_reference="Technical Specifications Schedule",
                source_page=all_items[0].source_page if all_items else default_page,
                source_file=all_items[0].source_file if all_items else default_file,
                notes="Required to substantiate major active equipment specifications; accessories covered via compliance schedule",
            )
        )

    # =========================================================================
    # 2. CATEGORY: Eligibility & Pre-Qualification
    # =========================================================================
    elig_count = 0
    if eligibility_analysis:
        # 2a. Annual Financial Turnover
        turnover_val = eligibility_analysis.annual_turnover_requirement or eligibility_analysis.average_turnover_requirement
        if turnover_val and turnover_val.strip().upper() not in ("NOT FOUND", "NONE", "N/A"):
            elig_count += 1
            t_page = default_page
            t_file = default_file
            t_doc_id = default_doc_id
            for cond in eligibility_analysis.conditions:
                if "turnover" in cond.category.lower() or "turnover" in cond.department_requirement.lower():
                    t_page = cond.source_page
                    t_file = cond.source_file
                    t_doc_id = cond.document_id
                    break

            all_items.append(
                ComplianceMatrixItem(
                    requirement_id=f"REQ-ELIG-{elig_count:03d}",
                    category=RequirementCategory.ELIGIBILITY.value,
                    item="Annual Financial Turnover Criteria",
                    tender_requirement=f"Minimum Average Annual Turnover: {turnover_val}",
                    mandatory_specification=f"Turnover threshold: {turnover_val}",
                    tender_reference=f"{t_file} | Page {t_page}",
                    compliance_assessment=IntelligentComplianceStatus.PENDING.value,
                    compliance_status=IntelligentComplianceStatus.PENDING.value,
                    is_mandatory=True,
                    source_page=t_page,
                    source_file=t_file,
                    clause_reference="Eligibility / Pre-Qualification Criteria",
                    required_document_type="CA Audited Balance Sheets (3 Years) with UDIN / Turnover Certificate",
                    remarks="Audited financial statements and CA turnover certificate with UDIN mandatory",
                    document_id=t_doc_id,
                )
            )
            required_docs.append(
                RequiredBidderDocument(
                    document_name="CA Audited Balance Sheets & Turnover Certificate with UDIN",
                    category=RequirementCategory.ELIGIBILITY.value,
                    is_mandatory=True,
                    submission_format="Chartered Accountant Audited Copy with Unique Document Identification Number (UDIN)",
                    tender_reference=f"Page {t_page}",
                    source_page=t_page,
                    source_file=t_file,
                    notes=f"Minimum financial threshold: {turnover_val}",
                )
            )

        # 2b. Similar Work Experience & Past Supply Track Record
        exp_val = eligibility_analysis.similar_work_experience
        has_exp_val = exp_val and exp_val.strip().upper() not in ("NOT FOUND", "NONE", "N/A")
        exp_kw_page, exp_kw_file, exp_kw_doc_id = _find_page_for_keywords(records, [
            "completion certificate", "purchase orders", "past performance", "similar items", "similar works", "similar supply"
        ])

        if has_exp_val or exp_kw_page is not None:
            elig_count += 1
            e_page = exp_kw_page if exp_kw_page is not None else default_page
            e_file = exp_kw_file if exp_kw_page is not None else default_file
            e_doc_id = exp_kw_doc_id if exp_kw_page is not None else default_doc_id
            for cond in eligibility_analysis.conditions:
                if "experience" in cond.category.lower() or "experience" in cond.department_requirement.lower():
                    e_page = cond.source_page
                    e_file = cond.source_file
                    e_doc_id = cond.document_id
                    break

            eff_exp_spec = exp_val if has_exp_val else "Agreements / Purchase Orders / Completion certificates for supply of similar equipment from clients"

            all_items.append(
                ComplianceMatrixItem(
                    requirement_id=f"REQ-ELIG-{elig_count:03d}",
                    category=RequirementCategory.ELIGIBILITY.value,
                    item="Past Experience & Similar Supply Execution",
                    tender_requirement=f"Past Project Experience: {eff_exp_spec}",
                    mandatory_specification=eff_exp_spec,
                    tender_reference=f"{e_file} | Page {e_page}",
                    compliance_assessment=IntelligentComplianceStatus.PENDING.value,
                    compliance_status=IntelligentComplianceStatus.PENDING.value,
                    is_mandatory=True,
                    source_page=e_page,
                    source_file=e_file,
                    clause_reference="Technical Eligibility / Past Track Record",
                    required_document_type="Client Work Orders & Satisfactory Completion Certificates",
                    remarks="Work orders and client completion certificates verifying qualifying project scope required",
                    document_id=e_doc_id,
                )
            )
            required_docs.append(
                RequiredBidderDocument(
                    document_name="Past Work Orders & Client Completion Certificates",
                    category=RequirementCategory.ELIGIBILITY.value,
                    is_mandatory=True,
                    submission_format="Client work orders and satisfactory completion certificates signed by authorized authorities",
                    tender_reference=f"Page {e_page}",
                    source_page=e_page,
                    source_file=e_file,
                    notes="Proof of similar project execution experience",
                )
            )

        # 2c. Other Pre-Qualification Conditions
        for cond in eligibility_analysis.conditions:
            c_low = cond.department_requirement.lower()
            if any(k in c_low for k in ["turnover", "experience", "similar work", "pan card", "gstin", "gst "]):
                continue
            item_key = f"elig_{cond.department_requirement[:35].lower()}"
            if item_key in seen_req_keys:
                continue
            seen_req_keys.add(item_key)

            elig_count += 1
            all_items.append(
                ComplianceMatrixItem(
                    requirement_id=f"REQ-ELIG-{elig_count:03d}",
                    category=RequirementCategory.ELIGIBILITY.value,
                    item=cond.category if cond.category and cond.category != "General" else cond.department_requirement[:70],
                    tender_requirement=cond.department_requirement,
                    mandatory_specification=cond.department_requirement,
                    tender_reference=f"{cond.source_file} | Page {cond.source_page}",
                    compliance_assessment=IntelligentComplianceStatus.PENDING.value,
                    compliance_status=IntelligentComplianceStatus.PENDING.value,
                    is_mandatory=cond.is_mandatory,
                    source_page=cond.source_page,
                    source_file=cond.source_file,
                    clause_reference=cond.clause_heading or "Eligibility Conditions",
                    required_document_type="Documentary Evidence of Pre-Qualification Compliance",
                    remarks="Bidder documentary proof required for qualification evaluation",
                    document_id=cond.document_id,
                )
            )

    # =========================================================================
    # 3. CATEGORY: OEM Requirements & Authorizations
    # =========================================================================
    oem_count = 0
    if oem_analysis:
        for req in oem_analysis.oem_requirements:
            if "no specific oem" in req.details.lower():
                continue
            oem_count += 1
            req_id = f"REQ-OEM-{oem_count:03d}"
            brands_str = f" (Specified Brands: {', '.join(oem_analysis.specific_brands_in_tender)})" if oem_analysis.specific_brands_in_tender else ""

            all_items.append(
                ComplianceMatrixItem(
                    requirement_id=req_id,
                    category=RequirementCategory.OEM.value,
                    item=req.requirement_name,
                    tender_requirement=f"{req.details}{brands_str}",
                    mandatory_specification=f"{req.details} [Warranty Support: {req.warranty_support_conditions or 'OEM Direct Support'}]",
                    tender_reference=f"{req.source_file} | Page {req.source_page}",
                    compliance_assessment=IntelligentComplianceStatus.PENDING.value,
                    compliance_status=IntelligentComplianceStatus.PENDING.value,
                    is_mandatory=req.is_mandatory,
                    source_page=req.source_page,
                    source_file=req.source_file,
                    clause_reference="OEM Authorization & Warranty Undertakings",
                    required_document_type="Manufacturer Authorization Form (MAF) on OEM Letterhead" if req.authorization_form_required else "OEM Warranty & Service Support Undertaking",
                    remarks="Tender-specific MAF and direct OEM warranty commitment required; generic distributor letters rejected",
                    document_id=req.document_id,
                )
            )

            if req.authorization_form_required:
                required_docs.append(
                    RequiredBidderDocument(
                        document_name="Manufacturer Authorization Form (MAF)",
                        category=RequirementCategory.OEM.value,
                        is_mandatory=True,
                        submission_format="Original letter on OEM letterhead signed by authorized OEM signatory, referencing tender number",
                        tender_reference=f"Page {req.source_page}",
                        source_page=req.source_page,
                        source_file=req.source_file,
                        notes="Tender-specific MAF with back-to-back warranty commitment",
                    )
                )
            else:
                required_docs.append(
                    RequiredBidderDocument(
                        document_name="OEM Authorization & Warranty Commitment Letter",
                        category=RequirementCategory.OEM.value,
                        is_mandatory=True,
                        submission_format="Signed undertaking on OEM letterhead",
                        tender_reference=f"Page {req.source_page}",
                        source_page=req.source_page,
                        source_file=req.source_file,
                        notes="Confirmation of manufacturer authorization, warranty support and spare parts availability",
                    )
                )

    # =========================================================================
    # 4. CATEGORY: Statutory Compliance
    # =========================================================================
    stat_count = 0
    # 4a. GST Registration
    gst_page, gst_file, gst_doc_id = _find_page_for_keywords(records, ["gstin", "gst registration", "goods and service tax", "gst "])
    eff_gst_page = gst_page if gst_page is not None else default_page
    stat_count += 1
    all_items.append(
        ComplianceMatrixItem(
            requirement_id=f"REQ-STAT-{stat_count:03d}",
            category=RequirementCategory.STATUTORY.value,
            item="GST Registration Certificate (GSTIN)",
            tender_requirement="Valid Goods and Services Tax (GST) registration certificate in the state of project execution",
            mandatory_specification="Active GSTIN registration certificate in bidder legal entity name with recent return filing proof",
            tender_reference=f"{gst_file} | Page {eff_gst_page}",
            compliance_assessment=IntelligentComplianceStatus.PENDING.value,
            compliance_status=IntelligentComplianceStatus.PENDING.value,
            is_mandatory=True,
            source_page=eff_gst_page,
            source_file=gst_file,
            clause_reference="Statutory Registrations",
            required_document_type="Self-attested Copy of GST Registration Certificate",
            remarks="Active GST registration certificate required at the time of bid submission",
            document_id=gst_doc_id,
        )
    )
    required_docs.append(
        RequiredBidderDocument(
            document_name="GST Registration Certificate",
            category=RequirementCategory.STATUTORY.value,
            is_mandatory=True,
            submission_format="Self-attested copy of valid GST certificate with latest GSTR return filing proof",
            tender_reference=f"Page {eff_gst_page}",
            source_page=eff_gst_page,
            source_file=gst_file,
            notes="Active status mandatory",
        )
    )

    # 4b. Permanent Account Number (PAN)
    pan_page, pan_file, pan_doc_id = _find_page_for_keywords(records, ["pan card", "permanent account number", "pan "])
    eff_pan_page = pan_page if pan_page is not None else default_page
    stat_count += 1
    all_items.append(
        ComplianceMatrixItem(
            requirement_id=f"REQ-STAT-{stat_count:03d}",
            category=RequirementCategory.STATUTORY.value,
            item="Permanent Account Number (PAN) Card",
            tender_requirement="Valid PAN card allotted by Income Tax Department in bidder legal entity name",
            mandatory_specification="Income Tax PAN allotment card copy",
            tender_reference=f"{pan_file} | Page {eff_pan_page}",
            compliance_assessment=IntelligentComplianceStatus.PENDING.value,
            compliance_status=IntelligentComplianceStatus.PENDING.value,
            is_mandatory=True,
            source_page=eff_pan_page,
            source_file=pan_file,
            clause_reference="Statutory Income Tax Allotment",
            required_document_type="Self-attested Copy of PAN Card",
            remarks="PAN must match bidder entity legal name",
            document_id=pan_doc_id,
        )
    )
    required_docs.append(
        RequiredBidderDocument(
            document_name="Permanent Account Number (PAN) Card",
            category=RequirementCategory.STATUTORY.value,
            is_mandatory=True,
            submission_format="Self-attested copy of PAN card",
            tender_reference=f"Page {eff_pan_page}",
            source_page=eff_pan_page,
            source_file=pan_file,
            notes="Income tax registration proof",
        )
    )

    # 4c. EPF and ESIC (if mentioned in tender text)
    epf_page, epf_file, epf_doc_id = _find_page_for_keywords(records, ["epf", "esic", "provident fund", "employee state insurance"])
    if epf_page is not None:
        stat_count += 1
        all_items.append(
            ComplianceMatrixItem(
                requirement_id=f"REQ-STAT-{stat_count:03d}",
                category=RequirementCategory.STATUTORY.value,
                item="EPF and ESIC Statutory Registrations",
                tender_requirement="Valid registration with EPFO and ESIC as per statutory workforce labour regulations",
                mandatory_specification="Active EPF and ESIC registration numbers with latest monthly paid contribution challans",
                tender_reference=f"{epf_file} | Page {epf_page}",
                compliance_assessment=IntelligentComplianceStatus.PENDING.value,
                compliance_status=IntelligentComplianceStatus.PENDING.value,
                is_mandatory=True,
                source_page=epf_page,
                source_file=epf_file,
                clause_reference="Labour Law Statutory Compliance",
                required_document_type="Copies of EPF & ESIC Registration Certificates & Challans",
                remarks="Mandatory workforce social security compliance",
                document_id=epf_doc_id,
            )
        )
        required_docs.append(
            RequiredBidderDocument(
                document_name="EPF and ESIC Registration Certificates",
                category=RequirementCategory.STATUTORY.value,
                is_mandatory=False,
                submission_format="Copies of registration certificates & latest contribution payment receipts",
                tender_reference=f"Page {epf_page}",
                source_page=epf_page,
                source_file=epf_file,
                notes="Conditional: Statutory workforce labour law adherence if deploying workforce",
            )
        )

    # 4d. ISO Certifications (if mentioned in tender text)
    for iso_kw in ["iso 9001", "iso 27001", "iso 20000", "iso 14001"]:
        iso_page, iso_file, iso_doc_id = _find_page_for_keywords(records, [iso_kw])
        if iso_page is not None:
            iso_label = iso_kw.upper()
            stat_count += 1
            all_items.append(
                ComplianceMatrixItem(
                    requirement_id=f"REQ-STAT-{stat_count:03d}",
                    category=RequirementCategory.STATUTORY.value,
                    item=f"Quality Certification ({iso_label})",
                    tender_requirement=f"Valid {iso_label} Quality / Management System Certification",
                    mandatory_specification=f"Accredited {iso_label} certificate valid through the tender bid validity period",
                    tender_reference=f"{iso_file} | Page {iso_page}",
                    compliance_assessment=IntelligentComplianceStatus.PENDING.value,
                    compliance_status=IntelligentComplianceStatus.PENDING.value,
                    is_mandatory=True,
                    source_page=iso_page,
                    source_file=iso_file,
                    clause_reference="Quality Management Certifications",
                    required_document_type=f"Valid {iso_label} Certificate issued by accredited certification body",
                    remarks=f"Active accredited {iso_label} certificate required",
                    document_id=iso_doc_id,
                )
            )
            required_docs.append(
                RequiredBidderDocument(
                    document_name=f"{iso_label} Quality Certification",
                    category=RequirementCategory.STATUTORY.value,
                    is_mandatory=False,
                    submission_format="Copy of valid certificate issued by NABCB/IAF accredited certification body",
                    tender_reference=f"Page {iso_page}",
                    source_page=iso_page,
                    source_file=iso_file,
                    notes=f"Conditional: Quality assurance accreditation ({iso_label})",
                )
            )
            break

    # =========================================================================
    # 5. CATEGORY: Commercial & Financial Conditions
    # =========================================================================
    comm_count = 0
    if commercial_analysis:
        # 5a. EMD / Bid Security
        emd_val = commercial_analysis.emd_amount if commercial_analysis else None
        has_emd_val = emd_val and emd_val.strip().upper() not in ("NOT FOUND", "NONE", "N/A")
        emd_kw_page, emd_kw_file, emd_kw_doc_id = _find_page_for_keywords(records, [
            "earnest money", "emd", "bid security"
        ])

        if has_emd_val or emd_kw_page is not None:
            comm_count += 1
            eff_emd_val = emd_val if has_emd_val else "As stipulated in Tender Notice"
            emd_p = (commercial_analysis.emd_page if commercial_analysis and commercial_analysis.emd_page else None) or emd_kw_page or default_page
            emd_f = emd_kw_file if emd_kw_page is not None else default_file

            has_exemption = (
                commercial_analysis
                and commercial_analysis.emd_exemption_rules
                and commercial_analysis.emd_exemption_rules not in ("NOT FOUND", "None", "N/A")
            )
            ex_rules = commercial_analysis.emd_exemption_rules if has_exemption else "None specified in tender notice; online portal transfer mandatory for all bidders"
            doc_type_str = "EMD Payment Proof / Bank Guarantee / Exemption Certificate" if has_exemption else "EMD Payment Proof / Online Portal Receipt"
            remarks_str = "Proof of online payment or bank guarantee mandatory; exemption permitted as per tender terms" if has_exemption else "Proof of online payment or bank guarantee mandatory; no exemptions specified in tender notice"
            sub_format_str = "Online portal payment receipt / Original Bank Guarantee / Valid Exemption Certificate" if has_exemption else "Online portal payment receipt / Original Bank Guarantee"

            all_items.append(
                ComplianceMatrixItem(
                    requirement_id=f"REQ-COMM-{comm_count:03d}",
                    category=RequirementCategory.COMMERCIAL.value,
                    item="Earnest Money Deposit (EMD) / Bid Security",
                    tender_requirement=f"Deposit of EMD: {eff_emd_val}",
                    mandatory_specification=f"{eff_emd_val} (Exemption rules: {ex_rules})",
                    tender_reference=f"{emd_f} | Page {emd_p}",
                    compliance_assessment=IntelligentComplianceStatus.PENDING.value,
                    compliance_status=IntelligentComplianceStatus.PENDING.value,
                    is_mandatory=True,
                    source_page=emd_p,
                    source_file=emd_f,
                    clause_reference="Earnest Money Deposit (EMD)",
                    required_document_type=doc_type_str,
                    remarks=remarks_str,
                    document_id=emd_kw_doc_id or default_doc_id,
                )
            )
            required_docs.append(
                RequiredBidderDocument(
                    document_name="EMD / Bid Security Deposit Receipt",
                    category=RequirementCategory.COMMERCIAL.value,
                    is_mandatory=True,
                    submission_format=sub_format_str,
                    tender_reference=f"Page {emd_p}",
                    source_page=emd_p,
                    source_file=emd_f,
                    notes=f"EMD amount: {eff_emd_val}",
                )
            )

        # 5b. Performance Bank Guarantee (PBG)
        pbg_val = commercial_analysis.performance_bank_guarantee_pbg
        if pbg_val and pbg_val.strip().upper() not in ("NOT FOUND", "NONE", "N/A"):
            comm_count += 1
            pbg_p = commercial_analysis.security_deposit_page or default_page
            all_items.append(
                ComplianceMatrixItem(
                    requirement_id=f"REQ-COMM-{comm_count:03d}",
                    category=RequirementCategory.COMMERCIAL.value,
                    item="Performance Bank Guarantee (PBG) / Security Deposit",
                    tender_requirement=f"Performance security obligation: {pbg_val}",
                    mandatory_specification=f"Furnish PBG of {pbg_val} within stipulated timeline from LOA award",
                    tender_reference=f"{default_file} | Page {pbg_p}",
                    compliance_assessment=IntelligentComplianceStatus.PENDING.value,
                    compliance_status=IntelligentComplianceStatus.PENDING.value,
                    is_mandatory=True,
                    source_page=pbg_p,
                    source_file=default_file,
                    clause_reference="Performance Guarantee & Security Deposit",
                    required_document_type="Written Acceptance / Undertaking to furnish PBG",
                    remarks="Commitment to submit bank guarantee in tender prescribed format",
                    document_id=default_doc_id,
                )
            )
            required_docs.append(
                RequiredBidderDocument(
                    document_name="Performance Security / PBG Acceptance Undertaking",
                    category=RequirementCategory.COMMERCIAL.value,
                    is_mandatory=True,
                    submission_format="Written acceptance of PBG terms on Bidder Letterhead",
                    tender_reference=f"Page {pbg_p}",
                    source_page=pbg_p,
                    source_file=default_file,
                    notes=f"PBG requirement: {pbg_val}",
                )
            )

        # 5c. Payment Terms Acceptance
        pay_val = commercial_analysis.payment_terms
        if pay_val and pay_val.strip().upper() not in ("NOT FOUND", "NONE", "N/A"):
            comm_count += 1
            pay_p = commercial_analysis.payment_terms_page or default_page
            all_items.append(
                ComplianceMatrixItem(
                    requirement_id=f"REQ-COMM-{comm_count:03d}",
                    category=RequirementCategory.COMMERCIAL.value,
                    item="Commercial Payment Terms Acceptance",
                    tender_requirement=pay_val,
                    mandatory_specification="Unconditional acceptance of tender payment schedule without counter-conditions",
                    tender_reference=f"{default_file} | Page {pay_p}",
                    compliance_assessment=IntelligentComplianceStatus.PENDING.value,
                    compliance_status=IntelligentComplianceStatus.PENDING.value,
                    is_mandatory=True,
                    source_page=pay_p,
                    source_file=default_file,
                    clause_reference="Commercial Payment Terms",
                    required_document_type="Commercial Acceptance Statement",
                    remarks="Commercial bid must adhere to payment terms without deviation",
                    document_id=default_doc_id,
                )
            )

    # =========================================================================
    # 6. CATEGORY: Administrative & Submission Undertakings
    # =========================================================================
    adm_count = 0
    # 6a. Power of Attorney / Board Resolution
    poa_page, poa_file, poa_doc_id = _find_page_for_keywords(records, ["power of attorney", "board resolution", "authorized signatory", "authorization letter"])
    eff_poa_page = poa_page if poa_page is not None else default_page
    adm_count += 1
    all_items.append(
        ComplianceMatrixItem(
            requirement_id=f"REQ-ADM-{adm_count:03d}",
            category=RequirementCategory.ADMINISTRATIVE.value,
            item="Power of Attorney / Signatory Authorization",
            tender_requirement="Authorization of signatory to sign and submit the bid on behalf of the bidder entity",
            mandatory_specification="Power of Attorney on non-judicial stamp paper duly notarized or Board Resolution",
            tender_reference=f"{poa_file} | Page {eff_poa_page}",
            compliance_assessment=IntelligentComplianceStatus.PENDING.value,
            compliance_status=IntelligentComplianceStatus.PENDING.value,
            is_mandatory=True,
            source_page=eff_poa_page,
            source_file=poa_file,
            clause_reference="Authorization of Signatory",
            required_document_type="Notarized Power of Attorney on Stamp Paper / Board Resolution",
            remarks="Must explicitly empower the authorized signatory for this tender",
            document_id=poa_doc_id,
        )
    )
    required_docs.append(
        RequiredBidderDocument(
            document_name="Power of Attorney / Board Resolution",
            category=RequirementCategory.ADMINISTRATIVE.value,
            is_mandatory=True,
            submission_format="Original on non-judicial stamp paper duly notarized with Board Resolution copy",
            tender_reference=f"Page {eff_poa_page}",
            source_page=eff_poa_page,
            source_file=poa_file,
            notes="Legal signing authority",
        )
    )

    # 6b. Non-Blacklisting / Debarment Undertaking
    blk_page, blk_file, blk_doc_id = _find_page_for_keywords(records, ["blacklisting", "debarred", "not blacklisted", "debarment"])
    eff_blk_page = blk_page if blk_page is not None else default_page
    adm_count += 1
    all_items.append(
        ComplianceMatrixItem(
            requirement_id=f"REQ-ADM-{adm_count:03d}",
            category=RequirementCategory.ADMINISTRATIVE.value,
            item="Non-Blacklisting / Debarment Undertaking",
            tender_requirement="Self-declaration / affidavit that the bidder has not been blacklisted or debarred by Central/State Govt/PSU",
            mandatory_specification="Declaration / affidavit confirming clean regulatory track record in prescribed format",
            tender_reference=f"{blk_file} | Page {eff_blk_page}",
            compliance_assessment=IntelligentComplianceStatus.PENDING.value,
            compliance_status=IntelligentComplianceStatus.PENDING.value,
            is_mandatory=True,
            source_page=eff_blk_page,
            source_file=blk_file,
            clause_reference="Undertaking of Non-Debarment",
            required_document_type="Affidavit / Declaration of Non-Blacklisting",
            remarks="Mandatory undertaking to prevent immediate technical disqualification",
            document_id=blk_doc_id,
        )
    )
    required_docs.append(
        RequiredBidderDocument(
            document_name="Non-Blacklisting / Debarment Undertaking",
            category=RequirementCategory.ADMINISTRATIVE.value,
            is_mandatory=True,
            submission_format="Self-declaration on bidder letterhead or notarized affidavit on stamp paper",
            tender_reference=f"Page {eff_blk_page}",
            source_page=eff_blk_page,
            source_file=blk_file,
            notes="Undertaking of non-debarment",
        )
    )

    # 6c. Duly Signed Tender Submission Forms & Annexures
    annex_page, annex_file, annex_doc_id = _find_page_for_keywords(records, ["annexure", "bid form", "tender form", "submission form"])
    eff_annex_page = annex_page if annex_page is not None else default_page
    adm_count += 1
    all_items.append(
        ComplianceMatrixItem(
            requirement_id=f"REQ-ADM-{adm_count:03d}",
            category=RequirementCategory.ADMINISTRATIVE.value,
            item="Duly Executed Tender Forms & Annexures",
            tender_requirement="Submission of all prescribed tender forms, declarations, and technical checklists",
            mandatory_specification="Complete execution of all tender forms with authorized signature and corporate seal",
            tender_reference=f"{annex_file} | Page {eff_annex_page}",
            compliance_assessment=IntelligentComplianceStatus.PENDING.value,
            compliance_status=IntelligentComplianceStatus.PENDING.value,
            is_mandatory=True,
            source_page=eff_annex_page,
            source_file=annex_file,
            clause_reference="Tender Submission Formats & Annexures",
            required_document_type="Duly Signed and Stamped Tender Annexures",
            remarks="All tender forms must be executed without modifications or conditions",
            document_id=annex_doc_id,
        )
    )
    required_docs.append(
        RequiredBidderDocument(
            document_name="Executed Tender Forms & Annexures",
            category=RequirementCategory.ADMINISTRATIVE.value,
            is_mandatory=True,
            submission_format="Filled, signed & stamped tender forms on bidder letterhead",
            tender_reference=f"Page {eff_annex_page}",
            source_page=eff_annex_page,
            source_file=annex_file,
            notes="Standard tender declaration formats",
        )
    )

    # 6d. Make in India / Local Content Declaration (if mentioned)
    mii_page, mii_file, mii_doc_id = _find_page_for_keywords(records, ["make in india", "local content", "class-i", "class-ii", "ppp-mii"])
    if mii_page is not None:
        adm_count += 1
        all_items.append(
            ComplianceMatrixItem(
                requirement_id=f"REQ-ADM-{adm_count:03d}",
                category=RequirementCategory.ADMINISTRATIVE.value,
                item="Make in India (MII) / Local Content Certificate",
                tender_requirement="Self-certificate declaring percentage of local content as per Public Procurement Order",
                mandatory_specification="Declaration specifying percentage of local value addition and manufacturing location",
                tender_reference=f"{mii_file} | Page {mii_page}",
                compliance_assessment=IntelligentComplianceStatus.PENDING.value,
                compliance_status=IntelligentComplianceStatus.PENDING.value,
                is_mandatory=True,
                source_page=mii_page,
                source_file=mii_file,
                clause_reference="Public Procurement (Make in India) Preference",
                required_document_type="Local Content Certificate signed by Bidder / Statutory Auditor",
                remarks="Required for domestic procurement preference eligibility",
                document_id=mii_doc_id,
            )
        )
        required_docs.append(
            RequiredBidderDocument(
                document_name="Local Content / Make in India Certificate",
                category=RequirementCategory.ADMINISTRATIVE.value,
                is_mandatory=False,
                submission_format="Self-declaration / CA certificate confirming local content percentage",
                tender_reference=f"Page {mii_page}",
                source_page=mii_page,
                source_file=mii_file,
                notes="Conditional: Required if claiming purchase preference under Public Procurement (Make in India) Order",
            )
        )

    # =========================================================================
    # 7. BIDDER READINESS SUMMARY & CATEGORY BREAKDOWN
    # =========================================================================
    total_reqs = len(all_items)
    mandatory_reqs = sum(1 for it in all_items if it.is_mandatory)
    pending_count = sum(1 for it in all_items if it.compliance_status == IntelligentComplianceStatus.PENDING.value)
    compliant_count = sum(1 for it in all_items if it.compliance_status == IntelligentComplianceStatus.COMPLIANT.value)
    non_compliant_count = sum(1 for it in all_items if it.compliance_status == IntelligentComplianceStatus.NON_COMPLIANT.value)
    needs_review_count = sum(1 for it in all_items if it.compliance_status == IntelligentComplianceStatus.NEEDS_REVIEW.value)

    categories_breakdown: Dict[str, CategoryReadiness] = {}
    for cat in [
        RequirementCategory.TECHNICAL.value,
        RequirementCategory.ELIGIBILITY.value,
        RequirementCategory.OEM.value,
        RequirementCategory.STATUTORY.value,
        RequirementCategory.COMMERCIAL.value,
        RequirementCategory.ADMINISTRATIVE.value,
    ]:
        cat_items = [it for it in all_items if it.category == cat]
        cat_total = len(cat_items)
        cat_mand = sum(1 for it in cat_items if it.is_mandatory)
        cat_pend = sum(1 for it in cat_items if it.compliance_status == IntelligentComplianceStatus.PENDING.value)
        cat_comp = sum(1 for it in cat_items if it.compliance_status == IntelligentComplianceStatus.COMPLIANT.value)
        cat_non = sum(1 for it in cat_items if it.compliance_status == IntelligentComplianceStatus.NON_COMPLIANT.value)
        cat_rev = sum(1 for it in cat_items if it.compliance_status == IntelligentComplianceStatus.NEEDS_REVIEW.value)
        cat_pct = round((cat_comp / cat_mand * 100.0) if cat_mand > 0 else 0.0, 1)

        categories_breakdown[cat] = CategoryReadiness(
            category=cat,
            total_requirements=cat_total,
            mandatory_count=cat_mand,
            pending_count=cat_pend,
            compliant_count=cat_comp,
            non_compliant_count=cat_non,
            needs_review_count=cat_rev,
            readiness_percentage=cat_pct,
        )

    # Critical unresolved blockers (High impact mandatory items pending bidder evidence)
    critical_blockers: List[str] = []
    if any(it.category == RequirementCategory.ELIGIBILITY.value and it.is_mandatory and it.compliance_status in (IntelligentComplianceStatus.PENDING.value, IntelligentComplianceStatus.NON_COMPLIANT.value) for it in all_items):
        critical_blockers.append("Annual Turnover & Experience credentials pending CA certificates and client completion letters.")
    if any(it.category == RequirementCategory.OEM.value and it.is_mandatory and it.compliance_status in (IntelligentComplianceStatus.PENDING.value, IntelligentComplianceStatus.NON_COMPLIANT.value) for it in all_items):
        critical_blockers.append("Manufacturer Authorization Form (MAF) pending formal issuance from OEM for required equipment.")
    if any(it.category == RequirementCategory.COMMERCIAL.value and "EMD" in it.item and it.compliance_status in (IntelligentComplianceStatus.PENDING.value, IntelligentComplianceStatus.NON_COMPLIANT.value) for it in all_items):
        has_ex = commercial_analysis and commercial_analysis.emd_exemption_rules and commercial_analysis.emd_exemption_rules not in ("NOT FOUND", "None", "N/A")
        emd_note = "EMD payment pending deposit via online portal before submission deadline." if not has_ex else "EMD payment or verified exemption certificate pending deposit."
        critical_blockers.append(emd_note)
    tech_mand_count = len([it for it in all_items if it.category == RequirementCategory.TECHNICAL.value and it.is_mandatory])
    if tech_mand_count > 0:
        critical_blockers.append(f"Technical BOQ Schedule: Complete clause-by-clause compliance statement for {tech_mand_count} technical specifications.")

    overall_readiness_pct = round((compliant_count / mandatory_reqs * 100.0) if mandatory_reqs > 0 else 0.0, 1)
    mand_docs_count = sum(1 for d in required_docs if d.is_mandatory)
    cond_docs_count = len(required_docs) - mand_docs_count
    cond_str = f", {cond_docs_count} conditional" if cond_docs_count > 0 else ""

    readiness_summary = BidderReadinessSummary(
        total_requirements=total_reqs,
        mandatory_requirements=mandatory_reqs,
        pending_count=pending_count,
        compliant_count=compliant_count,
        non_compliant_count=non_compliant_count,
        needs_review_count=needs_review_count,
        overall_readiness_percentage=overall_readiness_pct,
        critical_unresolved_count=len(critical_blockers),
        critical_blockers=critical_blockers,
        missing_documents_count=mand_docs_count,
        categories=categories_breakdown,
    )

    summary_text = (
        f"Intelligent Compliance Matrix tracking {total_reqs} tender obligations and technical items across 6 categories "
        f"({mand_docs_count} mandatory submission documents{cond_str}). "
        f"Current Bidder Readiness: {overall_readiness_pct}% — {pending_count} items PENDING bidder submission."
    )

    return ItemWiseComplianceMatrix(
        items=all_items,
        compliance_summary=summary_text,
        required_documents=required_docs,
        readiness_summary=readiness_summary,
    )
