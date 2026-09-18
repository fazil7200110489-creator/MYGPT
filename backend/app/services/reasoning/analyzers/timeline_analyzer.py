import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from loguru import logger
from backend.app.services.reasoning.domain_detector import domain_detector

CURRENT_YEAR = datetime.now().year

class TimelineAnalyzer:
    """Handles experience timeline construction, career transitions, and total experience calculations."""

    def analyze(self, entities: Dict[str, Any], raw_text: str) -> Dict[str, Any]:
        timeline = self._build_experience_timeline(entities, raw_text)
        career_transition = self._detect_career_transition(timeline, entities)
        experience_data = self._calculate_multilevel_experience(timeline, entities, raw_text)
        
        return {
            "timeline": timeline,
            "career_transition": career_transition,
            **experience_data
        }

    def _build_experience_timeline(self, entities: Dict[str, Any], text: str) -> List[Dict[str, Any]]:
        """Build chronological employment timeline from structured entities and OCR text."""
        timeline = []
        exp_list = entities.get("work_experience") or entities.get("experience") or []
        if isinstance(exp_list, str):
            exp_list = [l.strip() for l in exp_list.split('\n') if l.strip()]

        for item in exp_list:
            if not isinstance(item, str) or len(item.strip()) < 5:
                continue
            entry = self._parse_experience_entry(item)
            if entry:
                timeline.append(entry)

        # If no structured entries, try parsing raw text for employment blocks
        if not timeline and text:
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            for l in lines:
                if re.search(r'\b(?:19|20)\d{2}\b', l):
                    entry = self._parse_experience_entry(l)
                    if entry:
                        timeline.append(entry)

        # Sort chronologically
        timeline.sort(key=lambda x: x.get("start_year", 0))
        return timeline

    def _parse_experience_entry(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse a single experience string into timeline entry.
        Filters out education-related lines.
        """
        text_lower = text.lower()
        edu_kws = ["education", "bachelor", "master", "degree", "diploma", "school", "college", "university", "btech", "mba", "bca", "bsc", "bcom", "be", "gnm", "ssc", "hsc", "academic", "matriculation", "study", "studied", "b.tech", "b.ca", "b.sc", "b.com", "b.e", "m.tech", "m.ba", "m.ca", "m.sc", "m.com"]
        for kw in edu_kws:
            if len(kw) <= 5:
                if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
                    return None
            else:
                if kw in text_lower:
                    return None

        years_match = re.search(
            r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|[a-z]+)?\s*\b((?:19|20)\d{2})\b\s*[-–—to]+\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|[a-z]+)?\s*\b((?:19|20)\d{2}|present|current|till date)\b',
            text, re.IGNORECASE
        )
        if not years_match:
            return None

        start_year = int(years_match.group(1))
        end_str = years_match.group(2).strip().lower()
        end_year = CURRENT_YEAR if end_str in ("present", "current", "till date") else int(years_match.group(2))
        years_label = f"{start_year}–{end_str.title() if end_str in ('present', 'current', 'till date') else end_year}"

        # Try to extract title/company from BEFORE and AFTER the year range
        before_year = text[:years_match.start()].strip()
        after_year = text[years_match.end():].strip().lstrip(':').strip()
        after_year = after_year.lstrip(')').strip()

        if after_year and len(after_year) > 3:
            parts = re.split(r'\s*[\-–—|@,]\s*', after_year)
            title = parts[0].strip().title() if parts else "Not Mentioned"
            company = parts[1].strip().title() if len(parts) > 1 else "Not Mentioned"
        elif before_year and len(before_year) > 3:
            clean_before = re.sub(r'\($', '', before_year).strip()
            clean_before = re.sub(r'^(?:experience|work experience|employment)\s*:\s*', '', clean_before, flags=re.IGNORECASE).strip()
            parts = re.split(r'\s*(?:at|@|[\-–—|,])\s*', clean_before)
            title = parts[0].strip().title() if parts else "Not Mentioned"
            company = parts[1].strip().title() if len(parts) > 1 else "Not Mentioned"
        else:
            title = "Not Mentioned"
            company = "Not Mentioned"

        domain_guess = domain_detector.detect_domain({"designation": title}, "")

        return {
            "years": years_label,
            "title": title,
            "company": company,
            "domain": domain_guess,
            "start_year": start_year,
            "end_year": end_year
        }

    def _detect_career_transition(self, timeline: List[Dict], entities: Dict[str, Any]) -> Dict[str, Any]:
        """Detect career domain transitions from the employment timeline."""
        if len(timeline) < 2:
            return {
                "is_transition": False,
                "transition_path": "",
                "current_domain": "",
                "previous_domains": []
            }

        domains_seen = []
        for entry in timeline:
            d = entry.get("domain", "General")
            if not domains_seen or domains_seen[-1] != d:
                domains_seen.append(d)

        if len(set(domains_seen)) < 2:
            return {
                "is_transition": False,
                "transition_path": " -> ".join(domains_seen),
                "current_domain": domains_seen[-1] if domains_seen else "",
                "previous_domains": []
            }

        current = domains_seen[-1]
        previous = [d for d in dict.fromkeys(domains_seen[:-1]) if d != current]
        path = " -> ".join(dict.fromkeys(domains_seen))

        return {
            "is_transition": True,
            "transition_path": path,
            "current_domain": current,
            "previous_domains": previous
        }

    def _calculate_multilevel_experience(
        self, timeline: List[Dict], entities: Dict[str, Any], text: str
    ) -> Dict[str, Any]:
        """Calculate total, current-domain, and per-domain experience from actual dates."""
        summary_text = entities.get("summary") or text
        summary_exp = None
        if summary_text:
            m = re.search(
                r'(?i)\b(?:over|around|more than|with|\+)?\s*(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\b.*?\b(?:experience|exp|work|industry)\b',
                summary_text
            )
            if m:
                summary_exp = f"{m.group(1)}+ Years"

        per_domain: Dict[str, int] = {}
        total_months = 0

        for entry in timeline:
            start = entry.get("start_year", 0)
            end = entry.get("end_year", CURRENT_YEAR)
            if start and end >= start:
                months = (end - start) * 12
                total_months += months
                domain = entry.get("domain", "General")
                per_domain[domain] = per_domain.get(domain, 0) + months

        def fmt_months(m: int) -> str:
            y, mo = m // 12, m % 12
            if y > 0 and mo > 0:
                return f"{y} Year{'s' if y > 1 else ''} {mo} Month{'s' if mo > 1 else ''}"
            elif y > 0:
                return f"{y} Year{'s' if y > 1 else ''}"
            elif mo > 0:
                return f"{mo} Month{'s' if mo > 1 else ''}"
            return "Not Mentioned"

        total_exp = (
            summary_exp if summary_exp
            else fmt_months(total_months) if total_months > 0
            else "Not Mentioned"
        )

        current_domain = timeline[-1].get("domain", "") if timeline else ""
        current_domain_months = per_domain.get(current_domain, 0)
        current_domain_exp = (
            f"{fmt_months(current_domain_months)} in {current_domain}"
            if current_domain_months > 0 and current_domain
            else "Not Mentioned"
        )

        per_domain_formatted = {
            d: fmt_months(m) for d, m in per_domain.items() if m > 0
        }

        # Experience history list
        exp_history = entities.get("work_experience") or entities.get("experience") or []
        if isinstance(exp_history, str):
            exp_history = [exp_history]

        current_comp_exp = "Not Mentioned"
        if timeline:
            latest_entry = timeline[-1]
            c_start = latest_entry.get("start_year", 0)
            c_end = latest_entry.get("end_year", CURRENT_YEAR)
            if c_start and c_end >= c_start:
                c_months = (c_end - c_start) * 12
                comp_name = latest_entry.get("company", "Current Company")
                current_comp_exp = f"{fmt_months(c_months)} at {comp_name}"

        return {
            "total_experience": total_exp,
            "current_domain_experience": current_domain_exp,
            "current_company_experience": current_comp_exp,
            "per_domain_experience": per_domain_formatted,
            "experience_history": [str(e) for e in exp_history if e]
        }
