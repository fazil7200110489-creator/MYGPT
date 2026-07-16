import re
from typing import Dict, List, Optional
from loguru import logger
from backend.app.services.embedding_service import embedding_service

class IntentClassifier:
    """Classifies user queries semantically into canonical intents using embedding similarity."""

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
        if "father" in q_lower:
            return "FATHER_NAME"
        if "mother" in q_lower:
            return "MOTHER_NAME"
        if "candidate" in q_lower and "name" in q_lower:
            return "CANDIDATE_NAME"
        if "applicant" in q_lower and "name" in q_lower:
            return "CANDIDATE_NAME"
        if "name" in q_lower and not any(k in q_lower for k in ["father", "mother", "spouse", "guardian"]):
            # E.g. "what is the name", "whose resume"
            return "CANDIDATE_NAME"
        if "email" in q_lower or "gmail" in q_lower:
            return "EMAIL"
        if "address" in q_lower:
            return "ADDRESS"
        if "birth" in q_lower or "dob" in q_lower or "d.o.b" in q_lower:
            return "DATE_OF_BIRTH"
        if "gender" in q_lower or "sex" in q_lower:
            return "GENDER"
        if "language" in q_lower:
            if any(w in q_lower for w in ["programming", "coding", "software", "development", "markup", "technical", "computer"]):
                return "SKILLS"
            return "LANGUAGES"
        if "objective" in q_lower:
            return "OBJECTIVE"

        # 1. Exact Keyword Override / Fallback Checks
        keyword_mappings = {
            "PHONE": ["phone", "mobile", "telephone", "cell", "contact"],
            "EMAIL": ["email", "gmail", "e-mail", "mail"],
            "SKILLS": ["skills", "expertise", "technologies", "languages"],
            "PROJECTS": ["projects", "applications", "portfolio", "built"],
            "EDUCATION": ["education", "qualification", "degree", "university", "college"],
            "CERTIFICATIONS": ["certificate", "certification", "credentials"],
            "SUMMARY": ["summary", "summarize", "overview", "brief", "abstract"],
            "EXPERIENCE": ["experience", "employment", "career", "work"],
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
