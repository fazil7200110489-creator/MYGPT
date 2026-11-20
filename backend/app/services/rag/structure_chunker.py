"""Structure-Aware Chunking Service for MYGPT Hybrid RAG.

Transforms parsed tender pages, clauses, headings, and tables into semantic,
structure-preserving TenderChunk objects without separating table values from headers
or dropping clause context.
"""

import hashlib
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from loguru import logger


class TenderChunk(BaseModel):
    """Semantic structure-preserving chunk of a tender document."""

    chunk_id: str = Field(..., description="Unique deterministic chunk identifier")
    doc_id: str = Field(default="", description="Parent document identifier")
    filename: str = Field(default="", description="Original file basename")
    page_number: int = Field(..., description="Original 1-indexed document page number")
    content_type: str = Field(
        ..., description="Content category: clause | paragraph | table | ocr"
    )
    section_heading: Optional[str] = Field(
        default=None, description="Enclosing tender section or heading"
    )
    clause_number: Optional[str] = Field(
        default=None, description="Clause or sub-clause number (e.g. 1.1, 4.2.3)"
    )
    table_title: Optional[str] = Field(
        default=None, description="Title of the table if content_type is table"
    )
    table_headers: Optional[List[str]] = Field(
        default=None, description="Column headers preserved for table rows"
    )
    text: str = Field(..., description="Searchable textual representation")
    raw_content: str = Field(..., description="Original verbatim content / markdown")
    char_count: int = Field(default=0, description="Character count of text")
    prev_chunk_id: Optional[str] = Field(
        default=None, description="Preceding sequential chunk ID"
    )
    next_chunk_id: Optional[str] = Field(
        default=None, description="Succeeding sequential chunk ID"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary extra metadata"
    )


class StructureAwareChunker:
    """Chunks documents while preserving tender headings, clauses, and table integrity."""

    def __init__(
        self,
        max_chunk_chars: int = 900,
        min_chunk_chars: int = 60,
        chunk_overlap_chars: int = 120,
        max_table_rows_per_chunk: int = 7,
    ) -> None:
        self.max_chunk_chars = max_chunk_chars
        self.min_chunk_chars = min_chunk_chars
        self.chunk_overlap_chars = chunk_overlap_chars
        self.max_table_rows_per_chunk = max_table_rows_per_chunk

    def chunk_document(
        self,
        parsed_doc: Dict[str, Any],
        doc_id: str = "",
        filename: str = "",
    ) -> List[TenderChunk]:
        """Converts parsed document pages, tables, and clauses into structured chunks.

        Args:
            parsed_doc: Dict containing 'pages', 'file_hash', etc. from document_parser.
            doc_id: Unique document identifier.
            filename: Original document filename.

        Returns:
            List of sequentially linked TenderChunk objects.
        """
        if not parsed_doc:
            return []

        doc_hash = str(parsed_doc.get("file_hash") or "")[:12]
        effective_doc_id = doc_id or doc_hash or "doc"
        effective_filename = filename or parsed_doc.get("filename") or "document.pdf"

        pages = parsed_doc.get("pages") or []
        raw_chunks: List[TenderChunk] = []
        current_section = "GENERAL NOTICE"
        current_clause = None

        seen_content_hashes: set = set()

        for page in pages:
            page_num = int(page.get("page_number", 1))
            is_ocr = bool(page.get("is_ocr", False))
            page_headings = page.get("headings") or []
            page_tables = page.get("tables") or []
            page_text = page.get("text") or ""

            # Update running section/clause from page headings
            if page_headings:
                h0 = page_headings[0]
                if h0.get("title"):
                    current_section = h0["title"]
                if h0.get("section_number"):
                    current_clause = h0["section_number"]

            # -------------------------------------------------------------
            # 1. Process Structured Tables (Never detach headers from rows)
            # -------------------------------------------------------------
            for t_idx, table in enumerate(page_tables, start=1):
                headers = table.get("headers") or []
                rows = table.get("rows") or []
                title = table.get("title") or f"Table {t_idx} (Page {page_num})"
                is_cont = bool(table.get("is_continuation", False))

                if not rows:
                    continue

                # Header string
                header_line = " | ".join(headers) if headers else "Col " + " | Col ".join(str(i + 1) for i in range(len(rows[0])))

                # Slice table into manageable row batches if very large
                for batch_start in range(0, len(rows), self.max_table_rows_per_chunk):
                    batch_rows = rows[batch_start : batch_start + self.max_table_rows_per_chunk]
                    
                    # Construct markdown representation
                    md_lines = [f"### {title}"]
                    if is_cont:
                        md_lines.append("*(Continued from previous table)*")
                    md_lines.append(f"| {header_line} |")
                    md_lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
                    for r in batch_rows:
                        md_lines.append("| " + " | ".join(r) + " |")

                    table_md = "\n".join(md_lines)

                    # Searchable text embedding format
                    search_lines = [f"Table: {title}", f"Headers: {header_line}"]
                    for r in batch_rows:
                        # Label columns for semantic clarity
                        labeled_cells = [
                            f"{headers[ci] if ci < len(headers) else f'Col {ci+1}'}: {val}"
                            for ci, val in enumerate(r)
                            if val
                        ]
                        search_lines.append(" | ".join(labeled_cells) if labeled_cells else " | ".join(r))
                    searchable_text = "\n".join(search_lines)

                    # Deduplication check
                    content_digest = hashlib.md5(searchable_text.encode("utf-8")).hexdigest()
                    if content_digest in seen_content_hashes:
                        continue
                    seen_content_hashes.add(content_digest)

                    c_id = f"{effective_doc_id}_p{page_num}_t{t_idx}_{batch_start}"
                    chunk = TenderChunk(
                        chunk_id=c_id,
                        doc_id=effective_doc_id,
                        filename=effective_filename,
                        page_number=page_num,
                        content_type="table",
                        section_heading=current_section,
                        clause_number=current_clause,
                        table_title=title,
                        table_headers=headers,
                        text=searchable_text,
                        raw_content=table_md,
                        char_count=len(searchable_text),
                        metadata={
                            "table_number": t_idx,
                            "batch_start_row": batch_start,
                            "row_count": len(batch_rows),
                            "is_continuation": is_cont,
                        },
                    )
                    raw_chunks.append(chunk)

            # -------------------------------------------------------------
            # 2. Process Paragraphs & Clauses
            # -------------------------------------------------------------
            # Filter out table blocks that were already formatted into table chunks
            clean_page_text = re.sub(r"\[Table \d+\].*?(?=\n\n|\Z)", "", page_text, flags=re.DOTALL)
            clean_page_text = clean_page_text.strip()
            if not clean_page_text:
                continue

            paragraphs = [p.strip() for p in clean_page_text.split("\n\n") if p.strip()]
            active_buf: List[str] = []
            active_buf_len = 0

            for para in paragraphs:
                # Detect clause/heading marker at start of paragraph
                m_clause = re.match(r"^(\d+(?:\.\d+)+|[A-Z0-9.\-]+\.)\s+([^\n\r]+)", para)
                if m_clause:
                    # Flush prior buffer before starting new clause
                    if active_buf:
                        block_text = "\n\n".join(active_buf).strip()
                        if len(block_text) >= self.min_chunk_chars:
                            self._add_text_chunk(
                                raw_chunks,
                                block_text,
                                effective_doc_id,
                                effective_filename,
                                page_num,
                                is_ocr,
                                current_section,
                                current_clause,
                                seen_content_hashes,
                            )
                        active_buf = []
                        active_buf_len = 0
                    current_clause = m_clause.group(1).rstrip(".")

                # If paragraph fits in current buffer, accumulate
                if active_buf_len + len(para) <= self.max_chunk_chars:
                    active_buf.append(para)
                    active_buf_len += len(para) + 2
                else:
                    # Flush current buffer
                    if active_buf:
                        block_text = "\n\n".join(active_buf).strip()
                        if len(block_text) >= self.min_chunk_chars:
                            self._add_text_chunk(
                                raw_chunks,
                                block_text,
                                effective_doc_id,
                                effective_filename,
                                page_num,
                                is_ocr,
                                current_section,
                                current_clause,
                                seen_content_hashes,
                            )
                    # If single paragraph is oversized, slice with overlap
                    if len(para) > self.max_chunk_chars:
                        self._slice_oversized_paragraph(
                            raw_chunks,
                            para,
                            effective_doc_id,
                            effective_filename,
                            page_num,
                            is_ocr,
                            current_section,
                            current_clause,
                            seen_content_hashes,
                        )
                        active_buf = []
                        active_buf_len = 0
                    else:
                        active_buf = [para]
                        active_buf_len = len(para)

            # Flush remaining buffer for page
            if active_buf:
                block_text = "\n\n".join(active_buf).strip()
                if len(block_text) >= self.min_chunk_chars:
                    self._add_text_chunk(
                        raw_chunks,
                        block_text,
                        effective_doc_id,
                        effective_filename,
                        page_num,
                        is_ocr,
                        current_section,
                        current_clause,
                        seen_content_hashes,
                    )

        # -------------------------------------------------------------
        # 3. Link Sequential Chunks (prev_chunk_id, next_chunk_id)
        # -------------------------------------------------------------
        for i in range(len(raw_chunks)):
            if i > 0:
                raw_chunks[i].prev_chunk_id = raw_chunks[i - 1].chunk_id
            if i < len(raw_chunks) - 1:
                raw_chunks[i].next_chunk_id = raw_chunks[i + 1].chunk_id

        logger.info(
            f"[STRUCTURE_CHUNKER] Created {len(raw_chunks)} semantic chunks for "
            f"doc={effective_filename} across {len(pages)} pages."
        )
        return raw_chunks

    def _add_text_chunk(
        self,
        chunks: List[TenderChunk],
        text: str,
        doc_id: str,
        filename: str,
        page_num: int,
        is_ocr: bool,
        section_heading: str,
        clause_number: Optional[str],
        seen_hashes: set,
    ) -> None:
        """Helper to create and append a deduplicated text chunk."""
        digest = hashlib.md5(text.encode("utf-8")).hexdigest()
        if digest in seen_hashes:
            return
        seen_hashes.add(digest)

        chunk_idx = len(chunks) + 1
        c_id = f"{doc_id}_p{page_num}_c{chunk_idx}"
        content_type = "ocr" if is_ocr else ("clause" if clause_number else "paragraph")

        # Expand domain acronyms for superior semantic vector retrieval
        enriched_text = text
        if re.search(r"\bEMD\b", enriched_text) and "earnest money" not in enriched_text.lower():
            enriched_text = re.sub(r"\bEMD\b", "EMD (Earnest Money Deposit)", enriched_text)
        if re.search(r"\bPBG\b", enriched_text) and "performance bank guarantee" not in enriched_text.lower():
            enriched_text = re.sub(r"\bPBG\b", "PBG (Performance Bank Guarantee)", enriched_text)
        if re.search(r"\bMAF\b", enriched_text) and "manufacturer authorization" not in enriched_text.lower():
            enriched_text = re.sub(r"\bMAF\b", "MAF (Manufacturer Authorization Form)", enriched_text)
        if re.search(r"\bBOQ\b", enriched_text) and "bill of quantities" not in enriched_text.lower():
            enriched_text = re.sub(r"\bBOQ\b", "BOQ (Bill of Quantities)", enriched_text)
        if re.search(r"\bNIT\b", enriched_text) and "notice inviting tender" not in enriched_text.lower():
            enriched_text = re.sub(r"\bNIT\b", "NIT (Notice Inviting Tender)", enriched_text)

        # Prepend section / clause prefix for dense semantic retrieval clarity
        prefixed_text = enriched_text
        if clause_number and not enriched_text.startswith(clause_number):
            prefixed_text = f"Clause {clause_number}: {enriched_text}"
        elif section_heading and not enriched_text.startswith(section_heading):
            prefixed_text = f"[{section_heading}]\n{enriched_text}"

        chunk = TenderChunk(
            chunk_id=c_id,
            doc_id=doc_id,
            filename=filename,
            page_number=page_num,
            content_type=content_type,
            section_heading=section_heading,
            clause_number=clause_number,
            text=prefixed_text,
            raw_content=text,
            char_count=len(text),
            metadata={"is_ocr": is_ocr},
        )
        chunks.append(chunk)

    def _slice_oversized_paragraph(
        self,
        chunks: List[TenderChunk],
        para: str,
        doc_id: str,
        filename: str,
        page_num: int,
        is_ocr: bool,
        section_heading: str,
        clause_number: Optional[str],
        seen_hashes: set,
    ) -> None:
        """Slices oversized paragraph into overlapping segments without losing context."""
        step = self.max_chunk_chars - self.chunk_overlap_chars
        for start_pos in range(0, len(para), step):
            slice_text = para[start_pos : start_pos + self.max_chunk_chars].strip()
            if len(slice_text) >= self.min_chunk_chars:
                self._add_text_chunk(
                    chunks,
                    slice_text,
                    doc_id,
                    filename,
                    page_num,
                    is_ocr,
                    section_heading,
                    clause_number,
                    seen_hashes,
                )


# Global singleton instance
structure_chunker = StructureAwareChunker()
