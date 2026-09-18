"""Comprehensive Test Suite for Generic Excel Semantic Understanding & Column-Aware Operations.

Tests the 20 explicit test cases and unseen variations specified in the prompt:
1. "what are the columns available?"
2. "give me the username column"
3. "give me username as excel"
4. "what is the expiry date?"
5. "who are all expired?"
6. "how many users are expired?"
7. "give me expired users as excel"
8. "give me their usernames"
9. "give me their usernames as excel"
10. "who expires this month?"
11. "who expired last month?"
12. "what is the latest expiry date?"
13. "what is the earliest expiry date?"
14. "give me mobile numbers"
15. "give me mobile numbers as excel"
16. "moile numbers only as exel"
17. "give me contact numbers"
18. "give me email addresses as excel"
19. "give me those as Excel"
20. "make an Excel sheet"
+ Unseen natural language variations
"""

import os
import openpyxl
import pytest
from datetime import date

from backend.app.schemas.company_ai import CompanyAIChatRequest
from backend.app.schemas.security import UserRoleEnum
from backend.app.services.company_ai_service import CompanyAIService
from backend.app.services.conversation_context_manager import conversation_context_manager
from backend.app.services.document_manager import document_manager
from backend.app.services.excel.semantic_excel_resolver import semantic_excel_resolver
from backend.app.services.excel.excel_aggregator import excel_aggregator


@pytest.fixture
def users_workbook(tmp_path):
    """Creates a real Excel file with arbitrary company headers."""
    file_path = str(tmp_path / "user_accounts.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "UserAccounts"

    headers = ["UserName", "FirstName", "VleId", "MobileNo", "Email", "Expiry_Date"]
    ws.append(headers)

    # Reference today: 2026-09-18
    # 3 expired (2024-05-10, 2025-12-31, 2026-08-15)
    # 1 this month (2026-09-25)
    # 1 next month (2026-10-30)
    # 1 future (2027-01-01)
    data = [
        ["user01", "John", "VLE001", "9876543210", "john@example.com", "2025-12-31"],
        ["user02", "Alice", "VLE002", "9876543211", "alice@example.com", "2026-08-15"],
        ["user03", "Bob", "VLE003", "9876543212", "bob@example.com", "2026-09-25"],
        ["user04", "Charlie", "VLE004", "9876543213", "charlie@example.com", "2026-10-30"],
        ["user05", "David", "VLE005", "9876543214", "david@example.com", "2024-05-10"],
        ["user06", "Emma", "VLE006", "9876543215", "emma@example.com", "2027-01-01"]
    ]
    for row in data:
        ws.append(row)

    wb.save(file_path)

    with open(file_path, "rb") as f:
        content = f.read()
    doc_meta = document_manager.upload_document(
        filename="user_accounts.xlsx",
        file_content=content
    )
    return doc_meta


@pytest.fixture
def service():
    return CompanyAIService()


# ====================================================================
# Unit / Resolver Tests
# ====================================================================

def test_semantic_column_resolution_and_typos():
    headers = ["UserName", "FirstName", "VleId", "MobileNo", "Email", "Expiry_Date"]

    # Synonyms and typos
    assert semantic_excel_resolver.resolve_column("username", headers) == "UserName"
    assert semantic_excel_resolver.resolve_column("usernames", headers) == "UserName"
    assert semantic_excel_resolver.resolve_column("mobile number", headers) == "MobileNo"
    assert semantic_excel_resolver.resolve_column("moile numbers only as exel", headers) == "MobileNo"
    assert semantic_excel_resolver.resolve_column("contact numbers", headers) == "MobileNo"
    assert semantic_excel_resolver.resolve_column("phone numbers", headers) == "MobileNo"
    assert semantic_excel_resolver.resolve_column("email addresses", headers) == "Email"
    assert semantic_excel_resolver.resolve_column("expiry date", headers) == "Expiry_Date"
    assert semantic_excel_resolver.resolve_column("when does it expire", headers) == "Expiry_Date"
    assert semantic_excel_resolver.resolve_column("VLE ID", headers) == "VleId"


def test_semantic_request_date_filters():
    headers = ["UserName", "FirstName", "VleId", "MobileNo", "Email", "Expiry_Date"]

    # 1. Expired users
    req1 = semantic_excel_resolver.understand_request("who are all expired?", headers)
    assert req1.operation == "FILTER"
    assert req1.filters[0]["operator"] == "BEFORE_TODAY"
    assert req1.filters[0]["column"] == "Expiry_Date"

    # 2. Expired users as excel
    req2 = semantic_excel_resolver.understand_request("give me expired users as excel", headers)
    assert req2.operation == "FILTER_EXPORT"
    assert req2.output_format == "XLSX"

    # 3. Usernames of expired users
    req3 = semantic_excel_resolver.understand_request("give me usernames of expired users", headers)
    assert req3.operation == "FILTER_COLUMN"
    assert req3.target_columns == ["UserName"]

    # 4. Expiring this month
    req4 = semantic_excel_resolver.understand_request("who expires this month?", headers)
    assert req4.operation == "FILTER"
    assert req4.filters[0]["operator"] in ("CURRENT_MONTH", "THIS_MONTH")

    # 5. Expired last month
    req5 = semantic_excel_resolver.understand_request("who expired last month?", headers)
    assert req5.operation == "FILTER"
    assert req5.filters[0]["operator"] == "LAST_MONTH"

    # 6. Latest expiry date
    req6 = semantic_excel_resolver.understand_request("what is the latest expiry date?", headers)
    assert req6.operation == "MAX"
    assert req6.target_column == "Expiry_Date"

    # 7. Earliest expiry date
    req7 = semantic_excel_resolver.understand_request("what is the earliest expiry date?", headers)
    assert req7.operation == "MIN"
    assert req7.target_column == "Expiry_Date"


# ====================================================================
# End-to-End Chat Pipeline Tests (20 Specific Cases)
# ====================================================================

def test_case_1_columns_available(service, users_workbook):
    resp = service.process_chat(CompanyAIChatRequest(
        message="what are the columns available?",
        document_id=users_workbook["id"],
        conversation_id="conv-case-1",
        user_role=UserRoleEnum.EMPLOYEE
    ))
    assert "UserName" in resp.answer
    assert "MobileNo" in resp.answer
    assert "Expiry_Date" in resp.answer


def test_case_2_give_me_username_column(service, users_workbook):
    resp = service.process_chat(CompanyAIChatRequest(
        message="give me the username column",
        document_id=users_workbook["id"],
        conversation_id="conv-case-2",
        user_role=UserRoleEnum.EMPLOYEE
    ))
    assert resp.tool_results.get("card_type") in ("excel_preview", "column_preview", "column_analysis")
    assert resp.tool_results.get("column") == "UserName"
    assert resp.tool_results.get("record_count") == 6


def test_case_3_give_me_username_as_excel(service, users_workbook):
    resp = service.process_chat(CompanyAIChatRequest(
        message="give me username as excel",
        document_id=users_workbook["id"],
        conversation_id="conv-case-3",
        user_role=UserRoleEnum.EMPLOYEE
    ))
    assert len(resp.files) > 0
    assert "UserName" in resp.files[0]["filename"]


def test_case_4_what_is_the_expiry_date(service, users_workbook):
    resp = service.process_chat(CompanyAIChatRequest(
        message="what is the expiry date?",
        document_id=users_workbook["id"],
        conversation_id="conv-case-4",
        user_role=UserRoleEnum.EMPLOYEE
    ))
    assert resp.intent in ("excel_read_column", "excel_column_export", "excel_max", "excel_min")
    assert "Expiry_Date" in resp.answer or "Expiry_Date" in str(resp.tool_results)


def test_case_5_who_are_all_expired(service, users_workbook):
    resp = service.process_chat(CompanyAIChatRequest(
        message="who are all expired?",
        document_id=users_workbook["id"],
        conversation_id="conv-case-5",
        user_role=UserRoleEnum.EMPLOYEE
    ))
    assert resp.intent == "excel_filter"
    assert resp.tool_results.get("count") == 3
    # Check that user01, user02, user05 are in matched records
    matched = resp.tool_results.get("matched_rows", [])
    usernames = [r.get("UserName") for r in matched]
    assert "user01" in usernames
    assert "user02" in usernames
    assert "user05" in usernames


def test_case_6_how_many_users_are_expired(service, users_workbook):
    resp = service.process_chat(CompanyAIChatRequest(
        message="how many users are expired?",
        document_id=users_workbook["id"],
        conversation_id="conv-case-6",
        user_role=UserRoleEnum.EMPLOYEE
    ))
    assert "3" in resp.answer or resp.tool_results.get("count") == 3


def test_case_7_give_me_expired_users_as_excel(service, users_workbook):
    resp = service.process_chat(CompanyAIChatRequest(
        message="give me expired users as excel",
        document_id=users_workbook["id"],
        conversation_id="conv-case-7",
        user_role=UserRoleEnum.EMPLOYEE
    ))
    assert len(resp.files) > 0
    assert resp.tool_results.get("record_count") == 3


def test_cases_8_and_9_follow_up_usernames_and_export(service, users_workbook):
    conv_id = "conv-case-8-9"

    # Step 1: Who are the expired users?
    resp1 = service.process_chat(CompanyAIChatRequest(
        message="who are the expired users?",
        document_id=users_workbook["id"],
        conversation_id=conv_id,
        user_role=UserRoleEnum.EMPLOYEE
    ))
    assert resp1.tool_results.get("count") == 3

    # Step 2: "give me their usernames" (Case 8)
    resp2 = service.process_chat(CompanyAIChatRequest(
        message="give me their usernames",
        conversation_id=conv_id,
        user_role=UserRoleEnum.EMPLOYEE
    ))
    assert resp2.tool_results.get("card_type") == "column_values"
    assert resp2.tool_results.get("column") == "UserName"
    assert len(resp2.tool_results.get("values", [])) == 3
    assert "user01" in resp2.tool_results.get("values", [])

    # Step 3: "give me that as Excel" (Case 9 & Case 19)
    resp3 = service.process_chat(CompanyAIChatRequest(
        message="give me that as Excel",
        conversation_id=conv_id,
        user_role=UserRoleEnum.EMPLOYEE
    ))
    assert len(resp3.files) > 0
    assert resp3.tool_results.get("record_count") == 3
    # Must NOT generate full summary
    assert resp3.intent == "excel_export_result"


def test_case_10_who_expires_this_month(service, users_workbook):
    resp = service.process_chat(CompanyAIChatRequest(
        message="who expires this month?",
        document_id=users_workbook["id"],
        conversation_id="conv-case-10",
        user_role=UserRoleEnum.EMPLOYEE
    ))
    assert resp.intent == "excel_filter"
    matched = resp.tool_results.get("matched_rows", [])
    usernames = [r.get("UserName") for r in matched]
    assert "user03" in usernames


def test_case_11_who_expired_last_month(service, users_workbook):
    resp = service.process_chat(CompanyAIChatRequest(
        message="who expired last month?",
        document_id=users_workbook["id"],
        conversation_id="conv-case-11",
        user_role=UserRoleEnum.EMPLOYEE
    ))
    assert resp.intent == "excel_filter"
    matched = resp.tool_results.get("matched_rows", [])
    usernames = [r.get("UserName") for r in matched]
    assert "user02" in usernames


def test_case_12_latest_expiry_date(service, users_workbook):
    resp = service.process_chat(CompanyAIChatRequest(
        message="what is the latest expiry date?",
        document_id=users_workbook["id"],
        conversation_id="conv-case-12",
        user_role=UserRoleEnum.EMPLOYEE
    ))
    assert "2027-01-01" in resp.answer or resp.tool_results.get("primary_value") == "2027-01-01"


def test_case_13_earliest_expiry_date(service, users_workbook):
    resp = service.process_chat(CompanyAIChatRequest(
        message="what is the earliest expiry date?",
        document_id=users_workbook["id"],
        conversation_id="conv-case-13",
        user_role=UserRoleEnum.EMPLOYEE
    ))
    assert "2024-05-10" in resp.answer or resp.tool_results.get("primary_value") == "2024-05-10"


def test_case_14_and_15_mobile_numbers(service, users_workbook):
    resp14 = service.process_chat(CompanyAIChatRequest(
        message="give me mobile numbers",
        document_id=users_workbook["id"],
        conversation_id="conv-case-14",
        user_role=UserRoleEnum.EMPLOYEE
    ))
    assert resp14.tool_results.get("column") == "MobileNo"

    resp15 = service.process_chat(CompanyAIChatRequest(
        message="give me mobile numbers as excel",
        document_id=users_workbook["id"],
        conversation_id="conv-case-15",
        user_role=UserRoleEnum.EMPLOYEE
    ))
    assert len(resp15.files) > 0
    assert "MobileNo" in resp15.files[0]["filename"]


def test_case_16_typo_moile_numbers(service, users_workbook):
    resp = service.process_chat(CompanyAIChatRequest(
        message="moile numbers only as exel",
        document_id=users_workbook["id"],
        conversation_id="conv-case-16",
        user_role=UserRoleEnum.EMPLOYEE
    ))
    assert len(resp.files) > 0
    assert "MobileNo" in resp.files[0]["filename"]


def test_case_17_synonym_contact_numbers(service, users_workbook):
    resp = service.process_chat(CompanyAIChatRequest(
        message="give me contact numbers",
        document_id=users_workbook["id"],
        conversation_id="conv-case-17",
        user_role=UserRoleEnum.EMPLOYEE
    ))
    assert resp.tool_results.get("column") == "MobileNo"


def test_case_18_email_addresses_as_excel(service, users_workbook):
    resp = service.process_chat(CompanyAIChatRequest(
        message="give me email addresses as excel",
        document_id=users_workbook["id"],
        conversation_id="conv-case-18",
        user_role=UserRoleEnum.EMPLOYEE
    ))
    assert len(resp.files) > 0
    assert "Email" in resp.files[0]["filename"]


def test_case_20_make_an_excel_sheet(service, users_workbook):
    conv_id = "conv-case-20"
    service.process_chat(CompanyAIChatRequest(
        message="who are all expired?",
        document_id=users_workbook["id"],
        conversation_id=conv_id,
        user_role=UserRoleEnum.EMPLOYEE
    ))

    resp20 = service.process_chat(CompanyAIChatRequest(
        message="make an Excel sheet",
        conversation_id=conv_id,
        user_role=UserRoleEnum.EMPLOYEE
    ))
    assert len(resp20.files) > 0
    assert resp20.tool_results.get("record_count") == 3


# ====================================================================
# Unseen Natural Language Variations Tests
# ====================================================================

def test_unseen_variations(service, users_workbook):
    # "which accounts are no longer valid?"
    r1 = service.process_chat(CompanyAIChatRequest(
        message="which accounts are no longer valid?",
        document_id=users_workbook["id"],
        conversation_id="conv-unseen-1",
        user_role=UserRoleEnum.EMPLOYEE
    ))
    assert r1.tool_results.get("count") == 3

    # "show people whose validity has ended"
    r2 = service.process_chat(CompanyAIChatRequest(
        message="show people whose validity has ended",
        document_id=users_workbook["id"],
        conversation_id="conv-unseen-2",
        user_role=UserRoleEnum.EMPLOYEE
    ))
    assert r2.tool_results.get("count") == 3

    # "put those expired users into a spreadsheet"
    r3 = service.process_chat(CompanyAIChatRequest(
        message="put those expired users into a spreadsheet",
        document_id=users_workbook["id"],
        conversation_id="conv-unseen-3",
        user_role=UserRoleEnum.EMPLOYEE
    ))
    assert len(r3.files) > 0
    assert r3.tool_results.get("record_count") == 3
