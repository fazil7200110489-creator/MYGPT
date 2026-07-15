"""Verification tests for the Document Intelligence Engine upgrade.

Tests:
1. Resume QA: name, email, skills extraction
2. Invoice QA: amount, tax, due date
3. Summary: clean paragraph output
4. Follow-up: doc context preserved without re-specifying doc_id
5. Zero-confidence: "I couldn't find that information" response
6. Fact extraction: structured entity extraction
7. Intent detection: new intents (Image, Resume, Follow-up)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.services.reasoning_service import reasoning_service, extract_facts
from backend.app.services.answer_formatter import answer_formatter, format_extraction_answer
from backend.app.services.context_builder import context_builder
from backend.app.services.chunk_service import chunk_service

# ──────────────────────────────────────────────
# Test 1: Intent Detection — New Intents
# ──────────────────────────────────────────────
def test_intent_detection():
    print("Testing intent detection for new intents...")
    
    assert reasoning_service.infer_intent("What does the image show?") == "Image", "Image intent failed"
    assert reasoning_service.infer_intent("Show the photo details") == "Image", "Image/photo intent failed"
    assert reasoning_service.infer_intent("Analyze this resume") == "Resume", "Resume intent failed"
    assert reasoning_service.infer_intent("What about his projects?") == "Follow-up", "Follow-up intent failed"
    assert reasoning_service.infer_intent("What about those details?") == "Follow-up", "Follow-up/those intent failed"
    assert reasoning_service.infer_intent("Summarize this document") == "Summary", "Summary intent failed"
    assert reasoning_service.infer_intent("What is the invoice amount?") == "Invoice", "Invoice intent failed"
    
    print("[OK] All intent detection tests passed.\n")


# ──────────────────────────────────────────────
# Test 2: Fact Extraction — Structured Entities
# ──────────────────────────────────────────────
def test_fact_extraction():
    print("Testing structured fact extraction...")
    
    resume_text = """Name: John Doe
Email: john.doe@example.com
Phone: +1-555-123-4567
Skills: Python, React, Node.js
Experience: 5 years
Education: B.Tech Computer Science"""
    
    facts = extract_facts(resume_text, "Resume")
    assert "Email" in facts, "Email not extracted"
    assert facts["Email"] == "john.doe@example.com", f"Email wrong: {facts['Email']}"
    assert "Phone" in facts, "Phone not extracted"
    assert "Name" in facts, "Name not extracted from KV"
    print(f"  Extracted facts: {facts}")
    
    invoice_text = """Invoice Number: INV-2024-001
Amount: $3,200.00
Tax: 18%
Due Date: 15/01/2025"""
    
    facts2 = extract_facts(invoice_text, "Invoice")
    assert "Amount" in facts2, "Amount not extracted"
    assert "Percentage" in facts2, "Percentage not extracted"
    assert "Date" in facts2, "Date not extracted"
    print(f"  Invoice facts: {facts2}")
    
    print("[OK] All fact extraction tests passed.\n")


# ──────────────────────────────────────────────
# Test 3: Resume QA — Reasoning with Facts
# ──────────────────────────────────────────────
def test_resume_qa():
    print("Testing resume QA reasoning...")
    
    context = """Name: John Doe
Email: john.doe@example.com
Phone: +1-555-123-4567

Skills: Python, React, Node.js, Docker
Experience: 5 years as a Full Stack Developer
Education: B.Tech Computer Science from MIT"""
    
    ans, conf = reasoning_service.reason(context, "What is the candidate's email?", intent="Resume")
    print(f"  Answer: {ans}")
    print(f"  Confidence: {conf:.1f}%")
    assert "john.doe@example.com" in ans.lower(), f"Email not in answer: {ans}"
    assert conf > 0.0, "Confidence should be positive"
    
    print("[OK] Resume QA test passed.\n")


# ──────────────────────────────────────────────
# Test 4: Invoice QA — Amount Extraction
# ──────────────────────────────────────────────
def test_invoice_qa():
    print("Testing invoice QA reasoning...")
    
    context = """Invoice Number: INV-2024-001
Customer: Acme Corp
Amount: $3,200.00
GST: 18%
Due Date: 15/01/2025"""
    
    ans, conf = reasoning_service.reason(context, "What is the invoice amount?", intent="Invoice")
    print(f"  Answer: {ans}")
    print(f"  Confidence: {conf:.1f}%")
    assert "3,200" in ans or "3200" in ans, f"Amount not in answer: {ans}"
    
    print("[OK] Invoice QA test passed.\n")


# ──────────────────────────────────────────────
# Test 5: Zero-Confidence — No Information Available
# ──────────────────────────────────────────────
def test_zero_confidence():
    print("Testing zero-confidence guard...")
    
    # Empty context
    ans, conf = reasoning_service.reason("", "What is the weather?")
    assert "couldn't find" in ans.lower(), f"Expected not-found message, got: {ans}"
    assert conf == 0.0, f"Expected 0.0 confidence, got: {conf}"
    
    print(f"  Answer: {ans}")
    print("[OK] Zero-confidence guard passed.\n")


# ──────────────────────────────────────────────
# Test 6: Sources Suppression on Zero Confidence
# ──────────────────────────────────────────────
def test_sources_suppression():
    print("Testing sources suppression on zero confidence...")
    
    formatted = answer_formatter.format_response(
        answer="I couldn't find that information in the uploaded document.",
        confidence=0.0,
        retrieved_chunks=[{"text": "dummy", "chunk_id": "doc_chunk_0", "page_number": 1, "section": "Content", "score": 0.1}],
        intent="Question Answering"
    )
    assert "**Sources:**" not in formatted["answer"], f"Sources should be suppressed: {formatted['answer']}"
    
    print("[OK] Sources suppression test passed.\n")


# ──────────────────────────────────────────────
# Test 7: Extraction Formatting
# ──────────────────────────────────────────────
def test_extraction_formatting():
    print("Testing extraction intent formatting...")
    
    answer = "the email is john@example.com. Additionally, the phone is +1-555-123-4567. Furthermore, the name is John Doe."
    formatted = format_extraction_answer(answer)
    print(f"  Formatted:\n{formatted}\n")
    assert "## Extracted Information" in formatted, "Missing extraction header"
    assert "john@example.com" in formatted, "Missing email in formatted output"
    
    print("[OK] Extraction formatting test passed.\n")


# ──────────────────────────────────────────────
# Test 8: Natural Connectors in Multi-Sentence Answer
# ──────────────────────────────────────────────
def test_natural_connectors():
    print("Testing natural connectors in merged sentences...")
    
    context = """The company was founded in 2010.

The headquarters is located in San Francisco.

The company has 500 employees worldwide."""
    
    ans, conf = reasoning_service.reason(context, "Tell me about the company", intent="Summary")
    print(f"  Answer: {ans}")
    # Check that at least one connector word is present
    connectors_found = any(c in ans for c in ["Additionally", "Furthermore", "Also", "Moreover"])
    assert connectors_found, f"No natural connectors found in: {ans}"
    
    print("[OK] Natural connectors test passed.\n")


# ──────────────────────────────────────────────
# Test 9: Context Builder — Intent-Aware Sizing
# ──────────────────────────────────────────────
def test_context_builder_sizing():
    print("Testing context builder intent-aware sizing...")
    
    # Create mock chunks with enough text to exceed 1500 chars
    long_text = "This is a test sentence about company policies and procedures. " * 30
    chunks = [{"text": long_text, "page_number": 1, "section": "Content", "chunk_id": "test_chunk_0"}]
    
    # Summary intent should allow 2500 chars
    ctx_summary = context_builder.build_context("Summarize", chunks, intent="Summary")
    # Invoice intent should limit to 1000 chars
    ctx_invoice = context_builder.build_context("What is the amount?", chunks, intent="Invoice")
    
    print(f"  Summary context length: {len(ctx_summary)} chars")
    print(f"  Invoice context length: {len(ctx_invoice)} chars")
    assert len(ctx_summary) >= len(ctx_invoice), "Summary context should be >= Invoice context"
    
    print("[OK] Context builder sizing test passed.\n")


# ──────────────────────────────────────────────
# Test 10: Chunk Service — Content Type Detection
# ──────────────────────────────────────────────
def test_content_type_detection():
    print("Testing chunk content type detection...")
    
    assert chunk_service.detect_content_type("# Main Heading") == "heading"
    assert chunk_service.detect_content_type("- Item 1\n- Item 2\n- Item 3") == "list"
    assert chunk_service.detect_content_type("Name | Age | City\nJohn | 30 | NYC\nJane | 25 | LA") == "table"
    assert chunk_service.detect_content_type("This is a normal paragraph of text.") == "text"
    
    print("[OK] Content type detection test passed.\n")


# ──────────────────────────────────────────────
# Run all tests
# ──────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("DOCUMENT INTELLIGENCE ENGINE — VERIFICATION SUITE")
    print("=" * 60 + "\n")
    
    test_intent_detection()
    test_fact_extraction()
    test_resume_qa()
    test_invoice_qa()
    test_zero_confidence()
    test_sources_suppression()
    test_extraction_formatting()
    test_natural_connectors()
    test_context_builder_sizing()
    test_content_type_detection()
    
    print("=" * 60)
    print("ALL VERIFICATION TESTS PASSED!")
    print("=" * 60)
