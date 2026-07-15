"""Verification script for Milestone 4 of the local Document Assistant.
"""

import os
import sys
import json
from fastapi.testclient import TestClient

# Add project root directory to path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from backend.app.main import app
from backend.app.services.document_manager import document_manager
from backend.app.services.storage_service import storage_service

client = TestClient(app)


def run_verification():
    print("=========================================")
    print("RUNNING MILESTONE 4 VERIFICATION TESTS")
    print("=========================================")

    session_id = "test_verification_session"
    doc_id = None

    try:
        # 1. Test upload API
        print("\n[Test 1] Testing document upload API...")
        file_content = b"INVOICE INV-9999. Total Amount: $3,200. Due Date: 2026-09-15. GST: 18%."
        
        response = client.post(
            "/api/documents/upload",
            files={"file": ("test_invoice_9999.txt", file_content, "text/plain")},
            data={"chunk_size": 40}
        )
        assert response.status_code == 200, f"Upload failed: {response.text}"
        data = response.json()
        doc_id = data["id"]
        assert doc_id is not None
        assert data["filename"] == "test_invoice_9999.txt"
        
        # Wait/Poll for background indexing to transition status to processed
        import time
        status = data.get("status")
        print(f"Initial upload status: {status}. Polling for background indexing to complete...")
        for _ in range(30):
            if status == "processed":
                break
            time.sleep(0.5)
            list_resp = client.get("/api/documents")
            assert list_resp.status_code == 200
            docs = list_resp.json()
            doc_info = next((d for d in docs if d["id"] == doc_id), None)
            if doc_info:
                status = doc_info.get("status")
                print(f"  Current background status: {status}")
            else:
                break
        
        assert status == "processed", f"Background indexing did not complete successfully. End status: {status}"
        print(f"[OK] Upload and background indexing succeeded. Document ID: {doc_id}")

        # 2. Test list documents API
        print("\n[Test 2] Testing list documents API...")
        list_resp = client.get("/api/documents")
        assert list_resp.status_code == 200
        docs = list_resp.json()
        assert any(d["id"] == doc_id for d in docs), "Uploaded document not in listing"
        print("[OK] List documents check passed.")

        # 3. Test non-streaming Chat API
        print("\n[Test 3] Testing non-streaming Chat API...")
        chat_req = {
            "session_id": session_id,
            "question": "What is the total amount?",
            "doc_id": doc_id,
            "stream": False
        }
        chat_resp = client.post("/api/chat", json=chat_req)
        assert chat_resp.status_code == 200, f"Chat failed: {chat_resp.text}"
        chat_data = chat_resp.json()
        assert "answer" in chat_data
        assert "$3,200" in chat_data["answer"]
        assert chat_data["confidence"] > 0.0
        assert len(chat_data["sources"]) > 0
        assert len(chat_data["suggested_questions"]) > 0
        print(f"Non-streaming Chat Answer: {chat_data['answer']}")
        print(f"Confidence: {chat_data['confidence']}%")
        print("[OK] Non-streaming chat checks passed.")

        # 4. Test streaming Chat API (SSE)
        print("\n[Test 4] Testing streaming Chat API (SSE)...")
        chat_req["stream"] = True
        chat_req["question"] = "What is the GST tax?"
        
        stream_resp = client.post("/api/chat", json=chat_req)
        assert stream_resp.status_code == 200
        
        # Read stream events
        has_token = False
        has_metadata = False
        
        for line in stream_resp.iter_lines():
            if line:
                line_str = line if isinstance(line, str) else line.decode("utf-8")
                if line_str.startswith("data: "):
                    event_data = line_str[6:]
                    if event_data == "[DONE]":
                        break
                    
                    data_obj = json.loads(event_data)
                    if "token" in data_obj:
                        has_token = True
                    if "metadata" in data_obj:
                        has_metadata = True
                        meta_obj = data_obj["metadata"]
                        assert "confidence" in meta_obj
                        assert "sources" in meta_obj
                        assert "suggested_questions" in meta_obj

        assert has_token, "Stream did not yield any token items"
        assert has_metadata, "Stream did not yield final metadata"
        print("[OK] Streaming SSE chat checks passed.")

        # 5. Test history API
        print("\n[Test 5] Testing history API...")
        history_resp = client.get(f"/api/chat/history?session_id={session_id}")
        assert history_resp.status_code == 200
        history_data = history_resp.json()
        assert len(history_data) >= 4, f"Dialogue turns count mismatch: {len(history_data)}"
        print("[OK] Dialogue turns stored correctly.")

        # 6. Test reset API
        print("\n[Test 6] Testing reset history API...")
        reset_resp = client.post("/api/chat/reset", data={"session_id": session_id})
        assert reset_resp.status_code == 200
        
        history_resp = client.get(f"/api/chat/history?session_id={session_id}")
        assert len(history_resp.json()) == 0, "Failed to reset dialogue memory logs"
        print("[OK] Reset history checks passed.")

        # 7. Test delete API
        print("\n[Test 7] Testing document deletion API...")
        del_resp = client.delete(f"/api/documents/{doc_id}")
        assert del_resp.status_code == 200
        assert len(storage_service.get_chunks(doc_id)) == 0, "Indexed chunks not deleted"
        print("[OK] Document deletion passed.")

        print("\n=========================================")
        print("ALL MILESTONE 4 VERIFICATION TESTS PASSED!")
        print("=========================================")
        return True

    except Exception as e:
        print(f"\n[FAIL] Milestone 4 test failed: {e}")
        # Clean up if failed
        if doc_id:
            document_manager.delete_document(doc_id)
            storage_service.delete_chunks(doc_id)
        raise e


if __name__ == "__main__":
    success = run_verification()
    sys.exit(0 if success else 1)
