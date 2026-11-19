"""Comprehensive Regression Tests for Tender Upload Cache & Document Isolation.

Scenarios Covered:
- Scenario A: Different tenders (Tender A vs Tender B).
- Scenario B: Same filename with different content (SHA-256 separation).
- Scenario C: Same PDF uploaded twice (safe cache hit with hash verification).
- Scenario D: Follow-up questions after new upload strictly use new document's evidence.
- Scenario E: Dynamic suggested questions replace old domain questions on new upload.
- Scenario F: Multi-document package vs single isolated document.
- Scenario G: Active document precedence (request overrides stale context).
- Scenario H: New conversation does not inherit previous conversation's active doc context.
"""

import hashlib
import os
import pytest
from typing import Any, Dict

from backend.app.schemas.company_ai import CompanyAIChatRequest, StructuredRequest
from backend.app.services.capabilities.document_capability import DocumentCapability
from backend.app.services.company_ai_service import company_ai_service
from backend.app.services.conversation_context_manager import conversation_context_manager
from backend.app.services.document_manager import document_manager
from backend.app.services.tender.tender_section_retriever import compute_bundle_signature
from backend.app.services.tender_intelligence.intelligence_engine import tender_intelligence_engine
from backend.app.services.tender_intelligence.intelligence_report_builder import intelligence_report_builder


def _make_mock_doc(doc_id: str, filename: str, content: str) -> Dict[str, Any]:
    file_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return {
        "id": doc_id,
        "document_id": doc_id,
        "filename": filename,
        "file_hash": file_hash,
        "document_type": "TENDER",
        "file_type": ".pdf",
        "extension": ".pdf",
        "extracted_text": content,
        "pages": [{"page_number": 1, "text": content}],
        "total_pages": 1,
    }


TENDER_A_TEXT = (
    "NOTICE INVITING TENDER: Supply of 1000 Body Worn Cameras (BWC).\n"
    "Tender No: BWC/2026/001. Issued by: West Bengal Police Directorate.\n"
    "EMD Amount: Rs. 5,00,000/-. Estimated Value: Rs. 2.50 Crore.\n"
    "Bid Submission Last Date: 20-Dec-2026.\n"
    "Eligibility: Minimum 3 years experience in body worn cameras. Annual turnover Rs. 5 Crore.\n"
    "Scope: 1080p full HD recording, GPS, 12 hours battery life, AES-256 encryption."
)

TENDER_B_TEXT = (
    "NOTICE INVITING E-TENDER: Implementation of Smart City CCTV Surveillance System.\n"
    "Tender No: WTL/WBPNB/CCTV/26-27/046. Issued by: Webel Technology Limited.\n"
    "EMD Amount: Rs. 16,00,000/-. Estimated Tender Value: Rs. 8.00 Crore.\n"
    "Bid Submission Last Date: 15-Jan-2027.\n"
    "Eligibility: Similar work experience of one project Rs. 6.40 Cr, or two Rs. 4.00 Cr, or three Rs. 3.20 Cr.\n"
    "Scope: 4K ANPR Cameras, PTZ cameras, Central Command Center, 30 days video storage."
)


class TestTenderUploadCacheIsolation:

    def setup_method(self):
        # Register mock docs in document_manager
        self.doc_a = _make_mock_doc("doc_bwc_001", "bwc_tender.pdf", TENDER_A_TEXT)
        self.doc_b = _make_mock_doc("doc_cctv_002", "cctv_tender.pdf", TENDER_B_TEXT)

        db = document_manager._read_metadata()
        db["doc_bwc_001"] = self.doc_a
        db["doc_cctv_002"] = self.doc_b
        document_manager._write_metadata(db)

    def test_scenario_a_different_tenders_isolation(self):
        """Scenario A: Two different tenders produce distinct bundle signatures and isolated evaluations."""
        sig_a = compute_bundle_signature([self.doc_a])
        sig_b = compute_bundle_signature([self.doc_b])

        assert sig_a != sig_b, "Two different tenders must have completely distinct bundle signatures"

        rep_a = tender_intelligence_engine.evaluate_tender([self.doc_a], force_refresh=True, mode="fast")
        rep_b = tender_intelligence_engine.evaluate_tender([self.doc_b], force_refresh=True, mode="fast")

        # Verify Tender A content
        assert "Body Worn" in (rep_a.overview.tender_title or "") or "bwc" in (rep_a.overview.tender_title or "").lower()
        # Verify Tender B content
        assert "CCTV" in (rep_b.overview.tender_title or "") or "cctv" in (rep_b.overview.tender_title or "").lower()
        # Ensure no cross-contamination
        assert rep_a.document_ids == ["doc_bwc_001"]
        assert rep_b.document_ids == ["doc_cctv_002"]

    def test_scenario_b_same_filename_different_content(self):
        """Scenario B: Same filename with different content must NEVER share a cache signature."""
        doc_x1 = _make_mock_doc("doc_x1", "tender.pdf", TENDER_A_TEXT)
        doc_x2 = _make_mock_doc("doc_x2", "tender.pdf", TENDER_B_TEXT)

        assert doc_x1["filename"] == doc_x2["filename"]
        assert doc_x1["file_hash"] != doc_x2["file_hash"]

        sig_1 = compute_bundle_signature([doc_x1])
        sig_2 = compute_bundle_signature([doc_x2])

        assert sig_1 != sig_2, "Identical filename with different contents must produce different signatures"

    def test_scenario_c_same_pdf_uploaded_twice_cache_reuse(self):
        """Scenario C: Same PDF uploaded again (new doc_id, same content hash) safely reuses cache."""
        doc_original = _make_mock_doc("doc_orig", "bwc_tender.pdf", TENDER_A_TEXT)
        # Second upload gets a new UUID
        doc_duplicate = _make_mock_doc("doc_dup_uuid_999", "bwc_tender.pdf", TENDER_A_TEXT)

        assert doc_original["file_hash"] == doc_duplicate["file_hash"]

        sig_orig = compute_bundle_signature([doc_original])
        sig_dup = compute_bundle_signature([doc_duplicate])

        assert sig_orig == sig_dup, "Exact same PDF content must generate identical bundle signature"

        # Evaluate first doc
        rep_1 = tender_intelligence_engine.evaluate_tender([doc_original], force_refresh=True, mode="fast")
        assert rep_1 is not None

        # Second doc should hit cache
        rep_2 = tender_intelligence_engine.evaluate_tender([doc_duplicate], force_refresh=False, mode="fast")
        assert rep_2.cache_hit is True
        assert rep_2.document_ids == ["doc_dup_uuid_999"]

    def test_scenario_d_follow_up_uses_new_tender_evidence(self):
        """Scenario D: Follow-up question after new upload strictly uses new document's evidence."""
        # 1. Ask about Tender A
        ans_a, _ = tender_intelligence_engine.answer_consultant_question(
            [self.doc_a], "What is the EMD amount?"
        )
        assert "5,00,000" in ans_a or "5 Lakh" in ans_a or "5" in ans_a

        # 2. Upload Tender B and ask same question
        ans_b, _ = tender_intelligence_engine.answer_consultant_question(
            [self.doc_b], "What is the EMD amount?"
        )
        assert "16,00,000" in ans_b or "16 Lakh" in ans_b or "16" in ans_b
        # Ensure Tender B does NOT mention Tender A's EMD
        assert "5,00,000" not in ans_b

    def test_scenario_e_dynamic_suggested_questions_isolation(self):
        """Scenario E: Suggested questions for Tender A vs Tender B reflect respective domains."""
        rep_a = tender_intelligence_engine.evaluate_tender([self.doc_a], force_refresh=True, mode="fast")
        rep_b = tender_intelligence_engine.evaluate_tender([self.doc_b], force_refresh=True, mode="fast")

        sugg_a = rep_a.suggested_questions or intelligence_report_builder.generate_suggested_questions(rep_a)
        sugg_b = rep_b.suggested_questions or intelligence_report_builder.generate_suggested_questions(rep_b)

        assert len(sugg_a) >= 3
        assert len(sugg_b) >= 3

        # Suggested questions should be relevant to their respective tenders
        assert any("camera" in q.lower() or "bwc" in q.lower() or "battery" in q.lower() or "emd" in q.lower() for q in sugg_a)
        assert any("cctv" in q.lower() or "surveillance" in q.lower() or "anpr" in q.lower() or "emd" in q.lower() for q in sugg_b)

    def test_scenario_f_multi_document_package_isolation(self):
        """Scenario F: Multi-document package evaluation requires explicit flag."""
        # Unflagged batch: must evaluate ONLY primary document
        rep_single = tender_intelligence_engine.evaluate_tender(
            [self.doc_a, self.doc_b], is_multi_document_package=False, force_refresh=True, mode="fast"
        )
        assert rep_single.is_multi_document_package is False
        assert rep_single.document_ids == ["doc_bwc_001"]

        # Explicit package: combines both documents
        rep_pkg = tender_intelligence_engine.evaluate_tender(
            [self.doc_a, self.doc_b], is_multi_document_package=True, package_name="security_bundle", force_refresh=True, mode="fast"
        )
        assert rep_pkg.is_multi_document_package is True
        assert len(rep_pkg.document_ids) == 2

    def test_scenario_g_request_active_document_overrides_stale_context(self):
        """Scenario G: Request active document has top precedence over stale context document in DocumentCapability."""
        cap = DocumentCapability()
        session_id = "test_session_isolation_override"

        # Context has Tender A
        ctx = conversation_context_manager.set_active_document(session_id, self.doc_a, is_explicit_package=False)
        assert ctx.active_document_id == "doc_bwc_001"

        # Request arrives targeting Tender B
        req = StructuredRequest(
            capability="DOCUMENT",
            operation="TENDER_CONSULTANT",
            user_request="Uploaded cctv_tender.pdf",
            active_document="doc_cctv_002",
        )

        docs = cap._collect_active_documents(req, context=ctx)
        assert len(docs) == 1
        assert docs[0]["id"] == "doc_cctv_002", "Request active_document must override stale context"
        assert docs[0]["filename"] == "cctv_tender.pdf"

    def test_scenario_h_new_conversation_isolation(self):
        """Scenario H: A new conversation session starts clean with no active document."""
        session_old = "session_old_bwc"
        session_new = "session_new_clean"

        # Old session has active tender
        conversation_context_manager.set_active_document(session_old, self.doc_a)
        state_old = conversation_context_manager.get_state(session_old)
        assert state_old.active_document_id == "doc_bwc_001"

        # New session must have no active document
        state_new = conversation_context_manager.get_state(session_new)
        assert state_new.active_document is None
        assert state_new.active_document_id is None
        assert state_new.active_document_ids == []

