"""Verification script for Milestone 2 of the local Document Assistant.
"""

import os
import sys

# Add project root directory to path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from backend.app.services.indexing_service import indexing_service
from backend.app.services.storage_service import storage_service
from backend.app.services.embedding_service import embedding_service
from backend.app.services.search_coordinator import search_coordinator
from backend.app.services.document_manager import document_manager


def run_verification():
    print("=========================================")
    print("RUNNING MILESTONE 2 VERIFICATION TESTS")
    print("=========================================")

    doc_id = "test_invoice_doc"

    try:
        # Register a mock document in manager first to enable status updates
        document_manager.upload_document("test_invoice.txt", b"dummy")
        # Overwrite the auto-generated id mapping to test_invoice_doc
        db = document_manager._read_metadata()
        for k in list(db.keys()):
            if db[k]["filename"] == "test_invoice.txt":
                db[doc_id] = db[k]
                db[doc_id]["id"] = doc_id
                del db[k]
                break
        document_manager._write_metadata(db)

        # 1. Structure a parsed document matching an invoice
        parsed_doc = {
            "text": "INVOICE #1001. Due Date: 2026-08-31. Total Due: $5,400. GST: 18%. Bill To: John Doe.",
            "pages": [
                {
                    "page_number": 1,
                    "text": "INVOICE #1001. Due Date: 2026-08-31. Total Due: $5,400."
                },
                {
                    "page_number": 2,
                    "text": "GST: 18%. Bill To: John Doe."
                }
            ],
            "file_type": ".txt"
        }

        # 2. Test Indexing
        print("\n[Test 1] Indexing parsed document...")
        indexing_service.index_document(doc_id, parsed_doc, chunk_size=40)
        
        # Verify chunks exist in store
        chunks = storage_service.get_chunks(doc_id)
        assert len(chunks) > 0, "No chunks saved to storage"
        assert "embedding" in chunks[0], "Chunk did not store embedding"
        assert len(chunks[0]["embedding"]) > 0, "Embedding vector is empty"
        print(f"[OK] Indexing succeeded. Generated {len(chunks)} chunks.")

        # 3. Test Embedding Service directly
        print("\n[Test 2] Testing embedding dimension...")
        texts = ["What is the total amount?", "Who is the client?"]
        vectors = embedding_service.get_embeddings(texts)
        assert len(vectors) == 2
        assert len(vectors[0]) == len(chunks[0]["embedding"]), "Embedding dimensions mismatched"
        print(f"[OK] Embedding dimension check passed: dim={len(vectors[0])}")

        # 4. Test Search Coordinator and Retrieval
        print("\n[Test 3] Testing search retrieval...")
        # Query for amount should match chunk containing "$5,400"
        results = search_coordinator.search("total amount due", doc_id=doc_id, top_k=2)
        assert len(results) > 0, "Retrieval returned empty results"
        print("Scored results:")
        for r in results:
            print(f"  Score={r['score']:.4f} Page={r['page_number']} Text='{r['text']}'")
        
        # Check Top-K constraint
        assert len(results) <= 2, "Top-K parameter violated"
        print("[OK] Search and retrieval works successfully!")

        # 5. Clean up Index
        print("\n[Test 4] Cleaning up index...")
        indexing_service.delete_document_index(doc_id)
        document_manager.delete_document(doc_id)
        assert len(storage_service.get_chunks(doc_id)) == 0, "Failed to delete chunks index"
        print("[OK] Index cleanup passed!")

        print("\n=========================================")
        print("ALL MILESTONE 2 VERIFICATION TESTS PASSED!")
        print("=========================================")
        return True

    except Exception as e:
        print(f"\n[FAIL] Milestone 2 test failed: {e}")
        # Cleanup index if failed
        storage_service.delete_chunks(doc_id)
        document_manager.delete_document(doc_id)
        raise e


if __name__ == "__main__":
    success = run_verification()
    sys.exit(0 if success else 1)
