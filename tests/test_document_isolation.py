"""Phase 2 Regression Tests: Document and Session Isolation for MYGPT Tender Consultant.

Strictly verifies:
1. Single document uploads reset and isolate active document scope (no accumulation).
2. evaluate_tender rejects automatic combination of unrelated tenders.
3. Explicit tender packages preserve multiple documents while retaining individual identity.
4. Cache keys are strictly isolated per document hash and filename.
5. All findings, citations, and items retain their source document_id.
"""

import sys
import uuid
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.services.conversation_context_manager import conversation_context_manager
from backend.app.services.capabilities.document_capability import DocumentCapability
from backend.app.services.tender.tender_section_retriever import (
    PageRecord,
    collect_page_records,
    compute_bundle_signature,
)
from backend.app.services.tender_intelligence.intelligence_schema import (
    TenderEvidenceCitation,
    EligibilityCondition,
    TechnicalScopeItem,
    TechnicalSpecificationItem,
    OEMRequirementItem,
    ComplianceMatrixItem,
    ContractualClauseItem,
    RiskContradictionItem,
    ActionRoadmapItem,
    TenderConsultantReport,
)
from backend.app.services.tender_intelligence import tender_intelligence_engine


def test_session_isolation_resets_on_new_upload():
    """Verify that uploading Document B after Document A does not accumulate both in active scope."""
    session_id = f"test_iso_session_{uuid.uuid4().hex[:8]}"

    doc_a = {
        "id": "doc_nitk_123",
        "document_id": "doc_nitk_123",
        "filename": "NITK_Desktop.pdf",
        "file_hash": "hash_nitk_aaa",
        "document_type": "TENDER",
    }
    conversation_context_manager.set_active_document(session_id, doc_a, is_explicit_package=False)
    state = conversation_context_manager.get_state(session_id)
    assert state.active_document_ids == ["doc_nitk_123"]
    assert state.active_document_id == "doc_nitk_123"
    assert not state.is_explicit_package

    # Now upload Document B in the same session
    doc_b = {
        "id": "doc_tripura_456",
        "document_id": "doc_tripura_456",
        "filename": "Tripura_WiFi.pdf",
        "file_hash": "hash_tripura_bbb",
        "document_type": "TENDER",
    }
    conversation_context_manager.set_active_document(session_id, doc_b, is_explicit_package=False)
    state_after = conversation_context_manager.get_state(session_id)

    # Active IDs must be strictly Document B ONLY (no accumulation of NITK)
    assert state_after.active_document_ids == ["doc_tripura_456"]
    assert state_after.active_document_id == "doc_tripura_456"
    assert state_after.active_document_name == "Tripura_WiFi.pdf"
    assert not state_after.is_explicit_package

    # Full history is preserved for chat audit, but active scope is isolated
    all_doc_ids = [d.get("document_id") for d in state_after.conversation_documents]
    assert "doc_nitk_123" in all_doc_ids
    assert "doc_tripura_456" in all_doc_ids


def test_explicit_tender_package_grouping():
    """Verify explicit package grouping keeps multiple PDFs while preserving individual identities."""
    session_id = f"test_pkg_session_{uuid.uuid4().hex[:8]}"
    doc_vol1 = {
        "id": "vol1_tech",
        "document_id": "vol1_tech",
        "filename": "Tender_Vol1_Technical.pdf",
        "file_hash": "hash_v1",
        "document_type": "TENDER",
    }
    doc_vol2 = {
        "id": "vol2_comm",
        "document_id": "vol2_comm",
        "filename": "Tender_Vol2_Commercial.pdf",
        "file_hash": "hash_v2",
        "document_type": "TENDER",
    }

    state = conversation_context_manager.set_tender_package(
        session_id, [doc_vol1, doc_vol2], package_name="Campus Wi-Fi Multi-Volume Tender"
    )
    assert state.is_explicit_package is True
    assert state.active_document_ids == ["vol1_tech", "vol2_comm"]
    assert state.package_name == "Campus Wi-Fi Multi-Volume Tender"


def test_engine_rejects_unrelated_combination_without_package_flag(monkeypatch):
    """Verify that evaluate_tender refuses to combine multiple documents if not an explicit package."""
    monkeypatch.setattr(tender_intelligence_engine, "_call_gemma_json", lambda *a, **k: {})
    doc_1 = {
        "document_id": "nitk_id",
        "filename": "NITK_Desktop.pdf",
        "file_hash": "hash_nitk",
        "pages": [{"page_number": 1, "text": "National Institute of Technology Karnataka High End Desktop tender."}],
    }
    doc_2 = {
        "document_id": "tripura_id",
        "filename": "Tripura_WiFi.pdf",
        "file_hash": "hash_tripura",
        "pages": [{"page_number": 1, "text": "Tripura University Campus Wide Wi-Fi Network tender."}],
    }

    # Pass both documents WITHOUT is_multi_document_package
    report = tender_intelligence_engine.evaluate_tender(
        [doc_1, doc_2], force_refresh=True, is_multi_document_package=False
    )

    # Engine must have isolated strictly to doc_1 (NITK)
    assert len(report.document_ids) == 1
    assert report.document_ids[0] == "nitk_id"
    assert report.source_files[0] == "NITK_Desktop.pdf"
    assert report.is_multi_document_package is False


def test_cache_signature_isolation():
    """Verify different tenders produce completely distinct cache signatures."""
    doc_a = [{"document_id": "id_a", "filename": "doc_a.pdf", "file_hash": "hash_111"}]
    doc_b = [{"document_id": "id_b", "filename": "doc_b.pdf", "file_hash": "hash_222"}]

    sig_a = compute_bundle_signature(doc_a)
    sig_b = compute_bundle_signature(doc_b)
    assert sig_a != sig_b
    assert len(sig_a) == 64


def test_page_records_and_schema_retain_document_identity():
    """Verify collect_page_records and schema models carry document_id and file_hash."""
    docs = [
        {
            "id": "doc_test_999",
            "document_id": "doc_test_999",
            "filename": "SampleTender.pdf",
            "file_hash": "hash_sample_999",
            "pages": [{"page_number": 1, "text": "Page 1 sample"}],
        }
    ]
    records = collect_page_records(docs)
    assert len(records) == 1
    assert records[0].document_id == "doc_test_999"
    assert records[0].filename == "SampleTender.pdf"
    assert records[0].file_hash == "hash_sample_999"

    # Verify schema models instantiate with document_id
    cit = TenderEvidenceCitation(
        filename="SampleTender.pdf",
        page_number=1,
        document_id="doc_test_999",
        source_text="Test clause",
    )
    assert cit.document_id == "doc_test_999"

    cond = EligibilityCondition(
        category="Turnover",
        department_requirement="Rs. 5 Crore",
        supporting_document_required="CA Cert",
        source_page=1,
        source_file="SampleTender.pdf",
        document_id="doc_test_999",
    )
    assert cond.document_id == "doc_test_999"
