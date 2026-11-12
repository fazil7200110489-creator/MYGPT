"""Validation, grounding verification, and conflict detection for extracted tender fields."""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from backend.app.services.tender.tender_schema import (
    ALL_TENDER_FIELD_NAMES,
    ADDITIONAL_FIELDS,
    BASIC_INFO_FIELDS,
    FIELD_DISPLAY_LABELS,
    FINANCIAL_FIELDS,
    IMPORTANT_DATE_FIELDS,
    TenderConflictAlternative,
    TenderFieldEvidence,
)
from backend.app.services.tender.tender_section_retriever import PageRecord

_INVALID_VALUES = {
    "",
    "n/a",
    "na",
    "none",
    "null",
    "nil",
    "not found",
    "not_found",
    "not available",
    "not specified",
    "unknown",
    "-",
    "--",
}


def field_section_for(field_name: str) -> str:
    if field_name in BASIC_INFO_FIELDS:
        return "basic_information"
    if field_name in FINANCIAL_FIELDS:
        return "financial_information"
    if field_name in IMPORTANT_DATE_FIELDS:
        return "important_dates"
    if field_name in ADDITIONAL_FIELDS:
        return "additional_information"
    return "basic_information"


def clean_candidate_value(val: Optional[str]) -> str:
    if not val:
        return ""
    cleaned = re.sub(r"\s+", " ", str(val)).strip(" \t\r\n:;,-|")
    if cleaned.lower() in _INVALID_VALUES:
        return ""
    return cleaned


def normalize_for_comparison(field_name: str, value: str) -> str:
    """Normalizes values so identical dates/amounts written slightly differently match cleanly."""
    v = (value or "").lower().strip()
    v = re.sub(r"\s+", " ", v)
    if field_name in FINANCIAL_FIELDS:
        v = v.replace("inr", "rs").replace("rs.", "rs").replace("/-", "").replace("₹", "rs")
        v = re.sub(r"\([^)]*\)", "", v)  # Ignore "(Rupees Five Lakh only)" parenthetical wording
        v = re.sub(r"[\s,]", "", v)
        return v
    if field_name in IMPORTANT_DATE_FIELDS:
        m = re.search(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})", v)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if y < 100:
                y += 2000
            return f"{y:04d}-{mo:02d}-{d:02d}"
        return re.sub(r"\s+", " ", v)
    if field_name == "tender_portal_url":
        return v.rstrip("/")
    return re.sub(r"[^a-z0-9]+", "", v)


def verify_value_in_records(
    field_name: str,
    value: str,
    records: List[PageRecord],
) -> Optional[Tuple[PageRecord, str]]:
    """Checks whether a proposed value is grounded in the parsed tender pages.

    Returns (PageRecord, matching_snippet) if grounded, else None.
    """
    cleaned = clean_candidate_value(value)
    if not cleaned:
        return None

    # Special derived fields that synthesize across text
    if field_name == "keywords_for_summary":
        words = [w.strip().lower() for w in re.split(r"[,;]+", cleaned) if len(w.strip()) >= 3]
        if not words:
            return None
        for rec in records:
            txt_l = rec.text.lower()
            hits = [w for w in words if w in txt_l]
            if hits:
                return rec, rec.text[:240]
        return None

    if field_name == "category":
        # Category can be inferred (e.g. "IT & CCTV Infrastructure") if tender text has core keywords
        tokens = [t.lower() for t in re.findall(r"[A-Za-z0-9]{3,}", cleaned)]
        if records:
            for rec in records:
                txt_l = rec.text.lower()
                if any(t in txt_l for t in tokens):
                    return rec, _extract_snippet_around(rec.text, tokens[0])
            return records[0], records[0].text[:200]
        return None

    target_norm = re.sub(r"\s+", " ", cleaned.lower())

    for rec in records:
        txt = rec.text or ""
        txt_norm = re.sub(r"\s+", " ", txt.lower())
        if target_norm in txt_norm:
            return rec, _extract_snippet_around(txt, cleaned[:40])

    # Token/digit grounding for formatted dates, amounts, and tender IDs
    digits = re.findall(r"\d{2,}", cleaned)
    if digits:
        for rec in records:
            txt = rec.text or ""
            txt_compact = re.sub(r"[,\s]+", "", txt.lower())
            cleaned_compact = re.sub(r"[,\s]+", "", cleaned.lower())
            if cleaned_compact in txt_compact:
                return rec, _extract_snippet_around(txt, digits[0])
            if field_name in IMPORTANT_DATE_FIELDS:
                date_nums = re.findall(r"\d{2}[-/]\d{2}[-/]\d{2,4}", cleaned)
                if date_nums and any(d in txt or d.replace("-", "/") in txt for d in date_nums):
                    return rec, _extract_snippet_around(txt, date_nums[0])

    # Multi-word title / organization grounding (>= 60% significant words match on same page)
    sig_words = [w.lower() for w in re.findall(r"[A-Za-z0-9]{3,}", cleaned)]
    if len(sig_words) >= 2:
        for rec in records:
            txt_l = (rec.text or "").lower()
            hits = sum(1 for w in sig_words if w in txt_l)
            if hits / len(sig_words) >= 0.6:
                return rec, _extract_snippet_around(rec.text, sig_words[0])

    return None


def _extract_snippet_around(text: str, needle: str, radius: int = 130) -> str:
    if not text:
        return ""
    idx = text.lower().find((needle or "").lower())
    if idx < 0:
        return re.sub(r"\s+", " ", text[: radius * 2]).strip()
    start = max(0, idx - radius)
    end = min(len(text), idx + len(needle) + radius)
    snippet = re.sub(r"\s+", " ", text[start:end]).strip()
    return snippet


def resolve_field_candidates(
    field_name: str,
    candidates: List[TenderFieldEvidence],
    unreadable_pages_count: int = 0,
    total_pages: int = 0,
) -> TenderFieldEvidence:
    """Selects primary field value and flags cross-page conflicts or corrigenda."""
    section = field_section_for(field_name)
    label = FIELD_DISPLAY_LABELS.get(field_name, field_name)

    valid = [c for c in candidates if clean_candidate_value(c.value)]
    if not valid:
        if total_pages > 0 and unreadable_pages_count == total_pages:
            return TenderFieldEvidence(
                field_name=field_name,
                label=label,
                section=section,  # type: ignore[arg-type]
                value="NOT_FOUND",
                confidence=0.0,
                status="UNREADABLE",
                notes="Document pages could not be read or OCR failed.",
            )
        return TenderFieldEvidence(
            field_name=field_name,
            label=label,
            section=section,  # type: ignore[arg-type]
            value="NOT_FOUND",
            confidence=0.0,
            status="NOT_FOUND",
        )

    # Group by normalized value to deduplicate identical sightings across pages
    grouped: Dict[str, List[TenderFieldEvidence]] = {}
    for cand in valid:
        norm_key = normalize_for_comparison(field_name, cand.value) or cand.value.lower()
        grouped.setdefault(norm_key, []).append(cand)

    # Merge substring duplicates for descriptive fields (keep fuller version)
    if field_name in ("bid_title", "customer_address", "department_organization", "customer_name", "bid_emd_value", "estimated_tender_value"):
        keys = sorted(grouped.keys(), key=len, reverse=True)
        merged_grouped: Dict[str, List[TenderFieldEvidence]] = {}
        for k in keys:
            parent = next((mk for mk in merged_grouped if len(k) >= 6 and k in mk), None)
            if parent:
                merged_grouped[parent].extend(grouped[k])
            else:
                merged_grouped[k] = grouped[k]
        grouped = merged_grouped

    distinct_best: List[TenderFieldEvidence] = []
    for norm_key, group in grouped.items():
        group.sort(
            key=lambda x: (
                1 if ("corrigendum" in (x.source_file or "").lower() or "corrigendum" in (x.notes or "").lower()) else 0,
                1 if (field_name in IMPORTANT_DATE_FIELDS and re.search(r"\b(am|pm|hrs|noon)\b", x.value, re.I)) else 0,
                x.confidence,
                len(x.value),
                -(x.source_page or 999),
            ),
            reverse=True,
        )
        distinct_best.append(group[0])

    # Sort distinct variants by authority: corrigendum > highest confidence > earliest page
    def _rank(ev: TenderFieldEvidence) -> Tuple[int, float, int]:
        is_corr = (
            "corrigendum" in (ev.source_file or "").lower()
            or "corrigendum" in (ev.notes or "").lower()
            or "corrigendum" in (ev.source_text or "").lower()
        )
        return (1 if is_corr else 0, ev.confidence, -(ev.source_page or 999))

    distinct_best.sort(key=_rank, reverse=True)
    primary = distinct_best[0].model_copy(deep=True)
    primary.label = label
    primary.section = section  # type: ignore[arg-type]

    if len(distinct_best) > 1:
        others = distinct_best[1:]
        alternatives = [
            TenderConflictAlternative(
                value=alt.value,
                source_file=alt.source_file,
                source_page=alt.source_page,
                source_sheet=alt.source_sheet,
                source_text=alt.source_text,
                reason=alt.notes or "Conflicting value found on another page/file",
            )
            for alt in others
        ]
        primary.alternatives = alternatives

        primary_is_corr = (
            "corrigendum" in (primary.source_file or "").lower()
            or "corrigendum" in (primary.notes or "").lower()
            or "corrigendum" in (primary.source_text or "").lower()
        )
        if primary_is_corr:
            primary.status = "NEEDS_REVIEW"
            primary.notes = "Updated via Corrigendum; previous value preserved in alternatives."
        else:
            primary.status = "AMBIGUOUS"
            primary.confidence = min(primary.confidence, 0.72)
            primary.notes = f"Multiple conflicting values found ({len(distinct_best)} variants)."
    else:
        if primary.status not in ("NEEDS_REVIEW", "AMBIGUOUS", "UNREADABLE"):
            primary.status = "VERIFIED" if primary.confidence >= 0.75 else "NEEDS_REVIEW"

    return primary


def _parse_date_loose(value: str) -> Optional[datetime]:
    if not value or value == "NOT_FOUND":
        return None
    m = re.search(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})", value)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000
        try:
            return datetime(y, mo, d)
        except ValueError:
            return None
    for fmt in ("%d %B %Y", "%d %b %Y", "%d-%b-%Y", "%d-%B-%Y"):
        m_txt = re.search(r"\d{1,2}[\s\-]+[A-Za-z]+[\s\-]+\d{4}", value)
        if m_txt:
            try:
                return datetime.strptime(m_txt.group(0).strip(), fmt)
            except ValueError:
                continue
    return None


def validate_date_chronology(important_dates: Dict[str, TenderFieldEvidence]) -> List[str]:
    """Produces non-fatal warnings if tender milestone dates contradict chronological order."""
    warnings: List[str] = []
    ordered_pairs = [
        ("tender_publication_date", "bid_submission_end"),
        ("document_download_start", "document_download_end"),
        ("prebid_query_start", "prebid_query_end"),
        ("bid_submission_start", "bid_submission_end"),
        ("bid_submission_end", "technical_bid_opening_date"),
        ("technical_bid_opening_date", "financial_bid_opening_date"),
    ]
    for earlier_key, later_key in ordered_pairs:
        ev1 = important_dates.get(earlier_key)
        ev2 = important_dates.get(later_key)
        if not ev1 or not ev2:
            continue
        dt1 = _parse_date_loose(ev1.value)
        dt2 = _parse_date_loose(ev2.value)
        if dt1 and dt2 and dt1 > dt2:
            warnings.append(
                f"Date order check: {FIELD_DISPLAY_LABELS.get(earlier_key, earlier_key)} ({ev1.value}) "
                f"appears later than {FIELD_DISPLAY_LABELS.get(later_key, later_key)} ({ev2.value})."
            )
    return warnings

