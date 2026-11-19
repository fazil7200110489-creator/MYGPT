"""Document Understanding, Tender Extraction, and Summarization Capability.

Processes PDF, Scanned PDF, Mixed PDF, DOCX, XLSX, Images, and TXT files for:
1. Automatic 25-field Tender Information Extraction across complete multi-page/multi-file bundles
2. Page-cited Tender Follow-Up Q&A
3. General full-document Summarization and Q&A without arbitrary 4,000-char truncation
"""

import os
from typing import Any, Dict, List, Optional
from loguru import logger

from backend.app.schemas.company_ai import StructuredRequest
from backend.app.schemas.capability import CapabilityEnum, CapabilityResult, TaskTypeEnum
from backend.app.services.capabilities.base_capability import BaseCapability
from backend.app.services.document_manager import document_manager
from backend.app.services.document_parser import document_parser
from backend.app.services.llm.answer_model_service import answer_model_service
from backend.app.services.tender.tender_extractor import (
    format_tender_extraction_markdown,
    tender_extractor,
)
from backend.app.services.tender_intelligence import (
    tender_intelligence_engine,
    intelligence_report_builder,
    TenderConsultantReport,
)
from backend.app.services.tender.tender_section_retriever import (
    collect_page_records,
    format_pages_for_prompt,
    retrieve_evidence_for_query,
)


class DocumentCapability(BaseCapability):
    """Document Intelligence, Tender Extraction, and Text QA Specialist."""

    def __init__(self):
        super().__init__(CapabilityEnum.DOCUMENT.value)

    def can_handle(self, request: StructuredRequest, context: Optional[Any] = None) -> bool:
        cap = (request.capability or "").upper()
        if cap in ("DOCUMENT", "DOC", "TENDER"):
            return True
        if request.task_type in (
            TaskTypeEnum.DOCUMENT_SUMMARY.value,
            TaskTypeEnum.DOCUMENT_QA.value,
            TaskTypeEnum.DOCUMENT_EXTRACTION.value,
        ):
            return True

        active_doc = request.active_document or (context.active_document if context else None)
        if isinstance(active_doc, dict):
            if str(active_doc.get("document_type", "")).upper() == "TENDER":
                return True
            ext = (active_doc.get("extension") or active_doc.get("file_type") or "").lower()
            if ext in (".pdf", ".docx", ".doc", ".txt", ".md"):
                return True

        return False

    def _collect_active_documents(
        self, request: StructuredRequest, context: Optional[Any]
    ) -> List[Dict[str, Any]]:
        """Resolves single active document or multi-file session bundle with persisted pages."""
        docs: List[Dict[str, Any]] = []
        seen_ids: set = set()

        def _add_doc(meta: Optional[Dict[str, Any]]) -> None:
            if not isinstance(meta, dict):
                return
            did = str(meta.get("document_id") or meta.get("id") or "")
            if did and did in seen_ids:
                return
            # Refresh from document_manager if pages are missing from thin dict
            if did and not meta.get("pages"):
                fresh = document_manager.get_document(did)
                if fresh:
                    meta = fresh
            if did:
                seen_ids.add(did)
            docs.append(meta)

        is_pkg = bool(getattr(context, "is_explicit_package", False)) if context is not None else False

        # 1. Top Precedence: Explicit active document in current request
        req_doc = getattr(request, "active_document", None)
        explicit_doc: Optional[Dict[str, Any]] = None
        if isinstance(req_doc, dict):
            explicit_doc = req_doc
        elif isinstance(req_doc, str) and req_doc.strip():
            explicit_doc = document_manager.get_document(req_doc.strip())

        if explicit_doc:
            _add_doc(explicit_doc)
            # Strict Isolation: For non-package evaluation, isolate strictly to the requested document.
            # Never allow stale documents from previous conversation context to contaminate this evaluation.
            if not is_pkg:
                return self._hydrate_pages_if_needed(docs)
            # If explicit package, pull remaining documents in the package
            if context is not None:
                doc_ids = getattr(context, "active_document_ids", None) or []
                for did in doc_ids:
                    if did != (explicit_doc.get("id") or explicit_doc.get("document_id")):
                        _add_doc(document_manager.get_document(did))
            return self._hydrate_pages_if_needed(docs)

        # 2. Context fallback when no explicit request document was specified
        if context is not None:
            doc_ids = getattr(context, "active_document_ids", None) or []
            active_type = str(getattr(context, "active_document_type", "") or "").upper()
            if doc_ids and is_pkg and (active_type == "TENDER" or len(doc_ids) > 1):
                for did in doc_ids:
                    _add_doc(document_manager.get_document(did))
            elif getattr(context, "active_document", None):
                _add_doc(getattr(context, "active_document", None))
            elif getattr(context, "active_document_id", None):
                _add_doc(document_manager.get_document(context.active_document_id))

        return self._hydrate_pages_if_needed(docs)

    def _hydrate_pages_if_needed(self, docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Ensures every collected document has parsed pages and a reliable SHA-256 file_hash."""
        import hashlib
        hydrated: List[Dict[str, Any]] = []
        for meta in docs:
            if not meta.get("pages") and meta.get("file_path") and os.path.exists(str(meta["file_path"])):
                try:
                    parsed = document_parser.parse(meta["file_path"])
                    meta = dict(meta)
                    meta["pages"] = parsed.get("pages", [])
                    meta["extracted_text"] = parsed.get("text", meta.get("extracted_text", ""))
                    meta["total_pages"] = parsed.get("total_pages", len(meta["pages"]))
                    meta["ocr_pages"] = parsed.get("ocr_pages", [])
                    meta["unreadable_pages"] = parsed.get("unreadable_pages", [])
                    meta["ocr_engine"] = parsed.get("ocr_engine")
                    if parsed.get("file_hash") and not meta.get("file_hash"):
                        meta["file_hash"] = parsed["file_hash"]
                except Exception as pe:
                    meta = dict(meta)
                    meta["parse_error"] = str(pe)

            # Ensure SHA-256 file_hash is always present
            if not meta.get("file_hash"):
                meta = dict(meta)
                if meta.get("file_path") and os.path.exists(str(meta["file_path"])):
                    try:
                        with open(str(meta["file_path"]), "rb") as f:
                            meta["file_hash"] = hashlib.sha256(f.read()).hexdigest()
                    except Exception:
                        pass
                if not meta.get("file_hash"):
                    txt = meta.get("extracted_text") or ""
                    meta["file_hash"] = hashlib.sha256(txt.encode("utf-8", errors="ignore")).hexdigest()

            hydrated.append(meta)
        return hydrated

    def _is_tender_bundle(self, docs: List[Dict[str, Any]], query: str, context: Optional[Any]) -> bool:
        from backend.app.services.tender_intelligence.document_validator import is_authentic_tender_document
        is_tender, _ = is_authentic_tender_document(docs)
        return is_tender

    def _is_consultant_trigger(self, query: str) -> bool:
        q = (query or "").strip().lower()
        if not q or q.startswith("uploaded "):
            return True
        return any(
            phrase in q
            for phrase in (
                "consultant", "ai consultant", "tender consultant", "consultant analysis",
                "consultant report", "bid strategy", "evaluate tender", "evaluate this tender",
                "tender evaluation", "eligibility analysis", "risk analysis", "risk and contradiction",
                "compliance matrix", "action roadmap", "tender intelligence", "tender dossier",
                "analyze this tender", "analyse this tender", "tender summary", "briefing",
                "executive briefing", "summarize", "summary", "overview", "review this tender",
            )
        )

    def _is_raw_fields_trigger(self, query: str) -> bool:
        q = (query or "").strip().lower()
        return any(
            phrase in q
            for phrase in (
                "25 fields", "25 field", "raw fields", "raw extraction", "field table",
                "raw table", "raw 25", "legacy extraction", "i-bid fields", "extract fields",
                "show extracted fields",
            )
        )

    def _is_extraction_trigger(self, query: str) -> bool:
        return self._is_raw_fields_trigger(query)

    def execute(self, request: StructuredRequest, context: Optional[Any] = None) -> CapabilityResult:
        query = (request.user_request or request.normalized_message or "").strip()
        task_id = getattr(request, "task_id", None)
        logger.info(f"[DOCUMENT_CAPABILITY] Processing query: {query!r} (task_id={task_id})")

        docs = self._collect_active_documents(request, context)
        if not docs:
            file_path, filename = self._resolve_doc_path(request, context)
            if file_path:
                docs = [{"filename": filename or os.path.basename(file_path), "file_path": file_path}]
                docs = self._collect_active_documents_from_paths(docs)

        if not docs:
            return CapabilityResult(
                success=False,
                capability=self.capability_name,
                operation="NO_DOCUMENT",
                task_type=TaskTypeEnum.DOCUMENT_QA.value,
                answer="No document is currently active. Please attach or upload a tender, PDF, Word, Excel, or image file to analyze.",
                answer_type="error",
                confidence=1.0,
            )

        try:
            # 1. Tender extraction & Tender QA flow
            if self._is_tender_bundle(docs, query, context):
                source_names = [str(d.get("filename") or "uploaded_tender") for d in docs]
                cached_extraction = None
                cached_intelligence = None
                for d in docs:
                    sd = d.get("structured_data")
                    if isinstance(sd, dict) and sd.get("tender_extraction"):
                        cached_extraction = sd["tender_extraction"]
                        break
                    if isinstance(sd, dict):
                        if sd.get("tender_extraction") and not cached_extraction:
                            cached_extraction = sd["tender_extraction"]
                        if sd.get("tender_intelligence") and not cached_intelligence:
                            cached_intelligence = sd["tender_intelligence"]

                # A. Tender Consultant Trigger (Higher Intelligence Level)
                if self._is_consultant_trigger(query) or (request.operation or "").upper() in (
                    "TENDER_CONSULTANT", "CONSULTANT", "TENDER_INTELLIGENCE"
                ):
                    report = tender_intelligence_engine.evaluate_tender(docs, user_query=query, task_id=task_id)
                    report_dict = report.model_dump()

                    # Cache structured intelligence back on primary active doc metadata in memory/store
                    if context and isinstance(getattr(context, "active_document", None), dict):
                        sd = context.active_document.setdefault("structured_data", {})
                        if isinstance(sd, dict):
                            sd["tender_intelligence"] = report_dict
                        try:
                            prim_id = context.active_document.get("document_id") or context.active_document.get("id")
                            if prim_id:
                                db = document_manager._read_metadata()
                                if prim_id in db and isinstance(db[prim_id], dict):
                                    db[prim_id].setdefault("structured_data", {})["tender_intelligence"] = report_dict
                                    document_manager._write_metadata(db)
                        except Exception:
                            pass

                    initial_ans = report.initial_conversational_summary or report.consultant_briefing_markdown or report.executive_summary_markdown
                    suggestions = report.suggested_questions or intelligence_report_builder.generate_suggested_questions(report)

                    return CapabilityResult(
                        success=True,
                        capability=self.capability_name,
                        operation="TENDER_CONSULTANT",
                        task_type=TaskTypeEnum.DOCUMENT_EXTRACTION.value,
                        answer=initial_ans,
                        answer_type="tender_intelligence",
                        suggested_questions=suggestions,
                        structured_data={
                            "tender_intelligence": report_dict,
                            "suggested_questions": suggestions,
                            "has_detailed_analysis": True,
                            "tender_extraction": cached_extraction,
                        },
                        sources=source_names,
                        confidence=0.96,
                    )

                # B. Explicit 25-Field Tender Extraction Trigger (Only when requested)
                if self._is_raw_fields_trigger(query) or (request.operation or "").upper() in ("EXTRACT_FIELDS", "RAW_EXTRACTION"):
                    nas_path = next((d.get("nas_path") for d in docs if d.get("nas_path")), None)
                    result = tender_extractor.extract_from_documents(docs, nas_path=nas_path, use_llm=True)
                    result_dict = result.model_dump()
                    markdown_report = format_tender_extraction_markdown(result)

                    # Cache structured extraction back on primary active doc metadata in memory/store
                    if context and isinstance(getattr(context, "active_document", None), dict):
                        sd = context.active_document.setdefault("structured_data", {})
                        if isinstance(sd, dict):
                            sd["tender_extraction"] = result_dict
                        try:
                            prim_id = context.active_document.get("document_id") or context.active_document.get("id")
                            if prim_id:
                                db = document_manager._read_metadata()
                                if prim_id in db and isinstance(db[prim_id], dict):
                                    db[prim_id].setdefault("structured_data", {})["tender_extraction"] = result_dict
                                    document_manager._write_metadata(db)
                        except Exception:
                            pass

                    return CapabilityResult(
                        success=True,
                        capability=self.capability_name,
                        operation="TENDER_EXTRACTION",
                        task_type=TaskTypeEnum.DOCUMENT_EXTRACTION.value,
                        answer=markdown_report,
                        answer_type="tender_extraction",
                        structured_data={"tender_extraction": result_dict},
                        sources=source_names,
                        confidence=0.95,
                    )

                # C. Tender Follow-Up Q&A across complete document pages/sheets
                cached_rep = None
                if cached_intelligence:
                    try:
                        cached_rep = TenderConsultantReport(**cached_intelligence)
                    except Exception:
                        cached_rep = None

                qa_res = tender_intelligence_engine.answer_consultant_question(
                    docs, query, cached_report=cached_rep, task_id=task_id
                )
                answer = qa_res[0]
                cited_sources = qa_res[1]
                follow_up_suggestions = getattr(qa_res, "suggested_questions", []) or (
                    intelligence_report_builder.generate_suggested_questions(cached_rep, last_query=query, last_answer=answer)
                    if cached_rep else []
                )

                return CapabilityResult(
                    success=True,
                    capability=self.capability_name,
                    operation="TENDER_QA",
                    task_type=TaskTypeEnum.DOCUMENT_QA.value,
                    answer=answer,
                    answer_type="text",
                    suggested_questions=follow_up_suggestions,
                    structured_data={
                        "cited_sources": cited_sources,
                        "suggested_questions": follow_up_suggestions,
                        "tender_intelligence": cached_intelligence,
                    },
                    sources=source_names,
                    confidence=0.92,
                )

            # If user explicitly requested tender consultant/extraction but document is NOT a tender, reject immediately
            if self._is_consultant_trigger(query) or self._is_raw_fields_trigger(query) or (request.operation or "").upper() in (
                "TENDER_CONSULTANT", "CONSULTANT", "TENDER_INTELLIGENCE", "TENDER_EXTRACTION", "EXTRACT_FIELDS"
            ):
                if task_id:
                    processing_progress_tracker.fail_task(
                        task_id,
                        "validating_document",
                        "This document does not appear to be a tender document. Please upload a valid tender or bid document."
                    )
                return CapabilityResult(
                    success=False,
                    capability=self.capability_name,
                    operation="REJECTED_NON_TENDER",
                    task_type=TaskTypeEnum.DOCUMENT_QA.value,
                    answer="This document does not appear to be a tender document. Please upload a valid tender or bid document.",
                    answer_type="error",
                    confidence=1.0,
                )

            # 2. General (Non-Tender) Full-Document Summarization & Page-Retrieved QA
            primary_doc = docs[0]
            filename = str(primary_doc.get("filename") or "document")
            records = collect_page_records(docs)
            if not records:
                return CapabilityResult(
                    success=False,
                    capability=self.capability_name,
                    operation="EMPTY_TEXT",
                    task_type=TaskTypeEnum.DOCUMENT_QA.value,
                    answer=f"Could not extract readable text from `{filename}`.",
                    answer_type="error",
                    confidence=0.9,
                )

            if any(w in query.lower() for w in ("summarize", "summary", "overview", "brief")) or query.lower().startswith("uploaded "):
                full_context = format_pages_for_prompt(records, max_chars=2600)
                summary_prompt = (
                    f"Summarize the following document clearly with main sections and key takeaways:\n\n"
                    f"Document: {filename}\n\nContent:\n{full_context}"
                )
                summary_ans = answer_model_service.generate_general_response(summary_prompt, max_tokens=200)
                return CapabilityResult(
                    success=True,
                    capability=self.capability_name,
                    operation="SUMMARY",
                    task_type=TaskTypeEnum.DOCUMENT_SUMMARY.value,
                    answer=summary_ans,
                    answer_type="text",
                    sources=[filename],
                    confidence=0.95,
                )

            relevant_context, cited = retrieve_evidence_for_query(records, query, max_pages=5, max_chars=2600)
            prompt = (
                f"Answer the user query strictly using the supplied document context (cite page numbers when available):\n\n"
                f"Document: {filename}\n\nContent:\n{relevant_context}\n\nUser Question: {query}"
            )
            qa_ans = answer_model_service.generate_general_response(prompt)
            return CapabilityResult(
                success=True,
                capability=self.capability_name,
                operation="DOCUMENT_QA",
                task_type=TaskTypeEnum.DOCUMENT_QA.value,
                answer=qa_ans,
                answer_type="text",
                structured_data={"cited_sources": cited},
                sources=[filename],
                confidence=0.95,
            )

        except ValueError as ve:
            if "not appear to be a tender" in str(ve).lower():
                return CapabilityResult(
                    success=False,
                    capability=self.capability_name,
                    operation="REJECTED_NON_TENDER",
                    task_type=TaskTypeEnum.DOCUMENT_QA.value,
                    answer="This document does not appear to be a tender document. Please upload a valid tender or bid document.",
                    answer_type="error",
                    confidence=1.0,
                )
            logger.error(f"[DOCUMENT_CAPABILITY] ValueError: {ve}")
            return CapabilityResult(
                success=False,
                capability=self.capability_name,
                operation="ERROR",
                task_type=TaskTypeEnum.DOCUMENT_QA.value,
                answer=f"Document analysis error: {str(ve)}",
                answer_type="error",
                confidence=0.5,
            )
        except Exception as e:
            logger.error(f"[DOCUMENT_CAPABILITY] Execution error: {e}")
            return CapabilityResult(
                success=False,
                capability=self.capability_name,
                operation="ERROR",
                task_type=TaskTypeEnum.DOCUMENT_QA.value,
                answer=f"Document analysis error: {str(e)}",
                answer_type="error",
                confidence=0.5,
            )

    def _collect_active_documents_from_paths(self, docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for d in docs:
            fp = d.get("file_path")
            if fp and os.path.exists(fp):
                parsed = document_parser.parse(fp)
                out.append({
                    **d,
                    "pages": parsed.get("pages", []),
                    "extracted_text": parsed.get("text", ""),
                    "total_pages": parsed.get("total_pages", 1),
                    "ocr_pages": parsed.get("ocr_pages", []),
                    "unreadable_pages": parsed.get("unreadable_pages", []),
                })
        return out

    def _resolve_doc_path(self, request: StructuredRequest, context: Optional[Any]) -> tuple[Optional[str], Optional[str]]:
        doc_id = getattr(request, "active_document", None)
        if not doc_id and context:
            doc_id = getattr(context, "active_document_id", None) or getattr(context, "active_document", None)

        if isinstance(doc_id, dict):
            return doc_id.get("file_path") or doc_id.get("path"), doc_id.get("filename")

        if doc_id:
            doc_meta = document_manager.get_document(doc_id)
            if doc_meta:
                return doc_meta.get("file_path"), doc_meta.get("filename")

        return None, None
