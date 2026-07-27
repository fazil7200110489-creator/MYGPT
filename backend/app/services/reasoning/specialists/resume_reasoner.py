import re
from typing import Dict, Any, List, Optional, Tuple

from backend.app.services.reasoning.domain_detector import domain_detector
from backend.app.services.reasoning.role_inference_engine import role_inference_engine

# Validation helpers (Problem 7 & v2.3 Validation)
def validate_name(name: Any) -> bool:
    if not name:
        return False
    name_str = str(name).strip()
    if "@" in name_str or "." in name_str or re.search(r'\d+', name_str):
        return False
    if len(name_str.split()) > 4:
        return False
    return True

def validate_skills(skills: Any) -> List[str]:
    if not skills:
        return []
    items = []
    if isinstance(skills, list):
        for x in skills:
            if isinstance(x, str):
                items.extend([s.strip() for s in re.split(r'[,;•\-*|/()]|\n', x) if s.strip()])
            else:
                items.append(str(x))
    else:
        items = [s.strip() for s in re.split(r'[,;•\-*|/()]|\n', str(skills)) if s.strip()]
        
    valid = []
    exclude_words = {
        "developed", "worked", "managed", "trained", "skills", "experience", 
        "learning", "project", "responsible", "using", "with", "building",
        "excellent", "communication", "team", "leader", "motivated", "ability",
        "knowledge", "professional", "seeking", "to", "and", "the", "a", "an",
        "objective", "responsibilities", "summary", "description", "details"
    }
    for s in items:
        s_clean = s.strip()
        s_clean = re.sub(r'^(?:[•\-*]|\d+[\.\)]|\s)+', '', s_clean).strip()
        if not s_clean:
            continue
        words = s_clean.split()
        if len(words) > 3:
            continue
        if any(w.lower() in exclude_words for w in words):
            continue
        valid.append(s_clean)
    return valid

def validate_projects(projects: Any) -> List[str]:
    if not projects:
        return []
    items = []
    if isinstance(projects, list):
        items = projects
    else:
        items = [p.strip() for p in str(projects).split('\n') if p.strip()]
        
    valid = []
    addr_indicators = {"street", "road", "pincode", "lane", "nagar", "city", "state", "bangalore", "chennai", "mumbai"}
    for p in items:
        p_clean = p.strip()
        p_lower = p_clean.lower()
        if any(ind in p_lower for ind in addr_indicators) and re.search(r'\b\d{6}\b', p_lower):
            continue
        if len(p_clean) > 3 and not p_clean.lower().startswith("email:") and not p_clean.lower().startswith("phone:"):
            valid.append(p_clean)
    return valid

def validate_experience(exp: Any) -> List[str]:
    if not exp:
        return []
    items = []
    if isinstance(exp, list):
        for e in exp:
            if isinstance(e, dict):
                items.append(f"{e.get('title', '')} at {e.get('company', '')} ({e.get('years', '')})")
            else:
                items.append(str(e))
    else:
        items = [e.strip() for e in str(exp).split('\n') if e.strip()]
        
    valid = []
    role_kws = {"engineer", "developer", "manager", "architect", "analyst", "specialist", "consultant", "officer", "lead", "designer", "professional", "executive", "bba", "mba"}
    for e in items:
        e_clean = e.strip()
        e_lower = e_clean.lower()
        if "total experience" in e_lower or "at" in e_lower or "-" in e_lower or "–" in e_lower:
            valid.append(e_clean)
            continue
        has_role = any(kw in e_lower for kw in role_kws)
        has_company = any(kw in e_lower for kw in ["at", "company", "ltd", "inc", "corp", "systems", "solutions", "limited", "technologies", "software", "hotels", "university"])
        if has_role or has_company:
            valid.append(e_clean)
    return valid

def validate_education(edu: Any) -> List[str]:
    if not edu:
        return []
    items = []
    if isinstance(edu, list):
        for ed in edu:
            if isinstance(ed, dict):
                items.append(f"{ed.get('degree', '')} from {ed.get('institution', '')}")
            else:
                items.append(str(ed))
    else:
        items = [ed.strip() for ed in str(edu).split('\n') if ed.strip()]
        
    valid = []
    edu_kws = {
        "bachelor", "master", "doctor", "degree", "diploma", "qualification",
        "college", "school", "university", "technology", "institute", "engineering",
        "bca", "mca", "mba", "bba", "b.tech", "m.tech", "be", "me", "bsc", "msc",
        "b.com", "m.com", "b.sc", "m.sc", "b.a", "m.a", "phd", "llb", "llm", "mbbs",
        "ca", "cma", "cpa", "b.arch", "m.arch", "high school", "ssc", "hsc"
    }
    for ed in items:
        ed_clean = ed.strip()
        ed_lower = ed_clean.lower()
        if any(kw in ed_lower for kw in edu_kws) and not any(kw in ed_lower for kw in ["engineer at", "developer at", "manager at"]):
            valid.append(ed_clean)
    return valid

def validate_address(address: Any) -> bool:
    if not address:
        return False
    addr_str = str(address).strip()
    addr_lower = addr_str.lower()
    proj_kws = {"project", "developed", "using", "application", "system", "designed", "implemented", "react", "python"}
    if any(kw in addr_lower for kw in proj_kws) and len(addr_str.split()) > 10:
        return False
    if len(addr_str) < 5:
        return False
    return True

def validate_languages(langs: Any) -> List[str]:
    if not langs:
        return []
    items = []
    if isinstance(langs, list):
        items = langs
    else:
        items = [l.strip() for l in re.split(r'[,;•\-*]|\n', str(langs)) if l.strip()]
    HUMAN_LANGS = {
        "english", "tamil", "hindi", "french", "german", "spanish", "mandarin", 
        "japanese", "russian", "arabic", "bengali", "portuguese", "urdu", 
        "telugu", "marathi", "kannada", "malayalam", "gujarati", "punjabi"
    }
    valid = []
    for l in items:
        l_clean = l.strip()
        if l_clean.lower() in HUMAN_LANGS:
            valid.append(l_clean.title())
    return valid

def calculate_total_experience(experience_list: Any) -> str:
    if not experience_list:
        return "0 years"
    if not isinstance(experience_list, list):
        experience_list = [experience_list]
    clean_list = []
    for item in experience_list:
        if isinstance(item, dict):
            clean_list.append(f"{item.get('title', '')} at {item.get('company', '')} ({item.get('years', '')})")
        else:
            clean_list.append(str(item))

    total_months = 0
    # Prefer pre-extracted if total experience text is already matched in items
    for exp in clean_list:
        if "total experience" in exp.lower():
            match = re.search(r'\b\d+(?:\.\d+)?\s*(?:year|yr)s?\b', exp.lower())
            if match:
                return match.group(0)
    for exp in clean_list:
        exp_lower = exp.lower()
        if "total experience" in exp_lower:
            continue
        dur_match = re.search(r'\b(\d+(?:\.\d+)?)\s*(year|yr)s?\b', exp_lower)
        if dur_match:
            total_months += int(float(dur_match.group(1)) * 12)
            month_match = re.search(r'and\s*(\d+)\s*(month|mon)s?\b', exp_lower)
            if month_match:
                total_months += int(month_match.group(1))
            continue
            
        years = re.findall(r'\b(19\d{2}|20\d{2})\b', exp_lower)
        if len(years) == 2:
            y1, y2 = int(years[0]), int(years[1])
            total_months += (y2 - y1) * 12
        elif len(years) == 1:
            if any(k in exp_lower for k in ["present", "current", "till date", "now"]):
                y1 = int(years[0])
                y2 = 2026
                total_months += (y2 - y1) * 12

    if total_months > 0:
        yrs = total_months // 12
        mns = total_months % 12
        if mns > 0:
            return f"{yrs} years and {mns} months"
        return f"{yrs} years"
    return "0 years"

# Context Filtering (Problem 4)
def filter_facts_by_intent(facts: List[str], intent: str) -> List[str]:
    intent_upper = intent.upper()
    filtered = []
    
    intent_keywords = {
        "SKILLS": ["skills", "technical", "expertise", "languages", "tools", "frameworks", "technologies", "css framework"],
        "EDUCATION": ["education", "academic", "university", "college", "schooling", "qualifications", "degree"],
        "EXPERIENCE": ["experience", "work", "employment", "career", "job", "previous", "company", "designation", "role"],
        "PROJECTS": ["projects", "applications", "portfolio", "built", "developed", "system", "project"],
        "ADDRESS": ["address", "location", "city", "place", "live", "reside"],
        "PHONE": ["phone", "mobile", "cell", "telephone", "contact"],
        "EMAIL": ["email", "gmail", "e-mail", "mail"]
    }
    
    keywords = intent_keywords.get(intent_upper, [])
    if not keywords:
        return facts
        
    for f in facts:
        f_lower = f.lower()
        if any(kw in f_lower for kw in keywords):
            cleaned_lines = []
            for line in f.split('\n'):
                line_strip = line.strip()
                if not line_strip:
                    continue
                # Page numbers / headers / duplicate section names
                if re.match(r'^\bpage\b\s*\d+', line_strip, re.IGNORECASE) or re.match(r'^\d+\s*/\s*\d+$', line_strip):
                    continue
                if line_strip.lower() in ["work experience", "skills", "education", "projects", "certifications", "professional experience"]:
                    continue
                if len(line_strip) < 3 and not line_strip.isalnum():
                    continue
                cleaned_lines.append(line_strip)
            if cleaned_lines:
                filtered.append("\n".join(cleaned_lines))
                

    return filtered if filtered else facts


# ---------------------------------------------------------------------------
# Role Inferencer — data-driven developer role detection
# ---------------------------------------------------------------------------

# ROLE_CONFIG: maps (role_label, confidence_weight) → required skill tokens
# A role is matched when at least `min_matches` tokens from its list are
# found in the candidate's skills.
# Extend this list to add new roles — no code changes required.
ROLE_CONFIG: List[Tuple[str, int, List[str]]] = [
    # (role_label, min_matches, skill_tokens)
    ("Full Stack Developer (MERN)",   3, ["mongodb", "express", "react", "node"]),
    ("Full Stack Developer (MEAN)",   3, ["mongodb", "express", "angular", "node"]),
    ("Full Stack Developer",          3, ["frontend", "backend", "full stack", "fullstack"]),
    ("Mobile Application Developer",  2, ["flutter", "dart"]),
    ("iOS Developer",                 1, ["swift", "ios", "swiftui", "objective-c"]),
    ("Android Developer",             1, ["android", "kotlin", "java android"]),
    ("React Native Developer",        2, ["react native", "react", "mobile"]),
    ("Frontend Developer",            2, ["react", "angular", "vue", "html", "css", "javascript"]),
    ("Backend Developer (Python)",    2, ["django", "flask", "fastapi", "python"]),
    ("Backend Developer (Java)",      2, ["spring", "spring boot", "java", "hibernate"]),
    ("Backend Developer (PHP)",       2, ["laravel", "php", "symfony", "codeigniter"]),
    ("Backend Developer (Node.js)",   2, ["node", "express", "nestjs", "nodejs"]),
    ("Backend Developer",             2, ["rest api", "microservices", "backend", "server"]),
    ("DevOps / Cloud Engineer",       2, ["docker", "kubernetes", "aws", "gcp", "azure", "ci/cd", "jenkins"]),
    ("Data Engineer",                 2, ["spark", "kafka", "airflow", "hadoop", "etl", "pipeline"]),
    ("ML / AI Engineer",              2, ["tensorflow", "pytorch", "keras", "machine learning", "deep learning", "scikit-learn"]),
    ("Data Analyst",                  2, ["power bi", "tableau", "excel", "sql", "data analysis", "pandas"]),
    ("Database Administrator",        2, ["mysql", "postgresql", "oracle", "dba", "sql server", "mongodb"]),
    ("QA / Test Engineer",            2, ["selenium", "cypress", "junit", "testing", "qa", "quality assurance"]),
    ("Software Developer",            1, ["software", "developer", "programmer", "coding"]),
]


class RoleInferencer:
    """Infers a developer role label from a candidate's extracted skills.

    Usage::

        inferencer = RoleInferencer()
        role, evidence = inferencer.infer(["Flutter", "Dart", "Firebase"])
        # → ("Mobile Application Developer", ["flutter", "dart"])
    """

    def infer(
        self, skills: List[str]
    ) -> Tuple[Optional[str], List[str]]:
        """Infer the most specific developer role from a skills list.

        Args:
            skills: List of skill strings (case-insensitive).

        Returns:
            Tuple of (role_label, matched_tokens).
            role_label is None if no role could be inferred.
        """
        if not skills:
            return None, []

        # Flatten skills to a single searchable string for token matching
        skills_text = " ".join(s.lower() for s in skills)

        best_role: Optional[str] = None
        best_count: int = 0
        best_evidence: List[str] = []

        for role_label, min_matches, tokens in ROLE_CONFIG:
            matched = [t for t in tokens if t in skills_text]
            if len(matched) >= min_matches and len(matched) > best_count:
                best_count = len(matched)
                best_role = role_label
                best_evidence = matched

        return best_role, best_evidence

    def build_answer(
        self,
        role: Optional[str],
        evidence: List[str],
        question: str,
        candidate_name: Optional[str] = None,
    ) -> str:
        """Build a natural language answer for a role inference question.

        Args:
            role:           Inferred role label (or None).
            evidence:       Skills that led to the inference.
            question:       Original user question (lowercased).
            candidate_name: Candidate name for personalized response.

        Returns:
            Natural language answer string.
        """
        subject = candidate_name or "The candidate"
        q = question.lower()

        if role is None:
            return (
                f"Based on the skills listed in the resume, it is not possible "
                f"to clearly identify a specific developer role for {subject}."
            )

        skill_list = ", ".join(e.title() for e in evidence[:4])

        # Yes/No phrasing for "is he / can he / suitable" questions
        is_yes_no = any(w in q.split()[:3] for w in ["is", "can", "does", "would", "could"])
        if is_yes_no:
            # Check if the question references a specific role
            q_lower_full = q
            role_lower = role.lower()
            # Check overlap: if the question mentions the inferred role area
            role_words = set(role_lower.replace("(", "").replace(")", "").split())
            q_words = set(re.findall(r"\b\w+\b", q_lower_full))
            overlap = role_words & q_words - {"developer", "engineer", "a", "the", "an"}
            if overlap:
                return (
                    f"Yes. Based on the resume skills ({skill_list}), "
                    f"{subject} appears to be a {role}."
                )
            else:
                # Question asks about a different role than what we inferred
                return (
                    f"Based on the resume skills ({skill_list}), "
                    f"{subject} is best suited as a {role}, "
                    f"not the specific role mentioned in the question."
                )

        return (
            f"Based on the candidate's skills ({skill_list}), "
            f"{subject} appears to be a {role}."
        )


# Singleton instance — created once, reused
_role_inferencer = RoleInferencer()


class ResumeReasoner:
    """Document Specialist for parsing and reasoning over CVs/Resumes."""


    def pre_resolve_entities(self, entities: Dict[str, Any], facts: List[str]):
        if entities.get("_pre_resolved"):
            return

        # 1. Candidate Name
        name_val = entities.get("candidate_name") or entities.get("name")
        if name_val:
            name_val = str(name_val).strip() if validate_name(name_val) else None
        if not name_val and facts:
            for f in facts:
                for line in f.split('\n'):
                    if "name" in line.lower() and not any(k in line.lower() for k in ["father", "mother", "spouse", "company"]):
                        cleaned = re.sub(r'^(?:name|candidate name|applicant name)\s*[:\-]?\s*', '', line, flags=re.IGNORECASE).strip()
                        if validate_name(cleaned):
                            name_val = cleaned
                            break
                if name_val:
                    break
        entities["candidate_name"] = name_val

        # 2. Father Name
        father_val = entities.get("father_name")
        if father_val:
            father_val = str(father_val).strip() if validate_name(father_val) else None
        if not father_val and facts:
            for f in facts:
                for line in f.split('\n'):
                    if "father" in line.lower():
                        cleaned = re.sub(r'^(?:father\'s name|father name)\s*[:\-]?\s*', '', line, flags=re.IGNORECASE).strip()
                        if validate_name(cleaned):
                            father_val = cleaned
                            break
                if father_val:
                    break
        entities["father_name"] = father_val

        # 3. Mother Name
        mother_val = entities.get("mother_name")
        if mother_val:
            mother_val = str(mother_val).strip() if validate_name(mother_val) else None
        if not mother_val and facts:
            for f in facts:
                for line in f.split('\n'):
                    if "mother" in line.lower():
                        cleaned = re.sub(r'^(?:mother\'s name|mother name)\s*[:\-]?\s*', '', line, flags=re.IGNORECASE).strip()
                        if validate_name(cleaned):
                            mother_val = cleaned
                            break
                if mother_val:
                    break
        entities["mother_name"] = mother_val

        # 4. Email
        email_val = entities.get("email") or entities.get("emails")
        if email_val:
            email_val = email_val if isinstance(email_val, str) else email_val[0]
        if not email_val and facts:
            for f in facts:
                match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', f)
                if match:
                    email_val = match.group(0)
                    break
        entities["email"] = email_val

        # 5. Phone
        phone_val = entities.get("phone") or entities.get("phones")
        if phone_val:
            phone_val = phone_val if isinstance(phone_val, str) else phone_val[0]
        if not phone_val and facts:
            for f in facts:
                match = re.search(r'\b\d{6,15}\b', f)
                if match:
                    phone_val = match.group(0)
                    break
        entities["phone"] = phone_val

        # 6. Designation
        desg_val = entities.get("designation") or entities.get("designations")
        if desg_val:
            desg_val = desg_val if isinstance(desg_val, str) else desg_val[0]
        entities["designation"] = desg_val

        # 7. Location/Address
        addr_val = entities.get("address") or entities.get("addresses") or entities.get("location")
        if addr_val:
            addr_val = addr_val if isinstance(addr_val, str) else addr_val[0]
        entities["address"] = addr_val

        # 8. Experience
        exp_val = entities.get("work_experience") or entities.get("experience") or []
        exp_val = validate_experience(exp_val)
        if not exp_val and facts:
            for f in facts:
                for line in f.split('\n'):
                    line_strip = line.strip()
                    if "experience" in line_strip.lower() or "work" in line_strip.lower() or "employment" in line_strip.lower() or "engineer" in line_strip.lower() or "developer" in line_strip.lower():
                        cleaned = re.sub(r'^(?:experience|work experience|employment history)\s*[:\-]?\s*', '', line_strip, flags=re.IGNORECASE).strip()
                        if cleaned:
                            exp_val.append(cleaned)
            exp_val = validate_experience(exp_val)
        entities["experience"] = exp_val

        # 9. Education
        edu_val = entities.get("education") or []
        edu_val = validate_education(edu_val)
        if not edu_val and facts:
            for f in facts:
                for line in f.split('\n'):
                    line_strip = line.strip()
                    if "education" in line_strip.lower() or "degree" in line_strip.lower() or "university" in line_strip.lower() or "college" in line_strip.lower() or "academic" in line_strip.lower():
                        cleaned = re.sub(r'^(?:education|degree|university)\s*[:\-]?\s*', '', line_strip, flags=re.IGNORECASE).strip()
                        if cleaned:
                            edu_val.append(cleaned)
            edu_val = validate_education(edu_val)
        entities["education"] = edu_val

        # 10. Skills
        skills_val = entities.get("skills") or []
        skills_val = validate_skills(skills_val)
        if not skills_val and facts:
            for f in facts:
                for line in f.split('\n'):
                    line_strip = line.strip()
                    if "skill" in line_strip.lower() or "technologies" in line_strip.lower() or line_strip.startswith(("•", "-", "*")):
                        cleaned = re.sub(r'^(?:skills|technical skills|technologies)\s*[:\-]?\s*', '', line_strip, flags=re.IGNORECASE).strip()
                        for s in re.split(r'[,;•\-*|/()]', cleaned):
                            s_clean = s.strip()
                            if s_clean:
                                skills_val.append(s_clean)
            skills_val = validate_skills(skills_val)
        entities["skills"] = skills_val

        # 11. Projects
        proj_val = entities.get("projects") or []
        proj_val = validate_projects(proj_val)
        if not proj_val and facts:
            for f in facts:
                for line in f.split('\n'):
                    line_strip = line.strip()
                    if "education" in line_strip.lower() or "bachelor" in line_strip.lower() or "degree" in line_strip.lower() or "college" in line_strip.lower():
                        continue
                    if "project" in line_strip.lower() or "developed" in line_strip.lower() or "portfolio" in line_strip.lower() or ":" in line_strip:
                        cleaned = re.sub(r'^(?:projects|project)\s*[:\-]?\s*', '', line_strip, flags=re.IGNORECASE).strip()
                        for sub in cleaned.split(','):
                            sub_clean = sub.strip()
                            if len(sub_clean) > 3:
                                proj_val.append(sub_clean)
            proj_val = validate_projects(proj_val)
        entities["projects"] = proj_val

        # 12. Certifications
        certs_val = entities.get("certifications") or []
        if not certs_val and facts:
            for f in facts:
                for line in f.split('\n'):
                    line_strip = line.strip()
                    if any(kw in line_strip.lower() for kw in ["certification", "certifications", "certified", "license"]):
                        cleaned = re.sub(r'^(?:certifications|certification)\s*[:\-]?\s*', '', line_strip, flags=re.IGNORECASE).strip()
                        if cleaned:
                            certs_val.append(cleaned)
        entities["certifications"] = certs_val

        entities["_pre_resolved"] = True

    def select_and_validate(self, entities: Dict[str, Any], facts: List[str], intent: str, key_names: List[str], validator_func, raw_extractor_func=None) -> Any:
        # Priority 1: Structured Entity
        for k in key_names:
            val = entities.get(k)
            if val:
                res = validator_func(val)
                if res:
                    return res

        # Priority 2: Section-specific facts
        filtered_facts = filter_facts_by_intent(facts, intent)
        if filtered_facts:
            accumulated = []
            for f in filtered_facts:
                for line in f.split('\n'):
                    line_clean = line.strip()
                    if not line_clean:
                        continue
                    extracted = raw_extractor_func(line_clean) if raw_extractor_func else line_clean
                    if extracted:
                        res = validator_func(extracted)
                        if res:
                            if isinstance(res, list):
                                accumulated.extend(res)
                            else:
                                return res
            if accumulated:
                return accumulated

        # Priority 3: Generic facts
        if facts:
            accumulated = []
            for f in facts:
                for line in f.split('\n'):
                    line_clean = line.strip()
                    if not line_clean:
                        continue
                    extracted = raw_extractor_func(line_clean) if raw_extractor_func else line_clean
                    if extracted:
                        res = validator_func(extracted)
                        if res:
                            if isinstance(res, list):
                                accumulated.extend(res)
                            else:
                                return res
            if accumulated:
                return accumulated

        return None

    def reason(self, entities: Dict[str, Any], facts: List[str], intent: str, question: Optional[str] = None) -> Any:
        """Extracts the appropriate field or values based on the intent and entities."""
        self.pre_resolve_entities(entities, facts)
        intent_upper = intent.upper()
        text = "\n".join(facts) if facts else ""

        # 1. Zero-Inference policy for unmentioned attributes
        if question:
            q_lower = question.lower().strip()
            # Do not infer marital status, salary, relocation, notice period, spouse, children
            outside_kws = ["marital", "married", "salary", "notice period", "notice", "relocate", "relocation", "spouse", "children", "gender", "male", "female", "sex"]
            if any(kw in q_lower for kw in outside_kws):
                return "The uploaded resume does not mention this information."

        # 2. Check for Yes/No questions classification
        is_yes_no = False
        if question:
            q_lower = question.lower().strip()
            first_word = q_lower.split()[0] if q_lower.split() else ""
            if first_word in ["did", "does", "is", "has", "was", "can", "are", "should", "would", "do"]:
                is_yes_no = True

        if is_yes_no and question:
            q_lower = question.lower().strip()

            # 1. Graduation / Education check
            if any(k in q_lower for k in ["graduated", "graduate", "educated"]):
                edu = entities.get("education") or []
                edu = validate_education(edu)
                if edu:
                    degree = edu[0].split('\n')[0].strip()
                    return (
                        f"Answer:\nYes\n\n"
                        f"Reason:\nThe candidate holds a {degree}.\n\n"
                        f"Evidence:\nEducation section\n\n"
                        f"Confidence:\n95%"
                    )
                return (
                    f"Answer:\nNo\n\n"
                    f"Reason:\nThe uploaded resume does not mention graduation or degree details.\n\n"
                    f"Evidence:\nEducation section\n\n"
                    f"Confidence:\n95%"
                )

            # 2. Total Experience check
            if any(k in q_lower for k in ["experienced", "experience"]) and not any(k in q_lower for k in ["flutter", "react", "python", "java", "node", "api", "mobile", "backend", "frontend", "cloud"]):
                exp = entities.get("work_experience") or entities.get("experience") or []
                total_exp_str = calculate_total_experience(exp)
                if total_exp_str != "0 years":
                    return (
                        f"Answer:\nYes\n\n"
                        f"Reason:\nThe candidate has approximately {total_exp_str} of professional experience.\n\n"
                        f"Evidence:\nWork Experience section\n\n"
                        f"Confidence:\n95%"
                    )

            # 3a. Location-based yes/no check: "Is she from Chennai?" / "Is he based in Bangalore?"
            LOCATION_YES_NO_PATTERNS = [
                r'\b(?:from|based in|living in|located in|residing in|staying in|is she from|is he from|native of)\b'
            ]
            is_location_query = any(re.search(p, q_lower) for p in LOCATION_YES_NO_PATTERNS)
            if is_location_query:
                from backend.app.services.reasoning.candidate_profile_builder import candidate_profile_builder
                profile = candidate_profile_builder.build_profile(entities, text)
                city_m = re.search(r'(?:from|in|of)\s+([A-Za-z]+)', q_lower)
                if city_m:
                    city_q = city_m.group(1).strip().title()
                    current = profile.get("current_location", "") or ""
                    permanent = profile.get("permanent_address", "") or ""
                    work = profile.get("work_location", "") or ""
                    locations_str = f"{current}, {permanent}, {work}"
                    if city_q.lower() in locations_str.lower():
                        return (
                            f"Answer:\nYes\n\n"
                            f"Reason:\nCandidate is associated with {city_q}. "
                            f"Current Location: {current}. Permanent Address: {permanent}."
                            f"{'Work Location: ' + work + '.' if work and work != 'Not Mentioned' else ''}\n\n"
                            f"Evidence:\n{', '.join(profile.get('location_sources', ['Location section']))}\n\n"
                            f"Confidence:\n90%"
                        )
                    else:
                        return (
                            f"Answer:\nNo\n\n"
                            f"Reason:\nThe resume does not indicate the candidate is from {city_q}. "
                            f"Current Location: {current}. Permanent Address: {permanent}.\n\n"
                            f"Evidence:\n{', '.join(profile.get('location_sources', ['Location section']))}\n\n"
                            f"Confidence:\n88%"
                        )

            # 3b. Domain-Aware Role / Suitability Yes/No check
            role_keywords = [
                "app developer", "backend developer", "frontend developer",
                "full stack developer", "fullstack developer", "mobile developer",
                "devops engineer", "cloud engineer", "ml engineer", "ai engineer",
                "developer", "engineer", "accountant", "hr", "analyst", "designer",
                "consultant", "architect", "manager", "officer", "suitable", "suitability",
                "fit", "work as", "role"
            ]
            if any(rk in q_lower for rk in role_keywords):
                domain = domain_detector.detect_domain(entities, text)
                is_suitable, reason_msg, evidence_sec = role_inference_engine.infer_role_suitability(entities, target_role_query=question, domain=domain)
                ans_str = "Yes" if is_suitable else "No"
                return (
                    f"Answer:\n{ans_str}\n\n"
                    f"Reason:\n{reason_msg}\n\n"
                    f"Evidence:\n{evidence_sec}\n\n"
                    f"Confidence:\n95%"
                )

            # 4. Extract topic for technology / skill / entity inquiry
            YES_NO_STOP = {
                "did", "does", "is", "has", "was", "can", "are", "should",
                "would", "do", "she", "he", "they", "it", "this", "that",
                "know", "have", "study", "complete", "work", "worked", "use",
                "used", "got", "get", "hold", "holds", "at", "in", "with",
                "the", "a", "an", "on", "for", "of", "to", "or", "and",
                "candidate", "applicant", "person", "resume", "experienced",
                "graduated", "graduate", "any", "ever", "certificate", "experience"
            }
            q_tokens = [
                w for w in re.findall(r'\b\w[\w+#]*\b', q_lower)
                if w not in YES_NO_STOP and len(w) > 1
            ]

            if not q_tokens:
                return (
                    f"Answer:\nNo\n\n"
                    f"Reason:\nThe uploaded resume does not mention this information.\n\n"
                    f"Evidence:\nResume Document\n\n"
                    f"Confidence:\n95%"
                )

            topic = " ".join(q_tokens)
            
            # Map query to appropriate intent
            target_intent = "SKILLS"
            if any(k in topic for k in ["project", "app", "portfolio"]):
                target_intent = "PROJECTS"
            elif any(k in topic for k in ["cert", "ibm", "aws cert", "microsoft"]):
                target_intent = "CERTIFICATIONS"
            elif any(k in topic for k in ["company", "worked at"]):
                target_intent = "EXPERIENCE"

            from backend.app.services.reasoning.evidence_selector import evidence_selector
            sections_dict = entities.get("sections", {}) if isinstance(entities, dict) else {}
            selected = evidence_selector.select(
                entities=entities,
                sections=sections_dict,
                intent=target_intent,
                topic=topic,
                question=question
            )

            if selected.is_found:
                evidence_detail = ", ".join(selected.matched_tokens) if selected.matched_tokens else selected.section_name
                return (
                    f"Answer:\nYes\n\n"
                    f"Reason:\n{selected.reasoning}\n\n"
                    f"Evidence:\n{evidence_detail}\n\n"
                    f"Confidence:\n88%"
                )
            else:
                return (
                    f"Answer:\nNo\n\n"
                    f"Reason:\n{selected.reasoning}\n\n"
                    f"Evidence:\n{selected.section_name}\n\n"
                    f"Confidence:\n88%"
                )

        # 3. Route through Candidate Profile Builder & Entity Resolver (Single Source of Truth)
        from backend.app.services.reasoning.candidate_profile_builder import candidate_profile_builder
        from backend.app.services.reasoning.entity_resolver import entity_resolver

        profile = entities.get("candidate_profile") if isinstance(entities, dict) else None
        if not profile:
            profile = candidate_profile_builder.build_profile(entities, text)
            if isinstance(entities, dict):
                entities["candidate_profile"] = profile

        resolved_data, subtree_path, was_updated = entity_resolver.resolve(
            profile=profile,
            intent=intent_upper,
            question=question,
            raw_text=text,
            raw_entities=entities
        )

        if intent_upper in ["DOMAIN", "INDUSTRY"]:
            conf = profile.get("primary_domain_confidence", 85)
            sec = profile.get("secondary_domain", "")
            sec_conf = profile.get("secondary_domain_confidence", 0)
            result = f"Primary Domain: {profile['domain']} ({conf}% confidence)"
            if sec and sec != "Not Applicable":
                result += f"\nSecondary Domain: {sec} ({sec_conf}% confidence)"
            return result

        elif intent_upper in ["CONTACT", "CONTACT_DETAILS"]:
            return (
                f"Candidate Information\n\n"
                f"Name: {profile['name']}\n"
                f"Email: {profile['email']}\n"
                f"Phone: {profile['phone']}\n"
                f"Current Location: {profile['current_location']}\n"
                f"Permanent Address: {profile['permanent_address']}\n"
                f"LinkedIn: {profile['linkedin']}\n"
                f"GitHub: {profile['github']}\n"
                f"Portfolio: {profile['portfolio']}"
            )

        elif intent_upper in ["PHONE", "PHONE_NUMBERS"]:
            return profile["phone"]

        elif intent_upper == "EMAIL":
            return profile["email"]

        elif intent_upper in ["CANDIDATE_NAME", "NAME", "NAMES"]:
            return profile["name"]

        elif intent_upper == "LINKEDIN":
            return profile["linkedin"]

        elif intent_upper == "GITHUB":
            return profile["github"]

        elif intent_upper == "PORTFOLIO":
            return profile["portfolio"]

        elif intent_upper in ["ADDRESS", "LOCATION"]:
            # Handle "Is she from Chennai?" type queries
            q_lower = (question or "").lower()
            city_m = re.search(r'from\s+([A-Za-z]+)', q_lower) or re.search(r'in\s+([A-Za-z]+)', q_lower)
            if city_m:
                city_q = city_m.group(1).title()
                current = profile.get("current_location", "")
                permanent = profile.get("permanent_address", "")
                work = profile.get("work_location", "")
                locations_str = f"{current}, {permanent}, {work}"
                if city_q.lower() in locations_str.lower():
                    return (
                        f"Answer:\nYes\n\n"
                        f"Reason:\nCandidate is associated with {city_q}. "
                        f"Current Location: {current}. Permanent Address: {permanent}."
                        f"{'Work Location: ' + work + '.' if work and work != 'Not Mentioned' else ''}\n\n"
                        f"Evidence:\n{', '.join(profile.get('location_sources', ['Location section']))}\n\n"
                        f"Confidence:\n90%"
                    )
                else:
                    return (
                        f"Answer:\nNo\n\n"
                        f"Reason:\nThe resume does not indicate the candidate is from {city_q}. "
                        f"Current Location: {current}. Permanent Address: {permanent}.\n\n"
                        f"Evidence:\n{', '.join(profile.get('location_sources', ['Location section']))}\n\n"
                        f"Confidence:\n88%"
                    )
            # General address / native place query
            addr_details = profile.get("address_details", {})
            full_addr = profile.get("address") or profile.get("permanent_address") or profile.get("current_location")
            if full_addr and full_addr != "Not Mentioned":
                lines = [f"Address: {full_addr}"]
                if addr_details.get("city") and addr_details["city"] != "Not Mentioned":
                    lines.append(f"City: {addr_details['city']}")
                if addr_details.get("state") and addr_details["state"] != "Not Mentioned":
                    lines.append(f"State: {addr_details['state']}")
                if addr_details.get("pincode") and addr_details["pincode"] != "Not Mentioned":
                    lines.append(f"Pincode: {addr_details['pincode']}")
                return "\n".join(lines)
            return "The uploaded resume does not mention address details."

        elif intent_upper == "COMPANIES":
            companies = profile.get("companies", [])
            if not companies:
                timeline = profile.get("experience_timeline", [])
                companies = [t["company"] for t in timeline if t.get("company") and t["company"] != "Not Mentioned"]
            if companies:
                return "Companies Worked In:\n\n" + "\n".join(f"• {c}" for c in dict.fromkeys(companies))
            return "The uploaded resume does not mention company details."

        elif intent_upper == "DESIGNATION":
            return profile["designation"]

        elif intent_upper == "CURRENT_COMPANY":
            timeline = profile.get("experience_timeline", [])
            if timeline:
                latest = timeline[-1]
                return (
                    f"Current Company: {latest.get('company', 'Not Mentioned')}\n"
                    f"Current Role: {latest.get('title', 'Not Mentioned')}\n"
                    f"Since: {latest.get('years', 'Not Mentioned')}"
                )
            hist = profile.get("experience_history", [])
            return hist[0] if hist else "Not Mentioned"

        elif intent_upper == "ERP_PLATFORMS":
            erps = profile.get("erp_platforms", [])
            return erps if erps else "The resume does not mention any ERP platforms."

        elif intent_upper == "AWARDS":
            awards = profile.get("awards", [])
            if not awards:
                return "The resume does not mention any awards or recognitions."
            lines = []
            for a in awards:
                name = a.get("name", "Not Mentioned")
                org = a.get("organization", "Not Mentioned")
                yr = a.get("year", "Not Mentioned")
                lines.append(f"• {name}" + (f" — {org}" if org != "Not Mentioned" else "") + (f" ({yr})" if yr != "Not Mentioned" else ""))
            return "Awards & Recognitions:\n" + "\n".join(lines)

        elif intent_upper in ["CGPA", "CGPA_PERCENTAGE"]:
            for edu in profile.get("education", []):
                cgpa = edu.get("cgpa_percentage", "")
                if cgpa and cgpa not in ("Not Mentioned", "Not Specified", ""):
                    return f"Academic Score: {cgpa}\n(From: {edu.get('degree', 'Higher Education')} — {edu.get('institution', 'Institution')})"
            return "The resume does not mention CGPA or percentage."

        elif intent_upper in ["GRADUATION_YEAR", "GRADUATION"]:
            years = []
            for edu in profile.get("education", []):
                year = edu.get("year", "")
                degree = edu.get("degree", "")
                if year and year != "Not Mentioned":
                    years.append(f"{degree} — {year}" if degree and degree != "Not Mentioned" else year)
            return "\n".join(years) if years else "The resume does not mention graduation year."

        elif intent_upper == "CAREER_TRANSITION":
            ct = profile.get("career_transition", {})
            if ct.get("is_transition"):
                prev_domains = ", ".join(ct.get("previous_domains", []))
                return (
                    f"Career Transition Detected\n\n"
                    f"Transition Path: {ct.get('transition_path', 'Not Mentioned')}\n"
                    f"Current Career: {ct.get('current_domain', 'Not Mentioned')}\n"
                    f"Previous Career(s): {prev_domains or 'Not Mentioned'}"
                )
            return f"No significant career transition detected. Candidate has consistently worked in {profile.get('domain', 'their current domain')}."

        elif intent_upper == "DOMAIN_EXPERIENCE":
            per_domain = profile.get("per_domain_experience", {})
            if not per_domain:
                return f"Total Experience: {profile.get('total_experience', 'Not Mentioned')}"
            lines = [f"• {d}: {exp}" for d, exp in per_domain.items()]
            return (
                f"Total Professional Experience: {profile.get('total_experience', 'Not Mentioned')}\n\n"
                f"Experience by Domain:\n" + "\n".join(lines)
            )

        elif intent_upper == "TIMELINE":
            timeline = profile.get("experience_timeline", [])
            if not timeline:
                return "Experience timeline information not available in the resume."
            lines = []
            for entry in timeline:
                years = entry.get("years", "")
                title = entry.get("title", "")
                company = entry.get("company", "")
                domain = entry.get("domain", "")
                lines.append(f"{years}\n  {title}\n  {company}" + (f" ({domain})" if domain else ""))
            return "Experience Timeline:\n\n" + "\n\n".join(lines)

        elif intent_upper == "SKILL_VERIFY":
            q_lower = (question or "").lower()
            # Extract skill being asked about
            skill_patterns = [
                r'(?:know|use|have|learned|experienced in|proficient in|familiar with)\s+([A-Za-z\s\+\.\#]+?)(?:\?|$|\s+and)',
                r'(?:does|is|can)\s+(?:she|he|the candidate|candidate)\s+(?:know|use|have)\s+([A-Za-z\s\+\.\#]+?)(?:\?|$)',
            ]
            topic_skill = ""
            for pat in skill_patterns:
                m = re.search(pat, q_lower)
                if m:
                    topic_skill = m.group(1).strip()
                    break
            if not topic_skill:
                # Single-word query IS the skill
                topic_skill = (question or "").strip().rstrip("?")

            topic_lower = topic_skill.lower()
            all_skills_lower = [s.lower() for s in profile.get("skills", [])]
            all_skills_text = " ".join(all_skills_lower)
            found = any(topic_lower in s for s in all_skills_lower) or topic_lower in all_skills_text

            if found:
                matching = [s for s in profile.get("skills", []) if topic_lower in s.lower()]
                evidence_str = ", ".join(matching[:3]) if matching else topic_skill.title()
                return (
                    f"Answer:\nYes\n\n"
                    f"Reason:\n{topic_skill.title()} is listed in the candidate's skill set.\n\n"
                    f"Evidence:\n{evidence_str}\n\n"
                    f"Confidence:\n92%"
                )
            else:
                return (
                    f"Answer:\nNo\n\n"
                    f"Reason:\nThe resume does not mention {topic_skill.title()} in the skills section.\n\n"
                    f"Evidence:\nSkills section\n\n"
                    f"Confidence:\n88%"
                )

        elif intent_upper == "ROLE_COMPARE":
            q_lower = (question or "").lower()
            # Extract two roles from query: "HR Manager vs HR Business Partner"
            vs_match = re.search(r'(.+?)\s+(?:vs\.?|versus|or|compared to|and)\s+(.+?)(?:\?|$)', q_lower)
            if vs_match:
                role_a = vs_match.group(1).strip().title()
                role_b = vs_match.group(2).strip().title()
                comparison = role_inference_engine.compare_roles(entities, role_a, role_b, profile["domain"])
                ra = comparison[role_a]
                rb = comparison[role_b]
                return (
                    f"Role Comparison: {role_a} vs {role_b}\n\n"
                    f"**{role_a}:** {ra['match_percentage']}% match — {ra['suitability_tier']}\n"
                    f"  Matching: {', '.join(ra['matching_skills']) or 'Core domain skills'}\n"
                    f"  Missing: {', '.join(ra['missing_skills']) or 'None'}\n\n"
                    f"**{role_b}:** {rb['match_percentage']}% match — {rb['suitability_tier']}\n"
                    f"  Matching: {', '.join(rb['matching_skills']) or 'Core domain skills'}\n"
                    f"  Missing: {', '.join(rb['missing_skills']) or 'None'}\n\n"
                    f"Recommendation: {comparison['recommendation']}"
                )
            return "Please specify two roles to compare (e.g. 'HR Manager vs HR Business Partner')."

        elif intent_upper == "HUMAN_LANGUAGES":
            langs = entities.get("human_languages") or entities.get("languages") or []
            return validate_languages(langs) if langs else None

        elif intent_upper == "PROGRAMMING_LANGUAGES":
            progs = profile.get("programming_languages", [])
            return progs if progs else profile.get("skills") or None

        elif intent_upper in ["SUMMARY", "PROFILE_SUMMARY"]:
            recommended_roles = role_inference_engine.recommend_roles(profile, profile["domain"])
            
            display_desig = profile.get("designation")
            if not display_desig or display_desig == "Not Mentioned":
                display_desig = recommended_roles[0] if recommended_roles else "Professional"
                
            roles_str = ", ".join(recommended_roles) if recommended_roles else display_desig
            edu_list = profile.get("education", [])
            edu_str = edu_list[0]["degree"] if edu_list and edu_list[0].get("degree") != "Not Mentioned" else "Not Mentioned"
            certs = profile.get("certifications", [])
            certs_str = ", ".join(certs[:3]) if certs else "Not Mentioned"
            proj_list = profile.get("projects", [])
            proj_str = "\n".join(f"• {p}" for p in proj_list[:3]) if proj_list else "• Not Mentioned"
            skills_str = ", ".join(profile["skills"][:10]) if profile["skills"] else "Not Mentioned"

            # Transition summary line
            ct = profile.get("career_transition", {})
            transition_line = ""
            if ct.get("is_transition"):
                transition_line = f"• **Career Path:** {ct.get('transition_path', '')}\n"

            # Fetch strengths
            strengths_list = profile.get("insights", {}).get("strengths", [])
            strengths_str = "\n".join(f"• {s}" for s in strengths_list) if strengths_list else "• Not Mentioned"

            highlights = (
                f"## Candidate Highlights\n\n"
                f"### Candidate Overview\n"
                f"• **Name:** {profile['name']}\n"
                f"• **Designation:** {display_desig}\n"
                f"• **Primary Domain:** {profile['domain']} ({profile.get('primary_domain_confidence', '—')}% confidence)\n"
                f"{transition_line}"
                f"• **Total Experience:** {profile['total_experience']}\n"
                f"• **Current Domain Experience:** {profile.get('current_domain_experience', 'Not Mentioned')}\n"
                f"• **Recommended Roles:** {roles_str}\n\n"
                f"### Strengths\n"
                f"{strengths_str}\n\n"
                f"### Education\n"
                f"• {edu_str}\n\n"
                f"### Technical & Professional Expertise\n"
                f"• **Core Skills:** {skills_str}\n"
                f"• **HR Skills:** {', '.join(profile.get('hr_skills', [])) or 'Not Mentioned'}\n"
                f"• **ERP Systems:** {', '.join(profile.get('erp_platforms', [])) or 'Not Mentioned'}\n\n"
                f"### Certifications\n"
                f"• {certs_str}\n\n"
                f"### Awards & Recognitions\n"
                f"• {', '.join(a['name'] for a in profile.get('awards', [])[:3]) or 'Not Mentioned'}\n\n"
                f"### Key Projects\n"
                f"{proj_str}"
            )
            return highlights

        elif intent_upper == "SKILLS":
            if question and any(fw_kw in question.lower() for fw_kw in ["framework", "library", "libraries"]):
                FRAMEWORKS = {
                    "yii2", "angular", "react", "vue", "django", "flask", "laravel",
                    "spring", "express", "next.js", "fastapi", "rails", "asp.net"
                }
                found = [s for s in profile["skills"] if any(fw in s.lower() for fw in FRAMEWORKS)]
                return found if found else None

            # Return categorized skills for HR/domain resumes
            hr_skills = profile.get("hr_skills", [])
            tech_skills = profile.get("technical_skills", [])
            soft_skills = profile.get("soft_skills", [])

            if hr_skills:
                result_parts = []
                if hr_skills:
                    result_parts.append(f"HR Skills: {', '.join(hr_skills)}")
                if tech_skills:
                    result_parts.append(f"Technical Skills: {', '.join(tech_skills)}")
                if soft_skills:
                    result_parts.append(f"Soft Skills: {', '.join(soft_skills)}")
                return "\n".join(result_parts) if result_parts else profile["skills"]

            return profile["skills"] if profile["skills"] else "Not Mentioned"

        elif intent_upper == "EDUCATION":
            structured_edu = []
            for item in profile["education"]:
                degree = item.get("degree", "Not Mentioned")
                inst = item.get("institution", "Not Mentioned")
                year = item.get("year", "Not Mentioned")
                spec = item.get("specialization", "Not Mentioned")
                cgpa = item.get("cgpa_percentage", "Not Mentioned")
                edu_level = item.get("education_level", "")

                if degree == "Not Mentioned" and inst == "Not Mentioned":
                    continue

                block = f"{edu_level + ': ' if edu_level and edu_level != 'Not Mentioned' else ''}{degree}"
                if inst != "Not Mentioned":
                    block += f"\n  Institution: {inst}"
                if year != "Not Mentioned":
                    block += f"\n  Year: {year}"
                if spec != "Not Mentioned":
                    block += f"\n  Specialization: {spec}"
                if cgpa != "Not Mentioned":
                    block += f"\n  CGPA/Percentage: {cgpa}"
                structured_edu.append(block)
            return structured_edu if structured_edu else "Not Mentioned"

        elif intent_upper == "CERTIFICATIONS":
            certs = profile.get("certifications", [])
            return certs if certs else "The resume does not mention any certifications."

        elif intent_upper in ["EXPERIENCE", "WORK_EXPERIENCE"]:
            if question:
                q_lower = question.lower().strip()
                if any(k in q_lower for k in ["years of experience", "how many years", "total experience"]):
                    return f"Total Experience: {profile['total_experience']}"

            ct = profile.get("career_transition", {})
            per_domain = profile.get("per_domain_experience", {})

            result = f"Total Professional Experience: {profile['total_experience']}"
            if profile.get("current_domain_experience") and profile["current_domain_experience"] != "Not Mentioned":
                result += f"\nCurrent Domain: {profile['current_domain_experience']}"
            if per_domain and len(per_domain) > 1:
                result += "\n\nExperience by Domain:"
                for d, exp in per_domain.items():
                    result += f"\n• {d}: {exp}"

            timeline = profile.get("experience_timeline", [])
            if timeline:
                result += "\n\nWork History:"
                for entry in reversed(timeline):
                    result += f"\n• {entry.get('years', '')} — {entry.get('title', '')} at {entry.get('company', '')}"

            return result

        elif intent_upper == "PROJECTS":
            if not profile.get("has_dedicated_projects", False) or not profile["projects"]:
                # Fallback to responsibilities from experience
                hist = profile.get("experience_history", [])
                if hist:
                    resp_str = "\n".join(f"• {e}" for e in hist[:5])
                    return (
                        f"No separate Projects section was found in this resume.\n\n"
                        f"Key Professional Responsibilities:\n{resp_str}"
                    )
                return "No separate Projects section was found in this resume. The resume does not detail individual projects."
            return profile["projects"]

        elif intent_upper == "BASIC_PROFILE":
            ct = profile.get("career_transition", {})
            transition_str = ct.get("transition_path", "Not Mentioned") if ct.get("is_transition") else "Not Applicable"
            recs = role_inference_engine.recommend_roles(profile, profile["domain"])
            return {
                "Name": profile["name"],
                "Designation": profile["designation"],
                "Primary Domain": profile["domain"],
                "Secondary Domain": profile.get("secondary_domain", "Not Applicable"),
                "Career Transition": transition_str,
                "Total Experience": profile["total_experience"],
                "Current Domain Experience": profile.get("current_domain_experience", "Not Mentioned"),
                "Education": profile["education"][0]["degree"] if profile["education"] and profile["education"][0].get("degree") != "Not Mentioned" else "Not Mentioned",
                "Email": profile["email"],
                "Phone": profile["phone"],
                "Current Location": profile.get("current_location", "Not Mentioned"),
                "LinkedIn": profile["linkedin"],
                "Recommended Roles": ", ".join(recs)
            }

        elif intent_upper in ["GENERAL", "ROLE_INFERENCE"]:
            q_for_role = question or "Role Suitability"
            suitability_res = role_inference_engine.calculate_role_similarity(entities, q_for_role, profile["domain"])

            matching_str = ", ".join(suitability_res["matching_skills"]) if suitability_res["matching_skills"] else "Core domain skills"
            missing_str = ", ".join(suitability_res["missing_skills"]) if suitability_res["missing_skills"] else "None"

            return (
                f"Answer:\n{suitability_res['suitability_tier']} for {suitability_res['target_role']} (Match: {suitability_res['match_percentage']}%)\n\n"
                f"Reason:\n{suitability_res['reason']}\n\n"
                f"Matching Skills:\n{matching_str}\n\n"
                f"Missing Skills:\n{missing_str}\n\n"
                f"Evidence:\n{suitability_res['evidence']}\n\n"
                f"Confidence:\n88%"
            )

        # Final fallback: return section-filtered facts or None if empty
        filtered = filter_facts_by_intent(facts, intent)
        return filtered if filtered else None

    def calculate_resume_health_score(self, entities: Dict[str, Any], text: str = "") -> Dict[str, Any]:
        """Calculates candidate Resume Health Score (0-100%) and itemized component checklist using CandidateProfileBuilder."""
        from backend.app.services.reasoning.candidate_profile_builder import candidate_profile_builder
        profile = candidate_profile_builder.build_profile(entities, text)
        return {
            "health_score": profile["health_score"],
            "checklist": profile["health_checklist"]
        }

    def generate_candidate_insights(self, entities: Dict[str, Any], text: str = "") -> Dict[str, Any]:
        """Generates candidate profile insights using CandidateProfileBuilder."""
        from backend.app.services.reasoning.candidate_profile_builder import candidate_profile_builder
        profile = candidate_profile_builder.build_profile(entities, text)
        return profile["insights"]
