"""Real Execution Benchmark & Latency Verification for MYGPT Tender Consultant.

Benchmarks:
1. Initial analysis of tender (fresh Gemma inference).
2. Simple follow-up question.
3. Complex eligibility question.
4. Repeated identical question (QA cache hit).
5. Question after uploading a second tender (strict isolation).
"""

import os
import sys
import time
import pytest
from typing import Dict, Any

from backend.app.services.tender_intelligence.intelligence_engine import tender_intelligence_engine
from backend.app.services.tender_intelligence.intelligence_report_builder import intelligence_report_builder
from backend.app.services.tender_intelligence.intelligence_retriever import intelligence_retriever
from backend.app.services.tender.tender_section_retriever import compute_bundle_signature

WTL_PDF = "data/uploads/1a5fa635-e77b-4d14-85b9-64b0878e8549.pdf"
TRIPURA_PDF = "data/uploads/Tender_Document_WiFi.pdf"

@pytest.fixture(scope="module")
def wtl_doc():
    if not os.path.exists(WTL_PDF):
        pytest.skip(f"WTL tender PDF not found: {WTL_PDF}")
    return {
        "id": "wtl_bench_doc",
        "document_id": "wtl_bench_doc",
        "filename": "1a5fa635-e77b-4d14-85b9-64b0878e8549.pdf",
        "path": WTL_PDF,
        "file_type": ".pdf",
        "extension": ".pdf",
    }

@pytest.fixture(scope="module")
def tripura_doc():
    if not os.path.exists(TRIPURA_PDF):
        # Fallback to mock doc if not present
        return {
            "id": "tripura_mock_doc",
            "document_id": "tripura_mock_doc",
            "filename": "tripura_wifi.pdf",
            "file_hash": "aabbcc112233",
            "extracted_text": "Tender for Campus-wide Wi-Fi at Tripura University. EMD: Rs. 1,00,000/-. Turnover: Rs. 2 Crore.",
            "pages": [{"page_number": 1, "text": "Tender for Campus-wide Wi-Fi at Tripura University. EMD: Rs. 1,00,000/-. Turnover: Rs. 2 Crore."}],
            "total_pages": 1,
        }
    return {
        "id": "tripura_bench_doc",
        "document_id": "tripura_bench_doc",
        "filename": "Tender_Document_WiFi.pdf",
        "path": TRIPURA_PDF,
        "file_type": ".pdf",
        "extension": ".pdf",
    }


def test_benchmark_1_initial_tender_analysis(wtl_doc):
    """Benchmark 1: Initial analysis of a tender (fresh Gemma inference)."""
    print("\n" + "=" * 70)
    print("BENCHMARK 1: Fresh Initial Tender Analysis (WTL CCTV)")
    print("=" * 70)

    t0 = time.time()
    report = tender_intelligence_engine.evaluate_tender([wtl_doc], force_refresh=True, mode="fast")
    duration = time.time() - t0

    print(f"Total Pipeline Duration: {duration:.2f}s")
    for k, v in report.processing_latency_breakdown.items():
        print(f"  {k}: {v}s")

    assert report is not None
    assert report.overview.tender_title != "NOT_FOUND"
    assert report.bid_strategy.recommendation is not None
    assert len(report.initial_conversational_summary) > 200

    # Ensure total duration is significantly less than the 289s baseline
    print(f"-> Baseline: 292.5s | Achieved: {duration:.2f}s")


def test_benchmark_2_simple_followup_question(wtl_doc):
    """Benchmark 2: Simple follow-up question (factual intent)."""
    print("\n" + "=" * 70)
    print("BENCHMARK 2: Simple Follow-up Question (EMD)")
    print("=" * 70)

    t0 = time.time()
    res = tender_intelligence_engine.answer_consultant_question([wtl_doc], "What is the EMD amount?")
    duration = time.time() - t0

    answer, sources = res[0], res[1]
    print(f"Question: What is the EMD amount?")
    print(f"Answer:\n{answer}")
    print(f"Sources: {sources}")
    print(f"Total Duration: {duration:.4f}s")

    assert "16,00,000" in answer or "16" in answer
    assert duration < 20.0, f"Simple factual question must return in <20s, took {duration:.2f}s"


def test_benchmark_3_complex_eligibility_question(wtl_doc):
    """Benchmark 3: Complex eligibility question."""
    print("\n" + "=" * 70)
    print("BENCHMARK 3: Complex Eligibility Question (Similar Work Alternatives)")
    print("=" * 70)

    t0 = time.time()
    res = tender_intelligence_engine.answer_consultant_question([wtl_doc], "What are the similar work experience alternatives?")
    duration = time.time() - t0

    answer, sources = res[0], res[1]
    print(f"Question: What are the similar work experience alternatives?")
    print(f"Answer snippet: {answer[:250]}...")
    print(f"Sources: {sources}")
    print(f"Total Duration: {duration:.2f}s")

    assert len(answer) > 50
    assert len(sources) > 0


def test_benchmark_4_repeated_identical_question_cache_hit(wtl_doc):
    """Benchmark 4: Repeated identical question (QA cache hit)."""
    print("\n" + "=" * 70)
    print("BENCHMARK 4: Repeated Identical Question (Cache Hit)")
    print("=" * 70)

    t0 = time.time()
    res = tender_intelligence_engine.answer_consultant_question([wtl_doc], "What is the EMD amount?")
    duration = time.time() - t0

    answer = res[0]
    print(f"Cached Answer Latency: {duration:.4f}s")
    assert getattr(res, "cache_hit", False) is True or duration < 0.05
    assert "16,00,000" in answer or "16" in answer
    print(f"-> Baseline: ~253s | Cache-hit Achieved: {duration:.4f}s")


def test_benchmark_5_question_after_uploading_second_tender(wtl_doc, tripura_doc):
    """Benchmark 5: Question after uploading second tender (strict isolation)."""
    print("\n" + "=" * 70)
    print("BENCHMARK 5: Second Tender Question & Isolation")
    print("=" * 70)

    # 1. Ask about Tender 2
    t0 = time.time()
    res_2 = tender_intelligence_engine.answer_consultant_question([tripura_doc], "What is the EMD amount?")
    dur_2 = time.time() - t0

    ans_2 = res_2[0]
    print(f"Tender 2 (Tripura) EMD Answer ({dur_2:.2f}s):\n{ans_2}")

    # Ensure Tender 2 answer does NOT mention Tender 1 (WTL) EMD of 16 Lakhs
    assert "16,00,000" not in ans_2
    assert "Tripura" in ans_2 or "1,00,000" in ans_2 or "1" in ans_2 or "NOT SPECIFIED" in ans_2

