"""Chunk Service for splitting document text semantically into logical chunks.
"""

import re
from typing import Dict, Any, List
from loguru import logger


class ChunkService:
    """Splits document text semantically by paragraphs, sentences, and headings."""

    def split_sentences(self, text: str) -> List[str]:
        """Splits a block of text into sentences using simple regex.
        
        Args:
            text: Input text block.
            
        Returns:
            List of sentence strings.
        """
        # Split by periods, question marks, or exclamation marks followed by whitespace
        sentence_endings = re.compile(r"(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s")
        sentences = sentence_endings.split(text)
        return [s.strip() for s in sentences if s.strip()]

    def extract_heading(self, text: str) -> str:
        """Heuristically extracts a heading or title from a chunk of text.
        
        Args:
            text: Chunk text.
            
        Returns:
            Extracted heading name, or 'Content' if none identified.
        """
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if not lines:
            return "Content"

        first_line = lines[0]
        # Markdown heading check
        if first_line.startswith("#"):
            return first_line.lstrip("#").strip()
        # Short capitalized line check
        if len(first_line) < 60 and (first_line.isupper() or any(first_line.startswith(p) for p in ["Section", "Chapter", "Article"])):
            return first_line
        
        return "Content"

    def detect_content_type(self, text: str) -> str:
        """Detects whether a chunk is text, list, table, or heading.
        
        Args:
            text: Chunk text.
            
        Returns:
            One of 'heading', 'list', 'table', 'text'.
        """
        stripped = text.strip()
        lines = [l.strip() for l in stripped.split('\n') if l.strip()]
        if not lines:
            return "text"
        
        # Heading: single short line, possibly markdown
        if len(lines) == 1 and len(lines[0]) < 80 and (lines[0].startswith('#') or lines[0].isupper()):
            return "heading"
        
        # Table: majority of lines contain pipe delimiters
        pipe_lines = sum(1 for l in lines if '|' in l)
        if pipe_lines >= len(lines) * 0.5 and pipe_lines >= 2:
            return "table"
        
        # List: majority of lines start with bullet characters
        bullet_lines = sum(1 for l in lines if re.match(r'^[\u2022\-*\d]+[.\)\s]', l))
        if bullet_lines >= len(lines) * 0.5 and bullet_lines >= 2:
            return "list"
        
        return "text"

    def chunk_document(
        self,
        parsed_doc: Dict[str, Any],
        doc_id: str,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> List[Dict[str, Any]]:
        """Splits parsed document pages semantically into logical chunks.
        
        Args:
            parsed_doc: The output dictionary from DocumentParser.parse.
            doc_id: The document identifier.
            chunk_size: Ideal character count per chunk.
            chunk_overlap: Ideal character overlap between chunks.
            
        Returns:
            List of chunk dictionaries containing text and metadata.
        """
        logger.info(f"Chunking document: {doc_id} with size={chunk_size}, overlap={chunk_overlap}")
        
        chunks: List[Dict[str, Any]] = []
        chunk_idx = 0
        pages = parsed_doc.get("pages", [])

        # Process page by page to ensure accurate page mapping
        for page_data in pages:
            page_num = page_data.get("page_number", 1)
            page_text = page_data.get("text", "")
            
            if not page_text.strip():
                continue

            # Split into paragraphs
            paragraphs = page_text.split("\n\n")
            current_chunk_text = ""
            current_start_char = 0
            
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue

                # Detect if paragraph is a structured block (list or table)
                is_structured = bool(re.match(r'^[\s]*[\u2022\-*|]', para)) or '|' in para
                
                # If structured block, flush current chunk and emit block as its own chunk
                if is_structured and len(para) > 20:
                    if current_chunk_text:
                        heading = self.extract_heading(current_chunk_text)
                        content_type = self.detect_content_type(current_chunk_text)
                        char_end = current_start_char + len(current_chunk_text)
                        chunks.append({
                            "chunk_id": f"{doc_id}_chunk_{chunk_idx}",
                            "doc_id": doc_id,
                            "text": current_chunk_text,
                            "page_number": page_num,
                            "section": heading,
                            "content_type": content_type,
                            "char_range": [current_start_char, char_end]
                        })
                        chunk_idx += 1
                        current_chunk_text = ""
                        current_start_char = char_end
                    
                    # Emit structured block as its own chunk
                    heading = self.extract_heading(para)
                    content_type = self.detect_content_type(para)
                    char_end = current_start_char + len(para)
                    chunks.append({
                        "chunk_id": f"{doc_id}_chunk_{chunk_idx}",
                        "doc_id": doc_id,
                        "text": para,
                        "page_number": page_num,
                        "section": heading,
                        "content_type": content_type,
                        "char_range": [current_start_char, char_end]
                    })
                    chunk_idx += 1
                    current_start_char = char_end
                    continue

                # If paragraph alone fits within size, or is first in chunk
                if len(current_chunk_text) + len(para) <= chunk_size:
                    if current_chunk_text:
                        current_chunk_text += "\n\n" + para
                    else:
                        current_chunk_text = para
                else:
                    # Paragraph makes chunk exceed size, save current chunk first if it exists
                    if current_chunk_text:
                        heading = self.extract_heading(current_chunk_text)
                        content_type = self.detect_content_type(current_chunk_text)
                        char_end = current_start_char + len(current_chunk_text)
                        chunks.append({
                            "chunk_id": f"{doc_id}_chunk_{chunk_idx}",
                            "doc_id": doc_id,
                            "text": current_chunk_text,
                            "page_number": page_num,
                            "section": heading,
                            "content_type": content_type,
                            "char_range": [current_start_char, char_end]
                        })
                        chunk_idx += 1
                        # Start new chunk with overlap
                        overlap_start = max(0, len(current_chunk_text) - chunk_overlap)
                        current_chunk_text = current_chunk_text[overlap_start:] + "\n\n" + para
                        current_start_char = char_end - (len(current_chunk_text) - len(para) - 2)
                    else:
                        # Single paragraph is too large on its own, split it by sentence
                        sentences = self.split_sentences(para)
                        for sent in sentences:
                            if len(current_chunk_text) + len(sent) <= chunk_size:
                                if current_chunk_text:
                                    current_chunk_text += " " + sent
                                else:
                                    current_chunk_text = sent
                            else:
                                if current_chunk_text:
                                    heading = self.extract_heading(current_chunk_text)
                                    content_type = self.detect_content_type(current_chunk_text)
                                    char_end = current_start_char + len(current_chunk_text)
                                    chunks.append({
                                        "chunk_id": f"{doc_id}_chunk_{chunk_idx}",
                                        "doc_id": doc_id,
                                        "text": current_chunk_text,
                                        "page_number": page_num,
                                        "section": heading,
                                        "content_type": content_type,
                                        "char_range": [current_start_char, char_end]
                                    })
                                    chunk_idx += 1
                                    overlap_start = max(0, len(current_chunk_text) - chunk_overlap)
                                    current_chunk_text = current_chunk_text[overlap_start:] + " " + sent
                                    current_start_char = char_end - (len(current_chunk_text) - len(sent) - 1)
                                else:
                                    # Single sentence is larger than chunk size! Force split by length
                                    # to prevent infinite loops or oversize chunks
                                    for i in range(0, len(sent), chunk_size):
                                        sub_sent = sent[i:i + chunk_size]
                                        heading = self.extract_heading(sub_sent)
                                        content_type = self.detect_content_type(sub_sent)
                                        char_end = current_start_char + len(sub_sent)
                                        chunks.append({
                                            "chunk_id": f"{doc_id}_chunk_{chunk_idx}",
                                            "doc_id": doc_id,
                                            "text": sub_sent,
                                            "page_number": page_num,
                                            "section": heading,
                                            "content_type": content_type,
                                            "char_range": [current_start_char, char_end]
                                        })
                                        chunk_idx += 1
                                        current_start_char = char_end

            # Flush final chunk on page
            if current_chunk_text:
                heading = self.extract_heading(current_chunk_text)
                content_type = self.detect_content_type(current_chunk_text)
                char_end = current_start_char + len(current_chunk_text)
                chunks.append({
                    "chunk_id": f"{doc_id}_chunk_{chunk_idx}",
                    "doc_id": doc_id,
                    "text": current_chunk_text,
                    "page_number": page_num,
                    "section": heading,
                    "content_type": content_type,
                    "char_range": [current_start_char, char_end]
                })
                chunk_idx += 1

        # Print all generated chunks in terminal with clear headers
        print("\n" + "="*80)
        print(f"DEBUG: GENERATED CHUNKS FOR '{doc_id}' (Total: {len(chunks)} chunks)")
        print("="*80)
        for i, chunk in enumerate(chunks):
            print(f"Chunk {i} | ID: {chunk['chunk_id']} | Page: {chunk['page_number']} | Section: {chunk['section']}")
            print("-" * 40)
            print(chunk["text"])
            print("-" * 40)
        print("="*80 + "\n")

        logger.info(f"Completed chunking. Generated {len(chunks)} chunks for document: {doc_id}")
        return chunks


chunk_service = ChunkService()
