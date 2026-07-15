"""Verification tests for the Document Understanding Engine upgrade (MyGPT v2.0).
"""

import sys
import os
import json
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.services.knowledge_service import knowledge_builder, knowledge_store
from backend.app.services.reasoning_service import reasoning_service
from backend.app.services.trainer_service import trainer_service
from backend.app.core.config import settings

# ──────────────────────────────────────────────
# Test 1: Document Classification & Segmenting
# ──────────────────────────────────────────────
def test_document_classification():
    print("Testing document classification heuristics...")
    
    resume_text = "John Doe is seeking a Full Stack role. Skills: Python, Django, React. Education: BS CS. Work experience includes 3 years at Acme Corp."
    invoice_text = "Tax Invoice INV-2026. Bill To: customer, Total Due Amount: $1,250. GST Rate: 18%. Due Date: 12/10/2026."
    policy_text = "This employee leave policy guidelines document details the probationary requirements, working hours, and rules."
    excel_text = "Name | Salary | Department\nJohn | 5000 | IT\nJane | 7000 | HR"
    
    assert knowledge_builder.classify_document(resume_text, ".txt") == "Resume"
    assert knowledge_builder.classify_document(invoice_text, ".txt") == "Invoice"
    assert knowledge_builder.classify_document(policy_text, ".txt") == "Policy"
    assert knowledge_builder.classify_document(excel_text, ".csv") == "Excel"
    assert knowledge_builder.classify_document("Picture", ".png") == "Image"
    
    print("[OK] Document classification tests passed.\n")


# ──────────────────────────────────────────────
# Test 2: LexRank Heuristics Summary Generation
# ──────────────────────────────────────────────
def test_summary_generation():
    print("Testing LexRank summary generator...")
    
    text = (
        "The project was launched successfully. "
        "The team worked very hard to meet the deadline. "
        "The project was launched successfully. " # repeated
        "Our primary objective was to deliver a scalable system architecture. "
        "This project marks a significant milestone for our company operations."
    )
    
    summary = knowledge_builder.generate_summary(text, "Generic")
    print(f"  Summary: {summary}")
    assert len(summary) > 0
    assert "launched" in summary or "milestone" in summary
    
    print("[OK] Summary generation tests passed.\n")


# ──────────────────────────────────────────────
# Test 3: Table Parsing & Analytical Queries
# ──────────────────────────────────────────────
def test_table_reasoning():
    print("Testing table reasoning (sums, averages, max/min, filters)...")
    
    table_text = (
        "Name | Salary | Department\n"
        "---|---|---\n"
        "John Doe | 6000 | IT\n"
        "Jane Smith | 9500 | HR\n"
        "Bob Johnson | 7500 | IT\n"
        "Alice Williams | 9500 | IT\n"
    )
    
    knowledge = knowledge_builder.build_knowledge(table_text, ".csv")
    doc_id = "test_table_doc_123"
    knowledge_store.save_knowledge(doc_id, knowledge)
    
    # 1. Test highest query (max)
    ans, conf, used = reasoning_service.reason("", "Who has the highest Salary?", doc_id=doc_id)
    print(f"  Highest Salary Ans: {ans}")
    assert "Jane Smith" in ans or "Alice Williams" in ans
    assert used is True
    
    # 2. Test average query
    ans_avg, _, _ = reasoning_service.reason("", "What is the average Salary?", doc_id=doc_id)
    print(f"  Average Salary Ans: {ans_avg}")
    assert "8125" in ans_avg or "8,125" in ans_avg or "8125.00" in ans_avg
    
    # 3. Test total sum query
    ans_sum, _, _ = reasoning_service.reason("", "What is the total sum of Salary?", doc_id=doc_id)
    print(f"  Total Sum Salary Ans: {ans_sum}")
    assert "32500" in ans_sum or "32,500" in ans_sum or "32500.00" in ans_sum
    
    # 4. Test filter count query
    ans_count, _, _ = reasoning_service.reason("", "How many employees are in IT?", doc_id=doc_id)
    print(f"  IT Count Ans: {ans_count}")
    assert "3" in ans_count
    
    # Clean up knowledge store
    knowledge_store.delete_knowledge(doc_id)
    print("[OK] Table reasoning tests passed.\n")


# ──────────────────────────────────────────────
# Test 4: Knowledge-First Reasoning Path
# ──────────────────────────────────────────────
def test_knowledge_first_flow():
    print("Testing Knowledge-First lookup and fallback paths...")
    
    invoice_text = (
        "Invoice Number: INV-8888\n"
        "Vendor: Acme Systems Ltd\n"
        "Total Amount: $4,500.00\n"
        "GST: 18%\n"
        "Due Date: 20/12/2026"
    )
    
    doc_id = "test_invoice_doc_456"
    knowledge = knowledge_builder.build_knowledge(invoice_text, ".txt")
    knowledge_store.save_knowledge(doc_id, knowledge)
    
    # Query direct facts
    ans, conf, used = reasoning_service.reason("", "What is the invoice number?", doc_id=doc_id)
    print(f"  Answer: {ans}")
    assert "INV-8888" in ans or "inv-8888" in ans
    assert used is True
    
    # Fallback to chunk context path if query doesn't match knowledge facts
    ans_fallback, conf_fallback, used_fallback = reasoning_service.reason(
        context="Acme Systems operates global warehouses. The storage units are temperature controlled.",
        question="Describe the storage units",
        doc_id=doc_id
    )
    print(f"  Fallback Ans: {ans_fallback}")
    assert "temperature controlled" in ans_fallback.lower()
    assert used_fallback is False
    
    knowledge_store.delete_knowledge(doc_id)
    print("[OK] Knowledge-First routing tests passed.\n")


# ──────────────────────────────────────────────
# Test 5: Training Logging Schema Integration
# ──────────────────────────────────────────────
def test_trainer_logging_schema():
    print("Testing training logs persistence schema...")
    
    # Setup fresh temporary logs file
    test_jsonl = os.path.join(settings.DATA_DIR, "training_samples.jsonl")
    if os.path.exists(test_jsonl):
        backup_path = test_jsonl + ".backup"
        shutil.copyfile(test_jsonl, backup_path)
        os.remove(test_jsonl)
        
    try:
        doc_id = "dummy_logged_doc"
        knowledge = {
            "document_type": "Resume",
            "summary": "This is a mock resume."
        }
        knowledge_store.save_knowledge(doc_id, knowledge)
        
        trainer_service.save_training_sample(
            doc_id=doc_id,
            question="What is this resume about?",
            answer="This is a mock resume.",
            confidence=95.0,
            knowledge_used=True,
            supporting_chunks=[{"chunk_id": "c1", "text": "chunk text context", "page_number": 1, "score": 0.95}]
        )
        
        assert os.path.exists(test_jsonl), "JSONL file not generated"
        
        with open(test_jsonl, "r", encoding="utf-8") as f:
            lines = f.readlines()
            assert len(lines) == 1, "Expected exactly 1 line logged"
            sample = json.loads(lines[0])
            
            print(f"  Logged Sample:\n{json.dumps(sample, indent=2)}\n")
            
            assert sample["document_type"] == "Resume"
            assert sample["document_id"] == "dummy_logged_doc"
            assert sample["knowledge_used"] is True
            assert len(sample["supporting_chunks"]) == 1
            assert sample["supporting_chunks"][0]["chunk_id"] == "c1"
            assert "timestamp" in sample
            
        knowledge_store.delete_knowledge(doc_id)
        
    finally:
        # Restore backup if it existed
        if os.path.exists(test_jsonl + ".backup"):
            shutil.copyfile(test_jsonl + ".backup", test_jsonl)
            os.remove(test_jsonl + ".backup")
            
    print("[OK] Trainer logging schema checks passed.\n")


# ──────────────────────────────────────────────
# Run All Tests
# ──────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("MYGPT VERSION 2.0 — UNDERSTANDING ENGINE TEST SUITE")
    print("=" * 60 + "\n")
    
    test_document_classification()
    test_summary_generation()
    test_table_reasoning()
    test_knowledge_first_flow()
    test_trainer_logging_schema()
    
    print("=" * 60)
    print("ALL VERSION 2.0 VERIFICATION TESTS PASSED!")
    print("=" * 60)
