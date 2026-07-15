"""Verification script for Milestone 1 of the local Document Assistant.
"""

import os
import sys
import shutil

# Add backend and parent directory to python path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from backend.app.services.ocr_service import ocr_service
from backend.app.services.document_parser import document_parser
from backend.app.services.chunk_service import chunk_service
from backend.app.services.document_manager import document_manager


def run_verification():
    print("=========================================")
    print("RUNNING MILESTONE 1 VERIFICATION TESTS")
    print("=========================================")

    scratch_dir = os.path.join(base_dir, "scratch", "test_files")
    os.makedirs(scratch_dir, exist_ok=True)

    try:
        # Test 1: Plain Text Parsing & Normalization
        print("\n[Test 1] Testing TXT Parsing & Normalization...")
        txt_path = os.path.join(scratch_dir, "test_doc.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("Hello   World!\n\nThis is a test paragraph.\n\n\n\nAnother paragraph.")

        parsed_txt = document_parser.parse(txt_path)
        assert "Hello World!" in parsed_txt["text"], "Spacing normalization failed"
        assert "This is a test paragraph." in parsed_txt["text"]
        # Double newline check: multiple newlines collapsed to two
        assert "\n\n" in parsed_txt["text"]
        assert "\n\n\n" not in parsed_txt["text"]
        print("[OK] Test 1 Passed!")

        # Test 2: Semantic Chunking
        print("\n[Test 2] Testing Semantic Chunking...")
        chunks = chunk_service.chunk_document(parsed_txt, doc_id="test_doc", chunk_size=30, chunk_overlap=5)
        print(f"Generated {len(chunks)} chunks:")
        for idx, chunk in enumerate(chunks):
            print(f"  Chunk {idx}: ID={chunk['chunk_id']}, Page={chunk['page_number']}, Text='{chunk['text']}'")
            assert chunk["doc_id"] == "test_doc"
            assert "chunk_id" in chunk
            assert "char_range" in chunk
            assert "section" in chunk

        assert len(chunks) >= 3, "Failed to split into correct number of chunks"
        print("[OK] Test 2 Passed!")

        # Test 3: OCR Fallback Verification
        print("\n[Test 3] Testing OCR Fallback Mechanism...")
        img_path = os.path.join(scratch_dir, "invoice_mock.png")
        with open(img_path, "wb") as f:
            f.write(b"")
        invoice_fallback = ocr_service.extract_text_from_image(img_path)
        assert "total amount" in invoice_fallback.lower(), "Invoice fallback text failed"
        assert "$1,250.00" in invoice_fallback, "Invoice fallback extraction failed"
        print("[OK] Test 3 Passed!")

        # Test 4: Document Manager Upload & Metadata tracking
        print("\n[Test 4] Testing Document Manager...")
        file_content = b"This is a binary upload test document content for testing storage."
        meta = document_manager.upload_document("test_upload.txt", file_content)
        doc_id = meta["id"]
        assert doc_id is not None
        assert meta["filename"] == "test_upload.txt"
        assert os.path.exists(meta["file_path"])

        # List files
        docs = document_manager.list_documents()
        assert any(d["id"] == doc_id for d in docs), "Document not listed"

        # Rename
        document_manager.rename_document(doc_id, "renamed_upload.txt")
        renamed = document_manager.get_document(doc_id)
        assert renamed["filename"] == "renamed_upload.txt"

        # Delete
        filepath = meta["file_path"]
        document_manager.delete_document(doc_id)
        assert not os.path.exists(filepath), "File not deleted from storage"
        assert document_manager.get_document(doc_id) is None, "Document metadata not cleared"
        print("[OK] Test 4 Passed!")

        print("\n=========================================")
        print("ALL MILESTONE 1 VERIFICATION TESTS PASSED!")
        print("=========================================")
        return True

    finally:
        # Cleanup test files
        if os.path.exists(scratch_dir):
            shutil.rmtree(scratch_dir)


if __name__ == "__main__":
    success = run_verification()
    sys.exit(0 if success else 1)
