"""Department Registry and Capability Definitions for Company AI.
"""

from typing import Dict, Any, List, Optional, Union
from backend.app.schemas.department import DepartmentEnum, DepartmentInfo


class DepartmentRegistry:
    """Central registry maintaining company department metadata, supported intents,
    associated knowledge bases, and required tool specifications.
    """

    def __init__(self):
        self._registry: Dict[DepartmentEnum, DepartmentInfo] = {
            DepartmentEnum.TECH: DepartmentInfo(
                department=DepartmentEnum.TECH,
                name="Technology & Infrastructure",
                description="Technical troubleshooting, system errors, IT support, code analysis, and DevOps diagnostics.",
                knowledge_base="tech",
                supported_intents=[
                    "technical_question",
                    "error_diagnosis",
                    "log_analysis",
                    "troubleshooting",
                    "code_analysis",
                    "incident_report"
                ],
                available_tools=[
                    "system_info",
                    "network_diagnostics",
                    "process_check",
                    "service_check",
                    "log_reader",
                    "code_analyzer"
                ],
                default_permission_required=False
            ),
            DepartmentEnum.HR: DepartmentInfo(
                department=DepartmentEnum.HR,
                name="Human Resources & Talent",
                description="Company policies, leave management, employee queries, talent acquisition, and recruitment.",
                knowledge_base="hr",
                supported_intents=[
                    "policy_question",
                    "employee_information",
                    "recruitment",
                    "candidate_search",
                    "interview_questions",
                    "offer_letter",
                    "hr_document"
                ],
                available_tools=[
                    "employee_lookup",
                    "candidate_pool_search",
                    "candidate_ranking",
                    "interview_generator",
                    "offer_letter_generator"
                ],
                default_permission_required=False
            ),
            DepartmentEnum.FINANCE: DepartmentInfo(
                department=DepartmentEnum.FINANCE,
                name="Finance & Accounting",
                description="Financial calculations, travel expenses, invoicing, budgets, and financial reporting.",
                knowledge_base="finance",
                supported_intents=[
                    "expense_calculation",
                    "expense_report",
                    "invoice",
                    "budget_analysis",
                    "financial_question",
                    "financial_document"
                ],
                available_tools=[
                    "calculator",
                    "finance_database",
                    "invoice_extractor",
                    "excel_generator",
                    "pdf_report_generator"
                ],
                default_permission_required=True
            ),
            DepartmentEnum.GENERAL: DepartmentInfo(
                department=DepartmentEnum.GENERAL,
                name="General Corporate Intelligence",
                description="General company queries, FAQs, and unclassified organizational requests.",
                knowledge_base="general",
                supported_intents=[
                    "general_question",
                    "unknown"
                ],
                available_tools=[],
                default_permission_required=False
            )
        }

        # Intent to specific tools mapping
        self._intent_tools_map: Dict[str, List[str]] = {
            # TECH
            "troubleshooting": ["network_diagnostics", "system_info"],
            "error_diagnosis": ["service_check", "log_reader"],
            "log_analysis": ["log_reader"],
            "code_analysis": ["code_analyzer"],
            "technical_question": [],
            "incident_report": ["system_info", "log_reader"],

            # HR
            "policy_question": [],
            "employee_information": ["employee_lookup"],
            "recruitment": ["candidate_pool_search", "candidate_ranking"],
            "candidate_search": ["candidate_pool_search", "candidate_ranking"],
            "interview_questions": ["interview_generator"],
            "offer_letter": ["offer_letter_generator"],
            "hr_document": [],

            # FINANCE
            "expense_calculation": ["calculator"],
            "expense_report": ["finance_database", "calculator", "excel_generator"],
            "invoice": ["invoice_extractor", "calculator"],
            "budget_analysis": ["finance_database", "calculator"],
            "financial_question": [],
            "financial_document": ["excel_generator", "pdf_report_generator"],

            # GENERAL
            "general_question": [],
            "unknown": []
        }

        # Intents requiring elevated authorization
        self._sensitive_intents: Dict[str, bool] = {
            "offer_letter": True,
            "employee_information": True,
            "expense_report": True,
            "invoice": True,
            "budget_analysis": True,
            "incident_report": True,
        }

    def get_department(self, dept: Union[DepartmentEnum, str]) -> Optional[DepartmentInfo]:
        """Retrieves metadata for a specific department."""
        if isinstance(dept, str):
            try:
                dept = DepartmentEnum(dept.upper())
            except ValueError:
                return None
        return self._registry.get(dept)

    def list_departments(self) -> List[DepartmentInfo]:
        """Returns metadata for all registered departments."""
        return list(self._registry.values())

    def get_tools_for_intent(self, intent: str) -> List[str]:
        """Returns the tools required for a given intent."""
        return self._intent_tools_map.get(intent, [])

    def is_permission_required(self, department: DepartmentEnum, intent: str) -> bool:
        """Determines if the given intent requires elevated permission check."""
        if department == DepartmentEnum.FINANCE and intent in ["expense_report", "budget_analysis", "invoice"]:
            return True
        return self._sensitive_intents.get(intent, False)

    def get_knowledge_base_for_department(self, dept: DepartmentEnum) -> str:
        """Returns the knowledge base ID for a department."""
        dept_info = self._registry.get(dept)
        return dept_info.knowledge_base if dept_info else "general"


# Global singleton instance
department_registry = DepartmentRegistry()
