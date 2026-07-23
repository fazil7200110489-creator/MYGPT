import re
import json
from typing import Dict, Any, List, Optional

class EntityExtractor:
    """Extracts logical entities from raw context text and integrates pre-computed knowledge facts."""

    def extract(self, text: str, knowledge: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Combines regex extraction over raw text with structured facts from the knowledge store."""
        entities: Dict[str, Any] = {
            "name": None,
            "phones": [],
            "emails": [],
            "addresses": [],
            "companies": [],
            "organizations": [],
            "skills": [],
            "projects": [],
            "education": [],
            "certifications": [],
            "experience": [],
            "dates": [],
            "amounts": [],
            "invoice_numbers": [],
            "gst": None,
            "tables": [],
            "technologies": [],
            "human_languages": [],
            "programming_languages": [],
            "designation": None,
            "location": None,
            "linkedin": None,
            "github": None
        }

        # 1. Integrate pre-computed knowledge entities and candidate profile if available
        profile = None
        if knowledge:
            profile = knowledge.get("candidate_profile") or (knowledge.get("facts", {}).get("candidate_profile") if isinstance(knowledge.get("facts"), dict) else None)
            
            # Extract root level keys
            for key, val in knowledge.items():
                if key not in ["entities", "tables", "metadata", "sections"]:
                    entities[key] = val

            k_entities = knowledge.get("entities", {})
            k_facts = knowledge.get("facts", {}) if isinstance(knowledge.get("facts"), dict) else {}
            tables = knowledge.get("tables", [])
            entities["tables"] = tables

        if profile:
            entities["candidate_profile"] = profile
            entities["name"] = profile["name"]
            entities["candidate_name"] = profile["name"]
            entities["phone"] = profile["personal_info"].get("phone")
            entities["email"] = profile["personal_info"].get("email")
            entities["address"] = profile["personal_info"].get("address")
            entities["phones"] = [profile["personal_info"]["phone"]] if profile["personal_info"].get("phone") != "Not Mentioned" else []
            entities["emails"] = [profile["personal_info"]["email"]] if profile["personal_info"].get("email") != "Not Mentioned" else []
            entities["addresses"] = [profile["personal_info"]["address"]] if profile["personal_info"].get("address") != "Not Mentioned" else []
            entities["skills"] = profile.get("skills", [])
            entities["education"] = profile.get("education", [])
            entities["experience"] = profile.get("experience_timeline", [])
            entities["work_experience"] = profile.get("experience_timeline", [])
            entities["companies"] = profile.get("companies", [])
            entities["projects"] = profile.get("projects", [])
            entities["certifications"] = profile.get("certifications", [])
            entities["designation"] = profile.get("designation")
            entities["location"] = profile.get("current_location")
            entities["linkedin"] = profile["personal_info"].get("linkedin")
            entities["github"] = profile["personal_info"].get("github")
            entities["primary_domain"] = profile.get("primary_domain")
        elif knowledge:
            # Map legacy names if candidate profile not yet attached
            people_list = k_entities.get("people")
            entities["name"] = k_facts.get("name") or entities.get("candidate_name") or (people_list[0] if isinstance(people_list, list) and people_list else None)
            entities["phones"] = k_facts.get("phones") or ([entities.get("phone")] if entities.get("phone") else k_entities.get("phones", []))
            entities["emails"] = k_facts.get("emails") or ([entities.get("email")] if entities.get("email") else k_entities.get("emails", []))
            entities["addresses"] = [entities.get("address")] if entities.get("address") else k_entities.get("addresses", [])
            entities["companies"] = entities.get("companies") or k_entities.get("companies", [])
            entities["projects"] = entities.get("projects") or []
            entities["education"] = entities.get("education") or []
            entities["certifications"] = entities.get("certifications") or []
            entities["experience"] = entities.get("work_experience") or []
            entities["dates"] = k_facts.get("dates") or k_entities.get("dates", [])
            entities["amounts"] = k_entities.get("amounts", [])
            entities["invoice_numbers"] = [k_facts.get("invoice_number")] if k_facts.get("invoice_number") else []
            entities["gst"] = k_facts.get("gst") or k_facts.get("tax")

        # Partition raw text into sections dynamically
        sections: Dict[str, str] = {}
        current_sec = "header"
        current_lines = []
        
        header_patterns = {
            "SKILLS": ["skills", "technical skills", "core competencies", "technical expertise", "hardware knowledge", "software skills", "technologies", "hardware skills", "software skills"],
            "EDUCATION": ["education", "academic", "degree", "university", "college", "schooling", "qualifications", "academic background"],
            "EXPERIENCE": ["experience", "work experience", "employment history", "career details", "previous jobs", "work history", "job history", "employment"],
            "PROJECTS": ["projects", "applications", "portfolio", "built", "project"],
            "ADDRESS": ["address", "location", "contact", "personal details", "personal info"]
        }
        
        for line in text.split('\n'):
            trimmed = line.strip()
            if not trimmed:
                continue
            is_header = False
            matched_sec = None
            for sec, keywords in header_patterns.items():
                for kw in keywords:
                    if kw == trimmed.lower() or (len(trimmed) < 30 and kw in trimmed.lower() and not any(verb in trimmed.lower() for verb in ["was", "did", "worked", "completed", "have", "with", "know", "study"])):
                        is_header = True
                        matched_sec = sec
                        break
                if is_header:
                    break
            if is_header:
                sections[current_sec] = "\n".join(current_lines)
                current_sec = matched_sec
                current_lines = []
            else:
                current_lines.append(line)
        sections[current_sec] = "\n".join(current_lines)

        # 2. Extract from raw text context if pre-computed fields are empty

        # ── Email (standard pattern) ──────────────────────────────────────────
        if not entities["emails"]:
            emails = re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', text)
            entities["emails"] = list(dict.fromkeys(e.strip().lower() for e in emails))

        # ── Phone (OCR-tolerant: handles dots, dashes, spaces, brackets, + prefix) ─
        if not entities["phones"]:
            raw_phones = re.findall(
                r'(?:\+?\d{1,3}[\s\-.])?'        # optional country code
                r'[\(\[\{]?\d{2,5}[\)\]\}]?'     # area code (possibly in brackets)
                r'[\s\-.]?\d{3,5}'               # middle digits
                r'[\s\-.]?\d{3,5}',              # last digits
                text
            )
            normalized = []
            for p in raw_phones:
                # Keep only digits and a leading +
                digits = re.sub(r'[^\d+]', '', p.strip())
                if len(digits) >= 7:             # filter noise
                    normalized.append(digits)
            entities["phones"] = list(dict.fromkeys(normalized))

        # ── LinkedIn (OCR-tolerant) ────────────────────────────────────────────
        # Matches: linkedin.com/in/handle, linkedin: handle, LinkedIn: handle
        # Also tolerates OCR artefacts like "Iinkedin" or missing dot in ".com"
        linkedin_patterns = [
            r'(?:linkedin[\s.]?com[\s/]+in[\s/]+)([\w\-]+)',   # URL form
            r'(?:linkedin\s*[:/]+\s*)([\w\-]+)',                # "linkedin: handle"
            r'(?:linked\s*in\s*[:/]+\s*)([\w\-]+)',            # "linked in: handle"
            r'(?:l[ií]nked[\s\-]?[iíl]n[\s/]+in[\s/]+)([\w\-]+)',  # OCR: Iinkedin etc.
        ]
        linkedin_val = None
        for lp in linkedin_patterns:
            m = re.search(lp, text, re.IGNORECASE)
            if m:
                linkedin_val = m.group(1).strip()
                break
        entities["linkedin"] = linkedin_val

        # ── GitHub (OCR-tolerant) ─────────────────────────────────────────────
        # Matches: github.com/handle, github: handle, git hub: handle
        github_patterns = [
            r'(?:github[\s.]?com[\s/]+)([\w\-]+)',              # URL form
            r'(?:github\s*[:/]+\s*)([\w\-]+)',                  # "github: handle"
            r'(?:git[\s\-]?hub\s*[:/]+\s*)([\w\-]+)',          # "git hub: handle"
        ]
        github_val = None
        for gp in github_patterns:
            m = re.search(gp, text, re.IGNORECASE)
            if m:
                github_val = m.group(1).strip()
                break
        entities["github"] = github_val


        if not entities["name"]:
            name_match = re.search(r'(?i)\bname\s*:\s*([A-Za-z\s]{2,40})(?:\n|,|$)', text)
            if name_match:
                entities["name"] = name_match.group(1).strip()
            else:
                capital_name = re.search(r'\b([A-Z][a-z]+)\s+([A-Z][a-z]+)\b', text)
                if capital_name:
                    entities["name"] = capital_name.group(0)

        # Section-isolated extraction
        if not entities["addresses"]:
            addr_text = sections.get("ADDRESS", "")
            if addr_text:
                addr_lines = []
                for l in addr_text.split('\n'):
                    l_str = l.strip()
                    digits = re.sub(r'[^\d]', '', l_str)
                    if len(l_str) > 3 and "@" not in l_str and "http" not in l_str and len(digits) < 6:
                        addr_lines.append(l_str)
                entities["addresses"] = addr_lines[:2]

        if not entities["skills"]:
            skills_text = sections.get("SKILLS", "")
            if skills_text:
                items = re.split(r'[,;•\-*]|\n', skills_text)
                entities["skills"] = [i.strip() for i in items if len(i.strip()) > 1 and len(i.strip()) < 30]

        if not entities["projects"]:
            proj_text = sections.get("PROJECTS", "")
            if proj_text:
                proj_lines = [l.strip() for l in proj_text.split('\n') if len(l.strip()) > 5]
                entities["projects"] = proj_lines

        if not entities["experience"]:
            exp_text = sections.get("EXPERIENCE", "")
            if exp_text:
                exp_lines = [l.strip() for l in exp_text.split('\n') if len(l.strip()) > 5]
                entities["experience"] = exp_lines

        if not entities["education"]:
            edu_text = sections.get("EDUCATION", "")
            if edu_text:
                edu_lines = [l.strip() for l in edu_text.split('\n') if len(l.strip()) > 5]
                entities["education"] = edu_lines

        # Verify section-isolated containment
        if "ADDRESS" in sections:
            addr_sec_text = sections["ADDRESS"].lower()
            entities["addresses"] = [a for a in entities["addresses"] if str(a).lower() in addr_sec_text]
            
        if "SKILLS" in sections:
            skills_sec_text = sections["SKILLS"].lower()
            entities["skills"] = [s for s in entities["skills"] if str(s).lower() in skills_sec_text]

        if "PROJECTS" in sections:
            proj_sec_text = sections["PROJECTS"].lower()
            entities["projects"] = [p for p in entities["projects"] if str(p).lower() in proj_sec_text]

        if "EXPERIENCE" in sections:
            exp_sec_text = sections["EXPERIENCE"].lower()
            entities["experience"] = [e for e in entities["experience"] if str(e).lower() in exp_sec_text]

        if "EDUCATION" in sections:
            edu_sec_text = sections["EDUCATION"].lower()
            entities["education"] = [ed for ed in entities["education"] if str(ed).lower() in edu_sec_text]

        # Extract designation, location, human_languages, and programming_languages
        role_kws = {"engineer", "developer", "manager", "architect", "analyst", "specialist", "consultant", "officer", "lead", "designer", "professional"}
        desg_match = re.search(r'(?i)\b(?:designation|job role|role)\s*:\s*([A-Za-z\s]{2,40})(?:\n|,|$)', text)
        if desg_match:
            entities["designation"] = desg_match.group(1).strip()
        
        if not entities["designation"]:
            entities["designation"] = entities.get("designation") or (knowledge.get("designation") if knowledge else None)
        if not entities["designation"] and knowledge:
            k_facts = knowledge.get("facts", {})
            k_entities = knowledge.get("entities", {})
            designations_list = k_entities.get("designations")
            know_designations = knowledge.get("designations")
            entities["designation"] = (
                k_facts.get("designation") or 
                (designations_list[0] if isinstance(designations_list, list) and designations_list else None) or
                (know_designations[0] if isinstance(know_designations, list) and know_designations else None)
            )
        if not entities["designation"]:
            for item in entities["experience"]:
                item_lower = item.lower()
                for kw in role_kws:
                    if kw in item_lower:
                        parts = re.split(r'\b(?:at|for|in)\b', item, flags=re.IGNORECASE)
                        entities["designation"] = parts[0].strip()
                        break
                if entities["designation"]:
                    break

        entities["location"] = entities.get("location") or (entities["addresses"][0] if entities["addresses"] else None)

        HUMAN_LANGS = {
            "english", "tamil", "hindi", "french", "german", "spanish", "mandarin", 
            "japanese", "russian", "arabic", "bengali", "portuguese", "urdu", 
            "telugu", "marathi", "kannada", "malayalam", "gujarati", "punjabi"
        }

        PROGRAMMING_LANGS = {
            "php", "python", "java", "javascript", "c#", "c++", "c", "ruby", "golang", 
            "swift", "kotlin", "typescript", "rust", "scala", "perl", "r", "shell", "bash",
            "sql", "html", "css", "assembly"
        }

        human_langs_found = []
        k_langs = []
        if knowledge:
            k_langs = (
                knowledge.get("languages") or 
                knowledge.get("entities", {}).get("languages", []) or 
                knowledge.get("facts", {}).get("languages", [])
            )
        if isinstance(k_langs, str):
            k_langs = [l.strip() for l in re.split(r'[,;•\-*]|\n', k_langs) if l.strip()]
        for lang in k_langs:
            if lang.lower() in HUMAN_LANGS:
                human_langs_found.append(lang.title())
                
        for lang in HUMAN_LANGS:
            if re.search(r'\b' + re.escape(lang) + r'\b', text.lower()):
                human_langs_found.append(lang.title())
                
        entities["human_languages"] = list(dict.fromkeys(human_langs_found))

        prog_langs_found = []
        for s in entities["skills"]:
            s_lower = s.lower()
            for pl in PROGRAMMING_LANGS:
                if pl == "c#":
                    if "c#" in s_lower:
                        prog_langs_found.append("C#")
                elif pl == "c++":
                    if "c++" in s_lower:
                        prog_langs_found.append("C++")
                elif pl == s_lower or re.search(r'\b' + re.escape(pl) + r'\b', s_lower):
                    prog_langs_found.append(pl.upper() if pl in ["php", "sql", "html", "css"] else pl.title())
                    
        for pl in PROGRAMMING_LANGS:
            pattern = r'\b' + re.escape(pl) + r'\b'
            if pl == "c#":
                pattern = r'\bc#\b'
            elif pl == "c++":
                pattern = r'\bc\+\+'
            if re.search(pattern, text.lower()):
                prog_langs_found.append(pl.upper() if pl in ["php", "sql", "html", "css"] else pl.title())
                
        entities["programming_languages"] = list(dict.fromkeys(prog_langs_found))

        # Filter languages out of general skills to avoid mixing them
        entities["skills"] = [s for s in entities["skills"] if s.lower() not in HUMAN_LANGS]

        # Ensure lists are clean of duplicates while preserving order
        for key in ["phones", "emails", "companies", "skills", "projects", "education", "certifications", "experience", "dates", "amounts", "human_languages", "programming_languages"]:
            val_list = entities.get(key)
            if isinstance(val_list, list):
                seen = set()
                cleaned = []
                for item in val_list:
                    if item and str(item).strip().lower() not in seen:
                        seen.add(str(item).strip().lower())
                        cleaned.append(item)
                entities[key] = cleaned

        return entities
