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

        if context is not None:
            doc_ids = getattr(context, "active_document_ids", None) or []
            active_type = str(getattr(context, "active_document_type", "") or "").upper()
            # When active bundle is a TENDER or multiple files were uploaded together, include batch docs
            if doc_ids and (active_type == "TENDER" or len(doc_ids) > 1):
                for did in doc_ids:
                    _add_doc(document_manager.get_document(did))
            _add_doc(getattr(context, "active_document", None))
            if not docs and getattr(context, "active_document_id", None):
                _add_doc(document_manager.get_document(context.active_document_id))

        req_doc = getattr(request, "active_document", None)
        if isinstance(req_doc, dict):
            _add_doc(req_doc)
        elif isinstance(req_doc, str) and not docs:
            _add_doc(document_manager.get_document(req_doc))

        # Ensure every doc has parsed pages ready (avoid re-parsing if already stored)
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
                except Exception as pe:
                    meta = dict(meta)
                    meta["parse_error"] = str(pe)
            hydrated.append(meta)

        return hydrated

    def _is_tender_bundle(self, docs: List[Dict[str, Any]], query: str, context: Optional[Any]) -> bool:
        if any(str(d.get("document_type", "")).upper() == "TENDER" for d in docs):
            return True
        if context and str(getattr(context, "active_document_type", "") or "").upper() == "TENDER":
            return True
        q_low = (query or "").lower()
        if any(k in q_low for k in ("extract tender", "tender fields", "tender details", "emd", "nit ")):
            return True
        combined_sample = " ".join((d.get("extracted_text") or "")[:3000].lower() for d in docs)
        hits = sum(
            1
            for cue in (
                "notice inviting", "e-tender", "earnest money", "emd", "bid submission",
                "tender no", "nit no", "pre-bid", "technical bid", "financial bid", "eprocure",
            )
            if cue in combined_sample
        )
        return hits >= 2

    def _is_extraction_trigger(self, query: str) -> bool:
        q = (query or "").strip().lower()
        if not q or q.startswith("uploaded "):
            return True
        return any(
            phrase in q
            for phrase in (
                "extract tender", "extract all", "extract information", "tender summary",
                "analyze this tender", "analyse this tender", "summarize", "summary",
                "overview", "extract fields", "show extracted",
            )
        )

    def execute(self, request: StructuredRequest, context: Optional[Any] = None) -> CapabilityResult:
        query = (request.user_request or request.normalized_message or "").strip()
        logger.info(f"[DOCUMENT_CAPABILITY] Processing query: {query!r}")

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
                for d in docs:
                    sd = d.get("structured_data")
                    if isinstance(sd, dict) and sd.get("tender_extraction"):
                        cached_extraction = sd["tender_extraction"]
                        break

                if self._is_extraction_trigger(query) or (request.operation or "").upper() in ("SUMMARY", "EXTRACT", "TENDER_EXTRACT"):
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

                # Tender Follow-Up Q&A across complete document pages/sheets
                answer, cited_sources = tender_extractor.answer_followup_question(
                    docs, query, cached_extraction=cached_extraction
                )
                return CapabilityResult(
                    success=True,
                    capability=self.capability_name,
                    operation="TENDER_QA",
                    task_type=TaskTypeEnum.DOCUMENT_QA.value,
                    answer=answer,
                    answer_type="text",
                    structured_data={"cited_sources": cited_sources},
                    sources=source_names,
                    confidence=0.92,
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
