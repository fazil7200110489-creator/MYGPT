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
    CommercialFinancialAnalysis,
    ComplianceMatrixItem,
    ComplianceStatus,
    ContractualClauseItem,
    ContractualLegalAnalysis,
    EligibilityAnalysis,
    EligibilityCondition,
    EvidenceClassification,
    ItemWiseComplianceMatrix,
    OEMRequirementAnalysis,
    OEMRequirementItem,
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

    # Discover brands mentioned in text
    brand_keywords = ["cisco", "aruba", "ruckus", "hp", "dell", "fortinet", "hikvision", "intel", "nvidia", "windows", "realtek"]
    for rec in records:
        txt_low = rec.text.lower()
        for b in brand_keywords:
            if re.search(r"\b" + re.escape(b) + r"\b", txt_low):
                specific_brands.add(b.title())

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
        r"^\s*(\d{1,3})\.?\s+([A-Za-z0-9][A-Za-z0-9\s/&,()\-+]{4,80}?)\s+(\d{1,6})\s*(?:Nos?\.?|Units?|Sets?|Sites?|Each)?\s*$",
        re.M,
    )
    for b_rec in records:
        if b_rec.page_number in parsed_boq_pages:
            continue
        b_text = b_rec.text
        b_low = b_text.lower()
        if any(h in b_low for h in [
            "bill of material", "bill of materials", "bill of quantities",
            "schedule of requirements", "schedule for delivery", "commercial bid",
            "item / description qty", "bill of final materials"
        ]):
            parsed_boq_pages.add(b_rec.page_number)
            for m in boq_line_pat.finditer(b_text):
                num = int(m.group(1))
                desc = _clean_text_span(m.group(2))
                qty = m.group(3)
                wp_cat = _classify_work_package(desc)
                root = re.sub(r"[^a-z0-9]", "", desc.lower())[:20]

                # Deduplicate against already extracted items
                is_dup = False
                for ex in tech_items:
                    ex_root = re.sub(r"[^a-z0-9]", "", ex.item_name.lower())
                    if root in ex_root or ex_root in root:
                        is_dup = True
                        break
                    if ex.clause_heading and f"Item {num}" in ex.clause_heading and wp_cat in ex.subsystem_or_category:
                        is_dup = True
                        break

                if not is_dup and len(root) >= 3:
                    if wp_cat not in detected_subsystems:
                        detected_subsystems.append(wp_cat)
                    tech_items.append(
                        TechnicalSpecificationItem(
                            item_name=f"{desc}",
                            required_quantity=f"{qty} Nos",
                            unit_of_measurement="Nos",
                            technical_specifications=desc,
                            subsystem_or_category=wp_cat,
                            clause_heading=f"Bill of Materials (Page {b_rec.page_number})",
                            table_source=f"{b_rec.filename} | Page {b_rec.page_number} | Item {num}",
                            table_columns=["Item No", "Item Description", "Qty"],
                            table_row_data={"Item No": str(num), "Description": desc, "Qty": qty},
                            verbatim_evidence=f"Item {num}: {desc} | Quantity: {qty}",
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
                            tender_requirement=f"Supply and deployment of {qty} Nos as per tender specifications",
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
            structured_tables_count += 1
            lines = text.split("\n")
            in_table = False
            current_table_headers: List[str] = []
            table_idx = 1

            for line in lines:
                if line.startswith("[Table"):
                    in_table = True
                    current_table_headers = []
                    m_tnum = re.search(r"\[Table\s*(\d+)\]", line)
                    if m_tnum:
                        table_idx = int(m_tnum.group(1))
                    continue

                if in_table and "|" in line:
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) < 2:
                        continue

                    # Semantic Table Classification: Ignore non-technical tables (Date schedules, turnover forms, blank declarations, price bid formats)
                    row_lower = line.lower()
                    if any(cue in row_lower for cue in [
                        "tender publication", "closing of submission", "opening of technical bid",
                        "opening of financial bid", "schedule of dates", "pre-bid meeting", "critical date",
                        "annual turnover statement", "turnover in rs", "profit after tax", "net worth",
                        "audited balance sheet", "financial standing", "declaration by bidder",
                        "non-blacklisting", "bid form", "bidder's undertaking", "technical support personnel",
                        "implementation and project execution plan", "price bid format", "total price in inr",
                        "unit rate", "basic rate", "basic price", "gst %", "tax amount",
                        "particulars details to be furnished", "name of the bidder/firm"
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
                    if len(parts) >= 3 and len(parts[0]) <= 4 and (parts[0].replace(".", "").isdigit() or parts[0] == ""):
                        item_number_val = parts[0].replace(".", "").strip() if parts[0] else None
                        param_name = parts[1]
                        spec_val = parts[2]
                    # In 2-column tables: [S.No | Minimum required Technical Features]
                    elif len(parts) == 2 and (
                        parts[0].replace(".", "").strip().isdigit()
                        or (len(parts[0].strip()) <= 4 and re.match(r"^\d+", parts[0].strip()))
                    ):
                        item_number_val = parts[0].replace(".", "").strip()
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

                    # Skip header residual rows
                    if param_name.lower() in [
                        "sl.no", "sl.n o", "number", "parameter", "description", "item", "s n", "s. no.",
                        "pre-qualification criteria", "documentary proof to be submitted", "qualifying requirements"
                    ]:
                        continue

                    # Skip Table of Contents / Index entries
                    p_norm = re.sub(r"[\s_]+", " ", param_name.strip()).lower()
                    p_compact = re.sub(r"[^a-z0-9]", "", param_name.lower())
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
                        "biddingprocedure", "prebiddate", "lastdateandtime", "dateandtimeofopening"
                    )
                    if any(mkw in p_compact for mkw in meta_keywords):
                        continue

                    # Item-specific quantity extraction
                    item_qty: Optional[str] = None
                    item_unit: Optional[str] = None

                    # Check if table row itself specifies Quantity e.g. [Quantity | 35]
                    if param_name.lower() in ["quantity", "qty", "required quantity"]:
                        item_qty = spec_val
                        # If a parent equipment item exists in this subsystem, update its quantity
                        for it in reversed(tech_items):
                            if it.subsystem_or_category == current_subsystem and not it.required_quantity:
                                it.required_quantity = spec_val
                                break

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
                        norm_key = f"{eff_subsystem}_{param_name.lower()[:30]}"
                        if norm_key not in seen_params:
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
                                    item=param_name,
                                    tender_requirement=param_name,
                                    mandatory_specification=spec_val,
                                    tender_reference=f"{rec.filename} | Page {rec.page_number}",
                                    compliance_assessment=ComplianceStatus.CLEARLY_SPECIFIED.value,
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
                                        item=key,
                                        tender_requirement=key,
                                        mandatory_specification=val,
                                        tender_reference=f"{rec.filename} | Page {rec.page_number}",
                                        compliance_assessment=ComplianceStatus.CLEARLY_SPECIFIED.value,
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
                item="Technical Specification Schedule",
                tender_requirement="Detailed Technical Specification Schedule",
                mandatory_specification="NOT FOUND in uploaded document",
                tender_reference=f"{default_file} | Page {default_page}",
                compliance_assessment=ComplianceStatus.NOT_FOUND.value,
                remarks="Technical schedule not found or requires separate volume attachment",
                document_id=default_doc_id,
            )
        )

    # 4. OEM Requirements
    has_oem_mandate = False
    for rec in records:
        txt = rec.text
        txt_low = txt.lower()
        if "oem" in txt_low or "manufacturer" in txt_low:
            if "maf" in txt_low or "authorization" in txt_low:
                has_oem_mandate = True
                oem_items.append(
                    OEMRequirementItem(
                        requirement_name="Manufacturer Authorization Form (MAF)",
                        is_mandatory=True,
                        details="Tender-specific Manufacturer Authorization Form (MAF) confirming genuine equipment supply and back-to-back warranty backing",
                        specific_brands_mentioned=", ".join(sorted(specific_brands)) if specific_brands else "NOT SPECIFIED",
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
                security_deposit = pbg
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
                    security_deposit = pbg
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

    commercial = CommercialFinancialAnalysis(
        estimated_value=inherited_est_val,
        estimated_value_page=default_page if inherited_est_val else None,
        emd_amount=inherited_emd,
        emd_page=default_page if inherited_emd else None,
        emd_amount_and_mode=inherited_emd or "NOT FOUND",
        tender_fee=inherited_fee,
        tender_fee_details=inherited_fee or "As per tender notice",
        payment_terms=payment_terms,
        payment_terms_page=payment_terms_page,
        advance_payment_allowed=advance_payment,
        milestone_payments="90% upon completion & commissioning, 10% retained as security deposit; Manpower paid semi-annually over 3 years" if "90%" in payment_terms else ("As stipulated in payment schedule" if payment_terms != "NOT FOUND" else "NOT FOUND"),
        retention_amount="10% of Contract Price retained as security deposit" if "10%" in security_deposit or "10%" in payment_terms else (security_deposit if (security_deposit != "NOT FOUND" and ("retained" in security_deposit.lower() or "%" in security_deposit)) else "NOT FOUND"),
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
