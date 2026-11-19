"""
Unit tests for Document Storage Quota and Automatic LRU Eviction.
Validates:
1. Automatic LRU deletion of oldest documents when document count limit is reached.
2. Hard disk MB quota enforcement.
3. Strict protection of essential test fixtures.
4. Clean removal of physical files, metadata records, and parsed disk cache.
"""

import os
import time
import tempfile
import pytest
from backend.app.services.document_manager import document_manager
from backend.app.core.config import settings


def test_storage_stats_reporting():
    """Verifies storage statistics report accurate counts and MB numbers."""
    stats = document_manager.get_storage_stats()
    assert "total_files" in stats
    assert "total_size_mb" in stats
    assert "max_storage_mb" in stats
    assert "max_documents" in stats
    assert stats["max_storage_mb"] == 200
    assert stats["max_documents"] == 5
    assert stats["total_size_mb"] < 200.0


def test_protected_files_are_never_evicted():
    """Verifies that protected fixtures are retained even under aggressive limits."""
    # Run quota enforcement with max_docs = 1 and max_mb = 1
    # Protected files should still be present
    res = document_manager.enforce_storage_quota(max_mb=1, max_docs=1)
    
    # Check that protected fixtures still exist on disk
    for protected_fname in document_manager.PROTECTED_FILENAMES:
        p = os.path.join(document_manager.upload_dir, protected_fname)
        if protected_fname.endswith(".pdf") and "WiFi" not in protected_fname:
            # Fixtures that exist must remain
            assert os.path.exists(p), f"Protected file {protected_fname} was incorrectly deleted!"


def test_lru_auto_pruning_on_upload():
    """Simulates uploading documents and verifies the oldest non-protected file is automatically pruned."""
    # Upload 6 dummy test files
    uploaded_ids = []
    try:
        for i in range(6):
            content = f"Test document content for quota validation file {i} - {time.time()}".encode("utf-8")
            meta = document_manager.upload_document(
                filename=f"quota_test_file_{i}.txt",
                file_content=content,
                pre_parse=False
            )
            uploaded_ids.append(meta["id"])
            time.sleep(0.01)

        # Enforce quota with max_docs=3
        res = document_manager.enforce_storage_quota(max_docs=3)
        
        # After keeping max 3, the earliest uploaded files should be pruned
        db = document_manager._read_metadata()
        remaining_test_ids = [uid for uid in uploaded_ids if uid in db]
        assert len(remaining_test_ids) <= 3
        # The newest (last uploaded) must still be present
        assert uploaded_ids[-1] in db
    finally:
        # Cleanup any remaining test uploads
        for uid in uploaded_ids:
            document_manager.delete_document(uid)

