import sys
import openpyxl
import os

from backend.app.schemas.company_ai import CompanyAIChatRequest
from backend.app.schemas.security import UserRoleEnum
from backend.app.services.company_ai_service import CompanyAIService
from backend.app.services.document_manager import document_manager
from backend.app.services.conversation_context_manager import conversation_context_manager

print("1. Creating test workbook...")
wb = openpyxl.Workbook()
ws = wb.active
ws.title = "UserAccounts"
headers = ["UserName", "FirstName", "VleId", "MobileNo", "Email", "Expiry_Date"]
ws.append(headers)
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

file_path = "scratch_test_wb.xlsx"
wb.save(file_path)

with open(file_path, "rb") as f:
    doc_meta = document_manager.upload_document("scratch_user_accounts.xlsx", f.read())

print("2. Doc meta uploaded:", doc_meta["id"])
service = CompanyAIService()

print("3. Executing process_chat for: 'what are the columns available?'...")
resp = service.process_chat(CompanyAIChatRequest(
    message="what are the columns available?",
    document_id=doc_meta["id"],
    conversation_id="conv-debug-1",
    user_role=UserRoleEnum.EMPLOYEE
))

print("4. Response answer:", resp.answer)
print("5. Response intent:", resp.intent)
