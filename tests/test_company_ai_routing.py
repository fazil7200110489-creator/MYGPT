"""Unit and integration tests for Company AI Department Registry and Hybrid Intent Router (Phase 2).
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.schemas.department import DepartmentEnum, RoutingDecision, RouteRequest
from backend.app.services.routing.intent_router import intent_router
from backend.app.departments.department_registry import department_registry

client = TestClient(app)


class TestCompanyAIRouting:
    """Test suite for Phase 2 Department Registry and Hybrid Intent Router."""

    def test_tech_troubleshooting_routing(self):
        req = RouteRequest(message="My laptop has Wi-Fi but internet is not working.")
        decision = intent_router.route(req)
        assert decision.department == DepartmentEnum.TECH
        assert decision.intent == "troubleshooting"
        assert decision.confidence >= 0.85
        assert decision.knowledge_base == "tech"
        assert "network_diagnostics" in decision.required_tools

    def test_tech_error_diagnosis_routing(self):
        req = RouteRequest(message="My application is returning HTTP 500.")
        decision = intent_router.route(req)
        assert decision.department == DepartmentEnum.TECH
        assert decision.intent == "error_diagnosis"
        assert decision.confidence >= 0.85
        assert decision.entities.get("status_code") == "500"

    def test_tech_log_analysis_routing(self):
        req = RouteRequest(message="Analyze this server error log.")
        decision = intent_router.route(req)
        assert decision.department == DepartmentEnum.TECH
        assert decision.intent == "log_analysis"
        assert decision.confidence >= 0.85
        assert "log_reader" in decision.required_tools

    def test_tech_code_analysis_routing(self):
        req = RouteRequest(message="Debug this Python function and fix the syntax error.")
        decision = intent_router.route(req)
        assert decision.department == DepartmentEnum.TECH
        assert decision.intent == "code_analysis"
        assert decision.confidence >= 0.80

    def test_hr_leave_policy_routing(self):
        req = RouteRequest(message="What is our casual leave policy?")
        decision = intent_router.route(req)
        assert decision.department == DepartmentEnum.HR
        assert decision.intent == "policy_question"
        assert decision.confidence >= 0.90
        assert decision.knowledge_base == "hr"
        assert decision.requires_permission is False

    def test_hr_offer_letter_routing(self):
        req = RouteRequest(message="Generate an offer letter for this candidate.")
        decision = intent_router.route(req)
        assert decision.department == DepartmentEnum.HR
        assert decision.intent == "offer_letter"
        assert decision.confidence >= 0.90
        assert decision.requires_permission is True
        assert "offer_letter_generator" in decision.required_tools

    def test_hr_candidate_search_routing(self):
        req = RouteRequest(message="Find candidates matching this job description.")
        decision = intent_router.route(req)
        assert decision.department == DepartmentEnum.HR
        assert decision.intent in ["candidate_search", "recruitment"]
        assert decision.confidence >= 0.85
        assert "candidate_pool_search" in decision.required_tools

    def test_hr_employee_information_routing(self):
        req = RouteRequest(message="What is the employee info and reporting manager for John?")
        decision = intent_router.route(req)
        assert decision.department == DepartmentEnum.HR
        assert decision.intent == "employee_information"
        assert decision.requires_permission is True

    def test_finance_expense_calculation_routing(self):
        req = RouteRequest(message="Calculate total travel expenses for July.")
        decision = intent_router.route(req)
        assert decision.department == DepartmentEnum.FINANCE
        assert decision.intent == "expense_calculation"
        assert decision.confidence >= 0.90
        assert decision.knowledge_base == "finance"
        assert "calculator" in decision.required_tools
        assert decision.entities.get("period") == "July"

    def test_finance_expense_report_routing(self):
        req = RouteRequest(message="Generate the monthly expense report.")
        decision = intent_router.route(req)
        assert decision.department == DepartmentEnum.FINANCE
        assert decision.intent == "expense_report"
        assert decision.confidence >= 0.90
        assert decision.requires_permission is True
        assert "excel_generator" in decision.required_tools

    def test_finance_invoice_extraction_routing(self):
        req = RouteRequest(message="Extract information from this invoice.")
        decision = intent_router.route(req)
        assert decision.department == DepartmentEnum.FINANCE
        assert decision.intent == "invoice"
        assert decision.confidence >= 0.90
        assert "invoice_extractor" in decision.required_tools

    def test_finance_budget_analysis_routing(self):
        req = RouteRequest(message="Can you perform a quarterly budget analysis for Q3?")
        decision = intent_router.route(req)
        assert decision.department == DepartmentEnum.FINANCE
        assert decision.intent == "budget_analysis"
        assert decision.confidence >= 0.85
        assert decision.requires_permission is True

    def test_general_question_routing(self):
        req = RouteRequest(message="Hello, what are your capabilities and what can you do?")
        decision = intent_router.route(req)
        assert decision.department == DepartmentEnum.GENERAL
        assert decision.intent == "general_question"
        assert decision.knowledge_base == "general"

    def test_unknown_gibberish_routing(self):
        req = RouteRequest(message="xyz 123 foo bar")
        decision = intent_router.route(req)
        assert decision.department == DepartmentEnum.GENERAL
        assert decision.intent in ["unknown", "general_question"]
        assert decision.confidence <= 0.50

    def test_empty_message_handling(self):
        req = RouteRequest(message="   ")
        decision = intent_router.route(req)
        assert decision.department == DepartmentEnum.GENERAL
        assert decision.intent == "unknown"
        assert decision.confidence == 0.0

    def test_confidence_boundary_constraints(self):
        test_messages = [
            "What is our casual leave policy?",
            "Calculate total travel expenses for July.",
            "My application is returning HTTP 500.",
            "Some ambiguous query",
            "Hello"
        ]
        for msg in test_messages:
            dec = intent_router.route(RouteRequest(message=msg))
            assert 0.0 <= dec.confidence <= 1.0
            assert isinstance(dec.department, DepartmentEnum)
            assert isinstance(dec.intent, str)
            assert isinstance(dec.required_tools, list)

    def test_department_registry_consistency(self):
        depts = department_registry.list_departments()
        dept_enums = [d.department for d in depts]
        assert DepartmentEnum.TECH in dept_enums
        assert DepartmentEnum.HR in dept_enums
        assert DepartmentEnum.FINANCE in dept_enums
        assert DepartmentEnum.GENERAL in dept_enums

        tech_info = department_registry.get_department(DepartmentEnum.TECH)
        assert tech_info is not None
        assert tech_info.knowledge_base == "tech"
        assert "troubleshooting" in tech_info.supported_intents

    def test_route_api_endpoint(self):
        res = client.post("/api/company/route", json={"message": "What is our casual leave policy?"})
        assert res.status_code == 200
        data = res.json()
        assert data["department"] == "HR"
        assert data["intent"] == "policy_question"
        assert data["knowledge_base"] == "hr"
        assert data["confidence"] >= 0.90
        assert data["requires_permission"] is False

    def test_departments_api_endpoint(self):
        res = client.get("/api/company/departments")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 4
        dept_names = [d["department"] for d in data]
        assert "TECH" in dept_names
        assert "HR" in dept_names
        assert "FINANCE" in dept_names
        assert "GENERAL" in dept_names
