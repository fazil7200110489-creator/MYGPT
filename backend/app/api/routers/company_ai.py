"""API Router for Company AI Central Platform.
Provides endpoints for natural-language request routing, department metadata, and capability discovery.
"""

import re
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form, Query
from loguru import logger

from backend.app.schemas.department import (
    RoutingDecision, RouteRequest, DepartmentInfo
)
from backend.app.schemas.security import KnowledgeSearchRequest
from backend.app.schemas.company_ai import (
    CompanyAIChatRequest, CompanyAIChatResponse, AIStatusResponse
)
from backend.app.services.routing.intent_router import intent_router
from backend.app.departments.department_registry import department_registry
from backend.app.services.rag.department_rag import department_rag
from backend.app.services.company_ai_service import company_ai_service
from backend.app.services.document_manager import document_manager
from backend.app.services.document_parser import document_parser
from backend.app.services.conversation_context_manager import conversation_context_manager
from backend.app.services.excel.workbook_detector import workbook_detector
from backend.app.services.excel.excel_aggregator import excel_aggregator

router = APIRouter(prefix="/company", tags=["Company AI"])


@router.post("/route", response_model=RoutingDecision)
async def route_company_request(req: RouteRequest) -> RoutingDecision:
    """Analyzes a natural language user request and determines target department,
    specific intent, required tools, and permission level without executing any tools.
    """
    try:
        decision = intent_router.route(req)
        logger.info(
            f"Company AI Route Decision: Dept={decision.department}, "
            f"Intent={decision.intent}, Confidence={decision.confidence:.2f}"
        )
        return decision
    except Exception as e:
        logger.error(f"Error in Company AI router: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Intent routing failure: {str(e)}"
        )


@router.post("/chat", response_model=CompanyAIChatResponse)
async def chat_with_company_ai(req: CompanyAIChatRequest) -> CompanyAIChatResponse:
    """Primary chat endpoint for Company AI.
    Executes: MYGPT Router -> RBAC Permission Check -> Department Workflow / Deterministic Tools ->
    Verified Result Contract -> Local Qwen Answer Formatting -> Final Response.
    """
    try:
        return company_ai_service.process_chat(req)
    except Exception as e:
        logger.error(f"Company AI chat error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Company AI processing failed: {str(e)}"
        )


@router.get("/ai/status", response_model=AIStatusResponse)
async def get_ai_status() -> AIStatusResponse:
    """Returns local AI status and answer model availability."""
    return company_ai_service.get_ai_status()


@router.get("/departments", response_model=List[DepartmentInfo])
async def list_company_departments() -> List[DepartmentInfo]:
    """Returns metadata for all available company departments."""
    return department_registry.list_departments()


@router.post("/knowledge/search")
async def search_department_knowledge(req: KnowledgeSearchRequest) -> List[Dict[str, Any]]:
    """(Development/Test Endpoint) Performs department-scoped, permission-filtered knowledge retrieval."""
    try:
        results = department_rag.retrieve(
            query=req.query,
            department=req.department,
            user_role=req.user_role or "EMPLOYEE",
            user_id=req.user_id or "dev_user",
            top_k=req.top_k
        )
        return results
    except Exception as e:
        logger.error(f"Error searching department knowledge: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Knowledge retrieval failed: {str(e)}"
        )


@router.get("/conversations")
async def list_company_conversations() -> List[Dict[str, Any]]:
    """Retrieves all persistent conversations sorted by most recent."""
    return company_ai_service.list_conversations()


@router.get("/conversations/{conversation_id}")
async def get_company_conversation(conversation_id: str) -> Dict[str, Any]:
    """Retrieves details, messages, and document references for a specific conversation."""
    return company_ai_service.get_conversation(conversation_id)


@router.delete("/conversations/{conversation_id}")
async def delete_company_conversation(conversation_id: str) -> Dict[str, Any]:
    """Deletes a conversation and its persisted history."""
    success = company_ai_service.delete_conversation(conversation_id)
    return {"success": success, "conversation_id": conversation_id}


@router.get("/chat/history")
async def get_chat_history(session_id: str = "default_session") -> List[Dict[str, Any]]:
    """Retrieves conversation history for a specific session."""
    return company_ai_service.get_history(session_id)


@router.post("/chat/reset")
async def reset_chat_history(session_id: str = "default_session") -> Dict[str, Any]:
    """Clears conversation history for a specific session."""
    company_ai_service.clear_history(session_id)
    return {"success": True, "message": f"Session '{session_id}' reset successfully."}


def _process_single_upload(
    filename: str,
    content_bytes: bytes,
    session_id: str,
    user_role: str = "EMPLOYEE",
    user_id: str = "dev_user",
    department: Optional[str] = None
) -> Dict[str, Any]:
    """Internal helper to parse, classify, index, and register a single uploaded document in context."""
    # 1. Save document via document_manager
    doc_meta = document_manager.upload_document(filename, content_bytes)
    doc_id = doc_meta["id"]
    filepath = doc_meta["file_path"]
    file_type = doc_meta["file_type"]

    # 2. Extract text via document_parser with safe fallback
    extracted_text = ""
    try:
        parsed = document_parser.parse(filepath)
        extracted_text = parsed.get("text", "")
    except Exception as parse_err:
        logger.warning(f"document_parser failed on {filename}: {parse_err}, attempting fallback")
        if file_type in [".txt", ".md", ".csv", ".json"]:
            extracted_text = content_bytes.decode("utf-8", errors="ignore")
        elif file_type == ".pdf":
            try:
                from pypdf import PdfReader
                import io
                reader = PdfReader(io.BytesIO(content_bytes))
                extracted_text = "\n".join([p.extract_text() or "" for p in reader.pages])
            except Exception:
                extracted_text = f"Uploaded PDF document: {filename}"
        else:
            extracted_text = f"Uploaded document: {filename}"

    # 3. Classify document type and extract structured fields purely from authentic text
    text_lower = extracted_text.lower()
    file_lower = filename.lower()
    doc_type = "GENERAL_DOCUMENT"
    structured_data: Dict[str, Any] = {}

    # Excel / Spreadsheet detection
    if file_type in [".xlsx", ".xls", ".csv"] or filename.lower().endswith((".xlsx", ".xls", ".csv")) or "sprint" in file_lower or "spreadsheet" in file_lower:
        doc_type = "EXCEL"
        try:
            inspection = excel_aggregator.inspect_workbook(filepath)
            wb_type = inspection.get("workbook_type", "GENERIC")
            structured_data = {
                "document_type": "EXCEL",
                "workbook_type": wb_type,
                "worksheet_names": inspection.get("worksheet_names", []),
                "headers": inspection.get("headers", []),
                "owners": inspection.get("owners", []),
                "total_rows": inspection.get("total_rows", 0),
                "total_valid_rows": inspection.get("total_valid_rows", 0),
                "summary": inspection.get("text_summary", "")
            }
            extracted_text = (
                f"Excel Workbook ({wb_type}): {filename}\n"
                f"Worksheets: {', '.join(inspection.get('worksheet_names', []))}\n"
                f"Columns: {', '.join(inspection.get('headers', []))[:200]}\n"
                f"Total Records: {inspection.get('total_valid_rows', inspection.get('total_rows', 0))}\n\n"
                f"{inspection.get('text_summary', '')}"
            )
        except Exception as excel_err:
            logger.warning(f"excel_aggregator inspection failed for {filename}: {excel_err}")
            structured_data = {
                "document_type": "EXCEL",
                "workbook_type": "GENERIC",
                "worksheet_names": [],
                "headers": [],
                "owners": [],
                "total_rows": 0,
                "total_valid_rows": 0
            }
    # Resume / CV detection
    elif any(k in file_lower for k in ["resume", "cv", "curriculum_vitae"]) or any(k in text_lower for k in [
        "curriculum vitae", "education", "work experience", "professional experience",
        "technical skills", "career summary", "academic background", "projects", "certifications"
    ]):
        doc_type = "RESUME"
        name_m = re.search(r'^(?:name[\s:]*)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', extracted_text.strip())
        email_m = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', extracted_text)
        phone_m = re.search(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', extracted_text)
        
        structured_data = {
            "document_type": "RESUME",
            "candidate_name": name_m.group(1).strip() if name_m else filename.rsplit('.', 1)[0],
            "email": email_m.group(0) if email_m else None,
            "phone": phone_m.group(0) if phone_m else None,
        }
    elif any(k in text_lower for k in ["invoice", "inv-", "bill to", "due date", "amount due", "subtotal", "tax"]):
        doc_type = "INVOICE"
        inv_num_m = re.search(r'(?:invoice\s*#?|inv[\s#:]*)([a-zA-Z0-9\-]+)', extracted_text, re.IGNORECASE)
        vendor_m = re.search(r'(?:from|vendor|company|billed by)[\s:]*([^\n,]+)', extracted_text, re.IGNORECASE)
        subtotal_m = re.search(r'\b(?:subtotal|sub-total)\b[\s:]*\$?([0-9,]+\.?[0-9]*)', extracted_text, re.IGNORECASE)
        tax_m = re.search(r'\b(?:tax|vat|gst)\b[\s:]*\$?([0-9,]+\.?[0-9]*)', extracted_text, re.IGNORECASE)
        total_m = re.search(r'\b(?:total amount|grand total|total due|amount due|balance due|total)\b[\s:]*\$?([0-9,]+\.?[0-9]*)', extracted_text, re.IGNORECASE)
        date_m = re.search(r'(?:date|invoice date)[\s:]*([0-9]{1,4}[-/\.][0-9]{1,2}[-/\.][0-9]{1,4}|[A-Za-z]+ \d{1,2},? \d{4})', extracted_text, re.IGNORECASE)

        inv_num = inv_num_m.group(1).strip() if inv_num_m else None
        vendor = vendor_m.group(1).strip() if vendor_m else None
        date_val = date_m.group(1).strip() if date_m else None

        total_val = None
        if total_m:
            try:
                total_val = float(total_m.group(1).replace(",", ""))
            except Exception:
                pass

        subtotal_val = None
        if subtotal_m:
            try:
                subtotal_val = float(subtotal_m.group(1).replace(",", ""))
            except Exception:
                pass

        tax_val = None
        if tax_m:
            try:
                tax_val = float(tax_m.group(1).replace(",", ""))
            except Exception:
                pass

        structured_data = {
            "invoice_number": inv_num,
            "vendor": vendor,
            "date": date_val,
            "total_amount": total_val,
            "subtotal": subtotal_val,
            "tax": tax_val,
            "document_type": "INVOICE"
        }
    elif any(k in text_lower for k in ["offer of employment", "we are pleased to offer you the position of", "employment offer letter", "offer letter template"]):
        doc_type = "OFFER_LETTER_TEMPLATE"
        cand_m = re.search(r'(?:dear|candidate|name)[\s:]*([A-Za-z\s]+)(?:,|\n)', extracted_text, re.IGNORECASE)
        role_m = re.search(r'(?:position|role|title)[\s:]*([^\n,]+)', extracted_text, re.IGNORECASE)
        sal_m = re.search(r'(?:salary|compensation|annual base)[\s:]*\$?([0-9,]+)', extracted_text, re.IGNORECASE)
        start_m = re.search(r'(?:start date|joining date|effective date)[\s:]*([^\n,]+)', extracted_text, re.IGNORECASE)

        structured_data = {
            "candidate_name": cand_m.group(1).strip() if cand_m else None,
            "position": role_m.group(1).strip() if role_m else None,
            "salary": sal_m.group(1).strip() if sal_m else None,
            "start_date": start_m.group(1).strip() if start_m else None,
            "document_type": "OFFER_LETTER_TEMPLATE"
        }
    elif any(k in text_lower for k in ["expense report", "travel expense", "reimbursement", "expenditure report"]):
        doc_type = "EXPENSE_REPORT"
        structured_data = {
            "report_type": "Expense Report",
            "document_type": "EXPENSE_REPORT"
        }
    elif any(k in text_lower for k in ["leave policy", "pto policy", "code of conduct", "attendance policy", "employee handbook", "hr policy", "casual leave", "sick leave", "earned leave", "hr operations", "human resources policy", "leave management"]) or any(k in filename.lower() for k in ["hr_ops", "hr_policy", "leave_policy", "handbook"]):
        doc_type = "HR_POLICY"
        structured_data = {
            "policy_name": filename,
            "document_type": "HR_POLICY"
        }

    # 4. Save enhanced metadata
    doc_meta["document_type"] = doc_type
    doc_meta["extracted_text"] = extracted_text
    doc_meta["structured_data"] = structured_data
    
    # Persist updated doc metadata
    db = document_manager._read_metadata()
    db[doc_id] = doc_meta
    document_manager._write_metadata(db)

    # 5. Set as active document in conversation state
    conversation_context_manager.set_active_document(session_id, doc_meta)
    logger.info(f"Successfully processed upload: {filename} (ID: {doc_id}, Type: {doc_type}) for session {session_id}")

    return {
        "success": True,
        "doc_id": doc_id,
        "id": doc_id,
        "filename": filename,
        "file_type": file_type,
        "document_type": doc_type,
        "structured_data": structured_data,
        "extracted_text_preview": extracted_text[:300] if extracted_text else "",
        "message": f"Document '{filename}' uploaded and indexed successfully."
    }


@router.post("/upload-multiple")
async def upload_multiple_company_documents(
    files: List[UploadFile] = File(...),
    session_id: str = Form("default_session"),
    user_role: str = Form("EMPLOYEE"),
    user_id: str = Form("dev_user"),
    department: Optional[str] = Form(None)
) -> Dict[str, Any]:
    """Uploads multiple company documents simultaneously and registers all of them into active conversation context."""
    try:
        results = []
        for file in files:
            content_bytes = await file.read()
            fname = file.filename or "uploaded_file.bin"
            res = _process_single_upload(fname, content_bytes, session_id, user_role, user_id, department)
            results.append(res)

        return {
            "success": True,
            "count": len(results),
            "documents": results,
            "session_id": session_id,
            "message": f"Successfully uploaded and indexed {len(results)} documents for session '{session_id}'."
        }
    except Exception as e:
        logger.error(f"Failed in upload-multiple: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Multiple upload failed: {str(e)}"
        )


@router.post("/upload")
async def upload_company_document(
    file: UploadFile = File(...),
    session_id: str = Form("default_session"),
    user_role: str = Form("EMPLOYEE"),
    user_id: str = Form("dev_user"),
    department: Optional[str] = Form(None)
) -> Dict[str, Any]:
    """Uploads a single company document and registers it in the active conversation context."""
    try:
        content_bytes = await file.read()
        filename = file.filename or "uploaded_file.bin"
        return _process_single_upload(filename, content_bytes, session_id, user_role, user_id, department)
    except Exception as e:
        logger.error(f"Failed to upload document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload processing failed: {str(e)}"
        )


@router.get("/files/{file_id}/download")
async def download_company_file(
    file_id: str,
    user_role: str = Query("EMPLOYEE"),
    user_id: str = Query("dev_user")
):
    """Downloads a system-generated or uploaded file after verifying RBAC permissions."""
    import os
    from fastapi.responses import FileResponse

    # 1. Check generated files
    meta = company_ai_service.get_generated_file(file_id)
    if meta:
        required_role = meta.get("role_required", "EMPLOYEE")
        filepath = meta.get("file_path", "")
        filename = meta.get("filename", f"{file_id}.xlsx")
        
        # Enforce RBAC for role-restricted files (e.g. Finance expense reports)
        if required_role in ["FINANCE_MANAGER", "ADMIN"] and user_role not in ["FINANCE_MANAGER", "ADMIN"]:
            logger.warning(f"Download denied for file {file_id}: User role {user_role} lacks {required_role}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Downloading this file requires {required_role} role."
            )
            
        if not os.path.exists(filepath):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File binary not found on disk."
            )

        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if filename.endswith(".xlsx") else "application/octet-stream"
        return FileResponse(
            path=filepath,
            filename=filename,
            media_type=media_type
        )

    # 2. Check uploaded documents
    doc_meta = document_manager.get_document(file_id)
    if doc_meta:
        filepath = doc_meta.get("file_path", "")
        filename = doc_meta.get("filename", f"{file_id}")
        if not os.path.exists(filepath):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Uploaded document not found on disk."
            )
        return FileResponse(
            path=filepath,
            filename=filename,
            media_type="application/octet-stream"
        )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"File ID '{file_id}' not found."
    )


@router.get("/files/{file_id}/preview")
async def preview_company_file(
    file_id: str,
    user_role: str = Query("EMPLOYEE"),
    user_id: str = Query("dev_user"),
    max_rows: int = Query(25, ge=1, le=100)
):
    """Returns structured metadata and sample rows for in-browser Excel preview without full file download."""
    import os
    import openpyxl

    # 1. Check generated files
    filepath = ""
    filename = ""
    required_role = "EMPLOYEE"

    meta = company_ai_service.get_generated_file(file_id)
    if meta:
        required_role = meta.get("role_required", "EMPLOYEE")
        filepath = meta.get("file_path", "")
        filename = meta.get("filename", f"{file_id}.xlsx")
    else:
        doc_meta = document_manager.get_document(file_id)
        if doc_meta:
            filepath = doc_meta.get("file_path", "")
            filename = doc_meta.get("filename", f"{file_id}")
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File ID '{file_id}' not found.")

    if required_role in ["FINANCE_MANAGER", "ADMIN"] and user_role not in ["FINANCE_MANAGER", "ADMIN"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    if not os.path.exists(filepath):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk.")

    if not filename.lower().endswith((".xlsx", ".xls")):
        return {
            "file_id": file_id,
            "filename": filename,
            "file_type": "generic",
            "sheets": [],
            "row_count": 0,
            "column_count": 0,
            "columns": [],
            "preview_rows": []
        }

    try:
        wb = openpyxl.load_workbook(filepath, data_only=True, read_only=True)
        sheet_names = wb.sheetnames
        active_sheet_name = sheet_names[0] if sheet_names else "Sheet1"
        ws = wb[active_sheet_name]

        rows_iter = ws.iter_rows(values_only=True)
        header_row = next(rows_iter, None)

        if not header_row:
            wb.close()
            return {
                "file_id": file_id,
                "filename": filename,
                "file_type": "xlsx",
                "sheets": sheet_names,
                "active_sheet": active_sheet_name,
                "row_count": 0,
                "column_count": 0,
                "columns": [],
                "preview_rows": []
            }

        headers = [str(h).strip() if h is not None else f"Col_{i+1}" for i, h in enumerate(header_row)]
        preview_rows = []
        total_rows = 0

        for r in rows_iter:
            total_rows += 1
            if len(preview_rows) < max_rows and any(v is not None for v in r):
                row_dict = {}
                for col_idx, col_name in enumerate(headers):
                    val = r[col_idx] if col_idx < len(r) else ""
                    row_dict[col_name] = str(val) if val is not None else ""
                preview_rows.append(row_dict)

        wb.close()

        return {
            "file_id": file_id,
            "filename": filename,
            "file_type": "xlsx",
            "sheets": sheet_names,
            "active_sheet": active_sheet_name,
            "row_count": total_rows,
            "column_count": len(headers),
            "columns": headers,
            "preview_rows": preview_rows
        }
    except Exception as e:
        logger.error(f"Failed to generate file preview for {file_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Preview generation failed: {str(e)}")
