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
        q_words = set(re.findall(r"\w+", q_lower))
        
        intent_keywords = {
            "Summary": ["summarize", "summary", "conclusion", "overview", "synopsis", "brief", "abstract", "takeaways"],
            "Explanation": ["explain", "why", "how does", "describe", "elaborate", "explanation"],
            "Comparison": ["compare", "difference", "versus", "vs", "similarity", "comparison"],
            "Projects": ["project", "portfolio", "built", "developed", "projects", "works", "applications"],
            "Tax": ["gst", "vat", "tax", "tax rate", "tax amount"],
            "Dates": ["date", "due date", "when", "year", "month", "invoice date", "payment date"],
            "Count": ["count", "how many", "number of", "total count", "transactions"],
            "Highest": ["highest", "maximum", "max", "most", "largest", "biggest"],
            "Lowest": ["lowest", "minimum", "min", "least", "smallest"],
            "Average": ["average", "mean", "avg"],
            "Total": ["total", "sum", "total sum", "aggregate", "total amount", "total due", "grand total"],
            "Emails": ["email", "e-mail", "mail address", "email address"],
            "Phone Numbers": ["phone", "mobile", "tel", "contact number", "cell", "telephone", "phone number"],
            "Names": ["name", "who is the candidate", "who is", "person name", "candidate's name", "candidate name"],
            "Invoice": ["invoice", "bill", "gst", "tax", "due", "total", "amount", "charge", "payment", "subtotal", "invoice amount", "totals"],
            "Skills": ["skills", "languages", "stack", "frameworks", "tools"],
            "Technologies": ["technologies", "technology", "tech stack"],
            "Experience": ["experience", "employment", "work history", "job", "career"],
            "Education": ["education", "degree", "university", "college", "academic"],
            "Certifications": ["certifications", "certificate", "award"],
            "Image": ["image", "picture", "photo", "screenshot", "chart", "diagram", "graph", "visual", "figure", "illustration"],
            "Resume": ["resume", "cv", "curriculum", "candidate", "applicant", "hire"],
            "Policies": ["policy", "leave", "probation", "rules", "guidelines", "probationary"],
            "Research": ["research", "paper", "method", "results", "study", "analysis"],
        }
        
        best_intent = "Question Answering"
        max_overlap = 0
        
        for intent, keywords in intent_keywords.items():
            overlap = 0
            for kw in keywords:
                if " " in kw:
                    if kw in q_lower:
                        overlap += 2
                else:
                    if kw in q_words:
                        overlap += 1
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
            
            if intent in ["SKILLS", "TECHNOLOGIES"]:
                return f"the candidate's {key.lower()} is listed as {val}"
            elif intent in ["TOTAL", "TAX", "Invoice", "Numbers"]:
                return f"the {key.lower()} is {val}"
            elif intent == "EDUCATION":
                return f"the candidate completed a {key} with {val}"
            else:
                return f"the {key.lower()} is specified as {val}"

        # Table row pattern: "Header | Value | Header | Value"
        if '|' in clean_candidate:
            parts = [p.strip() for p in clean_candidate.split('|') if p.strip()]
            if len(parts) >= 2:
                return f"the data shows {', '.join(parts)}"

        # Default intent-based wrapping templates without leading generic prefix
        if intent == "SUMMARY":
            return f"the document details include {clean_candidate}"
        elif intent in ["SKILLS", "TECHNOLOGIES"]:
            return f"the candidate has experience with {clean_candidate}"
        elif intent in ["TOTAL", "TAX", "Invoice", "Numbers"]:
            return f"the invoice details show {clean_candidate}"
        elif intent == "Policies":
            return f"the policy indicates that {clean_candidate}"
        elif intent == "Image":
            return f"the image shows {clean_candidate}"
        elif intent == "Resume":
            return f"the candidate's profile indicates {clean_candidate}"
        elif intent == "Research":
            return f"the research findings indicate {clean_candidate}"
        elif intent == "COMPARISON":
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

    def _clean_token_repetitions(self, text: str) -> str:
        """Robust formatting helper to eliminate run-together duplicates and repeated tokens."""
        if not text:
            return ""
        # 1. Clean run-together consecutive duplicate words like "SummarySummary", "DeveloperDeveloper"
        # Match word sequences of length 3+ repeated consecutively without spaces
        text = re.sub(r'\b([A-Za-z]{3,})\1\b', r'\1', text)
        
        # 2. Clean space-separated repeated tokens (e.g. "ororororor" or "the the")
        prev = None
        while prev != text:
            prev = text
            text = re.sub(r'\b(\w+)\s+\1\b', r'\1', text, flags=re.IGNORECASE)
            
        # 3. Clean spaces
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def reason(
        self,
        context: str,
        question: str,
        retrieved_chunks: Optional[List[Dict[str, Any]]] = None,
        intent: Optional[str] = None,
        context_summary: Optional[str] = None,
        doc_id: Optional[str] = None,
    ) -> Tuple[str, float, bool]:
        """Performs reasoning over the context or structured knowledge using MyGPT.
        
        Args:
            context: Aggregated clean text chunks.
            question: Search query.
            retrieved_chunks: Optional retrieved metadata chunks for scoring and logs.
            intent: Optional inferred query intent.
            context_summary: Optional memory summary.
            doc_id: Optional document ID for direct Knowledge Store lookups.
            
        Returns:
            Tuple of (answer_text, confidence_score, knowledge_used).
        """
        import json
        t_start = time.time()
        logger.info("REASONING START")
        logger.info(f"Reasoning query: '{question}'")

        # 1. Question Understanding Engine (semantic intent classification)
        if not intent or intent == "Question Answering":
            intent = self.infer_intent(question)
        logger.info(f"Semantic Intent: {intent}")

        # 2. Ingest or load Knowledge Object
        from backend.app.services.knowledge_service import knowledge_store, knowledge_builder
        knowledge = None
        if doc_id:
            knowledge = knowledge_store.get_knowledge(doc_id)
        elif retrieved_chunks:
            candidate_doc_id = retrieved_chunks[0].get("doc_id")
            if candidate_doc_id:
                knowledge = knowledge_store.get_knowledge(candidate_doc_id)

        if not knowledge and context:
            # Build temporary knowledge on the fly for reasoning/tests
            knowledge = knowledge_builder.build_knowledge(context, ".txt")

        doc_type = knowledge.get("document_type", "Generic") if knowledge else "Generic"
        facts = knowledge.get("facts", {}) if knowledge else {}
        entities = knowledge.get("entities", {}) if knowledge else {}
        tables = knowledge.get("tables", []) if knowledge else []

        # 3. Conversation Memory pronoun resolution & context merging (Phase 8 & 5)
        # If intent is FOLLOW_UP, resolve pronoun context
        intent_upper = intent.upper().replace("-", "_").replace(" ", "_") if intent else "GENERAL"
        if intent_upper == "FOLLOW_UP" and context_summary:
            if "skills" in question.lower() or "technologies" in question.lower():
                intent_upper = "SKILLS"
            elif "project" in question.lower():
                intent_upper = "PROJECTS"
            elif "experience" in question.lower() or "work" in question.lower():
                intent_upper = "EXPERIENCE"
            elif "education" in question.lower() or "degree" in question.lower():
                intent_upper = "EDUCATION"
            else:
                intent_upper = "GENERAL"

        # 4. Context Reasoner & Document Specialists routing (Phase 5 & 11)
        reasoning_steps = []
        raw_ans = ""
        knowledge_used = False

        q_lower = question.lower()
        q_words = set(re.findall(r"\w+", q_lower))

        def clean_val(val):
            if not val:
                return ""
            if isinstance(val, list):
                return ", ".join(val)
            val = str(val).strip()
            return val

        # Specialized reasoning modules (Phase 11)
        if doc_type == "Resume":
            reasoning_steps.append("Executing ResumeSpecialist reasoning pathway.")
            if (intent_upper in ["PHONE", "PHONE_NUMBERS"] or any(w in q_lower for w in ["phone", "mobile", "cell", "contact"])) and facts.get("phones"):
                raw_ans = clean_val(facts["phones"][0])
                knowledge_used = True
            elif (intent_upper in ["EMAIL", "EMAILS"] or any(w in q_lower for w in ["email", "e-mail", "mail"])) and facts.get("emails"):
                raw_ans = clean_val(facts["emails"][0])
                knowledge_used = True
            elif (intent_upper in ["NAME", "NAMES"] or any(w in q_lower for w in ["name", "who is"])) and facts.get("name"):
                raw_ans = clean_val(facts["name"])
                knowledge_used = True
            elif (intent_upper == "SKILLS" or "skills" in q_lower) and facts.get("skills"):
                raw_ans = ", ".join(facts["skills"])
                knowledge_used = True
            elif (intent_upper == "TECHNOLOGIES" or "technolog" in q_lower) and facts.get("technologies"):
                raw_ans = ", ".join(facts["technologies"])
                knowledge_used = True
            elif (intent_upper == "PROJECTS" or "project" in q_lower) and facts.get("projects"):
                raw_ans = clean_val(facts["projects"])
                knowledge_used = True
            elif (intent_upper == "EDUCATION" or any(w in q_lower for w in ["education", "degree", "university", "college"])) and facts.get("education"):
                raw_ans = clean_val(facts["education"])
                knowledge_used = True
            elif (intent_upper == "CERTIFICATIONS" or "certificat" in q_lower) and facts.get("certifications"):
                raw_ans = clean_val(facts["certifications"])
                knowledge_used = True
            elif (intent_upper == "EXPERIENCE" or "experience" in q_lower) and facts.get("experience"):
                raw_ans = clean_val(facts["experience"])
                knowledge_used = True
            elif (intent_upper == "SUMMARY" or "summary" in q_lower) and facts.get("summary"):
                raw_ans = clean_val(facts["summary"])
                knowledge_used = True

        elif doc_type == "Invoice":
            reasoning_steps.append("Executing InvoiceSpecialist reasoning pathway.")
            if any(w in q_lower for w in ["invoice number", "invoice #", "inv #", "inv no", "invoice no", "number"]) and facts.get("invoice_number"):
                raw_ans = clean_val(facts["invoice_number"])
                knowledge_used = True
            elif (intent_upper in ["TOTAL", "INVOICE"] or any(w in q_lower for w in ["total", "grand total", "amount", "due"])) and facts.get("grand_total"):
                raw_ans = clean_val(facts["grand_total"])
                knowledge_used = True
            elif (intent_upper == "TAX" or any(w in q_lower for w in ["gst", "vat", "tax"])) and facts.get("gst"):
                raw_ans = clean_val(facts["gst"])
                knowledge_used = True
            elif (intent_upper in ["DATE", "DATES"] or any(w in q_lower for w in ["date", "when"])) and (facts.get("due_date") or facts.get("invoice_date")):
                if "late" in q_lower or "overdue" in q_lower:
                    due_date_str = facts.get("due_date")
                    pmt_status = facts.get("payment_status", "")
                    raw_ans = "Yes, the invoice was overdue or payment was late." if "unpaid" in pmt_status.lower() else "No, it was settled on time."
                else:
                    raw_ans = clean_val(facts.get("due_date") or facts.get("invoice_date"))
                knowledge_used = True
            elif intent_upper == "COUNT" and facts.get("items"):
                raw_ans = str(len(facts["items"]))
                knowledge_used = True

        elif doc_type == "Excel":
            reasoning_steps.append("Executing ExcelSpecialist reasoning pathway.")
            rows = facts.get("rows", [])
            columns = facts.get("columns", [])
            stats = facts.get("statistics", {})

            def find_matching_col():
                for col in columns:
                    if col.lower() in question.lower():
                        return col
                numeric_cols = [c for c in columns if c in stats]
                if numeric_cols:
                    return numeric_cols[0]
                return None

            col = find_matching_col()
            if intent_upper == "COUNT":
                filter_val = None
                filter_col = None
                stopwords = {"how", "many", "employees", "are", "in", "is", "the", "a", "of", "to", "for", "count", "number"}
                for c in columns:
                    for r in rows:
                        val = str(r.get(c, "")).strip()
                        if val.lower() in q_lower and val.lower() not in stopwords:
                            filter_val = val
                            filter_col = c
                            break
                if filter_val and filter_col:
                    matching_rows = [r for r in rows if str(r.get(filter_col, "")).strip().lower() == filter_val.lower()]
                    raw_ans = str(len(matching_rows))
                    reasoning_steps.append(f"Filtered count on {filter_col} = {filter_val}: {raw_ans}")
                else:
                    raw_ans = str(len(rows))
                knowledge_used = True
                
            elif intent_upper == "AVERAGE" and col and col in stats:
                raw_ans = f"{stats[col]['avg']:.2f}"
                if raw_ans.endswith(".00"):
                    raw_ans = raw_ans[:-3]
                knowledge_used = True
                
            elif intent_upper == "TOTAL" and col and col in stats:
                raw_ans = f"{stats[col]['sum']:.2f}"
                if raw_ans.endswith(".00"):
                    raw_ans = raw_ans[:-3]
                knowledge_used = True
                
            elif intent_upper in ["HIGHEST", "LOWEST"] and col and col in stats:
                target_val = stats[col]["max"] if intent_upper == "HIGHEST" else stats[col]["min"]
                matching_rows = []
                for r in rows:
                    val_str = str(r.get(col, ""))
                    cleaned_val = re.sub(r'[^\d.-]', '', val_str)
                    try:
                        if cleaned_val and float(cleaned_val) == target_val:
                            matching_rows.append(r)
                    except ValueError:
                        pass
                
                if matching_rows:
                    if any(w in q_lower for w in ["who", "which", "name", "person", "employee"]):
                        name_col = None
                        for h in columns:
                            if any(k in h.lower() for k in ["name", "employee", "vendor", "customer", "item", "person"]):
                                name_col = h
                                break
                        if not name_col:
                            for h in columns:
                                if h not in stats:
                                    name_col = h
                                    break
                        if name_col:
                            raw_ans = ", ".join(str(r.get(name_col, "")) for r in matching_rows)
                        else:
                            raw_ans = ", ".join(str(r) for r in matching_rows)
                    else:
                        raw_ans = str(target_val)
                else:
                    raw_ans = str(target_val)
                knowledge_used = True

        elif doc_type == "Research Paper":
            reasoning_steps.append("Executing ResearchSpecialist reasoning pathway.")
            if intent_upper == "SUMMARY" and facts.get("abstract"):
                raw_ans = facts["abstract"]
                knowledge_used = True
            elif "conclusion" in question.lower() and facts.get("conclusion"):
                raw_ans = facts["conclusion"]
                knowledge_used = True
            elif "method" in question.lower() and facts.get("methods"):
                raw_ans = facts["methods"]
                knowledge_used = True

        # Fallback to general chunk parsing or keyword search
        if not raw_ans and context:
            reasoning_steps.append("No direct structured fact match found. Searching raw context blocks.")
            
            sections = knowledge.get("sections", {}) if knowledge else {}
            for sec_name, sec_content in sections.items():
                if sec_name.lower() in q_lower:
                    raw_ans = sec_content
                    knowledge_used = True
                    break

            if not raw_ans:
                if intent_upper in ["PHONE", "PHONE_NUMBERS"] and entities.get("phones"):
                    raw_ans = clean_val(entities["phones"][0])
                elif intent_upper in ["EMAIL", "EMAILS"] and entities.get("emails"):
                    raw_ans = clean_val(entities["emails"][0])
                elif intent_upper in ["NAME", "NAMES"] and entities.get("people"):
                    raw_ans = clean_val(entities["people"][0])
                elif intent_upper in ["TOTAL", "INVOICE"] and entities.get("amounts"):
                    raw_ans = clean_val(entities["amounts"][0])

            if not raw_ans:
                clean_context = re.sub(r'\[Page \d+ \| Section: [^\]]+\]', '', context)
                sentences = [s.strip() for s in clean_context.split("\n\n") if s.strip()]
                if sentences:
                    scored_sentences = []
                    for s in sentences:
                        s_words = set(re.findall(r"\w+", s.lower()))
                        overlap = len(q_words.intersection(s_words))
                        scored_sentences.append((s, overlap))
                    scored_sentences.sort(key=lambda x: x[1], reverse=True)
                    if scored_sentences and scored_sentences[0][1] > 0:
                        raw_ans = scored_sentences[0][0]

        # 5. Answer Planner & Natural Language Generator (Phase 6 & 7)
        planned_style = "EXPLANATION"
        if intent_upper in ["PHONE", "PHONE_NUMBERS", "EMAIL", "EMAILS", "NAME", "NAMES", "TOTAL", "INVOICE", "DATE", "DATES", "COUNT", "HIGHEST", "LOWEST", "AVERAGE", "TAX"]:
            planned_style = "SINGLE_VALUE"
        elif intent_upper in ["SKILLS", "TECHNOLOGIES", "PROJECTS", "CERTIFICATIONS"]:
            planned_style = "LIST"
        elif intent_upper == "SUMMARY":
            planned_style = "SUMMARY"
        elif intent_upper == "COMPARISON":
            planned_style = "COMPARISON"

        formatted_ans = ""
        if not raw_ans:
            formatted_ans = "I couldn't find that information in the uploaded document."
            confidence = 0.0
        else:
            if planned_style == "SINGLE_VALUE":
                # Clean leading bullets/punctuation, but do not strip numeric answers!
                formatted_ans = clean_val(raw_ans).strip()
                formatted_ans = re.sub(r"^[•\-*\s]+", "", formatted_ans).strip()
                formatted_ans = re.sub(r'^(?:According to the document|Based on the candidate\'s profile|The contact phone number is|The candidate\'s name is|The email address is|The grand total is|The total amount is|the due date is|the vendor is|the client is|the matched entry is|the data shows|the average of \w+ is|the total sum of \w+ is)\s*[:,\-]?\s*', '', formatted_ans, flags=re.IGNORECASE).strip()
            elif planned_style == "LIST":
                items = []
                if isinstance(raw_ans, list):
                    items = raw_ans
                else:
                    lines = [l.strip() for l in raw_ans.split('\n') if l.strip()]
                    for l in lines:
                        cleaned_line = re.sub(r"^[•\-*\d\.\s]+", "", l).strip()
                        if cleaned_line:
                            items.append(cleaned_line)
                
                unique_items = []
                seen_items = set()
                for item in items:
                    if item.lower() not in seen_items:
                        seen_items.add(item.lower())
                        unique_items.append(item)
                        
                formatted_ans = "\n".join([f"{i+1}. {item}" for i, item in enumerate(unique_items[:10])])
            elif planned_style == "SUMMARY":
                sentences = [s.strip() for s in re.split(r'(?<=\.|\?)\s+', raw_ans) if s.strip()]
                formatted_ans = synthesize_summary(sentences, prefix="")
            elif planned_style == "COMPARISON":
                formatted_ans = f"## Comparison\n{raw_ans}"
            else:
                formatted_ans = post_process_answer(raw_ans)

        # Apply robust heading/token deduplication (Phase 10)
        formatted_ans = self._clean_token_repetitions(formatted_ans)

        # 6. Confidence Engine (Phase 9)
        confidence = 0.0
        if formatted_ans != "I couldn't find that information in the uploaded document.":
            retrieval_factor = 0.9 if retrieved_chunks else 0.5
            coverage_factor = 0.9 if len(formatted_ans) > 2 else 0.2
            
            validation_factor = 1.0
            if intent_upper in ["PHONE", "PHONE_NUMBERS"]:
                if not re.search(r'\d{3,}', formatted_ans):
                    validation_factor = 0.1
            elif intent_upper in ["EMAIL", "EMAILS"]:
                if "@" not in formatted_ans:
                    validation_factor = 0.1
            
            raw_confidence = (0.4 * retrieval_factor + 0.3 * coverage_factor + 0.3 * validation_factor) * 100.0
            confidence = min(99.0, max(25.0, raw_confidence))
            
            if validation_factor <= 0.1:
                formatted_ans = "I couldn't find that information in the uploaded document."
                confidence = 0.0

        # 7. Debug Logging block (Phase 13)
        execution_time_ms = (time.time() - t_start) * 1000
        print("\n" + "="*80)
        print("MYGPT DOCUMENT INTELLIGENCE DEBUG LOGS")
        print("="*80)
        print(f"Document Type:      {doc_type}")
        print(f"Detected Intent:    {intent}")
        print(f"Retrieved Chunks:   {len(retrieved_chunks) if retrieved_chunks else 0} chunks")
        print(f"Extracted Facts:    {json.dumps(facts)[:200] + '...' if facts else 'None'}")
        print(f"Reasoning Steps:    {'; '.join(reasoning_steps)}")
        print(f"Planned Answer Type:{planned_style}")
        print(f"Generated Answer:   {raw_ans[:100] + '...' if len(raw_ans) > 100 else raw_ans}")
        print(f"Formatted Answer:   {formatted_ans}")
        print(f"Confidence:         {confidence:.1f}%")
        print(f"Execution Time:     {execution_time_ms:.2f} ms")
        print("="*80 + "\n")

        return formatted_ans, confidence, knowledge_used


reasoning_service = ReasoningService()
