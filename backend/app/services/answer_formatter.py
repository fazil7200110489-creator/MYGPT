"""Answer Formatter Service for structuring final chat response models.
"""

import re
from typing import Dict, Any, List, Optional
from loguru import logger


def format_list_answer(answer: str) -> str:
    """Converts a prose list sentence into a Markdown bullet points list under ## Details."""
    # Look for a list after a colon or try to find list items
    if ":" in answer:
        parts = answer.split(":", 1)
        intro = parts[0].strip()
        list_part = parts[1].strip()
    elif "is listed as" in answer:
        parts = answer.split("is listed as", 1)
        intro = parts[0].strip() + " is listed as"
        list_part = parts[1].strip()
    elif "experience with" in answer:
        parts = answer.split("experience with", 1)
        intro = parts[0].strip() + " experience with"
        list_part = parts[1].strip()
    else:
        intro = "The document lists the following"
        list_part = answer
        
    # Clean list_part: remove ending periods
    if list_part.endswith("."):
        list_part = list_part[:-1]
        
    # Split by comma or 'and' / 'or'
    raw_items = re.split(r",\s*|\b(?:and|or)\b", list_part)
    cleaned_items = []
    for item in raw_items:
        item = item.strip()
        if item:
            cleaned_items.append(item)
            
    if cleaned_items:
        bullets = "\n".join([f"• {item}" for item in cleaned_items])
        return f"{intro}:\n\n## Details\n{bullets}"
    else:
        return f"## Details\n• {answer}"


def format_extraction_answer(answer: str) -> str:
    """Formats extraction intent results as labeled structured output."""
    # Parse comma-separated fact clauses like "the email is x, the phone is y"
    clauses = re.split(r'(?:Additionally|Furthermore|Also|Moreover),?\s*', answer, flags=re.IGNORECASE)
    lines = []
    for clause in clauses:
        clause = clause.strip()
        if not clause:
            continue
        # Try to extract "the X is Y" pattern
        match = re.match(r'.*?the\s+(.+?)\s+is\s+(.+)', clause, re.IGNORECASE)
        if match:
            label = match.group(1).strip().title()
            value = match.group(2).strip()
            # Strip trailing periods
            value = re.sub(r'\.+$', '', value).strip()
            lines.append(f"**{label}:** {value}")
        else:
            lines.append(f"• {clause}")
    
    if lines:
        return "## Extracted Information\n" + "\n".join(lines)
    return answer


def format_comparison_answer(answer: str) -> str:
    """Formats comparison intent results with section markers."""
    return f"## Comparison\n{answer}"


def format_research_answer(answer: str) -> str:
    """Formats research intent results with structured abstract block."""
    return f"## Research Findings\n{answer}"


class AnswerFormatter:
    """Formats reasoning outputs, references, and dynamics follow-up questions."""

    def _strip_duplicate_sentences(self, text: str) -> str:
        """Final pass: removes near-duplicate sentences and run-together word duplicates.

        Args:
            text: Answer text that may contain repeated sentences or words.

        Returns:
            Clean text with duplicates removed.
        """
        # 1. Fix run-together word duplicates (e.g. "SummarySummary")
        text = re.sub(r'\b([A-Za-z]{3,})\1\b', r'\1', text)

        # 2. Fix space-separated word repetition (e.g. "Developer Developer")
        prev = None
        while prev != text:
            prev = text
            text = re.sub(r'\b(\w+)\s+\1\b', r'\1', text, flags=re.IGNORECASE)

        # 3. Split into sentences and deduplicate at sentence level
        # Preserve markdown structure: don't split bullet lines
        lines = text.split("\n")
        processed_lines = []
        seen_sentences: set = set()

        for line in lines:
            # Don't deduplicate bullet/header lines — handle them as-is
            if line.strip().startswith(("#", "-", "•", "*", "**")):
                processed_lines.append(line)
                continue

            # Split prose lines into sentences
            sentence_parts = re.split(r'(?<=[.!?])\s+', line)
            unique_parts = []
            for part in sentence_parts:
                normalized = re.sub(r'\s+', ' ', part.strip().lower())
                if normalized and normalized not in seen_sentences:
                    seen_sentences.add(normalized)
                    unique_parts.append(part)
            processed_lines.append(" ".join(unique_parts))

        return "\n".join(processed_lines)

    def _generate_suggested_questions(self, answer: str, confidence: float, intent: Optional[str] = None) -> List[str]:
        """Generates suggested follow-up questions dynamically based on answer content and intent."""
        if confidence == 0.0:
            return ["What information is in this document?", "Summarize the document.", "What are the key points?"]

        if not intent:
            intent = "General"

        ans_lower = answer.lower()
        ans_words = set(re.findall(r"\w+", ans_lower))

        # Find significant capitalized words (nouns/entities) from the answer to make questions dynamic
        # Ignore common words
        stopwords = {"the", "and", "a", "of", "to", "in", "is", "that", "it", "he", "was", "for", "on", "are", "as", "with", "his", "they", "i", "at", "be", "this", "have", "from", "or", "one", "had", "by", "word", "but", "not", "what", "all", "were", "we", "when", "your", "can", "said", "there", "use", "an", "each", "which", "she", "do", "how", "their", "if", "will", "up", "other", "about", "out", "many", "then", "them", "these", "so", "some", "her", "would", "make", "like", "him", "into", "has", "look", "more", "write", "go", "see", "number", "no", "way", "could", "people", "my", "than", "first", "water", "been", "call", "who", "oil", "its", "now", "find", "long", "down", "day", "did", "get", "come", "made", "may", "part"}
        
        keywords = [w for w in re.findall(r"\b\w{3,}\b", answer) if w.lower() not in stopwords]
        
        # Keep unique keywords preserving order
        seen = set()
        unique_keywords = []
        for k in keywords:
            if k.lower() not in seen:
                seen.add(k.lower())
                unique_keywords.append(k)

        # Dynamic questions list
        questions = []

        # Intent-specific dynamic questions
        if intent == "Invoice":
            if any(w in ans_words for w in ["gst", "tax"]):
                questions.append("What is the tax rate mentioned?")
            if any(w in ans_words for w in ["due", "date"]):
                questions.append("When is the final payment due?")
            if any(w in ans_words for w in ["total", "amount", "charge"]):
                questions.append("Are there any additional charges listed?")
            if unique_keywords:
                questions.append(f"Can you explain the details regarding {unique_keywords[0]}?")
            else:
                questions.append("What other payment details are listed?")
                
        elif intent in ["Skills", "Technologies", "Projects"]:
            tech_mentions = [k for k in unique_keywords if k.lower() not in ["skills", "candidate", "technologies", "experience", "document"]]
            if tech_mentions:
                questions.append(f"How is {tech_mentions[0]} applied in the projects?")
                if len(tech_mentions) > 1:
                    questions.append(f"What other skills are related to {tech_mentions[1]}?")
            else:
                questions.append("What other technical tools are mentioned?")
            questions.append("Can you elaborate on the projects listed?")

        elif intent == "Summary":
            questions.append("What is the main conclusion of the document?")
            if unique_keywords:
                questions.append(f"Can you expand on the section discussing {unique_keywords[0]}?")
            questions.append("What are the key takeaways?")

        elif intent == "Policies":
            if "leave" in ans_words:
                questions.append("How does the leave policy handle probation?")
            if "probation" in ans_words:
                questions.append("What happens after the probation period ends?")
            if unique_keywords:
                questions.append(f"What are the guidelines for {unique_keywords[0]}?")
            else:
                questions.append("Are there exceptions to these policies?")

        # General dynamic questions
        if len(questions) < 3:
            topic = unique_keywords[0] if unique_keywords else "this topic"
            questions.append(f"Can you provide more details about {topic}?")
            if len(unique_keywords) > 1:
                questions.append(f"How does the document describe {unique_keywords[1]}?")
            questions.append("What is the context of this information?")

        return questions[:4]

    def format_response(
        self,
        answer: str,
        confidence: float,
        retrieved_chunks: List[Dict[str, Any]],
        intent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Builds the complete formatted chat output structure.
        
        Args:
            answer: Answer text generated by ReasoningService.
            confidence: Confidence score (0.0-100.0 percentage or 0.0-1.0).
            retrieved_chunks: List of raw context chunk mappings.
            intent: Optional inferred user query intent.
            
        Returns:
            Formatted response dict.
        """
        logger.info(f"Formatting final chat response. Confidence={confidence}")
        logger.info("ANSWER GENERATED")

        # Normalize confidence to percentage scale
        if confidence <= 1.0:
            confidence_pct = round(confidence * 100, 1)
        else:
            confidence_pct = round(confidence, 1)

        # Extract sources from retrieved chunks
        sources = []
        for chunk in retrieved_chunks:
            chunk_text = chunk.get("text", "")
            chunk_id = chunk.get("chunk_id", chunk.get("id", ""))
            
            # Extract chunk index/number from chunk_id
            chunk_num = 1
            match = re.search(r"_chunk_(\d+)", chunk_id)
            if match:
                chunk_num = int(match.group(1)) + 1
                
            sources.append({
                "page_number": chunk.get("page_number", 1),
                "section": chunk.get("section", "Content"),
                "text": chunk_text[:200] + "..." if len(chunk_text) > 200 else chunk_text,
                "score": chunk.get("score", chunk.get("similarity", 0.0)),
                "chunk_num": chunk_num,
            })

        # Remove duplicate sources to keep references clean
        unique_sources = []
        seen_sources: set = set()
        for src in sources:
            src_key = (src["page_number"], src["section"], src["text"][:30])
            if src_key not in seen_sources:
                seen_sources.add(src_key)
                unique_sources.append(src)

        # Determine formatted output based on intent
        intent_upper = intent.upper() if intent else ""
        if intent_upper == "SUMMARY":
            formatted_answer = f"## Summary\n{answer}"
        elif intent_upper in ["SKILLS", "TECHNOLOGIES", "PROJECTS"]:
            formatted_answer = format_list_answer(answer)
        elif intent_upper == "COMPARISON":
            formatted_answer = format_comparison_answer(answer)
        elif intent_upper == "Research":
            formatted_answer = format_research_answer(answer)
        else:
            formatted_answer = answer

        # Final dedup pass on the formatted answer (never append sources text block to answer)
        formatted_answer = self._strip_duplicate_sentences(formatted_answer)

        suggested = self._generate_suggested_questions(answer, confidence, intent)

        return {
            "answer": formatted_answer,
            "confidence": confidence_pct,
            "sources": unique_sources,
            "suggested_questions": suggested
        }


answer_formatter = AnswerFormatter()

