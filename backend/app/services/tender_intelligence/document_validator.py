"""
Strict Document Validator for MYGPT Tender Intelligence.

Enforces robust contextual and word-boundary classification to distinguish authentic
tender/bidding documents from non-tender files (resumes, CVs, invoices, receipts, ordinary letters, code).
Prevents false positives from common substring matches (e.g. 'gem' in 'management', 'nit' in 'unit').
"""

import re
from typing import List, Dict, Any, Tuple, Optional
from loguru import logger


# Strong regex patterns requiring word boundaries (\b)
STRONG_TENDER_PATTERNS = [
    re.compile(r"\bnotice\s+inviting\s+(?:e-)?tender\b", re.I),
    re.compile(r"\bnotice\s+inviting\s+bids?\b", re.I),
    re.compile(r"\b(?:nit|nib|rfp|rfq)\s*(?:no|number|ref)?[.:\s]+[a-z0-9\-_/]+", re.I),
    re.compile(r"\be-tender\s+(?:document|notice|system|portal)\b", re.I),
    re.compile(r"\bearnest\s+money\s+deposit\b", re.I),
    re.compile(r"\b(?:emd|bid\s+security)\s*[:\-]?\s*(?:rs\.?|inr|₹|amount)", re.I),
    re.compile(r"\b(?:closing|last)\s+date\s+(?:and\s+time\s+)?for\s+(?:submission|receipt)\s+of\s+(?:bids?|tenders?)\b", re.I),
    re.compile(r"\btechnical\s+bid\s+(?:document|opening|evaluation)\b", re.I),
    re.compile(r"\bfinancial\s+bid\s+(?:opening|evaluation|schedule|boq)\b", re.I),
    re.compile(r"\bbill\s+of\s+quantities\b", re.I),
    re.compile(r"\beligibility\s+criteria\s+(?:for|of)\s+bidders?\b", re.I),
    re.compile(r"\bpre-bid\s+(?:meeting|conference|clarification)\b", re.I),
    re.compile(r"\b(?:eprocure|etenders)\.gov\.in\b", re.I),
    re.compile(r"\bge?m(?:\.gov\.in|\s+portal|\s+contract|\s+bid)\b", re.I),
    re.compile(r"\bperformance\s+(?:bank\s+guarantee|security)\s*\((?:pbg|pb)\)", re.I),
    re.compile(r"\binstruction\s+to\s+bidders?\b", re.I),
    re.compile(r"\bgeneral\s+conditions\s+of\s+contract\b", re.I),
    re.compile(r"\bspecial\s+conditions\s+of\s+contract\b", re.I),
    re.compile(r"\bcommercial\s+terms\s+and\s+conditions\b", re.I),
    re.compile(r"\btender\s+inviting\s+authority\b", re.I),
]

# Definite non-tender patterns
RESUME_PATTERNS = [
    re.compile(r"\bcurriculum\s+vitae\b", re.I),
    re.compile(r"\b(?:professional\s+summary|career\s+objective|work\s+experience|employment\s+history|education\s+history)\b", re.I),
    re.compile(r"\b(?:bachelor\s+of\s+computer|master\s+of\s+computer|b\.tech|m\.tech|bca|mca|b\.sc|m\.sc)\b", re.I),
    re.compile(r"\b(?:technical\s+skills|soft\s+skills|programming\s+languages):\b", re.I),
]

INVOICE_PATTERNS = [
    re.compile(r"\b(?:tax\s+invoice|commercial\s+invoice|invoice\s+no|bill\s+to|ship\s+to|due\s+date|payment\s+due)\b", re.I),
    re.compile(r"\b(?:subtotal|amount\s+due|balance\s+due|remit\s+to)\b", re.I),
]


def is_authentic_tender_document(
    documents: List[Dict[str, Any]],
    extracted_text: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Validates whether uploaded document(s) constitute an authentic tender or bid document.
    Returns (is_tender, reason).
    """
    if not documents and not extracted_text:
        return False, "No document content provided."

    # Aggregate text sample from documents (first 6 pages or up to 10,000 chars)
    combined_text = extracted_text or ""
    if not combined_text and documents:
        parts: List[str] = []
        for d in documents[:3]:
            # Check pre-classified doc_type
            dtype = str(d.get("document_type") or "").upper()
            if dtype in ("RESUME", "INVOICE", "CODE", "EXPENSE_REPORT", "HR_POLICY"):
                return False, f"Document was classified as {dtype}, not a tender."
            
            raw_text = d.get("extracted_text") or d.get("text") or ""
            if not raw_text and isinstance(d.get("pages"), list):
                raw_text = " ".join(p.get("text", "") for p in d.get("pages", [])[:6])
            parts.append(raw_text[:4000])
        combined_text = " ".join(parts)

    if len(combined_text.strip()) < 40:
        return False, "Document text is too sparse or empty to be a tender."

    # 1. Check for Resume cues
    resume_hits = sum(1 for p in RESUME_PATTERNS if p.search(combined_text))
    if resume_hits >= 2:
        logger.warning(f"[DOCUMENT_VALIDATOR] Rejected non-tender: Matched {resume_hits} resume patterns.")
        return False, "Document matches resume/CV patterns and does not contain tender bidding specifications."

    # 2. Check for Invoice cues (without tender clauses)
    invoice_hits = sum(1 for p in INVOICE_PATTERNS if p.search(combined_text))
    tender_hits = sum(1 for p in STRONG_TENDER_PATTERNS if p.search(combined_text))

    if invoice_hits >= 2 and tender_hits == 0:
        logger.warning(f"[DOCUMENT_VALIDATOR] Rejected non-tender: Matched {invoice_hits} invoice patterns with 0 tender cues.")
        return False, "Document appears to be a commercial invoice or billing receipt, not a tender."

    # 3. Check for Strong Tender Patterns (require at least 2 distinct patterns)
    if tender_hits >= 2:
        return True, f"Verified tender document with {tender_hits} distinct tender indicators."

    # 4. Check filename keywords if 1 strong pattern matched
    if tender_hits == 1 and documents:
        fname = str(documents[0].get("filename") or "").lower()
        if any(k in fname for k in ("tender", "nit", "rfp", "bid", "gem_")):
            return True, "Verified tender document with strong tender pattern and filename confirmation."

    logger.warning(f"[DOCUMENT_VALIDATOR] Rejected non-tender: Only {tender_hits} tender patterns found (minimum 2 required).")
    return False, "Document does not contain sufficient tender, procurement, or bidding indicators."
