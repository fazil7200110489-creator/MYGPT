"""Verification script for Milestone 3 of the local Document Assistant.
"""

import os
import sys

# Add project root directory to path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from backend.app.services.context_builder import context_builder
from backend.app.services.reasoning_service import reasoning_service
from backend.app.services.answer_formatter import answer_formatter


def run_verification():
    print("=========================================")
    print("RUNNING MILESTONE 3 VERIFICATION TESTS")
    print("=========================================")

    # 1. Test Context Builder
    print("\n[Test 1] Testing context building & deduplication...")
    chunks = [
        {"page_number": 1, "section": "Leave Policy", "text": "Employees get 20 days of paid leave."},
        {"page_number": 1, "section": "Leave Policy", "text": "Employees get 20 days of paid leave."},  # Duplicate
        {"page_number": 2, "section": "Probation", "text": "Probationary period is 6 months."}
    ]
    context = context_builder.build_context("leave policy", chunks, max_context_chars=100)
    print("Aggregated Context:")
    print(context)
    assert "[Page 1 | Section: Leave Policy]" in context
    # Check deduplication
    assert context.count("Employees get 20 days of paid leave.") == 1, "Deduplication failed"
    print("[OK] Context building passed!")

    # 2. Test Reasoning Engine QA & Fallback
    print("\n[Test 2] Testing reasoning with MyGPT...")
    # Test valid answer
    ans, conf, _ = reasoning_service.reason(context, "How much paid leave is allowed?")
    print(f"Answer: '{ans}' (Confidence: {conf:.4f})")
    assert "20 days" in ans, "Failed to locate correct answer in context"
    assert conf > 0.0, "Confidence should be positive for hit"

    # Test fallback statement for missing info
    fallback_ans, fallback_conf = reasoning_service.reason(context, "What is the company revenue?")
    print(f"Fallback Answer: '{fallback_ans}' (Confidence: {fallback_conf:.4f})")
    assert "couldn't find" in fallback_ans.lower(), "Missing fallback response"
    assert fallback_conf == 0.0, "Fallback confidence should be 0.0"
    print("[OK] Reasoning and fallback checks passed!")

    # 3. Test Answer Formatter
    print("\n[Test 3] Testing answer formatting...")
    formatted = answer_formatter.format_response(ans, conf, chunks)
    assert "answer" in formatted
    assert "confidence" in formatted
    assert "sources" in formatted
    assert "suggested_questions" in formatted
    assert formatted["confidence"] == round(conf * 100, 1)
    # Check duplicate sources are filtered out
    assert len(formatted["sources"]) == 2, "Formatting source deduplication failed"
    print("Suggested Questions:")
    print(formatted["suggested_questions"])
    print("[OK] Formatting checks passed!")

    print("\n=========================================")
    print("ALL MILESTONE 3 VERIFICATION TESTS PASSED!")
    print("=========================================")
    return True


if __name__ == "__main__":
    success = run_verification()
    sys.exit(0 if success else 1)
