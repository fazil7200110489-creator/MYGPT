"""Tests for Company AI UI API endpoints.
Validates:
- POST /api/company/chat
- GET /api/company/ai/status
- GET /api/company/departments
- POST /api/company/route
- GET /api/company/chat/history
- POST /api/company/chat/reset
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


class TestCompanyAIUIAPI:
    """Test suite for FastAPI endpoints supporting the Company AI UI."""

    def test_get_ai_status_endpoint(self):
        """GET /api/company/ai/status returns online status and local model info."""
        res = client.get("/api/company/ai/status")
        assert res.status_code == 200
        data = res.json()
        assert data["company_ai"] == "online"
        assert data["mygpt"] == "available"
        assert "Qwen" in data["answer_model"]
        assert data["external_ai"] is False

    def test_list_departments_endpoint(self):
        """GET /api/company/departments returns TECH, HR, FINANCE, and GENERAL."""
        res = client.get("/api/company/departments")
        assert res.status_code == 200
        departments = res.json()
        dept_names = [d["department"] for d in departments]
        assert "TECH" in dept_names
        assert "HR" in dept_names
        assert "FINANCE" in dept_names
        assert "GENERAL" in dept_names

    def test_chat_hr_endpoint(self):
        """POST /api/company/chat with HR leave query."""
        payload = {
            "message": "What is our casual leave policy?",
            "user_role": "EMPLOYEE",
            "user_id": "test_emp"
        }
        res = client.post("/api/company/chat", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["department"] == "HR"
        assert data["intent"] == "policy_question"
        assert data["status"] == "success"
        assert len(data["answer"]) > 0
        assert len(data["sources"]) > 0

    def test_chat_tech_endpoint(self):
        """POST /api/company/chat with Tech diagnostic query."""
        payload = {
            "message": "My PHP API returns HTTP 500 error",
            "user_role": "EMPLOYEE",
            "user_id": "test_emp"
        }
        res = client.post("/api/company/chat", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["department"] == "TECH"
        assert data["intent"] == "error_diagnosis"
        assert data["status"] == "success"
        assert "500" in data["answer"]
        assert len(data["actions"]) > 0

    def test_chat_finance_calculation_endpoint(self):
        """POST /api/company/chat with Finance expense calculation."""
        payload = {
            "message": "Calculate total expenses: Travel $500, Hotel $700, Food $150",
            "user_role": "EMPLOYEE",
            "user_id": "test_emp"
        }
        res = client.post("/api/company/chat", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["department"] == "FINANCE"
        assert data["intent"] == "expense_calculation"
        assert data["status"] == "success"
        assert "1,350" in data["answer"] or "1350" in data["answer"] or "$1350" in data["answer"]

    def test_chat_history_and_reset_endpoints(self):
        """GET /api/company/chat/history and POST /api/company/chat/reset."""
        session_id = "test_ui_session_123"
        # 1. Send message
        client.post(
            "/api/company/chat",
            json={"message": "Hello Company AI", "session_id": session_id}
        )
        # 2. Get history
        hist_res = client.get(f"/api/company/chat/history?session_id={session_id}")
        assert hist_res.status_code == 200
        history = hist_res.json()
        assert len(history) >= 1
        assert history[0]["user_message"] == "Hello Company AI"

        # 3. Reset history
        reset_res = client.post(f"/api/company/chat/reset?session_id={session_id}")
        assert reset_res.status_code == 200
        assert reset_res.json()["success"] is True

        # 4. Verify cleared
        hist_res2 = client.get(f"/api/company/chat/history?session_id={session_id}")
        assert len(hist_res2.json()) == 0
