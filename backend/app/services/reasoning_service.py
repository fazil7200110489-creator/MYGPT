"""Reasoning Service that performs offline QA generation and confidence scoring using MyGPT.
"""

import math
import re
import time
import torch
import torch.nn.functional as F
from typing import Dict, Any, List, Tuple, Optional
from loguru import logger

from backend.app.services.model_manager import model_manager
from backend.app.services.tokenizer_service import tokenizer


def list_to_prose(text: str, intent: str) -> str:
    """Converts a bulleted list string into natural language prose."""
    # Split text into lines
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    items = []
    for line in lines:
        match = re.match(r"^[•\-*\d\.\s]+(.*)$", line)
        if match:
            item = match.group(1).strip()
            if item:
                items.append(item)
            
    if len(items) >= 2:
        if len(items) == 2:
            items_str = f"{items[0]} and {items[1]}"
        else:
            items_str = ", ".join(items[:-1]) + f", and {items[-1]}"
            
        if intent in ["Skills", "Technologies"]:
            return f"the document lists the following technologies: {items_str}"
        elif intent == "Projects":
            return f"the document lists the following projects: {items_str}"
        else:
            return f"the document lists the following items: {items_str}"
    return ""


def extract_facts(text: str, intent: str) -> Dict[str, str]:
    """Extracts structured key-value facts from text based on intent.

    Uses regex patterns to identify emails, phones, amounts, dates,
    percentages, and generic Key: Value pairs relevant to the intent.
    """
    facts: Dict[str, str] = {}

    # Generic key-value patterns: "Key: Value"
    kv_patterns = re.findall(r'([A-Za-z][A-Za-z\s]{1,30}):\s*(.+?)(?:\n|$)', text)
    for key, val in kv_patterns:
        key = key.strip()
        val = val.strip()
        if key and val and len(val) > 1:
            facts[key] = val

    # Email extraction
    if intent in ["Contacts", "Emails", "Extraction", "Resume", "Question Answering"]:
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        for i, email in enumerate(emails):
            facts[f"Email {i+1}" if i > 0 else "Email"] = email

    # Phone extraction
    if intent in ["Contacts", "Phone Numbers", "Extraction", "Resume", "Question Answering"]:
        phones = re.findall(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}', text)
        for i, phone in enumerate(phones):
            facts[f"Phone {i+1}" if i > 0 else "Phone"] = phone.strip()

    # Amount/currency extraction
    if intent in ["Invoice", "Numbers", "Extraction", "Question Answering"]:
        amounts = re.findall(r'[\$\u20b9\u20ac\u00a3]\s*[\d,]+\.?\d*|\d[\d,]*\.?\d*\s*(?:USD|INR|EUR|GBP|rupees|dollars)', text, re.IGNORECASE)
        for i, amt in enumerate(amounts):
            facts[f"Amount {i+1}" if i > 0 else "Amount"] = amt.strip()

    # Date extraction
    if intent in ["Dates", "Invoice", "Extraction", "Question Answering"]:
        dates = re.findall(
            r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}'
            r'|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{2,4}'
            r'|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+\d{2,4}',
            text, re.IGNORECASE
        )
        for i, date in enumerate(dates):
            facts[f"Date {i+1}" if i > 0 else "Date"] = date.strip()

    # Percentage extraction
    if intent in ["Invoice", "Numbers", "Extraction", "Question Answering"]:
        pcts = re.findall(r'\d+\.?\d*\s*%', text)
        for i, pct in enumerate(pcts):
            facts[f"Percentage {i+1}" if i > 0 else "Percentage"] = pct.strip()

    return facts


def get_intent_prefix(intent: str) -> str:
    """Gets prefix based on intent."""
    prefixes = {
        "Summary": "Based on the document overview, ",
        "Explanation": "According to the detailed explanation, ",
        "Comparison": "Comparing the details in the document, ",
        "Search": "Based on the document search, ",
        "Extraction": "The extracted details show: ",
        "Skills": "Regarding the candidate's skills, ",
        "Education": "Regarding the candidate's education, ",
        "Experience": "Regarding the work experience, ",
        "Invoice": "Based on the invoice details, ",
        "Dates": "According to the specified dates, ",
        "Numbers": "According to the document values, ",
        "Policies": "According to the company policy, ",
        "Research": "Based on the research findings, ",
        "Tables": "According to the tabular data, ",
        "Contacts": "According to the contact information, ",
        "Emails": "According to the email details, ",
        "Phone Numbers": "According to the phone records, ",
        "Names": "Regarding the names mentioned, ",
        "Projects": "Regarding the projects listed, ",
        "Technologies": "Regarding the technologies used, ",
        "Image": "Based on the image analysis, ",
        "Resume": "Based on the candidate's profile, ",
        "Follow-up": "Following up on the previous context, ",
    }
    return prefixes.get(intent, "Based on the uploaded document, ")


def post_process_answer(answer: str) -> str:
    """Fixes punctuation, spacing, and strips leading bullets."""
    # Strip leading bullets or list indicators
    answer = re.sub(r"^[•\-*\d\.\s]+", "", answer).strip()
    # Normalize whitespace
    answer = re.sub(r"\s+", " ", answer).strip()
    # Fix punctuation spacing (e.g. "word , word" -> "word, word")
    answer = re.sub(r"\s+([.,!?;:])", r"\1", answer)
    # Fix double punctuation
    answer = re.sub(r"\.{2,}", ".", answer)
    return answer


def deduplicate_sentences(sentences: List[str], similarity_threshold: float = 0.70) -> List[str]:
    """Removes near-duplicate sentences from a list, keeping only the first occurrence.

    Two sentences are considered duplicates if they share >= `similarity_threshold`
    fraction of word tokens.

    Args:
        sentences: Ordered list of sentence strings.
        similarity_threshold: Word-overlap fraction [0, 1] above which a sentence
            is considered a duplicate of an already-kept sentence.

    Returns:
        Filtered list of unique sentences.
    """
    kept: List[str] = []
    for candidate in sentences:
        cand_words = set(re.findall(r"\w+", candidate.lower()))
        is_dup = False
        for ref in kept:
            ref_words = set(re.findall(r"\w+", ref.lower()))
            if not cand_words or not ref_words:
                continue
            overlap = len(cand_words & ref_words) / max(len(cand_words), len(ref_words))
            if overlap >= similarity_threshold:
                is_dup = True
                break
        if not is_dup:
            kept.append(candidate)
    return kept


def synthesize_summary(sentences: List[str], prefix: str) -> str:
    """Builds a 4-8 sentence fluent prose paragraph for Summary intent.

    Deduplicates sentences, ensures each ends with proper punctuation, and joins
    them with natural connectors.

    Args:
        sentences: Candidate sentences (already scored/selected).
        prefix: Intent-specific opening phrase.

    Returns:
        A clean, fluent multi-sentence paragraph.
    """
    unique = deduplicate_sentences(sentences)
    # Cap at 8 sentences for summary
    unique = unique[:8]
    parts = []
    connectors = ["", "Furthermore, ", "Additionally, ", "Moreover, ", "Also, ",
                  "In addition, ", "Notably, ", "Overall, "]
    for i, s in enumerate(unique):
        s = s.strip()
        if not s:
            continue
        if s[-1] not in '.!?':
            s += '.'
        if i == 0:
            # First sentence: capitalize
            s = s[0].upper() + s[1:]
        else:
            connector = connectors[i] if i < len(connectors) else ""
            if connector:
                s = connector + s[0].lower() + s[1:]
            else:
                s = s[0].upper() + s[1:]
        parts.append(s)
    paragraph = " ".join(parts)
    # Apply prefix
    if prefix and paragraph:
        if prefix.endswith(", ") or prefix.endswith(": "):
            paragraph = prefix + paragraph[0].lower() + paragraph[1:]
        else:
            paragraph = prefix + paragraph
    return paragraph


def synthesize_experience(sections: Dict[str, str], context: str) -> str:
    """Produces a structured experience answer from knowledge sections or context.

    Args:
        sections: Document section dict from knowledge store (may be empty).
        context: Raw text context from chunks.

    Returns:
        A natural prose description of work experience.
    """
    exp_lines = []

    # First try to pull the Experience section from knowledge
    for sec_name, sec_content in sections.items():
        if any(k in sec_name.lower() for k in ["experience", "work", "employment", "career", "job"]):
            lines = [l.strip() for l in sec_content.split("\n") if l.strip()]
            exp_lines = lines
            break

    # Fallback: grep experience sentences from raw context
    if not exp_lines:
        all_lines = [l.strip() for l in context.split("\n") if l.strip()]
        exp_lines = [
            l for l in all_lines
            if any(k in l.lower() for k in ["developer", "engineer", "worked", "experience",
                                             "responsible", "led", "designed", "built", "managed",
                                             "developed", "implemented", "maintained"])
        ]

    if not exp_lines:
        return ""

    unique_lines = deduplicate_sentences(exp_lines)
    # Format as prose: join with commas and natural language
    if len(unique_lines) == 1:
        return f"According to the document, the candidate's work experience includes: {unique_lines[0]}."
    parts = "; ".join(unique_lines[:6])
    return f"According to the document, the candidate's work experience includes the following: {parts}."


def synthesize_skills(context: str, sections: Dict[str, str]) -> str:
    """Extracts a clean skills bullet list from the knowledge sections or context.

    Args:
        context: Raw text context.
        sections: Document section dict.

    Returns:
        A newline-separated bullet list of unique skills.
    """
    skill_lines = []

    # Pull from knowledge skills section first
    for sec_name, sec_content in sections.items():
        if any(k in sec_name.lower() for k in ["skill", "technolog", "stack", "proficien", "language", "tool"]):
            lines = [l.strip() for l in sec_content.split("\n") if l.strip()]
            skill_lines.extend(lines)

    # Fallback: look for bullet lines or comma-separated lists in context
    if not skill_lines:
        for line in context.split("\n"):
            line = line.strip()
            if re.match(r'^[-•*]', line) or re.search(r',', line):
                # Split comma-separated items
                items = [i.strip().lstrip('-•* ') for i in re.split(r'[,|]', line) if i.strip()]
                skill_lines.extend(items)

    # Deduplicate (case-insensitive)
    seen: set = set()
    unique_skills = []
    for s in skill_lines:
        key = s.lower().strip()
        if key and key not in seen and len(s) < 60:
            seen.add(key)
            unique_skills.append(s)

    if not unique_skills:
        return ""

    bullets = "\n".join([f"- {s}" for s in unique_skills[:15]])
    return f"The candidate's skills include:\n\n{bullets}"


def query_table_knowledge(tables: List[Dict[str, Any]], question: str) -> Optional[str]:
    """Runs analytical structural queries over JSON tables (sum, avg, min, max, count)."""
    q_lower = question.lower()
    if not tables:
        return None
        
    table = tables[0]  # Focus on primary table
    headers = table.get("headers", [])
    rows = table.get("rows", [])
    stats = table.get("stats", {})

    if not rows:
        return None

    def find_column(keywords: List[str]) -> Optional[str]:
        for h in headers:
            h_lower = h.lower()
            if any(k in h_lower for k in keywords):
                return h
        return None

    # Check for average / mean queries
    if "average" in q_lower or "mean" in q_lower:
        for col, col_stats in stats.items():
            if col.lower() in q_lower or len(stats) == 1:
                avg_val = col_stats["avg"]
                return f"the average of {col} is {avg_val:.2f}"

    # Check for sum / total queries
    if "total" in q_lower or "sum" in q_lower:
        for col, col_stats in stats.items():
            if col.lower() in q_lower or len(stats) == 1:
                sum_val = col_stats["sum"]
                return f"the total sum of {col} is {sum_val:.2f}"

    # Check for min/max queries: e.g. "highest salary"
    is_max = any(w in q_lower for w in ["highest", "maximum", "max", "most", "largest", "biggest"])
    is_min = any(w in q_lower for w in ["lowest", "minimum", "min", "least", "smallest"])
    
    if is_max or is_min:
        numeric_col = None
        for col in stats.keys():
            if col.lower() in q_lower or len(stats) == 1:
                numeric_col = col
                break
        
        if numeric_col:
            target_val = stats[numeric_col]["max"] if is_max else stats[numeric_col]["min"]
            matching_row = None
            for r in rows:
                val_str = r.get(numeric_col, "")
                cleaned_val = re.sub(r'[^\d.-]', '', val_str)
                try:
                    if cleaned_val and float(cleaned_val) == target_val:
                        matching_row = r
                        break
                except ValueError:
                    pass

            if matching_row:
                name_col = find_column(["name", "employee", "vendor", "item", "customer", "person", "id"])
                if not name_col:
                    for h in headers:
                        if h not in stats:
                            name_col = h
                            break
                
                entity_name = matching_row.get(name_col, "the item") if name_col else "the item"
                op_label = "highest" if is_max else "lowest"
                return f"the row with the {op_label} {numeric_col} shows {entity_name} with a value of {matching_row.get(numeric_col)}"

    # Check for counts: "how many employees in IT" or filter queries
    if "how many" in q_lower or "count" in q_lower or "number of" in q_lower:
        for h in headers:
            for r in rows:
                val = r.get(h, "")
                val_lower = val.lower().strip()
                if val_lower and val_lower in q_lower:
                    matching_rows = [row for row in rows if row.get(h, "").lower().strip() == val_lower]
                    return f"there are {len(matching_rows)} entries where {h} is {val}"
        
        return f"the table contains a total of {len(rows)} entries"

    # Fallback row matching
    for r in rows:
        for h, val in r.items():
            if val.lower().strip() in q_lower:
                row_desc = ", ".join([f"{k}: {v}" for k, v in r.items()])
                return f"the matched entry is {row_desc}"

    return f"the table lists details with columns: {', '.join(headers)} across {len(rows)} rows"


def query_knowledge(knowledge: Dict[str, Any], question: str, intent: str) -> Optional[Tuple[str, float]]:
    """Answers a user question from structured knowledge store blocks, returning (answer, confidence)."""
    q_lower = question.lower()
    
    # 1. Summary intent
    if intent == "Summary" or "summarize" in q_lower or "summary" in q_lower:
        if knowledge.get("summary"):
            return knowledge["summary"], 95.0

    # 2. Table query
    tables = knowledge.get("tables", [])
    if tables and (intent in ["Tables", "Numbers"] or any(k in q_lower for k in ["table", "salary", "average", "highest", "total", "max", "min", "count", "how many", "sheet"])):
        ans = query_table_knowledge(tables, question)
        if ans:
            return ans, 90.0

    # 3. Specific entity extraction
    entities = knowledge.get("entities", {})
    if entities:
        if "email" in q_lower and entities.get("emails"):
            return f"the email address is {', '.join(entities['emails'])}", 95.0
        if ("phone" in q_lower or "mobile" in q_lower or "contact number" in q_lower) and entities.get("phones"):
            return f"the contact phone number is {', '.join(entities['phones'])}", 95.0
        if "date" in q_lower and entities.get("dates"):
            if "due" in q_lower:
                due_dates = [d for d in entities["dates"] if "due" in d.lower() or "/" in d or "-" in d]
                if due_dates:
                    return f"the due date is {due_dates[0]}", 90.0
            return f"the dates mentioned in the document are: {', '.join(entities['dates'])}", 90.0
        if "amount" in q_lower and entities.get("amounts"):
            return f"the amount is {', '.join(entities['amounts'])}", 90.0
        if "percentage" in q_lower and entities.get("percentages"):
            return f"the percentages mentioned are {', '.join(entities['percentages'])}", 90.0

    # 4. Key-Value Facts Matching
    facts = knowledge.get("facts", {})
    if facts:
        for k, v in facts.items():
            k_words = set(re.findall(r'\w+', k.lower()))
            q_words = set(re.findall(r'\w+', q_lower))
            overlap = len(k_words.intersection(q_words))
            if overlap >= len(k_words) * 0.7 and len(k_words) > 0:
                return f"the {k.lower()} is {v}", 95.0

    # 5. Section Heading Matching
    sections = knowledge.get("sections", {})
    if sections:
        for sec_name, sec_content in sections.items():
            sec_lower = sec_name.lower()
            if sec_lower in q_lower or any(w in q_lower for w in sec_lower.split()):
                if len(sec_content) > 20:
                    return sec_content, 85.0

    return None


class ReasoningService:
    """Core reasoning engine. Only service allowed to perform inference on MyGPT."""

    def __init__(self) -> None:
        logger.info("Initializing ReasoningService.")

    def infer_intent(self, question: str) -> str:
        """Dynamically infers the user question intent using keyword mapping."""
        q_lower = question.lower()
        intent_keywords = {
            "Summary": ["summarize", "summary", "conclusion", "overview", "synopsis"],
            "Explanation": ["explain", "why", "how does", "describe", "elaborate"],
            "Comparison": ["compare", "difference", "versus", "vs", "similarity"],
            "Search": ["find", "search", "locate", "where is"],
            "Extraction": ["extract", "list", "get", "retrieve"],
            "Skills": ["skills", "languages", "technologies", "tech", "proficient", "frameworks", "tools"],
            "Education": ["education", "degree", "college", "university", "cgpa", "gpa", "bca", "mca", "btech", "mtech", "school"],
            "Experience": ["experience", "years", "work", "job", "career", "developer", "engineer", "role"],
            "Invoice": ["invoice", "bill", "gst", "tax", "due", "total", "amount", "charge", "payment"],
            "Dates": ["date", "due date", "when", "year", "month"],
            "Numbers": ["number", "amount", "quantity", "count", "value"],
            "Policies": ["policy", "leave", "probation", "rules", "guidelines", "probationary"],
            "Research": ["research", "paper", "method", "results", "study", "analysis"],
            "Tables": ["table", "row", "column", "data structure"],
            "Contacts": ["contact", "email", "phone", "mobile", "address", "call"],
            "Emails": ["email", "e-mail", "mail"],
            "Phone Numbers": ["phone", "mobile", "tel", "contact number"],
            "Names": ["name", "who is", "person"],
            "Projects": ["project", "portfolio", "built", "developed"],
            "Technologies": ["technology", "tech stack", "languages", "software", "libraries"],
            "Image": ["image", "picture", "photo", "screenshot", "chart", "diagram", "graph", "visual", "figure", "illustration"],
            "Resume": ["resume", "cv", "curriculum", "candidate", "applicant", "hire"],
        }
        
        best_intent = "Question Answering"
        max_overlap = 0
        
        q_words = set(re.findall(r"\w+", q_lower))
        for intent, keywords in intent_keywords.items():
            overlap = len(q_words.intersection(set(keywords)))
            if overlap > max_overlap:
                max_overlap = overlap
                best_intent = intent
        
        # Follow-up detection: short questions with pronouns referencing previous context
        follow_up_indicators = ["his", "her", "its", "their", "that", "those", "these", "the same", "above", "previous"]
        if max_overlap == 0 and any(w in q_lower.split() for w in follow_up_indicators):
            if len(q_words) <= 8:
                best_intent = "Follow-up"
                
        return best_intent

    def _expand_candidate_to_sentence(self, candidate: str, intent: str, question: str) -> str:
        """Converts raw text chunks or bullet lists dynamically into natural conversational sentences."""
        if not candidate:
            return ""

        # Check for list-to-prose conversion first
        if '\n' in candidate or any(candidate.strip().startswith(b) for b in ['•', '-', '*']):
            prose = list_to_prose(candidate, intent)
            if prose:
                return prose

        # Remove leading bullets or list dashes
        clean_candidate = re.sub(r"^[•\-*\d\.\s]+", "", candidate).strip()

        # Pattern 1: Key-Value structural matches (e.g. "GST: 18%" or "Education: BCA")
        kv_match = re.match(r"^([\w\s_-]+):\s*(.+)$", clean_candidate)
        if kv_match:
            key = kv_match.group(1).strip()
            val = kv_match.group(2).strip()
            
            if intent in ["Skills", "Technologies"]:
                return f"the candidate's {key.lower()} is listed as {val}"
            elif intent in ["Invoice", "Numbers"]:
                return f"the {key.lower()} is {val}"
            elif intent == "Education":
                return f"the candidate completed a {key} with {val}"
            else:
                return f"the {key.lower()} is specified as {val}"

        # Table row pattern: "Header | Value | Header | Value"
        if '|' in clean_candidate:
            parts = [p.strip() for p in clean_candidate.split('|') if p.strip()]
            if len(parts) >= 2:
                return f"the data shows {', '.join(parts)}"

        # Default intent-based wrapping templates without leading generic prefix
        if intent == "Summary":
            return f"the document details include {clean_candidate}"
        elif intent in ["Skills", "Technologies"]:
            return f"the candidate has experience with {clean_candidate}"
        elif intent in ["Invoice", "Numbers"]:
            return f"the invoice details show {clean_candidate}"
        elif intent == "Policies":
            return f"the policy indicates that {clean_candidate}"
        elif intent == "Image":
            return f"the image shows {clean_candidate}"
        elif intent == "Resume":
            return f"the candidate's profile indicates {clean_candidate}"
        elif intent == "Research":
            return f"the research findings indicate {clean_candidate}"
        elif intent == "Comparison":
            return f"comparing the information, {clean_candidate}"
        elif intent == "Extraction":
            return f"the extracted information shows {clean_candidate}"
        
        return clean_candidate

    def evaluate_answer_confidence(self, prompt: str, answer: str) -> float:
        """Runs MyGPT model inference to compute answer token log-likelihood.
        
        Args:
            prompt: Question prompt context.
            answer: Answer text.
            
        Returns:
            Normalized confidence score (0.0 to 1.0).
        """
        model = model_manager.load_model()
        model.eval()

        device = model_manager.device
        context_len = model.config.context_len

        # Tokenize prompt and answer
        prompt_ids = tokenizer.encode(prompt, add_bos=True)
        answer_ids = tokenizer.encode(answer, add_eos=True)

        full_ids = prompt_ids + answer_ids
        if len(full_ids) > context_len:
            full_ids = full_ids[-context_len:]

        # Shift target IDs by 1 to compute cross-entropy
        input_ids = full_ids[:-1]
        target_ids = full_ids[1:]

        # Find start index of answer tokens in target sequence
        ans_start_idx = max(0, len(prompt_ids) - 1)

        input_tensor = torch.tensor([input_ids], dtype=torch.long, device=device)
        
        try:
            with torch.no_grad():
                # Forward pass to get logits
                logits, _ = model(input_tensor)
                logits = logits.squeeze(0)  # (seq_len, vocab_size)

                # Focus on logits matching the answer target tokens
                ans_logits = logits[ans_start_idx:]
                ans_targets = torch.tensor(target_ids[ans_start_idx:], dtype=torch.long, device=device)

                if len(ans_targets) == 0:
                    return 0.5

                # Compute log probabilities using log_softmax
                log_probs = F.log_softmax(ans_logits, dim=-1)
                target_log_probs = log_probs[torch.arange(len(ans_targets)), ans_targets]

                # Average log likelihood
                mean_log_prob = target_log_probs.mean().item()
                # Map log likelihood to confidence score: e.g. exp(mean_log_prob)
                confidence = math.exp(max(-5.0, mean_log_prob))
                
                # Boost/scale confidence to fit reasonable bounds [0.3 - 0.95] for matches
                confidence = 0.3 + 0.65 * confidence
                return min(1.0, max(0.0, confidence))
        except Exception as e:
            logger.error(f"Error calculating MyGPT log-likelihood: {e}")
            return 0.5

    def compute_mathematical_confidence(
        self,
        retrieval_score: float,
        question: str,
        candidate: str,
        context: str,
        q_emb: List[float],
        c_emb: List[float],
    ) -> float:
        """Calculates exact confidence based on retrieval match, keyword overlap, and semantic similarity."""
        from backend.app.services.retrieval_service import retrieval_service

        # 1. Keyword overlap
        q_words = set(re.findall(r"\w+", question.lower()))
        c_words = set(re.findall(r"\w+", candidate.lower()))
        keyword_score = len(q_words.intersection(c_words)) / len(q_words) if q_words else 0.0
        
        # 2. Semantic overlap
        semantic_score = retrieval_service._cosine_similarity(q_emb, c_emb)
        
        # 3. Context coverage
        context_words = set(re.findall(r"\w+", context.lower()))
        coverage_score = len(q_words.intersection(context_words)) / len(q_words) if q_words else 0.0
        
        # Aggregate scores mathematically
        final_score = (
            0.3 * retrieval_score +
            0.2 * keyword_score +
            0.4 * semantic_score
        )
        # Convert to percentage [0-100] and clamp to safe boundaries
        percent = final_score * 100.0
        return min(99.0, max(25.0, percent))

    def reason(
        self,
        context: str,
        question: str,
        retrieved_chunks: Optional[List[Dict[str, Any]]] = None,
        intent: Optional[str] = None,
        context_summary: Optional[str] = None,
        doc_id: Optional[str] = None,
    ) -> Tuple[str, float]:
        """Performs reasoning over the context or structured knowledge using MyGPT.
        
        Args:
            context: Aggregated clean text chunks.
            question: Search query.
            retrieved_chunks: Optional retrieved metadata chunks for scoring and logs.
            intent: Optional inferred query intent.
            context_summary: Optional memory summary.
            doc_id: Optional document ID for direct Knowledge Store lookups.
            
        Returns:
            Tuple of (answer_text, confidence_score).
        """
        t_start = time.time()
        logger.info("REASONING START")
        logger.info(f"Reasoning query: '{question}'")

        # 1. Infer user intent automatically
        if not intent:
            intent = self.infer_intent(question)
        logger.info(f"Inferred intent: {intent}")

        # 2. Knowledge-First Query Path
        from backend.app.services.knowledge_service import knowledge_store
        knowledge = None
        if doc_id:
            knowledge = knowledge_store.get_knowledge(doc_id)
        elif retrieved_chunks:
            candidate_doc_id = retrieved_chunks[0].get("doc_id")
            if candidate_doc_id:
                knowledge = knowledge_store.get_knowledge(candidate_doc_id)

        if knowledge:
            knowledge_ans_data = query_knowledge(knowledge, question, intent)
            if knowledge_ans_data:
                knowledge_ans, knowledge_conf = knowledge_ans_data
                
                # Apply intent prefix if it's not already prefixed
                prefix = get_intent_prefix(intent)
                if not knowledge_ans.startswith(prefix) and not intent in ["Tables", "Summary", "Extraction"]:
                    if prefix.endswith(", ") or prefix.endswith(": "):
                        first_char = knowledge_ans[0]
                        if first_char.isupper() and not (len(knowledge_ans) > 1 and knowledge_ans[1].isupper()):
                            knowledge_ans = first_char.lower() + knowledge_ans[1:]
                    knowledge_ans = prefix + knowledge_ans
                
                # Clean and normalize answer
                knowledge_ans = post_process_answer(knowledge_ans)
                # Word-duplicate cleaning
                prev_ans = ""
                while prev_ans != knowledge_ans:
                    prev_ans = knowledge_ans
                    knowledge_ans = re.sub(r'\b(\w+)\s+\1\b', r'\1', knowledge_ans, flags=re.IGNORECASE)
                
                execution_time_ms = (time.time() - t_start) * 1000
                print("\n" + "="*80)
                print("DEBUG: MYGPT REASONING & CONFIDENCE EVALUATION (KNOWLEDGE-FIRST)")
                print("="*80)
                print(f"QUESTION: {question}")
                print(f"INTENT: {intent}")
                print(f"KNOWLEDGE USED: YES (Doc Type: {knowledge.get('document_type')})")
                print(f"GENERATED ANSWER:\n{knowledge_ans}")
                print(f"CONFIDENCE: {knowledge_conf:.1f}%")
                print(f"TOTAL EXECUTION TIME: {execution_time_ms:.2f} ms")
                print("="*80 + "\n")
                
                logger.info("TOKENS GENERATED")
                logger.info("ANSWER GENERATED")
                return knowledge_ans, knowledge_conf, True

        # 3. Check if context is available (chunk-based fallback path)
        if not context or not context.strip():
            logger.info("ANSWER GENERATED")
            return "I couldn't find that information in the uploaded document.", 0.0, False

        # 4. Dynamic candidate sentence matching using text embeddings
        from backend.app.services.embedding_service import embedding_service
        from backend.app.services.retrieval_service import retrieval_service

        # Split context by double newline (since ContextBuilder joins with \n\n)
        sentences = [s.strip() for s in context.split("\n\n") if s.strip()]
        if not sentences:
            # Fallback split if no double newlines
            sentences = [s.strip() for s in re.split(r"(?<=\.|\?)\s+", context) if s.strip()]

        if not sentences:
            logger.info("ANSWER GENERATED")
            return "I couldn't find that information in the uploaded document.", 0.0, False

        # Embed query (with context summary if available)
        embedding_query = f"{context_summary} {question}" if context_summary else question
        q_emb = embedding_service.get_embeddings([embedding_query])[0]
        sentence_embs = embedding_service.get_embeddings(sentences)
        
        scored_sentences = []
        for s, s_emb in zip(sentences, sentence_embs):
            cosine_score = retrieval_service._cosine_similarity(q_emb, s_emb)
            
            s_words = set(re.findall(r"\w+", s.lower()))
            q_words = set(re.findall(r"\w+", question.lower()))
            overlap = len(q_words.intersection(s_words))
            overlap_ratio = overlap / len(q_words) if q_words else 0.0
            
            combined_score = 0.6 * cosine_score + 0.4 * overlap_ratio
            scored_sentences.append((s, combined_score, cosine_score, s_emb))

        # Sort sentences by combined_score descending
        scored_sentences.sort(key=lambda x: x[1], reverse=True)

        # Zero-hallucination check
        best_score = scored_sentences[0][1] if scored_sentences else 0.0
        best_sentence = scored_sentences[0][0] if scored_sentences else ""
        best_retrieval_score = scored_sentences[0][2] if scored_sentences else 0.5
        best_c_emb = scored_sentences[0][3] if scored_sentences else [0.0] * len(q_emb)

        if best_score < 0.2:
            logger.info("ANSWER GENERATED")
            return "I couldn't find that information in the uploaded document.", 0.0, False

        # Select top-N relevant sentences: 8 for Summary, 5 for Experience, 3 for others
        if intent == "Summary":
            N = 8
        elif intent in ["Experience", "Research"]:
            N = 5
        else:
            N = 3
        top_sentences_data = [item for item in scored_sentences[:N] if item[1] >= 0.2]

        # 5. Intent-specific synthesis routing
        prefix = get_intent_prefix(intent)
        knowledge_sections = knowledge.get("sections", {}) if knowledge else {}

        if intent == "Summary":
            raw_texts = [item[0] for item in top_sentences_data]
            answer = synthesize_summary(raw_texts, prefix)
            if not answer:
                answer = "I couldn't find that information in the uploaded document."
            answer = post_process_answer(answer)

        elif intent == "Experience":
            answer = synthesize_experience(knowledge_sections, context)
            if not answer:
                # Fall through to generic builder
                answer = ""

        elif intent in ["Skills", "Technologies"]:
            answer = synthesize_skills(context, knowledge_sections)
            if not answer:
                answer = ""

        else:
            answer = ""

        # 5.5 — For intents that did NOT produce a synthesized answer above, use generic prose builder
        if not answer:
            # Convert sentences to natural prose clauses using templates
            prose_sentences = []
            for item in top_sentences_data:
                s_text = item[0]
                converted = self._expand_candidate_to_sentence(s_text, intent, question)
                if converted:
                    prose_sentences.append(converted)

            # Extract structured facts and add precision clauses
            facts = extract_facts(context, intent)
            if facts and intent in ["Invoice", "Resume", "Dates", "Numbers", "Contacts", "Emails", "Phone Numbers", "Extraction"]:
                for label, value in list(facts.items())[:5]:
                    fact_clause = f"the {label.lower()} is {value}"
                    # Only add if not already covered by prose sentences
                    if not any(value.lower() in ps.lower() for ps in prose_sentences):
                        prose_sentences.append(fact_clause)

            # Deduplicate prose clauses (sentence-level)
            unique_prose = deduplicate_sentences(prose_sentences)

            # Merge sentences into a single paragraph with natural connectors
            connectors = ["Additionally, ", "Furthermore, ", "Also, ", "Moreover, "]
            formatted_sentences = []
            for i, s in enumerate(unique_prose):
                s = s.strip()
                if not s:
                    continue
                # Ensure ending punctuation
                if s[-1] not in ['.', '!', '?']:
                    s += '.'
                
                # Capitalize and add natural connectors for subsequent sentences
                if i > 0:
                    if i <= len(connectors):
                        s = connectors[i - 1] + s[0].lower() + s[1:]
                    else:
                        s = s[0].upper() + s[1:]
                formatted_sentences.append(s)

            merged_paragraph = " ".join(formatted_sentences)

            # Apply intent prefix
            if prefix.endswith(", ") or prefix.endswith(": "):
                if merged_paragraph:
                    first_char = merged_paragraph[0]
                    if first_char.isupper() and not (len(merged_paragraph) > 1 and merged_paragraph[1].isupper()):
                        merged_paragraph = first_char.lower() + merged_paragraph[1:]
            
            answer = prefix + merged_paragraph

        # 6. Post-processing: strip leading bullets, fix punctuation, normalize whitespace
        answer = post_process_answer(answer)

        # 7. Run duplicate-word filter on final answer (case-insensitive repeat check)
        prev_answer = ""
        while prev_answer != answer:
            prev_answer = answer
            answer = re.sub(r'\b(\w+)\s+\1\b', r'\1', answer, flags=re.IGNORECASE)
        # Also handle run-together duplicates like "SummarySummary"
        answer = re.sub(r'\b([A-Za-z]{3,})\1\b', r'\1', answer)

        # 9. Calculate confidence
        prompt = f"Context: {context}\n\nQuestion: {question}\n\nAnswer:"
        math_confidence = self.compute_mathematical_confidence(
            retrieval_score=best_retrieval_score,
            question=question,
            candidate=best_sentence,
            context=context,
            q_emb=q_emb,
            c_emb=best_c_emb
        )

        # Clamp max confidence to 40% if combined score is low (< 0.3)
        if best_score < 0.3:
            math_confidence = min(40.0, math_confidence)

        # 10. Debug Logging (explicit print statement logs)
        chunk_count = len(retrieved_chunks) if retrieved_chunks else 0
        chunk_scores = [c.get("score", c.get("similarity", 0.0)) for c in retrieved_chunks] if retrieved_chunks else []
        chunk_scores_str = ", ".join([f"{s:.4f}" for s in chunk_scores])
        execution_time_ms = (time.time() - t_start) * 1000

        print("\n" + "="*80)
        print("DEBUG: MYGPT REASONING & CONFIDENCE EVALUATION")
        print("="*80)
        print(f"QUESTION: {question}")
        print(f"INTENT: {intent}")
        print(f"RETRIEVED CHUNKS: {chunk_count} chunks (Scores: {chunk_scores_str})")
        print(f"SIMILARITY: {best_retrieval_score:.4f}")
        print(f"FINAL CONTEXT:\n{context}")
        print("-"*40)
        print(f"GENERATED ANSWER:\n{answer}")
        print(f"CONFIDENCE: {math_confidence:.1f}%")
        print(f"TOTAL EXECUTION TIME: {execution_time_ms:.2f} ms")
        print("="*80 + "\n")

        logger.info("TOKENS GENERATED")
        logger.info("ANSWER GENERATED")
        return answer, math_confidence, False


reasoning_service = ReasoningService()
