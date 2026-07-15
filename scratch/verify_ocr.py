"""Verification tests for the OCR & Ingestion Pipeline Reliability Upgrade.
"""

import sys
import os
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.services.ocr_service import ocr_service
from backend.app.services.document_parser import document_parser
from backend.app.services.ai_orchestrator import ai_orchestrator
from backend.app.services.document_manager import document_manager

# ──────────────────────────────────────────────
# Test 1: PIL Preprocessing & Deskewing
# ──────────────────────────────────────────────
def test_image_preprocessing():
    print("Testing Pillow image preprocessing filters...")
    
    # Create a simple test image (skewed or solid)
    img = Image.new('RGB', (200, 100), color='white')
    processed = ocr_service.preprocess_image(img)
    
    assert processed.mode == 'L', "Image should be converted to grayscale (mode L)"
    print("[OK] Pillow image preprocessing tests passed.\n")


# ──────────────────────────────────────────────
# Test 2: Ingestion Rejection on Short/Empty Documents
# ──────────────────────────────────────────────
def test_ingestion_validation():
    print("Testing validation filters & extraction failure paths...")
    
    # 1. Test short text document (under 30 words)
    temp_path = "data/temp_short_doc.txt"
    os.makedirs(os.path.dirname(temp_path), exist_ok=True)
    with open(temp_path, "w", encoding="utf-8") as f:
        f.write("This is a short text. It only has a few words.")
        
    try:
        document_parser.parse(temp_path)
        assert False, "Should have raised ValueError due to insufficient word count (< 30 words)"
    except ValueError as e:
        print(f"  Successfully caught expected validation error: {e}")
        assert "Unable to extract readable text" in str(e)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
    # 2. Test mock document validation (over 30 words)
    temp_mock_path = "data/temp_scanned_resume_cv.txt"
    with open(temp_mock_path, "w", encoding="utf-8") as f:
        f.write(
            "This is a mocked scanned resume of John Doe who is looking for a job as a developer. "
            "Skills: Python, Django, React, Javascript, HTML, CSS, SQL. "
            "Experience: 4 years as a Full Stack engineer. "
            "Education: BS CS. Contact email: john@example.com."
        )
    try:
        parsed = document_parser.parse(temp_mock_path)
        assert parsed is not None
        print("  Mock document passed validation (sufficient length)")
    finally:
        if os.path.exists(temp_mock_path):
            os.remove(temp_mock_path)
            
    print("[OK] Ingestion validation tests passed.\n")


# ──────────────────────────────────────────────
# Test 3: Orchestrator Rejection & Error Status
# ──────────────────────────────────────────────
def test_orchestrator_failure_handling():
    print("Testing orchestrator error handling & status tracking...")
    
    # Process a document with invalid text content
    filename = "empty_doc.txt"
    content = b"Short description." # Invalid, under 30 words
    
    try:
        doc_meta, parsed_doc = ai_orchestrator.process_new_document(filename, content)
        assert False, "Sync parse should have thrown ValueError"
    except ValueError as e:
        print(f"  Orchestrator threw expected exception: {e}")
        
        # Verify metadata shows error state
        docs = document_manager.list_documents()
        error_docs = [d for d in docs if d["filename"] == "empty_doc.txt" and d["status"] == "error"]
        assert len(error_docs) > 0, "Document status was not set to error"
        assert "Unable to extract readable text" in error_docs[0]["error"]
        print(f"  Metadata entry successfully transitioned to error: {error_docs[0]['error']}")
        
        # Clean up database entry
        document_manager.delete_document(error_docs[0]["id"])
        
    print("[OK] Failure handling tests passed.\n")


# ──────────────────────────────────────────────
# Run All Tests
# ──────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("MYGPT OCR & PARSING RELIABILITY — VERIFICATION SUITE")
    print("=" * 60 + "\n")
    
    test_image_preprocessing()
    test_ingestion_validation()
    test_orchestrator_failure_handling()
    
    print("=" * 60)
    print("ALL OCR & RELIABILITY VERIFICATION TESTS PASSED!")
    print("=" * 60)
