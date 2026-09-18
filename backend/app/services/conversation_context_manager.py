"""Conversation Context Manager for Multi-Turn Chat Orchestration in Company AI.

Maintains stateful dialogue context per session:
- Active department context (e.g. 'I'm from tech department')
- Last executed department, intent, action, topic, entities
- Last generated files and documents for contextual modification/export
- Pending actions / questions (e.g. awaiting error details after user confirms 'yes')
- Follow-up signal resolution across detail expansions, document operations, and arithmetic continuations.

NOTE: Conversation context is for conversational steering only. It NEVER grants or bypasses RBAC.
"""

import os
import re
import time
from typing import Dict, Any, List, Optional, Tuple
from loguru import logger

from backend.app.schemas.department import DepartmentEnum
from backend.app.schemas.company_ai import ConversationState, CompanyAIResult
from backend.app.services.excel.semantic_excel_resolver import semantic_excel_resolver


class ConversationContextManager:
    """Thread-safe conversation state and follow-up resolver for Company AI."""

    def __init__(self):
        self._states: Dict[str, ConversationState] = {}
        self._turn_history: Dict[str, List[Dict[str, Any]]] = {}
        logger.info("ConversationContextManager initialized.")

    def get_state(self, session_id: str) -> ConversationState:
        """Retrieves or creates the conversation state for a session."""
        if session_id not in self._states:
            self._states[session_id] = ConversationState(conversation_id=session_id)
        return self._states[session_id]

    def clear_state(self, session_id: str) -> None:
        """Resets the state and history for a given session."""
        if session_id in self._states:
            del self._states[session_id]
        if session_id in self._turn_history:
            del self._turn_history[session_id]
        logger.info(f"ConversationContextManager: Cleared state for session '{session_id}'")

    def clear_session(self, session_id: str) -> None:
        """Alias for clear_state."""
        self.clear_state(session_id)

    # ------------------------------------------------------------------
    # Explicit Department Context Declaration
    # ------------------------------------------------------------------

    _DEPT_DECLARATION_PATTERNS = [
        (re.compile(r"\b(i'm|i am|we are|im)\s+(from|in|part of|working in)\s+(the\s+)?(tech|it|engineering|developer|devops|technology|software)\b", re.I), DepartmentEnum.TECH),
        (re.compile(r"\b(i'm|i am|we are|im)\s+(from|in|part of|working in)\s+(the\s+)?(hr|human resources?|people ops|talent)\b", re.I), DepartmentEnum.HR),
        (re.compile(r"\b(i'm|i am|we are|im)\s+(from|in|part of|working in)\s+(the\s+)?(finance|accounting|accounts|payroll|billing)\b", re.I), DepartmentEnum.FINANCE),
        (re.compile(r"\b(tech|it|engineering)\s+(department|dept|team)\s*(here|member)?\b", re.I), DepartmentEnum.TECH),
        (re.compile(r"\b(hr|human resources?)\s+(department|dept|team)\s*(here|member)?\b", re.I), DepartmentEnum.HR),
        (re.compile(r"\b(finance|accounting)\s+(department|dept|team)\s*(here|member)?\b", re.I), DepartmentEnum.FINANCE),
    ]

    def detect_department_declaration(self, text: str) -> Optional[DepartmentEnum]:
        """Detects whether user is explicitly declaring their department context (e.g. 'I'm from tech department')."""
        clean = text.strip()
        for pattern, dept in self._DEPT_DECLARATION_PATTERNS:
            if pattern.search(clean):
                logger.info(f"ContextManager: Detected explicit department declaration: '{clean}' -> {dept.value}")
                return dept
        return None

    # ------------------------------------------------------------------
    # Follow-Up and Contextual Signal Detection
    # ------------------------------------------------------------------

    _CONFIRMATION_PATTERN = re.compile(
        r"^(yes|yeah|yep|yup|sure|ok|okay|k|fine|continue|go ahead|proceed|alright|certainly|please do)[.!]?$",
        re.I
    )

    _EXPANSION_PATTERNS = [
        re.compile(r"\b(give me (in )?detail(s)?|more detail(s)?|in detail|explain (that |it |this )?in detail|explain more|tell me more|elaborate|expand on that|break it down)\b", re.I),
        re.compile(r"\b(can (you|u) (give|provide|share) (me )?(more|full|complete) (detail|details|info|information))\b", re.I),
        re.compile(r"\b(make (it|this) (more )?detailed|detailed explanation|go into details)\b", re.I),
    ]

    _SUMMARY_PATTERNS = [
        re.compile(r"\b(give me (a |the )?(overall )?summary( of (this|that|the) (report|file|document|invoice|spreadsheet|excel|pdf))?|summary of (this|that|the) (report|file|document|invoice|spreadsheet|excel|policy|resume|pdf)|summarize (this|that|it|the report|the document|the file|the invoice|the policy|the resume|the pdf)?|give a summary|provide a summary|what is (this|that) (report|document|file|resume|pdf) about|explain (this|that) (report|document|resume|pdf)|what is the purpose of (this|that|the) (document|report|file|manual|resume|policy))\b", re.I),
        re.compile(r"^(summary|summarize|give summary|give overall summary|overall summary|summary of this|summarize this|summarize this document|summarize document|what is this document about|explain this document|what is this about)[.!]?$", re.I),
    ]

    _DOCUMENT_ACTION_PATTERNS = [
        (re.compile(r"\b(make|put|convert|export|give|generate|create|turn)\s+(me\s+)?(it|this|that|the same|same)\s+(in|into|to|as)?\s*(an?\s*)?(excel|xlsx|spreadsheet|csv)\b", re.I), "EXPORT", "xlsx"),
        (re.compile(r"\b(make|put|convert|export|give|generate|create|turn)\s+(me\s+)?(it|this|that|the same|same)\s+(in|into|to|as)?\s*(an?\s*)?(word|docx|doc|document)\b", re.I), "EXPORT", "docx"),
        (re.compile(r"\b(make|create|generate|export)\s+(me\s+)?(an?\s*)?(excel|xlsx|spreadsheet)\s*(document|file|sheet)?\b", re.I), "EXPORT", "xlsx"),
        (re.compile(r"\b(export|download)\s+(it|this|that|the file|the document|the excel|the spreadsheet)\b", re.I), "EXPORT", "xlsx"),
        (re.compile(r"^(export|download|export it|download it|give me that in excel|make it excel|export to excel)[.!]?$", re.I), "EXPORT", "xlsx"),
        (re.compile(r"\b(make (an? )?excel (from|for|of) (this|that|the) invoice|convert (this|that|the) invoice to excel)\b", re.I), "INVOICE_EXCEL", "xlsx"),
        (re.compile(r"\b(make (an? )?excel (from|for|of) (this|that|the) (document|resume|summary|policy)|convert (this|that|the) (document|resume|summary|policy) to excel)\b", re.I), "EXPORT", "xlsx"),
        (re.compile(r"\b(add|insert|include|append)\s+(an?\s*)?([a-z\s]+?)\s*(section|clause|paragraph|part|acknowledg(e)?ment)\b", re.I), "MODIFY", "section"),
        (re.compile(r"\b(change|modify|update|edit)\s+(it|this|that|the document|the policy)\b", re.I), "MODIFY", "general"),
    ]

    _INVOICE_INQUIRY_PATTERNS = [
        (re.compile(r"\b(how much is the total|what is the total|total amount|invoice total|how much total|total cost)\b", re.I), "INVOICE_TOTAL"),
        (re.compile(r"\b(how much (is the )?gst|what is the gst|gst amount|tax amount|how much tax|sales tax)\b", re.I), "INVOICE_TAX"),
        (re.compile(r"\b(who is the vendor|vendor name|invoice date|due date|invoice number|invoice id)\b", re.I), "INVOICE_METADATA"),
        (re.compile(r"\b(vendor|supplier|billed to|issue date|payment terms)\b", re.I), "INVOICE_METADATA"),
    ]

    _COMPARISON_PATTERNS = [
        re.compile(r"\b(compare (this|it) with (the )?previous( invoice| file| document)?|compare (these|the) (two|2|both)( (invoices|files|documents|spreadsheets|excel))?|compare (these|them|both|two)|create a mismatch report|find (mismatches|differences|discrepancies)|what are (the\s+)?mismatches|show (the\s+)?mismatches|mismatches\?|any mismatches)\b", re.I)
    ]

    _EXCEL_OPERATION_PATTERNS = [
        # Split sprint / excel
        (re.compile(r"\b(make\s+(a\s+)?(separate\s+)+sprint(s)?\s+(for\s+)?(the\s+)?|split\s+(this\s+|the\s+)?(sprint|excel|spreadsheet|file|it)?\s*(for|by|into)?\s*|separate\s+sprint(s)?\s+(for\s+)?(the\s+)?|create\s+(a\s+)?(separate\s+)+sprint(s)?\s+(for\s+)?)(.+)", re.I), "EXCEL_SPLIT"),
        (re.compile(r"\b(make\s+(a\s+)?(separate\s+)+sprint|split\s+(this|the\s+sprint|the\s+excel|the\s+spreadsheet|the\s+file|it)|separate\s+sprints?)\b", re.I), "EXCEL_SPLIT"),
        # Filter single owner / tasks
        (re.compile(r"\b(give\s+(me\s+)?only\s+(the\s+)?|only\s+(for\s+)?|make\s+one\s+for\s+(the\s+)?|filter\s+(by|for)\s+(the\s+)?|show\s+(me\s+)?only\s+(the\s+)?)(.+)", re.I), "EXCEL_FILTER"),
        (re.compile(r"\b(give\s+(me\s+)?([a-z]+)'s\s+sprint|make\s+one\s+for\s+([a-z]+)|only\s+([a-z]+)|([a-z]+)'s\s+sprint)\b", re.I), "EXCEL_FILTER"),
        # Summary & reporting
        (re.compile(r"\b(sprint\s+summary|summarize\s+(the\s+|this\s+)?(sprint|excel|sheet|workbook|tasks?)|what('s|\s+is)\s+(in\s+)?(this\s+|the\s+)?(sprint|excel|sheet)|sprint\s+overview)\b", re.I), "EXCEL_SUMMARY"),
        (re.compile(r"\b(sprint\s+report|generate\s+(sprint\s+)?report|excel\s+report)\b", re.I), "EXCEL_REPORT"),
        (re.compile(r"\b(compare\s+(these\s+)?(two|both|sprints?|sheets?)|excel\s+comparison)\b", re.I), "EXCEL_COMPARISON"),
        (re.compile(r"\b(export\s+(this\s+|the\s+)?(sprint|sheet|excel|data)|convert\s+to\s+excel)\b", re.I), "EXCEL_EXPORT"),
    ]

    _CANDIDATE_INQUIRY_PATTERNS = [
        (
            re.compile(
                r"\b(is (she|he|they|the candidate|this candidate) fit( for)?|"
                r"fit for (the|an?|this)?\s*([a-z\s]+)?role|"
                r"suitab(le|ility)|good fit|recommend(ation|ed)? (for|as)|"
                r"strengths (for|of)?\s*(this|the)?\s*([a-z\s]+)?role|candidate fit|role fit|role-fit)\b",
                re.I
            ),
            "CANDIDATE_ROLE_FIT_ANALYSIS"
        ),
        (
            re.compile(
                r"\b(what('s|\s+is)\s+(the\s+)?(work\s+|hr\s+|total\s+)?(experience|experince|background)\s*(of\s+(this\s+|the\s+)?candidate)?|"
                r"how much (work\s+|hr\s+)?(experience|experince) (does\s+)?(she|he|they|the candidate|this candidate)?\s*(have|has)?|"
                r"(her|his|their|the\s+candidate'?s?|this\s+candidate'?s?)\s+(work\s+|hr\s+|total\s+)?(experience|experince)|"
                r"what (hr|work)?\s*(experience|experince) (does\s+)?(she|he|they|the candidate|this candidate)?\s*(have|has)?|"
                r"years of (experience|experince)|how many years (of (experience|experince))?|"
                r"(what|which) companies (did )?(she|he|they|the candidate|this candidate) work for|"
                r"work history|career history|employment history|past roles?|previous companies|past companies|"
                r"recruitment experience|sourcing experience|talent acquisition experience|hiring experience|"
                r"does (she|he|the candidate|this candidate) have (recruitment|sourcing|talent acquisition|hr|hiring) experience|"
                r"(experience|experince)\s*(details?|\?)?)\b",
                re.I
            ),
            "CANDIDATE_EXPERIENCE"
        ),
        (
            re.compile(
                r"\b(what('s|\s+is)\s+(the\s+)?(key\s+|core\s+|technical\s+|hr\s+)?skills\s*(of\s+(this\s+|the\s+)?candidate|\?)?|"
                r"what are (her|his|their|the\s+candidate'?s?|this\s+candidate'?s?)\s+(key\s+|core\s+|technical\s+|hr\s+)?skills|"
                r"what skills (does )?(she|he|they|the candidate|this candidate) (have|possess)|"
                r"(her|his|their|the\s+candidate'?s?|this\s+candidate'?s?)\s+skills|"
                r"key skills|core competencies|technical skills|hr skills|skills\?|"
                r"what about (his|her|their|the candidate'?s?) (certifications?|skills)|"
                r"certifications?\?|what certifications?|"
                r"tools? (she|he|they|the candidate) (knows?|uses?)|software skills|technologies)\b",
                re.I
            ),
            "CANDIDATE_SKILLS"
        ),
        (
            re.compile(
                r"\b(what('s|\s+is)\s+(the\s+)?(educational?\s+(details?|background|qualifications?)|education|academics?|degrees?)\s*(of\s+(this\s+|the\s+)?candidate)?|"
                r"what is (her|his|their|the\s+candidate'?s?|this\s+candidate'?s?)\s+(education|educational details?|qualifications?)|"
                r"(her|his|their|the\s+candidate'?s?|this\s+candidate'?s?)\s+(education|educational details?|academics?|degrees?|qualifications?|college|university)|"
                r"educational background|educational details?|qualifications?|degrees?|what degree|"
                r"(which|what)\s+degree\s+(is\s+)?(she|he|they|the candidate|this candidate)?\s*(completed|has|pursued|done)?|"
                r"passed?\s+out\s+year|year\s+of\s+passing|graduation\s+year|pass\s+out\s+year|which\s+year\s+(did\s+)?(she|he|they|the candidate)\s+(pass\s+out|graduate)|"
                r"what\s+qualification\s+does\s+(she|he|they|that\s+candidate|the\s+candidate|this\s+candidate)\s+have|"
                r"which college|which university|academics?|"
                r"where did (she|he|they|the candidate|this candidate) study)\b",
                re.I
            ),
            "CANDIDATE_EDUCATION"
        ),
        (
            re.compile(
                r"\b(give me (her|his|their|the candidate'?s?|this candidate'?s?)\s+(professional\s+)?summary|"
                r"give (the\s+|a\s+)?summary of (this\s+|the\s+)?(resume|candidate)|"
                r"(her|his|candidate'?s?|this\s+candidate'?s?)\s+(profile|bio|overview|background)|"
                r"tell me about (her|him|this candidate|the candidate|the resume I uploaded earlier)|"
                r"professional summary of (the candidate|this candidate|her|him)|"
                r"tell me more|give me more details?|more details?)\b",
                re.I
            ),
            "CANDIDATE_SUMMARY"
        ),
    ]

    _ARITHMETIC_CONTINUATION_PATTERN = re.compile(
        r"^(?:and\s+)?(add|plus|minus|subtract|deduct)\s+(\$?\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:more|dollars?|to that|from that)?\s*$",
        re.I
    )

    # ------------------------------------------------------------------
    # Context State Access & Manipulation
    # ------------------------------------------------------------------

    def set_active_document(self, session_id: str, doc_dict: Dict[str, Any]) -> ConversationState:
        """Sets the active document in session context and preserves multi-document history."""
        state = self.get_state(session_id)
        new_doc_id = doc_dict.get("id") or doc_dict.get("document_id") or doc_dict.get("doc_id")
        old_doc_id = (state.active_document.get("id") or state.active_document.get("document_id") or state.active_document.get("doc_id")) if state.active_document else None

        if state.active_document and old_doc_id and new_doc_id and old_doc_id != new_doc_id:
            state.previous_document = state.active_document

        doc_dict_normalized = dict(doc_dict)
        doc_dict_normalized["id"] = new_doc_id
        doc_dict_normalized["document_id"] = new_doc_id

        state.active_document = doc_dict_normalized
        state.active_document_id = new_doc_id
        state.active_document_name = doc_dict.get("filename") or doc_dict.get("name")
        state.active_document_type = doc_dict.get("document_type") or "GENERAL_DOCUMENT"

        # Multi-document tracking stack (Part C)
        if not hasattr(state, "conversation_documents") or state.conversation_documents is None:
            state.conversation_documents = []
        if not hasattr(state, "documents") or state.documents is None:
            state.documents = []

        if not any((d.get("document_id") == new_doc_id or d.get("id") == new_doc_id) for d in state.conversation_documents):
            state.conversation_documents.append(doc_dict_normalized)
        if not any((d.get("document_id") == new_doc_id or d.get("id") == new_doc_id) for d in state.documents):
            state.documents.append(doc_dict_normalized)

        if not hasattr(state, "active_document_ids") or state.active_document_ids is None:
            state.active_document_ids = []
        if new_doc_id and new_doc_id not in state.active_document_ids:
            state.active_document_ids.append(new_doc_id)

        dept = doc_dict.get("department")
        if dept and dept != "GENERAL":
            state.department = dept
            state.last_department = dept

        logger.info(
            f"ContextManager: Set active document for session '{session_id}' -> "
            f"name='{state.active_document_name}' id='{state.active_document_id}' type='{state.active_document_type}' "
            f"(Total session docs: {len(state.documents)})"
        )
        return state

    def resolve_document_for_query(self, session_id: str, query: str) -> Optional[Dict[str, Any]]:
        """Resolves target active document from user query references ('this resume', 'the resume', 'this excel', 'the invoice', 'that candidate')."""
        state = self.get_state(session_id)
        raw_docs = getattr(state, "documents", []) or getattr(state, "conversation_documents", []) or []
        if not raw_docs and state.active_document:
            raw_docs = [state.active_document]
        if not raw_docs:
            return None

        query_lower = query.lower()

        # 1. User explicitly references a Resume / Candidate
        if re.search(r"\b(resume|resumes|candidate|candidates|cv|applicant|degree|graduation|qualification|passed\s+out)\b", query_lower, re.I):
            resume_docs = [
                d for d in raw_docs 
                if str(d.get("document_type", "")).upper() == "RESUME"
                or any(str(d.get("filename") or "").lower().endswith(ext) for ext in [".pdf", ".docx", ".doc", ".txt"])
                or "resume" in str(d.get("filename") or "").lower()
            ]
            if resume_docs:
                target_doc = resume_docs[-1]
                self.set_active_document(session_id, target_doc)
                logger.info(f"ContextManager: Resolved document from reference '{query}' -> RESUME '{target_doc.get('filename')}'")
                return target_doc

        # 2. User explicitly references an Excel / Spreadsheet / Sprint / History
        if re.search(r"\b(excel|spreadsheet|sheet|sprint|topup|transactions?|workbook)\b", query_lower, re.I):
            excel_docs = [
                d for d in raw_docs 
                if str(d.get("document_type", "")).upper() in ("EXCEL", "EXCEL_WORKBOOK", "SPREADSHEET")
                or any(str(d.get("filename") or "").lower().endswith(ext) for ext in [".xlsx", ".xls", ".csv"])
            ]
            if excel_docs:
                target_doc = excel_docs[-1]
                self.set_active_document(session_id, target_doc)
                logger.info(f"ContextManager: Resolved document from reference '{query}' -> EXCEL '{target_doc.get('filename')}'")
                return target_doc

        # 3. User explicitly references an Invoice
        if re.search(r"\b(invoice|invoices|bill|vendor)\b", query_lower, re.I):
            invoice_docs = [
                d for d in raw_docs 
                if str(d.get("document_type", "")).upper() == "INVOICE"
                or "invoice" in str(d.get("filename") or "").lower()
            ]
            if invoice_docs:
                target_doc = invoice_docs[-1]
                self.set_active_document(session_id, target_doc)
                logger.info(f"ContextManager: Resolved document from reference '{query}' -> INVOICE '{target_doc.get('filename')}'")
                return target_doc

        return state.active_document

    def resolve_comparison_documents(self, session_id: str, text: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Resolves two distinct documents from session history for comparison or multi-document summary."""
        state = self.get_state(session_id)
        raw_docs = getattr(state, "documents", []) or getattr(state, "conversation_documents", []) or []
        if not raw_docs:
            return (None, None)

        def get_did(d: Optional[Dict[str, Any]]) -> str:
            if not d:
                return ""
            return str(d.get("document_id") or d.get("id") or d.get("doc_id") or "")

        # Deduplicate docs by stable document_id
        docs: List[Dict[str, Any]] = []
        seen_ids = set()
        for d in raw_docs:
            did = get_did(d)
            if did and did not in seen_ids:
                seen_ids.add(did)
                docs.append(d)

        if not docs:
            return (None, None)

        text_lower = text.lower()

        # 1. Match by specific keywords / filenames in query
        matched_docs: List[Dict[str, Any]] = []
        for d in docs:
            fname = str(d.get("filename") or d.get("name") or "").lower()
            base_tokens = [tok for tok in re.split(r"[\s\-_\.]+", fname) if len(tok) >= 3 and tok not in ("xlsx", "xls", "csv", "pdf", "docx", "export", "final", "from", "resume", "ops")]
            if any(tok in text_lower for tok in base_tokens) or (fname in text_lower):
                if get_did(d) not in [get_did(m) for m in matched_docs]:
                    matched_docs.append(d)

        if len(matched_docs) >= 2 and get_did(matched_docs[0]) != get_did(matched_docs[1]):
            return (matched_docs[0], matched_docs[1])

        # 2. Check if user is asking about resumes/candidates
        if any(k in text_lower for k in ["resume", "resumes", "candidate", "candidates", "hr role", "cv", "applicant"]):
            resume_docs = [d for d in docs if d.get("document_type") == "RESUME" or any(str(d.get("filename") or "").lower().endswith(ext) for ext in [".pdf", ".docx", ".doc", ".txt"])]
            if len(resume_docs) >= 2 and get_did(resume_docs[0]) != get_did(resume_docs[1]):
                return (resume_docs[0], resume_docs[1])

        # 3. Check Excel files
        excel_docs = [d for d in docs if any(str(d.get("filename") or "").lower().endswith(ext) for ext in [".xlsx", ".xls", ".csv"])]
        if len(excel_docs) >= 2 and get_did(excel_docs[0]) != get_did(excel_docs[1]):
            return (excel_docs[0], excel_docs[1])

        # 4. If 1 matched from keyword and 1 active
        if len(matched_docs) == 1 and state.active_document and get_did(state.active_document) != get_did(matched_docs[0]):
            return (state.active_document, matched_docs[0])

        # 5. Fallback to first two distinct documents
        if len(docs) >= 2 and get_did(docs[0]) != get_did(docs[1]):
            return (docs[0], docs[1])

        return (None, None)

    def _normalize_text_for_excel(self, text: str) -> str:
        """Normalizes typos and colloquial terms for Excel processing."""
        t = text
        # Typos & phonetic spelling variations
        t = re.sub(r"\b(exel|excl|excle|exle|hseet|xlsx?|spreadsheet|spredsheet|spreedsheet)\b", "excel", t, flags=re.I)
        t = re.sub(r"\b(colunms?|colums?|culumns?|culoumns?)\b", "columns", t, flags=re.I)
        t = re.sub(r"\b(maount|ammount|amont|amout)\b", "amount", t, flags=re.I)
        t = re.sub(r"\b(foudn|fount|fund)\b", "find", t, flags=re.I)
        t = re.sub(r"\b(gie|gve|guve)\b", "give", t, flags=re.I)
        t = re.sub(r"\b(seprate|seperate|seperte|seperat)\b", "separate", t, flags=re.I)
        t = re.sub(r"\b(asnd|adn|adnd|annd)\b", "and", t, flags=re.I)
        t = re.sub(r"\b(detals|detalis|detailes)\b", "details", t, flags=re.I)
        t = re.sub(r"\b(suamary|sumarry|sumary|sumeray|summarie|sumarrys)\b", "summary", t, flags=re.I)
        t = re.sub(r"\b(docuemt|documnt|documnet|documant|documet|documnts)\b", "document", t, flags=re.I)
        t = re.sub(r"\b(hisitory|histroy|hsitory|histry)\b", "history", t, flags=re.I)
        t = re.sub(r"\b(experince|experiance|experence|exprerience)\b", "experience", t, flags=re.I)
        t = re.sub(r"\b(transction|trasaction|tranaction|transacton|transacttion|transatction)\b", "transaction", t, flags=re.I)
        t = re.sub(r"\b(transctions|trasactions|tranactions|transactons|transacttions)\b", "transactions", t, flags=re.I)
        t = re.sub(r"\b(hoghest|hghest|heighest|heighest)\b", "highest", t, flags=re.I)
        t = re.sub(r"\b(largst|largset)\b", "largest", t, flags=re.I)
        t = re.sub(r"\b(biggst|bigest)\b", "biggest", t, flags=re.I)
        t = re.sub(r"\b(moile|mobil|moble|mbl)\b", "mobile", t, flags=re.I)
        t = re.sub(r"\b(phn|phne)\b", "phone", t, flags=re.I)
        t = re.sub(r"\bcan\s+u\s+giveme\b", "can you give me", t, flags=re.I)
        t = re.sub(r"\bgiveme\b", "give me", t, flags=re.I)
        t = re.sub(r"\bu\b", "you", t, flags=re.I)
        return t

    def _extract_target_owners(self, text: str, known_owners: Optional[List[str]] = None) -> List[str]:
        """Extracts genuine developer / sprint owner names while preventing false positives on general action phrases."""
        clean_text = self._normalize_text_for_excel(text)

        # 1. Match against known owners from workbook inspection if available
        if known_owners:
            matched = []
            for o in known_owners:
                if str(o).strip() and re.search(rf"\b{re.escape(str(o).strip())}\b", clean_text, re.I):
                    matched.append(str(o).strip().title())
            if matched:
                return list(dict.fromkeys(matched))

        # Do NOT extract owners for non-sprint queries (columns, comparisons, summaries, counts, exports, financial metrics)
        if re.search(r"\b(column|columns|heading|headings|header|headers|rid|trn|crn|amount|total|average|count|highest|biggest|largest|lowest|smallest|min|max|summary|report|compare|mismatch|ebo|topup|upi|qr|bqr|history|records|export|document|doc|all|data|transactions|transaction|full|sheet|excel)\b", clean_text, re.I):
            return []

        stop_words = {
            "sprint", "sheet", "excel", "file", "files", "document", "tasks", "task",
            "the", "me", "a", "an", "one", "this", "that", "it", "them", "these", "those",
            "separate", "sprints", "work", "items", "and", "with", "for", "of", "in", "by", "details",
            "summary", "short", "report", "overview", "total", "amount", "average", "count",
            "highest", "biggest", "largest", "lowest", "smallest", "min", "max",
            "qr", "upi", "bqr", "status", "columns", "column", "headings", "heading", "headers", "header",
            "rid", "crn", "trn", "ebo", "topup", "mismatch", "mismatches",
            "history", "records", "data", "full", "complete", "entire", "you", "give", "make", "create", "all"
        }

        # 2. Explicit names after "for":
        m_for = re.findall(r"\b(?:for|and|&|,)\s+([A-Za-z0-9]+)\b", clean_text, re.I)
        valid_fors = [w.strip().title() for w in m_for if w.strip().lower() not in stop_words and len(w.strip()) > 1]
        if valid_fors:
            return list(dict.fromkeys(valid_fors))

        # 3. Match explicit list of names connected by 'and' or '&'
        m_pairs = re.findall(r"\b([A-Za-z0-9]+)\s+(?:and|&|\+)\s+([A-Za-z0-9]+)\b", clean_text, re.I)
        for p1, p2 in m_pairs:
            owners = [p.strip().title() for p in (p1, p2) if p.strip().lower() not in stop_words and len(p.strip()) > 1]
            if owners:
                return list(dict.fromkeys(owners))

        return []

    def _detect_excel_operation(self, text: str, known_owners: Optional[List[str]] = None) -> Tuple[Optional[str], List[str], Dict[str, Any]]:
        """Detects Excel operation intent and extracts target owners, columns, and filter specifications from normalized text."""
        norm = self._normalize_text_for_excel(text)
        target_owners = self._extract_target_owners(norm, known_owners)
        meta: Dict[str, Any] = {}

        # 0. Contextual Result Export ("give me as excel", "can u give me as exel", "give me as exel sheet", "excel sheet", "export this result", "download this", "export this")
        if re.search(
            r"^(?:(?:can\s+(?:you|u)\s+)?(?:please\s+)?(?:give|put|convert|make|show)\s+(?:me\s+)?(?:(?:it|this|that|those|the\s+result|the\s+previous\s+result)\s+)?(?:as|in|into|to)\s+(?:an?\s+)?(?:excel|sheet|spreadsheet)(?:\s+(?:sheet|file|document|doc|report|workbook))?|"
            r"(?:can\s+(?:you|u)\s+)?(?:please\s+)?give\s+(?:me\s+)?(?:this|that|those|it)\s+(?:as|in|into|to)\s+(?:an?\s+)?(?:excel|sheet|spreadsheet)(?:\s+(?:sheet|file|document|doc|report|workbook))?|"
            r"(?:as|in|into|to)\s+(?:an?\s+)?(?:excel|sheet|spreadsheet)(?:\s+(?:sheet|file|document|doc|report|workbook))?|"
            r"(?:can\s+(?:you|u)\s+)?(?:please\s+)?export\s+(?:this|that|it|these|those|the\s+result|the\s+previous\s+result)?(?:\s+as\s+(?:excel|sheet|spreadsheet)(?:\s+(?:sheet|file|document|doc|report|workbook))?)?|"
            r"(?:can\s+(?:you|u)\s+)?(?:please\s+)?download\s+(?:this|that|it|the\s+result)?(?:\s+as\s+(?:excel|sheet|spreadsheet)(?:\s+(?:sheet|file|document|doc|report|workbook))?)?|"
            r"make\s+it\s+(?:excel|sheet|spreadsheet)(?:\s+(?:sheet|file|document|doc|report|workbook))?|"
            r"excel\s+(?:sheet|file|document|doc|report|workbook)|"
            r"excel)[.!]?$",
            norm,
            re.I
        ):
            return ("EXCEL_EXPORT_RESULT", [], meta)

        # 0a. Full Workbook Export ("give me the full topup history as excel", "export the full topup history", "give me this entire excel as another excel", "export all records", "give me the complete transaction history as excel", "give me the full data as excel", "give me all transactions as excel", "give me the full sheet as excel", "export full excel")
        if re.search(
            r"\b(full\s+(?:topup\s+)?history\s+as\s+excel|"
            r"export\s+(?:the\s+)?(?:full|complete|entire)\s+(?:topup\s+)?history|"
            r"export\s+all\s+(?:records|rows|data|transactions)|"
            r"(?:complete|entire|full)\s+(?:transaction\s+)?(?:history|data|records|workbook|sheet)\s+as\s+excel|"
            r"give\s+(?:me\s+)?(?:the\s+)?(?:full|complete|entire)\s+(?:topup\s+history|transaction\s+history|data|sheet|records|workbook)\s+(?:as|in|to)\s+(?:an?\s+)?excel|"
            r"give\s+(?:me\s+)?all\s+(?:the\s+)?(?:transactions|records|data|rows)\s+(?:as|in|to)\s+(?:an?\s+)?excel|"
            r"create\s+an?\s+excel\s+containing\s+all\s+(?:this\s+)?data|"
            r"give\s+(?:me\s+)?(?:this\s+)?entire\s+excel\s+as\s+(?:another\s+)?excel|"
            r"export\s+(?:the\s+)?complete\s+workbook|full\s+export\s+as\s+excel|export\s+full\s+excel|"
            r"export\s+(?:the\s+)?full\s+(?:topup\s+)?data|"
            r"give\s+(?:me\s+)?(?:the\s+)?full\s+topup\s+history\s+as\s+excel|"
            r"give\s+(?:me\s+)?(?:the\s+)?full\s+topup\s+history)\b",
            norm,
            re.I
        ):
            return ("EXCEL_FULL_EXPORT", [], meta)

        # 0b. Column / Headings Listing ("give me the headings of the excel", "give me the headings", "what are the headings", "what are the columns", "show me the columns", "list the columns", "what columns are there", "tell me the Excel column names", "column names of this file", "list every field")
        if re.search(
            r"\b(names?\s+of\s+(?:the\s+)?(?:colunms?|columns?|colums?|headings?|hedings?|headers?|fields?|feilds?)|"
            r"(?:colunms?|columns?|colums?|headings?|hedings?|headers?|fields?|feilds?)\s+names?|"
            r"list\s+(?:the\s+|all\s+|every\s+)?(?:colunms?|columns?|colums?|headings?|hedings?|headers?|fields?|feilds?)|"
            r"show\s+(?:me\s+)?(?:the\s+|all\s+|every\s+)?(?:colunms?|columns?|colums?|headings?|hedings?|headers?|fields?|feilds?)|"
            r"what\s+are\s+(?:the\s+)?(?:colunms?|columns?|colums?|headings?|hedings?|headers?|fields?|feilds?)|"
            r"(?:colunms?|columns?|colums?|headings?|hedings?|headers?|fields?|feilds?)\s+list|"
            r"give\s+(?:me\s+)?(?:the\s+)?(?:all\s+)?(?:headings|hedings|headers|columns?\s+names?|colunms?\s+names?|columns?\s+list|fields?\s+list)(?:\s+of\s+(?:the\s+)?(?:excel|file|doc|document|workbook|sheet))?|"
            r"give\s+(?:me\s+)?(?:the\s+)?(?:columns?|colunms?|fields?|feilds?)(?:\s+of\s+(?:the\s+)?(?:excel|file|doc|document|workbook|sheet))?$|"
            r"what\s+(?:colunms?|columns?|colums?|headings?|hedings?|headers?|fields?|feilds?)\s+are\s+there|"
            r"tell\s+me\s+(?:the\s+)?(?:excel\s+)?(?:column|colunm|heading|header|field)\s+names?|"
            r"(?:column|colunm|field)\s+names\s+of\s+this\s+file)\b",
            norm,
            re.I
        ):
            return ("EXCEL_COLUMN_LIST", [], meta)

        # 0c. Strict Column Extraction / Export ("give me the rid as the excel sheet", "give me the transaction id column as excel", "give me those transaction ids as excel", "export rid column")
        m_col_exp = re.search(
            r"\b(?:give\s+me\s+|extract\s+|export\s+)(?:the\s+|those\s+|all\s+)?([a-zA-Z0-9_\s]+?)\s+(?:as\s+(?:the\s+|an?\s+)?(?:excel|exel|exle|sheet|hseet|file|xlsx|csv)|to\s+excel)\b|"
            r"\b(?:export\s+|extract\s+)(?:the\s+|those\s+|all\s+)?([a-zA-Z0-9_\s]+?)\s+(?:column|field)\b",
            norm,
            re.I
        )
        if m_col_exp:
            cand_col = (m_col_exp.group(1) or m_col_exp.group(2) or "").strip()
            excluded_phrases = {
                "summary", "report", "overview", "it", "this", "that", "these", "those", "them",
                "complete data", "entire excel", "complete workbook", "full sheet", "data", "records",
                "transactions", "all transactions", "topup", "document", "file", "headings", "columns",
                "upi", "qr", "bqr", "upi transaction", "qr transaction", "bqr transaction",
                "upi transactions", "qr transactions", "bqr transactions",
                "upi mode", "qr mode", "bqr mode", "upi payment", "qr payment", "upi payments", "qr payments",
                "transaction mode", "payment mode"
            }
            cand_lower = cand_col.lower()
            is_mode_phrase = any(cand_lower == k or cand_lower.startswith(f"{k} ") or cand_lower.endswith(f" {k}") for k in ["upi", "qr", "bqr"])
            if cand_lower and cand_lower not in excluded_phrases and not is_mode_phrase:
                meta["target_column"] = cand_col
                meta["column"] = cand_col
                return ("EXCEL_COLUMN_EXPORT", [], meta)

        # 0d. Two-File Comparison & Mismatches ("compare the ebo topup and upi qr excel and find the mismatch details")
        if re.search(r"\b(compare|reconcile|mismatch(es)?|discrepanc(y|ies)|diff)\b", norm, re.I):
            if re.search(r"\b(mismatch(es)?|discrepanc(y|ies))\b", norm, re.I) and not re.search(r"\b(compare|reconcile|between|vs)\b", norm, re.I):
                if re.search(r"\b(excel|sheet|file|export|download)\b", norm, re.I):
                    meta["follow_up_action"] = "EXPORT_MISMATCHES"
                elif re.search(r"\b(how\s+many|count)\b", norm, re.I):
                    meta["follow_up_action"] = "COUNT_MISMATCHES"
                else:
                    meta["follow_up_action"] = "SHOW_MISMATCHES"
            return ("EXCEL_COMPARE", [], meta)

        # 1a. Highest / Maximum / Biggest Transaction / Amount (EXCEL_MAX):
        if re.search(
            r"\b(highest\s+(?:transaction|amount|value|topup|payment)|"
            r"biggest\s+(?:transaction|amount|value|topup|payment)|"
            r"largest\s+(?:transaction|amount|value|topup|payment)|"
            r"maximum\s+(?:transaction|amount|value|topup|payment)|"
            r"which\s+(?:is\s+)?(?:the\s+)?(?:highest|biggest|largest|maximum)\s+(?:transaction|amount|value)|"
            r"what\s+(?:is\s+)?(?:the\s+)?(?:highest|biggest|largest|maximum)\s+(?:transaction|amount|value)|"
            r"(?:can\s+(?:you|u)\s+)?give\s+(?:me\s+)?(?:the\s+)?(?:highest|biggest|largest|maximum)\s+(?:transaction|amount|value)|"
            r"max\s+(?:amount|transaction|value))\b",
            norm,
            re.I
        ):
            meta["target_column"] = "Amount"
            return ("EXCEL_MAX", target_owners, meta)

        # 1b. Lowest / Minimum / Smallest Transaction / Amount (EXCEL_MIN):
        if re.search(
            r"\b(lowest\s+(?:transaction|amount|value|topup|payment)|"
            r"smallest\s+(?:transaction|amount|value|topup|payment)|"
            r"minimum\s+(?:transaction|amount|value|topup|payment)|"
            r"which\s+(?:is\s+)?(?:the\s+)?(?:lowest|smallest|minimum)\s+(?:transaction|amount|value)|"
            r"what\s+(?:is\s+)?(?:the\s+)?(?:lowest|smallest|minimum)\s+(?:transaction|amount|value)|"
            r"(?:can\s+(?:you|u)\s+)?give\s+(?:me\s+)?(?:the\s+)?(?:lowest|smallest|minimum)\s+(?:transaction|amount|value)|"
            r"min\s+(?:amount|transaction|value))\b",
            norm,
            re.I
        ):
            meta["target_column"] = "Amount"
            return ("EXCEL_MIN", target_owners, meta)

        # 1c. Total / Sum / Financial Aggregation:
        is_total = bool(re.search(
            r"\b(what('s|\s+is)\s+(the\s+)?total(\s+amount)?|"
            r"total\s+amount|sum\s+amount|total\s+settled\s+amount|settled\s+amount|"
            r"how\s+much\s+money|how\s+much\s+is\s+the\s+total|sum\s+the\s+amount|"
            r"what\s+is\s+the\s+total|what('s|\s+is)\s+the\s+sum|calculate\s+total|give\s+me\s+the\s+total|"
            r"grand\s+total|amount\s+total|calculate\s+(?:the\s+)?total\s+amount)\b",
            norm,
            re.I
        ))
        if is_total:
            if re.search(r"\b(settled(\s+amount)?)\b", norm, re.I):
                meta["target_column"] = "Settled_Amount"
            elif re.search(r"\b(total\s+amount)\b", norm, re.I):
                meta["target_column"] = "Total Amount"
            elif re.search(r"\b(commission(\s+amount)?)\b", norm, re.I):
                meta["target_column"] = "Commission Amount"
            elif re.search(r"\b(gst(\s+amount)?)\b", norm, re.I):
                meta["target_column"] = "GST Amount"
            elif re.search(r"\b(amount)\b", norm, re.I):
                meta["target_column"] = "Amount"
            return ("EXCEL_TOTAL", target_owners, meta)

        # 2. Average / Mean:
        if re.search(r"\b(average|avg|mean)\b", norm, re.I):
            if re.search(r"\b(amount|transaction|settled)\b", norm, re.I):
                meta["target_column"] = "Amount"
            return ("EXCEL_AVERAGE", target_owners, meta)

        # 3. Count / Number of records / Transaction IDs:
        is_count = bool(re.search(
            r"\b(how\s+many\s+(?:transactions?|transaction(?:\s+id)?s?|records?|rows?|items?|unique\s+ids?|ids?|rids?|topups?)|"
            r"(?:transactions?|transaction(?:\s+id)?s?|records?|rows?|items?|ids?|topups?)\s+count|"
            r"count\s+(?:of\s+)?(?:transactions?|transaction(?:\s+id)?s?|records?|rows?|ids?|rids?|topups?)|"
            r"total\s+(?:number\s+of\s+)?(?:transactions?|transaction(?:\s+id)?s?|records?|rows?|ids?|rids?|count|topups?)|"
            r"number\s+of\s+(?:transactions?|transaction(?:\s+id)?s?|records?|rows?|ids?|rids?|topups?)|"
            r"tell\s+(?:me\s+)?(?:the\s+)?(?:transaction|record|row)\s+count|"
            r"(?:can\s+(?:you|u)\s+)?tell\s+(?:me\s+)?how\s+many\s+(?:transactions?|transaction(?:\s+id)?s?|records?|rows?|items?|ids?|rids?|topups?)|"
            r"how\s+many\s+transaction\s+id\s+are\s+there|"
            r"how\s+many\s+transaction\s+ids\s+are\s+there|"
            r"how\s+many\s+transaction\s+ids?|"
            r"count\s+transaction\s+ids?|"
            r"total\s+transaction\s+ids?|"
            r"number\s+of\s+transaction\s+ids?|"
            r"tell\s+me\s+the\s+transaction\s+count|"
            r"total\s+number\s+of\s+transactions)\b",
            norm,
            re.I
        ))
        # 3. Mode / Threshold Filter queries (e.g. "give me only the upi mode transaction count", "give me only the qr mode transaction", "show me transactions above 10000"):
        is_count_mode = bool(re.search(r"\b(count|how\s+many|number\s+of|total\s+number)\b", norm, re.I))
        if re.search(r"\b(upi|upi\s+mode)\b", norm, re.I) and not re.search(r"\b(what\s+are\s+the\s+modes|list\s+modes|bank\s+names?|what\s+banks?)\b", norm, re.I):
            meta["filter"] = {"mode": "UPI"}
            if is_count_mode or is_count:
                meta["target_column"] = "Transaction ID"
                return ("EXCEL_COUNT", target_owners, meta)
            return ("EXCEL_FILTER", target_owners, meta)
        if re.search(r"\b(qr|qr\s+mode)\b", norm, re.I) and not re.search(r"\b(what\s+are\s+the\s+modes|list\s+modes|bank\s+names?|what\s+banks?)\b", norm, re.I):
            meta["filter"] = {"mode": "QR"}
            if is_count_mode or is_count:
                meta["target_column"] = "Transaction ID"
                return ("EXCEL_COUNT", target_owners, meta)
            return ("EXCEL_FILTER", target_owners, meta)
        if re.search(r"\b(bqr|bqr\s+mode)\b", norm, re.I):
            meta["filter"] = {"mode": "BQR"}
            if is_count_mode or is_count:
                meta["target_column"] = "Transaction ID"
                return ("EXCEL_COUNT", target_owners, meta)
            return ("EXCEL_FILTER", target_owners, meta)

        m_above = re.search(r"\b(?:above|greater\s+than|over|>)\s*(\d+(?:,\d{3})*(?:\.\d+)?)\b", norm, re.I)
        if m_above:
            val_str = m_above.group(1).replace(",", "")
            meta["filter"] = {"min_amount": float(val_str)}
            return ("EXCEL_FILTER", target_owners, meta)

        # 4. Generic Count / Number of records / Transaction IDs:
        if is_count:
            if re.search(r"\b(transaction\s+id|transaction_id|txn\s+id|rid|unique\s+id|id)\b", norm, re.I):
                meta["target_column"] = "Transaction ID"
            return ("EXCEL_COUNT", target_owners, meta)

        # 5. Excel Split / Multi-file Export (strictly for sprint workbooks / multiple developer names):
        is_split_intent = (
            len(target_owners) >= 2
            or bool(re.search(r"\b(separate|split|individual|respective|each|both)\s+(?:sprint|tasks|sheet|developer|owner)", norm, re.I))
            or bool(re.search(r"\b(create|make|generate|give|export)\s+(?:the\s+|a\s+|an\s+)?(?:separate\s+)*(?:excel|file|sprint|sheet)s?\s+(?:for|of|with)\s+[A-Za-z0-9]+\s+and\s+[A-Za-z0-9]+", norm, re.I))
        )

        if is_split_intent and target_owners:
            return ("EXCEL_SPLIT", target_owners, meta)

        # 6. Excel Single Filter by Owner:
        if len(target_owners) == 1:
            return ("EXCEL_FILTER", target_owners, meta)

        # 7. Summary / Inspection (with typo tolerance):
        if re.search(r"\b(summary|summarize|overview|breakdown|what('s|\s+is)\s+in|describe|short\s+summary|full\s+summary|summary\s+of\s+(?:the\s+)?(?:doc|document|excel|file)|give\s+me\s+(?:the\s+)?details)\b", norm, re.I):
            return ("EXCEL_SUMMARY", target_owners, meta)

        # 8. Excel Report:
        if re.search(r"\b(report|status|audit|generate\s+report)\b", norm, re.I):
            return ("EXCEL_REPORT", target_owners, meta)

        # 9. Excel Export:
        if re.search(r"\b(export|download|convert)\b", norm, re.I):
            return ("EXCEL_EXPORT", target_owners, meta)

        # 10. General document action verbs on active Excel document:
        if re.search(r"\b(create|make|generate|extract|give|get|show)\b", norm, re.I):
            if len(target_owners) >= 2:
                return ("EXCEL_SPLIT", target_owners, meta)
            elif len(target_owners) == 1:
                return ("EXCEL_FILTER", target_owners, meta)
            return ("EXCEL_SUMMARY", target_owners, meta)

        return (None, target_owners, meta)

    def resolve_follow_up_signals(self, text: str, state: ConversationState) -> Dict[str, Any]:
        """Analyzes incoming text in light of current ConversationState to identify follow-up actions."""
        text_clean = text.strip()
        signals: Dict[str, Any] = {
            "is_follow_up": False,
            "signal_type": None,
            "target_action": None,
            "inherited_department": state.department or state.last_department or DepartmentEnum.GENERAL.value,
            "inherited_topic": state.last_topic,
            "referenced_document": state.active_document_name or state.last_generated_file,
            "referenced_doc_id": state.active_document_id,
            "entities": {}
        }

        # 1. Confirmation continuation ("yes", "sure", "ok")
        if self._CONFIRMATION_PATTERN.match(text_clean):
            signals["is_follow_up"] = True
            signals["signal_type"] = "confirmation"
            signals["target_action"] = "CONFIRM"
            signals["pending_action"] = state.pending_action
            return signals

        # 1b. Contextual inquiry: "what happened", "why did it fail", "what went wrong"
        if re.search(r"\b(what\s+happened|why\s+did\s+it\s+fail|what\s+went\s+wrong|what\s+happened\s+with\s+(?:my\s+)?(?:file|doc|document|excel)|tell\s+me\s+what\s+happened)\b", text_clean, re.I):
            signals["is_follow_up"] = True
            signals["signal_type"] = "contextual_explanation"
            signals["target_action"] = "EXPLAIN_STATUS"
            signals["inherited_department"] = state.department or state.last_department or DepartmentEnum.GENERAL.value
            signals["entities"]["active_doc"] = state.active_document_name or "uploaded document"
            signals["entities"]["doc_id"] = state.active_document_id
            signals["entities"]["filename"] = state.active_document_name
            return signals

        # 2. Candidate / Resume Comparison ("compare this 2 resumes", "who is best for the HR position?", "why?", "give me more details", "give me the comparison in Excel")
        is_resume_comp = bool(re.search(
            r"\b(compare\s+(?:this|these|the|both|\d+)?\s*(?:two|2)?\s*resumes?|"
            r"compare\s+(?:the\s+)?candidates?|"
            r"(?:who|which)\s+(?:candidate|resume|person)?\s*(?:is|has)?\s*(?:the\s+)?(?:best|better|most\s+suitable|highest\s+score|stronger|winner)|"
            r"candidate\s+comparison|resume\s+comparison|"
            r"compare\s+(?:the\s+)?two\s+candidates|"
            r"evaluate\s+both\s+resumes|"
            r"who\s+(?:is\s+best|matches|has\s+more\s+relevant\s+experience|would\s+be\s+best|should\s+be\s+hired|fits)\s+(?:for\s+)?(?:the\s+)?([a-z\s]+)?\s*(?:role|position|job)?|"
            r"compare\s+.*\s+for\s+(?:the\s+)?([a-z\s]+)?\s*role)\b",
            text_clean, re.I
        ))
        is_comparison_follow_up = (
            state.last_intent in ("candidate_comparison", "resume_comparison", "hr_candidate_comparison")
            or state.last_operation in ("RESUME_COMPARISON", "candidate_comparison")
            or getattr(state, "last_result_type", None) == "RESUME_COMPARISON"
            or state.last_comparison_result is not None
        ) and any(
            re.search(rf"\b{w}\b", text_clean, re.I)
            for w in [
                "detail", "details", "more", "experience", "skills", "skill", "education",
                "excel", "report", "sheet", "pdf", "export", "download",
                "first", "second", "winner", "best", "better", "compare", "comparison",
                "why", "how", "reason", "suit", "suitable", "fit", "match", "matches",
                "role", "position", "who", "which", "recommend", "recommendation"
            ]
        )

        if is_resume_comp or is_comparison_follow_up:
            signals["is_follow_up"] = True
            signals["signal_type"] = "candidate_comparison"
            signals["target_action"] = "CANDIDATE_COMPARISON"
            signals["inherited_department"] = DepartmentEnum.HR.value
            signals["entities"]["action"] = "CANDIDATE_COMPARISON"
            signals["entities"]["intent"] = "candidate_comparison"
            signals["entities"]["department"] = DepartmentEnum.HR.value
            signals["entities"]["target_role"] = getattr(state, "target_role", None) or "HR Role"
            signals["entities"]["raw_query"] = text_clean
            if re.search(r"\b(in\s+excel|as\s+excel|to\s+excel|excel\s+sheet|excel\s+report|download\s+as\s+excel|export\s+to\s+excel|as\s+spreadsheet)\b", text_clean, re.I):
                signals["entities"]["export_format"] = "EXCEL"

            doc_a, doc_b = self.resolve_comparison_documents(state.conversation_id, text_clean)
            if doc_a and doc_b:
                signals["entities"]["doc_id_a"] = doc_a.get("document_id") or doc_a.get("id")
                signals["entities"]["filename_a"] = doc_a.get("filename")
                signals["entities"]["doc_id_b"] = doc_b.get("document_id") or doc_b.get("id")
                signals["entities"]["filename_b"] = doc_b.get("filename")
                signals["entities"]["selected_document_ids"] = [signals["entities"]["doc_id_a"], signals["entities"]["doc_id_b"]]
                state.selected_document_ids = signals["entities"]["selected_document_ids"]
            elif state.selected_document_ids and len(state.selected_document_ids) >= 2:
                signals["entities"]["doc_id_a"] = state.selected_document_ids[0]
                signals["entities"]["doc_id_b"] = state.selected_document_ids[1]

            logger.info(f"ContextManager: Resolved resume comparison '{text_clean}' -> CANDIDATE_COMPARISON (doc_a={signals['entities'].get('filename_a')}, doc_b={signals['entities'].get('filename_b')})")
            return signals

        # 3. Candidate / Resume Single-Document Follow-up Inquiry ("is she fit for the hr role", "what is his experience", "what is the educational details of this candidate")
        is_resume_active = (
            str(state.active_document_type).upper() == "RESUME"
            or (state.active_document and any(k in str(state.active_document.get("filename", "")).lower() for k in ["resume", "cv"]))
            or (state.active_document and any(str(state.active_document.get("filename", "")).lower().endswith(ext) for ext in [".pdf", ".docx"]) and (state.last_department == "HR" or state.department == "HR"))
            or (state.last_department == "HR" and ("candidate" in str(state.last_intent or "").lower() or "resume" in str(state.last_intent or "").lower() or "document_summary" in str(state.last_intent or "").lower()))
            or (state.last_verified_result and "resume" in str(state.last_verified_result).lower())
        )
        has_candidate_ref = any(
            re.search(rf"\b{w}\b", text_clean, re.I)
            for w in [
                "she", "her", "he", "his", "him", "candidate", "this candidate", "the candidate",
                "this resume", "the resume", "this person", "the person", "fit for",
                "experience", "experince", "education", "educational", "skills", "skill",
                "certification", "certifications", "qualification", "qualifications"
            ]
        )

        if is_resume_active or has_candidate_ref:
            for pat, action in self._CANDIDATE_INQUIRY_PATTERNS:
                if pat.search(text_clean):
                    signals["is_follow_up"] = True
                    signals["signal_type"] = "candidate_inquiry"
                    signals["target_action"] = action
                    signals["inherited_department"] = DepartmentEnum.HR.value
                    signals["entities"]["candidate_action"] = action
                    signals["entities"]["doc_id"] = state.active_document_id
                    signals["entities"]["document_id"] = state.active_document_id
                    signals["entities"]["filename"] = state.active_document_name
                    logger.info(f"ContextManager: Resolved candidate inquiry follow-up '{text_clean}' -> {action}")
                    return signals

        # 3. Active Excel Document Operations (Priority Resolution)
        is_excel_active = (
            str(state.active_document_type).upper() in ("EXCEL", "EXCEL_WORKBOOK", "SPREADSHEET")
            or (state.active_document and any(str(state.active_document.get("filename", "")).lower().endswith(ext) for ext in [".xlsx", ".xls", ".csv"]))
            or "sprint" in str(state.active_document_name or "").lower()
            or "qr" in str(state.active_document_name or "").lower()
            or "upi" in str(state.active_document_name or "").lower()
            or (state.last_result_type and ("FILTER_RESULT" in state.last_result_type or "EXCEL" in str(state.last_result_type)))
            or (state.last_excel_result is not None)
            or (str(state.last_intent or "").startswith("excel_"))
        )

        if is_excel_active:
            # Check if this is an explicit follow-up to mismatches/comparison
            if re.search(r"\b(export\s+(?:the\s+)?mismatches|give\s+(?:me\s+)?(?:the\s+)?mismatches\s+as\s+excel|show\s+(?:the\s+)?mismatches|how\s+many\s+mismatches|count\s+(?:the\s+)?mismatches)\b", text_clean, re.I):
                doc_a, doc_b = self.resolve_comparison_documents(state.conversation_id, text_clean)
                if doc_a and doc_b:
                    signals["is_follow_up"] = True
                    signals["signal_type"] = "excel_operation"
                    signals["target_action"] = "EXCEL_COMPARE"
                    signals["inherited_department"] = DepartmentEnum.GENERAL.value
                    signals["entities"]["action"] = "EXCEL_COMPARE"
                    signals["entities"]["operation"] = "EXCEL_COMPARE"
                    signals["entities"]["document_type"] = "EXCEL"
                    signals["entities"]["doc_id_a"] = doc_a.get("document_id") or doc_a.get("id")
                    signals["entities"]["filename_a"] = doc_a.get("filename")
                    signals["entities"]["doc_id_b"] = doc_b.get("document_id") or doc_b.get("id")
                    signals["entities"]["filename_b"] = doc_b.get("filename")
                    signals["entities"]["selected_document_ids"] = [signals["entities"]["doc_id_a"], signals["entities"]["doc_id_b"]]
                    signals["entities"]["follow_up_action"] = "COUNT_MISMATCHES" if re.search(r"\b(how\s+many|count)\b", text_clean, re.I) else "EXPORT_MISMATCHES"
                    state.selected_document_ids = signals["entities"]["selected_document_ids"]
                    logger.info(f"ContextManager: Resolved mismatch follow-up '{text_clean}' -> EXCEL_COMPARE referencing '{doc_a.get('filename')}' & '{doc_b.get('filename')}'")
                    return signals

            known_owners = []
            headers = []
            if state.active_document and isinstance(state.active_document.get("structured_data"), dict):
                known_owners = state.active_document.get("structured_data", {}).get("owners", [])
                headers = state.active_document.get("structured_data", {}).get("headers", [])

            if not headers:
                fp = (state.active_document or {}).get("file_path")
                if not fp and state.active_document_id:
                    from backend.app.services.document_manager import document_manager
                    dm = document_manager.get_document(state.active_document_id)
                    if dm:
                        fp = dm.get("file_path")
                if fp and os.path.exists(fp):
                    try:
                        from backend.app.services.excel.excel_aggregator import excel_aggregator
                        insp = excel_aggregator.inspect_workbook(fp)
                        headers = insp.get("headers", [])
                        if not isinstance(state.active_document, dict):
                            state.active_document = {}
                        if not isinstance(state.active_document.get("structured_data"), dict):
                            state.active_document["structured_data"] = {}
                        state.active_document["structured_data"]["headers"] = headers
                        if "owners" in insp:
                            known_owners = insp.get("owners", [])
                            state.active_document["structured_data"]["owners"] = known_owners
                    except Exception as e:
                        logger.warning(f"Failed to extract headers for session: {e}")

            op_type, target_owners, meta_dict = self._detect_excel_operation(text_clean, known_owners)

            # Consult SemanticExcelResolver for advanced natural language & schema understanding
            sem_req = semantic_excel_resolver.understand_request(text_clean, headers, state.active_document_id, state)
            if sem_req and sem_req.operation:
                op_map = {
                    "MULTI_DOCUMENT_SUMMARY": "EXCEL_MULTI_DOCUMENT_SUMMARY",
                    "UNIQUE_VALUES": "EXCEL_UNIQUE_VALUES",
                    "GROUP_MAX": "EXCEL_GROUP_MAX",
                    "GROUP_MIN": "EXCEL_GROUP_MIN",
                    "MAX": "EXCEL_MAX",
                    "MIN": "EXCEL_MIN",
                    "TOTAL": "EXCEL_TOTAL",
                    "AVERAGE": "EXCEL_AVERAGE",
                    "COUNT": "EXCEL_COUNT",
                    "COLUMNS": "EXCEL_COLUMN_LIST",
                    "COLUMN_EXPORT": "EXCEL_COLUMN_EXPORT",
                    "FULL_EXPORT": "EXCEL_FULL_EXPORT",
                    "EXPORT_RESULT": "EXCEL_EXPORT_RESULT",
                    "COMPARISON": "EXCEL_COMPARE",
                    "SUMMARY": "EXCEL_SUMMARY",
                    "FILTER": "EXCEL_FILTER",
                    "FILTER_EXPORT": "EXCEL_FILTER_EXPORT",
                    "FILTER_COLUMN": "EXCEL_FILTER_COLUMN",
                    "FILTER_COLUMN_EXPORT": "EXCEL_FILTER_COLUMN_EXPORT",
                    "READ_COLUMN": "EXCEL_READ_COLUMN",
                    "CLARIFICATION": "EXCEL_CLARIFICATION"
                }
                mapped_op = op_map.get(sem_req.operation)
                if mapped_op:
                    # Prefer semantic resolver when not a specialized multi-owner sprint split/filter
                    is_owner_op = bool(target_owners and op_type in ("EXCEL_SPLIT", "EXCEL_FILTER", "EXCEL_FILTER_EXPORT"))
                    if not is_owner_op and (
                        not op_type
                        or op_type == "EXCEL_SUMMARY"
                        or (mapped_op != "EXCEL_CLARIFICATION" and sem_req.confidence >= 0.85)
                    ):
                        op_type = mapped_op
                        if sem_req.target_column:
                            meta_dict["target_column"] = sem_req.target_column
                            meta_dict["column"] = sem_req.target_column
                        if sem_req.target_columns:
                            meta_dict["target_columns"] = sem_req.target_columns
                        if sem_req.target_concept:
                            meta_dict["target_concept"] = sem_req.target_concept
                        if sem_req.output_format:
                            meta_dict["output_format"] = sem_req.output_format
                        if sem_req.group_by_column:
                            meta_dict["group_by_column"] = sem_req.group_by_column
                            meta_dict["group_column"] = sem_req.group_by_column
                        if sem_req.filters:
                            meta_dict["filters"] = sem_req.filters
                            meta_dict.setdefault("filter", {}).update(sem_req.filters if isinstance(sem_req.filters, dict) else {})
                        if isinstance(sem_req.filters, dict) and sem_req.filters.get("sections"):
                            meta_dict["sections"] = sem_req.filters["sections"]
                        if isinstance(sem_req.filters, dict) and sem_req.filters.get("follow_up_action"):
                            meta_dict["follow_up_action"] = sem_req.filters["follow_up_action"]

            if op_type:
                signals["is_follow_up"] = True
                signals["signal_type"] = "excel_operation"
                signals["target_action"] = op_type
                signals["inherited_department"] = state.department or state.last_department or DepartmentEnum.GENERAL.value
                signals["entities"]["action"] = op_type
                signals["entities"]["document_type"] = "EXCEL"
                signals["entities"]["operation"] = "FILTER_AND_EXPORT" if op_type in ("EXCEL_SPLIT", "EXCEL_FILTER") and target_owners else op_type
                signals["entities"]["target_owners"] = target_owners
                signals["entities"]["column"] = meta_dict.get("target_column") or ("Owner" if target_owners else "Amount")
                signals["entities"]["target_column"] = meta_dict.get("target_column")
                signals["entities"]["target_columns"] = meta_dict.get("target_columns")
                signals["entities"]["target_concept"] = meta_dict.get("target_concept")
                signals["entities"]["output_format"] = meta_dict.get("output_format")
                signals["entities"]["group_by_column"] = meta_dict.get("group_by_column")
                signals["entities"]["group_column"] = meta_dict.get("group_by_column")
                signals["entities"]["filter"] = meta_dict.get("filter")
                signals["entities"]["filters"] = meta_dict.get("filters")
                signals["entities"]["sections"] = meta_dict.get("sections")
                signals["entities"]["follow_up_action"] = meta_dict.get("follow_up_action")
                signals["entities"]["doc_id"] = state.active_document_id
                signals["entities"]["document_id"] = state.active_document_id
                signals["entities"]["filename"] = state.active_document_name

                signals["entities"]["last_operation"] = state.last_operation
                signals["entities"]["last_metric"] = state.last_metric
                signals["entities"]["last_result"] = state.last_result
                signals["entities"]["last_excel_result"] = state.last_excel_result
                signals["entities"]["last_result_type"] = state.last_result_type
                signals["entities"]["last_filters"] = getattr(state, "last_filters", {}) or {}
                signals["entities"]["last_exportable_rows"] = getattr(state, "last_exportable_rows", []) or []
                signals["entities"]["last_target_columns"] = getattr(state, "last_target_columns", None)
                signals["entities"]["last_exportable_result"] = getattr(state, "last_exportable_result", None)
                if "_multi_doc_summary" in state.last_entities:
                    signals["entities"]["_multi_doc_summary"] = state.last_entities["_multi_doc_summary"]
                if "_comparison_result" in state.last_entities:
                    signals["entities"]["_comparison_result"] = state.last_entities["_comparison_result"]

                if op_type in ("EXCEL_COMPARE", "EXCEL_MULTI_DOCUMENT_SUMMARY"):
                    doc_a, doc_b = self.resolve_comparison_documents(state.conversation_id, text_clean)
                    if doc_a and doc_b:
                        signals["entities"]["doc_id_a"] = doc_a.get("document_id") or doc_a.get("id")
                        signals["entities"]["filename_a"] = doc_a.get("filename")
                        signals["entities"]["doc_id_b"] = doc_b.get("document_id") or doc_b.get("id")
                        signals["entities"]["filename_b"] = doc_b.get("filename")
                        signals["entities"]["selected_document_ids"] = [signals["entities"]["doc_id_a"], signals["entities"]["doc_id_b"]]
                        state.selected_document_ids = signals["entities"]["selected_document_ids"]

                logger.info(f"ContextManager: Resolved Excel operation '{text_clean}' -> {op_type} (column={meta_dict.get('target_column')}, filter={meta_dict.get('filter')}, owners={target_owners}) referencing '{state.active_document_name}'")
                return signals

        # 4. Detail expansion ("give me in detail", "explain more")
        for pat in self._EXPANSION_PATTERNS:
            if pat.search(text_clean):
                signals["is_follow_up"] = True
                signals["signal_type"] = "expansion"
                signals["target_action"] = "EXPAND"
                return signals

        # 4. Document summarization ("give me a summary of this report", "summarize this")
        for pat in self._SUMMARY_PATTERNS:
            if pat.search(text_clean):
                signals["is_follow_up"] = True
                signals["signal_type"] = "document_summary"
                signals["target_action"] = "SUMMARIZE"
                signals["entities"]["referenced_file"] = state.active_document_name or state.last_generated_file
                signals["entities"]["referenced_doc_id"] = state.active_document_id
                return signals

        # 5. Two-file / Dual invoice comparison ("compare this with the previous invoice")
        for pat in self._COMPARISON_PATTERNS:
            if pat.search(text_clean):
                signals["is_follow_up"] = True
                signals["signal_type"] = "comparison"
                signals["target_action"] = "COMPARE"
                signals["entities"]["current_doc"] = state.active_document_name
                signals["entities"]["prev_doc"] = (state.previous_document or {}).get("filename")
                return signals

        # 6. Invoice Inquiry on active document
        if state.active_document_type == "INVOICE" or "invoice" in text_clean.lower() or state.active_document:
            for pat, action in self._INVOICE_INQUIRY_PATTERNS:
                if pat.search(text_clean):
                    signals["is_follow_up"] = True
                    signals["signal_type"] = "invoice_inquiry"
                    signals["target_action"] = action
                    signals["entities"]["doc_id"] = state.active_document_id
                    signals["entities"]["filename"] = state.active_document_name
                    return signals

        # 7. Document action on previous context ("make me an excel document", "add section", "export it")
        for pat, action, fmt in self._DOCUMENT_ACTION_PATTERNS:
            match = pat.search(text_clean)
            if match:
                signals["is_follow_up"] = True
                signals["signal_type"] = "document_action"
                signals["target_action"] = action
                signals["entities"]["format"] = fmt
                if action == "MODIFY":
                    section_match = re.search(r"\b(add|insert|include)\s+(an?\s*)?([a-z\s]+?)\s*(section|clause|paragraph)\b", text_clean, re.I)
                    if section_match:
                        signals["entities"]["section_name"] = section_match.group(3).strip()
                return signals

        # 8. Arithmetic continuation ("add 500 more", "plus 200")
        arith_match = self._ARITHMETIC_CONTINUATION_PATTERN.search(text_clean)
        if arith_match:
            op = arith_match.group(1).lower()
            val_str = arith_match.group(2).replace("$", "")
            try:
                delta_val = float(val_str)
                signals["is_follow_up"] = True
                signals["signal_type"] = "arithmetic"
                signals["target_action"] = "CALCULATE"
                signals["entities"]["delta_op"] = op
                signals["entities"]["delta_val"] = delta_val
                return signals
            except ValueError:
                pass

        # 9. Generic reference check ("where should I fix it?", "show me the corrected code", "same one")
        if re.search(r"\b(where should i fix it|show me the (corrected )?code|how (do|can) i fix (it|this)|what changed|fix it)\b", text_clean, re.I):
            signals["is_follow_up"] = True
            signals["signal_type"] = "reference"
            signals["target_action"] = "FIX_LOCATION" if "where" in text_clean.lower() else "SHOW_CODE"
            return signals

        return signals

    # ------------------------------------------------------------------
    # State Updates
    # ------------------------------------------------------------------

    def record_turn(
        self,
        session_id: str,
        user_message: str,
        verified_result: CompanyAIResult,
        answer: str,
        structured_req: Optional[Any] = None,
        pending_action: Optional[str] = None,
        pending_question: Optional[str] = None
    ) -> ConversationState:
        """Updates the conversation state after a turn executes."""
        state = self.get_state(session_id)
        state.turn_count += 1
        state.last_department = verified_result.department.value

        # Update department steering if result succeeded in a concrete department
        if verified_result.department != DepartmentEnum.GENERAL:
            state.department = verified_result.department.value

        state.last_intent = verified_result.intent
        state.last_action = getattr(structured_req, "action", "QUERY") if structured_req else "QUERY"

        # Track last operation, metric, result, result_type, target_column, filters
        state.last_operation = verified_result.intent
        if verified_result.tool_results:
            tr = verified_result.tool_results
            state.last_result = tr
            state.last_result_type = "METRIC" if tr.get("card_type") == "metric_card" else ("TABLE" if tr.get("card_type") in ("excel_preview", "column_list", "filter_result", "column_values") else "GENERAL")
            state.last_metric = tr.get("title") or verified_result.intent
            state.last_target_column = tr.get("column")
            if tr.get("target_columns"):
                state.last_target_columns = tr.get("target_columns")
            if tr.get("filter"):
                state.last_filters = tr.get("filter")
            if tr.get("filters"):
                state.last_filters = tr.get("filters")
            if tr.get("matched_rows"):
                state.last_exportable_rows = tr.get("matched_rows")
                state.last_exportable_result = tr
            elif tr.get("rows"):
                state.last_exportable_rows = tr.get("rows")
                state.last_exportable_result = tr
            if verified_result.intent.startswith("excel_"):
                state.last_excel_result = tr

        if structured_req and getattr(structured_req, "filters", None):
            state.last_filters = structured_req.filters
        if structured_req and getattr(structured_req, "target_columns", None):
            state.last_target_columns = structured_req.target_columns

        if state.last_filters and isinstance(state.last_filters, dict) and state.last_filters.get("mode"):
            mode_tag = str(state.last_filters.get("mode")).upper()
            state.last_result_type = f"{mode_tag}_FILTER_RESULT"

        # Track meaningful topics
        if verified_result.task and verified_result.task not in ("Company AI General Inquiry", "Conversational Greeting"):
            state.last_topic = verified_result.task
        elif "policy" in verified_result.intent:
            state.last_topic = "HR leave policy"
        elif "expense" in verified_result.intent:
            state.last_topic = "monthly travel expenses"
        elif "invoice" in verified_result.intent:
            state.last_topic = "invoice processing"
        elif "error" in verified_result.intent or "troubleshooting" in verified_result.intent:
            state.last_topic = "project troubleshooting and error diagnosis"

        # Track entities
        if structured_req and getattr(structured_req, "entities", None):
            state.last_entities.update(structured_req.entities)
        if getattr(verified_result, "tool_results", None):
            state.last_entities.update(verified_result.tool_results)

        state.last_normalized_message = getattr(structured_req, "normalized_message", user_message) or user_message
        state.last_verified_result = {
            "department": verified_result.department.value,
            "intent": verified_result.intent,
            "task": verified_result.task,
            "summary": verified_result.summary,
            "findings": verified_result.findings,
            "tool_results": verified_result.tool_results,
            "files": verified_result.files
        }

        # Track files generated
        if verified_result.files:
            last_f = verified_result.files[-1]
            state.last_generated_file = last_f.get("filename")
            state.last_generated_file_id = last_f.get("file_id")
            state.last_file_metadata = dict(last_f)

        state.pending_action = pending_action
        state.pending_question = pending_question

        # Store compact turn in turn history
        if session_id not in self._turn_history:
            self._turn_history[session_id] = []
        self._turn_history[session_id].append({
            "timestamp": time.time(),
            "user_message": user_message,
            "department": verified_result.department.value,
            "intent": verified_result.intent,
            "answer": answer,
            "files": [f.get("filename") for f in verified_result.files] if verified_result.files else []
        })

        # Keep history bounded (last 15 turns)
        if len(self._turn_history[session_id]) > 15:
            self._turn_history[session_id] = self._turn_history[session_id][-15:]

        logger.info(
            f"ContextManager: Updated state for session '{session_id}' — "
            f"dept={state.department} last_intent={state.last_intent} "
            f"last_topic='{state.last_topic}' pending_action={state.pending_action}"
        )
        return state

    def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Returns turn history for a session."""
        return self._turn_history.get(session_id, [])

    def get_context_summary_for_qwen(self, session_id: str, max_turns: int = 5) -> Dict[str, Any]:
        """Builds a bounded context summary dictionary for Qwen Layer 1 prompt."""
        state = self.get_state(session_id)
        history = self.get_history(session_id)
        recent = history[-max_turns:] if history else []

        recent_lines = []
        for turn in recent:
            recent_lines.append(f"User: {turn.get('user_message', '')}")
            ans_short = str(turn.get('answer', ''))[:140].replace("\n", " ")
            recent_lines.append(f"Assistant: {ans_short}")

        return {
            "department": state.department or state.last_department or "None",
            "last_intent": state.last_intent or "None",
            "last_action": state.last_action or "None",
            "last_topic": state.last_topic or "None",
            "pending_action": state.pending_action or "None",
            "last_normalized_message": state.last_normalized_message or "None",
            "last_generated_file": state.last_generated_file or "None",
            "active_document": state.active_document_name or "None",
            "active_document_type": state.active_document_type or "None",
            "recent_turns": "\n".join(recent_lines) if recent_lines else "None"
        }


# Global singleton instance
conversation_context_manager = ConversationContextManager()
