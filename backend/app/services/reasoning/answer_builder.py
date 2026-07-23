import re
from typing import Any, List, Union

# ---------------------------------------------------------------------------
# Field-specific "not mentioned" messages — extend here, not in code
# ---------------------------------------------------------------------------
_NOT_MENTIONED_MESSAGES: dict = {
    "AGE":            "The uploaded resume does not mention the candidate's age.",
    "DATE_OF_BIRTH":  "The uploaded resume does not mention the candidate's date of birth.",
    "DOB":            "The uploaded resume does not mention the candidate's date of birth.",
    "GENDER":         "The uploaded resume does not mention the candidate's gender.",
    "SALARY":         "The uploaded resume does not mention the candidate's expected salary or CTC.",
    "NOTICE_PERIOD":  "The uploaded resume does not mention the candidate's notice period.",
    "MARITAL_STATUS": "The uploaded resume does not mention the candidate's marital status.",
    "NATIONALITY":    "The uploaded resume does not mention the candidate's nationality.",
    "CERTIFICATIONS": "No certifications were found in the resume.",
}

_RESUME_FALLBACK = "The uploaded resume does not mention this information."
_GENERIC_FALLBACK = "I couldn't find that information in the uploaded document."


class AnswerBuilder:
    """Formats answer values into structured styles depending on the Canonical Intent.

    Design principles:
    - Never returns an empty string.
    - Field-specific "not mentioned" messages are driven by ``_NOT_MENTIONED_MESSAGES``.
    - Adding a new intent formatter requires only adding a new elif branch or
      extending the intent list on an existing branch.
    """

    def build(self, value: Any, intent: str, doc_type: str) -> str:
        """Constructs response output strings based on intent formatting rules."""
        intent_upper = intent.upper()

        # --- GENERAL / ROLE_INFERENCE: value is already a prose string ---
        if intent_upper in ["GENERAL", "ROLE_INFERENCE"]:
            if value and str(value).strip():
                return str(value).strip()
            return _RESUME_FALLBACK

        # --- Empty / missing value guard ---
        if not value or value == "Not Found" or (isinstance(value, list) and len(value) == 0):
            if intent_upper in _NOT_MENTIONED_MESSAGES:
                return _NOT_MENTIONED_MESSAGES[intent_upper]
            if doc_type.lower() == "resume":
                return _RESUME_FALLBACK
            return _GENERIC_FALLBACK

        # 1. PHONE / EMAIL: raw single value strings
        if intent_upper in ["PHONE", "PHONE_NUMBERS"]:
            val_str = str(value).strip()
            digits = re.sub(r'[^\d+()-]', '', val_str)
            if digits:
                return digits
            return val_str

        elif intent_upper == "EMAIL":
            val_str = str(value).strip()
            email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', val_str)
            if email_match:
                return email_match.group(0)
            return val_str

        # 2. NAME / ADDRESS / DESIGNATION: raw single value strings (Problem 5)
        elif intent_upper in ["CANDIDATE_NAME", "NAME", "NAMES"]:
            return str(value).strip()

        elif intent_upper in ["ADDRESS", "LOCATION"]:
            val_str = str(value).strip()
            val_str = re.sub(r'^(?:[•\-*]|\d+[\.\)]|\s)+', '', val_str).strip()
            return val_str

        elif intent_upper in ["LINKEDIN", "GITHUB", "PORTFOLIO"]:
            return str(value).strip()

        elif intent_upper in ["DOMAIN", "INDUSTRY"]:
            return str(value).strip()

        elif intent_upper == "DESIGNATION":
            return str(value).strip()

        # 3. SKILLS / PROGRAMMING_LANGUAGES / HUMAN_LANGUAGES: Bullet points list
        elif intent_upper in ["SKILLS", "PROGRAMMING_LANGUAGES", "HUMAN_LANGUAGES"]:
            items = self._to_list(value)
            if items:
                items = [item for item in items if item.lower() not in ["skills", "technical skills", "education", "experience"]]
                return "\n".join([f"• {item}" for item in items])
            return str(value)

        # 4. PROJECTS: Numbered list
        elif intent_upper == "PROJECTS":
            items = self._to_list(value)
            if items:
                items = [item for item in items if item.lower() not in ["projects", "skills", "education", "experience"]]
                formatted_items = []
                for idx, item in enumerate(items):
                    lines = item.split('\n')
                    formatted_lines = [f"{idx+1}. {lines[0]}"]
                    for line in lines[1:]:
                        formatted_lines.append("   " + line)
                    formatted_items.append("\n".join(formatted_lines))
                return "\n".join(formatted_items)
            return str(value)

        # 5. CERTIFICATIONS: Bullet points list
        elif intent_upper == "CERTIFICATIONS":
            if value == "No certifications were found in the resume.":
                return value
            items = self._to_list(value)
            if items:
                items = [item for item in items if item.lower() not in ["certifications", "education", "skills"]]
                return "\n".join([f"• {item}" for item in items])
            return "No certifications were found in the resume."

        # 6. EDUCATION: Bullet list of blocks
        elif intent_upper == "EDUCATION":
            items = self._to_list(value)
            if items:
                items = [item for item in items if item.lower() not in ["education", "skills", "experience"]]
                formatted_items = []
                for item in items:
                    lines = item.split('\n')
                    formatted_lines = [f"• {lines[0]}"]
                    for line in lines[1:]:
                        formatted_lines.append("  " + line)
                    formatted_items.append("\n".join(formatted_lines))
                return "\n".join(formatted_items)
            return str(value)

        # 7. EXPERIENCE / WORK_EXPERIENCE: Bullet list of blocks
        elif intent_upper in ["EXPERIENCE", "WORK_EXPERIENCE"]:
            items = self._to_list(value)
            if items:
                items = [item for item in items if item.lower() not in ["experience", "work experience", "professional experience", "skills", "education"]]
                formatted_items = []
                for item in items:
                    lines = item.split('\n')
                    formatted_lines = [f"• {lines[0]}"]
                    for line in lines[1:]:
                        formatted_lines.append("  " + line)
                    formatted_items.append("\n".join(formatted_lines))
                return "\n".join(formatted_items)
            return str(value)

        # 8. COUNT: return only the number
        elif intent_upper in ["COUNT", "COUNT_YEARS", "YEARS_COUNT"]:
            match = re.search(r'\b\d+\b', str(value))
            if match:
                return match.group(0)
            return str(value).strip()

        # 9. SUMMARY / PROFILE_SUMMARY: Single clean paragraph
        elif intent_upper in ["SUMMARY", "PROFILE_SUMMARY"]:
            sentences = self._to_list(value)
            if not sentences:
                return str(value)
            cleaned_sentences = []
            for s in sentences:
                s = s.strip()
                if s and not s.endswith(('.', '!', '?')):
                    s += '.'
                if s:
                    cleaned_sentences.append(s)
            
            paragraph = " ".join(cleaned_sentences)
            paragraph = re.sub(r'^(?:[•\-*]|\d+[\.\)]|\s)+', '', paragraph).strip()
            return paragraph

        # 10. BASIC_PROFILE
        elif intent_upper == "BASIC_PROFILE":
            if isinstance(value, dict):
                lines = []
                for k, v in value.items():
                    if isinstance(v, list):
                        v_str = "\n".join(f"• {x}" for x in v)
                    else:
                        v_str = str(v)
                    lines.append(f"{k}:\n{v_str}")
                return "\n\n".join(lines)

        # 12. Fallback for any unhandled intent
        if isinstance(value, list):
            result = "\n".join(str(v) for v in value if str(v).strip())
            return result if result.strip() else _RESUME_FALLBACK if doc_type.lower() == "resume" else _GENERIC_FALLBACK
        result = str(value).strip()
        return result if result else (_RESUME_FALLBACK if doc_type.lower() == "resume" else _GENERIC_FALLBACK)

    def _to_list(self, value: Any) -> List[str]:
        """Helper to convert various types into clean lists of strings."""
        if not value:
            return []
        if isinstance(value, list):
            items = value
        elif isinstance(value, str):
            items = [line.strip() for line in value.split('\n') if line.strip()]
            if len(items) <= 1 and ',' in value:
                items = [item.strip() for item in value.split(',') if item.strip()]
        else:
            items = [str(value)]

        cleaned_items = []
        for item in items:
            if self._is_table_header_or_separator(item):
                continue
            item = re.sub(r'^(?:[•\-*]|\d+[\.\)]|\s)+', '', item).strip()
            if item:
                cleaned_items.append(item)
        return cleaned_items

    def _is_table_header_or_separator(self, text: str) -> bool:
        text_clean = text.strip().lower()
        if not text_clean:
            return False
        # Match horizontal line separators (e.g. ---, |---|)
        if re.match(r'^[|\s\-+=:_]*$', text_clean):
            return True
        headers = {"s", "no", "sno", "qualification", "year", "per", "percentage", "university", "cgpa", "marks", "board", "passing", "major", "grade", "institute", "school", "college"}
        if text_clean in headers:
            return True
        words = re.findall(r'\b\w+\b', text_clean)
        if words and all(w in headers for w in words):
            return True
        return False
