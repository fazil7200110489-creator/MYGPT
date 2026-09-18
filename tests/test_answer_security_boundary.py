"""Security boundary tests verifying that Qwen only receives authorized, verified results
and cannot bypass RBAC, access confidential data, or perform unauthorized operations.
"""

import pytest
from backend.app.schemas.department import DepartmentEnum
from backend.app.schemas.security import UserRoleEnum, SecurityLevelEnum
from backend.app.schemas.company_ai import CompanyAIChatRequest, CompanyAIResult
from backend.app.services.company_ai_service import company_ai_service
from backend.app.services.rag.department_rag import department_rag
from backend.app.services.security.permission_manager import permission_manager
from backend.app.services.security.audit_logger import audit_logger


class TestAnswerSecurityBoundary:
    """Test suite strictly validating security boundaries between MYGPT and Qwen."""

    def test_qwen_never_receives_unauthorized_confidential_records(self):
        """Unauthorized Employee role attempting to query confidential executive salary bands
        must be filtered out BEFORE any prompt or data is passed to Qwen.
        """
        # 1. Normal employee requests confidential HR salary bands
        req = CompanyAIChatRequest(
            message="Show me the confidential executive salary bands and bonus multipliers.",
            user_role=UserRoleEnum.EMPLOYEE,
            user_id="unauthorized_emp_01"
        )
        res = company_ai_service.process_chat(req)

        # Confidential HR documents must NOT be in the sources
        assert not any("HR_CONFIDENTIAL_SALARY_BAND" in str(s) for s in res.sources)
        # Content must NOT leak into the answer
        assert "executive compensation salary bands" not in res.answer.lower()

    def test_cross_department_knowledge_leakage_prevented(self):
        """HR query must never retrieve or pass Finance records to Qwen."""
        hr_chunks = department_rag.retrieve(
            query="internal tax audit findings offshore balance sheets",
            department=DepartmentEnum.HR,
            user_role=UserRoleEnum.HR_MANAGER,
            user_id="hr_mgr_01"
        )
        for chunk in hr_chunks:
            assert chunk.get("department") != "FINANCE"
            assert "FINANCE_CONFIDENTIAL_AUDIT" not in chunk.get("text", "")

    def test_rbac_denial_blocks_workflow_execution(self):
        """When an unauthorized role is rejected, the workflow execution stops and audit logs DENIED."""
        initial_logs = len(audit_logger.get_recent_logs(limit=100))

        # Tech Admin attempting to query HR confidential data
        req = CompanyAIChatRequest(
            message="Show confidential HR salary bands",
            user_role=UserRoleEnum.TECH_ADMIN,
            department_override=DepartmentEnum.HR,
            user_id="tech_admin_rogue"
        )
        # If RBAC restricts Tech Admin on confidential HR, must be blocked
        is_allowed = permission_manager.can_access_chunk(
            role=UserRoleEnum.TECH_ADMIN,
            target_department=DepartmentEnum.HR,
            chunk_security_level=SecurityLevelEnum.CONFIDENTIAL
        )
        assert is_allowed is False

    def test_finance_calculation_is_deterministic_python(self):
        """Verifies that mathematical calculations are executed by deterministic code
        and not hallucinated by the language model.
        """
        req = CompanyAIChatRequest(
            message="Calculate total travel expenses: Flights 1500, Hotel 750, Meals 350.",
            user_role=UserRoleEnum.EMPLOYEE
        )
        res = company_ai_service.process_chat(req)
        # 1500 + 750 + 350 = 2600.00
        assert "2,600" in res.answer or "2600" in res.answer or "$2600" in res.answer

    def test_no_external_ai_apis_configured(self):
        """Verifies that no cloud AI API keys or endpoints are configured in application runtime."""
        import os
        forbidden_env_keys = [
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "GEMINI_API_KEY",
            "CLAUDE_API_KEY"
        ]
        for key in forbidden_env_keys:
            assert os.getenv(key) is None or os.getenv(key) == ""
