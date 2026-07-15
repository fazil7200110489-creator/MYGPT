"""Document Parser Service for extracting text from various file formats.
"""

import os
import csv
import json
import re
from typing import Dict, Any, List
from loguru import logger

# Import third-party parsers
from pypdf import PdfReader
import docx
import openpyxl
from pptx import Presentation
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

from .ocr_service import ocr_service


class DocumentParser:
    """Parses uploaded files and extracts text, normalizing contents."""

    def detect_file_type(self, filepath: str) -> str:
        """Determines the file extension in lowercase.
        
        Args:
            filepath: File path.
            
        Returns:
            Lowercase extension (e.g. '.pdf', '.docx').
        """
        _, ext = os.path.splitext(filepath)
        return ext.lower()

    def clean_text(self, text: str) -> str:
        """Normalizes text by collapsing spaces while preserving paragraphs.
        
        Args:
            text: Raw input text.
            
        Returns:
            Normalized clean text.
        """
        if not text:
            return ""
        # Replace multiple spaces with a single space
        text = re.sub(r"[ \t]+", " ", text)
        # Standardize newlines
        text = text.replace("\r\n", "\n")
        # Replace 3 or more consecutive newlines with exactly 2 newlines (paragraph separator)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def normalize_text(self, text: str) -> str:
        """Deep normalization: removes duplicate words, lines, punctuation runs, and fixes unicode.

        This runs AFTER clean_text() and is the final guard before indexing.

        Args:
            text: Clean text (output of clean_text).

        Returns:
            Fully normalized text safe for chunking and embedding.
        """
        if not text:
            return ""

        # 1. Normalize unicode smart-quotes, em-dashes, non-breaking spaces, and bullet variants
        replacements = [
            ("\u2018", "'"), ("\u2019", "'"), ("\u201c", '"'), ("\u201d", '"'),
            ("\u2013", "-"), ("\u2014", "-"), ("\u00a0", " "),
            ("\u2022", "-"), ("\u25cf", "-"), ("\u25e6", "-"), ("\u2023", "-"),
        ]
        for old, new in replacements:
            text = text.replace(old, new)

        # 2. Remove duplicate consecutive WORDS (e.g. "SummarySummary" or "Hello Hello")
        # First handle run-together duplicates like "SummarySummary" (no space)
        text = re.sub(
            r'\b([A-Za-z]{3,})\1\b',
            r'\1',
            text
        )
        # Then handle space-separated word repetition: "Hello Hello" -> "Hello"
        prev = None
        while prev != text:
            prev = text
            text = re.sub(r'\b(\w+)\s+\1\b', r'\1', text, flags=re.IGNORECASE)

        # 3. Remove duplicate consecutive LINES within each paragraph block
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
                    unique_lines.append(line)  # preserve blank separators
            cleaned_blocks.append("\n".join(unique_lines))
        text = "\n\n".join(cleaned_blocks)

        # 4. Collapse runs of identical punctuation (e.g. "...." -> ".", ",," -> ",")
        text = re.sub(r'\.{2,}', '.', text)
        text = re.sub(r',{2,}', ',', text)
        text = re.sub(r';{2,}', ';', text)
        text = re.sub(r'!{2,}', '!', text)
        text = re.sub(r'\?{2,}', '?', text)

        # 5. Final whitespace collapse
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    def parse(self, filepath: str) -> Dict[str, Any]:
        """Orchestrates file text extraction based on file extension.
        
        Args:
            filepath: Path to target file.
            
        Returns:
            Dictionary containing:
              - "text": Whole document text.
              - "pages": List of dicts [{"page_number": idx, "text": page_text}].
              - "file_type": Detected file type extension.
        """
        import time
        t_parse_start = time.time()
        logger.info("PARSING START")
        logger.info(f"Parsing document: {filepath}")
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Document file not found: {filepath}")

        ext = self.detect_file_type(filepath)
        raw_text = ""
        pages: List[Dict[str, Any]] = []

        try:
            if ext == ".pdf":
                raw_text, pages = self._parse_pdf(filepath)
            elif ext in [".docx", ".doc"]:
                raw_text, pages = self._parse_docx(filepath)
            elif ext in [".txt", ".md", ".markdown"]:
                raw_text, pages = self._parse_txt(filepath)
            elif ext == ".csv":
                raw_text, pages = self._parse_csv(filepath)
            elif ext in [".xlsx", ".xls"]:
                raw_text, pages = self._parse_excel(filepath)
            elif ext in [".pptx", ".ppt"]:
                raw_text, pages = self._parse_powerpoint(filepath)
            elif ext == ".json":
                raw_text, pages = self._parse_json(filepath)
            elif ext in [".html", ".htm"]:
                raw_text, pages = self._parse_html(filepath)
            elif ext in [".xml"]:
                raw_text, pages = self._parse_xml(filepath)
            elif ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]:
                logger.info("OCR START")
                raw_text = ocr_service.extract_text_from_image(filepath)
                logger.info("OCR END")
                pages = [{"page_number": 1, "text": raw_text}]
            else:
                # Treat as plain text fallback
                logger.warning(f"Unsupported file type '{ext}', attempting plain text fallback.")
                raw_text, pages = self._parse_txt(filepath)
        except Exception as e:
            logger.error(f"Error parsing file {filepath} with extension {ext}: {e}")
            raw_text = f"[Error: Document parsing failed - {str(e)}]"
            pages = [{"page_number": 1, "text": raw_text}]

        cleaned_text = self.normalize_text(self.clean_text(raw_text))

        # Validation Stage: Only validate documents and scanned content (PDF and Images)
        is_val_target = ext in [".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"]
        if is_val_target:
            words = cleaned_text.split()
            if len(words) < 30 or "ocr_failed" in cleaned_text.lower() or "no readable text" in cleaned_text.lower():
                logger.error(f"Validation failed: text too short ({len(words)} words) or invalid.")
                raise ValueError("Unable to extract readable text from the uploaded document.")

        cleaned_pages = [
            {"page_number": p["page_number"], "text": self.normalize_text(self.clean_text(p["text"]))}
            for p in pages
        ]

        t_parse_total = time.time() - t_parse_start
        logger.info("PARSING END")
        logger.info(f"TOTAL LATENCY (parse): {t_parse_total*1000:.2f} ms")

        # Print extracted text with clear section headers
        print("\n" + "="*80)
        print(f"DEBUG: EXTRACTED TEXT FROM '{os.path.basename(filepath)}' (Size: {len(cleaned_text)} chars)")
        print("="*80)
        print(cleaned_text)
        print("="*80 + "\n")

        return {
            "text": cleaned_text,
            "pages": cleaned_pages,
            "file_type": ext
        }

    def _parse_pdf(self, filepath: str) -> tuple[str, List[Dict[str, Any]]]:
        """Parses PDF text, falling back to OCR if scanned or empty."""
        reader = PdfReader(filepath)
        pages = []
        full_text_list = []
        has_extracted_text = False

        for idx, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            pages.append({"page_number": idx, "text": text})
            full_text_list.append(text)
            if len(text.strip()) > 10:
                has_extracted_text = True

        full_text = "\n\n".join(full_text_list)
        words = full_text.split()

        # Scanned PDF detection: if no pages have significant extracted text or word count < 30
        if not has_extracted_text or len(words) < 30:
            logger.info("OCR START")
            logger.info(f"PDF appears to be scanned or selectable text is too short ({len(words)} words). Dispatching to OCR...")
            ocr_text = ocr_service.extract_text_from_scanned_pdf(filepath)
            logger.info("OCR END")
            pages = [{"page_number": 1, "text": ocr_text}]
            return ocr_text, pages

        return full_text, pages

    def _parse_docx(self, filepath: str) -> tuple[str, List[Dict[str, Any]]]:
        doc = docx.Document(filepath)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        
        # Extract tables as labeled rows
        table_texts = []
        for table in doc.tables:
            headers = []
            for row_idx, row in enumerate(table.rows):
                cells = [cell.text.strip() for cell in row.cells]
                if row_idx == 0:
                    headers = cells
                    table_texts.append(" | ".join(headers))
                elif headers:
                    labeled = []
                    for j, val in enumerate(cells):
                        label = headers[j] if j < len(headers) else f"Column {j+1}"
                        if val:
                            labeled.append(f"{label}: {val}")
                    if labeled:
                        table_texts.append(" | ".join(labeled))
                else:
                    non_empty = [c for c in cells if c]
                    if non_empty:
                        table_texts.append(" | ".join(non_empty))
        
        all_parts = paragraphs
        if table_texts:
            all_parts.append("\n".join(table_texts))
        
        full_text = "\n\n".join(all_parts)
        
        # Docx does not have explicit native pages, map to page 1
        pages = [{"page_number": 1, "text": full_text}]
        return full_text, pages

    def _parse_txt(self, filepath: str) -> tuple[str, List[Dict[str, Any]]]:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return content, [{"page_number": 1, "text": content}]

    def _parse_csv(self, filepath: str) -> tuple[str, List[Dict[str, Any]]]:
        rows = []
        headers = []
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            for i, row in enumerate(reader):
                if i == 0:
                    headers = [h.strip() for h in row]
                    rows.append(" | ".join(headers))  # Header row
                elif headers:
                    # Labeled row: "Header1: Value1 | Header2: Value2"
                    labeled = []
                    for j, val in enumerate(row):
                        label = headers[j] if j < len(headers) else f"Column {j+1}"
                        labeled.append(f"{label}: {val.strip()}")
                    rows.append(" | ".join(labeled))
                else:
                    rows.append(", ".join(row))
        full_text = "\n".join(rows)
        return full_text, [{"page_number": 1, "text": full_text}]

    def _parse_excel(self, filepath: str) -> tuple[str, List[Dict[str, Any]]]:
        wb = openpyxl.load_workbook(filepath, data_only=True)
        sheets_text = []
        for name in wb.sheetnames:
            sheet = wb[name]
            headers = []
            sheet_rows = []
            for row_idx, row in enumerate(sheet.iter_rows(values_only=True)):
                # Filter out completely empty rows
                row_vals = [str(cell) if cell is not None else "" for cell in row]
                non_empty = [v for v in row_vals if v.strip()]
                if not non_empty:
                    continue
                if row_idx == 0:
                    # Treat first row as headers
                    headers = [v.strip() for v in row_vals]
                    sheet_rows.append(" | ".join(headers))
                elif headers:
                    # Labeled row: "Header1: Value1 | Header2: Value2"
                    labeled = []
                    for j, val in enumerate(row_vals):
                        label = headers[j] if j < len(headers) else f"Column {j+1}"
                        if val.strip():
                            labeled.append(f"{label}: {val.strip()}")
                    if labeled:
                        sheet_rows.append(" | ".join(labeled))
                else:
                    clean_vals = [v for v in row_vals if v.strip()]
                    if clean_vals:
                        sheet_rows.append(" | ".join(clean_vals))
            if sheet_rows:
                sheets_text.append(f"Sheet: {name}\n" + "\n".join(sheet_rows))
                
        full_text = "\n\n".join(sheets_text)
        return full_text, [{"page_number": 1, "text": full_text}]

    def _parse_powerpoint(self, filepath: str) -> tuple[str, List[Dict[str, Any]]]:
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
            pages.append({"page_number": idx, "text": slide_text})
            
        full_text = "\n\n--- Slide ---\n\n".join(slide_texts)
        return full_text, pages

    def _parse_json(self, filepath: str) -> tuple[str, List[Dict[str, Any]]]:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
        full_text = json.dumps(data, indent=2)
        return full_text, [{"page_number": 1, "text": full_text}]

    def _parse_html(self, filepath: str) -> tuple[str, List[Dict[str, Any]]]:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            soup = BeautifulSoup(f, "html.parser")
        # Remove script and style elements
        for element in soup(["script", "style"]):
            element.decompose()
        text = soup.get_text()
        # Collapse multiple empty lines
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase for phrase in lines if phrase)
        full_text = "\n\n".join(chunks)
        return full_text, [{"page_number": 1, "text": full_text}]

    def _parse_xml(self, filepath: str) -> tuple[str, List[Dict[str, Any]]]:
        tree = ET.parse(filepath)
        root = tree.getroot()
        texts = []
        for elem in root.iter():
            if elem.text and elem.text.strip():
                texts.append(f"{elem.tag}: {elem.text.strip()}")
        full_text = "\n".join(texts)
        return full_text, [{"page_number": 1, "text": full_text}]


document_parser = DocumentParser()
