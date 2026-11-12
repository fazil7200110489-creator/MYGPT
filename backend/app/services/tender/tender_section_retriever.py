"""Full-document page, table, and sheet index + retriever for Tender extraction and QA.

Builds a cached document-level inverted index over every page and spreadsheet sheet
across one or more uploaded tender files / annexures, enabling targeted group
retrieval (Basic, Financial, Dates, Additional) and follow-up QA without sending
or truncating the entire document repeatedly.
"""

from collections import OrderedDict, defaultdict
from dataclasses import dataclass
import hashlib
import re
import threading
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class PageRecord:
    """Normalized page or sheet slice belonging to an uploaded tender file."""

    filename: str
    document_id: str
    file_type: str
    page_number: int
    text: str
    sheet_name: Optional[str] = None
    extraction_method: str = "text"
    ocr_confidence: Optional[float] = None
    unreadable_reason: Optional[str] = None

    def location_label(self) -> str:
        if self.sheet_name:
            return f"{self.filename} | Sheet: {self.sheet_name} (Page {self.page_number})"
        return f"{self.filename} | Page {self.page_number}"


BASIC_KEYWORDS = [
    "tender", "nit", "notice inviting", "e-tender", "rfp", "rfq", "bid",
    "name of work", "title", "project", "department", "organization", "organisation",
    "authority", "invited by", "issued by", "corporation", "university", "limited",
    "state", "address", "pin", "phone", "tel", "mobile", "contact", "email",
    "portal", "website", "url", "eprocure", "wbtenders", "gem", "etender",
    "tender id", "tender no", "nit no", "reference no", "ref. no", "bid no",
]

FINANCIAL_KEYWORDS = [
    "emd", "earnest money", "bid security", "estimated", "estimate",
    "tender value", "project cost", "work value", "put to tender",
    "approximate value", "cost of work", "tender fee", "processing fee",
    "security deposit", "performance", "rs.", "inr", "crore", "lakh",
    "boq", "bill of quantities", "grand total", "total amount", "schedule of quantities",
]

DATE_KEYWORDS = [
    "date", "time", "schedule", "publish", "publication", "released",
    "sale", "download", "start date", "end date", "closing", "deadline",
    "pre-bid", "prebid", "pre bid", "clarification", "query", "queries",
    "meeting", "conference", "response", "corrigendum", "addendum",
    "submission", "last date", "due date", "opening", "pq", "pre-qualification",
    "technical bid", "financial bid", "price bid", "commercial bid",
]

SUMMARY_ELIGIBILITY_KEYWORDS = [
    "scope", "objective", "overview", "background", "eligibility",
    "qualification", "turnover", "similar work", "experience", "oem",
    "technical specification", "deliverables", "warranty", "sla", "completion period",
    "evaluation", "corrigendum", "important instruction",
]


def collect_page_records(documents: List[Dict[str, Any]]) -> List[PageRecord]:
    """Converts uploaded document metadata records into ordered PageRecord slices."""
    records: List[PageRecord] = []
    for doc in documents:
        doc_id = str(doc.get("document_id") or "")
        filename = str(doc.get("filename") or doc.get("original_filename") or "uploaded_document")
        file_type = str(doc.get("extension") or doc.get("file_type") or "").lower()
        pages = doc.get("pages") or []

        if not pages and doc.get("extracted_text"):
            raw_text = str(doc["extracted_text"])
            # Attempt to split by explicit page markers if present
            split_pages = re.split(r"\n?---+\s*Page\s+(\d+)\s*---+\n?", raw_text)
            if len(split_pages) >= 3:
                idx = 1
                while idx + 1 < len(split_pages):
                    p_num = int(split_pages[idx])
                    p_txt = split_pages[idx + 1].strip()
                    records.append(
                        PageRecord(
                            filename=filename,
                            document_id=doc_id,
                            file_type=file_type,
                            page_number=p_num,
                            text=p_txt,
                        )
                    )
                    idx += 2
            else:
                records.append(
                    PageRecord(
                        filename=filename,
                        document_id=doc_id,
                        file_type=file_type,
                        page_number=1,
                        text=raw_text,
                    )
                )
            continue

        for idx, p in enumerate(pages, start=1):
            p_num = int(p.get("page_number") or idx)
            p_text = str(p.get("text") or "")
            sheet_name = p.get("sheet_name")
            method = str(p.get("extraction_method") or ("ocr" if p.get("is_ocr") else "text"))
            records.append(
                PageRecord(
                    filename=filename,
                    document_id=doc_id,
                    file_type=file_type,
                    page_number=p_num,
                    text=p_text,
                    sheet_name=sheet_name,
                    extraction_method=method,
                    ocr_confidence=p.get("ocr_confidence"),
                    unreadable_reason=p.get("unreadable_reason"),
                )
            )
    return records


GROUP_KEYWORDS: Dict[str, List[str]] = {
    "basic": BASIC_KEYWORDS,
    "financial": FINANCIAL_KEYWORDS,
    "dates": DATE_KEYWORDS,
    "additional": SUMMARY_ELIGIBILITY_KEYWORDS,
}

FIELD_SPECIFIC_KEYWORDS: Dict[str, List[str]] = {
    "bid_title": ["name of work", "title", "tender for", "e-tender for", "nit", "rfp", "procurement of", "subject"],
    "department_organization": ["department", "organization", "organisation", "invited by", "issued by", "authority", "corporation", "board", "limited"],
    "state": ["state", "west bengal", "maharashtra", "karnataka", "delhi", "gujarat", "rajasthan", "tamil nadu", "uttar pradesh", "telangana", "kerala", "punjab", "haryana", "bihar", "odisha", "assam"],
    "customer_name": ["customer", "contact person", "nodal officer", "tendering authority", "client", "office of"],
    "customer_phone": ["phone", "tel", "mobile", "contact no", "helpline", "fax"],
    "customer_address": ["address", "pin", "street", "floor", "sector", "road", "block", "kolkata", "mumbai", "delhi"],
    "category": ["category", "work type", "goods", "services", "works", "consultancy", "hardware", "software", "civil", "electrical"],
    "tender_portal_url": ["http", "https", "www.", "portal", "eprocure", "wbtenders", "gem.gov", "etender"],
    "tender_id": ["tender id", "tender no", "nit no", "ref. no", "reference no", "bid no", "rfp no"],
    "estimated_tender_value": ["estimated cost", "estimated value", "tender value", "put to tender", "project cost", "cost of work", "boq", "grand total"],
    "bid_emd_value": ["emd", "earnest money", "bid security"],
    "tender_publication_date": ["publish", "publication", "released", "nit date", "date of issue"],
    "document_download_start": ["download start", "sale start", "document start"],
    "document_download_end": ["download end", "sale end", "document end", "last date of download"],
    "prebid_query_start": ["query start", "clarification start", "pre-bid query start"],
    "prebid_query_end": ["query end", "clarification end", "last date for queries", "queries reaching"],
    "prebid_meeting_date": ["pre-bid meeting", "prebid meeting", "pre bid meeting", "conference"],
    "prebid_response_date": ["response", "reply to queries", "clarification upload"],
    "bid_submission_start": ["submission start", "start date of submission", "uploading start"],
    "bid_submission_end": ["submission end", "last date", "closing date", "due date", "deadline"],
    "pq_bid_opening_date": ["pq", "pre-qualification", "pre qualification"],
    "technical_bid_opening_date": ["technical bid opening", "opening of technical", "technical opening"],
    "financial_bid_opening_date": ["financial bid opening", "price bid opening", "commercial opening"],
    "keywords_for_summary": ["scope", "objective", "deliverables", "eligibility", "corrigendum"],
}


def compute_bundle_signature(documents: List[Dict[str, Any]]) -> str:
    """Stable SHA-256 signature over a bundle of documents (file hashes + text lengths + names)."""
    h = hashlib.sha256()
    for doc in documents:
        doc_hash = str(doc.get("file_hash") or "")
        fname = str(doc.get("filename") or doc.get("original_filename") or "")
        doc_id = str(doc.get("document_id") or "")
        if doc_hash:
            part = f"{fname}|{doc_hash}"
        else:
            pages = doc.get("pages") or []
            p_text_concat = "\n".join(str(p.get("text") or "") for p in pages)
            if not p_text_concat:
                p_text_concat = str(doc.get("extracted_text") or "")
            t_digest = hashlib.sha256(p_text_concat.encode("utf-8", errors="ignore")).hexdigest()[:16]
            part = f"{fname}|{doc_id}|{len(pages)}:{t_digest}"
        h.update(part.encode("utf-8", errors="ignore"))
        h.update(b"\n")
    return h.hexdigest()


class TenderDocumentIndex:
    """In-memory inverted term + group index over every page/sheet across all tender files."""

    def __init__(self, signature: str, records: List[PageRecord]) -> None:
        self.signature = signature
        self.records = records
        self.lower_texts: List[str] = []
        self.lines_per_page: List[List[str]] = []
        self.term_to_pages: Dict[str, List[int]] = defaultdict(list)
        self.group_scores: Dict[str, List[float]] = {g: [] for g in GROUP_KEYWORDS}

        for idx, rec in enumerate(records):
            txt = rec.text or ""
            txt_l = txt.lower()
            self.lower_texts.append(txt_l)
            self.lines_per_page.append(txt.splitlines())

            seen_terms: Set[str] = set(re.findall(r"[a-z0-9]{3,}", txt_l))
            for term in seen_terms:
                self.term_to_pages[term].append(idx)

            for group_name, kws in GROUP_KEYWORDS.items():
                self.group_scores[group_name].append(_score_page_text(rec, txt_l, kws))

    def candidate_pages_for_terms(self, terms: List[str]) -> Set[int]:
        hits: Set[int] = set()
        for t in terms:
            for tok in re.findall(r"[a-z0-9]{3,}", t.lower()):
                hits.update(self.term_to_pages.get(tok, ()))
        return hits

    def extract_focused_snippets(
        self,
        keywords: List[str],
        candidate_indices: Optional[List[int]] = None,
        max_chars: int = 1600,
        max_lines_per_page: int = 10,
    ) -> str:
        """Extracts high-signal lines (+1 neighbor line) across indexed pages without blind slicing."""
        if not self.records:
            return ""
        indices = candidate_indices if candidate_indices is not None else list(range(len(self.records)))
        kw_lower = [k.lower() for k in keywords if k]
        blocks: List[str] = []
        used = 0

        for idx in indices:
            rec = self.records[idx]
            lines = self.lines_per_page[idx]
            if not lines:
                continue
            matched_line_nums: List[int] = []
            for li, raw_line in enumerate(lines):
                ll = raw_line.lower()
                if any(kw in ll for kw in kw_lower):
                    matched_line_nums.append(li)
                    if li + 1 < len(lines) and lines[li + 1].strip():
                        matched_line_nums.append(li + 1)

            if not matched_line_nums:
                # For page 1 of a file, include top summary lines cleanly
                if rec.page_number <= 1:
                    chosen_lines = [ln.strip() for ln in lines[:8] if ln.strip()]
                else:
                    continue
            else:
                unique_nums = sorted(set(matched_line_nums))[:max_lines_per_page]
                chosen_lines = [lines[n].strip() for n in unique_nums if lines[n].strip()]

            if not chosen_lines:
                continue
            header = f"\n=== SOURCE: {rec.location_label()} ===\n"
            body = "\n".join(chosen_lines)
            budget = max_chars - used - len(header)
            if budget <= 120:
                break
            block = header + body[:budget]
            blocks.append(block)
            used += len(block)
            if used >= max_chars:
                break

        return "\n".join(blocks).strip()

    def retrieve_for_groups(
        self,
        missing_fields: List[str],
        max_chars: int = 1550,
    ) -> str:
        """Builds one compact, multi-group context targeted ONLY at missing/uncertain fields."""
        if not self.records:
            return ""
        # Collect keywords for the missing fields across all 4 groups
        target_kws: List[str] = []
        target_groups: Set[str] = set()
        for f in missing_fields:
            target_kws.extend(FIELD_SPECIFIC_KEYWORDS.get(f, []))
            if f in {"estimated_tender_value", "bid_emd_value"}:
                target_groups.add("financial")
            elif f.endswith("_date") or f.endswith("_start") or f.endswith("_end"):
                target_groups.add("dates")
            elif f == "keywords_for_summary":
                target_groups.add("additional")
            else:
                target_groups.add("basic")
        if not target_groups:
            target_groups.add("additional")
        for g in target_groups:
            target_kws.extend(GROUP_KEYWORDS[g][:8])

        # Rank pages by combined score over requested groups + page 1 per file
        scored: List[Tuple[float, int]] = []
        first_seen: Set[str] = set()
        for idx, rec in enumerate(self.records):
            sc = sum(self.group_scores[g][idx] for g in target_groups)
            if rec.filename not in first_seen and rec.text.strip():
                first_seen.add(rec.filename)
                sc += 5.0
            if sc > 0:
                scored.append((sc, idx))

        scored.sort(key=lambda item: (-item[0], item[1]))
        top_indices = sorted(idx for _, idx in scored[:8])
        if not top_indices:
            top_indices = list(range(min(4, len(self.records))))

        return self.extract_focused_snippets(target_kws, candidate_indices=top_indices, max_chars=max_chars)


_INDEX_CACHE_LOCK = threading.Lock()
_INDEX_CACHE: "OrderedDict[str, TenderDocumentIndex]" = OrderedDict()
_MAX_INDEX_CACHE = 48


def get_or_build_index(documents: List[Dict[str, Any]]) -> Tuple[TenderDocumentIndex, bool]:
    """Returns a cached TenderDocumentIndex for documents, or builds & caches one."""
    sig = compute_bundle_signature(documents)
    with _INDEX_CACHE_LOCK:
        cached = _INDEX_CACHE.get(sig)
        if cached is not None:
            _INDEX_CACHE.move_to_end(sig)
            return cached, True

    records = collect_page_records(documents)
    index = TenderDocumentIndex(signature=sig, records=records)
    with _INDEX_CACHE_LOCK:
        _INDEX_CACHE[sig] = index
        while len(_INDEX_CACHE) > _MAX_INDEX_CACHE:
            _INDEX_CACHE.popitem(last=False)
    return index, False


def invalidate_index_cache() -> None:
    """Clears the cached document index entries (useful in tests or file changes)."""
    with _INDEX_CACHE_LOCK:
        _INDEX_CACHE.clear()


def _score_page_text(record: PageRecord, text_lower: str, keywords: List[str], bonus_first_pages: bool = True) -> float:
    if not text_lower.strip():
        return 0.0

    score = 0.0
    for kw in keywords:
        if kw in text_lower:
            score += min(3, text_lower.count(kw)) * (1.8 if " " in kw else 1.0)

    if "corrigendum" in text_lower or "addendum" in text_lower or "corrigendum" in record.filename.lower():
        score += 4.5
    if "boq" in record.filename.lower() or "sheet" in (record.sheet_name or "").lower():
        score += 2.0
    if "date and time schedule" in text_lower or "critical dates" in text_lower or "key dates" in text_lower:
        score += 6.0
    if bonus_first_pages and record.page_number <= 3:
        score += max(0.0, 4.0 - record.page_number)

    return score


def _score_page(record: PageRecord, keywords: List[str], bonus_first_pages: bool = True) -> float:
    return _score_page_text(record, (record.text or "").lower(), keywords, bonus_first_pages=bonus_first_pages)


def select_high_signal_pages(
    records: List[PageRecord],
    keywords: List[str],
    max_pages: int = 10,
    always_include_first_per_file: bool = True,
) -> List[PageRecord]:
    """Ranks all pages/sheets across all files and returns highest-signal slices."""
    if not records:
        return []

    scored: List[Tuple[float, int, PageRecord]] = []
    first_pages_seen: set = set()
    selected_indices: List[int] = []

    for idx, rec in enumerate(records):
        if always_include_first_per_file and rec.filename not in first_pages_seen and rec.text.strip():
            first_pages_seen.add(rec.filename)
            selected_indices.append(idx)
        score = _score_page(rec, keywords)
        scored.append((score, idx, rec))

    scored.sort(key=lambda item: (-item[0], item[1]))
    for score, idx, _rec in scored:
        if len(selected_indices) >= max_pages:
            break
        if idx not in selected_indices and (score > 0 or len(selected_indices) < 3):
            selected_indices.append(idx)

    # Return in reading order for coherent LLM reasoning
    selected_indices = sorted(set(selected_indices))[:max_pages]
    return [records[i] for i in selected_indices]


def format_pages_for_prompt(pages: List[PageRecord], max_chars: int = 8500) -> str:
    """Formats selected pages into a bounded, page-cited prompt context."""
    parts: List[str] = []
    used = 0
    for rec in pages:
        txt = (rec.text or "").strip()
        if not txt:
            continue
        header = f"\n=== SOURCE: {rec.location_label()} ===\n"
        budget = max_chars - used - len(header)
        if budget <= 180:
            break
        slice_txt = txt[:budget]
        block = header + slice_txt
        parts.append(block)
        used += len(block)
    return "\n".join(parts).strip()


def retrieve_evidence_for_query(
    records: Any,
    query: str,
    max_pages: int = 5,
    max_chars: int = 2600,
) -> Tuple[str, List[Dict[str, Any]]]:
    """Retrieves the most relevant pages/sheets across the entire tender for follow-up QA."""
    if isinstance(records, TenderDocumentIndex):
        page_records = records.records
        lower_texts = records.lower_texts
    else:
        page_records = list(records or [])
        lower_texts = [(r.text or "").lower() for r in page_records]

    q_lower = (query or "").lower()
    query_tokens = [
        t for t in re.findall(r"[a-z0-9\-/]{3,}", q_lower)
        if t not in {"what", "when", "where", "which", "this", "that", "with", "from", "about", "does", "have", "please", "explain", "tell", "tender", "document"}
    ]

    # Expand synonyms for common tender follow-ups
    synonyms = list(query_tokens)
    if any(w in q_lower for w in ["emd", "earnest", "deposit", "fee", "cost", "value", "amount", "financial"]):
        synonyms.extend(["emd", "earnest money", "bid security", "estimated", "tender fee", "security deposit", "rs.", "lakh", "crore"])
    if any(w in q_lower for w in ["deadline", "last date", "submission", "closing", "opening", "pre-bid", "prebid", "schedule", "date", "when"]):
        synonyms.extend(["submission", "last date", "closing", "opening", "pre-bid", "date", "schedule", "critical dates"])
    if any(w in q_lower for w in ["eligib", "qualif", "criteria", "turnover", "experience", "similar work", "pre-qualification", "pq"]):
        synonyms.extend(["eligibility", "pre-qualification", "turnover", "similar work", "experience", "bidder", "oem"])
    if any(w in q_lower for w in ["section", "clause", "scope", "summary", "explain", "overview", "requirement"]):
        synonyms.extend(["section", "clause", "scope", "specification", "general", "instruction"])

    # Exact section/clause reference match (e.g. "Section 4", "Section C", "Clause 3.2")
    section_refs = re.findall(r"(?:section|clause|annexure)\s+[a-z0-9.\-]+", q_lower)
    synonyms.extend(section_refs)

    scored: List[Tuple[float, int, PageRecord]] = []
    for idx, rec in enumerate(page_records):
        text_lower = lower_texts[idx]
        if not text_lower.strip():
            continue
        score = 0.0
        for tok in set(synonyms):
            if tok in text_lower:
                score += (5.0 if tok in section_refs else (2.5 if tok in query_tokens else 1.2)) * min(3, text_lower.count(tok))
        # Prefer actual table/body matches over TOC if both match
        if "table of contents" in text_lower and len(text_lower) < 1200:
            score *= 0.6
        scored.append((score, idx, rec))

    scored.sort(key=lambda item: (-item[0], item[1]))
    top = [rec for sc, _i, rec in scored[:max_pages] if sc > 0]
    if not top:
        top = [r for r in page_records if r.text.strip()][:max_pages]

    context_text = format_pages_for_prompt(top, max_chars=max_chars)
    sources = [
        {
            "filename": r.filename,
            "page_number": r.page_number,
            "sheet_name": r.sheet_name,
            "label": r.location_label(),
        }
        for r in top
    ]
    return context_text, sources

