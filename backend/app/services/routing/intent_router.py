"""Hybrid Intent Router for Enterprise Multi-Department Company AI.

Analyzes natural language messages using pattern rules, domain heuristics, and entity
detection to produce a structured RoutingDecision (Department, Intent, Confidence, Tools).
Does NOT execute tools or retrieve documents directly.
"""

import re
from typing import Dict, Any, List, Tuple, Optional
from loguru import logger

from backend.app.schemas.department import DepartmentEnum, RoutingDecision, RouteRequest
from backend.app.departments.department_registry import department_registry
from backend.app.schemas.company_ai import ConversationState
from backend.app.services.conversation_context_manager import conversation_context_manager


class IntentRouter:
    """Enterprise Hybrid Intent & Department Router.
    Combines deterministic rules, regex patterns, domain lexicons, and confidence scoring.
    """

    def __init__(self):
        # 1. Deterministic Rule Patterns: (pattern_regex, department, intent, base_confidence)
        self._rule_patterns: List[Tuple[re.Pattern, DepartmentEnum, str, float]] = [
            # --- TECH RULES ---
            (
                re.compile(r"\b(wifi|wi-fi|ethernet|internet|network|dns|vpn|connectivity|offline|no internet)\b", re.I),
                DepartmentEnum.TECH,
                "troubleshooting",
                0.93
            ),
            (
                re.compile(r"\b(http\s*[45]\d{2}|status code\s*[45]\d{2}|500 internal|404 not found|exception|traceback|crash|segfault|runtime error|nullpointer)\b", re.I),
                DepartmentEnum.TECH,
                "error_diagnosis",
                0.95
            ),
            (
                re.compile(r"\b(error log|server log|access log|syslog|audit log|log analysis|analyze .*log|logs? file)\b", re.I),
                DepartmentEnum.TECH,
                "log_analysis",
                0.94
            ),
            (
                re.compile(r"\b(code review|refactor|pull request|git commit|syntax error|debug (this|my)? (code|script|function|query)|python|javascript|typescript|c\+\+|sql query|api endpoint|php api)\b", re.I),
                DepartmentEnum.TECH,
                "code_analysis",
                0.91
            ),
            (
                re.compile(r"\b(rca|root cause|incident report|post-mortem|outage|downtime|service disruption)\b", re.I),
                DepartmentEnum.TECH,
                "incident_report",
                0.92
            ),
            (
                re.compile(r"\b(laptop|desktop|monitor|keyboard|printer|mouse|os update|docker|kubernetes|aws|azure|database connection|server)\b", re.I),
                DepartmentEnum.TECH,
                "technical_question",
                0.86
            ),
            (
                re.compile(r"\b(issue in my project|problem in my project|issue with my project|project issue|trouble with my project|project error|project troubleshooting)\b", re.I),
                DepartmentEnum.TECH,
                "troubleshooting",
                0.97
            ),
            (
                re.compile(r"\b(typeerror|referenceerror|syntaxerror|cannot read propert(y|ies)|undefined|nullpointer|zerodivision|indexoutofbound)\b", re.I),
                DepartmentEnum.TECH,
                "error_diagnosis",
                0.98
            ),
            (
                re.compile(r"\b(node(\.js)?\s+(server|error|crash)|debug\s+my\s+node(\.js)?\s+error|debug\s+my\s+node)\b", re.I),
                DepartmentEnum.TECH,
                "error_diagnosis",
                0.98
            ),

            # --- EXCEL / CONTEXTUAL STATUS RULES ---
            (
                re.compile(
                    r"^(what\s+happened|why\s+did\s+it\s+fail|what\s+went\s+wrong|tell\s+me\s+what\s+happened)[.?!]?$",
                    re.I
                ),
                DepartmentEnum.GENERAL,
                "what_happened",
                0.99
            ),
            (
                re.compile(
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
                    re.I
                ),
                DepartmentEnum.GENERAL,
                "excel_full_export",
                0.99
            ),
            (
                re.compile(
                    r"^(give\s+(?:me\s+)?(?:(?:it|this|that|those|the\s+result|the\s+previous\s+result)\s+)?(?:as|in|to)\s+(?:an?\s+)?excel|"
                    r"give\s+(?:me\s+)?(?:this|that|those|it)\s+(?:as|in|to)\s+(?:an?\s+)?excel|"
                    r"(?:as|in|to)\s+(?:an?\s+)?excel|"
                    r"export\s+(?:this|that|it|these|those|the\s+result|the\s+previous\s+result)?(?:\s+as\s+excel)?|"
                    r"download\s+(?:this|that|it|the\s+result)?(?:\s+as\s+excel)?|"
                    r"make\s+it\s+excel)[.!]?$",
                    re.I
                ),
                DepartmentEnum.GENERAL,
                "excel_export_result",
                0.99
            ),
            (
                re.compile(
                    r"\b(names?\s+of\s+(?:the\s+)?(?:columns?|headings?|headers?)|"
                    r"(?:columns?|headings?|headers?)\s+names?|"
                    r"list\s+(?:the\s+|all\s+)?(?:columns?|headings?|headers?)|"
                    r"show\s+(?:me\s+)?(?:the\s+)?(?:columns?|headings?|headers?)|"
                    r"what\s+are\s+(?:the\s+)?(?:columns?|headings?|headers?)|"
                    r"(?:columns?|headings?|headers?)\s+list|"
                    r"give\s+(?:me\s+)?(?:the\s+)?(?:headings?|headers?|columns?)(?:\s+of\s+(?:the\s+)?(?:excel|file|doc|document|workbook|sheet))?|"
                    r"what\s+(?:columns?|headings?|headers?)\s+are\s+there|"
                    r"tell\s+me\s+(?:the\s+)?(?:excel\s+)?(?:column|heading|header)\s+names?|"
                    r"column\s+names\s+of\s+this\s+file)\b",
                    re.I
                ),
                DepartmentEnum.GENERAL,
                "excel_column_list",
                0.99
            ),
            (
                re.compile(
                    r"\b(highest\s+(?:transaction|amount|value|topup|payment)|"
                    r"biggest\s+(?:transaction|amount|value|topup|payment)|"
                    r"largest\s+(?:transaction|amount|value|topup|payment)|"
                    r"maximum\s+(?:transaction|amount|value|topup|payment)|"
                    r"which\s+(?:is\s+)?(?:the\s+)?(?:highest|biggest|largest|maximum)\s+(?:transaction|amount|value)|"
                    r"what\s+(?:is\s+)?(?:the\s+)?(?:highest|biggest|largest|maximum)\s+(?:transaction|amount|value)|"
                    r"(?:can\s+(?:you|u)\s+)?give\s+(?:me\s+)?(?:the\s+)?(?:highest|biggest|largest|maximum)\s+(?:transaction|amount|value)|"
                    r"max\s+(?:amount|transaction|value))\b",
                    re.I
                ),
                DepartmentEnum.GENERAL,
                "excel_max",
                0.99
            ),
            (
                re.compile(
                    r"\b(lowest\s+(?:transaction|amount|value|topup|payment)|"
                    r"smallest\s+(?:transaction|amount|value|topup|payment)|"
                    r"minimum\s+(?:transaction|amount|value|topup|payment)|"
                    r"which\s+(?:is\s+)?(?:the\s+)?(?:lowest|smallest|minimum)\s+(?:transaction|amount|value)|"
                    r"what\s+(?:is\s+)?(?:the\s+)?(?:lowest|smallest|minimum)\s+(?:transaction|amount|value)|"
                    r"(?:can\s+(?:you|u)\s+)?give\s+(?:me\s+)?(?:the\s+)?(?:lowest|smallest|minimum)\s+(?:transaction|amount|value)|"
                    r"min\s+(?:amount|transaction|value))\b",
                    re.I
                ),
                DepartmentEnum.GENERAL,
                "excel_min",
                0.99
            ),
            (
                re.compile(
                    r"\b(?:give\s+me\s+|extract\s+|export\s+)(?:the\s+|those\s+|all\s+)?(transaction\s+ids?|txn\s+ids?|rids?|unique\s+ids?|amounts?|statuses?|[a-zA-Z0-9_]+)\s+(?:as\s+(?:the\s+|an?\s+)?(?:excel|sheet|file|xlsx|csv)|to\s+excel|column)\b",
                    re.I
                ),
                DepartmentEnum.GENERAL,
                "excel_column_export",
                0.98
            ),
            (
                re.compile(
                    r"^(?=.*?\b(total\s+amount|sum\s+amount|how\s+much\s+money|total\s+settled|settled\s+amount|sum\s+the\s+amount|what\s+is\s+the\s+total(\s+amount)?|what('s|\s+is)\s+the\s+total|give\s+me\s+the\s+total|calculate\s+(?:the\s+)?total)\b)"
                    r"(?!.*?\b(expense|travel|trip|flight|hotel|reimbursement|per\s+diem|allowance|salary|payroll)\b).*",
                    re.I
                ),
                DepartmentEnum.GENERAL,
                "excel_total",
                0.99
            ),
            (
                re.compile(
                    r"\b(what('s|\s+is)\s+(the\s+)?average(\s+transaction)?(\s+amount)?|"
                    r"average\s+transaction\s+amount|average\s+amount|mean\s+transaction\s+amount|average\s+value)\b",
                    re.I
                ),
                DepartmentEnum.GENERAL,
                "excel_average",
                0.99
            ),
            (
                re.compile(
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
                    re.I
                ),
                DepartmentEnum.GENERAL,
                "excel_count",
                0.99
            ),
            (
                re.compile(
                    r"\b(how\s+many\s+qr(\s+transactions)?|qr\s+transactions?|how\s+many\s+upi(\s+transactions)?|upi\s+transactions?|"
                    r"show\s+me\s+transactions\s+above\s+\d+|transactions\s+above\s+\d+|transactions\s+>\s+\d+|"
                    r"filter\s+(by|for)\s+[a-z0-9]+)\b",
                    re.I
                ),
                DepartmentEnum.GENERAL,
                "excel_filter",
                0.98
            ),
            (
                re.compile(
                    r"\b(make\s+(a\s+)?(separate\s+|seprate\s+)*sprint|split\s+(this\s+|the\s+)?(sprint|excel|exel|spreadsheet|sheet|file)|"
                    r"separate\s+sprints?|seprate\s+sprints?|split\s+sprint|"
                    r"create\s+(a\s+|the\s+)?(separate\s+|seprate\s+)*(excel|exel|sprint|sheet|spreadsheet)?\s*(file|files|doc|document)?\s*(for|with|of|by)\b|"
                    r"create\s+(a\s+|the\s+)?(separate\s+|seprate\s+)*(excel|exel|sprint|sheet|spreadsheet)\s+(file|files)?|"
                    r"create\s+(a\s+|the\s+)?exel\s+file|"
                    r"create\s+one\s+for\s+[a-z0-9]+\s+and\s+one\s+for\s+[a-z0-9]+|"
                    r"split\s+this\s+for\s+[a-z0-9]+|"
                    r"give\s+me\s+separate\s+files?\s+for\s+[a-z0-9]+)\b",
                    re.I
                ),
                DepartmentEnum.GENERAL,
                "excel_split",
                0.99
            ),
            (
                re.compile(r"\b(give\s+me\s+a\s+(short\s+)?summary|sprint\s+summary|summarize\s+(the\s+|this\s+)?(sprint|excel|exel|sheet|tasks?|file|document|doc)|what\s+is\s+in\s+this\s+(sprint|excel|file|document)|sprint\s+overview|transaction\s+summary|summarize\s+[a-z0-9]+'?s?\s+sprint|give\s+(?:me\s+)?(?:the\s+)?full\s+summary|explain\s+(?:about\s+)?(?:this\s+|the\s+)?(?:document|doc|file)|what\s+is\s+this\s+(?:document|doc|file|presentation|pdf)|what\s+is\s+this\s+pdf\s+tells|what\s+about\s+(?:the\s+)?(?:previous\s+|earlier\s+)?(?:recruitment\s+)?(?:document|doc|file|report|manual|pdf|docx)|what\s+(?:does\s+|did\s+)?(?:the\s+)?(?:previous\s+|earlier\s+)?(?:recruitment\s+)?(?:document|doc|file|report|manual)\s+(?:say|contain|have|tell))\b", re.I),
                DepartmentEnum.GENERAL,
                "document_summary",
                0.98
            ),
            (
                re.compile(r"\b(give\s+me\s+a\s+report|generate\s+report|sprint\s+report|generate\s+sprint\s+report|excel\s+report|exel\s+report|transaction\s+report)\b", re.I),
                DepartmentEnum.GENERAL,
                "excel_report",
                0.98
            ),

            # --- FILE COMPARISON (FINANCE / DATA) ---
            (
                re.compile(r"\b(compare\s+(these\s+)?(two|2|both)?\s*(excel|spreadsheet|csv|sheets?|files?)|file comparison|compare excel|excel comparison|compare\s+[a-z0-9]+\s+and\s+[a-z0-9]+)\b", re.I),
                DepartmentEnum.FINANCE,
                "excel_comparison",
                0.99
            ),

            # --- HR RULES (DOCUMENT CREATION / EXPORT must come FIRST before policy_question) ---
            (
                re.compile(
                    r"\b(give me|create|make|prepare|generate|write|build|produce|draft)\b.{0,40}\b(excel|xlsx|\.xlsx|spreadsheet|csv)\b.{0,40}\b(leave|policy|hr|salary|employee|payroll|handbook)\b"
                    r"|\b(excel|xlsx|\.xlsx|spreadsheet)\b.{0,40}\b(leave|policy|hr|salary|employee|payroll|hr\s+report)\b",
                    re.I
                ),
                DepartmentEnum.HR,
                "document_export",
                0.98
            ),
            (
                re.compile(
                    r"\b(give me|create|make|prepare|generate|write|build|produce|draft)\b.{0,40}\b(word|docx|\.docx|doc)\b.{0,40}\b(document|file|policy|hr|letter)\b"
                    r"|\b(word|docx)\b.{0,40}\b(hr|policy|leave|employee)\b",
                    re.I
                ),
                DepartmentEnum.HR,
                "document_export",
                0.97
            ),
            (
                re.compile(
                    r"\b(create|make|prepare|generate|write|build|produce|draft|help me (make|create|write|prepare|draft|build|generate)|help with making|help with creating)\b.{0,50}\b(hr policy|hr document|company policy|policy document|leave policy document|hr manual|employee handbook|hr policy doc|policy doc|leave document|policy file)\b",
                    re.I
                ),
                DepartmentEnum.HR,
                "document_creation",
                0.97
            ),
            (
                re.compile(
                    r"\b(create|make|prepare|generate|write|build|produce|draft)\b.{0,50}\b(document|doc|file|template|form|report)\b.{0,50}\b(hr|policy|leave|employee|onboarding|appraisal|recruitment)\b",
                    re.I
                ),
                DepartmentEnum.HR,
                "document_creation",
                0.95
            ),
            (
                re.compile(r"\b(casual leave|sick leave|earned leave|maternity leave|paternity leave|leave policy|pto|vacation policy|holiday calendar|attendance policy|dress code|work from home policy|wfh policy|hr policy|company policy|posh policy)\b", re.I),
                DepartmentEnum.HR,
                "policy_question",
                0.96
            ),
            (
                re.compile(r"\b(offer letter|appointment letter|joining letter|employment contract|release letter|relieving letter)\b", re.I),
                DepartmentEnum.HR,
                "offer_letter",
                0.95
            ),
            # --- HR CANDIDATE / RESUME RULES ---
            (
                re.compile(r"\b(compare\s+(this|these|the|both|\d+)?\s*(two|2)?\s*resumes?|compare\s+(the\s+)?candidates?|which\s+(resume|candidate)\s+(is|matches|fits|is best|is better)\b.*(best|better|suitable|well|more|role|fit)|candidate\s+comparison|resume\s+comparison|compare\s+(the\s+)?two\s+candidates|evaluate\s+both\s+resumes|compare\s+.*\s+for\s+(the\s+)?([a-z\s]+)?\s*role|compare\s+candidates\s+from)\b", re.I),
                DepartmentEnum.HR,
                "candidate_comparison",
                0.99
            ),
            (
                re.compile(r"\b(is (she|he|the candidate|this candidate) fit|fit for (the |an? |this )?([a-z\s]+ )?role|role fit|role-fit|candidate suitability|candidate assessment|candidate screening|candidate strengths|strengths (for|of)?\s*(this|the)?\s*([a-z\s]+)?role)\b", re.I),
                DepartmentEnum.HR,
                "candidate_role_fit_analysis",
                0.98
            ),
            (
                re.compile(r"\b(what('s|\s+is)\s+(the\s+)?(work\s+|hr\s+|total\s+)?(experience|experince|background)\s*(of\s+(this\s+|the\s+)?candidate)?|how much (work |hr )?(experience|experince) (does )?(she|he|they|the candidate|this candidate)?\s*(have|has)?|(her|his|their|the\s+candidate'?s?|this\s+candidate'?s?)\s+(work\s+|hr\s+|total\s+)?(experience|experince)|what (hr|work)?\s*(experience|experince) (does )?(she|he|they|the candidate|this candidate)?\s*(have|has)?|years of (experience|experince)|how many years (of (experience|experince))?|(what|which) companies did (she|he|they|the candidate|this candidate) work for|work history|career history|employment history|does (she|he|the candidate|this candidate) have (recruitment|sourcing|talent acquisition|hr|hiring) experience|(experience|experince)\s*(details?|\?)?)\b", re.I),
                DepartmentEnum.HR,
                "candidate_experience",
                0.98
            ),
            (
                re.compile(r"\b(what('s|\s+is)\s+(the\s+)?(key\s+|core\s+|technical\s+|hr\s+)?skills\s*(of\s+(this\s+|the\s+)?candidate|\?)?|what are (her|his|their|the\s+candidate'?s?|this\s+candidate'?s?)\s+(key\s+|core\s+|technical\s+|hr\s+)?skills|what skills (does )?(she|he|they|the candidate|this candidate) (have|possess)|(her|his|their|the\s+candidate'?s?|this\s+candidate'?s?)\s+skills|candidate skills|core competencies|technical skills|hr skills|skills\?|tools (she|he|the candidate) (knows|uses)|what about (his|her|their|the candidate'?s?) (certifications?|skills)|certifications?\?|what certifications?)\b", re.I),
                DepartmentEnum.HR,
                "candidate_skills",
                0.98
            ),
            (
                re.compile(r"\b(what('s|\s+is)\s+(the\s+)?(educational?\s+(details?|background|qualifications?)|education|academics?|degrees?)\s*(of\s+(this\s+|the\s+)?candidate)?|what is (her|his|their|the\s+candidate'?s?|this\s+candidate'?s?)\s+(education|educational details?|qualifications?)|(her|his|their|the\s+candidate'?s?|this\s+candidate'?s?)\s+(education|educational details?|academics?|degrees?|qualifications?|college|university)|educational background|educational details?|candidate qualification|candidate degrees?|candidate certifications?|where did (she|he|they|the candidate|this candidate) study)\b", re.I),
                DepartmentEnum.HR,
                "candidate_education",
                0.98
            ),
            (
                re.compile(r"\b(give (me\s+)?(her|his|their|the\s+candidate'?s?|this\s+candidate'?s?)\s+(professional\s+)?summary|give (the\s+|a\s+)?summary of (this\s+|the\s+)?(resume|candidate)|(her|his|candidate'?s?|this\s+candidate'?s?)\s+(profile|bio|overview|background)|tell me about (her|him|this candidate|the candidate)|professional summary of (the candidate|this candidate|her|him))\b", re.I),
                DepartmentEnum.HR,
                "candidate_summary",
                0.98
            ),
            (
                re.compile(r"\b(find candidates?|search candidates?|shortlist|matching (this|the) (job|jd|role|profile)|resume screening|candidate pool|sourcing)\b", re.I),
                DepartmentEnum.HR,
                "candidate_search",
                0.94
            ),
            (
                re.compile(r"\b(interview questions?|interview script|technical interview|screening questions?|interview assessment)\b", re.I),
                DepartmentEnum.HR,
                "interview_questions",
                0.93
            ),
            (
                re.compile(r"\b(recruitment|hire|hiring pipeline|talent acquisition|open positions?|job opening|job description|ats)\b", re.I),
                DepartmentEnum.HR,
                "recruitment",
                0.90
            ),
            (
                re.compile(r"\b(employee info|employee details|employee directory|contact info for|reporting manager|employee id|emp code|work anniversary|onboarding status)\b", re.I),
                DepartmentEnum.HR,
                "employee_information",
                0.91
            ),
            (
                re.compile(r"\b(employee handbook|hr document|handbook|appraisal form|nda form)\b", re.I),
                DepartmentEnum.HR,
                "hr_document",
                0.89
            ),

            # --- FINANCE RULES ---
            (
                re.compile(r"\b(calculate|compute|what is|sum of|add up|add)\b.*\d+.*[\+\-\*\/].*\d+", re.I),
                DepartmentEnum.FINANCE,
                "expense_calculation",
                0.98
            ),
            (
                re.compile(r"^\s*(\$?\d+(?:\.\d+)?\s*[\+\-\*\/]\s*)+\$?\d+(?:\.\d+)?\.?\s*$", re.I),
                DepartmentEnum.FINANCE,
                "expense_calculation",
                0.98
            ),
            (
                re.compile(r"\b(calculate (total )?(travel )?expenses?|sum of expenses?|total (cost|amount|bill|spend|expenditure)|calculate .*expenses?|add up .*expenses?)\b", re.I),
                DepartmentEnum.FINANCE,
                "expense_calculation",
                0.96
            ),
            (
                re.compile(r"\b(expense report|travel expense|monthly expense|reimbursement report|claim report|expense summary|generate .*expense report)\b", re.I),
                DepartmentEnum.FINANCE,
                "expense_report",
                0.95
            ),
            (
                re.compile(r"\b(invoice|bill extraction|vendor invoice|extract .*invoice|invoice details|tax invoice|receipt extraction|gst invoice)\b", re.I),
                DepartmentEnum.FINANCE,
                "invoice",
                0.94
            ),
            (
                re.compile(r"\b(budget analysis|budget variance|quarterly budget|capex|opex|fiscal year|financial forecast|p&l|profit and loss|ebitda)\b", re.I),
                DepartmentEnum.FINANCE,
                "budget_analysis",
                0.92
            ),
            (
                re.compile(r"\b(financial statement|balance sheet|audit report|tds certificate|tax report|generate .*financial document|excel expense)\b", re.I),
                DepartmentEnum.FINANCE,
                "financial_document",
                0.91
            ),
            (
                re.compile(r"\b(compare\s+(these\s+)?(two|2|both)?\s*(invoices?|excel|spreadsheet|csv|sheets?|files?)|file comparison|compare excel|excel comparison|compare these two invoices|what are (the\s+)?mismatches|mismatch report|show mismatches)\b", re.I),
                DepartmentEnum.FINANCE,
                "file_comparison",
                0.98
            ),
            (
                re.compile(r"\b(payroll|salary slip|tax deduction|tds|gst rate|per diem|allowance limit)\b", re.I),
                DepartmentEnum.FINANCE,
                "financial_question",
                0.88
            ),

            # --- GENERAL RULES ---
            (
                re.compile(r"^(hi|hello|hey|greetings|good\s+(morning|afternoon|evening))\b[\!\.\?]?\s*$", re.I),
                DepartmentEnum.GENERAL,
                "greeting",
                0.98
            ),
            (
                re.compile(r"^(what can you do|who are you|help|capabilities|what are your capabilities)\b", re.I),
                DepartmentEnum.GENERAL,
                "general_question",
                0.92
            )
        ]

        # 2. Domain Keyword Lexicons for Secondary Scoring
        self._domain_lexicons: Dict[DepartmentEnum, List[str]] = {
            DepartmentEnum.TECH: [
                "laptop", "wifi", "internet", "server", "linux", "windows", "macos",
                "database", "sql", "git", "api", "docker", "code", "bug", "crash",
                "error", "log", "logs", "http", "port", "network", "ssh", "cloud",
                "terminal", "cpu", "ram", "disk", "proxy", "vpn", "firewall", "router"
            ],
            DepartmentEnum.HR: [
                "leave", "casual", "sick", "earned", "maternity", "paternity", "policy",
                "candidate", "resume", "recruitment", "interview", "offer", "letter",
                "employee", "onboarding", "hr", "benefits", "insurance", "notice",
                "resignation", "handbook", "attendance", "probation", "appraisal"
            ],
            DepartmentEnum.FINANCE: [
                "expense", "expenses", "invoice", "invoices", "budget", "cost", "bill",
                "finance", "financial", "accounting", "tax", "tds", "gst", "receipt",
                "reimbursement", "vendor", "travel", "dollars", "amount", "total",
                "audit", "balance", "ledger", "payout", "payment", "revenue"
            ]
        }

    def is_follow_up(self, text: str) -> bool:
        """Determines whether a message is a contextual follow-up to a previous question."""
        text_lower = text.lower().strip()
        follow_up_patterns = [
            r"\b(more detail(s|ed)?|give me more|tell me more|can (u|you) give me more|can (u|you) explain (more|that|further)|explain (more|that|further)|elaborate|can (u|you) elaborate|details? please|give more details?|tell me details?)\b",
            r"\b(what about|how about|why is that|and for|how many|what else|anything else|what if|who handles that|where do i send)\b",
            r"^(more\s+details?|details?|explain|elaborate|give\s+more|more|can\s+you\s+give\s+more|detailed|can\s+u\s+give\s+me\s+more\s+detailed)\b",
            r"^(next|continue|proceed|start|go on|move on|step by step|one by one)[.!]?$",
            r"\b(give\s+me\s+(the\s+)?(files?|code|artifacts?)|show\s+me\s+(the\s+)?(files?|code)|give\s+files?|get\s+files?)\b",
            r"\b(one\s+by\s+one|step\s+by\s+step|file\s+by\s+file)\b",
            r"\b(what\s+comes\s+(after\s+this|next)|what\s+is\s+next|what'?s\s+next|next\s+step|next\s+stage|next\s+file)\b",
            r"\b(give\s+me\s+(the\s+)?flow|show\s+the\s+flow|explain\s+the\s+flow|continue\s+the\s+flow|continue\s+(this|the)\s+workflow)\b",
            r"^(this|that|it|this\s+one|that\s+one|same|same\s+one|previous|above|the\s+above)[.!]?$",
            r"\b(continue\s+from\s+(here|current|this|the\s+current\s+stage)|continue\s+(this|the)\s+(task|implementation|process|project))\b",
            r"\b(explain\s+(the\s+)?(approval|stock|procurement|po|grn|outward|logistics|dispatch|receipt|reconciliation|finance|closure))\b",
        ]
        for pat in follow_up_patterns:
            if re.search(pat, text_lower):
                return True
        return False

    # --- Informal language patterns that signal NLP is needed ---
    _INFORMAL_TOKENS = re.compile(
        r"\b(u\b|ur\b|bro\b|yo\b|gonna|wanna|gimme|gotta|asap|plz|pls|thx|btw|fyi|lol|"
        r"dunno|nah|yep|yup|lemme|cmon|c'mon|heya|bruh|dude|mate|kinda|sorta|prolly|"
        r"hafta|oughta|shoulda|woulda|coulda|innit|ain't|won't|can't u|can u|"
        r"lmk|tbh|imo|imho|smh|idk|ngl)\b",
        re.I
    )
    _MULTI_ACTION = re.compile(
        r"\b(and (also|then|also then)|as well as|plus also|and (then )?make|"
        r"and (then )?send|and (then )?export|and (then )?create|"
        r"check .{3,40} and .{3,40} make|compare .{3,60} report)\b",
        re.I
    )
    _MULTI_FILE = re.compile(
        r"\b(two|2|both|multiple|compare|versus|vs\.?|difference between|diff between)\b"
        r".{0,40}\b(file|excel|spreadsheet|sheet|doc|document|report)\b",
        re.I
    )

    def needs_nlp_understanding(
        self,
        message: str,
        route_decision,
        context_state: Optional[ConversationState] = None
    ) -> bool:
        """Determines whether Qwen Layer 1 semantic understanding is required.

        Layer 1 is reserved ONLY for complex requests requiring MYGPT orchestration:
          - Excel / spreadsheet operations
          - Document / PDF operations
          - Coding, debugging, and refactoring requests
          - Vision / image understanding
          - Multi-step tasks and system-building requests
          - Tool execution and data comparison
          - Tasks referencing active documents or context-dependent files

        Simple general conversational questions, explanations, math expressions, and greetings
        do NOT require Layer 1, allowing MYGPT to answer them in a single direct LLM pass.
        """
        intent = getattr(route_decision, "intent", "unknown")
        msg_clean = message.strip().lower()
        words = msg_clean.split()

        # 1. Fast-path: trivial short greetings (<= 3 words)
        if intent == "greeting" and len(words) <= 3:
            return False

        # 2. Fast-path: pure standalone arithmetic / math expressions (e.g. "Calculate 25 * 40", "500 + 250")
        if re.search(r"(\bcalculate\b|\bsolve\b|\d+(\.\d+)?\s*%\s*of\s*\d+(\.\d+)?|^\s*(\$|€|£|₹|Rs\.?)?\s*\d+(?:\.\d+)?\s*(?:[\+\-\*\/]\s*(\$|€|£|₹|Rs\.?)?\s*\d+(?:\.\d+)?\s*)+\.?\s*$)", msg_clean):
            return False

        # 3. Fast-path: general definition and knowledge questions ("what is PHP?", "what is Python?", "explain JWT", "what is the capital of Japan?")
        # unless it explicitly references an active document, spreadsheet, or code file
        if re.match(r"^(what\s+is|what\s+are|who\s+is|explain\s+|tell\s+me\s+about\s+|define\s+)\b", msg_clean):
            if not any(w in msg_clean for w in ["this file", "this document", "this excel", "this sheet", "this code", "this error", "this bug", "this screenshot", "attached", "uploaded"]):
                return False

        # 4. Fast-path: simple confirmation when pending action exists
        if context_state and context_state.pending_action and msg_clean in ("yes", "yeah", "yep", "sure", "ok", "okay", "proceed", "confirm"):
            return False

        # 5. Fast-path: clarification selection reply ("1", "2", "option 2", "second one")
        if context_state and context_state.pending_clarification:
            sel_col, _ = conversation_context_manager.resolve_clarification_selection(message, context_state.pending_clarification)
            if sel_col:
                return False

        # 5b. Fast-path: active Tender upload/follow-up bypasses redundant Layer 1 round-trip
        if context_state and str(getattr(context_state, "active_document_type", "") or "").upper() == "TENDER":
            return False

        # 6. Check for Complex Orchestration Triggers (Only these need Layer 1)
        # 6a. Active document context inquiry/manipulation
        has_active_doc = bool(context_state and (getattr(context_state, "active_document", None) or getattr(context_state, "active_document_name", None)))
        if has_active_doc and any(w in msg_clean for w in ["document", "file", "sheet", "pdf", "table", "summary", "summarize", "column", "section", "this", "it", "above"]):
            return True

        # 6b. Excel / Spreadsheet operations
        if intent.startswith("excel_") or re.search(r"\b(excel|sheet|spreadsheet|csv|column|columns|row|rows|filter|sum|total|average|count|unique|min|max|formula|workbook|worksheet)\b", msg_clean):
            return True

        # 6c. Document / PDF / Resume operations
        if intent.startswith("document_") or re.search(r"\b(pdf|document|docx|word|resume|cv|invoice|contract|handbook|section|clause|page|pages)\b", msg_clean):
            return True

        # 6d. Coding, debugging, and software engineering tasks (fixing code, reviewing code, writing functions)
        if intent in ("code_generation", "coding_debug", "code_review", "code_analysis") or re.search(r"\b(fix\s+(?:this\s+)?code|debug\s+(?:this\s+)?code|write\s+(?:a\s+)?(?:script|function|class|query)|syntax\s*error|stack\s*trace|typeerror|refactor\s+code|codeigniter\s+controller)\b", msg_clean):
            return True

        # 6e. Vision & image understanding
        if intent in ("vision", "vision_analysis", "image_understanding") or re.search(r"\b(image|screenshot|photo|picture|diagram|chart|png|jpg|jpeg)\b", msg_clean):
            return True

        # 6f. System planning / architectural building requests
        if intent == "project_planning" or re.search(r"\b(build|create|develop)\s+(?:me\s+)?(?:a\s+)?(?:new\s+)?(?:web\s+)?(?:application|app|system|platform|portal)\b", msg_clean):
            return True

        # 6g. Explicit tool execution, file comparisons, or exports
        if re.search(r"\b(compare|difference|mismatch|export\s+to|download|convert)\b", msg_clean):
            return True

        # All other queries are simple general questions / explanations / conversations
        # -> Do NOT run Layer 1. Route directly to general answer generation.
        return False

    def route(
        self,
        request: RouteRequest,
        history: Optional[List[Dict[str, Any]]] = None,
        context_state: Optional[ConversationState] = None
    ) -> RoutingDecision:
        """Determines target department, specific intent, required tools, and permission level."""
        text = request.message.strip()
        if not text:
            return self._build_decision(
                dept=DepartmentEnum.GENERAL,
                intent="unknown",
                confidence=0.0,
                entities={"reason": "empty_input"}
            )

        # 0. Check for Direct Conversational Greeting (Trivial greetings must never trigger document operations)
        if re.match(r"^(hi|hello|hey|greetings|good\s+(morning|afternoon|evening))\b[\!\.\?]?\s*$", text, re.I):
            return self._build_decision(
                dept=DepartmentEnum.GENERAL,
                intent="greeting",
                confidence=0.99,
                entities={"greeting": True}
            )

        # 1. Check for Explicit Department Declaration ("I'm from tech department", "HR team here")
        declared_dept = conversation_context_manager.detect_department_declaration(text)
        if declared_dept:
            if len(text.split()) <= 7:
                return self._build_decision(
                    dept=declared_dept,
                    intent="department_declaration",
                    confidence=0.99,
                    entities={"declared_dept": declared_dept.value}
                )

        # 2. Check for Follow-Up Signals from Conversation State
        if context_state:
            signals = conversation_context_manager.resolve_follow_up_signals(text, context_state)
            if signals["is_follow_up"]:
                sig_type = signals.get("signal_type")
                target_act = signals.get("target_action")

                # 2_0. Clarification Selection reply ("1", "2", "option 2", "Count of ExamCentre")
                if sig_type == "clarification_selection":
                    resumed_intent = str(target_act or "excel_read_column").lower()
                    if not resumed_intent.startswith("excel_") and str(context_state.active_document_type).upper() in ("EXCEL", "EXCEL_WORKBOOK", "SPREADSHEET"):
                        resumed_intent = f"excel_{resumed_intent}"
                    logger.info(f"Route: Clarification selection '{text}' resolved column '{signals['entities'].get('selected_column')}' -> {resumed_intent}")
                    return self._build_decision(
                        dept=DepartmentEnum.GENERAL,
                        intent=resumed_intent,
                        confidence=0.99,
                        entities=signals.get("entities", {})
                    )

                # 2a. Confirmation ("yes", "sure", "ok") continuing a pending action
                if sig_type == "confirmation" and context_state.pending_action:
                    dept = DepartmentEnum(context_state.last_department) if context_state.last_department else DepartmentEnum.TECH
                    intent = context_state.last_intent or "troubleshooting"
                    logger.info(f"Route: Confirmation '{text}' mapped to pending action '{context_state.pending_action}' in {dept.value}")
                    return self._build_decision(
                        dept=dept,
                        intent=intent,
                        confidence=0.98,
                        entities={"is_follow_up": True, "action": "CONFIRM", "pending_action": context_state.pending_action}
                    )

                # 2_task. Task / Workflow / Step Continuation ("next", "give me the files", "step by step", "this one")
                if sig_type in ("task_continuation", "workflow_continuation", "step_continuation"):
                    dept_str = context_state.department or context_state.last_department or DepartmentEnum.TECH.value
                    try:
                        dept = DepartmentEnum(dept_str)
                    except ValueError:
                        dept = DepartmentEnum.TECH
                    intent = context_state.last_intent or "code_generation"
                    logger.info(f"Route: Task continuation '{text}' continuing {dept.value} / {intent} (task={getattr(context_state, 'task', None)}, topic={getattr(context_state, 'topic', None) or context_state.last_topic})")
                    entities = dict(signals.get("entities", {}))
                    entities.update({
                        "is_follow_up": True,
                        "action": "CONTINUE",
                        "topic": getattr(context_state, "topic", None) or context_state.last_topic,
                        "project": getattr(context_state, "project", None),
                        "task": getattr(context_state, "task", None),
                        "workflow": getattr(context_state, "workflow", None),
                        "current_module": getattr(context_state, "current_module", None),
                        "current_stage": getattr(context_state, "current_stage", None),
                        "conversation_mode": "continuation"
                    })
                    return self._build_decision(
                        dept=dept,
                        intent=intent,
                        confidence=0.99,
                        entities=entities
                    )

                # 2b. Detail expansion ("give me in detail", "explain more")
                if sig_type == "expansion" and context_state.last_department:
                    dept = DepartmentEnum(context_state.last_department)
                    intent = context_state.last_intent or "policy_question"
                    logger.info(f"Route: Detail expansion '{text}' inherited {dept.value} / {intent}")
                    return self._build_decision(
                        dept=dept,
                        intent=intent,
                        confidence=0.98,
                        entities={"is_follow_up": True, "action": "EXPAND", "topic": context_state.last_topic}
                    )

                # 2ca. Candidate Comparison Follow-up ("who is best?", "which candidate is better?", "why?", "give me more details", "give me the comparison in Excel")
                if sig_type == "candidate_comparison":
                    logger.info(f"Route: Candidate comparison follow-up '{text}' -> HR / candidate_comparison")
                    return self._build_decision(
                        dept=DepartmentEnum.HR,
                        intent="candidate_comparison",
                        confidence=0.99,
                        entities=signals.get("entities", {})
                    )

                # 2c. Candidate / Resume Inquiry on active document
                if sig_type == "candidate_inquiry":
                    target_action = str(target_act or "").upper()
                    if "ROLE_FIT" in target_action or "FIT" in target_action:
                        intent = "candidate_role_fit_analysis"
                    elif "EXPERIENCE" in target_action or "WORK" in target_action:
                        intent = "candidate_experience"
                    elif "SKILL" in target_action:
                        intent = "candidate_skills"
                    elif "EDUCATION" in target_action or "DEGREE" in target_action:
                        intent = "candidate_education"
                    elif "SUMMARY" in target_action or "PROFILE" in target_action:
                        intent = "candidate_summary"
                    else:
                        intent = "candidate_role_fit_analysis"

                    doc_name = signals["entities"].get("filename") or context_state.active_document_name
                    doc_id = signals["entities"].get("doc_id") or context_state.active_document_id
                    logger.info(f"Route: Candidate inquiry '{text}' -> HR / {intent} referencing '{doc_name}'")
                    return self._build_decision(
                        dept=DepartmentEnum.HR,
                        intent=intent,
                        confidence=0.98,
                        entities={
                            "is_follow_up": True,
                            "action": target_action,
                            "referenced_previous_document": doc_name,
                            "active_doc_id": doc_id,
                            "doc_id": doc_id,
                            "filename": doc_name,
                            "topic": context_state.last_topic or "candidate qualification"
                        }
                    )

                # 2w. Contextual Explanation ("what happened", "why did it fail")
                if sig_type == "contextual_explanation":
                    doc_name = signals["entities"].get("filename") or context_state.active_document_name or "uploaded document"
                    logger.info(f"Route: Contextual explanation '{text}' -> GENERAL / what_happened referencing '{doc_name}'")
                    return self._build_decision(
                        dept=DepartmentEnum.GENERAL,
                        intent="what_happened",
                        confidence=0.99,
                        entities={
                            "is_follow_up": True,
                            "action": "EXPLAIN_STATUS",
                            "active_doc": doc_name,
                            "filename": doc_name,
                            "topic": "Contextual status explanation"
                        }
                    )

                # 2x. Excel Document Operations (total, average, count, min, max, filter, summary, report, split, comparison, export, full_export)
                if sig_type == "excel_operation":
                    target_action = str(target_act or "").upper()
                    if target_action in ("EXCEL_MULTI_DOCUMENT_SUMMARY", "MULTI_DOCUMENT_SUMMARY"):
                        intent = "excel_multi_document_summary"
                    elif target_action in ("EXCEL_UNIQUE_VALUES", "UNIQUE_VALUES"):
                        intent = "excel_unique_values"
                    elif target_action in ("EXCEL_FULL_EXPORT", "FULL_EXPORT"):
                        intent = "excel_full_export"
                    elif target_action in ("EXCEL_COLUMN_LIST", "COLUMN_LIST"):
                        intent = "excel_column_list"
                    elif target_action in ("EXCEL_COLUMN_EXPORT", "COLUMN_EXPORT"):
                        intent = "excel_column_export"
                    elif target_action in ("EXCEL_COMPARE", "EXCEL_COMPARISON", "COMPARE"):
                        intent = "excel_compare"
                    elif target_action in ("EXCEL_TOTAL", "TOTAL"):
                        intent = "excel_total"
                    elif target_action in ("EXCEL_AVERAGE", "AVERAGE", "AVG"):
                        intent = "excel_average"
                    elif target_action in ("EXCEL_COUNT", "COUNT"):
                        intent = "excel_count"
                    elif target_action in ("EXCEL_GROUP_MAX", "GROUP_MAX"):
                        intent = "excel_group_max"
                    elif target_action in ("EXCEL_GROUP_MIN", "GROUP_MIN"):
                        intent = "excel_group_min"
                    elif target_action in ("EXCEL_MIN", "MIN"):
                        intent = "excel_min"
                    elif target_action in ("EXCEL_MAX", "MAX"):
                        intent = "excel_max"
                    elif target_action in ("EXCEL_SPLIT", "SPLIT"):
                        intent = "excel_split"
                    elif target_action in ("EXCEL_FILTER_EXPORT", "FILTER_EXPORT"):
                        intent = "excel_filter_export"
                    elif target_action in ("EXCEL_FILTER_COLUMN", "FILTER_COLUMN"):
                        intent = "excel_filter_column"
                    elif target_action in ("EXCEL_FILTER_COLUMN_EXPORT", "FILTER_COLUMN_EXPORT"):
                        intent = "excel_filter_column_export"
                    elif target_action in ("EXCEL_READ_COLUMN", "READ_COLUMN"):
                        intent = "excel_read_column"
                    elif target_action in ("EXCEL_READ_SHEET", "READ_SHEET", "SHEET_INSPECTION", "EXCEL_SHEET_INSPECTION"):
                        intent = "excel_read_sheet"
                    elif target_action in ("EXCEL_CLARIFICATION", "CLARIFICATION"):
                        intent = "excel_clarification"
                    elif target_action and str(target_action).lower().startswith("excel_"):
                        intent = str(target_action).lower()
                    else:
                        intent = "excel_clarification"

                    doc_name = signals["entities"].get("filename") or context_state.active_document_name
                    doc_id = signals["entities"].get("doc_id") or context_state.active_document_id
                    target_owners = signals["entities"].get("target_owners", [])
                    target_col = signals["entities"].get("target_column")
                    filter_spec = signals["entities"].get("filter")
                    filters_list = signals["entities"].get("filters") or filter_spec
                    
                    dept = (
                        DepartmentEnum(context_state.department) if context_state.department and context_state.department in DepartmentEnum._value2member_map_
                        else (DepartmentEnum(context_state.last_department) if context_state.last_department and context_state.last_department in DepartmentEnum._value2member_map_
                        else DepartmentEnum.GENERAL)
                    )
                    
                    logger.info(f"Route: Excel operation '{text}' -> {dept.value} / {intent} (column={target_col}, filter={filter_spec}, owners={target_owners}) referencing '{doc_name}'")
                    return self._build_decision(
                        dept=dept,
                        intent=intent,
                        confidence=0.99,
                        entities={
                            "is_follow_up": True,
                            "action": target_action,
                            "operation": "FILTER_AND_EXPORT" if intent in ("excel_split", "excel_filter") and target_owners else target_action,
                            "source": "active_document",
                            "column": target_col or ("Owner" if target_owners else "Amount"),
                            "target_column": target_col,
                            "target_columns": signals["entities"].get("target_columns"),
                            "target_concept": signals["entities"].get("target_concept"),
                            "output_format": signals["entities"].get("output_format"),
                            "filter": filter_spec or filters_list,
                            "filters": filters_list,
                            "pending_operation": (filters_list.get("pending_operation") if isinstance(filters_list, dict) else None),
                            "sections": signals["entities"].get("sections"),
                            "follow_up_action": signals["entities"].get("follow_up_action"),
                            "clarification_message": signals["entities"].get("clarification_message"),
                            "values": target_owners,
                            "target_owners": target_owners,
                            "last_exportable_rows": signals["entities"].get("last_exportable_rows"),
                            "last_target_columns": signals["entities"].get("last_target_columns"),
                            "last_exportable_result": signals["entities"].get("last_exportable_result"),
                            "referenced_previous_document": doc_name,
                            "active_doc_id": doc_id,
                            "doc_id": doc_id,
                            "document_id": doc_id,
                            "filename": doc_name,
                            "raw_query": text,
                            "message": text,
                            "doc_id_a": signals["entities"].get("doc_id_a"),
                            "doc_id_b": signals["entities"].get("doc_id_b"),
                            "filename_a": signals["entities"].get("filename_a"),
                            "filename_b": signals["entities"].get("filename_b"),
                            "_multi_doc_summary": signals["entities"].get("_multi_doc_summary"),
                            "_comparison_result": signals["entities"].get("_comparison_result"),
                            "selected_document_ids": signals["entities"].get("selected_document_ids", []),
                            "topic": context_state.last_topic or "Excel Analysis"
                        }
                    )

                # 2d. Document summary ("give me a summary of this report", "summarize this")
                if sig_type == "document_summary":
                    if context_state.active_document:
                        doc_type = str(context_state.active_document_type or context_state.active_document.get("document_type", "")).upper()
                        if doc_type in ("RESUME", "HR_POLICY", "OFFER_LETTER_TEMPLATE", "OFFER_LETTER") or any(k in str(context_state.active_document_name).lower() for k in ["hr", "ops", "resume", "cv"]):
                            dept = DepartmentEnum.HR
                        elif doc_type in ("INVOICE", "EXPENSE_REPORT") or any(k in str(context_state.active_document_name).lower() for k in ["inv", "expense", "bill", "receipt"]):
                            dept = DepartmentEnum.FINANCE
                        elif context_state.last_department:
                            dept = DepartmentEnum(context_state.last_department)
                        else:
                            dept = DepartmentEnum.HR if any(k in text.lower() for k in ["leave", "policy", "resume", "candidate"]) else (
                                DepartmentEnum.HR if str(context_state.active_document_type).upper() == "RESUME" else DepartmentEnum.GENERAL
                            )
                    elif context_state.last_department:
                        dept = DepartmentEnum(context_state.last_department)
                    else:
                        dept = DepartmentEnum.GENERAL

                    if dept == DepartmentEnum.FINANCE:
                        intent = "expense_report_summary" if "expense" in str(context_state.last_intent or "").lower() or "expense" in str(context_state.last_topic or "").lower() else "document_summary"
                    else:
                        intent = "document_summary"
                    ref_doc = signals["entities"].get("referenced_file") or context_state.last_generated_file or context_state.active_document_name
                    logger.info(f"Route: Document summary '{text}' -> {dept.value} / {intent} referencing '{ref_doc}'")
                    return self._build_decision(
                        dept=dept,
                        intent=intent,
                        confidence=0.98,
                        entities={
                            "is_follow_up": True,
                            "action": "SUMMARIZE",
                            "referenced_previous_document": ref_doc,
                            "active_doc_id": context_state.active_document_id,
                            "topic": context_state.last_topic
                        }
                    )

                # 2d_tf. Document Transformation / Flowchart / Workflow on active document ("give me a flow chart", "blueprint", "show me the workflow")
                if sig_type == "document_transformation":
                    ref_doc = signals["entities"].get("referenced_file") or context_state.active_document_name or "uploaded document"
                    doc_id = signals["entities"].get("doc_id") or context_state.active_document_id
                    logger.info(f"Route: Document Transformation '{text}' -> GENERAL / document_transformation referencing '{ref_doc}'")
                    return self._build_decision(
                        dept=DepartmentEnum.GENERAL,
                        intent="document_transformation",
                        confidence=0.98,
                        entities={
                            "is_follow_up": True,
                            "action": "DOCUMENT_TRANSFORMATION",
                            "operation": "DOCUMENT_TRANSFORMATION",
                            "output_format": signals["entities"].get("output_format") or "FLOWCHART",
                            "referenced_previous_document": ref_doc,
                            "active_doc_id": doc_id,
                            "doc_id": doc_id,
                            "filename": ref_doc,
                            "query": text,
                            "topic": signals["entities"].get("topic") or "Workflow Process Blueprint"
                        }
                    )

                # 2d_exp. Document Export to Excel / Spreadsheet on active document ("give me that in Excel", "export this as Excel")
                if sig_type == "document_export":
                    ref_doc = signals["entities"].get("referenced_file") or context_state.active_document_name or "uploaded document"
                    doc_id = signals["entities"].get("doc_id") or context_state.active_document_id
                    doc_type = str(context_state.active_document_type or "").upper()
                    dept = DepartmentEnum.HR if doc_type == "RESUME" else DepartmentEnum.GENERAL
                    logger.info(f"Route: Document Export '{text}' -> {dept.value} / document_export referencing '{ref_doc}'")
                    return self._build_decision(
                        dept=dept,
                        intent="document_export",
                        confidence=0.98,
                        entities={
                            "is_follow_up": True,
                            "action": "EXPORT_RESULT",
                            "operation": "EXPORT_RESULT",
                            "output_format": "XLSX",
                            "referenced_previous_document": ref_doc,
                            "active_doc_id": doc_id,
                            "doc_id": doc_id,
                            "filename": ref_doc,
                            "query": text,
                            "topic": "Document Export"
                        }
                    )

                # 2d_qa. Document QA / Information Extraction on active document ("what are the bugs", "what are the difficulties", "explain screenshot 3")
                if sig_type == "document_qa":
                    ref_doc = signals["entities"].get("referenced_file") or context_state.active_document_name or "uploaded document"
                    doc_id = signals["entities"].get("doc_id") or context_state.active_document_id
                    logger.info(f"Route: Document QA '{text}' -> GENERAL / document_qa referencing '{ref_doc}'")
                    return self._build_decision(
                        dept=DepartmentEnum.GENERAL,
                        intent="document_qa",
                        confidence=0.98,
                        entities={
                            "is_follow_up": True,
                            "action": "EXTRACT_INFORMATION",
                            "referenced_previous_document": ref_doc,
                            "active_doc_id": doc_id,
                            "doc_id": doc_id,
                            "filename": ref_doc,
                            "query": text,
                            "topic": signals["entities"].get("topic") or text
                        }
                    )

                # 2d. Invoice Inquiry on active document
                if sig_type == "invoice_inquiry":
                    logger.info(f"Route: Invoice inquiry '{text}' -> action={target_act}")
                    return self._build_decision(
                        dept=DepartmentEnum.FINANCE,
                        intent="invoice_inquiry",
                        confidence=0.98,
                        entities={
                            "is_follow_up": True,
                            "action": target_act,
                            "doc_id": signals["entities"].get("doc_id"),
                            "filename": signals["entities"].get("filename")
                        }
                    )

                # 2e. Two-File Comparison ("compare this with the previous invoice")
                if sig_type == "comparison":
                    dept = DepartmentEnum(context_state.last_department) if context_state.last_department else DepartmentEnum.FINANCE
                    intent = "excel_comparison" if dept == DepartmentEnum.FINANCE else "file_comparison"
                    logger.info(f"Route: Multi-document comparison '{text}' -> {dept.value} / {intent}")
                    return self._build_decision(
                        dept=dept,
                        intent=intent,
                        confidence=0.98,
                        entities={
                            "is_follow_up": True,
                            "action": "COMPARE",
                            "current_doc": signals["entities"].get("current_doc"),
                            "prev_doc": signals["entities"].get("prev_doc")
                        }
                    )

                # 2f. Document action ("make me an excel document", "make an Excel from this invoice", "export it", "add section")
                if sig_type == "document_action":
                    if target_act == "INVOICE_EXCEL":
                        logger.info(f"Route: Invoice Excel export '{text}' -> FINANCE / invoice_export")
                        return self._build_decision(
                            dept=DepartmentEnum.FINANCE,
                            intent="invoice_export",
                            confidence=0.98,
                            entities={
                                "is_follow_up": True,
                                "action": "EXPORT",
                                "format": "xlsx",
                                "doc_id": context_state.active_document_id,
                                "filename": context_state.active_document_name
                            }
                        )
                    elif target_act == "MODIFY" and context_state.last_department:
                        dept = DepartmentEnum(context_state.last_department)
                        logger.info(f"Route: Document modification '{text}' mapped to {dept.value}")
                        return self._build_decision(
                            dept=dept,
                            intent="document_modification",
                            confidence=0.98,
                            entities={
                                "is_follow_up": True,
                                "action": "MODIFY",
                                "section_name": signals["entities"].get("section_name", "acknowledgement"),
                                "previous_file": context_state.last_generated_file,
                                "topic": context_state.last_topic
                            }
                        )
                    elif target_act == "EXPORT":
                        if (context_state.last_department or context_state.active_document) and (context_state.last_topic or context_state.active_document_name):
                            dept = DepartmentEnum(context_state.last_department) if context_state.last_department else (
                                DepartmentEnum.HR if (str(context_state.active_document_type).upper() in ("RESUME", "HR_POLICY", "OFFER_LETTER_TEMPLATE", "OFFER_LETTER") or any(k in str(context_state.active_document_name).lower() for k in ["hr", "ops", "resume", "cv"])) else DepartmentEnum.FINANCE
                            )
                            if "comparison" in str(context_state.last_intent or "").lower() or "comparison" in str(context_state.last_topic or "").lower():
                                intent = "excel_comparison" if dept == DepartmentEnum.FINANCE else "file_comparison"
                            else:
                                intent = "document_export"

                            logger.info(f"Route: Document export '{text}' inherited {dept.value} context ({intent})")
                            return self._build_decision(
                                dept=dept,
                                intent=intent,
                                confidence=0.98,
                                entities={
                                    "is_follow_up": True,
                                    "action": "EXPORT",
                                    "format": signals["entities"].get("format", "xlsx"),
                                    "topic": context_state.last_topic,
                                    "doc_id": context_state.active_document_id,
                                    "filename": context_state.active_document_name
                                }
                            )
                        else:
                            # Ambiguous document request with NO prior context
                            logger.info(f"Route: Ambiguous document request '{text}' with zero prior context")
                            return self._build_decision(
                                dept=DepartmentEnum.GENERAL,
                                intent="ambiguous_document_request",
                                confidence=0.75,
                                entities={"ambiguous": True}
                            )

                # 2g. Arithmetic continuation ("add 500 more")
                if sig_type == "arithmetic" and (context_state.last_department == "FINANCE" or context_state.last_intent == "expense_calculation"):
                    logger.info(f"Route: Arithmetic continuation '{text}' in FINANCE context")
                    return self._build_decision(
                        dept=DepartmentEnum.FINANCE,
                        intent="expense_calculation",
                        confidence=0.98,
                        entities={
                            "is_follow_up": True,
                            "action": "CALCULATE",
                            "delta_op": signals["entities"].get("delta_op", "add"),
                            "delta_val": signals["entities"].get("delta_val", 0.0)
                        }
                    )

                # 2e. Tech reference ("where should I fix it?", "show me the corrected code")
                if sig_type == "reference" and (context_state.last_department == "TECH" or context_state.department == "TECH"):
                    intent = "code_analysis" if target_act == "SHOW_CODE" else "troubleshooting"
                    logger.info(f"Route: Tech reference '{text}' -> {intent}")
                    return self._build_decision(
                        dept=DepartmentEnum.TECH,
                        intent=intent,
                        confidence=0.98,
                        entities={"is_follow_up": True, "action": target_act, "topic": context_state.last_topic}
                    )

        # 3. Deterministic Pattern Matching Pass
        best_match: Optional[Tuple[DepartmentEnum, str, float]] = None
        for pattern, dept, intent, confidence in self._rule_patterns:
            if pattern.search(text):
                best_match = (dept, intent, confidence)
                break

        # Check if user previously established department context (e.g. "I'm from tech department")
        # and current query is a generic project issue (e.g. "I want to know the issue in my project")
        if context_state and context_state.department and not best_match:
            try:
                dept_enum = DepartmentEnum(context_state.department)
                if re.search(r"\b(issue|problem|project|trouble|help me with my project)\b", text, re.I):
                    return self._build_decision(
                        dept=dept_enum,
                        intent="troubleshooting" if dept_enum == DepartmentEnum.TECH else "general_question",
                        confidence=0.95,
                        entities={"department_context": dept_enum.value}
                    )
            except ValueError:
                pass

        # 4. Contextual Follow-Up Fallback from history list if context_state was not passed
        if self.is_follow_up(text) and history:
            for entry in reversed(history):
                prev_dept_str = entry.get("department")
                prev_intent = entry.get("intent")
                if prev_dept_str and prev_dept_str != "GENERAL":
                    try:
                        prev_dept = DepartmentEnum(prev_dept_str)
                        logger.info(f"Follow-up detected for '{text}'. Inherited context: {prev_dept.value} / {prev_intent}")
                        entities = self._extract_entities(text)
                        entities["is_follow_up"] = True
                        entities["original_context_message"] = entry.get("user_message", "")
                        return self._build_decision(
                            dept=prev_dept,
                            intent=prev_intent or self._infer_default_intent_for_domain(prev_dept, text),
                            confidence=0.95,
                            entities=entities
                        )
                    except ValueError:
                        pass

        # 5. Domain Lexicon Scoring Pass
        lexicon_scores = self._score_domain_lexicons(text)
        top_domain, top_lex_score = max(lexicon_scores.items(), key=lambda x: x[1])

        # 6. Decision Arbitration
        entities = self._extract_entities(text)

        if best_match:
            dept, intent, base_conf = best_match
            if top_domain == dept and top_lex_score > 0:
                final_conf = min(0.99, base_conf + 0.03)
            else:
                final_conf = base_conf
            return self._build_decision(dept, intent, final_conf, entities)

        if top_lex_score >= 2:
            dept = top_domain
            intent = self._infer_default_intent_for_domain(dept, text)
            conf = min(0.85, 0.50 + 0.10 * top_lex_score)
            return self._build_decision(dept, intent, conf, entities)

        # 7. Low-confidence / Ambiguous Fallback
        return self._build_decision(
            dept=DepartmentEnum.GENERAL,
            intent="general_question" if len(text.split()) > 3 else "unknown",
            confidence=0.30 if top_lex_score > 0 else 0.15,
            entities=entities
        )

    def _score_domain_lexicons(self, text: str) -> Dict[DepartmentEnum, int]:
        """Calculates token frequency match across domain lexicons."""
        text_lower = text.lower()
        words = set(re.findall(r"\b\w+\b", text_lower))
        scores: Dict[DepartmentEnum, int] = {
            DepartmentEnum.TECH: 0,
            DepartmentEnum.HR: 0,
            DepartmentEnum.FINANCE: 0
        }
        for dept, keywords in self._domain_lexicons.items():
            scores[dept] = sum(1 for kw in keywords if kw in words or kw in text_lower)
        return scores

    def _infer_default_intent_for_domain(self, dept: DepartmentEnum, text: str) -> str:
        """Selects a reasonable default intent when routed primarily via domain scoring."""
        text_lower = text.lower()
        doc_verbs = re.search(r"\b(create|make|prepare|generate|write|build|produce|draft|help me|help with making|help with creating)\b", text_lower)
        if dept == DepartmentEnum.TECH:
            if "error" in text_lower or "fail" in text_lower or "crash" in text_lower:
                return "error_diagnosis"
            if "log" in text_lower:
                return "log_analysis"
            return "technical_question"
        elif dept == DepartmentEnum.HR:
            if re.search(r"\b(excel|xlsx|spreadsheet|csv)\b", text_lower):
                return "document_export"
            if re.search(r"\b(word|docx|doc)\b", text_lower):
                return "document_export"
            if doc_verbs and re.search(r"\b(document|doc|file|template|policy|hr|manual|handbook|form)\b", text_lower):
                return "document_creation"
            if "leave" in text_lower or "policy" in text_lower:
                return "policy_question"
            if "candidate" in text_lower or "resume" in text_lower or "hire" in text_lower:
                return "candidate_search"
            return "employee_information"
        elif dept == DepartmentEnum.FINANCE:
            if re.search(r"\b(excel|xlsx|spreadsheet)\b", text_lower):
                return "document_export"
            if doc_verbs and re.search(r"\b(document|report|file|template)\b", text_lower):
                return "financial_document"
            if "calculate" in text_lower or "total" in text_lower or "sum" in text_lower:
                return "expense_calculation"
            if "report" in text_lower:
                return "expense_report"
            if "invoice" in text_lower or "bill" in text_lower:
                return "invoice"
            return "financial_question"
        return "general_question"

    def _extract_entities(self, text: str) -> Dict[str, Any]:
        """Extracts common entities (amounts, dates, error codes, URLs, file paths, output formats)."""
        entities: Dict[str, Any] = {}

        # HTTP / Error codes
        error_match = re.search(r"\b(HTTP\s*|status code\s*)?([45]\d{2})\b", text, re.I)
        if error_match:
            entities["status_code"] = error_match.group(2)

        # Months / Time frames
        months = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
        for m in months:
            if re.search(r"\b" + m + r"\b", text, re.I):
                entities["period"] = m.capitalize()
                break

        # Currency amounts ($100, 500 USD, Rs 1000)
        amounts = re.findall(r"(\$|€|£|₹|Rs\.?)\s*(\d+(?:,\d{3})*(?:\.\d{2})?)", text)
        if amounts:
            entities["amounts"] = [f"{sym}{val}" for sym, val in amounts]

        # Candidate / employee name mentions
        name_match = re.search(r"\b(for candidate|for employee|for)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", text)
        if name_match and name_match.group(2).lower() not in ["july", "this", "our", "the", "my"]:
            entities["candidate_name"] = name_match.group(2)

        # Output format detection for document creation/export requests
        if re.search(r"\b(excel|xlsx|\.xlsx|spreadsheet)\b", text, re.I):
            entities["output_format"] = "xlsx"
        elif re.search(r"\b(word|docx|\.docx|doc file)\b", text, re.I):
            entities["output_format"] = "docx"
        elif re.search(r"\b(pdf)\b", text, re.I):
            entities["output_format"] = "pdf"

        return entities

    def _build_decision(
        self,
        dept: DepartmentEnum,
        intent: str,
        confidence: float,
        entities: Dict[str, Any]
    ) -> RoutingDecision:
        """Constructs a fully validated Pydantic RoutingDecision object."""
        knowledge_base = department_registry.get_knowledge_base_for_department(dept)
        tools = department_registry.get_tools_for_intent(intent)
        requires_perm = department_registry.is_permission_required(dept, intent)

        return RoutingDecision(
            department=dept,
            intent=intent,
            confidence=max(0.0, min(1.0, confidence)),
            knowledge_base=knowledge_base,
            required_tools=tools,
            requires_permission=requires_perm,
            entities=entities
        )


# Global singleton instance
intent_router = IntentRouter()
