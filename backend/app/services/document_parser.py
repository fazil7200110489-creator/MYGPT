"""Document Parser Service for extracting text, tables, and page metadata across file formats."""

import copy
import csv
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    import docx
except ImportError:
    docx = None

try:
    import openpyxl
except ImportError:
    openpyxl = None

try:
    from pptx import Presentation
except ImportError:
    Presentation = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

from .ocr_service import ocr_service

BINARY_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".xlsm", ".pptx", ".ppt",
    ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp", ".gif",
}
_PARSE_CACHE_VERSION = "v2"
_PARSE_CACHE_DIR = os.path.join("data", "cache", "parsed")


class DocumentParser:
    """Parses uploaded files and extracts normalized text, tables, sheets, and page metadata."""

    def __init__(self) -> None:
        self._parse_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._cache_lock = threading.Lock()
        self._max_mem_cache = 64

    @staticmethod
    def compute_file_hash(filepath: str) -> str:
        """Computes streaming SHA-256 content hash for reliable cache keying/invalidation."""
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def _get_cached_parse(self, file_hash: str) -> Optional[Dict[str, Any]]:
        cache_key = f"{_PARSE_CACHE_VERSION}:{file_hash}"
        with self._cache_lock:
            cached = self._parse_cache.get(cache_key)
            if cached is not None:
                self._parse_cache.move_to_end(cache_key)
                out = copy.deepcopy(cached)
                out["cache_hit"] = "memory"
                return out

        disk_path = os.path.join(_PARSE_CACHE_DIR, f"{file_hash}.json")
        if os.path.exists(disk_path):
            try:
                with open(disk_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and data.get("_cache_version") == _PARSE_CACHE_VERSION:
                    with self._cache_lock:
                        self._parse_cache[cache_key] = copy.deepcopy(data)
                        while len(self._parse_cache) > self._max_mem_cache:
                            self._parse_cache.popitem(last=False)
                    data["cache_hit"] = "disk"
                    return data
            except Exception as e:
                logger.debug(f"Ignoring unreadable parse cache {disk_path}: {e}")
        return None

    def _store_cached_parse(self, file_hash: str, result: Dict[str, Any]) -> None:
        cache_key = f"{_PARSE_CACHE_VERSION}:{file_hash}"
        payload = copy.deepcopy(result)
        payload["_cache_version"] = _PARSE_CACHE_VERSION
        with self._cache_lock:
            self._parse_cache[cache_key] = copy.deepcopy(payload)
            self._parse_cache.move_to_end(cache_key)
            while len(self._parse_cache) > self._max_mem_cache:
                self._parse_cache.popitem(last=False)
        try:
            os.makedirs(_PARSE_CACHE_DIR, exist_ok=True)
            disk_path = os.path.join(_PARSE_CACHE_DIR, f"{file_hash}.json")
            with open(disk_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
        except Exception as e:
            logger.debug(f"Could not persist parse cache {file_hash}: {e}")

    def detect_file_type(self, filepath: str) -> str:
        _, ext = os.path.splitext(filepath)
        return ext.lower()

    def clean_text(self, text: str) -> str:
        if not text:
            return ""
        text = re.sub(r"[ \t]+", " ", text)
        text = text.replace("\r\n", "\n")
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def normalize_text(self, text: str) -> str:
        """Normalizes unicode, removes immediate duplicate words/lines, and collapses punctuation."""
        if not text:
            return ""

        replacements = [
            ("\u2018", "'"), ("\u2019", "'"), ("\u201c", '"'), ("\u201d", '"'),
            ("\u2013", "-"), ("\u2014", "-"), ("\u00a0", " "),
            ("\u2022", "-"), ("\u25cf", "-"), ("\u25e6", "-"), ("\u2023", "-"),
        ]
        for old, new in replacements:
            text = text.replace(old, new)

        text = re.sub(r"\b([A-Za-z]{3,})\1\b", r"\1", text)
        prev = None
        while prev != text:
            prev = text
            text = re.sub(r"\b(\w+)\s+\1\b", r"\1", text, flags=re.IGNORECASE)

        blocks = text.split("\n\n")
        cleaned_blocks = []
        for block in blocks:
            lines = block.split("\n")
            seen_lines: set = set()
            unique_lines = []
            for line in lines:
                stripped = line.strip().lower()
                if stripped and stripped not in seen_lines:
                    seen_lines.add(stripped)
                    unique_lines.append(line)
                elif not stripped:
                    unique_lines.append(line)
            cleaned_blocks.append("\n".join(unique_lines))
        text = "\n\n".join(cleaned_blocks)

        text = re.sub(r"\.{2,}", ".", text)
        text = re.sub(r",{2,}", ",", text)
        text = re.sub(r";{2,}", ";", text)
        text = re.sub(r"!{2,}", "!", text)
        text = re.sub(r"\?{2,}", "?", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def parse(self, filepath: str, file_hash: Optional[str] = None) -> Dict[str, Any]:
        """Extracts text and structured page/sheet/OCR metadata from a document with hash caching."""
        import time

        t_parse_start = time.time()
        logger.info("PARSING START")
        logger.info(f"Parsing document: {filepath}")
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Document file not found: {filepath}")

        try:
            computed_hash = file_hash or self.compute_file_hash(filepath)
        except Exception:
            computed_hash = ""

        if computed_hash:
            cached = self._get_cached_parse(computed_hash)
            if cached is not None:
                cached_ms = round((time.time() - t_parse_start) * 1000, 2)
                cached.setdefault("stage_timings", {})
                cached["stage_timings"]["total_parse_ms"] = cached_ms
                logger.info(
                    f"[PARSE_CACHE_HIT] source={cached.get('cache_hit')} hash={computed_hash[:12]} "
                    f"pages={cached.get('total_pages')} latency={cached_ms:.2f}ms"
                )
                return cached

        ext = self.detect_file_type(filepath)
        raw_text = ""
        pages: List[Dict[str, Any]] = []
        ocr_engine: Optional[str] = None
        sub_timings: Dict[str, float] = {}

        try:
            if ext == ".pdf":
                raw_text, pages, ocr_engine, pdf_timings = self._parse_pdf(filepath)
                sub_timings.update(pdf_timings)
            elif ext == ".docx":
                raw_text, pages = self._parse_docx(filepath)
            elif ext == ".doc":
                raw_text, pages = self._parse_legacy_doc(filepath)
            elif ext in [
                ".txt", ".md", ".markdown", ".php", ".py", ".js", ".ts",
                ".jsx", ".tsx", ".java", ".cs", ".cpp", ".c", ".sql", ".css", ".yaml", ".yml",
            ]:
                raw_text, pages = self._parse_txt(filepath)
            elif ext == ".csv":
                raw_text, pages = self._parse_csv(filepath)
            elif ext in [".xlsx", ".xlsm"]:
                raw_text, pages = self._parse_excel(filepath)
            elif ext == ".xls":
                raw_text, pages = self._parse_legacy_xls(filepath)
            elif ext in [".pptx", ".ppt"]:
                raw_text, pages = self._parse_powerpoint(filepath)
            elif ext == ".json":
                raw_text, pages = self._parse_json(filepath)
            elif ext in [".html", ".htm"]:
                raw_text, pages = self._parse_html(filepath)
            elif ext == ".xml":
                raw_text, pages = self._parse_xml(filepath)
            elif ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp", ".gif", ".svg"]:
                logger.info("OCR START")
                ocr_res = ocr_service.ocr_image_detailed(filepath, allow_vision_fallback=False)
                ocr_engine = ocr_res.get("engine")
                logger.info("OCR END")
                if ocr_res.get("ok") and ocr_res.get("text"):
                    raw_text = ocr_res["text"]
                    pages = [{
                        "page_number": 1,
                        "text": raw_text,
                        "is_ocr": True,
                        "ocr_confidence": ocr_res.get("confidence", 0.0),
                        "extraction_method": f"ocr:{ocr_engine}",
                        "unreadable_reason": None,
                    }]
                else:
                    raw_text = f"Visual image attachment: {os.path.basename(filepath)}"
                    pages = [{
                        "page_number": 1,
                        "text": raw_text,
                        "is_ocr": True,
                        "ocr_confidence": 0.0,
                        "extraction_method": "ocr_failed",
                        "unreadable_reason": ocr_res.get("error") or "OCR failed to extract readable text from image.",
                    }]
            else:
                logger.warning(f"Unsupported file type '{ext}', attempting plain text fallback.")
                raw_text, pages = self._parse_txt(filepath)
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error parsing file {filepath} with extension {ext}: {e}")
            if ext in BINARY_EXTENSIONS:
                raise ValueError(f"Failed to parse {ext} file '{os.path.basename(filepath)}': {e}") from e
            raw_text, pages = self._parse_txt(filepath)

        t_clean_start = time.time()
        cleaned_pages: List[Dict[str, Any]] = []
        ocr_pages: List[int] = []
        unreadable_pages: List[int] = []
        sheets: List[str] = []

        for idx, p in enumerate(pages, start=1):
            p_num = int(p.get("page_number") or idx)
            p_clean = self.normalize_text(self.clean_text(p.get("text") or ""))
            entry: Dict[str, Any] = {
                "page_number": p_num,
                "text": p_clean,
                "extraction_method": p.get("extraction_method") or "text",
                "is_ocr": bool(p.get("is_ocr", False)),
            }
            if p.get("sheet_name"):
                entry["sheet_name"] = p["sheet_name"]
                if p["sheet_name"] not in sheets:
                    sheets.append(p["sheet_name"])
            if p.get("ocr_confidence") is not None:
                entry["ocr_confidence"] = p["ocr_confidence"]
            if p.get("unreadable_reason"):
                entry["unreadable_reason"] = p["unreadable_reason"]
                unreadable_pages.append(p_num)
            if entry["is_ocr"] and not p.get("unreadable_reason"):
                ocr_pages.append(p_num)
            cleaned_pages.append(entry)

        if cleaned_pages:
            if any(p.get("sheet_name") for p in cleaned_pages):
                cleaned_text = "\n\n".join(
                    f"=== Sheet: {p['sheet_name']} ===\n{p['text']}" if p.get("sheet_name") else p["text"]
                    for p in cleaned_pages if p.get("text")
                ).strip()
            else:
                cleaned_text = "\n\n".join(
                    f"--- Page {p['page_number']} ---\n{p['text']}"
                    for p in cleaned_pages if p.get("text")
                ).strip()
            if not cleaned_text and raw_text:
                cleaned_text = self.normalize_text(self.clean_text(raw_text))
        else:
            cleaned_text = self.normalize_text(self.clean_text(raw_text))

        if ext in [".pdf", ".docx", ".doc"]:
            words = cleaned_text.split()
            if len(words) < 2 or cleaned_text.strip().lower() == "ocr_failed" or "no readable text" in cleaned_text.lower():
                logger.error(f"Validation failed: text too short ({len(words)} words) or invalid.")
                raise ValueError("Unable to extract readable text from the uploaded document.")

        t_clean_ms = round((time.time() - t_clean_start) * 1000, 2)
        t_parse_total = time.time() - t_parse_start
        sub_timings["clean_ms"] = t_clean_ms
        sub_timings["total_parse_ms"] = round(t_parse_total * 1000, 2)
        logger.info("PARSING END")
        logger.info(
            f"TOTAL LATENCY (parse): {t_parse_total * 1000:.2f} ms "
            f"(clean={t_clean_ms:.1f}ms, details={sub_timings})"
        )

        result = {
            "text": cleaned_text,
            "pages": cleaned_pages,
            "file_type": ext,
            "file_hash": computed_hash,
            "total_pages": len(cleaned_pages),
            "ocr_pages": ocr_pages,
            "unreadable_pages": unreadable_pages,
            "sheets": sheets,
            "ocr_engine": ocr_engine,
            "cache_hit": None,
            "stage_timings": sub_timings,
        }
        if computed_hash:
            self._store_cached_parse(computed_hash, result)
        return result

    def _format_fitz_tables(self, page: Any) -> str:
        """Extracts structured table rows from a PyMuPDF page cleanly."""
        if not hasattr(page, "find_tables"):
            return ""
        try:
            tf = page.find_tables()
            tables = getattr(tf, "tables", None) or []
        except Exception:
            return ""

        formatted_tables: List[str] = []
        for t_idx, table in enumerate(tables, start=1):
            try:
                rows = table.extract() or []
            except Exception:
                continue
            row_lines: List[str] = []
            for row in rows:
                cells = [re.sub(r"\s+", " ", str(c or "")).strip() for c in row]
                if any(cells):
                    row_lines.append(" | ".join(cells))
            if row_lines:
                formatted_tables.append(f"[Table {t_idx}]\n" + "\n".join(row_lines))
        return "\n\n".join(formatted_tables)

    def _parse_pdf(self, filepath: str) -> Tuple[str, List[Dict[str, Any]], Optional[str], Dict[str, Any]]:
        """Parses text, tables, and mixed scanned pages from a PDF preserving page numbers."""
        pages: List[Dict[str, Any]] = []
        ocr_needed_pages: List[int] = []
        ocr_engine: Optional[str] = None
        timings: Dict[str, Any] = {
            "pdf_text_ms": 0.0,
            "pdf_table_ms": 0.0,
            "ocr_ms": 0.0,
            "table_pages_scanned": 0,
        }

        if fitz is not None:
            doc = fitz.open(filepath)
            try:
                num_pages = len(doc)
                table_pages_scanned = 0
                for idx, page in enumerate(doc, start=1):
                    t_txt_start = time.time()
                    native_text = (page.get_text("text") or "").strip()
                    timings["pdf_text_ms"] += (time.time() - t_txt_start) * 1000.0
                    nt_lower = native_text.lower()

                    if num_pages <= 10:
                        should_check_tables = len(page.get_drawings()) >= 4
                    else:
                        has_schedule_signal = (
                            idx <= 2
                            or any(k in nt_lower for k in (
                                "critical date", "important date", "date and time",
                                "bid submission", "tender schedule", "corrigendum",
                                "addendum", "estimated cost", "earnest money",
                            ))
                        )
                        should_check_tables = (
                            has_schedule_signal
                            and table_pages_scanned < 4
                            and len(page.get_drawings()) >= 8
                        )

                    table_text = ""
                    if should_check_tables:
                        t_tbl_start = time.time()
                        table_text = self._format_fitz_tables(page)
                        timings["pdf_table_ms"] += (time.time() - t_tbl_start) * 1000.0
                        table_pages_scanned += 1

                    combined = native_text
                    if table_text and len(table_text) > 10:
                        combined = f"{native_text}\n\n{table_text}".strip() if native_text else table_text

                    compact_len = len(re.sub(r"\s+", "", native_text))
                    has_images = len(page.get_images()) > 0
                    pages.append({
                        "page_number": idx,
                        "text": combined,
                        "is_ocr": False,
                        "extraction_method": "pymupdf_text_table" if table_text else "pymupdf_text",
                    })
                    # Trigger per-page OCR on scanned/image-only pages (or mixed image pages with minimal text)
                    if (compact_len < 30 and (has_images or num_pages <= 45)) or (has_images and compact_len < 150):
                        ocr_needed_pages.append(idx)
                timings["table_pages_scanned"] = table_pages_scanned
            finally:
                doc.close()
        elif PdfReader is not None:
            t_txt_start = time.time()
            reader = PdfReader(filepath)
            for idx, page in enumerate(reader.pages, start=1):
                txt = (page.extract_text() or "").strip()
                pages.append({
                    "page_number": idx,
                    "text": txt,
                    "is_ocr": False,
                    "extraction_method": "pypdf_text",
                })
                if len(re.sub(r"\s+", "", txt)) < 30:
                    ocr_needed_pages.append(idx)
            timings["pdf_text_ms"] = (time.time() - t_txt_start) * 1000.0
        else:
            raise RuntimeError("Neither PyMuPDF nor pypdf is installed.")

        if ocr_needed_pages:
            t_ocr_start = time.time()
            logger.info(
                f"OCR START: Dispatching {len(ocr_needed_pages)} low-text/scanned PDF pages "
                f"for {os.path.basename(filepath)} ({ocr_needed_pages[:15]})"
            )
            ocr_results = ocr_service.extract_pages_from_scanned_pdf(filepath, page_numbers=ocr_needed_pages)
            timings["ocr_ms"] = round((time.time() - t_ocr_start) * 1000.0, 2)
            logger.info(f"OCR END ({timings['ocr_ms']:.2f}ms)")
            by_page = {r["page_number"]: r for r in ocr_results}
            for entry in pages:
                p_num = entry["page_number"]
                if p_num not in by_page:
                    continue
                ocr_res = by_page[p_num]
                ocr_engine = ocr_res.get("engine") or ocr_engine
                ocr_txt = (ocr_res.get("text") or "").strip()
                if ocr_txt:
                    existing = (entry.get("text") or "").strip()
                    entry["text"] = f"{existing}\n{ocr_txt}".strip() if existing else ocr_txt
                    entry["is_ocr"] = True
                    entry["ocr_confidence"] = ocr_res.get("ocr_confidence")
                    entry["extraction_method"] = f"ocr:{ocr_res.get('engine')}"
                elif not (entry.get("text") or "").strip():
                    entry["is_ocr"] = True
                    entry["ocr_confidence"] = 0.0
                    entry["extraction_method"] = "ocr_failed"
                    entry["unreadable_reason"] = ocr_res.get("unreadable_reason") or "Page image produced no OCR text."

        timings["pdf_text_ms"] = round(timings["pdf_text_ms"], 2)
        timings["pdf_table_ms"] = round(timings["pdf_table_ms"], 2)

        full_parts: List[str] = []
        for entry in pages:
            p_txt = (entry.get("text") or "").strip()
            if p_txt:
                full_parts.append(f"--- Page {entry['page_number']} ---\n{p_txt}")

        return "\n\n".join(full_parts), pages, ocr_engine, timings

    def _extract_docx_table_lines(self, table: Any, depth: int = 0) -> List[str]:
        """Recursively extracts labeled rows from a DOCX table including nested tables."""
        lines: List[str] = []
        headers: List[str] = []
        for row_idx, row in enumerate(table.rows):
            cell_texts: List[str] = []
            nested_lines: List[str] = []
            for cell in row.cells:
                c_txt = re.sub(r"\s+", " ", cell.text or "").strip()
                cell_texts.append(c_txt)
                if depth < 2 and getattr(cell, "tables", None):
                    for nt in cell.tables:
                        nested_lines.extend(self._extract_docx_table_lines(nt, depth=depth + 1))

            if row_idx == 0 and sum(1 for c in cell_texts if c) >= 2:
                headers = cell_texts
                lines.append(" | ".join(headers))
            elif headers and len(cell_texts) == len(headers) and len(headers) >= 2:
                # If this is a 2-col Key | Value table, output both "Key: Value" clearly
                if len(cell_texts) == 2 and cell_texts[0] and cell_texts[1]:
                    lines.append(f"{cell_texts[0]}: {cell_texts[1]}")
                else:
                    labeled = [
                        f"{headers[j] or f'Col {j+1}'}: {val}"
                        for j, val in enumerate(cell_texts)
                        if val
                    ]
                    if labeled:
                        lines.append(" | ".join(labeled))
            else:
                non_empty = [c for c in cell_texts if c]
                if non_empty:
                    if len(non_empty) == 2:
                        lines.append(f"{non_empty[0]}: {non_empty[1]}")
                    else:
                        lines.append(" | ".join(non_empty))

            lines.extend(nested_lines)
        return lines

    def _parse_docx(self, filepath: str) -> Tuple[str, List[Dict[str, Any]]]:
        if docx is None:
            raise RuntimeError("python-docx is not installed.")
        doc = docx.Document(filepath)
        parts: List[str] = []

        # Extract headers & footers (tenders often place NIT / org / contact info here)
        header_footer_lines: List[str] = []
        for section in doc.sections:
            for block in (section.header, section.footer):
                for p in block.paragraphs:
                    t = p.text.strip()
                    if t and t not in header_footer_lines:
                        header_footer_lines.append(t)
                for tbl in block.tables:
                    header_footer_lines.extend(self._extract_docx_table_lines(tbl))
        if header_footer_lines:
            parts.append("[Header/Footer]\n" + "\n".join(header_footer_lines))

        # Walk body paragraphs & tables in reading order
        from docx.text.paragraph import Paragraph
        from docx.table import Table

        body_lines: List[str] = []
        for child in doc.element.body.iterchildren():
            tag = child.tag.rsplit("}", 1)[-1]
            if tag == "p":
                p = Paragraph(child, doc)
                t = p.text.strip()
                if t:
                    body_lines.append(t)
            elif tag == "tbl":
                tbl = Table(child, doc)
                t_lines = self._extract_docx_table_lines(tbl)
                if t_lines:
                    body_lines.append("\n".join(t_lines))

        if body_lines:
            parts.append("\n\n".join(body_lines))

        full_text = "\n\n".join(parts).strip()
        # Split long DOCX logically into ~3500-char virtual pages so page citations stay focused
        if len(full_text) <= 4000:
            return full_text, [{"page_number": 1, "text": full_text, "extraction_method": "docx"}]

        pages: List[Dict[str, Any]] = []
        chunk_buf: List[str] = []
        buf_len = 0
        page_num = 1
        for block in full_text.split("\n\n"):
            if buf_len + len(block) > 3500 and chunk_buf:
                pages.append({"page_number": page_num, "text": "\n\n".join(chunk_buf), "extraction_method": "docx"})
                page_num += 1
                chunk_buf = [block]
                buf_len = len(block)
            else:
                chunk_buf.append(block)
                buf_len += len(block)
        if chunk_buf:
            pages.append({"page_number": page_num, "text": "\n\n".join(chunk_buf), "extraction_method": "docx"})

        return full_text, pages

    def _parse_legacy_doc(self, filepath: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Handles legacy binary .doc files via LibreOffice/antiword if available, else fails explicitly."""
        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        if soffice:
            with tempfile.TemporaryDirectory() as tmpdir:
                proc = subprocess.run(
                    [soffice, "--headless", "--convert-to", "docx", "--outdir", tmpdir, filepath],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                base = os.path.splitext(os.path.basename(filepath))[0] + ".docx"
                converted = os.path.join(tmpdir, base)
                if proc.returncode == 0 and os.path.exists(converted):
                    return self._parse_docx(converted)

        antiword = shutil.which("antiword")
        if antiword:
            proc = subprocess.run([antiword, filepath], capture_output=True, text=True, timeout=20)
            if proc.returncode == 0 and proc.stdout.strip():
                txt = proc.stdout.strip()
                return txt, [{"page_number": 1, "text": txt, "extraction_method": "antiword"}]

        raise ValueError(
            "Legacy .doc binary format is not supported locally without LibreOffice (soffice) or antiword. "
            "Please save or convert the file to .docx or .pdf."
        )

    def _parse_txt(self, filepath: str) -> Tuple[str, List[Dict[str, Any]]]:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return content, [{"page_number": 1, "text": content, "extraction_method": "text"}]

    def _parse_csv(self, filepath: str) -> Tuple[str, List[Dict[str, Any]]]:
        rows = []
        headers: List[str] = []
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            for i, row in enumerate(reader):
                if i == 0:
                    headers = [h.strip() for h in row]
                    rows.append(" | ".join(headers))
                elif headers:
                    labeled = [
                        f"{headers[j] if j < len(headers) else f'Column {j+1}'}: {val.strip()}"
                        for j, val in enumerate(row)
                    ]
                    rows.append(f"[Row {i+1}] " + " | ".join(labeled))
                else:
                    rows.append(", ".join(row))
        full_text = "\n".join(rows)
        return full_text, [{"page_number": 1, "text": full_text, "sheet_name": "CSV", "extraction_method": "csv"}]

    def _detect_excel_header_row(self, non_empty_rows: List[Tuple[int, List[str]]]) -> Optional[int]:
        """Finds the true header row index inside non_empty_rows (handles title banner rows)."""
        for list_idx, (_orig_row, vals) in enumerate(non_empty_rows[:8]):
            non_blank = [v for v in vals if v.strip()]
            if len(non_blank) >= 3:
                # Prefer rows where at least half of non-blank cells are non-numeric labels
                alpha_cells = sum(1 for v in non_blank if re.search(r"[A-Za-z]", v))
                if alpha_cells >= 2:
                    return list_idx
        return None

    def _format_excel_sheet_rows(self, sheet_name: str, raw_rows: List[List[str]]) -> str:
        non_empty_rows: List[Tuple[int, List[str]]] = []
        for r_idx, row_vals in enumerate(raw_rows, start=1):
            if any(v.strip() for v in row_vals):
                non_empty_rows.append((r_idx, [v.strip() for v in row_vals]))

        if not non_empty_rows:
            return ""

        hdr_list_idx = self._detect_excel_header_row(non_empty_rows)
        headers: List[str] = []
        out_lines: List[str] = [f"Sheet: {sheet_name}"]

        for list_idx, (excel_row_num, vals) in enumerate(non_empty_rows):
            clean_non_empty = [v for v in vals if v]
            if hdr_list_idx is not None and list_idx == hdr_list_idx:
                headers = vals
                out_lines.append(f"[Row {excel_row_num} Header] " + " | ".join(h for h in headers if h))
            elif hdr_list_idx is not None and list_idx > hdr_list_idx and headers:
                if len(clean_non_empty) == 2 and all(len(v) > 0 for v in clean_non_empty):
                    out_lines.append(f"[Row {excel_row_num}] {clean_non_empty[0]}: {clean_non_empty[1]}")
                else:
                    labeled = [
                        f"{headers[j] if j < len(headers) and headers[j] else f'Column {j+1}'}: {val}"
                        for j, val in enumerate(vals)
                        if val
                    ]
                    if labeled:
                        out_lines.append(f"[Row {excel_row_num}] " + " | ".join(labeled))
            else:
                if len(clean_non_empty) == 2:
                    out_lines.append(f"[Row {excel_row_num}] {clean_non_empty[0]}: {clean_non_empty[1]}")
                else:
                    out_lines.append(f"[Row {excel_row_num}] " + " | ".join(clean_non_empty))

        return "\n".join(out_lines)

    def _parse_excel(self, filepath: str) -> Tuple[str, List[Dict[str, Any]]]:
        if openpyxl is None:
            raise RuntimeError("openpyxl is not installed.")
        wb = openpyxl.load_workbook(filepath, data_only=True)
        sheets_text: List[str] = []
        pages: List[Dict[str, Any]] = []

        for idx, name in enumerate(wb.sheetnames, start=1):
            sheet = wb[name]
            raw_rows = [
                [str(cell) if cell is not None else "" for cell in row]
                for row in sheet.iter_rows(values_only=True)
            ]
            sheet_txt = self._format_excel_sheet_rows(name, raw_rows)
            if sheet_txt:
                sheets_text.append(sheet_txt)
                pages.append({
                    "page_number": idx,
                    "sheet_name": name,
                    "text": sheet_txt,
                    "extraction_method": "openpyxl",
                })

        full_text = "\n\n".join(sheets_text)
        return full_text, pages or [{"page_number": 1, "text": full_text, "extraction_method": "openpyxl"}]

    def _parse_legacy_xls(self, filepath: str) -> Tuple[str, List[Dict[str, Any]]]:
        if importlib.util.find_spec("xlrd") is None:
            raise ValueError(
                "Legacy .xls binary format requires 'xlrd' package which is not installed. "
                "Please convert the spreadsheet to .xlsx or .csv."
            )
        import xlrd  # type: ignore

        wb = xlrd.open_workbook(filepath)
        sheets_text: List[str] = []
        pages: List[Dict[str, Any]] = []
        for idx, name in enumerate(wb.sheet_names(), start=1):
            sheet = wb.sheet_by_name(name)
            raw_rows = [
                [str(sheet.cell_value(r, c)) for c in range(sheet.ncols)]
                for r in range(sheet.nrows)
            ]
            sheet_txt = self._format_excel_sheet_rows(name, raw_rows)
            if sheet_txt:
                sheets_text.append(sheet_txt)
                pages.append({
                    "page_number": idx,
                    "sheet_name": name,
                    "text": sheet_txt,
                    "extraction_method": "xlrd",
                })
        full_text = "\n\n".join(sheets_text)
        return full_text, pages or [{"page_number": 1, "text": full_text, "extraction_method": "xlrd"}]

    def _parse_powerpoint(self, filepath: str) -> Tuple[str, List[Dict[str, Any]]]:
        prs = Presentation(filepath)
        slide_texts = []
        pages = []
        for idx, slide in enumerate(prs.slides, start=1):
            slide_parts = []
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    slide_parts.append(shape.text.strip())
            slide_text = "\n".join(slide_parts)
            slide_texts.append(slide_text)
            pages.append({"page_number": idx, "text": slide_text, "extraction_method": "pptx"})
        full_text = "\n\n--- Slide ---\n\n".join(slide_texts)
        return full_text, pages

    def _parse_json(self, filepath: str) -> Tuple[str, List[Dict[str, Any]]]:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
        full_text = json.dumps(data, indent=2)
        return full_text, [{"page_number": 1, "text": full_text, "extraction_method": "json"}]

    def _parse_html(self, filepath: str) -> Tuple[str, List[Dict[str, Any]]]:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            soup = BeautifulSoup(f, "html.parser")
        for element in soup(["script", "style"]):
            element.decompose()
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase for phrase in lines if phrase)
        full_text = "\n\n".join(chunks)
        return full_text, [{"page_number": 1, "text": full_text, "extraction_method": "html"}]

    def _parse_xml(self, filepath: str) -> Tuple[str, List[Dict[str, Any]]]:
        tree = ET.parse(filepath)
        root = tree.getroot()
        texts = [
            f"{elem.tag}: {elem.text.strip()}"
            for elem in root.iter()
            if elem.text and elem.text.strip()
        ]
        full_text = "\n".join(texts)
        return full_text, [{"page_number": 1, "text": full_text, "extraction_method": "xml"}]


document_parser = DocumentParser()
