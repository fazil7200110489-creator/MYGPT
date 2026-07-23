"""Formatter module providing text cleanup and dedicated intent-specific answer formatters.

Ensures every intent uses its dedicated presentation format:
    - Contact -> Plain Contact Formatter
    - Education -> Education Formatter
    - Skills -> Bullet Skill Formatter
    - Experience -> Timeline Formatter
    - Role Match -> Score Card Formatter
    - Summary -> Recruiter Summary Formatter
"""

import re
from typing import List, Dict, Any, Optional
from backend.app.services.reasoning.answer_type_detector import AnswerType, answer_type_detector


class Formatter:
    """Normalizes whitespace, cleans duplicate words/syllables, and cleans punctuation.

    Must preserve: emails, URLs, dates, numbers, currency, and IDs.
    """

    def clean(self, text: str) -> str:
        """Applies robust deduplication and cleanup without altering original facts."""
        if not text:
            return ""

        # 1. Shield elements to preserve
        patterns = [
            # URLs
            r'https?://[^\s/$.?#].[^\s]*',
            # Emails
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            # Phone numbers
            r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}',
            # Dates
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{2,4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+\d{2,4}\b',
            # Currency
            r'[\$\u20b9\u20ac\u00a3]\s*[\d,]+\.?\d*',
            # Alphanumeric IDs and pure numbers
            r'\b[A-Za-z0-9]+-\d+\b|\b\d+\b'
        ]

        placeholders = []

        def shield_match(match):
            val = match.group(0)
            idx = len(placeholders)
            placeholders.append(val)
            return f"__SHIELD_VAL_{idx}__"

        # Replace each matched pattern in order of complexity
        for pattern in patterns:
            text = re.sub(pattern, shield_match, text)

        # 2. Perform the cleaning of duplicate words on the shielded text
        def replace_run_together(match):
            word = match.group(0)
            L = len(word)
            for chunk_len in range(2, L // 2 + 1):
                if L % chunk_len == 0:
                    chunk = word[:chunk_len]
                    if chunk.lower() * (L // chunk_len) == word.lower():
                        if word.lower() not in {"murmur", "tartar", "couscous", "cancan", "meme", "haha", "dodo", "coco", "gogo"}:
                            return word[:chunk_len]
            return word

        text = re.sub(r'[A-Za-z]+', replace_run_together, text)

        # Clean space-separated duplicate words: "Word Word" -> "Word"
        prev = None
        while prev != text:
            prev = text
            text = re.sub(r'\b([A-Za-z]+)\b\s+\b\1\b', r'\1', text, flags=re.IGNORECASE)

        # 3. Restore the shielded elements
        for idx, val in reversed(list(enumerate(placeholders))):
            text = text.replace(f"__SHIELD_VAL_{idx}__", val)

        # 4. Normalize spacing and punctuation
        text = re.sub(r"[ \t]+", " ", text).strip()
        text = re.sub(r"\s+([.,!?;:])", r"\1", text)
        text = re.sub(r"\.{2,}", ".", text)

        return text


# ---------------------------------------------------------------------------
# Dedicated Intent Answer Formatters
# ---------------------------------------------------------------------------

class ContactFormatter:
    """Plain Contact Formatter."""

    def format(self, data: Dict[str, Any]) -> str:
        if isinstance(data, str):
            return data
        lines = ["Candidate Information", ""]
        if data.get("name") and data["name"] != "Not Mentioned":
            lines.append(f"Name: {data['name']}")
        if data.get("email") and data["email"] != "Not Mentioned":
            lines.append(f"Email: {data['email']}")
        if data.get("phone") and data["phone"] != "Not Mentioned":
            lines.append(f"Phone: {data['phone']}")
        if data.get("current_location") and data["current_location"] != "Not Mentioned":
            lines.append(f"Current Location: {data['current_location']}")
        if data.get("permanent_address") and data["permanent_address"] != "Not Mentioned":
            lines.append(f"Permanent Address: {data['permanent_address']}")
        if data.get("linkedin") and data["linkedin"] != "Not Mentioned":
            lines.append(f"LinkedIn: {data['linkedin']}")
        if data.get("github") and data["github"] != "Not Mentioned":
            lines.append(f"GitHub: {data['github']}")
        if data.get("portfolio") and data["portfolio"] != "Not Mentioned":
            lines.append(f"Portfolio: {data['portfolio']}")
        return "\n".join(lines)


class EducationFormatter:
    """Education Formatter."""

    def format(self, edu_list: Any) -> str:
        if isinstance(edu_list, str):
            return edu_list
        if not isinstance(edu_list, list) or not edu_list:
            return "The resume does not mention education details."

        lines = ["Education & Academic Background", ""]
        for edu in edu_list:
            if isinstance(edu, dict):
                degree = edu.get("degree", "Not Mentioned")
                inst = edu.get("institution") or edu.get("university") or "Not Mentioned"
                year = edu.get("year", "Not Mentioned")
                cgpa = edu.get("cgpa_percentage", "Not Mentioned")
                spec = edu.get("specialization", "Not Mentioned")

                lines.append(f"• Degree: {degree}")
                if spec != "Not Mentioned":
                    lines.append(f"  Specialization: {spec}")
                if inst != "Not Mentioned":
                    lines.append(f"  Institution: {inst}")
                if year != "Not Mentioned":
                    lines.append(f"  Year: {year}")
                if cgpa != "Not Mentioned":
                    lines.append(f"  CGPA/Marks: {cgpa}")
                lines.append("")
            else:
                lines.append(f"• {edu}")

        return "\n".join(lines).strip()


class SkillsFormatter:
    """Bullet Skill Formatter with recruiter narrative."""

    def format(self, profile: Dict[str, Any]) -> str:
        domain = profile.get("primary_domain") or profile.get("domain") or "General"
        skills = profile.get("skills", [])
        hr_skills = profile.get("hr_skills", [])
        erp = profile.get("erp_platforms", [])
        prog = profile.get("programming_languages", [])
        ai = profile.get("ai_tools", [])

        narrative = f"The candidate possesses strong experience in {domain}."
        if erp:
            narrative += f" Experienced with ERP platforms such as {', '.join(erp[:4])}."
        elif prog:
            narrative += f" Proficient in programming languages including {', '.join(prog[:4])}."

        lines = [narrative, "", "**Core Skills & Competencies**:"]
        for s in skills[:12]:
            lines.append(f"• {s}")

        return "\n".join(lines)


class ExperienceFormatter:
    """Timeline Formatter."""

    def format(self, data: Dict[str, Any]) -> str:
        total = data.get("total_experience", "Not Mentioned")
        current_dom = data.get("current_domain_experience", "Not Mentioned")
        per_dom = data.get("per_domain_experience", {})
        timeline = data.get("timeline", [])

        lines = [
            f"• Total Professional Experience: {total}",
            f"• Current Domain Experience: {current_dom}",
        ]
        if per_domain := per_dom:
            lines.append("• Domain Breakdown:")
            for d, exp_str in per_domain.items():
                lines.append(f"   - {d}: {exp_str}")

        if timeline:
            lines.extend(["", "**Work History & Timeline**:"])
            for t in timeline:
                lines.append(f"• {t.get('years', 'Not Mentioned')} — {t.get('title', 'Role')} at {t.get('company', 'Company')} ({t.get('domain', 'General')})")

        return "\n".join(lines)


class RoleMatchFormatter:
    """Score Card Formatter."""

    def format(self, eval_data: Dict[str, Any]) -> str:
        target_role = eval_data.get("target_role") or eval_data.get("top_recommended_role") or "Target Role"
        tier = eval_data.get("suitability_tier", "Evaluated")
        match_pct = eval_data.get("match_percentage", 80)
        matching = eval_data.get("matching_skills", [])
        missing = eval_data.get("missing_skills", [])
        reason = eval_data.get("reason") or eval_data.get("summary_recommendation", "")

        lines = [
            f"**Role Fit Analysis**: {target_role}",
            f"• **Suitability Tier**: {tier} ({match_pct}% Match)",
            f"• **Assessment**: {reason}",
            "",
            "**Key Skill Matches**: " + (", ".join(matching) if matching else "Core Domain Alignment"),
        ]
        if missing:
            lines.append("**Skill Gaps / Missing**: " + ", ".join(missing))

        return "\n".join(lines)


class RecruiterSummaryFormatter:
    """Recruiter Summary Formatter."""

    def format(self, profile: Dict[str, Any]) -> str:
        name = profile.get("name", "Candidate")
        desig = profile.get("designation", "Professional")
        domain = profile.get("primary_domain", "General")
        exp = profile.get("total_experience", "Not Mentioned")
        skills = profile.get("skills", [])
        edu = profile.get("education", [])

        lines = [
            f"## Candidate Highlights",
            f"### Overview",
            f"**Name:** {name}",
            f"**Designation:** {desig}",
            f"**Primary Domain:** {domain}",
            f"**Total Experience:** {exp}",
            "",
            "### Core Technical & Professional Skills",
            f"• {', '.join(skills[:8]) if skills else 'Not Mentioned'}",
        ]
        if edu and edu[0].get("degree") != "Not Mentioned":
            lines.extend(["", "### Education", f"• {edu[0].get('degree')} from {edu[0].get('institution', 'Not Mentioned')} ({edu[0].get('year', '')})"])

        return "\n".join(lines)


# Formatters registry
formatters = {
    AnswerType.CONTACT: ContactFormatter(),
    AnswerType.EDUCATION: EducationFormatter(),
    AnswerType.SKILLS_BULLET: SkillsFormatter(),
    AnswerType.EXPERIENCE_TIMELINE: ExperienceFormatter(),
    AnswerType.ROLE_MATCH_SCORECARD: RoleMatchFormatter(),
    AnswerType.RECRUITER_SUMMARY: RecruiterSummaryFormatter(),
}

formatter = Formatter()
