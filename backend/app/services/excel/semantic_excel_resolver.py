"""Semantic Excel Resolver for Natural Language Request Understanding and Schema Resolution.

Translates diverse natural language queries into structured Excel operations and matches
semantic concepts to authentic workbook headers without fragile keyword-by-keyword if/else chains.
"""

import re
import difflib
from typing import Dict, Any, List, Optional, Tuple, Union
from pydantic import BaseModel, Field
from loguru import logger


class SemanticExcelRequest(BaseModel):
    """Structured representation of an Excel analytical operation."""
    domain: str = Field(default="EXCEL")
    operation: str = Field(..., description="SUMMARY | COLUMNS | TOTAL | COUNT | MAX | MIN | AVERAGE | FILTER | FILTER_EXPORT | FILTER_COLUMN | FILTER_COLUMN_EXPORT | SORT | GROUP | GROUP_MAX | GROUP_MIN | COMPARISON | COLUMN_EXPORT | FULL_EXPORT | EXPORT_RESULT | REPORT | READ_COLUMN | CLARIFICATION")
    target_sheet: Optional[str] = Field(default=None, description="Resolved actual worksheet name from workbook")
    target_column: Optional[str] = Field(default=None, description="Resolved actual column name from workbook")
    target_columns: Optional[Union[List[str], str]] = Field(default_factory=list, description="Resolved actual column names from workbook")
    target_concept: Optional[str] = Field(default=None, description="Semantic field concept: amount, id, date, status, mode, expiry_date, username, email, phone, etc.")
    group_by_column: Optional[str] = Field(default=None, description="Resolved actual grouping column from workbook")
    group_by_concept: Optional[str] = Field(default=None, description="Semantic grouping concept: mode, agent, store, status, owner, etc.")
    filters: Any = Field(default_factory=dict, description="Filter criteria e.g. [{'column': 'Expiry_Date', 'operator': 'BEFORE_TODAY'}] or {'mode': 'UPI'}")
    source: str = Field(default="ACTIVE_DOCUMENT", description="ACTIVE_DOCUMENT | MULTI_DOCUMENT | PREVIOUS_RESULT")
    source_documents: List[str] = Field(default_factory=list, description="Document IDs involved in operation")
    output_format: str = Field(default="ANSWER", description="ANSWER | XLSX | TABLE | METRIC_CARD")
    confidence: float = Field(default=0.95, ge=0.0, le=1.0)
    raw_query: str = Field(default="")
    clarification_message: Optional[str] = Field(default=None, description="Clarification question when request is ambiguous")


class SemanticExcelResolver:
    """Intelligent semantic mapper between user natural language and workbook schemas."""

    # Taxonomic field concept synonym sets
    CONCEPT_SYNONYMS = {
        "amount": [
            "amount", "amt", "price", "fee", "cost", "salary", "charge", "rate",
            "trans_amt", "trx_amount", "settled_amount", "settled", "net_amount", "gross_amount",
            "topup_amount", "recharge_amount", "paid", "balance", "payment_amount"
        ],
        "quantity": [
            "quantity", "qty", "quanity", "count", "units", "stock", "buffer", "shipment_quantity", "required_quantity"
        ],
        "transaction_id": [
            "trnsctn_nmbr", "transaction_id", "txn_id", "txnid", "trans_id", "reference",
            "reference_no", "ref", "rid", "bank_transaction_id", "ticket_id", "order_id", "receipt"
        ],
        "id": [
            "trnsctn_nmbr", "transaction_id", "txn_id", "txnid", "trans_id", "reference",
            "reference_no", "ref", "rid", "id", "identifier", "unique_id", "record_id",
            "vleid", "vle_id", "vle", "number", "no", "nmbr", "nbr", "code"
        ],
        "date": [
            "date", "dt", "time", "timestamp", "datetime", "created", "crtd_date", "crtd_dt",
            "topup_date", "txn_date", "transaction_date", "athrsd_date", "authorized_date",
            "settlement_date", "period", "day", "month", "year"
        ],
        "expiry_date": [
            "expiry_date", "expiry", "expired", "expires", "expire", "expiration",
            "expiration_date", "validity", "valid_upto", "due_date", "end_date", "valid_till",
            "maturity_date", "due", "exp", "validity_end", "valid_to", "expirydate", "renewal_date"
        ],
        "username": [
            "username", "user_name", "user", "users", "account", "account_name", "login",
            "login_id", "user_id", "userid", "usrname", "usr", "vle_user", "vle_username",
            "vleid_username", "vle_id"
        ],
        "name": [
            "firstname", "first_name", "fname", "name", "fullname", "full_name", "lastname",
            "last_name", "lname", "candidate_name", "employee_name", "client_name",
            "customer_name", "person_name", "person", "material_name", "materials_name"
        ],
        "email": [
            "email", "email_id", "email_address", "mail", "mail_id", "e_mail", "emailaddress", "emailid"
        ],
        "phone": [
            "phone", "mobile", "mobileno", "mobile_no", "mobile_number", "contact", "contact_no",
            "contact_number", "cell", "cell_number", "customer_mobile", "agent_mobile",
            "agent_phone", "phone_no", "mobile_num", "moile", "mobil", "phn", "telephone",
            "contact_num", "mobilenumber"
        ],
        "status": [
            "status", "state", "condition", "disposition", "result", "flag", "stage",
            "auth_status", "txn_status", "settlement_status", "progress"
        ],
        "mode": [
            "mode", "type", "method", "channel", "gateway", "medium", "transaction_mode",
            "payment_mode", "payment_method", "source_mode", "pay_mode"
        ],
        "store": [
            "store", "shop", "outlet", "branch", "location", "store_code", "store_id",
            "outlet_id", "merchant", "vendor", "facility"
        ],
        "agent": [
            "agent", "agent_name", "operator", "user", "person", "representative", "rep",
            "executive", "clerk", "cashier", "officer", "staff"
        ],
        "owner": [
            "owner", "developer", "assignee", "person", "engineer", "lead", "member",
            "author", "creator", "assigned_to"
        ],
        "bank": [
            "bank", "bank_name", "bankname", "bank_id", "financial_institution",
            "issuer_bank", "acquirer_bank", "sender_bank", "receiver_bank", "bank_desc",
            "issuing_bank", "acquiring_bank", "bank_code", "bank_title"
        ],
        "task": [
            "task", "ticket", "issue", "story", "bug", "item", "title", "summary",
            "description", "work_item", "activity"
        ]
    }

    # Core operation semantic signals
    OP_PATTERNS = {
        "SUMMARY": [
            r"\b(overall\s+summary|give\s+(?:me\s+)?(?:an?\s+)?(?:overall\s+|full\s+|complete\s+)?summary|summarize\s+(?:this|the)?\s*(?:doc|document|excel|file|workbook|sheet)|summary\s+of\s+(?:this|the)\s+(?:doc|document|excel|file|workbook|sheet)|sprint\s+summary|overview|breakdown|describe|what('s|\s+is)\s+in\s+this\s+(?:doc|document|excel|file|workbook|sheet)|what('s|\s+is)\s+in\s+the\s+(?:doc|document|excel|file|workbook|sheet)|give\s+(?:me\s+)?(?:the\s+)?(?:full\s+)?summary)\b",
            r"^(?:(?:can\s+(?:you|u)\s+)?(?:please\s+)?(?:give\s+(?:me\s+)?)?(?:a\s+|an\s+)?(?:overall\s+|full\s+|document\s+)?summary(?:\s+(?:of\s+)?(?:this|the)\s+(?:doc|document|excel|file|workbook|sheet))?|summarize|summary)[.!]?$"
        ],
        "MULTI_DOCUMENT_SUMMARY": [
            r"\b(?:summary\s+(?:report\s+)?for\s+(?:this|these)\s+2|summary\s+for\s+both\s+files?|summary\s+of\s+these\s+two|summary\s+for\s+the\s+two\s+excel\s+files|summary\s+of\s+both\s+of\s+them)\b",
            r"\b(?:give\s+me\s+a\s+summary\s+report\s+for\s+this\s+2|compare\s+these\s+two\s+and\s+summarize|summarize\s+both\s+files)\b"
        ],
        "UNIQUE_VALUES": [
            r"\b(?:what\s+(?:are\s+the\s+)?|which\s+(?:are\s+the\s+)?|give\s+me\s+(?:the\s+)?|list\s+(?:all\s+|the\s+)?|show\s+(?:me\s+)?(?:the\s+)?)(bank\s+names?|banks|banking\s+institutions?|financial\s+institutions?)(?:\s+(?:are\s+)?(?:there|included|present|represented|available))?\b",
            r"\b(?:what\s+(?:are\s+the\s+)?(?:transaction\s+|payment\s+)?modes|list\s+(?:all\s+|the\s+)?(?:transaction\s+|payment\s+)?modes|show\s+(?:me\s+)?(?:the\s+)?(?:transaction\s+|payment\s+)?modes|which\s+(?:transaction\s+|payment\s+)?modes\s+(?:are\s+)?(?:there|included|present|available|used))\b",
            r"\b(?:what\s+(?:are\s+the\s+)?|list\s+(?:all\s+|the\s+)?|show\s+(?:me\s+)?(?:the\s+)?)(transaction\s+modes?|payment\s+modes?|modes\s+of\s+payment|channels?)(?:\s+(?:are\s+)?(?:there|included|present|available))?\b"
        ],
        "FILTER": [
            r"\b(?:give\s+(?:me\s+)?only\s+(?:the\s+)?|show\s+(?:me\s+)?(?:only\s+|just\s+)?|only\s+(?:the\s+)?|filter\s+(?:by\s+|for\s+)?|just\s+)(upi|qr|bqr)(?:\s+mode)?(?:\s+transactions?|\s+payments?|\s+records?)?\b",
            r"\b(upi|qr|bqr)\s+(?:mode\s+)?(?:transactions?|payments?|details?)\b",
            r"\b(?:transactions?|payments?|records?)\s+(?:above|greater\s+than|over|>)\s*(\d+(?:,\d{3})*(?:\.\d+)?)\b"
        ],
        "GROUP_MAX": [
            r"\b(?:which|what|show|find|get)\s+([a-z0-9_\s]+?)\s+has\s+(?:the\s+)?(?:highest|biggest|largest|maximum|top|max)\s+([a-z0-9_\s]+)\b",
            r"\b(?:highest|biggest|largest|maximum|top|max)\s+([a-z0-9_\s]+?)\s+(?:for|per|by|in|each)\s+([a-z0-9_\s]+)\b",
            r"\b(?:group|breakdown|split)\s+by\s+([a-z0-9_\s]+?)\s+(?:find|show|get|with)?\s+(?:highest|biggest|largest|maximum|top|max)\s+([a-z0-9_\s]+)\b"
        ],
        "GROUP_MIN": [
            r"\b(?:which|what|show|find|get)\s+([a-z0-9_\s]+?)\s+has\s+(?:the\s+)?(?:lowest|smallest|minimum|bottom|min)\s+([a-z0-9_\s]+)\b",
            r"\b(?:lowest|smallest|minimum|bottom|min)\s+([a-z0-9_\s]+?)\s+(?:for|per|by|in|each)\s+([a-z0-9_\s]+)\b",
            r"\b(?:group|breakdown|split)\s+by\s+([a-z0-9_\s]+?)\s+(?:find|show|get|with)?\s+(?:lowest|smallest|minimum|bottom|min)\s+([a-z0-9_\s]+)\b"
        ],
        "MAX": [
            r"\b(?:which|what)\s+(?:transaction|payment|record|row|topup|amount|value|expiry|date)?\s*(?:is|was|has|had|represents)?\s*(?:the\s+)?(?:highest|biggest|largest|maximum|top|peak|greatest|latest|newest)\b",
            r"\b(highest|biggest|largest|maximum|max|top|peak|greatest|latest|newest)\s+(?:transaction|amount|payment|value|topup|money|record|row|number|expiry|date)?\b",
            r"\bwhat('s|\s+is|\s+was)\s+(?:the\s+)?(?:highest|biggest|largest|maximum|top|peak|greatest|latest|newest)\b",
            r"\bshow\s+(?:me\s+)?(?:the\s+)?(?:maximum|highest|biggest|largest|greatest|latest)\b"
        ],
        "MIN": [
            r"\b(?:which|what)\s+(?:transaction|payment|record|row|topup|amount|value|expiry|date)?\s*(?:is|was|has|had|represents)?\s*(?:the\s+)?(?:lowest|smallest|minimum|least|bottom|earliest|oldest|first)\b",
            r"\b(lowest|smallest|minimum|min|bottom|least|earliest|oldest|first)\s+(?:transaction|amount|payment|value|topup|money|record|row|number|expiry|date)?\b",
            r"\bwhat('s|\s+is|\s+was)\s+(?:the\s+)?(?:lowest|smallest|minimum|least|earliest|oldest)\b",
            r"\bshow\s+(?:me\s+)?(?:the\s+)?(?:minimum|lowest|smallest|least|earliest)\b"
        ],
        "TOTAL": [
            r"\b(total\s+(?:amount|settled|transaction|sum|value|cost|price|collection|balance|sales)|sum\s+(?:of\s+)?(?:the\s+)?(?:amount|settled|transaction|value|cost)|grand\s+total|calculate\s+(?:the\s+)?total|how\s+much\s+money|how\s+much\s+is\s+the\s+total|summation)\b",
            r"\bwhat('s|\s+is)\s+(?:the\s+)?(?:total\s+amount|sum\s+amount|total\s+value)\b"
        ],
        "AVERAGE": [
            r"\b(average\s+(?:amount|settled|transaction|value|cost|price)|avg\s+(?:amount|settled|transaction|value)|per\s+transaction\s+average|mean\s+amount)\b",
            r"\bwhat('s|\s+is)\s+(?:the\s+)?(?:average\s+amount|avg\s+amount|mean\s+amount)\b"
        ],
        "COUNT": [
            r"\b(how\s+many|count|number\s+of|total\s+number|quantity|volume)\s+(?:transactions?|records?|rows?|items?|ids?|entries|topups?|payments?|users?|accounts?|people|members?)\b",
            r"\b(?:transaction|record|row|entry|item|user|account)\s+count\b",
            r"\bhow\s+many\s+(?:are\s+)?(?:expired|active|valid)\b"
        ],
        "COLUMNS": [
            r"\b(what\s+are\s+the\s+(?:colunms?|columns?|colums?|headings?|hedings?|headers?|fields?|feilds?)(?:\s+available)?|"
            r"show\s+(?:me\s+)?(?:all\s+|the\s+|every\s+)?(?:colunms?|columns?|colums?|headings?|hedings?|headers?|fields?|feilds?)|"
            r"list\s+(?:all\s+|the\s+|every\s+)?(?:colunms?|columns?|colums?|headings?|hedings?|headers?|fields?|feilds?)|"
            r"(?:colunm|column|colum|heading|heding|header|field|feild)\s+names?|"
            r"names\s+of\s+(?:the\s+)?(?:colunms?|columns?|colums?|headings?|hedings?|headers?|fields?|feilds?)|"
            r"what\s+(?:colunms?|columns?|colums?|headings?|hedings?|headers?|fields?|feilds?)\s+are\s+there|"
            r"available\s+(?:colunms?|columns?|colums?|headings?|hedings?|headers?|fields?|feilds?)|"
            r"schema|attributes)\b"
        ],
        "FULL_EXPORT": [
            r"\b(full\s+(?:topup\s+)?history\s+as\s+excel|complete\s+(?:topup\s+)?history|entire\s+excel|whole\s+workbook|full\s+sheet|all\s+records\s+as\s+excel|all\s+data\s+as\s+excel|export\s+(?:the\s+)?(?:complete|entire|full)\s+(?:topup\s+)?(?:history|data|workbook|sheet))\b",
            r"\bgive\s+(?:me\s+)?(?:the\s+)?(?:whole\s+workbook|entire\s+workbook|complete\s+data|full\s+topup\s+history)\s+as\s+excel\b"
        ],
        "COLUMN_EXPORT": [
            r"\b(?:turn|convert|extract|export|give|get)\s+(?:the\s+|those\s+|all\s+)?([a-zA-Z0-9_\s]+?)\s+(?:field|column)?\s*(?:as|in|into|to)\s+(?:an?\s+)?(?:excel|exel|exle|sheet|spreadsheet)\b",
            r"\b(?:give\s+me\s+|extract\s+|export\s+)([a-zA-Z0-9_]+)\s+as\s+(?:excel|exel|exle)\b",
            r"\b(?:export|extract|download)\s+(?:the\s+)?([a-zA-Z0-9_]+)\s+(?:column|field)\b"
        ],
        "EXPORT_RESULT": [
            r"\b(?:(?:can\s+(?:you|u)\s+)?(?:please\s+)?(?:give|put|convert|make|show)\s+(?:me\s+)?(?:(?:it|this|that|those|the\s+result|the\s+previous\s+result)\s+)?(?:as|in|into|to)\s+(?:an?\s+)?(?:excel|exel|exle|xlsx|spreadsheet|sheet)(?:\s+(?:sheet|hseet|file))?|(?:can\s+(?:you|u)\s+)?(?:please\s+)?give\s+(?:me\s+)?(?:this|that|those|it)\s+(?:as|in|into|to)\s+(?:an?\s+)?(?:excel|exel|exle|xlsx|spreadsheet|sheet)(?:\s+(?:sheet|hseet|file))?|(?:can\s+(?:you|u)\s+)?(?:please\s+)?export\s+(?:this|that|it|these|those|the\s+result|the\s+previous\s+result|the\s+result\s+we\s+just\s+discussed)(?:\s+as\s+(?:excel|exel|exle|xlsx|spreadsheet|sheet)(?:\s+(?:sheet|hseet|file))?)?|(?:can\s+(?:you|u)\s+)?(?:please\s+)?download\s+(?:this|that|it|the\s+result|the\s+previous\s+result)(?:\s+as\s+(?:excel|exel|exle|xlsx|spreadsheet|sheet)(?:\s+(?:sheet|hseet|file))?)?|convert\s+(?:that|this|the)\s+result\s+(?:in|into|to|as)\s+(?:an?\s+)?(?:excel|exel|exle|xlsx|spreadsheet|sheet)|make\s+it\s+(?:excel|exel|exle|xlsx|spreadsheet|sheet)|make\s+an\s+(?:excel|exel|exle)\s+sheet|put\s+(?:those|these|this|that|the)\s+(?:[a-zA-Z0-9_\s]+?)\s+(?:into|in|to|as)\s+(?:a\s+|an\s+)?(?:excel|exel|exle|xlsx|spreadsheet|sheet)|export\s+the\s+result\s+we\s+just\s+discussed)\b",
            r"^(?:(?:can\s+(?:you|u)\s+)?(?:please\s+)?(?:give\s+(?:me\s+)?)?(?:as|in|into|to)\s+(?:an?\s+)?(?:excel|exel|exle|xlsx|sheet|hseet|spreadsheet)(?:\s+(?:sheet|hseet|file))?|export\s+as\s+(?:excel|exel|exle)|download\s+as\s+(?:excel|exel|exle)|as\s+(?:excel|exel|exle)(?:\s+(?:sheet|hseet|file))?|(?:excel|exel|exle)\s+(?:sheet|hseet|file))[.!]?$"
        ],
        "COMPARISON": [
            r"\b(compare|reconcile|reconciliation|differences?|different|differ|mismatches?|mismatch|discrepanc(y|ies)|diff|cross-check|what\s+doesn't\s+match|find\s+(?:the\s+)?(?:differences?|mismatches?)|give\s+me\s+only\s+the\s+(?:differences?|mismatches?)|what\s+is\s+different\s+between\s+them|what\s+is\s+missing|show\s+me\s+the\s+(?:differences?|mismatch)|give\s+me\s+the\s+(?:differences?|mismatch)\s+report)\b"
        ]
    }

    def normalize_token(self, text: str) -> str:
        """Removes special characters and normalizes token for comparison."""
        return re.sub(r"[^a-z0-9]", "", text.lower())

    def normalize_column_key(self, text: str) -> str:
        """Normalizes column names for robust typo and spelling variation matching."""
        t = str(text or "").strip().lower()
        # Common spelling variations and synonyms
        t = re.sub(r"\b(centere|center|centres|centers)\b", "centre", t)
        t = re.sub(r"\b(quantities|quanity|quanities)\b", "quantity", t)
        t = re.sub(r"\b(numbers|nmbr|nbr|num|nos)\b", "number", t)
        t = re.sub(r"\b(amounts|amt|ammount|amont|amout)\b", "amount", t)
        t = re.sub(r"\b(transactions|trans|trnsctn|txn|txns)\b", "transaction", t)
        t = re.sub(r"\b(expir|expired|expires|expiration|validity)\b", "expiry", t)
        t = re.sub(r"\b(dates|dt|dts)\b", "date", t)
        t = re.sub(r"\b(usernames|users|usr|usrs)\b", "username", t)
        t = re.sub(r"\b(vendors|vendrs)\b", "vendor", t)
        t = re.sub(r"\b(zonals|zones|zone)\b", "zonal", t)
        t = re.sub(r"\b(labels|lbls)\b", "label", t)
        t = re.sub(r"\b(mobiles|moile|mobil|moble|mbl)\b", "mobile", t)
        t = re.sub(r"\b(phones|phn|phne)\b", "phone", t)
        t = re.sub(r"\b(emails|mail|mails)\b", "email", t)
        t = re.sub(r"\b(ids|unique_id|unique_ids)\b", "id", t)
        t = re.sub(r"\b(colunms?|colums?|culumns?)\b", "column", t)
        return re.sub(r"[^a-z0-9]", "", t)

    def _clean_column_candidate(self, text: str) -> str:
        """Strips query filler words to isolate the underlying column concept candidate."""
        t = text.strip().lower()
        t = re.sub(r"\b(give\s+me|show\s+me|get\s+me|list|export|turn|convert|download|extract|fetch|can\s+i\s+get|can\s+u\s+give|tell\s+me|put\s+those|put\s+these)\b", " ", t, flags=re.I)
        t = re.sub(r"\b(what\s+is\s+the|what\s+are\s+the|what's\s+the|how\s+much\s+is\s+the|calculate\s+(?:the\s+)?)\b", " ", t, flags=re.I)
        t = re.sub(r"\b(only\s+as\s+excel|only\s+as\s+exel|only\s+as\s+exle|as\s+the\s+exle\s+hseet|as\s+the\s+excel\s+sheet|as\s+excel\s+sheet|as\s+exel\s+sheet|as\s+excel|as\s+exel|as\s+exle|in\s+excel|in\s+exel|to\s+excel|into\s+excel|sheet|hseet|spreadsheet)\b", " ", t, flags=re.I)
        t = re.sub(r"\b(column|columns|field|fields|heading|headings|header|headers|attribute|attributes)\b", " ", t, flags=re.I)
        t = re.sub(r"\b(only|all|the|those|these|their|our|my|whose|who|are|is|have|has|records?|users?|accounts?|details?)\b", " ", t, flags=re.I)
        return t.strip()

    def find_matching_columns(self, candidate_name: Optional[str], actual_headers: List[str], concept_hint: Optional[str] = None) -> List[str]:
        """Finds all distinct headers in the workbook that match the queried concept or terms with deterministic priority."""
        if not actual_headers or not candidate_name:
            return []

        cand_raw = str(candidate_name).strip()
        cand_cleaned = self._clean_column_candidate(cand_raw) or cand_raw.lower()
        cand_norm = self.normalize_column_key(cand_cleaned) or self.normalize_token(cand_cleaned)

        # 1. Exact match (case-insensitive)
        exact = [h for h in actual_headers if h.strip().lower() in (cand_raw.lower(), cand_cleaned.lower())]
        if exact:
            return exact

        # 2. Normalized exact match (including spelling normalizations e.g. centere/center/centre)
        norm_exact = [h for h in actual_headers if self.normalize_column_key(h) == cand_norm or self.normalize_token(h) == self.normalize_token(cand_cleaned)]
        if norm_exact:
            return norm_exact

        # 3. Stop-word stripped normalized exact match
        stop_words = {"of", "the", "a", "an", "for", "in", "to", "as", "is", "are", "what", "give", "me", "show", "tell", "get", "column", "columns", "field", "fields", "heading", "headings", "header", "headers", "row", "rows"}
        cand_tokens = [t for t in re.split(r"[_\s\-]+", cand_cleaned) if t and t.lower() not in stop_words and len(t) >= 2]
        cand_stopless_norm = self.normalize_column_key("".join(cand_tokens))

        stopless_matches = []
        for h in actual_headers:
            h_tokens = [t for t in re.split(r"[_\s\-]+", str(h).strip().lower()) if t and t.lower() not in stop_words and len(t) >= 2]
            h_stopless_norm = self.normalize_column_key("".join(h_tokens))
            if cand_stopless_norm and h_stopless_norm and (cand_stopless_norm == h_stopless_norm):
                stopless_matches.append(h)
        if stopless_matches:
            return stopless_matches

        # 4. Distinctive Token Coverage Matching
        # Extract meaningful distinctive words (excluding generic words like 'count', 'sum', 'total', 'avg', 'average', 'min', 'max', 'transaction', 'payment')
        generic_agg_words = {"count", "sum", "total", "average", "avg", "min", "max", "how", "many", "amount", "value", "values", "transaction", "transactions", "payment", "payments", "record", "records", "item", "items", "data"}
        distinctive_cand_tokens = [t for t in cand_tokens if t.lower() not in generic_agg_words and len(t) >= 3]

        if distinctive_cand_tokens:
            scored_headers = []
            for h in actual_headers:
                h_norm = self.normalize_column_key(h)
                h_tokens = [self.normalize_column_key(t) for t in re.split(r"[_\s\-]+", str(h).strip().lower()) if len(t) >= 2]
                matched_count = 0
                for ct in distinctive_cand_tokens:
                    ct_norm = self.normalize_column_key(ct)
                    if ct_norm and (ct_norm in h_norm or any(ct_norm in ht or ht in ct_norm for ht in h_tokens)):
                        matched_count += 1
                if matched_count > 0:
                    scored_headers.append((h, matched_count / len(distinctive_cand_tokens)))

            if scored_headers:
                scored_headers.sort(key=lambda x: x[1], reverse=True)
                top_score = scored_headers[0][1]
                # If the top header matches 100% (or significantly more) of distinctive tokens
                top_matches = [h for h, sc in scored_headers if sc == top_score]
                if top_score >= 0.5:
                    return top_matches

        # 5. Concept taxonomy matching with priority
        concept_priority = ["phone", "email", "expiry_date", "quantity", "username", "amount", "date", "name", "status", "mode", "bank", "owner", "store", "agent", "task", "id"]
        target_concepts = [concept_hint] if concept_hint and concept_hint in self.CONCEPT_SYNONYMS else concept_priority

        for concept in target_concepts:
            syns = self.CONCEPT_SYNONYMS.get(concept, [])
            concept_active = any(s in cand_cleaned for s in syns) or any(s in cand_tokens for s in syns) or (concept_hint == concept)
            if concept_active:
                matched_concept_headers = []
                for h in actual_headers:
                    h_clean = str(h).strip().lower()
                    h_norm = self.normalize_token(h_clean)
                    if any(s in h_clean or self.normalize_token(s) in h_norm for s in syns):
                        if h not in matched_concept_headers:
                            matched_concept_headers.append(h)
                if matched_concept_headers:
                    if concept in ("phone", "email", "expiry_date", "quantity", "username", "amount", "date"):
                        return matched_concept_headers

        # 6. Typo / Fuzzy Sequence Matching
        header_map = {self.normalize_column_key(h): h for h in actual_headers}
        close_matches = difflib.get_close_matches(cand_norm, list(header_map.keys()), n=3, cutoff=0.75)
        if close_matches:
            return [header_map[m] for m in close_matches]

        return []

    def resolve_column(self, candidate_name: Optional[str], actual_headers: List[str], concept_hint: Optional[str] = None) -> Optional[str]:
        """Resolves a semantic column query against authentic workbook headers with deterministic priority."""
        if not actual_headers:
            return candidate_name
        if not candidate_name:
            return None

        matching = self.find_matching_columns(candidate_name, actual_headers, concept_hint)
        if len(matching) == 1:
            return matching[0]
        elif len(matching) > 1:
            # Check for exact or normalized exact match first
            cand_raw = str(candidate_name).strip()
            cand_clean = self._clean_column_candidate(cand_raw) or cand_raw.lower()
            cand_norm = self.normalize_column_key(cand_clean)
            for m in matching:
                if m.strip().lower() in (cand_raw.lower(), cand_clean.lower()) or self.normalize_column_key(m) == cand_norm:
                    return m
            return matching[0]

        # Fallback to closest fuzzy match
        cand_norm = self.normalize_column_key(candidate_name)
        header_map = {self.normalize_column_key(h): h for h in actual_headers}
        close_matches = difflib.get_close_matches(cand_norm, list(header_map.keys()), n=1, cutoff=0.65)
        if close_matches:
            return header_map[close_matches[0]]

        return candidate_name

    def _clean_candidate(self, text: str) -> str:
        """Strips common conversational prefix/suffix framing from field or sheet queries."""
        cleaned = re.sub(
            r"^(?:can\s+(?:you|u)\s+)?(?:please\s+)?(?:give\s+(?:me\s+)?|show\s+(?:me\s+)?|get\s+(?:me\s+)?|what\s+is\s+(?:the\s+)?|what\s+are\s+(?:the\s+)?|display\s+|open\s+|view\s+|inspect\s+|fetch\s+|extract\s+|check\s+)+(?:the\s+|all\s+|a\s+|an\s+)?",
            "",
            text,
            flags=re.I
        ).strip()
        cleaned = re.sub(
            r"\b(?:as\s+(?:an?\s+)?(?:excel|sheet|spreadsheet|csv|table)|in\s+(?:the\s+)?(?:excel|sheet|workbook|document)|from\s+(?:the\s+)?(?:excel|sheet|workbook|document))\b.*$",
            "",
            cleaned,
            flags=re.I
        ).strip()
        return cleaned

    def match_sheet_name(self, query: str, available_sheets: Optional[List[str]]) -> Optional[str]:
        """Matches query against available worksheet names with strict preference over columns."""
        if not available_sheets:
            return None

        cleaned = self._clean_candidate(query)
        cleaned_no_tab = re.sub(r"\b(sheets?|worksheets?|tabs?|data)\b", "", cleaned, flags=re.I).strip()

        cand_norm = self.normalize_token(cleaned)
        cand_norm_no_tab = self.normalize_token(cleaned_no_tab)

        # 1. Exact match (case-insensitive)
        for s in available_sheets:
            if s.lower() in (query.lower(), cleaned.lower(), cleaned_no_tab.lower()):
                return s

        # 2. Normalized token exact match
        for s in available_sheets:
            s_norm = self.normalize_token(s)
            if s_norm and (s_norm == cand_norm or s_norm == cand_norm_no_tab):
                return s

        # 3. If explicit sheet keyword present ("... sheet", "... worksheet", "... tab")
        has_sheet_kw = bool(re.search(r"\b(sheets?|worksheets?|tabs?)\b", query, re.I))
        if has_sheet_kw and cand_norm_no_tab:
            for s in available_sheets:
                s_norm = self.normalize_token(s)
                if cand_norm_no_tab in s_norm or s_norm in cand_norm_no_tab:
                    return s

        # 4. Containment match if cand_norm is strong (>= 4 chars) and matches full sheet
        for s in available_sheets:
            s_norm = self.normalize_token(s)
            if s_norm and len(cand_norm_no_tab) >= 4 and (cand_norm_no_tab == s_norm or s_norm in cand_norm or cand_norm_no_tab in s_norm):
                return s

        return None

    def resolve_schema_for_structured_request(
        self,
        structured_req: Any,
        actual_headers: List[str],
        available_sheets: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Maps concepts from Qwen Layer 1 StructuredRequest to authentic workbook headers and schema entities."""
        resolved: Dict[str, Any] = {}
        headers = actual_headers or []
        sheets = available_sheets or []

        # 0. Target Sheet resolution
        target_sheet = getattr(structured_req, "target_sheet", None)
        if target_sheet and sheets:
            matched_s = self.match_sheet_name(target_sheet, sheets)
            if matched_s:
                resolved["target_sheet"] = matched_s
                resolved["sheet"] = matched_s

        # 1. Target Concept -> Target Column
        target_concept = getattr(structured_req, "target_concept", None)
        if target_concept and headers:
            col = self.resolve_column(target_concept, headers, concept_hint=target_concept)
            if col and col in headers:
                resolved["target_column"] = col
                resolved["column"] = col
                resolved["target_columns"] = [col]

        # 2. Target Columns list resolution
        target_columns = getattr(structured_req, "target_columns", []) or []
        if target_columns and headers:
            cols = []
            for tc in target_columns:
                c = self.resolve_column(tc, headers, concept_hint=tc)
                if c and c in headers and c not in cols:
                    cols.append(c)
            if cols:
                resolved["target_columns"] = cols
                if not resolved.get("target_column"):
                    resolved["target_column"] = cols[0]
                    resolved["column"] = cols[0]

        # 3. Group By dimension resolution
        group_by = getattr(structured_req, "group_by", None)
        if group_by and headers:
            if group_by not in ("month", "year", "day", "daily", "monthly", "yearly", "date"):
                c_grp = self.resolve_column(group_by, headers, concept_hint=group_by)
                if c_grp and c_grp in headers:
                    resolved["group_by_column"] = c_grp
                    resolved["group_column"] = c_grp
                    resolved["group_by_dimension"] = c_grp
            else:
                resolved["group_by_dimension"] = group_by

        # 4. Filter resolution (e.g. expired, validity passed)
        filters = getattr(structured_req, "filters", {}) or {}
        operation = getattr(structured_req, "operation", None)
        if operation in ("FILTER", "FILTER_EXPORT", "FILTER_COLUMN") and isinstance(filters, dict) and filters:
            f_keys = [str(k).lower() for k in filters.keys()]
            f_vals = [str(v).lower() for v in filters.values()]
            if any("expir" in k or "valid" in k or "status" in k for k in f_keys) and any("expir" in v or "past" in v or "before_today" in v or "passed" in v or "no longer" in v or "crossed" in v for v in f_vals):
                exp_col = self.resolve_column("expiry_date", headers) or "Expiry_Date"
                resolved["filters"] = [{"column": exp_col, "operator": "BEFORE_TODAY"}]
                resolved["filter"] = [{"column": exp_col, "operator": "BEFORE_TODAY"}]
            else:
                resolved["filters"] = filters
                resolved["filter"] = filters
        elif filters:
            resolved["filters"] = filters
            resolved["filter"] = filters

        return resolved

    def understand_request(
        self,
        query: str,
        actual_headers: Optional[List[str]] = None,
        active_doc_id: Optional[str] = None,
        context_state: Optional[Any] = None,
        available_sheets: Optional[List[str]] = None
    ) -> SemanticExcelRequest:
        """Parses natural language query into a structured SemanticExcelRequest."""
        query_clean = query.strip()
        query_norm = query_clean
        query_norm = re.sub(r"\b(sumarry|summry|summarie|sumary)\b", "summary", query_norm, flags=re.I)
        query_norm = re.sub(r"\b(docuemt|documnt|docuemnt|docment)\b", "document", query_norm, flags=re.I)
        query_norm = re.sub(r"\b(experince|expereince|experiance)\b", "experience", query_norm, flags=re.I)
        query_norm = re.sub(r"\b(centere|center|centres|centers)\b", "centre", query_norm, flags=re.I)
        headers = actual_headers or []
        sheets = available_sheets or []

        # 0. Check Worksheet Resolution ("give me the user modules", "show summary sheet")
        # Ensure sheet matching takes priority over column fuzzy matching unless explicit column inquiry
        is_explicit_col_kw = bool(re.search(r"\b(column|columns|field|fields|heading|headings|header|headers)\b", query_clean, re.I))
        if sheets and not is_explicit_col_kw:
            matched_sheet = self.match_sheet_name(query_clean, sheets)
            if matched_sheet:
                return SemanticExcelRequest(
                    operation="READ_SHEET",
                    target_sheet=matched_sheet,
                    source="ACTIVE_DOCUMENT",
                    output_format="ANSWER",
                    confidence=0.99,
                    raw_query=query_clean
                )

        # 1. Check Contextual Export Result ("give me this as Excel", "make an Excel sheet")
        # Only when NOT specifying a specific filter condition (e.g. expired, upi, validity, etc.)
        has_filter_keyword = bool(re.search(r"\b(expired?|expires?|expir\w*|valid\w*|upi|qr|bqr|today|tomorrow|week|month|greater|above|less|<|>)\b", query_clean, re.I))
        if not has_filter_keyword:
            for pat in self.OP_PATTERNS["EXPORT_RESULT"]:
                if re.search(pat, query_clean, re.I):
                    filt = {}
                    mode_m = re.search(r"\b(upi|qr|bqr)\b", query_clean, re.I)
                    if mode_m:
                        filt["mode"] = mode_m.group(1).upper()
                    last_cols = getattr(context_state, "last_target_columns", [])
                    if isinstance(last_cols, str):
                        last_cols = [last_cols]
                    elif not isinstance(last_cols, list):
                        last_cols = []
                    return SemanticExcelRequest(
                        operation="EXPORT_RESULT",
                        target_column=getattr(context_state, "last_target_column", None),
                        target_columns=last_cols,
                        target_concept="last_result",
                        filters=getattr(context_state, "last_filters", filt) or filt,
                        source="PREVIOUS_RESULT",
                        output_format="XLSX",
                        confidence=0.99,
                        raw_query=query_clean
                    )

        # 2. Check Multi-Document Summary
        is_summary_query = bool(re.search(r"\b(summary|summarize|overview|breakdown)\b", query_clean, re.I))
        is_multi_doc_query = is_summary_query and bool(
            re.search(r"\b(this\s+2|these\s+2|these\s+two|both\s+files?|two\s+files?|2\s+files?|both\s+of\s+them|this\s+and\s+that|from\s+both)\b", query_clean, re.I)
            or any(re.search(p, query_clean, re.I) for p in self.OP_PATTERNS["MULTI_DOCUMENT_SUMMARY"])
        )
        if is_multi_doc_query:
            sections = []
            if re.search(r"\b(highest|max|biggest|largest|peak|top)\b", query_clean, re.I):
                sections.append("HIGHEST_TRANSACTION")
            if re.search(r"\b(mismatch|difference|reconcil|discrepanc|what\s+doesn't\s+match|what\s+is\s+different|what\s+is\s+missing)\b", query_clean, re.I):
                sections.append("MISMATCHES")
            if re.search(r"\b(bank|banks|financial\s+institution)\b", query_clean, re.I):
                sections.append("BANK_NAMES")
            if re.search(r"\b(mode|channel|method)\b", query_clean, re.I):
                sections.append("TRANSACTION_MODES")
            if re.search(r"\b(total|sum|count|volume)\b", query_clean, re.I):
                sections.append("TOTALS")
            if not sections:
                sections = ["HIGHEST_TRANSACTION", "MISMATCHES", "BANK_NAMES"]

            return SemanticExcelRequest(
                operation="MULTI_DOCUMENT_SUMMARY",
                source="MULTI_DOCUMENT",
                filters={"sections": sections},
                output_format="ANSWER",
                confidence=0.99,
                raw_query=query_clean
            )

        # 2b. Check Comparison & Reconciliation (Two-file or Mismatch Queries)
        is_compare_query = bool(re.search(r"\b(compare|reconcil\w*|mismatch\w*|discrepanc\w*|what\s+is\s+different|what\s+is\s+missing|diff)\b", query_clean, re.I))
        if is_compare_query:
            follow_up = None
            if re.search(r"\b(excel|exel|exle|sheet|hseet|file|export|download|xlsx|csv)\b", query_clean, re.I):
                follow_up = "EXPORT_MISMATCHES"
            elif re.search(r"\b(how\s+many|count)\b", query_clean, re.I):
                follow_up = "COUNT_MISMATCHES"
            elif re.search(r"\b(show|details|list|mismatch)\b", query_clean, re.I):
                follow_up = "SHOW_MISMATCHES"

            return SemanticExcelRequest(
                operation="COMPARISON",
                source="MULTI_DOCUMENT",
                filters={"follow_up_action": follow_up} if follow_up else {},
                output_format="TABLE" if follow_up == "SHOW_MISMATCHES" else ("XLSX" if follow_up == "EXPORT_MISMATCHES" else "ANSWER"),
                confidence=0.98,
                raw_query=query_clean
            )

        # 3. Follow-up Column Request on previous filter result (e.g. "give me their usernames", "give me their usernames as excel", "can I get their phone numbers?")
        is_follow_up_col = bool(re.search(r"\b(their\s+|those\s+|these\s+)?(usernames?|mobile|phone|contact|emails?|names?|ids?)\b", query_clean, re.I))
        has_prev_filter = bool(context_state and (getattr(context_state, "last_exportable_rows", None) or getattr(context_state, "last_filters", None) or "FILTER" in str(getattr(context_state, "last_result_type", ""))))
        
        if is_follow_up_col and has_prev_filter and not re.search(r"\b(who|which|how\s+many|count|all|expired)\b", query_clean, re.I):
            cand_col = self.resolve_column(query_clean, headers)
            is_exp = bool(re.search(r"\b(excel|sheet|spreadsheet|export|download)\b", query_clean, re.I))
            if cand_col and cand_col in headers:
                return SemanticExcelRequest(
                    operation="FILTER_COLUMN_EXPORT" if is_exp else "FILTER_COLUMN",
                    target_column=cand_col,
                    target_columns=[cand_col],
                    target_concept=self.normalize_token(cand_col),
                    source="PREVIOUS_RESULT",
                    output_format="XLSX" if is_exp else "ANSWER",
                    confidence=0.99,
                    raw_query=query_clean
                )

        # 4. Check Expiry / Date Intelligence Queries
        is_expiry_word = bool(re.search(r"\b(expir\w*|valid\w*|expiration|validity|no\s+longer\s+valid|crossed\s+(?:their\s+)?expiry)\b", query_clean, re.I))
        if is_expiry_word:
            target_date_col = self.resolve_column("Expiry_Date", headers, concept_hint="expiry_date") or "Expiry_Date"
            
            # 4a. Latest / Earliest Expiry Date
            if re.search(r"\b(latest|highest|newest|maximum|max)\b", query_clean, re.I):
                return SemanticExcelRequest(
                    operation="MAX",
                    target_column=target_date_col,
                    target_concept="expiry_date",
                    source="ACTIVE_DOCUMENT",
                    output_format="METRIC_CARD",
                    confidence=0.99,
                    raw_query=query_clean
                )
            if re.search(r"\b(earliest|lowest|oldest|minimum|min|first)\b", query_clean, re.I):
                return SemanticExcelRequest(
                    operation="MIN",
                    target_column=target_date_col,
                    target_concept="expiry_date",
                    source="ACTIVE_DOCUMENT",
                    output_format="METRIC_CARD",
                    confidence=0.99,
                    raw_query=query_clean
                )

            # 4b. Pure column inquiry ("what is the expiry date?", "when does it expire")
            if re.search(r"\b(what\s+(?:is|are)\s+(?:the\s+)?expiry(?:\s+date)?|when\s+does\s+it\s+expire|what\s+is\s+the\s+validity)\b", query_clean, re.I) and not re.search(r"\b(who|which|how\s+many|count|all|expired|users?)\b", query_clean, re.I):
                return SemanticExcelRequest(
                    operation="READ_COLUMN",
                    target_column=target_date_col,
                    target_concept="expiry_date",
                    source="ACTIVE_DOCUMENT",
                    output_format="ANSWER",
                    confidence=0.98,
                    raw_query=query_clean
                )

            # 4c. Time frame filters
            operator = "BEFORE_TODAY"
            if re.search(r"\b(this\s+month|current\s+month)\b", query_clean, re.I):
                operator = "CURRENT_MONTH"
            elif re.search(r"\b(last\s+month|previous\s+month)\b", query_clean, re.I):
                operator = "LAST_MONTH"
            elif re.search(r"\b(next\s+month)\b", query_clean, re.I):
                operator = "NEXT_MONTH"
            elif re.search(r"\btoday\b", query_clean, re.I):
                operator = "TODAY"
            elif re.search(r"\btomorrow\b", query_clean, re.I):
                operator = "TOMORROW"
            elif re.search(r"\b(this\s+week|current\s+week)\b", query_clean, re.I):
                operator = "THIS_WEEK"

            is_count = bool(re.search(r"\b(how\s+many|count|number\s+of|total\s+number)\b", query_clean, re.I))
            is_export = bool(re.search(r"\b(excel|sheet|spreadsheet|export|download|put\s+(?:those|them|these)\s+into)\b", query_clean, re.I))
            
            # Check if specific column was requested with expired filter (e.g. "give me usernames of expired users")
            target_cols = []
            if re.search(r"\b(username|user\s+name|usernames|users)\b", query_clean, re.I):
                u_col = self.resolve_column("UserName", headers, concept_hint="username")
                if u_col:
                    target_cols.append(u_col)

            if is_export:
                return SemanticExcelRequest(
                    operation="FILTER_EXPORT",
                    target_column=target_date_col,
                    target_columns=target_cols if target_cols else [target_date_col],
                    target_concept="expiry_date",
                    filters=[{"column": target_date_col, "operator": operator}],
                    source="ACTIVE_DOCUMENT",
                    output_format="XLSX",
                    confidence=0.99,
                    raw_query=query_clean
                )
            elif is_count:
                return SemanticExcelRequest(
                    operation="FILTER_COUNT",
                    target_column=target_date_col,
                    target_concept="expiry_date",
                    filters=[{"column": target_date_col, "operator": operator}],
                    source="ACTIVE_DOCUMENT",
                    output_format="METRIC_CARD",
                    confidence=0.99,
                    raw_query=query_clean
                )
            elif target_cols:
                return SemanticExcelRequest(
                    operation="FILTER_COLUMN",
                    target_column=target_date_col,
                    target_columns=target_cols,
                    target_concept="expiry_date",
                    filters=[{"column": target_date_col, "operator": operator}],
                    source="ACTIVE_DOCUMENT",
                    output_format="ANSWER",
                    confidence=0.99,
                    raw_query=query_clean
                )
            else:
                return SemanticExcelRequest(
                    operation="FILTER",
                    target_column=target_date_col,
                    target_concept="expiry_date",
                    filters=[{"column": target_date_col, "operator": operator}],
                    source="ACTIVE_DOCUMENT",
                    output_format="TABLE",
                    confidence=0.99,
                    raw_query=query_clean
                )

        # 5. Check Mode Queries (UPI, QR, BQR)
        mode_match = re.search(r"\b(upi|qr|bqr)\b", query_clean, re.I)
        if mode_match and not re.search(r"\b(what\s+are\s+the\s+modes|list\s+modes|compare\s+modes)\b", query_clean, re.I):
            matched_mode = mode_match.group(1).upper()
            is_export_req = bool(re.search(r"\b(?:as|in|into|to)\s+(?:an?\s+)?(?:excel|sheet|spreadsheet)\b", query_clean, re.I))
            is_count_req = bool(re.search(r"\b(how\s+many|count|number\s+of|total\s+number|quantity|volume)\b", query_clean, re.I))
            is_total_req = bool(re.search(r"\b(total|sum|grand\s+total|amount|value|money)\b", query_clean, re.I)) and not is_count_req

            if is_export_req:
                return SemanticExcelRequest(
                    operation="EXPORT_RESULT",
                    target_column=self.resolve_column("Amount", headers, concept_hint="amount") or "Amount",
                    target_concept="mode",
                    filters={"mode": matched_mode},
                    source="ACTIVE_DOCUMENT",
                    output_format="XLSX",
                    confidence=0.99,
                    raw_query=query_clean
                )
            elif is_total_req:
                resolved_target = self.resolve_column("Amount", headers, concept_hint="amount")
                return SemanticExcelRequest(
                    operation="TOTAL",
                    target_column=resolved_target or "Amount",
                    target_concept="amount",
                    filters={"mode": matched_mode},
                    source="ACTIVE_DOCUMENT",
                    output_format="METRIC_CARD",
                    confidence=0.99,
                    raw_query=query_clean
                )
            elif is_count_req:
                resolved_target = self.resolve_column("Transaction ID", headers, concept_hint="id")
                return SemanticExcelRequest(
                    operation="COUNT",
                    target_column=resolved_target or "Transaction ID",
                    target_concept="id",
                    filters={"mode": matched_mode},
                    source="ACTIVE_DOCUMENT",
                    output_format="METRIC_CARD",
                    confidence=0.99,
                    raw_query=query_clean
                )
            else:
                resolved_target = self.resolve_column("Amount", headers, concept_hint="amount")
                return SemanticExcelRequest(
                    operation="FILTER",
                    target_column=resolved_target or "Amount",
                    target_concept="mode",
                    filters={"mode": matched_mode},
                    source="ACTIVE_DOCUMENT",
                    output_format="METRIC_CARD",
                    confidence=0.99,
                    raw_query=query_clean
                )

        # 5b. Check Numeric Threshold Queries ("transactions above 10000", "payments greater than 5000")
        num_thresh_m = re.search(r"\b(?:transactions?|payments?|records?|amounts?|values?|rows?)\s+(?:above|greater\s+than|over|>)\s*(\d+(?:,\d{3})*(?:\.\d+)?)\b", query_clean, re.I)
        if num_thresh_m:
            thresh_val = float(num_thresh_m.group(1).replace(",", ""))
            amt_col = self.resolve_column("Amount", headers, concept_hint="amount") or "Amount"
            return SemanticExcelRequest(
                operation="FILTER",
                target_column=amt_col,
                target_concept="amount",
                filters={"column": amt_col, "operator": ">", "value": thresh_val},
                source="ACTIVE_DOCUMENT",
                output_format="TABLE",
                confidence=0.99,
                raw_query=query_clean
            )

        # 6. Check UNIQUE_VALUES
        for pat in self.OP_PATTERNS["UNIQUE_VALUES"]:
            m = re.search(pat, query_clean, re.I)
            if m:
                matched_target = (m.group(1).lower() if m.groups() else query_clean.lower())
                if "bank" in matched_target:
                    resolved_target = self.resolve_column("Bank_Name", headers, concept_hint="bank")
                    return SemanticExcelRequest(
                        operation="UNIQUE_VALUES",
                        target_column=resolved_target or "Bank Name",
                        target_concept="bank",
                        source="ACTIVE_DOCUMENT",
                        output_format="ANSWER",
                        confidence=0.98,
                        raw_query=query_clean
                    )
                elif any(k in matched_target for k in ["mode", "channel", "method"]):
                    resolved_target = self.resolve_column("Transaction Mode", headers, concept_hint="mode")
                    return SemanticExcelRequest(
                        operation="UNIQUE_VALUES",
                        target_column=resolved_target or "Transaction Mode",
                        target_concept="mode",
                        source="ACTIVE_DOCUMENT",
                        output_format="ANSWER",
                        confidence=0.98,
                        raw_query=query_clean
                    )

        # 7. Check Columns / Headings Listing
        for pat in self.OP_PATTERNS["COLUMNS"]:
            if re.search(pat, query_clean, re.I):
                return SemanticExcelRequest(
                    operation="COLUMNS",
                    source="ACTIVE_DOCUMENT",
                    output_format="ANSWER",
                    confidence=0.98,
                    raw_query=query_clean
                )

        # 8. Check Group Aggregations (GROUP_MAX, GROUP_MIN)
        doc_refs = {"excel", "spreadsheet", "document", "file", "sheet", "workbook", "table", "data", "records", "rows"}
        for pat in self.OP_PATTERNS["GROUP_MAX"]:
            m = re.search(pat, query_clean, re.I)
            if m:
                groups = m.groups()
                group_cand = groups[0] if len(groups) > 0 else "mode"
                target_cand = groups[1] if len(groups) > 1 else "amount"
                if any(k in group_cand.lower() for k in ["amount", "transaction", "payment", "value"]):
                    group_cand, target_cand = target_cand, group_cand

                if any(c in group_cand.lower() for c in doc_refs) and not any(k in group_cand.lower() for k in ["mode", "channel", "type", "store", "agent", "category", "status", "each", "group", "code"]):
                    resolved_target = self.resolve_column(target_cand, headers, concept_hint="amount")
                    return SemanticExcelRequest(
                        operation="MAX",
                        target_column=resolved_target or "Amount",
                        target_concept="amount",
                        source="ACTIVE_DOCUMENT",
                        output_format="ANSWER",
                        confidence=0.98,
                        raw_query=query_clean
                    )

                resolved_group = self.resolve_column(group_cand, headers, concept_hint="mode")
                resolved_target = self.resolve_column(target_cand, headers, concept_hint="amount")
                return SemanticExcelRequest(
                    operation="GROUP_MAX",
                    target_column=resolved_target or "Amount",
                    target_concept="amount",
                    group_by_column=resolved_group or "Transaction Mode",
                    group_by_concept="mode",
                    source="ACTIVE_DOCUMENT",
                    output_format="ANSWER",
                    confidence=0.96,
                    raw_query=query_clean
                )

        for pat in self.OP_PATTERNS["GROUP_MIN"]:
            m = re.search(pat, query_clean, re.I)
            if m:
                groups = m.groups()
                group_cand = groups[0] if len(groups) > 0 else "mode"
                target_cand = groups[1] if len(groups) > 1 else "amount"
                if any(k in group_cand.lower() for k in ["amount", "transaction", "payment", "value"]):
                    group_cand, target_cand = target_cand, group_cand

                if any(c in group_cand.lower() for c in doc_refs) and not any(k in group_cand.lower() for k in ["mode", "channel", "type", "store", "agent", "category", "status", "each", "group", "code"]):
                    resolved_target = self.resolve_column(target_cand, headers, concept_hint="amount")
                    return SemanticExcelRequest(
                        operation="MIN",
                        target_column=resolved_target or "Amount",
                        target_concept="amount",
                        source="ACTIVE_DOCUMENT",
                        output_format="ANSWER",
                        confidence=0.98,
                        raw_query=query_clean
                    )

                resolved_group = self.resolve_column(group_cand, headers, concept_hint="mode")
                resolved_target = self.resolve_column(target_cand, headers, concept_hint="amount")
                return SemanticExcelRequest(
                    operation="GROUP_MIN",
                    target_column=resolved_target or "Amount",
                    target_concept="amount",
                    group_by_column=resolved_group or "Transaction Mode",
                    group_by_concept="mode",
                    source="ACTIVE_DOCUMENT",
                    output_format="ANSWER",
                    confidence=0.96,
                    raw_query=query_clean
                )

        # 9. Check SUMMARY (Overall summary, workbook summary, document summary)
        for pat in self.OP_PATTERNS["SUMMARY"]:
            if re.search(pat, query_norm, re.I):
                is_detailed = bool(re.search(r"\b(detail|detailed|in-depth|deep|breakdown)\b", query_norm, re.I))
                return SemanticExcelRequest(
                    operation="SUMMARY",
                    source="ACTIVE_DOCUMENT",
                    output_format="ANSWER",
                    filters={"detailed": True} if is_detailed else {},
                    confidence=0.98,
                    raw_query=query_clean
                )

        # 10. Check Full Export
        for pat in self.OP_PATTERNS["FULL_EXPORT"]:
            if re.search(pat, query_norm, re.I):
                return SemanticExcelRequest(
                    operation="FULL_EXPORT",
                    source="ACTIVE_DOCUMENT",
                    output_format="XLSX",
                    confidence=0.98,
                    raw_query=query_clean
                )

        # 11. Check COMPARISON (Must evaluate before raw column resolution for queries like 'How many differences?')
        for pat in self.OP_PATTERNS["COMPARISON"]:
            if re.search(pat, query_clean, re.I):
                follow_up = None
                if re.search(r"\b(excel|sheet|file|export|download)\b", query_clean, re.I):
                    follow_up = "EXPORT_MISMATCHES"
                elif re.search(r"\b(price\s+diff|price\s+difference)\b", query_clean, re.I):
                    follow_up = "FILTER_PRICE_DIFFERENCES"
                elif re.search(r"\b(availability|route)\b", query_clean, re.I):
                    follow_up = "FILTER_AVAILABILITY"
                elif re.search(r"\b(fail|failed|failure)\b", query_clean, re.I):
                    follow_up = "FILTER_FAILED_CASES"
                elif re.search(r"\b(how\s+many|count|number\s+of)\b", query_clean, re.I):
                    follow_up = "COUNT_DIFFERENCES"
                elif re.search(r"\b(show|details|list|mismatch|differences?)\b", query_clean, re.I):
                    follow_up = "SHOW_MISMATCHES"

                active_docs = getattr(context_state, "active_documents", []) or []
                source_doc = "MULTI_DOCUMENT" if len(active_docs) > 1 else "ACTIVE_DOCUMENT"
                logger.info(
                    f"\n[SEMANTIC_PIPELINE]\n"
                    f"raw_message: {query_clean}\n"
                    f"operation: COMPARISON\n"
                    f"follow_up_action: {follow_up}\n"
                    f"document_id: {active_doc_id}"
                )
                return SemanticExcelRequest(
                    operation="COMPARISON",
                    source=source_doc,
                    filters={"follow_up_action": follow_up} if follow_up else {},
                    output_format="TABLE" if follow_up in ("SHOW_MISMATCHES", "FILTER_PRICE_DIFFERENCES", "FILTER_AVAILABILITY", "FILTER_FAILED_CASES") else ("XLSX" if follow_up == "EXPORT_MISMATCHES" else "ANSWER"),
                    confidence=0.98,
                    raw_query=query_clean
                )

        # 12. Column Target & Operation Resolution (Target != Operation)
        cand_lower = query_norm.lower()
        has_filter_condition = bool(re.search(r"\b(above|greater|less|over|<|>|expired?|expires?|expir\w*|valid\w*|between|compare|mismatch|difference|differences|diff)\b", cand_lower))
        if not has_filter_condition and headers:
            matching_cols = self.find_matching_columns(query_norm, headers)
            cand_clean_name = self._clean_candidate(query_norm) or query_norm
            cand_norm = self.normalize_column_key(cand_clean_name)
            exact_match = next((h for h in headers if h.lower() in (query_norm.lower(), cand_clean_name.lower()) or self.normalize_column_key(h) == cand_norm), None)

            # If multiple genuine ambiguous candidates and no exact match -> Ask Clarification
            if len(matching_cols) > 1 and not exact_match:
                col_items = [f"{idx}. `{c}`" for idx, c in enumerate(matching_cols[:8], start=1)]
                clarif_msg = "I found multiple matching columns in the workbook:\n\n" + "\n".join(col_items) + "\n\nWhich one would you like to use?"

                is_exp = bool(re.search(r"\b(as\s+(?:an?\s+)?(?:excel|exel|exle|xlsx|spreadsheet|sheet)|export|download|make\s+an\s+excel\s+sheet)\b", query_norm, re.I))
                is_tot = bool(re.search(r"\b(total|sum|grand\s+total|overall\s+total|add\s+up|summation|calculate)\b", query_norm, re.I))
                is_cnt = bool(re.search(r"\b(how\s+many|count|number\s+of)\b", query_norm, re.I))
                is_avg = bool(re.search(r"\b(average|avg|mean)\b", query_norm, re.I))
                orig_op = "EXCEL_COLUMN_EXPORT" if is_exp else ("EXCEL_TOTAL" if is_tot else ("EXCEL_COUNT" if is_cnt else ("EXCEL_AVERAGE" if is_avg else "EXCEL_READ_COLUMN")))

                return SemanticExcelRequest(
                    operation="CLARIFICATION",
                    target_columns=matching_cols,
                    target_concept="column",
                    source="ACTIVE_DOCUMENT",
                    output_format="ANSWER",
                    confidence=0.95,
                    raw_query=query_clean,
                    clarification_message=clarif_msg,
                    filters={"pending_operation": orig_op}
                )

            # Single target column resolved
            resolved_col = exact_match or (matching_cols[0] if len(matching_cols) == 1 else self.resolve_column(query_norm, headers))
            if resolved_col and resolved_col in headers:
                col_norm = self.normalize_column_key(resolved_col)
                cand_clean_norm = self.normalize_column_key(cand_clean_name)
                
                # Verify match relevance (either exact, normalized, or distinctive token containment)
                col_tokens = [self.normalize_column_key(t) for t in re.split(r"[_\s\-]+", resolved_col) if len(t) >= 2]
                cand_tokens = [self.normalize_column_key(t) for t in re.split(r"[_\s\-]+", cand_clean_name) if len(t) >= 2]
                has_token_overlap = any(ct in col_norm or any(ct in ht or ht in ct for ht in col_tokens) for ct in cand_tokens)

                if exact_match or (len(matching_cols) == 1 and matching_cols[0] == resolved_col) or col_norm in cand_clean_norm or cand_clean_norm in col_norm or has_token_overlap:
                    is_col_export = bool(
                        re.search(r"\b(as\s+(?:an?\s+)?(?:excel|exel|exle|xlsx|spreadsheet|sheet)|export|download|make\s+an\s+excel\s+sheet|give\s+.*\s+as\s+excel)\b", query_norm, re.I)
                        or (re.search(r"\b(excel|exel|exle|sheet|xlsx)\b", query_norm, re.I) and not re.search(r"\b(in\s+(?:the\s+|this\s+)?(?:excel|exel|document|workbook|sheet)|from\s+(?:the\s+|this\s+)?(?:excel|exel|document|workbook|sheet)|calculate|total|sum|average|avg|count)\b", query_norm, re.I))
                    )
                    is_tot = bool(re.search(r"\b(total|sum|grand\s+total|overall\s+total|add\s+up|summation|calculate)\b", query_norm, re.I))
                    is_avg = bool(re.search(r"\b(average|avg|mean)\b", query_norm, re.I))
                    is_min = bool(re.search(r"\b(minimum|min|lowest|smallest)\b", query_norm, re.I))
                    is_max = bool(re.search(r"\b(maximum|max|highest|biggest|largest|peak)\b", query_norm, re.I))
                    is_cnt = bool(re.search(r"\b(how\s+many|number\s+of|count\s+of\s+rows|records)\b", query_norm, re.I))

                    if is_col_export:
                        op = "COLUMN_EXPORT"
                        out_fmt = "XLSX"
                    elif is_tot:
                        op = "TOTAL"
                        out_fmt = "METRIC_CARD"
                    elif is_avg:
                        op = "AVERAGE"
                        out_fmt = "METRIC_CARD"
                    elif is_min:
                        op = "MIN"
                        out_fmt = "METRIC_CARD"
                    elif is_max:
                        op = "MAX"
                        out_fmt = "METRIC_CARD"
                    elif is_cnt:
                        op = "COUNT"
                        out_fmt = "METRIC_CARD"
                    else:
                        if re.search(r"\b(what\s+is\s+(?:the\s+)?total|what\s+is\s+(?:the\s+)?count|how\s+much\s+is|calculate)\b", query_clean, re.I):
                            op = "TOTAL" if "count" in resolved_col.lower() else "READ_COLUMN"
                            out_fmt = "METRIC_CARD" if op == "TOTAL" else "ANSWER"
                        else:
                            op = "READ_COLUMN"
                            out_fmt = "ANSWER"

                    logger.info(
                        f"\n[SEMANTIC_PIPELINE]\n"
                        f"raw_message: {query_clean}\n"
                        f"target_candidate: {resolved_col}\n"
                        f"target_resolution: {'EXACT_MATCH' if exact_match else 'SEMANTIC_TARGET_MATCH'}\n"
                        f"operation: {op}\n"
                        f"document_id: {active_doc_id}\n"
                        f"final_target: {resolved_col}"
                    )

                    return SemanticExcelRequest(
                        operation=op,
                        target_column=resolved_col,
                        target_columns=[resolved_col],
                        target_concept=self.normalize_token(resolved_col),
                        source="ACTIVE_DOCUMENT",
                        output_format=out_fmt,
                        confidence=0.98,
                        raw_query=query_clean
                    )

        # 13. Check MAX / MIN
        for pat in self.OP_PATTERNS["MAX"]:
            if re.search(pat, query_clean, re.I):
                resolved_target = self.resolve_column("Amount", headers, concept_hint="amount")
                if not resolved_target and headers:
                    # Look for first numeric/amount candidate
                    for h in headers:
                        if any(k in h.lower() for k in ["amount", "qty", "quantity", "hours", "total", "score", "rate"]):
                            resolved_target = h
                            break
                return SemanticExcelRequest(
                    operation="MAX",
                    target_column=resolved_target or (headers[0] if headers else "Amount"),
                    target_concept="amount" if resolved_target and "amount" in resolved_target.lower() else "value",
                    source="ACTIVE_DOCUMENT",
                    output_format="METRIC_CARD",
                    confidence=0.98,
                    raw_query=query_clean
                )

        for pat in self.OP_PATTERNS["MIN"]:
            if re.search(pat, query_clean, re.I):
                resolved_target = self.resolve_column("Amount", headers, concept_hint="amount")
                if not resolved_target and headers:
                    for h in headers:
                        if any(k in h.lower() for k in ["amount", "qty", "quantity", "hours", "total", "score", "rate"]):
                            resolved_target = h
                            break
                return SemanticExcelRequest(
                    operation="MIN",
                    target_column=resolved_target or (headers[0] if headers else "Amount"),
                    target_concept="amount" if resolved_target and "amount" in resolved_target.lower() else "value",
                    source="ACTIVE_DOCUMENT",
                    output_format="METRIC_CARD",
                    confidence=0.98,
                    raw_query=query_clean
                )

        # 14. Check TOTAL
        for pat in self.OP_PATTERNS["TOTAL"]:
            if re.search(pat, query_clean, re.I):
                target_hint = "Settled_Amount" if re.search(r"\bsettled\b", query_clean, re.I) else "Amount"
                resolved_target = self.resolve_column(target_hint, headers, concept_hint="amount")
                if not resolved_target and headers:
                    for h in headers:
                        if any(k in h.lower() for k in ["amount", "qty", "quantity", "hours", "total", "score", "rate", "count"]):
                            resolved_target = h
                            break
                return SemanticExcelRequest(
                    operation="TOTAL",
                    target_column=resolved_target or (headers[0] if headers else target_hint),
                    target_concept="amount" if resolved_target and "amount" in resolved_target.lower() else "numeric",
                    source="ACTIVE_DOCUMENT",
                    output_format="METRIC_CARD",
                    confidence=0.98,
                    raw_query=query_clean
                )

        # 15. Check AVERAGE
        for pat in self.OP_PATTERNS["AVERAGE"]:
            if re.search(pat, query_clean, re.I):
                resolved_target = self.resolve_column("Amount", headers, concept_hint="amount")
                if not resolved_target and headers:
                    for h in headers:
                        if any(k in h.lower() for k in ["amount", "qty", "quantity", "hours", "rate", "score"]):
                            resolved_target = h
                            break
                return SemanticExcelRequest(
                    operation="AVERAGE",
                    target_column=resolved_target or (headers[0] if headers else "Amount"),
                    target_concept="amount" if resolved_target and "amount" in resolved_target.lower() else "numeric",
                    source="ACTIVE_DOCUMENT",
                    output_format="METRIC_CARD",
                    confidence=0.98,
                    raw_query=query_clean
                )

        # 16. Check COUNT
        for pat in self.OP_PATTERNS["COUNT"]:
            if re.search(pat, query_clean, re.I):
                resolved_target = self.resolve_column("Transaction ID", headers, concept_hint="id")
                if not resolved_target and headers:
                    for h in headers:
                        if any(k in h.lower() for k in ["id", "count", "number", "centre", "center", "ticket", "vle"]):
                            resolved_target = h
                            break
                return SemanticExcelRequest(
                    operation="COUNT",
                    target_column=resolved_target or (headers[0] if headers else "Record"),
                    target_concept="id",
                    source="ACTIVE_DOCUMENT",
                    output_format="METRIC_CARD",
                    confidence=0.98,
                    raw_query=query_clean
                )

        # 17. Unrecognized Query -> Return None so general NLU or Document Router handles it
        return None


# Global singleton instance
semantic_excel_resolver = SemanticExcelResolver()
