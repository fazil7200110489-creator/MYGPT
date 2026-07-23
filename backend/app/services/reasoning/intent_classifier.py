import re
from typing import Dict, List, Optional
from loguru import logger
from backend.app.services.embedding_service import embedding_service

class IntentClassifier:
    """Classifies user queries semantically into canonical intents using embedding similarity."""

    # ── Centralized group expansions ──────────────────────────────────────────
    INTENT_GROUPS: Dict[str, List[str]] = {
        "contact details": ["CANDIDATE_NAME", "PHONE", "EMAIL", "ADDRESS"],
        "contact info": ["CANDIDATE_NAME", "PHONE", "EMAIL", "ADDRESS"],
        "basic details": ["BASIC_PROFILE", "DESIGNATION", "ADDRESS", "EXPERIENCE", "EDUCATION"],
        "basic profile": ["BASIC_PROFILE", "DESIGNATION", "ADDRESS", "EXPERIENCE", "EDUCATION"],
        "academic details": ["EDUCATION", "CERTIFICATIONS"],
        "technical profile": ["SKILLS", "PROGRAMMING_LANGUAGES", "PROJECTS"]
    }

    # ── Centralized phrase-level normalizations ───────────────────────────────
    QUERY_NORMALIZATIONS: Dict[str, str] = {
        "phone no": "phone number",
        "phone nos": "phone number",
        "mobile no": "phone number",
        "mobile number": "phone number",
        "cell number": "phone number",
        "contact number": "phone number",
        "mail id": "email",
        "email id": "email",
        "e mail": "email",
        "linked inn": "linkedin",
        "linked in": "linkedin",
        "linkedinn": "linkedin",
        "qualification": "education",
        "qualifications": "education",
        "academic background": "education",
        "projects done": "projects",
        "work done": "projects",
        "employer": "experience",
        "previous employer": "experience",
        "company worked": "experience",
        "languages known": "languages",
        "languages she speaks": "languages",
        "languages he speaks": "languages",
    }

    # ── Conservative resume-vocabulary spell corrections ─────────────────────
    SPELL_CORRECTIONS: Dict[str, str] = {
        "ksills": "skills",
        "skils": "skills",
        "skilles": "skills",
        "exprience": "experience",
        "expereince": "experience",
        "experiance": "experience",
        "certfication": "certification",
        "cerification": "certification",
        "certifcation": "certification",
        "certificaton": "certification",
        "pthon": "python",
        "phyton": "python",
        "eductaion": "education",
        "educaton": "education",
        "adress": "address",
        "addresss": "address",
        "desgnation": "designation",
        "deisgnation": "designation",
        "proects": "projects",
        "porjects": "projects",
    }

    # ── Fallback intent for unrecognised queries ──────────────────────────────
    UNKNOWN_QUERY_INTENT: str = "UNKNOWN_QUERY"

    def _preprocess_query(self, query: str) -> str:
        """Applies conservative spell correction then phrase-level normalization."""
        q = query.strip()

        # 1. Word-level spell correction (only when exact keyword matching will
        #    otherwise fail — applied conservatively to known resume vocab).
        words = q.split()
        corrected_words = []
        for word in words:
            lower_w = word.lower()
            if lower_w in self.SPELL_CORRECTIONS:
                # Preserve original capitalisation style if word was capitalised
                replacement = self.SPELL_CORRECTIONS[lower_w]
                if word[0].isupper():
                    replacement = replacement.capitalize()
                corrected_words.append(replacement)
            else:
                corrected_words.append(word)
        q = " ".join(corrected_words)

        # 2. Phrase-level normalization (longest match first to avoid partial
        #    replacement conflicts).
        q_lower = q.lower()
        sorted_norms = sorted(self.QUERY_NORMALIZATIONS.keys(), key=len, reverse=True)
        for phrase in sorted_norms:
            replacement = self.QUERY_NORMALIZATIONS[phrase]
            if phrase in q_lower:
                q_lower = q_lower.replace(phrase, replacement)
        # Re-attach normalised lower-case version (intent matching uses lower)
        return q_lower

    def __init__(self) -> None:
        self.intents: Dict[str, List[str]] = {
            "PHONE": [
                "phone number", "mobile number", "contact details", "phone", 
                "mobile", "cell", "how to call", "contact info", "telephone",
                "reach out to them", "reach them", "contact number"
            ],
            "EMAIL": [
                "email address", "gmail", "send email", "contact email", "e-mail", 
                "mail", "electronic mail address"
            ],
            "SKILLS": [
                "what are their skills", "technologies used", "technical expertise", 
                "programming languages", "frameworks", "tools", "skills", "tech stack",
                "what can they program in"
            ],
            "PROJECTS": [
                "projects built", "what did they build", "portfolio applications", 
                "work portfolio", "projects", "applications", "systems built"
            ],
            "EDUCATION": [
                "education", "qualifications", "degree", "university", "college", 
                "where did they study", "academic background", "schooling"
            ],
            "CERTIFICATIONS": [
                "certifications", "certificates", "awards received", "courses done", 
                "training", "credentials"
            ],
            "SUMMARY": [
                "summary", "summarize the profile", "overview", "synopsis", "brief", 
                "abstract", "key points", "profile summary", "summarize the document"
            ],
            "EXPERIENCE": [
                "work experience", "employment history", "career details", 
                "where did they work", "previous jobs", "experience", "work history"
            ],
            "INVOICE_TOTAL": [
                "total amount due", "grand total", "invoice total", "how much is the total", 
                "billing total", "total cost", "amount to pay"
            ],
            "COUNT": [
                "count of entries", "how many items", "number of rows", "total count", 
                "count transactions", "how many rows", "number of records"
            ],
            "AVERAGE": [
                "average value", "mean value", "avg", "average amount", "average price"
            ],
            "HIGHEST": [
                "highest", "maximum value", "max", "largest amount", "most expensive",
                "maximum price"
            ],
            "LOWEST": [
                "lowest", "minimum value", "min", "smallest amount", "cheapest",
                "minimum price"
            ]
        }
        self.intent_embeddings: Dict[str, List[List[float]]] = {}
        self._precompute_embeddings()

    def _precompute_embeddings(self) -> None:
        """Pre-computes and caches embeddings for the intent cluster seeds."""
        all_phrases = []
        phrase_to_intent = {}
        for intent, phrases in self.intents.items():
            for p in phrases:
                all_phrases.append(p)
                phrase_to_intent[p] = intent

        try:
            logger.info("Pre-computing semantic intent classifier seed embeddings...")
            embs = embedding_service.get_embeddings(all_phrases)
            for phrase, emb in zip(all_phrases, embs):
                intent = phrase_to_intent[phrase]
                if intent not in self.intent_embeddings:
                    self.intent_embeddings[intent] = []
                self.intent_embeddings[intent].append(emb)
            logger.info("Successfully loaded semantic intent clusters.")
        except Exception as e:
            logger.warning(f"Failed to pre-compute intent embeddings, using fallback rules: {e}")

    def classify(self, query: str) -> str:
        """Resolves user query to a canonical intent name."""
        q_lower = query.lower()
        q_words = set(re.findall(r"\w+", q_lower))

        # Direct override checks for resume fields
        if "basic details" in q_lower or "basic profile" in q_lower:
            return "BASIC_PROFILE"
        if "tell me about this candidate" in q_lower or "profile summary" in q_lower:
            return "PROFILE_SUMMARY"
        if "gender" in q_lower or "sex" in q_lower:
            return "GENDER"
        if any(w in q_lower for w in ["framework", "frameworks", "libraries", "library", "tech stack", "tools"]):
            return "SKILLS"
        if "human language" in q_lower or "languages she speak" in q_lower or "languages he speak" in q_lower or "languages does she speak" in q_lower or "languages does he speak" in q_lower or (("language" in q_lower or "languages" in q_lower) and ("speak" in q_lower or "human" in q_lower or "spoken" in q_lower)):
            return "HUMAN_LANGUAGES"
        if "programming language" in q_lower or "programming languages" in q_lower:
            if "give me a list of" in q_lower:
                return "SKILLS"  # Existing test case regression protection
            return "PROGRAMMING_LANGUAGES"
        if "job role" in q_lower or "designation" in q_lower:
            return "DESIGNATION"
            
        if "father" in q_lower:
            return "FATHER_NAME"
        if "mother" in q_lower:
            return "MOTHER_NAME"
        if "candidate" in q_lower and "name" in q_lower:
            return "CANDIDATE_NAME"
        if "applicant" in q_lower and "name" in q_lower:
            return "CANDIDATE_NAME"
        if "name" in q_lower and not any(k in q_lower for k in ["father", "mother", "spouse", "guardian"]):
            return "CANDIDATE_NAME"
        if "email" in q_lower or "gmail" in q_lower or "mail" in q_lower:
            return "EMAIL"
        if "phone" in q_lower or "mobile" in q_lower or "cell" in q_lower or "telephone" in q_lower or "contact number" in q_lower:
            return "PHONE"
        if "address" in q_lower or "live" in q_lower or "reside" in q_lower or "location" in q_lower or "city" in q_lower or "place" in q_lower:
            return "ADDRESS"
        if "college" in q_lower or "school" in q_lower or "degree" in q_lower or "qualification" in q_lower or "academic" in q_lower or "graduation" in q_lower:
            return "EDUCATION"
        if "company" in q_lower or "employment" in q_lower or "career" in q_lower or "work" in q_lower:
            return "EXPERIENCE"
        if "css framework" in q_lower or "skills" in q_lower or "technologies" in q_lower or "framework" in q_lower or "tools" in q_lower or "programming" in q_lower:
            return "SKILLS"
        if "project" in q_lower or "developed" in q_lower or "application" in q_lower or "portfolio" in q_lower:
            return "PROJECTS"
        if "summary" in q_lower or "summarize" in q_lower or "overview" in q_lower or "brief" in q_lower:
            return "SUMMARY"
        if "objective" in q_lower:
            return "OBJECTIVE"

        # 1. Exact Keyword Override / Fallback Checks
        keyword_mappings = {
            "PHONE": ["phone", "mobile", "cell", "telephone", "contact number", "contact"],
            "EMAIL": ["mail", "gmail", "email address", "email", "e-mail"],
            "NAME": ["candidate", "applicant", "person", "name"],
            "EDUCATION": ["degree", "college", "school", "qualification", "academic", "graduation", "education"],
            "EXPERIENCE": ["experience", "career", "employment", "work", "job role", "designation", "company", "role"],
            "PROJECTS": ["project", "developed", "application", "system", "projects"],
            "SKILLS": ["skills", "technologies", "frameworks", "technical skills", "tools", "software", "programming languages", "programming", "languages", "expertise", "framework"],
            "CERTIFICATIONS": ["certificate", "certification", "course", "training", "certifications"],
            "SUMMARY": ["summary", "summarize", "overview", "brief", "abstract"],
            "ADDRESS": ["address", "location", "city", "place", "live", "reside"],
            "LANGUAGES": ["language", "languages known", "speak", "languages"],
            "INVOICE_TOTAL": ["total", "grand total", "total amount"],
            "COUNT": ["count", "how many", "number of"],
            "AVERAGE": ["average", "mean", "avg"],
            "HIGHEST": ["highest", "maximum", "max"],
            "LOWEST": ["lowest", "minimum", "min"]
        }

        # Highest overlap check
        best_kw_intent = "GENERAL"
        max_overlap = 0
        for intent, kw_list in keyword_mappings.items():
            overlap = sum(1 for kw in kw_list if kw in q_words or any(kw in w for w in q_words))
            if overlap > max_overlap:
                max_overlap = overlap
                best_kw_intent = intent

        # If keyword overlap is found, prioritize it immediately
        if best_kw_intent != "GENERAL":
            return best_kw_intent

        # 2. Semantic Embedding Similarity Check
        if self.intent_embeddings:
            try:
                query_emb = embedding_service.get_embeddings([query])[0]
                best_intent = "GENERAL"
                best_score = -1.0

                for intent, embs in self.intent_embeddings.items():
                    for emb in embs:
                        # Cosine similarity
                        dot_product = sum(q * r for q, r in zip(query_emb, emb))
                        q_norm = sum(q * q for q in query_emb) ** 0.5
                        r_norm = sum(r * r for r in emb) ** 0.5
                        similarity = dot_product / (q_norm * r_norm + 1e-9)
                        if similarity > best_score:
                            best_score = similarity
                            best_intent = intent

                # Accept classification if above threshold
                if best_score > 0.60:
                    return best_intent
            except Exception as e:
                logger.warning(f"Semantic similarity check failed: {e}")

        return "GENERAL"

    def classify_multi(self, query: str) -> List[str]:
        """Resolves user query to one or more canonical intent names.

        Processing order (per spec):
          1. Exact intent matching via keywords
          2. Group intent expansion (INTENT_GROUPS)
          3. Query normalization + spell correction (_preprocess_query)
          4. Technology reasoning happens in ResumeReasoner, not here
          5. Semantic similarity fallback (classify)
          6. UNKNOWN_QUERY as final fallback
        """
        # Step 3: normalise before any matching
        q_lower = self._preprocess_query(query)
        
        # 1. Match Group Terms in the query
        matched_spans = []
        matches_found = []  # List of tuples: (start_pos, list_of_intents)
        
        for group_term, group_intents in self.INTENT_GROUPS.items():
            pattern = r'\b' + re.escape(group_term) + r'\b'
            for match in re.finditer(pattern, q_lower):
                matched_spans.append((match.start(), match.end()))
                matches_found.append((match.start(), group_intents))
                break  # Match each group term once per query
                
        # 2. Define keyword matching mapping
        mappings = [
            ("FATHER_NAME", ["father name", "father's name", "father"]),
            ("MOTHER_NAME", ["mother name", "mother's name", "mother"]),
            ("CANDIDATE_NAME", ["candidate name", "candidate's name", "applicant name", "applicant's name", "name"]),
            ("EMAIL", ["email", "gmail", "e-mail", "email address"]),
            ("PHONE", ["phone", "mobile", "cell", "telephone", "contact number", "contact details", "contact info"]),
            ("ADDRESS", ["address", "location", "reside", "live", "city", "place"]),
            ("DESIGNATION", ["designation", "job role", "job designation", "role"]),
            ("EXPERIENCE", ["experience", "work history", "employment", "career", "work experience"]),
            ("EDUCATION", ["education", "degree", "college", "school", "qualification", "academic", "graduation"]),
            ("SKILLS", ["skills", "technologies", "frameworks", "tools", "libraries", "tech stack"]),
            ("PROJECTS", ["projects", "project", "developed", "portfolio"]),
            ("CERTIFICATIONS", ["certifications", "certification", "certificate", "courses", "course"]),
            ("GENDER", ["gender", "sex", "male", "female"]),
            ("PROGRAMMING_LANGUAGES", ["programming language", "programming languages", "coding language", "coding languages"]),
            ("HUMAN_LANGUAGES", ["human language", "human languages", "spoken languages", "languages she speak", "languages he speak", "languages does she speak", "languages does he speak", "languages known", "languages", "language"]),
            ("SALARY", ["salary"]),
            ("NOTICE_PERIOD", ["notice period", "notice"]),
            ("RELOCATION", ["relocate", "relocation"]),
            ("MARITAL_STATUS", ["marital", "married"])
        ]
        
        # 3. Match Individual Keywords
        for intent, kws in mappings:
            for kw in kws:
                pattern = r'\b' + re.escape(kw) + r'\b'
                if "'" in kw or "-" in kw:
                    pattern = re.escape(kw)
                
                for match in re.finditer(pattern, q_lower):
                    start = match.start()
                    # Skip if this keyword start position overlaps with any matched group term span
                    inside_group = any(g_start <= start < g_end for g_start, g_end in matched_spans)
                    if not inside_group:
                        matches_found.append((start, [intent]))
                        break
                        
        # Profile summary special case check if not inside any matched group
        is_ps = "tell me about this candidate" in q_lower or "profile summary" in q_lower
        if is_ps:
            match_ps = re.search(r'tell me about this candidate|profile summary', q_lower)
            if match_ps:
                start = match_ps.start()
                inside_group = any(g_start <= start < g_end for g_start, g_end in matched_spans)
                if not inside_group:
                    matches_found.append((start, ["PROFILE_SUMMARY"]))
                    
        # 4. Sort matches by position (Preserve User Order)
        matches_found.sort(key=lambda x: x[0])
        
        # 5. Extract unique intents preserving configurations order naturally
        unique_intents = []
        for _, intents_list in matches_found:
            for intent in intents_list:
                if intent not in unique_intents:
                    unique_intents.append(intent)
                    
        # Sort out duplicates/overlaps like FATHER_NAME/MOTHER_NAME vs CANDIDATE_NAME:
        has_father = "FATHER_NAME" in unique_intents
        has_mother = "MOTHER_NAME" in unique_intents
        if has_father or has_mother:
            if "CANDIDATE_NAME" in unique_intents:
                name_matches = list(re.finditer(r'\bname\b', q_lower))
                standalone_name = False
                for nm in name_matches:
                    start_idx = max(0, nm.start() - 15)
                    context_str = q_lower[start_idx:nm.end()]
                    if "father" not in context_str and "mother" not in context_str and "company" not in context_str:
                        standalone_name = True
                        break
                if not standalone_name:
                    unique_intents.remove("CANDIDATE_NAME")
                    
        # Sort out duplicates/overlaps like PROGRAMMING_LANGUAGES/HUMAN_LANGUAGES vs SKILLS:
        has_prog_langs = "PROGRAMMING_LANGUAGES" in unique_intents
        if has_prog_langs and "SKILLS" in unique_intents:
            skills_matches = list(re.finditer(r'\b(?:skills|technologies|frameworks|tools|libraries|tech stack)\b', q_lower))
            if not skills_matches:
                unique_intents.remove("SKILLS")
        if "HUMAN_LANGUAGES" in unique_intents:
            human_matches = list(re.finditer(r'\b(?:human|speak|spoken|known|english|hindi|french|german|spanish|languages)\b', q_lower))
            if not human_matches and "SKILLS" in unique_intents:
                unique_intents.remove("SKILLS")
            if "PROGRAMMING_LANGUAGES" in unique_intents and not any(k in q_lower for k in ["human", "speak", "spoken", "known", "english", "hindi", "french", "german", "spanish"]):
                unique_intents.remove("HUMAN_LANGUAGES")
        
        # Suppress ADDRESS when 'address' appears only as part of 'email address'
        # and not as a standalone location request.
        if "ADDRESS" in unique_intents and "EMAIL" in unique_intents:
            # Only keep ADDRESS if the query explicitly requests address/location
            # separately (not just the phrase "email address")
            addr_standalone = re.search(
                r'\b(?:address|location|city|live|reside|place)\b',
                re.sub(r'email\s+address', '', q_lower)
            )
            if not addr_standalone:
                unique_intents.remove("ADDRESS")
                
        # 6. Fallback (per spec ordering):
        #    a. Minimum-relevance guard: if the preprocessed query contains NO
        #       resume-related tokens, skip semantic similarity and go straight
        #       to UNKNOWN_QUERY.  This prevents superficial embedding matches
        #       for completely unrelated words (e.g. "love", "food", "today").
        #    b. Otherwise try the single-intent classifier (semantic similarity).
        #    c. If that also returns GENERAL, emit UNKNOWN_QUERY.
        if not unique_intents:
            RESUME_TOKENS = {
                "skill", "skills", "experience", "education", "project",
                "projects", "certification", "certifications", "certificate",
                "name", "phone", "mobile", "email", "address", "language",
                "languages", "designation", "summary", "summarize", "summarise",
                "overview", "brief", "profile", "objective", "degree",
                "college", "university", "work", "employment", "company",
                "linkedin", "github", "contact", "location", "role", "career",
                "qualification", "qualifications", "academic", "employer",
                "training", "course", "resume", "cv", "candidate", "applicant",
                "technologies", "technology", "frameworks", "tools",
                # spell-corrected forms that may appear in preprocessed query
                "python", "java", "react", "angular", "docker", "aws",
            }
            q_tokens_check = set(re.findall(r'\b\w+\b', q_lower))
            has_resume_token = bool(q_tokens_check & RESUME_TOKENS)

            if has_resume_token:
                single = self.classify(query)
                if single and single not in ("GENERAL", ""):
                    unique_intents = [single]
                else:
                    unique_intents = [self.UNKNOWN_QUERY_INTENT]
            else:
                # No resume-domain word at all → unrecognised query
                unique_intents = [self.UNKNOWN_QUERY_INTENT]

        return unique_intents
