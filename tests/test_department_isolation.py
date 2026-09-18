"""Unit and integration tests for Department-Scoped RAG, Permission Boundaries, and Audit Logging (Phase 3).
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.schemas.department import DepartmentEnum
from backend.app.schemas.security import UserRoleEnum, SecurityLevelEnum
from backend.app.services.rag.department_rag import department_rag
from backend.app.services.security.permission_manager import permission_manager
from backend.app.services.security.audit_logger import audit_logger

client = TestClient(app)


class TestDepartmentIsolation:
    """Test suite ensuring strict department knowledge boundaries, RBAC permissions, and audit trails."""

    def setup_method(self):
        # Ensure fresh synthetic test data is indexed
        department_rag._ensure_synthetic_test_data()

    def test_tech_retrieves_tech_document_allowed(self):
        """TECH request by Employee/Tech Admin successfully retrieves Tech documentation."""
        results = department_rag.retrieve(
            query="API code review and staging deployment policy",
            department=DepartmentEnum.TECH,
            user_role=UserRoleEnum.EMPLOYEE,
            user_id="tech_user_01"
        )
        assert len(results) > 0
        assert any("TECH_TEST_POLICY" in r["text"] for r in results)
        assert all(r["department"] == "TECH" for r in results)

    def test_hr_retrieves_hr_document_allowed(self):
        """HR request by Employee/HR Manager successfully retrieves HR leave policy."""
        results = department_rag.retrieve(
            query="casual leave and sick leave days policy",
            department=DepartmentEnum.HR,
            user_role=UserRoleEnum.EMPLOYEE,
            user_id="hr_user_01"
        )
        assert len(results) > 0
        assert any("HR_TEST_POLICY" in r["text"] for r in results)
        assert all(r["department"] == "HR" for r in results)

    def test_finance_retrieves_finance_document_allowed(self):
        """FINANCE request by Employee/Finance Manager successfully retrieves Finance expense policy."""
        results = department_rag.retrieve(
            query="monthly expense reports submission deadline 25th",
            department=DepartmentEnum.FINANCE,
            user_role=UserRoleEnum.EMPLOYEE,
            user_id="fin_user_01"
        )
        assert len(results) > 0
        assert any("FINANCE_TEST_POLICY" in r["text"] for r in results)
        assert all(r["department"] == "FINANCE" for r in results)

    def test_hr_request_cannot_retrieve_finance_documents(self):
        """HR department scoped search must NEVER return any Finance documents."""
        results = department_rag.retrieve(
            query="expense reports reimbursement deadline and tax audit",
            department=DepartmentEnum.HR,
            user_role=UserRoleEnum.HR_MANAGER,
            user_id="hr_manager_01"
        )
        # Should not find finance policies inside HR scope
        for r in results:
            assert r["department"] != "FINANCE"
            assert "FINANCE_TEST_POLICY" not in r["text"]
            assert "FINANCE_CONFIDENTIAL_AUDIT" not in r["text"]

    def test_finance_request_cannot_retrieve_hr_documents(self):
        """FINANCE department scoped search must NEVER return any HR documents."""
        results = department_rag.retrieve(
            query="casual leave policy and sick leave days",
            department=DepartmentEnum.FINANCE,
            user_role=UserRoleEnum.FINANCE_MANAGER,
            user_id="fin_manager_01"
        )
        for r in results:
            assert r["department"] != "HR"
            assert "HR_TEST_POLICY" not in r["text"]
            assert "HR_CONFIDENTIAL_SALARY_BAND" not in r["text"]

    def test_tech_request_cannot_retrieve_hr_confidential_documents(self):
        """TECH request must NEVER return confidential HR executive compensation data."""
        results = department_rag.retrieve(
            query="executive compensation salary bands FY2026",
            department=DepartmentEnum.TECH,
            user_role=UserRoleEnum.TECH_ADMIN,
            user_id="tech_admin_01"
        )
        for r in results:
            assert "HR_CONFIDENTIAL_SALARY_BAND" not in r["text"]

    def test_unauthorized_employee_denied_confidential_records(self):
        """Standard Employee role is strictly barred from retrieving confidential HR or Finance records."""
        # 1. Employee trying to retrieve confidential HR salary bands
        hr_results = department_rag.retrieve(
            query="executive compensation salary bands",
            department=DepartmentEnum.HR,
            user_role=UserRoleEnum.EMPLOYEE,
            user_id="emp_01"
        )
        assert not any("HR_CONFIDENTIAL_SALARY_BAND" in r["text"] for r in hr_results)

        # 2. HR Manager can retrieve confidential HR salary bands
        hr_mgr_results = department_rag.retrieve(
            query="executive compensation salary bands",
            department=DepartmentEnum.HR,
            user_role=UserRoleEnum.HR_MANAGER,
            user_id="hr_mgr_01"
        )
        assert any("HR_CONFIDENTIAL_SALARY_BAND" in r["text"] for r in hr_mgr_results)

    def test_metadata_filtering_and_enrichment(self):
        """Validates that all retrieved chunks carry required metadata fields."""
        results = department_rag.retrieve(
            query="leave policy",
            department=DepartmentEnum.HR,
            user_role=UserRoleEnum.HR_MANAGER
        )
        assert len(results) > 0
        chunk = results[0]
        assert "chunk_id" in chunk
        assert "doc_id" in chunk
        assert "department" in chunk
        assert "document_type" in chunk
        assert "security_level" in chunk
        assert "role_required" in chunk
        assert "created_at" in chunk
        assert "score" in chunk
        assert "embedding" not in chunk  # Raw vectors should be stripped from payload

    def test_audit_logging_generation(self):
        """Verifies that an audit record is logged on every knowledge access attempt."""
        init_logs_count = len(audit_logger.get_recent_logs(limit=100))

        # Perform an allowed search
        department_rag.retrieve(
            query="testing audit logging",
            department=DepartmentEnum.TECH,
            user_role=UserRoleEnum.EMPLOYEE,
            user_id="audit_test_user"
        )

        logs = audit_logger.get_recent_logs(limit=10)
        assert len(logs) > 0
        latest = logs[-1]
        assert latest["user_id"] == "audit_test_user"
        assert latest["department"] == "TECH"
        assert latest["operation"] == "KNOWLEDGE_RETRIEVAL"
        assert latest["access_allowed"] is True

    def test_api_knowledge_search_endpoint(self):
        """Tests the POST /api/company/knowledge/search endpoint."""
        res = client.post(
            "/api/company/knowledge/search",
            json={
                "query": "What is the casual leave policy?",
                "department": "HR",
                "user_role": "EMPLOYEE",
                "user_id": "test_api_user",
                "top_k": 2
            }
        )
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert data[0]["department"] == "HR"
        assert "HR_TEST_POLICY" in data[0]["text"]
