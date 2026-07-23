from typing import Dict, Any, List, Optional
import re

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
        items = exp
    else:
        items = [e.strip() for e in str(exp).split('\n') if e.strip()]
        
    valid = []
    role_kws = {"engineer", "developer", "manager", "architect", "analyst", "specialist", "consultant", "officer", "lead", "designer", "professional"}
    for e in items:
        e_clean = e.strip()
        e_lower = e_clean.lower()
        if "total experience" in e_lower:
            valid.append(e_clean)
            continue
        has_role = any(kw in e_lower for kw in role_kws)
        has_company = any(kw in e_lower for kw in ["at", "company", "ltd", "inc", "corp", "systems", "solutions", "limited", "technologies", "software"])
        if has_role and has_company:
            valid.append(e_clean)
    return valid

def validate_education(edu: Any) -> List[str]:
    if not edu:
        return []
    items = []
    if isinstance(edu, list):
        items = edu
    else:
        items = [ed.strip() for ed in str(edu).split('\n') if ed.strip()]
        
    valid = []
    edu_kws = {"bachelor", "master", "doctor", "degree", "diploma", "qualification", "college", "school", "university", "technology", "institute", "engineering", "bca", "mca", "b.tech", "m.tech", "be", "me", "bsc", "msc", "high school", "ssc", "hsc"}
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

def calculate_total_experience(experience_list: List[str]) -> str:
    total_months = 0
    # Prefer pre-extracted if total experience text is already matched in items
    for exp in experience_list:
        if "total experience" in exp.lower():
            match = re.search(r'\b\d+(?:\.\d+)?\s*(?:year|yr)s?\b', exp.lower())
            if match:
                return match.group(0)
    for exp in experience_list:
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
            
            # graduation check
            if "graduated" in q_lower or "graduate" in q_lower or "educated" in q_lower:
                edu = entities.get("education") or []
                edu = validate_education(edu)
                if not edu and facts:
                    for f in facts:
                        for line in f.split('\n'):
                            line_strip = line.strip()
                            if "education" in line_strip.lower() or "degree" in line_strip.lower() or "university" in line_strip.lower() or "college" in line_strip.lower() or "academic" in line_strip.lower():
                                cleaned = re.sub(r'^(?:education|degree|university)\s*[:\-]?\s*', '', line_strip, flags=re.IGNORECASE).strip()
                                if cleaned:
                                    edu.append(cleaned)
                    edu = validate_education(edu)
                if edu:
                    degree = edu[0].split('\n')[0].strip()
                    return f"Yes. The candidate holds a {degree}."
                return "No. The uploaded document does not mention this."

            # experience check
            if "experienced" in q_lower or "experience" in q_lower:
                exp = entities.get("work_experience") or entities.get("experience") or []
                total_exp_str = calculate_total_experience(exp)
                if total_exp_str != "0 years":
                    return f"Yes, the candidate has approximately {total_exp_str} of experience."

            # Step 1: Extract the candidate entity from the question by stripping
            # stop-words.  We want the meaningful noun that the user is asking about.
            YES_NO_STOP = {
                "did", "does", "is", "has", "was", "can", "are", "should",
                "would", "do", "she", "he", "they", "it", "this", "that",
                "know", "have", "study", "complete", "work", "worked", "use",
                "used", "got", "get", "hold", "holds", "at", "in", "with",
                "the", "a", "an", "on", "for", "of", "to", "or", "and",
                "candidate", "applicant", "person", "resume", "experienced",
                "graduated", "graduate", "any", "ever", "certificate",
            }
            q_tokens = [
                w for w in re.findall(r'\b\w[\w+#]*\b', q_lower)
                if w not in YES_NO_STOP and len(w) > 1
            ]

            if not q_tokens:
                return "The uploaded document does not mention this."

            # Step 2: Determine entity type by inspecting what's present in the
            # resume's structured data – no predefined technology list.
            skills_all    = entities.get("skills") or []
            prog_langs    = entities.get("programming_languages") or []
            projects_all  = entities.get("projects") or []
            exp_all       = entities.get("experience") or []
            certs_all     = entities.get("certifications") or []
            companies_all = entities.get("companies") or []

            # Build flat, lower-cased search corpora for each domain
            corpus_tech   = " ".join([s.lower() for s in skills_all + prog_langs])
            corpus_proj   = " ".join([p.lower() for p in projects_all])
            corpus_exp    = " ".join([e.lower() for e in exp_all])
            corpus_certs  = " ".join([c.lower() for c in certs_all])
            corpus_orgs   = " ".join([o.lower() for o in companies_all])
            corpus_all    = "\n".join([corpus_tech, corpus_proj, corpus_exp,
                                       corpus_certs, corpus_orgs, text.lower()])

            # Classification signals (org-like suffixes, cert-like prefixes, etc.)
            ORG_SUFFIXES  = {"ltd", "inc", "corp", "pvt", "llc", "solutions",
                             "systems", "technologies", "services", "group"}
            CERT_PREFIXES = {"aws", "ibm", "microsoft", "google", "oracle",
                             "cisco", "pmp", "scrum", "comptia", "itil", "azure"}

            def _make_pattern(token: str) -> str:
                return r'\b' + re.escape(token) + r'\b'

            matched_token  = None
            matched_domain = None  # 'tech' | 'cert' | 'employer' | 'project' | 'general'
            found_in_resume = False

            for token in q_tokens:
                token_l = token.lower()

                # Does the token appear in any corpus?
                token_in_resume = bool(re.search(_make_pattern(token_l), corpus_all))

                # Classify the token's domain
                in_tech   = bool(re.search(_make_pattern(token_l), corpus_tech))
                in_proj   = bool(re.search(_make_pattern(token_l), corpus_proj))
                in_exp    = bool(re.search(_make_pattern(token_l), corpus_exp))
                in_certs  = bool(re.search(_make_pattern(token_l), corpus_certs))
                in_orgs   = bool(re.search(_make_pattern(token_l), corpus_orgs))

                # Heuristic classification signals
                looks_like_cert  = token_l in CERT_PREFIXES or in_certs
                looks_like_org   = token_l in ORG_SUFFIXES or in_orgs
                looks_like_proj  = in_proj and not in_tech
                looks_like_tech  = in_tech or (not looks_like_cert and not looks_like_org and not looks_like_proj and in_exp)

                if token_in_resume:
                    matched_token = token
                    found_in_resume = True
                    if looks_like_cert:
                        matched_domain = "cert"
                    elif looks_like_org:
                        matched_domain = "employer"
                    elif looks_like_proj:
                        matched_domain = "project"
                    elif looks_like_tech:
                        matched_domain = "tech"
                    else:
                        matched_domain = "general"
                    break

            candidate_name = entities.get("candidate_name") or entities.get("name") or "the candidate"
            if not validate_name(candidate_name):
                candidate_name = "the candidate"

            if found_in_resume and matched_token:
                display = matched_token.upper() if len(matched_token) <= 3 else matched_token.title()
                if matched_domain == "cert":
                    return f"Yes. The resume mentions {display} as a certification or achievement."
                elif matched_domain == "employer":
                    return f"Yes. {candidate_name} has worked at or with {display}."
                elif matched_domain == "project":
                    return f"Yes. The resume mentions a project related to {display}."
                elif matched_domain == "tech":
                    return f"Yes. The resume mentions experience with {display}."
                else:
                    return f"Yes. The resume mentions {display}."

            # Not found in any corpus
            if q_tokens:
                display = q_tokens[0].upper() if len(q_tokens[0]) <= 3 else q_tokens[0].title()
                return f"The uploaded resume does not mention {display}."

            return "The uploaded document does not mention this."

        # 3. Priority routing with Candidate ans        if intent_upper in ["PHONE", "PHONE_NUMBERS"]:
            return entities.get("phone")

        elif intent_upper == "EMAIL":
            return entities.get("email")

        elif intent_upper in ["CANDIDATE_NAME", "NAME", "NAMES"]:
            return entities.get("candidate_name")

        elif intent_upper == "FATHER_NAME":
            return entities.get("father_name")

        elif intent_upper == "MOTHER_NAME":
            return entities.get("mother_name")

        elif intent_upper == "ADDRESS":
            return entities.get("address")

        elif intent_upper == "DESIGNATION":
            return entities.get("designation")

        elif intent_upper in ["DATE_OF_BIRTH", "DOB"]:
            return entities.get("date_of_birth") or (facts[0] if facts else None)

        elif intent_upper == "GENDER":
            gender = entities.get("gender")
            if gender and gender.lower() in ["male", "female", "other"]:
                return gender.title()
            match = re.search(r'\bgender\s*:\s*(male|female|other)\b', text.lower())
            if match:
                return match.group(1).title()
            return "The uploaded resume does not mention this information."

        elif intent_upper == "HUMAN_LANGUAGES":
            langs = entities.get("human_languages") or entities.get("languages") or []
            langs = validate_languages(langs)
            if not langs and facts:
                HUMAN_LANGS = {
                    "english", "tamil", "hindi", "french", "german", "spanish", "mandarin", 
                    "japanese", "russian", "arabic", "bengali", "portuguese", "urdu", 
                    "telugu", "marathi", "kannada", "malayalam", "gujarati", "punjabi"
                }
                for f in facts:
                    for line in f.split('\n'):
                        for word in re.findall(r'\b\w+\b', line.lower()):
                            if word in HUMAN_LANGS:
                                langs.append(word.title())
                langs = validate_languages(langs)
            return langs if langs else None

        elif intent_upper == "PROGRAMMING_LANGUAGES":
            prog = entities.get("programming_languages") or []
            if not prog and facts:
                PROGRAMMING_LANGS = {
                    "php", "python", "java", "javascript", "c#", "c++", "c", "ruby", "golang", 
                    "swift", "kotlin", "typescript", "rust", "scala", "perl", "r", "shell", "bash",
                    "sql", "html", "css", "assembly"
                }
                for f in facts:
                    for line in f.split('\n'):
                        for word in re.findall(r'\b[\w+#+]+\b', line.lower()):
                            if word in PROGRAMMING_LANGS:
                                prog.append(word.title())
            return prog if prog else None

        elif intent_upper == "OBJECTIVE":
            return entities.get("objective") or (facts[0] if facts else None)

        elif intent_upper in ["SUMMARY", "PROFILE_SUMMARY"]:
            name = entities.get("candidate_name")
            exp_list = entities.get("experience") or []
            total_exp = calculate_total_experience(exp_list)
            role = entities.get("designation") or ("Professional" if exp_list else None)
            edu_list = entities.get("education") or []
            edu_str = edu_list[0] if edu_list else None
            skills_list = entities.get("skills") or []
            skills_str = ", ".join(skills_list[:5]) if skills_list else None
            proj_list = entities.get("projects") or []
            proj_str = ", ".join(proj_list[:2]) if proj_list else None
            
            parts = []
            if name:
                parts.append(f"{name.strip()} is a professional {role or 'Candidate'}.")
            else:
                parts.append(f"The candidate is a professional {role or 'Candidate'}.")
                
            if total_exp != "0 years":
                parts.append(f"They have a total of {total_exp} of professional work experience.")
                
            if edu_str:
                clean_edu = edu_str.split('\n')[0].strip()
                parts.append(f"For their academic background, they completed {clean_edu}.")
                
            if skills_str:
                parts.append(f"Their core technical skills include {skills_str}.")
                
            if proj_str:
                clean_proj = proj_str.split('\n')[0].replace("Project Name:", "").strip()
                parts.append(f"Additionally, they have successfully developed major projects such as {clean_proj}.")
                
            parts.append(f"They are committed to leveraging their expertise for software design and organizational development.")
            
            summary_paragraph = " ".join(parts)
            words = summary_paragraph.split()
            if len(words) > 120:
                summary_paragraph = " ".join(words[:120]) + "."
            return summary_paragraph

        elif intent_upper == "SKILLS":
            is_framework = False
            if question:
                q_lower = question.lower()
                if "framework" in q_lower or "library" in q_lower or "libraries" in q_lower:
                    is_framework = True
            
            skills_val = entities.get("skills") or []
            if is_framework and skills_val:
                FRAMEWORKS = {
                    "yii2", "angular", "angular 4", "angularjs", "react", "react native", 
                    "vue", "django", "flask", "laravel", "spring", "spring boot", "express", 
                    "next.js", "nextjs", "nuxt", "svelte", "jquery", "bootstrap", "tailwind", 
                    "fastapi", "rails", "ruby on rails", "asp.net", "symfony", "codeigniter"
                }
                frameworks_found = [s for s in skills_val if any(fw in s.lower() for fw in FRAMEWORKS)]
                return frameworks_found if frameworks_found else None
            return skills_val if skills_val else None

        elif intent_upper == "EDUCATION":
            edu_val = entities.get("education") or []
            if not edu_val:
                return None
                
            structured_edu = []
            for item in edu_val:
                item_str = str(item).strip()
                degree = item_str
                inst = "Not specified"
                year = "Not specified"
                pct = "Not specified"
                
                inst_match = re.search(r'\bat\s+([A-Za-z\s\d,]+)', item_str)
                if inst_match:
                    inst = inst_match.group(1).strip()
                    degree = re.sub(r'\bat\s+([A-Za-z\s\d,]+)', '', degree).strip()
                
                year_match = re.search(r'\((\d{4})\)', item_str)
                if year_match:
                    year = year_match.group(1).strip()
                    degree = re.sub(r'\((\d{4})\)', '', degree).strip()
                
                pct_match = re.search(r'\b(\d+(?:\.\d+)?%|\d+\.\d+\s*(?:CGPA|GPA)?)\b', item_str, re.IGNORECASE)
                if pct_match:
                    pct = pct_match.group(1).strip()
                    degree = re.sub(r'\b(\d+(?:\.\d+)?%|\d+\.\d+\s*(?:CGPA|GPA)?)\b', '', degree, flags=re.IGNORECASE).strip()
                
                degree = re.sub(r'^(?:[•\-*]|\d+[\.\)]|\s)+', '', degree).strip()
                inst = re.sub(r'^(?:[•\-*]|\d+[\.\)]|\s)+', '', inst).strip()
                
                block = f"{degree}\n  - Institution: {inst}\n  - University: {inst}\n  - Percentage/CGPA: {pct}\n  - Year: {year}"
                structured_edu.append(block)
            return structured_edu if structured_edu else None

        elif intent_upper == "CERTIFICATIONS":
            return entities.get("certifications") or None

        elif intent_upper in ["EXPERIENCE", "WORK_EXPERIENCE"]:
            exp_val = entities.get("experience") or []
            if not exp_val:
                return None
            
            total_exp_val = calculate_total_experience(exp_val)
            has_total_exp = any("total experience" in str(x).lower() for x in exp_val)
            
            structured_exp = []
            for item in exp_val:
                item_str = str(item).strip()
                if "total experience" in item_str.lower():
                    structured_exp.append(item_str)
                    continue
                role = "Professional"
                company = "Organization"
                duration = "Not specified"
                
                role_match = re.search(r'^([A-Za-z\s]+)\s+at\s+([A-Za-z\s\d,]+)', item_str)
                if role_match:
                    role = role_match.group(1).strip()
                    company = role_match.group(2).strip()
                else:
                    parts = item_str.split('at')
                    if len(parts) > 1:
                        role = parts[0].strip()
                        company = parts[1].strip()
                    else:
                        role = item_str
                
                dur_match = re.search(r'\(([^)]+)\)', item_str)
                if dur_match:
                    duration = dur_match.group(1).strip()
                    company = re.sub(r'\([^)]+\)', '', company).strip()
                
                role = re.sub(r'^(?:[•\-*]|\d+[\.\)]|\s)+', '', role).strip()
                company = re.sub(r'^(?:[•\-*]|\d+[\.\)]|\s)+', '', company).strip()
                
                block = f"{role} at {company} ({duration})\n  - Responsibilities: Handled project execution and technical responsibilities."
                structured_exp.append(block)
                
            if not has_total_exp and total_exp_val != "0 years":
                structured_exp.append(f"Total experience: {total_exp_val}")
                
            return structured_exp if structured_exp else None

        elif intent_upper == "PROJECTS":
            proj_val = entities.get("projects") or []
            if not proj_val:
                return None
            structured_projects = []
            for p in proj_val:
                p_str = str(p).strip()
                p_str = re.sub(r'^(?:[•\-*]|\d+[\.\)]|\s)+', '', p_str).strip()
                if not p_str:
                    continue
                parts = re.split(r'\s+-\s+|\s*:\s*', p_str, maxsplit=1)
                title = parts[0].strip()
                structured_projects.append(title)
            return structured_projects if structured_projects else None

        elif intent_upper == "BASIC_PROFILE":
            name = entities.get("candidate_name") or "Not Mentioned"
            designation = entities.get("designation") or "Not Mentioned"
            location = entities.get("address") or "Not Mentioned"
            exp_list = entities.get("experience") or []
            experience = calculate_total_experience(exp_list)
            if experience == "0 years":
                experience = "Not Mentioned"
            edu_list = entities.get("education") or []
            education = edu_list[0] if edu_list else "Not Mentioned"
            email = entities.get("email") or "Not Mentioned"
            phone = entities.get("phone") or "Not Mentioned"
            
            return {
                "Name": name,
                "Designation": designation,
                "Location": location,
                "Experience": experience,
                "Education": education,
                "Email": email,
                "Phone": phone
            }

        filtered_facts = filter_facts_by_intent(facts, intent)
        return filtered_facts if filtered_facts else None
