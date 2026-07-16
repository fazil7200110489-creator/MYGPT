from typing import Dict, Any, List, Optional
import re

class ResumeReasoner:
    """Document Specialist for parsing and reasoning over CVs/Resumes."""

    def reason(self, entities: Dict[str, Any], facts: List[str], intent: str, question: Optional[str] = None) -> Any:
        """Extracts the appropriate field or values based on the intent and entities."""
        intent_upper = intent.upper()

        # Check for Yes/No questions classification
        is_yes_no = False
        if question:
            q_lower = question.lower().strip()
            first_word = q_lower.split()[0] if q_lower.split() else ""
            if first_word in ["did", "does", "is", "has", "was", "can", "are", "should", "would", "do"]:
                is_yes_no = True

        if is_yes_no and question:
            q_clean = question.lower().strip()
            q_words = [w.lower() for w in re.findall(r'\b\w+\b', q_clean) if w.lower() not in [
                "did", "she", "he", "does", "is", "has", "was", "can", "are", "should", "would", "do",
                "they", "know", "study", "complete", "at", "in", "with", "the", "a", "an", "on", "knows"
            ]]
            
            # Check Skills
            skills = entities.get("skills") or []
            skills_lower = [s.lower() for s in skills]
            skill_matched = None
            for w in q_words:
                for s in skills_lower:
                    if w in s or s in w:
                        skill_matched = s
                        break
                if skill_matched:
                    break

            # Check Education
            edu = entities.get("education") or []
            edu_lower = [e.lower() for e in edu]
            edu_matched = None
            for w in q_words:
                for e in edu_lower:
                    if w in e:
                        edu_matched = e
                        break
                if edu_matched:
                    break

            # Check Experience
            exp = entities.get("work_experience") or []
            exp_lower = [ex.lower() for ex in exp]
            exp_matched = None
            for w in q_words:
                for ex in exp_lower:
                    if w in ex:
                        exp_matched = ex
                        break
                if exp_matched:
                    break

            candidate_name = entities.get("candidate_name") or entities.get("name") or "the candidate"
            if skill_matched:
                return f"Yes, {candidate_name} has knowledge of {skill_matched.title()}."
            elif edu_matched:
                return f"Yes, {candidate_name} studied {edu_matched.title()}."
            elif exp_matched:
                return f"Yes, {candidate_name} worked at {exp_matched.title()}."

            # Search raw context/facts
            keyword_found = False
            found_sentence = ""
            for fact in facts:
                for w in q_words:
                    if len(w) > 2 and w in fact.lower():
                        sentences = re.split(r'(?<=\.|\?)\s+', fact)
                        for s in sentences:
                            if w in s.lower():
                                found_sentence = s.strip()
                                keyword_found = True
                                break
                        if keyword_found:
                            break
                if keyword_found:
                    break

            if keyword_found:
                # Ensure it starts with Yes/No followed by one short explanation
                return f"Yes, the document states: \"{found_sentence}\""

            return "The uploaded document does not mention this."

        if intent_upper in ["PHONE", "PHONE_NUMBERS"]:
            return entities.get("phone") or entities.get("phones", [None])[0] or (facts[0] if facts else None)

        elif intent_upper == "EMAIL":
            return entities.get("email") or entities.get("emails", [None])[0] or (facts[0] if facts else None)

        elif intent_upper in ["CANDIDATE_NAME", "NAME", "NAMES"]:
            return entities.get("candidate_name") or entities.get("name") or (facts[0] if facts else None)

        elif intent_upper == "FATHER_NAME":
            return entities.get("father_name") or (facts[0] if facts else None)

        elif intent_upper == "MOTHER_NAME":
            return entities.get("mother_name") or (facts[0] if facts else None)

        elif intent_upper == "ADDRESS":
            return entities.get("address") or (facts[0] if facts else None)

        elif intent_upper in ["DATE_OF_BIRTH", "DOB"]:
            return entities.get("date_of_birth") or (facts[0] if facts else None)

        elif intent_upper == "GENDER":
            return entities.get("gender") or (facts[0] if facts else None)

        elif intent_upper == "LANGUAGES":
            return entities.get("languages") or (facts[0] if facts else None)

        elif intent_upper == "OBJECTIVE":
            return entities.get("objective") or (facts[0] if facts else None)

        elif intent_upper in ["SUMMARY", "PROFILE_SUMMARY"]:
            # Generate a natural 4-6 sentences summary using extracted entities
            name = entities.get("candidate_name") or entities.get("name") or "The candidate"
            skills = entities.get("skills") or []
            experience = entities.get("work_experience") or []
            education = entities.get("education") or []
            projects = entities.get("projects") or []
            designations = entities.get("designations") or []
            
            role = designations[0] if designations else ("Professional" if experience else "Candidate")
            
            sentences = []
            sentences.append(f"{name} is a professional {role}.")
            
            if education:
                sentences.append(f"She completed her academic qualifications in {education[0]}.")
            
            if experience:
                jobs = ", ".join(experience[:2])
                sentences.append(f"Her work history includes roles such as {jobs}.")
            
            if skills:
                skills_str = ", ".join(skills[:5])
                sentences.append(f"She has technical expertise in core skills like {skills_str}.")
            
            if projects:
                proj_str = ", ".join(projects[:2])
                sentences.append(f"Additionally, she has worked on projects including {proj_str}.")
                
            sentences.append("She is focused on delivering high-quality contributions in her professional field.")
            return " ".join(sentences)

        elif intent_upper == "SKILLS":
            skills = entities.get("skills") or []
            filtered_skills = []
            exclude_kws = {"knowledge", "experience", "experience in", "trained", "worked on", "responsible for", "managed", "developed", "project", "developed a", "working as"}
            for s in skills:
                s_strip = s.strip()
                s_lower = s_strip.lower()
                if len(s_strip) > 40:
                    continue
                if len(s_strip.split()) > 5:
                    continue
                if any(kw in s_lower for kw in exclude_kws):
                    continue
                if s_lower in ["skills", "technical skills", "education", "experience", "professional experience"]:
                    continue
                filtered_skills.append(s_strip)
            return filtered_skills if filtered_skills else (facts if facts else None)

        elif intent_upper == "TECHNICAL_SKILLS":
            return entities.get("technical_skills") or (facts if facts else None)

        elif intent_upper == "HARDWARE_SKILLS":
            return entities.get("hardware_skills") or (facts if facts else None)

        elif intent_upper == "SOFTWARE_SKILLS":
            return entities.get("software_skills") or (facts if facts else None)

        elif intent_upper == "EDUCATION":
            edu = entities.get("education") or []
            structured_edu = []
            for item in edu:
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
                
                # Cleanup formatting
                degree = re.sub(r'^[•\-*\d\.\s]+', '', degree).strip()
                inst = re.sub(r'^[•\-*\d\.\s]+', '', inst).strip()
                
                block = f"{degree}\n  - Institution: {inst}\n  - University: {inst}\n  - Percentage/CGPA: {pct}\n  - Year: {year}"
                structured_edu.append(block)
            return structured_edu if structured_edu else (facts if facts else None)

        elif intent_upper == "CERTIFICATIONS":
            certs = entities.get("certifications")
            if not certs or len(certs) == 0:
                return "No certifications were found in the resume."
            return certs

        elif intent_upper in ["EXPERIENCE", "WORK_EXPERIENCE"]:
            exp = entities.get("work_experience") or []
            structured_exp = []
            for item in exp:
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
                
                role = re.sub(r'^[•\-*\d\.\s]+', '', role).strip()
                company = re.sub(r'^[•\-*\d\.\s]+', '', company).strip()
                
                block = f"{role} at {company} ({duration})\n  - Responsibilities: Handled project execution and technical responsibilities."
                structured_exp.append(block)
            if entities.get("total_experience"):
                structured_exp.append(f"Total experience: {entities['total_experience']}")
            return structured_exp if structured_exp else (facts if facts else None)

        elif intent_upper == "PROJECTS":
            projects = entities.get("projects") or []
            structured_projects = []
            for p in projects:
                p_str = str(p).strip()
                p_str = re.sub(r'^[•\-*\d\.\s]+', '', p_str).strip()
                if not p_str:
                    continue
                
                parts = re.split(r'\s+-\s+|\s*:\s*', p_str, 1)
                title = parts[0].strip()
                desc = parts[1].strip() if len(parts) > 1 else "Description not specified."
                
                skills = entities.get("skills") or []
                techs = [s.strip() for s in skills if s.strip().lower() in desc.lower()]
                techs_str = ", ".join(techs) if techs else None
                
                proj_block = f"Project Name: {title}\n  - Description: {desc}"
                if techs_str:
                    proj_block += f"\n  - Technologies: {techs_str}"
                proj_block += f"\n  - Responsibilities: Contributed to project implementation and deliverables."
                structured_projects.append(proj_block)
            return structured_projects if structured_projects else (facts if facts else None)

        elif intent_upper == "COMPANIES":
            return entities.get("companies") or (facts if facts else None)

        elif intent_upper == "DESIGNATIONS":
            return entities.get("designations") or (facts if facts else None)

        return facts if facts else None
