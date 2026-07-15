"""Knowledge Service for building and persisting structured knowledge representations of documents.
"""

import os
import re
import json
from typing import Dict, Any, List, Optional
from loguru import logger
from backend.app.core.config import settings


class KnowledgeBuilder:
    """Extracts structured knowledge representations from raw document text and tables."""

    def __init__(self) -> None:
        self.stopwords = {
            "the", "and", "a", "of", "to", "in", "is", "that", "it", "he", "was", "for", "on", "are", "as", 
            "with", "his", "they", "i", "at", "be", "this", "have", "from", "or", "one", "had", "by", "word", 
            "but", "not", "what", "all", "were", "we", "when", "your", "can", "said", "there", "use", "an", 
            "each", "which", "she", "do", "how", "their", "if", "will", "up", "other", "about", "out", "many", 
            "then", "them", "these", "so", "some", "her", "would", "make", "like", "him", "into", "has", "look", 
            "more", "write", "go", "see", "number", "no", "way", "could", "people", "my", "than", "first", 
            "water", "been", "call", "who", "oil", "its", "now", "find", "long", "down", "day", "did", "get", 
            "come", "made", "may", "part"
        }

    def classify_document(self, text: str, file_type: str) -> str:
        """Heuristically classifies the document type based on text content and extension."""
        ft_lower = file_type.lower()
        if ft_lower in [".xlsx", ".xls", ".csv"]:
            return "Excel"
        if ft_lower in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]:
            return "Image"

        text_lower = text.lower()

        # Keywords counts
        resume_keywords = ["skills", "experience", "education", "projects", "employment", "cv", "resume", "certifications", "technologies"]
        invoice_keywords = ["invoice", "bill to", "due date", "gst", "total amount", "tax", "quantity", "unit price", "invoice number", "gstin"]
        research_keywords = ["abstract", "methodology", "introduction", "conclusion", "references", "results", "discussion", "authors"]
        policy_keywords = ["policy", "handbook", "rules", "regulations", "probation", "working hours", "benefits", "guidelines", "leave policy"]
        contract_keywords = ["agreement", "contract", "parties", "hereby", "indemnity", "warranties", "effective date", "termination clause", "confidentiality"]

        scores = {
            "Resume": sum(1 for w in resume_keywords if w in text_lower),
            "Invoice": sum(1 for w in invoice_keywords if w in text_lower),
            "Research Paper": sum(1 for w in research_keywords if w in text_lower),
            "Policy": sum(1 for w in policy_keywords if w in text_lower),
            "Contract": sum(1 for w in contract_keywords if w in text_lower)
        }

        # Boost specific highly accurate terms
        if "curriculum vitae" in text_lower or "resume" in text_lower:
            scores["Resume"] += 3
        if "tax invoice" in text_lower or "invoice number" in text_lower:
            scores["Invoice"] += 3
        if "abstract" in text_lower and "methodology" in text_lower:
            scores["Research Paper"] += 3

        best_type = "Generic"
        max_score = 1  # Minimum score threshold to classify
        for doc_type, score in scores.items():
            if score > max_score:
                max_score = score
                best_type = doc_type

        return best_type

    def extract_sections(self, text: str, doc_type: str) -> Dict[str, str]:
        """Segments document text into logical sections based on headings."""
        sections: Dict[str, str] = {}
        lines = text.split('\n')
        current_section = "Introduction"
        current_content = []

        # Identify possible section headings
        heading_pattern = re.compile(r'^(?:[I|V|X\d]+\.\s*)?([A-Za-z][A-Za-z\s]{1,40})$')

        # Define expected sections per doc type to lock headings in
        expected_sections = {
            "Resume": ["skills", "experience", "education", "projects", "certifications", "summary", "contact"],
            "Invoice": ["invoice details", "billing information", "products", "payment terms"],
            "Research Paper": ["abstract", "introduction", "methodology", "results", "conclusion", "references", "discussion"],
            "Policy": ["leave policy", "working hours", "benefits", "rules", "regulations", "guidelines", "probation"],
            "Contract": ["parties", "effective date", "obligations", "payment terms", "termination", "confidentiality"]
        }

        expected = expected_sections.get(doc_type, [])

        for line in lines:
            line_strip = line.strip()
            if not line_strip:
                continue

            # Check if line looks like a markdown heading or section heading
            is_heading = False
            heading_title = ""

            if line_strip.startswith('#'):
                is_heading = True
                heading_title = line_strip.lstrip('#').strip()
            elif len(line_strip) < 50 and (line_strip.isupper() or heading_pattern.match(line_strip)):
                cleaned = re.sub(r'^[I|V|X\d]+\.\s*', '', line_strip).strip()
                # For non-uppercase heading candidates, match against expected sections
                if line_strip.isupper() or any(exp in cleaned.lower() for exp in expected):
                    is_heading = True
                    heading_title = cleaned

            if is_heading:
                # Save previous section
                if current_content:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = heading_title.title()
                current_content = []
            else:
                current_content.append(line_strip)

        if current_content:
            sections[current_section] = "\n".join(current_content).strip()

        # If no headings found, fall back to whole body as General
        if len(sections) <= 1 and "Introduction" in sections:
            sections = {"Content": text}

        return sections

    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extracts high-priority entity types from the text."""
        entities: Dict[str, List[str]] = {
            "emails": [],
            "phones": [],
            "dates": [],
            "amounts": [],
            "percentages": [],
            "urls": [],
            "companies": [],
            "people": []
        }

        # Emails
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        entities["emails"] = list(set(emails))

        # Phones
        phones = re.findall(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}', text)
        entities["phones"] = list(set([p.strip() for p in phones]))

        # Dates
        dates = re.findall(
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b'
            r'|\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{2,4}\b'
            r'|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+\d{2,4}\b',
            text, re.IGNORECASE
        )
        entities["dates"] = list(set([d.strip() for d in dates]))

        # Amounts
        amounts = re.findall(r'[\$\u20b9\u20ac\u00a3]\s*[\d,]+\.?\d*|\d[\d,]*\.?\d*\s*(?:USD|INR|EUR|GBP|rupees|dollars)', text, re.IGNORECASE)
        entities["amounts"] = list(set([a.strip() for a in amounts]))

        # Percentages
        pcts = re.findall(r'\b\d+\.?\d*\s*%', text)
        entities["percentages"] = list(set([p.strip() for p in pcts]))

        # URLs
        urls = re.findall(r'https?://[^\s/$.?#].[^\s]*', text, re.IGNORECASE)
        entities["urls"] = list(set([u.strip() for u in urls]))

        # Companies (e.g. Acme Corp, Google Inc.)
        companies = re.findall(r'\b[A-Z][A-Za-z0-9&\s]{1,25}\s+(?:Corp|Inc|Ltd|Company|Co\.|LLC|Corporation|Limited)\b', text)
        entities["companies"] = list(set([c.strip() for c in companies]))

        # People names heuristic
        people = re.findall(r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b', text)
        # Filter out false positives matching common nouns
        clean_people = []
        for p in people:
            words = p.lower().split()
            if not any(w in self.stopwords for w in words):
                clean_people.append(p)
        entities["people"] = list(set(clean_people))[:10]  # Cap names

        return entities

    def extract_facts(self, text: str) -> Dict[str, str]:
        """Extracts key-value facts matching 'Key: Value' layout from the text."""
        facts: Dict[str, str] = {}
        lines = text.split('\n')
        for line in lines:
            match = re.match(r'^([\w\s_-]{2,30}):\s*(.+)$', line.strip())
            if match:
                key = match.group(1).strip()
                val = match.group(2).strip()
                if key and val and len(val) > 1 and not key.lower() in ["http", "https"]:
                    facts[key] = val
        return facts

    def extract_tables(self, text: str) -> List[Dict[str, Any]]:
        """Identifies pipe-delimited or structured grid lines and builds table statistics."""
        tables: List[Dict[str, Any]] = []
        lines = [line.strip() for line in text.split('\n')]
        
        current_table_lines = []
        for line in lines:
            if '|' in line:
                current_table_lines.append(line)
            else:
                if current_table_lines:
                    self._parse_and_append_table(current_table_lines, tables)
                    current_table_lines = []
        if current_table_lines:
            self._parse_and_append_table(current_table_lines, tables)
            
        return tables

    def _parse_and_append_table(self, raw_lines: List[str], tables: List[Dict[str, Any]]) -> None:
        """Parses list of pipe-separated rows into JSON headers, rows, and computed statistics."""
        if len(raw_lines) < 2:
            return

        headers = [c.strip() for c in raw_lines[0].split('|') if c.strip()]
        
        # Check if the next line is a separator line (e.g. `---|---`)
        start_idx = 1
        if start_idx < len(raw_lines) and any(c in raw_lines[start_idx] for c in ['-', ':']):
            if len([c for c in raw_lines[start_idx].split('|') if c.strip()]) == len(headers):
                start_idx += 1

        rows = []
        for line in raw_lines[start_idx:]:
            cells = [c.strip() for c in line.split('|') if c.strip()]
            if not cells:
                continue
            
            # Map cell values to headers
            row_dict = {}
            for j, cell in enumerate(cells):
                if j < len(headers):
                    row_dict[headers[j]] = cell
                else:
                    row_dict[f"Column {j+1}"] = cell
            if row_dict:
                rows.append(row_dict)

        if not rows:
            return

        # Compute Column-level numerical statistics (sums, averages, min/max)
        stats = {}
        for header in headers:
            # Check if majority of values in this column are numeric
            numeric_vals = []
            for r in rows:
                val_str = r.get(header, "")
                # Clean currency and formatting punctuation
                cleaned_val = re.sub(r'[^\d.-]', '', val_str)
                try:
                    if cleaned_val:
                        numeric_vals.append(float(cleaned_val))
                except ValueError:
                    pass

            if len(numeric_vals) >= len(rows) * 0.5 and numeric_vals:
                stats[header] = {
                    "sum": sum(numeric_vals),
                    "avg": sum(numeric_vals) / len(numeric_vals),
                    "min": min(numeric_vals),
                    "max": max(numeric_vals),
                    "count": len(numeric_vals)
                }

        tables.append({
            "headers": headers,
            "rows": rows,
            "stats": stats
        })

    def generate_summary(self, text: str, doc_type: str) -> str:
        """Produces a clean abstractive paragraph summary using keyword-frequency sentence re-ranking."""
        # 1. Prioritize pre-existing summary sections
        sections = self.extract_sections(text, doc_type)
        for s_name in ["Summary", "Abstract", "Overview", "Introduction"]:
            if s_name in sections and len(sections[s_name]) > 100:
                # Truncate summary if too long
                summ = sections[s_name].strip()
                sentences = [s.strip() for s in re.split(r'(?<=\.|\?)\s+', summ) if s.strip()]
                return " ".join(sentences[:5])

        # 2. Heuristics fallback: TF-IDF LexRank-style sentence extraction
        sentences = [s.strip() for s in re.split(r'(?<=\.|\?)\s+', text) if s.strip()]
        if len(sentences) <= 3:
            return " ".join(sentences)

        # Build word frequency dictionary
        word_freqs = {}
        words = re.findall(r'\b\w{3,}\b', text.lower())
        for w in words:
            if w not in self.stopwords:
                word_freqs[w] = word_freqs.get(w, 0) + 1

        # Score sentences by average word frequency
        sentence_scores = []
        for s in sentences:
            s_words = [w for w in re.findall(r'\b\w{3,}\b', s.lower()) if w not in self.stopwords]
            if not s_words:
                sentence_scores.append((s, 0.0))
                continue
            score = sum(word_freqs.get(w, 0) for w in s_words) / len(s_words)
            sentence_scores.append((s, score))

        # Sort and select top-4 sentences, but preserve their original order
        top_sentences = sorted(sentence_scores, key=lambda x: x[1], reverse=True)[:4]
        selected_set = set(t[0] for t in top_sentences)

        summary_sentences = [s for s in sentences if s in selected_set]
        return " ".join(summary_sentences)

    def mine_keywords(self, text: str) -> List[str]:
        """Extracts top 10 unique descriptive keywords from text."""
        words = re.findall(r'\b\w{4,}\b', text.lower())
        freqs = {}
        for w in words:
            if w not in self.stopwords and not w.isdigit():
                freqs[w] = freqs.get(w, 0) + 1
        sorted_freqs = sorted(freqs.items(), key=lambda x: x[1], reverse=True)
        return [item[0] for item in sorted_freqs[:10]]

    def build_knowledge(self, text: str, file_type: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Orchestrates structured knowledge extraction from raw inputs."""
        doc_type = self.classify_document(text, file_type)
        sections = self.extract_sections(text, doc_type)
        entities = self.extract_entities(text)
        facts = self.extract_facts(text)
        tables = self.extract_tables(text)
        summary = self.generate_summary(text, doc_type)
        keywords = self.mine_keywords(text)

        return {
            "document_type": doc_type,
            "sections": sections,
            "entities": entities,
            "facts": facts,
            "tables": tables,
            "summary": summary,
            "keywords": keywords,
            "metadata": metadata or {}
        }


class KnowledgeStore:
    """Handles persistence of structured knowledge dictionaries to a local JSON file."""

    def __init__(self) -> None:
        self.store_path = os.path.join(settings.DATA_DIR, "knowledge_store.json")
        self._ensure_store_exists()

    def _ensure_store_exists(self) -> None:
        """Initializes empty JSON store file if not present."""
        if not os.path.exists(self.store_path):
            try:
                os.makedirs(os.path.dirname(self.store_path), exist_ok=True)
                with open(self.store_path, "w", encoding="utf-8") as f:
                    json.dump({}, f)
                logger.info(f"Initialized empty JSON knowledge store at {self.store_path}")
            except Exception as e:
                logger.error(f"Failed to create knowledge store: {e}")

    def _read_store(self) -> Dict[str, Dict[str, Any]]:
        """Reads document store data."""
        try:
            if not os.path.exists(self.store_path):
                return {}
            with open(self.store_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read knowledge store: {e}")
            return {}

    def _write_store(self, data: Dict[str, Dict[str, Any]]) -> None:
        """Writes store dictionary to disk."""
        try:
            with open(self.store_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write knowledge store: {e}")

    def save_knowledge(self, doc_id: str, knowledge: Dict[str, Any]) -> None:
        """Saves a document's structured knowledge dict."""
        logger.info(f"Persisting structured knowledge for document: {doc_id}")
        data = self._read_store()
        data[doc_id] = knowledge
        self._write_store(data)

    def get_knowledge(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves structured knowledge dict for a document ID."""
        data = self._read_store()
        return data.get(doc_id)

    def delete_knowledge(self, doc_id: str) -> None:
        """Removes a document ID's entry from the knowledge store."""
        logger.info(f"Deleting structured knowledge for document: {doc_id}")
        data = self._read_store()
        if doc_id in data:
            del data[doc_id]
            self._write_store(data)


# Instantiate singletons for global app access
knowledge_builder = KnowledgeBuilder()
knowledge_store = KnowledgeStore()
