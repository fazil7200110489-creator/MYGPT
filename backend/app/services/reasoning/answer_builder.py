import re
from typing import Any, List, Union

class AnswerBuilder:
    """Formats answer values into structured styles depending on the Canonical Intent."""

    def build(self, value: Any, intent: str, doc_type: str) -> str:
        """Constructs response output strings based on intent formatting rules."""
        if not value:
            return "I couldn't find that information in the uploaded document."

        intent_upper = intent.upper()

        # 1. PHONE / EMAIL: raw single value strings
        if intent_upper in ["PHONE", "PHONE_NUMBERS"]:
            val_str = str(value).strip()
            # Extract only digits and symbols
            digits = re.sub(r'[^\d+()-]', '', val_str)
            if digits:
                return digits
            return val_str

        elif intent_upper == "EMAIL":
            val_str = str(value).strip()
            # Extract email
            email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', val_str)
            if email_match:
                return email_match.group(0)
            return val_str

        # 2. SKILLS: Bullet points list
        elif intent_upper == "SKILLS":
            items = self._to_list(value)
            if items:
                items = [item for item in items if item.lower() not in ["skills", "technical skills", "education", "experience"]]
                return "\n".join([f"• {item}" for item in items])
            return str(value)

        # 3. PROJECTS: Numbered list
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

        # 4. CERTIFICATIONS: Bullet points list
        elif intent_upper == "CERTIFICATIONS":
            if value == "No certifications were found in the resume.":
                return value
            items = self._to_list(value)
            if items:
                items = [item for item in items if item.lower() not in ["certifications", "education", "skills"]]
                return "\n".join([f"• {item}" for item in items])
            return "No certifications were found in the resume."

        # 5. EDUCATION: Bullet list of blocks
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

        # 5.5 EXPERIENCE / WORK_EXPERIENCE: Bullet list of blocks
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

        # 5.6 COUNT: return only the number
        elif intent_upper in ["COUNT", "COUNT_YEARS", "YEARS_COUNT"]:
            match = re.search(r'\b\d+\b', str(value))
            if match:
                return match.group(0)
            return str(value).strip()

        # 5.7 SUMMARY: Single clean paragraph
        elif intent_upper == "SUMMARY":
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
            paragraph = re.sub(r'^[•\-*\s\d\.\)]+', '', paragraph).strip()
            return paragraph

        # 6. Fallback or general intent
        if isinstance(value, list):
            return "\n".join(str(v) for v in value)
        return str(value).strip()

    def _to_list(self, value: Any) -> List[str]:
        """Helper to convert various types into clean lists of strings."""
        if not value:
            return []
        if isinstance(value, list):
            items = value
        elif isinstance(value, str):
            # Split by newlines or list markers
            items = [line.strip() for line in value.split('\n') if line.strip()]
            if len(items) <= 1 and ',' in value:
                # Comma separated list fallback
                items = [item.strip() for item in value.split(',') if item.strip()]
        else:
            items = [str(value)]

        cleaned_items = []
        for item in items:
            # Clean list bullets
            item = re.sub(r'^[•\-*\d\.\s]+', '', item).strip()
            if item:
                cleaned_items.append(item)
        return cleaned_items
