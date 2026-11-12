"""Hybrid Deterministic + Gemma 4 Tender Information Extraction Service (Phase 1)."""

from collections import OrderedDict
import hashlib
import json
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger

from backend.app.services.tender.tender_schema import (
    ADDITIONAL_FIELDS,
    ALL_TENDER_FIELD_NAMES,
    BASIC_INFO_FIELDS,
    FIELD_DISPLAY_LABELS,
    FINANCIAL_FIELDS,
    IMPORTANT_DATE_FIELDS,
    TenderExtractionResult,
    TenderFieldEvidence,
    TenderFileCoverage,
)
from backend.app.services.tender.tender_section_retriever import (
    BASIC_KEYWORDS,
    DATE_KEYWORDS,
    FINANCIAL_KEYWORDS,
    SUMMARY_ELIGIBILITY_KEYWORDS,
    PageRecord,
    TenderDocumentIndex,
    collect_page_records,
    compute_bundle_signature,
    format_pages_for_prompt,
    get_or_build_index,
    retrieve_evidence_for_query,
    select_high_signal_pages,
)
from backend.app.services.tender.tender_validator import (
    clean_candidate_value,
    field_section_for,
    resolve_field_candidates,
    validate_date_chronology,
    verify_value_in_records,
)

INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
    "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
    "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Delhi", "New Delhi", "Chandigarh", "Jammu and Kashmir", "Ladakh", "Puducherry",
]

_CITY_TO_STATE = {
    "kolkata": "West Bengal",
    "salt lake": "West Bengal",
    "howrah": "West Bengal",
    "siliguri": "West Bengal",
    "north bengal": "West Bengal",
    "agartala": "Tripura",
    "suryamaninagar": "Tripura",
    "mumbai": "Maharashtra",
    "pune": "Maharashtra",
    "bengaluru": "Karnataka",
    "bangalore": "Karnataka",
    "chennai": "Tamil Nadu",
    "hyderabad": "Telangana",
    "ahmedabad": "Gujarat",
    "gandhinagar": "Gujarat",
    "jaipur": "Rajasthan",
    "lucknow": "Uttar Pradesh",
    "noida": "Uttar Pradesh",
    "patna": "Bihar",
    "bhubaneswar": "Odisha",
    "guwahati": "Assam",
    "new delhi": "Delhi",
}

_DATE_VALUE_RE = re.compile(
    r"(\b\d{1,2}([-/.])\d{1,2}\2\d{2,4}(?:\s*(?:at\.?|upto|on|@)?\s*\d{1,2}(?:[:.]\d{2})?\s*(?:AM|PM|Hrs|Hours|Noon)?)?"
    r"|\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*[\s,]+\d{4}(?:\s*(?:at|upto)?\s*\d{1,2}(?:[:.]\d{2})?\s*(?:AM|PM|Hrs)?)?)",
    re.I,
)

_CURRENCY_VALUE_RE = re.compile(
    r"((?:Rs\.?|INR|₹)\s*[\d,]+(?:\.\d+)?(?:\s*/-)?(?:\s*(?:Lakh|Lakhs|Lac|Lacs|Crore|Crores|Thousand|Million))?(?:\s*\([^)]+\))?"
    r"|\b[\d,]+(?:\.\d+)?\s*(?:Lakhs?|Lacs?|Crores?)\b(?:\s*\([^)]+\))?)",
    re.I,
)

_URL_RE = re.compile(
    r"(https?://[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+|www\.[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+)",
    re.I,
)

_PHONE_RE = re.compile(
    r"(?:(?:\+?\d{1,3}[\s\-]?)?(?:\(?\d{2,5}\)?[\s\-]?\d{6,8}(?:-\d{2})?|\b[6-9]\d{9}\b))"
)


class TenderExtractor:
    """Extracts all 25 fixed tender schema fields with provenance & grounding validation."""

    _DISK_CACHE_DIR = os.path.join("data", "cache", "extractions")
    _MAX_CACHE_ENTRIES = 48
    _CACHE_VERSION = "v3"

    def __init__(self) -> None:
        self._cache_lock = threading.Lock()
        self._extraction_cache: "OrderedDict[Tuple[str, str, bool], TenderExtractionResult]" = OrderedDict()

    def invalidate_cache(self) -> None:
        """Clears in-memory and disk tender extraction caches."""
        with self._cache_lock:
            self._extraction_cache.clear()
        if os.path.isdir(self._DISK_CACHE_DIR):
            for fname in os.listdir(self._DISK_CACHE_DIR):
                if fname.endswith(".json"):
                    try:
                        os.remove(os.path.join(self._DISK_CACHE_DIR, fname))
                    except OSError:
                        pass

    def _disk_cache_path(self, bundle_sig: str, nas_key: str, use_llm: bool) -> str:
        sub = hashlib.sha256(f"{self._CACHE_VERSION}|{bundle_sig}|{nas_key}|{int(use_llm)}".encode("utf-8")).hexdigest()[:24]
        return os.path.join(self._DISK_CACHE_DIR, f"{sub}.json")

    def _get_cached_extraction(
        self,
        bundle_sig: str,
        nas_path: Optional[str],
        use_llm: bool,
    ) -> Optional[TenderExtractionResult]:
        nas_key = str(nas_path or "").strip()
        key = (bundle_sig, nas_key, bool(use_llm))
        with self._cache_lock:
            cached = self._extraction_cache.get(key)
            if cached is not None:
                self._extraction_cache.move_to_end(key)
                clone = cached.model_copy(deep=True)
                clone.cache_hit = True
                return clone

        disk_path = self._disk_cache_path(bundle_sig, nas_key, use_llm)
        if os.path.exists(disk_path):
            try:
                with open(disk_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                loaded = TenderExtractionResult(**payload)
                loaded.cache_hit = True
                with self._cache_lock:
                    self._extraction_cache[key] = loaded.model_copy(deep=True)
                    while len(self._extraction_cache) > self._MAX_CACHE_ENTRIES:
                        self._extraction_cache.popitem(last=False)
                return loaded
            except Exception as e:
                logger.warning(f"Ignoring corrupt extraction cache {disk_path}: {e}")
        return None

    def _store_cached_extraction(
        self,
        bundle_sig: str,
        nas_path: Optional[str],
        use_llm: bool,
        result: TenderExtractionResult,
    ) -> None:
        nas_key = str(nas_path or "").strip()
        key = (bundle_sig, nas_key, bool(use_llm))
        with self._cache_lock:
            self._extraction_cache[key] = result.model_copy(deep=True)
            while len(self._extraction_cache) > self._MAX_CACHE_ENTRIES:
                self._extraction_cache.popitem(last=False)
        try:
            os.makedirs(self._DISK_CACHE_DIR, exist_ok=True)
            disk_path = self._disk_cache_path(bundle_sig, nas_key, use_llm)
            with open(disk_path, "w", encoding="utf-8") as f:
                json.dump(result.model_dump(), f, ensure_ascii=False)
        except Exception as e:
            logger.debug(f"Could not write extraction cache: {e}")

    def _add_candidate(
        self,
        bucket: Dict[str, List[TenderFieldEvidence]],
        field_name: str,
        value: str,
        rec: PageRecord,
        source_text: str,
        confidence: float,
        notes: Optional[str] = None,
        status: str = "VERIFIED",
    ) -> None:
        cleaned = clean_candidate_value(value)
        if not cleaned:
            return
        # Clean stray OCR/table artifacts
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" |.;:")
        if field_name in IMPORTANT_DATE_FIELDS:
            cleaned = re.sub(r"\bat\.\s*", "at ", cleaned, flags=re.I)
        if not cleaned or len(cleaned) < 2:
            return

        section = field_section_for(field_name)
        bucket.setdefault(field_name, []).append(
            TenderFieldEvidence(
                field_name=field_name,
                label=FIELD_DISPLAY_LABELS.get(field_name, field_name),
                section=section,  # type: ignore[arg-type]
                value=cleaned,
                source_file=rec.filename,
                source_page=rec.page_number,
                source_sheet=rec.sheet_name,
                source_text=(source_text or cleaned)[:320],
                confidence=round(min(0.99, max(0.1, confidence)), 2),
                status=status if status in ("VERIFIED", "NEEDS_REVIEW") else "NEEDS_REVIEW",  # type: ignore[arg-type]
                notes=notes,
            )
        )

    def _classify_date_label(self, label_text: str) -> Optional[str]:
        ll = re.sub(r"\s+", " ", (label_text or "").lower())
        if not ll:
            return None
        if any(k in ll for k in ("corrigendum", "amended")) and "submission" in ll and any(k in ll for k in ("end", "closing", "last", "extended", "revised")):
            return "bid_submission_end"
        if any(k in ll for k in ("corrigendum", "amended")) and "technical" in ll and "open" in ll:
            return "technical_bid_opening_date"
        if any(k in ll for k in ("date of uploading of n.i.t", "uploading of nit", "tender publication", "date of publication", "nit date", "issue date", "published date", "release date")):
            return "tender_publication_date"
        if any(k in ll for k in ("download start", "downloading", "sale start", "document sale / download start", "documents download start")) and "end" not in ll and "close" not in ll:
            return "document_download_start"
        if any(k in ll for k in ("download end", "download close", "download closing", "sale end", "document sale / download end")):
            return "document_download_end"
        if any(k in ll for k in ("query start", "clarification start", "pre-bid clarification start", "prebid query start")):
            return "prebid_query_start"
        if any(k in ll for k in ("query end", "queries end", "clarification end", "reaching wtl by", "last date of pre-bid quer", "pre-bid query closing", "queries by")):
            return "prebid_query_end"
        if any(k in ll for k in ("pre-bid meeting", "pre bid meeting", "prebid meeting", "pre-bid conference")):
            return "prebid_meeting_date"
        if any(k in ll for k in ("pre-bid response", "prebid response", "clarification response", "replies to pre-bid")):
            return "prebid_response_date"
        if any(k in ll for k in ("bid submission start", "submission start", "online bid submission start")):
            return "bid_submission_start"
        if any(k in ll for k in ("bid submission end", "bid submission closing", "last date & time of bid submission", "last date of bid submission", "closing of submission", "submission deadline", "due date for submission", "last date for submission")):
            return "bid_submission_end"
        if any(k in ll for k in ("pq bid opening", "pre-qualification bid opening", "prequalification opening", "pq opening")):
            return "pq_bid_opening_date"
        if any(k in ll for k in ("technical bid opening", "technical proposal", "opening of technical bid", "techno-commercial bid opening", "technical opening")):
            return "technical_bid_opening_date"
        if any(k in ll for k in ("financial bid opening", "opening of financial bid", "commercial bid opening", "price bid opening", "financial opening")):
            return "financial_bid_opening_date"
        return None

    def _clean_date_match(self, text: str) -> Optional[str]:
        if not text:
            return None
        # Skip placeholders like "To be intimated later"
        if re.search(r"\b(to be intimated|will be notified|to be announced)\b", text, re.I):
            return None
        m = _DATE_VALUE_RE.search(text)
        if not m:
            return None
        val = re.sub(r"\s+", " ", m.group(1)).strip(" ,.;:")
        # Validate numeric dd-mm-yyyy range to prevent tender codes like 26-27/046
        m_num = re.match(r"^(\d{1,2})([-/.])(\d{1,2})\2(\d{2,4})", val)
        if m_num:
            d, mo = int(m_num.group(1)), int(m_num.group(3))
            if not (1 <= d <= 31 and 1 <= mo <= 12):
                return None
        val = re.sub(r"\bat\.\s*", "at ", val, flags=re.I)
        return val

    def _extract_pairs_from_page(self, text: str) -> List[Tuple[str, str, str]]:
        """Extracts (label, value, raw_context_line) pairs from tables, colon lines, and adjacent lines."""
        pairs: List[Tuple[str, str, str]] = []
        raw_lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
        # Strip Excel "[Row N]" prefixes so key:value and pipe patterns match spreadsheet rows cleanly
        lines = [re.sub(r"^\[Row\s+\d+(?:\s+Header)?\]\s*", "", ln) for ln in raw_lines]
        inline_kv_re = re.compile(r"^([A-Za-z0-9 &/().,\-]{3,65}?)\s*(?::-|[:\-–]+)\s+(.+)$")

        for idx, line in enumerate(lines):
            # 1. Pipe-delimited table row: "Sl. No | Label | Value" or "Label | Value"
            if "|" in line:
                cells = [c.strip() for c in line.split("|") if c.strip()]
                if len(cells) >= 3 and re.match(r"^\d+\.?$", cells[0]):
                    label = cells[1]
                    val = " | ".join(cells[2:])
                    pairs.append((label, val, line))
                elif len(cells) >= 2:
                    pairs.append((cells[0], " | ".join(cells[1:]), line))
                # Also extract individual "Header: Value" fragments inside pipe row
                for c in cells:
                    if ":" in c and not c.lower().startswith("http"):
                        k, v = c.split(":", 1)
                        if k.strip() and v.strip():
                            pairs.append((k.strip(), v.strip(), line))

            # 2. Inline "Label: Value", "Label:- Value", or "Label - Value"
            m_colon = inline_kv_re.match(line) if not line.lower().startswith("http") else None
            if m_colon:
                k, v = m_colon.group(1).strip(), m_colon.group(2).strip()
                if not re.match(r"^https?$", k, re.I):
                    pairs.append((k, v, line))

            # 3. Vertical 2-line (or multi-line wrapped) layout ("Name of Item:\nDesign...", "Date...\n22-10-2026...")
            if idx + 1 < len(lines) and "|" not in line and not m_colon:
                next_line = lines[idx + 1]
                next_is_kv = bool(inline_kv_re.match(next_line)) and not next_line.lower().startswith("http")
                if not next_is_kv and len(line) <= 95:
                    if line.endswith(":"):
                        # Join wrapped continuation lines until sentence end, table/header, or next label
                        parts: List[str] = []
                        for j in range(idx + 1, min(len(lines), idx + 8)):
                            nxt = lines[j]
                            if (
                                "|" in nxt
                                or nxt.startswith("[Table")
                                or nxt.startswith("(")
                                or re.match(r"^(?:SL|S\.?\s*No\.?)\b", nxt, re.I)
                                or (nxt.endswith(":") and len(nxt) <= 65)
                                or (inline_kv_re.match(nxt) and not nxt.lower().startswith("http"))
                            ):
                                break
                            parts.append(nxt)
                            if nxt.endswith("."):
                                break
                        if parts:
                            joined = " ".join(parts)
                            pairs.append((line.rstrip(":"), joined, f"{line} -> {joined}"))
                    elif _DATE_VALUE_RE.search(next_line) or _CURRENCY_VALUE_RE.search(next_line) or _PHONE_RE.search(next_line):
                        pairs.append((line.rstrip(":"), next_line, f"{line} -> {next_line}"))

        return pairs

    def _extract_deterministic(self, records: List[PageRecord]) -> Dict[str, List[TenderFieldEvidence]]:
        """Extracts grounded high-confidence candidates using deterministic patterns across all pages."""
        bucket: Dict[str, List[TenderFieldEvidence]] = {}

        for rec in records:
            txt = rec.text or ""
            if not txt.strip():
                continue
            lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
            is_corrigendum = "corrigendum" in rec.filename.lower() or "corrigendum" in txt[:600].lower()
            conf_boost = 0.04 if is_corrigendum else 0.0
            corr_note = "Extracted from Corrigendum" if is_corrigendum else None

            # --- Pair-based extraction (tables, key:value, 2-line schedules) ---
            for label, val, raw_ctx in self._extract_pairs_from_page(txt):
                ll = label.lower()

                # Tender ID (avoid overwriting with dates)
                if any(k in ll for k in ("tender no", "tender id", "nit no", "rfp no", "ref. no", "bid number", "tender reference")):
                    id_match = re.match(r"^([A-Za-z0-9][A-Za-z0-9/.\-_]{4,60})(?:\s+(?:Dated|Date)\b.*)?$", val, re.I)
                    tid = id_match.group(1).strip(" .,:;") if id_match else val.split("Dated")[0].strip(" .,:;")
                    if tid and rec.extraction_method.startswith("ocr"):
                        tid = re.sub(r"(?<=[/-])l(?=[A-Z]{2,})|(?<=[A-Z])l(?=[A-Z/\-])", "I", tid)
                    if tid and not _DATE_VALUE_RE.fullmatch(tid) and len(tid) >= 5:
                        self._add_candidate(bucket, "tender_id", tid, rec, raw_ctx, 0.92 + conf_boost, notes=corr_note)
                    # Check if "Dated DD-MM-YYYY" is bundled on the same line
                    dated_m = re.search(r"Dated?\s*[:\-]?\s*(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})", val, re.I)
                    if dated_m:
                        self._add_candidate(bucket, "tender_publication_date", dated_m.group(1), rec, raw_ctx, 0.85, notes="Extracted from NIT Dated header")

                # Bid Title / Name of Work
                if any(k in ll for k in ("brief description of material", "name of work", "name of item", "title of tender", "bid title", "project title", "work description")):
                    if len(val) >= 12:
                        self._add_candidate(bucket, "bid_title", val, rec, raw_ctx, 0.90)

                # Organization / Department
                if any(k in ll for k in ("department", "organization", "organisation", "issuing authority", "execution authority", "procuring entity", "company name")) and "tender" not in ll:
                    if 3 <= len(val) <= 140 and not val.lower().startswith("to be"):
                        self._add_candidate(bucket, "department_organization", val, rec, raw_ctx, 0.86)

                # Financial: EMD vs Estimated Value (strict separation!)
                if any(k in ll for k in ("earnest money", "bid emd", "emd value", "emd amount", "bid security")) or re.fullmatch(r"emd", ll):
                    if "exemption" not in ll and "intimation" not in ll:
                        cm = _CURRENCY_VALUE_RE.search(val)
                        if cm:
                            self._add_candidate(bucket, "bid_emd_value", cm.group(1), rec, raw_ctx, 0.94 + conf_boost, notes=corr_note)

                if any(k in ll for k in ("estimated tender value", "estimated cost", "estimated value", "put to tender", "approximate value", "project cost", "grand total", "total estimated")) and not any(b in ll for b in ("turnover", "similar", "minimum project", "eligibility")):
                    cm = _CURRENCY_VALUE_RE.search(val)
                    if cm:
                        self._add_candidate(bucket, "estimated_tender_value", cm.group(1), rec, raw_ctx, 0.92 + conf_boost, notes=corr_note)

                # Dates
                date_field = self._classify_date_label(ll)
                if date_field:
                    dval = self._clean_date_match(val)
                    if dval:
                        self._add_candidate(bucket, date_field, dval, rec, raw_ctx, 0.93 + conf_boost, notes=corr_note)

                # Standalone "Date" header pair at top of NIT (page 1/2)
                if rec.page_number <= 3 and re.fullmatch(r"date", ll):
                    dval = self._clean_date_match(val)
                    if dval:
                        self._add_candidate(bucket, "tender_publication_date", dval, rec, raw_ctx, 0.86, notes="Document header Date")

                # Address & Contact Phone
                if (
                    re.match(r"^(?:[a-z]+\s+)?(?:office\s+|correspondence\s+|postal\s+|wtl\s+)?address$", ll)
                    and "details to be furnished" not in raw_ctx.lower()
                ):
                    addr_cleaned = re.split(r"\b13\.\s*contact\b|\bcontact person\b", val, maxsplit=1, flags=re.I)[0].strip()
                    if len(addr_cleaned) >= 12 and not addr_cleaned.endswith(":") and not any(bad in addr_cleaned.lower() for bad in ("tcp/ip", "http", "eprocure", "e-mail")):
                        self._add_candidate(bucket, "customer_address", addr_cleaned, rec, raw_ctx, 0.86)

                if any(k in ll for k in ("contact person", "phone", "tel", "telephone", "mobile", "helpline", "contact no")) and "details to be furnished" not in raw_ctx.lower():
                    pm = _PHONE_RE.search(val)
                    if pm:
                        ph = pm.group(0).strip()
                        if len(re.sub(r"\D", "", ph)) >= 8 and not re.match(r"^\d{6}$", ph):
                            self._add_candidate(bucket, "customer_phone", ph, rec, raw_ctx, 0.85)
                    elif not any(d in val for d in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")) and 3 <= len(val) <= 80:
                        self._add_candidate(bucket, "customer_name", val, rec, raw_ctx, 0.80)

                if any(k in ll for k in ("customer name", "client name", "purchaser", "beneficiary", "indenter", "nodal officer")):
                    if 3 <= len(val) <= 100:
                        self._add_candidate(bucket, "customer_name", val, rec, raw_ctx, 0.84)

                if re.fullmatch(r"state", ll):
                    if 3 <= len(val) <= 45:
                        self._add_candidate(bucket, "state", val, rec, raw_ctx, 0.90)

            # --- Prose / Header Patterns across full page text ---
            # 1. Cover / Page 1 Header Org & Tender ID (common in Indian government tenders)
            if rec.page_number <= 3:
                for ln in lines[:12]:
                    # Header organization in ALL CAPS or ending with Limited/University/Corporation/Board/Department
                    if (
                        len(ln) >= 6
                        and len(ln) <= 95
                        and not ln.startswith("(")
                        and not any(k in ln.lower() for k in ("notice inviting", "section", "page", "tender no", "version", "dated", "e-tender", "list of dates"))
                        and re.search(r"\b(LIMITED|UNIVERSITY|CORPORATION|AUTHORITY|DEPARTMENT|MINISTRY|BOARD|DIRECTORATE|COMMISSIONERATE|INSTITUTE)\b", ln, re.I)
                        and not ln.endswith(".")
                    ):
                        self._add_candidate(bucket, "department_organization", ln, rec, ln, 0.83)

                    # e.g. "WTL/WBPNB/CCTV/26-27/046 Dated 01-09-2026" or "No.F.TU/FIN/Wi-Fi/Vol-I/2025 Date: 22-10-2026"
                    m_hdr_id = re.search(r"(?:Tender\s+No\.?[:\-]*\s*)?([A-Za-z0-9][A-Za-z0-9./\-]{4,50})\s+(?:Dated?|Date)\s*[:\-]?\s*(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})", ln, re.I)
                    if m_hdr_id and "/" in m_hdr_id.group(1):
                        self._add_candidate(bucket, "tender_id", m_hdr_id.group(1), rec, ln, 0.90)
                        self._add_candidate(bucket, "tender_publication_date", m_hdr_id.group(2), rec, ln, 0.86)
                    elif ln.lower().startswith("no.") and "/" in ln and 6 <= len(ln) <= 55:
                        self._add_candidate(bucket, "tender_id", ln, rec, ln, 0.88)

            # 2. Inline prose pre-bid query cutoff (e.g., "Only queries ... reaching WTL by 07-09-26 at 3 PM")
            m_qend = re.search(
                r"(?:queries|clarifications)[^.]{0,110}\b(?:by|before|upto|on or before|till)\s+(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}(?:\s*(?:at|@)?\s*\d{1,2}(?:[:.]\d{2})?\s*(?:AM|PM|Hrs))?)",
                txt,
                re.I,
            )
            if m_qend:
                self._add_candidate(bucket, "prebid_query_end", m_qend.group(1), rec, m_qend.group(0), 0.88)

            # 3. Inline prose EMD & Estimated Value (e.g., Page 15 of Tripura University: "An EMD/Bid Security of Rs. 5,00,000/- ...")
            for m_emd in re.finditer(
                r"(?:EMD|Earnest\s+Money(?:\s+Deposit)?|Bid\s+Security)[^.\n]{0,70}?\b((?:Rs\.?|INR|₹)\s*[\d,]+(?:\.\d+)?(?:\s*/-)?(?:\s*(?:Lakh|Lakhs|Lac|Lacs|Crore|Crores))?(?:\s*\([^)]+\))?)",
                txt,
                re.I,
            ):
                snippet = m_emd.group(0)
                if "exemption" in snippet.lower() or "intimation" in snippet.lower():
                    continue
                self._add_candidate(bucket, "bid_emd_value", m_emd.group(1), rec, snippet, 0.91 + conf_boost, notes=corr_note)

            for m_est in re.finditer(
                r"(?:estimated\s+(?:tender\s+)?(?:cost|value)|project\s+(?:cost|value)|work\s+value|put\s+to\s+tender)[^.\n]{0,70}?\b((?:Rs\.?|INR|₹)\s*[\d,]+(?:\.\d+)?(?:\s*/-)?(?:\s*(?:Lakh|Lakhs|Lac|Lacs|Crore|Crores))?(?:\s*\([^)]+\))?)",
                txt,
                re.I,
            ):
                snippet = m_est.group(0)
                ctx_s = max(0, m_est.start() - 85)
                wide_snippet = txt[ctx_s : m_est.end()].lower()
                if any(bad in wide_snippet for bad in ("turnover", "similar work", "similar project", "minimum project", "involving", "solvency", "tender fee")):
                    continue
                self._add_candidate(bucket, "estimated_tender_value", m_est.group(1), rec, snippet, 0.90 + conf_boost, notes=corr_note)

            # 4. Inline prose Bid Title (NIT opening sentence)
            m_title = re.search(
                r"(?:invites?\s+(?:e-?Tenders?|bids?)[^\n]{0,220}?\bfor\s+(?:the\s+following\s+work\s*:\s*|implementation\s+of\s+)?|e-?Tender(?:s)?\s+are\s+invited\s+for\s+(?:implementation\s+of\s+)?)[\"\u201c]?([A-Za-z][A-Za-z0-9\s,()/&\-]{18,360})",
                txt,
                re.I,
            )
            if m_title and rec.page_number <= 5:
                cand_title = m_title.group(1).split("\u201d")[0].split('"')[0].strip(' ".,;:')
                cand_title = re.sub(r"\s+", " ", cand_title)
                self._add_candidate(bucket, "bid_title", cand_title, rec, m_title.group(0), 0.87)

            # 5. Customer / Inviting Beneficiary in prose ("under Inspector General of Police...")
            if rec.page_number <= 4:
                m_cust = re.search(
                    r"\bunder\s+(?:the\s+)?((?:Inspector\s+General\s+of\s+Police|Director\s+General|Department\s+of|Directorate\s+of|Commissioner(?:ate)?\s+of|Government\s+of)[A-Za-z0-9\s(),&\-]{4,85})",
                    txt,
                    re.I,
                )
                if m_cust:
                    cust_clean = re.sub(r"\b(?:Bids\s+are|No\.\s*F).*$", "", m_cust.group(1), flags=re.I).strip(" .,;")
                    if cust_clean:
                        self._add_candidate(bucket, "customer_name", cust_clean, rec, m_cust.group(0), 0.78)

            # 6. Portal URLs
            for m_url in _URL_RE.finditer(txt):
                u = m_url.group(1).rstrip(".,;)")
                # Fix glued PDF words like .../eprocure/appas or ...ac.inInterested
                u = re.sub(r"(/eprocure/app)[a-z]+$", r"\1", u, flags=re.I)
                u = re.sub(r"(\.(?:gov\.in|ac\.in|org\.in|nic\.in|co\.in|com|org))[A-Z][a-z]+.*$", r"\1", u)
                if any(bad in u.lower() for bad in ("w3.org", "schemas.", "openxmlformats", "example.com", "iafcertsearch")):
                    continue
                is_eproc = any(p in u.lower() for p in ("eprocure", "wbtenders", "etender", "gem.gov", "tender"))
                if not is_eproc and (rec.page_number > 6 or any("tender" in c.value.lower() or "eprocure" in c.value.lower() for c in bucket.get("tender_portal_url", []))):
                    continue
                conf_u = 0.94 if is_eproc else 0.72
                self._add_candidate(bucket, "tender_portal_url", u, rec, _around_match(txt, m_url.start(), m_url.end()), conf_u)

            # 7. Signed / Footer DDO or Officer block on Page 1-3 (e.g. "(Dr. Nirmalya Debnath) Drawing & Disbursing Officer")
            if rec.page_number <= 3:
                m_addr = re.search(r"([A-Za-z0-9\s,\-./]{10,120}[-–]\s*\d{6})", txt)
                if m_addr and "pin" not in m_addr.group(1).lower():
                    addr_val = re.sub(r"\s+", " ", m_addr.group(1)).strip(" .,;")
                    if len(addr_val) >= 14 and not re.search(r"tender\s+no|bid\s+submission", addr_val, re.I):
                        self._add_candidate(bucket, "customer_address", addr_val, rec, addr_val, 0.80)

            # 8. State detection (explicit state mention or unambiguous city/PIN state inference)
            if rec.page_number <= 4:
                for st in INDIAN_STATES:
                    if re.search(rf"\b{re.escape(st)}\b", txt, re.I):
                        self._add_candidate(bucket, "state", st, rec, _find_line_with(txt, st), 0.86)
                        break
                else:
                    tl = txt.lower()
                    for city, st in _CITY_TO_STATE.items():
                        if re.search(rf"\b{re.escape(city)}\b", tl):
                            self._add_candidate(
                                bucket,
                                "state",
                                st,
                                rec,
                                _find_line_with(txt, city),
                                0.76,
                                notes=f"Inferred from verified location '{city.title()}'",
                                status="NEEDS_REVIEW",
                            )
                            break

        return bucket

    def _run_gemma_enrichment(
        self,
        records: List[PageRecord],
        bucket: Dict[str, List[TenderFieldEvidence]],
        index: Optional[TenderDocumentIndex] = None,
    ) -> Tuple[Optional[str], str, str]:
        """Fast two-tier Gemma call: concise summary when core anchors exist, or delta JSON for missing fields."""
        try:
            from backend.app.services.llm.answer_model_service import answer_model_service
        except Exception as e:
            logger.warning(f"answer_model_service unavailable: {e}")
            return None, "", "unavailable"

        priority_order = [
            "bid_title", "department_organization", "state", "customer_name",
            "customer_phone", "customer_address", "category", "tender_id",
            "estimated_tender_value", "bid_emd_value", "bid_submission_end",
            "technical_bid_opening_date", "financial_bid_opening_date",
            "prebid_meeting_date", "tender_publication_date", "keywords_for_summary",
        ]
        missing_targets = [f for f in priority_order if not bucket.get(f)][:6]
        core_anchors_ready = len(bucket) >= 12 and all(
            bucket.get(k) for k in ("bid_title", "department_organization", "tender_id", "bid_submission_end")
        )

        # Tier 1: Fast grounded summary when all core anchors & 12+ fields are already extracted & verified
        if core_anchors_ready:
            if index is not None:
                context_block = index.retrieve_for_groups(["bid_title", "keywords_for_summary"], max_chars=750)
            else:
                pages_basic = select_high_signal_pages(records, BASIC_KEYWORDS + SUMMARY_ELIGIBILITY_KEYWORDS, max_pages=2)
                context_block = format_pages_for_prompt(pages_basic[:2], max_chars=750)
            if not context_block:
                return None, _build_deterministic_summary(records, bucket), "Gemma-4-E2B-It-Q4_K_M"

            summary_prompt = (
                "Write a crisp 2-sentence factual summary covering scope, issuing authority, deadline, and EMD "
                "using ONLY the excerpt below. Do not invent figures.\n\n"
                f"EXCERPT:\n{context_block}\n\nSUMMARY:"
            )
            model_name = "Gemma-4-E2B-It-Q4_K_M"
            try:
                raw_sum = answer_model_service.generate_general_response(
                    prompt=summary_prompt,
                    system_instruction="You are a concise government tender analyst. Output only 2 factual sentences.",
                    max_tokens=72,
                )
                status_info = answer_model_service.get_status()
                model_name = str(status_info.get("model_name") or model_name)
                clean_sum = re.sub(r"\s+", " ", (raw_sum or "")).strip()
                if len(clean_sum) >= 35 and "couldn't find" not in clean_sum.lower():
                    return raw_sum, clean_sum, model_name
            except Exception as e:
                logger.warning(f"Gemma summary-only enrichment failed cleanly: {e}")
            return None, _build_deterministic_summary(records, bucket), model_name

        # Tier 2: Targeted delta JSON extraction ONLY for missing fields + crisp summary
        if index is not None:
            context_block = index.retrieve_for_groups(missing_targets or ["bid_title", "keywords_for_summary"], max_chars=1350)
        else:
            pages_basic = select_high_signal_pages(records, BASIC_KEYWORDS + DATE_KEYWORDS + FINANCIAL_KEYWORDS, max_pages=3)
            context_block = format_pages_for_prompt(pages_basic[:3], max_chars=1350)

        if not context_block:
            return None, "", "empty_context"

        requested_keys = missing_targets + ["detailed_summary"]
        keys_str = ", ".join(requested_keys)
        prompt = (
            "Extract ONLY the missing tender fields listed below from the excerpts.\n"
            "Rules: Output ONE compact JSON object, no markdown. Never invent values; use \"NOT_FOUND\" if absent. "
            "Never put EMD/Bid Security, Tender Fee, or Bidder Turnover into estimated_tender_value.\n"
            f"Required JSON keys: {keys_str} (detailed_summary = 1-2 factual sentences).\n\n"
            f"EXCERPTS:\n{context_block}\n\nJSON:"
        )

        system_instr = (
            "You are a precision tender analyst. Respond ONLY with a compact valid JSON object containing strictly grounded facts."
        )

        raw = ""
        model_name = "Gemma-4-E2B-It-Q4_K_M"
        max_gen_tokens = 84 if not missing_targets else 136
        try:
            raw = answer_model_service.generate_general_response(
                prompt=prompt,
                system_instruction=system_instr,
                max_tokens=max_gen_tokens,
            )
            status_info = answer_model_service.get_status()
            model_name = str(status_info.get("model_name") or model_name)
        except Exception as e:
            logger.warning(f"Gemma enrichment failed cleanly (deterministic extraction preserved): {e}")
            return None, "", model_name

        parsed = _parse_json_object(raw)
        if not parsed:
            logger.info("Gemma enrichment returned non-JSON; keeping deterministic results and building grounded summary.")
            return None, _build_deterministic_summary(records, bucket), model_name

        # Verify every LLM-proposed field against source records before admitting into candidate bucket
        llm_fields = [f for f in ALL_TENDER_FIELD_NAMES if f != "nas_path"]
        for fname in llm_fields:
            val = parsed.get(fname)
            if isinstance(val, list):
                val = ", ".join(str(x) for x in val if x)
            val_str = clean_candidate_value(str(val) if val is not None else "")
            if not val_str:
                continue

            # Keep deterministic high-confidence candidates for strict numeric/date/ID fields
            if fname in (FINANCIAL_FIELDS + IMPORTANT_DATE_FIELDS + ["tender_id", "tender_portal_url"]) and bucket.get(fname):
                continue

            grounded = verify_value_in_records(fname, val_str, records)
            if grounded:
                rec, snippet = grounded
                # Strict anti-contamination guard for estimated_tender_value
                if fname == "estimated_tender_value":
                    sl = snippet.lower()
                    if any(bad in sl for bad in ("turnover", "similar work", "solvency", "tender fee")) or (
                        any(emd_kw in sl for emd_kw in ("emd", "earnest money", "bid security"))
                        and "estimated" not in sl
                    ):
                        continue
                conf = 0.78 if fname not in ("category", "keywords_for_summary") else 0.85
                status = "VERIFIED" if conf >= 0.78 else "NEEDS_REVIEW"
                self._add_candidate(
                    bucket,
                    fname,
                    val_str,
                    rec,
                    snippet,
                    conf,
                    notes="Extracted & source-verified by local LLM",
                    status=status,
                )

        summary = str(parsed.get("detailed_summary") or "").strip()
        if not summary or len(summary) < 40 or "couldn't find" in summary.lower():
            summary = _build_deterministic_summary(records, bucket)

        return raw, summary, model_name

    def extract_from_documents(
        self,
        documents: List[Dict[str, Any]],
        nas_path: Optional[str] = None,
        use_llm: bool = True,
        bypass_cache: bool = False,
    ) -> TenderExtractionResult:
        """Executes full multi-file, full-page tender extraction returning all 25 required fields."""
        t0 = time.perf_counter()
        bundle_sig = compute_bundle_signature(documents)

        if not bypass_cache:
            cached_res = self._get_cached_extraction(bundle_sig, nas_path, use_llm)
            if cached_res is not None:
                cached_ms = round((time.perf_counter() - t0) * 1000, 2)
                cached_res.elapsed_seconds = round(cached_ms / 1000.0, 4)
                timings = dict(cached_res.stage_timings or {})
                timings["cache_lookup_ms"] = cached_ms
                timings["cache_hit"] = True
                cached_res.stage_timings = timings
                logger.info(
                    f"TENDER EXTRACTION CACHE HIT: {cached_res.fields_found_count}/25 fields in {cached_ms:.2f}ms"
                )
                return cached_res

        t_idx0 = time.perf_counter()
        index, idx_cache_hit = get_or_build_index(documents)
        records = index.records
        index_ms = round((time.perf_counter() - t_idx0) * 1000, 2)

        # Collect per-file coverage metrics
        coverage_list: List[TenderFileCoverage] = []
        total_pages = 0
        ocr_pages_count = 0
        unreadable_pages_count = 0

        for doc in documents:
            doc_id = str(doc.get("document_id") or "")
            fname = str(doc.get("filename") or doc.get("original_filename") or "uploaded_document")
            ext = str(doc.get("extension") or doc.get("file_type") or "").lower()
            doc_pages = [r for r in records if r.filename == fname and (not doc_id or r.document_id == doc_id)]
            ocr_nums = [r.page_number for r in doc_pages if r.extraction_method.startswith("ocr") and not r.unreadable_reason]
            unread_nums = [r.page_number for r in doc_pages if r.unreadable_reason]
            sheets = list(dict.fromkeys([r.sheet_name for r in doc_pages if r.sheet_name]))
            extracted_cnt = sum(1 for r in doc_pages if r.text.strip() and not r.unreadable_reason)

            p_total = max(len(doc_pages), int(doc.get("total_pages") or 0))
            total_pages += p_total
            ocr_pages_count += len(ocr_nums)
            unreadable_pages_count += len(unread_nums)

            coverage_list.append(
                TenderFileCoverage(
                    filename=fname,
                    document_id=doc_id or None,
                    file_type=ext,
                    total_pages=p_total,
                    extracted_pages=extracted_cnt,
                    ocr_pages=ocr_nums,
                    unreadable_pages=unread_nums,
                    sheets=sheets,
                    ocr_engine=doc.get("ocr_engine"),
                    error=doc.get("parse_error"),
                )
            )

        t_det0 = time.perf_counter()
        bucket = self._extract_deterministic(records)

        # Prefer official e-procurement portal URLs over secondary institutional homepages
        portal_cands = bucket.get("tender_portal_url") or []
        eproc_only = [
            c for c in portal_cands
            if any(p in c.value.lower() for p in ("eprocure", "wbtenders", "etender", "gem.gov", "tender"))
        ]
        if eproc_only:
            bucket["tender_portal_url"] = eproc_only

        # Deterministic category inference if not explicitly labeled
        if not bucket.get("category") and records:
            inferred_cat = _infer_category_deterministic(records)
            if inferred_cat:
                self._add_candidate(
                    bucket,
                    "category",
                    inferred_cat,
                    records[0],
                    records[0].text[:200],
                    0.78,
                    notes="Classified from verified work scope keywords",
                    status="NEEDS_REVIEW",
                )

        # Deterministic keyword synthesis fallback so keywords_for_summary is factual even without LLM
        if not bucket.get("keywords_for_summary") and records:
            kw_terms = _extract_deterministic_keywords(records, bucket)
            if kw_terms:
                self._add_candidate(
                    bucket,
                    "keywords_for_summary",
                    ", ".join(kw_terms),
                    records[0],
                    records[0].text[:240],
                    0.82,
                    notes="Synthesized from verified tender headings",
                )
        det_extract_ms = round((time.perf_counter() - t_det0) * 1000, 2)

        t_llm0 = time.perf_counter()
        summary = ""
        model_used = "deterministic+Gemma-4-E2B-It-Q4_K_M"
        if use_llm and records:
            _raw, llm_summary, active_model = self._run_gemma_enrichment(records, bucket, index=index)
            summary = llm_summary
            model_used = active_model or model_used
        llm_extract_ms = round((time.perf_counter() - t_llm0) * 1000, 2)

        if not summary:
            summary = _build_deterministic_summary(records, bucket)

        t_val0 = time.perf_counter()

        # Resolve every one of the 25 required schema fields
        basic_out: Dict[str, TenderFieldEvidence] = {}
        fin_out: Dict[str, TenderFieldEvidence] = {}
        dates_out: Dict[str, TenderFieldEvidence] = {}
        add_out: Dict[str, TenderFieldEvidence] = {}

        missing_fields: List[str] = []
        conflicting_fields: List[Dict[str, Any]] = []
        unreadable_fields: List[str] = []

        for fname in ALL_TENDER_FIELD_NAMES:
            if fname == "nas_path":
                if nas_path and str(nas_path).strip():
                    ev = TenderFieldEvidence(
                        field_name="nas_path",
                        label=FIELD_DISPLAY_LABELS["nas_path"],
                        section="additional_information",
                        value=str(nas_path).strip(),
                        source_file="system_storage",
                        source_text="Provided by MYGPT file storage metadata",
                        confidence=1.0,
                        status="VERIFIED",
                    )
                else:
                    ev = TenderFieldEvidence(
                        field_name="nas_path",
                        label=FIELD_DISPLAY_LABELS["nas_path"],
                        section="additional_information",
                        value="NOT_FOUND",
                        confidence=0.0,
                        status="NOT_FOUND",
                        notes="No system NAS path provided.",
                    )
            else:
                ev = resolve_field_candidates(
                    fname,
                    bucket.get(fname, []),
                    unreadable_pages_count=unreadable_pages_count,
                    total_pages=total_pages,
                )

            if fname in BASIC_INFO_FIELDS:
                basic_out[fname] = ev
            elif fname in FINANCIAL_FIELDS:
                fin_out[fname] = ev
            elif fname in IMPORTANT_DATE_FIELDS:
                dates_out[fname] = ev
            else:
                add_out[fname] = ev

            if ev.status == "NOT_FOUND":
                missing_fields.append(fname)
            elif ev.status == "UNREADABLE":
                unreadable_fields.append(fname)
            elif ev.alternatives:
                conflicting_fields.append({
                    "field_name": fname,
                    "label": ev.label,
                    "primary_value": ev.value,
                    "status": ev.status,
                    "source_file": ev.source_file,
                    "source_page": ev.source_page,
                    "alternatives": [a.model_dump() for a in ev.alternatives],
                })

        warnings = validate_date_chronology(dates_out)
        if unreadable_pages_count > 0:
            warnings.append(
                f"{unreadable_pages_count} page(s) could not be read clearly by local OCR."
            )

        found_count = sum(
            1
            for group in (basic_out, fin_out, dates_out, add_out)
            for ev in group.values()
            if ev.status not in ("NOT_FOUND", "UNREADABLE")
        )

        # Build key summary citations
        summary_pages = select_high_signal_pages(records, BASIC_KEYWORDS + FINANCIAL_KEYWORDS + DATE_KEYWORDS, max_pages=5)
        summary_sources = [
            {"filename": p.filename, "page_number": p.page_number, "sheet_name": p.sheet_name}
            for p in summary_pages
        ]

        validation_ms = round((time.perf_counter() - t_val0) * 1000, 2)
        total_extract_ms = round((time.perf_counter() - t0) * 1000, 2)
        stage_timings = {
            "index_ms": index_ms,
            "index_cache_hit": idx_cache_hit,
            "det_extract_ms": det_extract_ms,
            "llm_extract_ms": llm_extract_ms,
            "validation_ms": validation_ms,
            "total_extract_ms": total_extract_ms,
            "cache_hit": False,
        }
        logger.info(
            f"TENDER EXTRACTION TIMINGS: {found_count}/25 fields in {total_extract_ms:.1f}ms "
            f"(index={index_ms:.1f}ms, det={det_extract_ms:.1f}ms, llm={llm_extract_ms:.1f}ms, val={validation_ms:.1f}ms)"
        )

        result = TenderExtractionResult(
            document_ids=[str(d.get("document_id") or "") for d in documents if d.get("document_id")],
            source_files=[c.filename for c in coverage_list],
            nas_path_provided=nas_path,
            basic_information=basic_out,
            financial_information=fin_out,
            important_dates=dates_out,
            additional_information=add_out,
            missing_fields=missing_fields,
            conflicting_fields=conflicting_fields,
            unreadable_fields=unreadable_fields,
            warnings=warnings,
            detailed_summary=summary,
            summary_sources=summary_sources,
            file_coverage=coverage_list,
            total_pages=total_pages,
            ocr_pages_count=ocr_pages_count,
            unreadable_pages_count=unreadable_pages_count,
            fields_found_count=found_count,
            fields_not_found_count=len(missing_fields) + len(unreadable_fields),
            fields_ambiguous_count=len(conflicting_fields),
            model_used=model_used,
            elapsed_seconds=round(total_extract_ms / 1000.0, 3),
            cache_hit=False,
            stage_timings=stage_timings,
        )
        self._store_cached_extraction(bundle_sig, nas_path, use_llm, result)
        return result

    def _try_direct_field_answer(
        self,
        question: str,
        cached_extraction: Optional[Dict[str, Any]],
    ) -> Optional[Tuple[str, List[Dict[str, Any]]]]:
        """Instant grounded reply for direct single-field lookups when already extracted & verified."""
        if not cached_extraction or not isinstance(cached_extraction, dict):
            return None
        ql = (question or "").lower()
        if any(w in ql for w in ("explain", "why", "how", "eligib", "criteria", "clause", "section", "scope", "compare", "all dates", "summary", "turnover")):
            return None

        field_triggers: List[Tuple[Tuple[str, ...], str, str]] = [
            (("emd", "earnest money", "bid security"), "financial_information", "bid_emd_value"),
            (("estimated value", "estimated cost", "tender value", "project cost"), "financial_information", "estimated_tender_value"),
            (("last date", "submission deadline", "bid submission end", "submission end", "closing date", "due date"), "important_dates", "bid_submission_end"),
            (("pre-bid meeting", "prebid meeting"), "important_dates", "prebid_meeting_date"),
            (("technical bid opening", "technical opening"), "important_dates", "technical_bid_opening_date"),
            (("financial bid opening", "commercial bid opening", "price bid opening"), "important_dates", "financial_bid_opening_date"),
            (("publication date", "published"), "important_dates", "tender_publication_date"),
            (("tender id", "nit no", "reference no", "ref no"), "basic_information", "tender_id"),
            (("portal", "website", "url"), "basic_information", "tender_portal_url"),
            (("phone", "contact number", "telephone"), "basic_information", "customer_phone"),
        ]

        matched_targets: List[Tuple[str, str]] = []
        for cues, sec, fname in field_triggers:
            if any(c in ql for c in cues):
                matched_targets.append((sec, fname))
        if len(matched_targets) != 1:
            return None

        sec_key, fname = matched_targets[0]
        fobj = (cached_extraction.get(sec_key) or {}).get(fname)
        if not isinstance(fobj, dict) or fobj.get("value") in (None, "", "NOT_FOUND"):
            return None
        if fobj.get("status") != "VERIFIED" and float(fobj.get("confidence") or 0) < 0.78:
            return None

        sfile = fobj.get("source_file") or "document"
        spage = fobj.get("source_page")
        ssheet = fobj.get("source_sheet")
        loc = f"Sheet {ssheet} (Page {spage})" if ssheet else (f"Page {spage}" if spage else "Document")
        snippet = str(fobj.get("source_text") or "").strip()
        ans = f"**{fobj.get('label', fname)}:** `{fobj['value']}`\n\n- **Source:** {sfile} | {loc}"
        if snippet:
            ans += f"\n- **Evidence:** \"{snippet[:240]}\""
        return ans, [{"filename": sfile, "page_number": spage, "sheet_name": ssheet, "label": f"{sfile} | {loc}"}]

    def answer_followup_question(
        self,
        documents: List[Dict[str, Any]],
        question: str,
        cached_extraction: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Answers a follow-up question strictly grounded in indexed tender evidence."""
        direct = self._try_direct_field_answer(question, cached_extraction)
        if direct is not None:
            return direct

        index, _hit = get_or_build_index(documents)
        context_block, sources = retrieve_evidence_for_query(index, question, max_pages=4, max_chars=2200)

        # Provide quick verified lookup hints if question targets EMD / dates / tender ID
        verified_hints: List[str] = []
        if cached_extraction and isinstance(cached_extraction, dict):
            for section_key in ("basic_information", "financial_information", "important_dates", "additional_information"):
                sec = cached_extraction.get(section_key) or {}
                for fname, fobj in sec.items():
                    if isinstance(fobj, dict) and fobj.get("value") not in (None, "", "NOT_FOUND"):
                        src_loc = f"Page {fobj.get('source_page')}" if fobj.get("source_page") else (f"Sheet {fobj.get('source_sheet')}" if fobj.get("source_sheet") else "")
                        verified_hints.append(f"- {fobj.get('label', fname)}: {fobj['value']} ({fobj.get('source_file', '')} {src_loc})")

        hints_text = "\n".join(verified_hints[:10])
        try:
            from backend.app.services.llm.answer_model_service import answer_model_service

            prompt = (
                f"Answer the user's question about the tender document using ONLY the verified facts and excerpts below.\n"
                f"Cite exact page numbers or sheet names. If absent, state it is not specified.\n\n"
                f"EXTRACTED FIELDS:\n{hints_text}\n\n"
                f"EXCERPTS:\n{context_block}\n\n"
                f"QUESTION: {question}\n\nANSWER:"
            )
            answer = answer_model_service.generate_general_response(
                prompt=prompt,
                system_instruction="You are a concise, grounded tender analyst. Cite page numbers and never invent figures.",
                max_tokens=160,
            )
            if answer and answer.strip():
                return answer.strip(), sources
        except Exception as e:
            logger.warning(f"LLM tender follow-up failed, using deterministic evidence fallback: {e}")

        # Deterministic grounded fallback if LLM unavailable
        if sources:
            top_excerpt = context_block[:1200]
            cites = ", ".join(s["label"] for s in sources[:4])
            return f"Based on {cites}:\n\n{top_excerpt}", sources
        return "I couldn't find supporting information for that question in the uploaded tender document.", []


def format_tender_extraction_markdown(result: TenderExtractionResult) -> str:
    """Formats extracted tender fields cleanly into the 5 required Markdown sections."""
    lines: List[str] = []
    lines.append(
        f"## Tender Extraction Report ({result.fields_found_count}/25 Fields Extracted | "
        f"{result.total_pages} Page(s) Analyzed)"
    )

    def _fmt_loc(ev: TenderFieldEvidence) -> str:
        parts = []
        if ev.source_file:
            parts.append(ev.source_file)
        if ev.source_sheet:
            parts.append(f"Sheet: {ev.source_sheet}")
        if ev.source_page:
            parts.append(f"Page {ev.source_page}")
        return " | ".join(parts) if parts else "-"

    def _render_section(title: str, group: Dict[str, TenderFieldEvidence]) -> None:
        lines.append(f"\n### {title}")
        lines.append("| Field | Value | Status | Source | Confidence |")
        lines.append("|---|---|---|---|---|")
        for ev in group.values():
            val = ev.value.replace("|", "\\|")
            src = _fmt_loc(ev).replace("|", "\\|")
            conf = f"{int(round(ev.confidence * 100))}%" if ev.status != "NOT_FOUND" else "-"
            lines.append(f"| **{ev.label}** | {val} | `{ev.status}` | {src} | {conf} |")

    _render_section("1. Basic Tender Information", result.basic_information)
    _render_section("2. Financial Information", result.financial_information)
    _render_section("3. Important Dates", result.important_dates)
    _render_section("4. Additional Information", result.additional_information)

    lines.append("\n### 5. Missing or Conflicting Information")
    if result.missing_fields:
        missing_labels = [FIELD_DISPLAY_LABELS.get(f, f) for f in result.missing_fields]
        lines.append(f"- **Not Found ({len(missing_labels)}):** " + ", ".join(missing_labels))
    else:
        lines.append("- **Not Found:** None (all fields located)")

    if result.conflicting_fields:
        lines.append("- **Conflicting / Revised Values:**")
        for cf in result.conflicting_fields:
            alts = "; ".join(
                f"`{a.get('value')}` ({a.get('source_file', '')} p.{a.get('source_page', '?')})"
                for a in cf.get("alternatives", [])
            )
            lines.append(f"  - **{cf.get('label')}**: Primary `{cf.get('primary_value')}` vs Alternatives: {alts}")
    if result.warnings:
        for w in result.warnings:
            lines.append(f"- **Warning:** {w}")

    lines.append("\n### Detailed Tender Summary")
    lines.append(result.detailed_summary or "Summary unavailable.")
    return "\n".join(lines)


def _around_match(text: str, start: int, end: int, pad: int = 80) -> str:
    s = max(0, start - pad)
    e = min(len(text), end + pad)
    return re.sub(r"\s+", " ", text[s:e]).strip()


def _find_line_with(text: str, needle: str) -> str:
    nl = needle.lower()
    for ln in text.splitlines():
        if nl in ln.lower():
            return re.sub(r"\s+", " ", ln).strip()
    return text[:180]


def _parse_json_object(raw: str) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.I)
    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _infer_category_deterministic(records: List[PageRecord]) -> Optional[str]:
    sample = " ".join(r.text.lower() for r in records[:6])
    if any(k in sample for k in ("cctv", "anpr", "surveillance", "camera")):
        return "IT / Security & CCTV Surveillance"
    if any(k in sample for k in ("wi-fi", "wifi", "access point", "firewall", "network", "switch")):
        return "IT / Networking & Wi-Fi Infrastructure"
    if any(k in sample for k in ("software", "application", "cloud", "erp", "portal", "server")):
        return "IT & Software Services"
    if any(k in sample for k in ("civil", "construction", "road", "building", "bridge", "water supply")):
        return "Civil & Infrastructure Works"
    if any(k in sample for k in ("medical", "hospital", "pharma", "diagnostic", "equipment")):
        return "Healthcare & Medical Equipment"
    if any(k in sample for k in ("solar", "electrical", "substation", "transformer", "ups")):
        return "Electrical & Power Systems"
    return None


def _extract_deterministic_keywords(
    records: List[PageRecord],
    bucket: Dict[str, List[TenderFieldEvidence]],
) -> List[str]:
    terms: List[str] = []
    domain_vocab = [
        "e-Tender", "CCTV Surveillance", "ANPR", "Wi-Fi Network", "System Integrator",
        "Network Security", "EMD", "Technical Bid", "Financial Bid", "BOQ",
        "Supply & Installation", "Comprehensive Maintenance", "OEM Authorization",
    ]
    full_low = " ".join(r.text.lower() for r in records[:10])
    for t in domain_vocab:
        if t.lower() in full_low and t not in terms:
            terms.append(t)
    if bucket.get("department_organization"):
        org = bucket["department_organization"][0].value[:45]
        if org not in terms:
            terms.insert(0, org)
    if not terms:
        terms = ["Tender", "Procurement", "Technical Bid", "Financial Bid"]
    return terms[:7]


def _build_deterministic_summary(
    records: List[PageRecord],
    bucket: Dict[str, List[TenderFieldEvidence]],
) -> str:
    title = bucket["bid_title"][0].value if bucket.get("bid_title") else "Tender document"
    org = bucket["department_organization"][0].value if bucket.get("department_organization") else "the issuing authority"
    tid = bucket["tender_id"][0].value if bucket.get("tender_id") else "N/A"
    emd = bucket["bid_emd_value"][0].value if bucket.get("bid_emd_value") else "not specified"
    est = bucket["estimated_tender_value"][0].value if bucket.get("estimated_tender_value") else "not specified"
    deadline = bucket["bid_submission_end"][0].value if bucket.get("bid_submission_end") else "not specified"
    tech_open = bucket["technical_bid_opening_date"][0].value if bucket.get("technical_bid_opening_date") else "not specified"

    parts = [
        f"This tender ({tid}) issued by {org} covers {title}.",
        f"The Earnest Money Deposit (EMD) is {emd} and estimated tender value is {est}.",
        f"Bid submission deadline is {deadline}, with technical bid opening scheduled for {tech_open}.",
    ]
    # Add short eligibility note if found
    for r in records:
        if re.search(r"\b(eligibility|turnover|similar work|minimum \d+ years)\b", r.text, re.I):
            parts.append(f"Eligibility & bidder qualification clauses appear on Page {r.page_number} ({r.filename}).")
            break
    return " ".join(parts)


tender_extractor = TenderExtractor()

