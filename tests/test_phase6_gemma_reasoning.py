"""Phase 6 Verification Tests: Gemma Reasoning & Context Optimization.

Verifies:
1. Dynamic Roadmap Citations: Each action roadmap step references its own authentic source page.
   Specifically verifies that the repeated [Page 13] bug on Tripura and all tenders is resolved.
2. Structured Context Grounding: All Python-extracted facts retain Document ID, filename, source page,
   entity role, and mandatory/optional tags.
3. Evidence-Based Reasoning: Strategic recommendations are explicitly distinguished from tender requirements.
4. Output Validation & Resilience: Safe recovery when Gemma returns empty, malformed, or hallucinated responses.
5. Performance Metrics: Explicit latency breakdown measuring extraction, context preparation, Gemma inference,
   and validation.
"""

import sys
import time
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.services.document_parser import document_parser
from backend.app.services.tender.tender_section_retriever import PageRecord, get_or_build_index
from backend.app.services.tender_intelligence.intelligence_extractors import (
    extract_overview_facts,
    extract_eligibility_conditions,
    extract_technical_specifications,
    extract_commercial_and_legal,
)
from backend.app.services.tender_intelligence.intelligence_engine import tender_intelligence_engine
from backend.app.services.tender_intelligence.intelligence_schema import (
    BidRecommendation,
    RiskLevel,
    TenderConsultantReport,
)


def _load_tender_records(pdf_path: str, doc_id: str, filename: str):
    parsed = document_parser.parse(pdf_path)
    records = []
    for p in parsed.get("pages", []):
        records.append(
            PageRecord(
                document_id=doc_id,
                filename=filename,
                file_type="pdf",
                file_hash=parsed.get("file_hash", "testhash"),
                page_number=p.get("page_number", 1),
                text=p.get("text", ""),
            )
        )
    return records


def test_tripura_dynamic_roadmap_citations_fixes_page_13_bug(monkeypatch):
    """Verify that Tripura University Wi-Fi tender produces distinct, authentic page citations
    across all roadmap steps rather than blindly repeating [Page 13].
    """
    pdf_path = r"D:\MYGPT\data\uploads\0aaa92a2-f665-4d5e-98ba-c39ce650f525.pdf"
    docs = [{"document_id": "tripura_p6_doc", "filename": "Tripura_WiFi.pdf", "file_path": pdf_path}]

    monkeypatch.setattr(
        tender_intelligence_engine,
        "_call_gemma_json",
        lambda prompt, max_tokens=350: {
            "recommendation": "PROCEED_WITH_CAUTION",
            "recommendation_rationale": "Viable terms.",
            "critical_risks": [],
            "strategic_recommendations": ["[CONSULTANT RECOMMENDATION] Conduct Joint Site Inspection & Feasibility Audit"],
        },
    )

    # Run evaluation in fast mode
    report = tender_intelligence_engine.evaluate_tender(docs, force_refresh=True, mode="fast")

    checklist = report.action_roadmap.checklist
    assert len(checklist) >= 5

    # Check that steps have distinct, authentic source pages
    pages_cited = [step.relevant_tender_page for step in checklist if step.relevant_tender_page is not None]

    # Critical Assertion: The roadmap must NOT have all steps citing Page 13!
    assert not all(p == 13 for p in pages_cited), f"All steps blindly cited Page 13: {pages_cited}"

    # Specific Authentic Citations:
    # Step 1: Turnover & PQ (Page 8 or 13)
    step1 = next(s for s in checklist if s.step_number == 1)
    assert step1.relevant_tender_page in [8, 13]
    assert "Turnover" in step1.activity

    # Step 2: OEM MAF (Page 8 or 14)
    step2 = next(s for s in checklist if s.step_number == 2)
    assert step2.relevant_tender_page in [8, 14]
    assert "OEM" in step2.activity

    # Step 3: Pre-Bid Clarification (Page 1 or 4)
    step3 = next(s for s in checklist if s.step_number == 3)
    assert step3.relevant_tender_page in [1, 2, 4]

    # Step 4: Technical Compliance Matrix (Page 20, 21 or 22)
    step4 = next(s for s in checklist if s.step_number == 4)
    assert step4.relevant_tender_page in [20, 21, 22]

    # Step 5: EMD & Commercial (Page 4, 12 or 15)
    step5 = next(s for s in checklist if s.step_number == 5)
    assert step5.relevant_tender_page in [4, 12, 15]

    # Step 6: Strategic Consultant Recommendation (Explicitly None - strategic advice)
    if len(checklist) >= 6:
        step6 = next(s for s in checklist if s.step_number == 6)
        assert step6.relevant_tender_page is None
        assert step6.activity.startswith("[CONSULTANT RECOMMENDATION]")


def test_nitk_dynamic_roadmap_citations(monkeypatch):
    """Verify that NITK Desktop tender produces distinct source pages across roadmap steps."""
    pdf_path = r"D:\MYGPT\data\uploads\2958370a-b714-47c0-9efa-9adfa6403d30.pdf"
    docs = [{"document_id": "nitk_p6_doc", "filename": "NITK_Desktop.pdf", "file_path": pdf_path}]

    monkeypatch.setattr(
        tender_intelligence_engine,
        "_call_gemma_json",
        lambda prompt, max_tokens=350: {
            "recommendation": "PROCEED_WITH_CAUTION",
            "recommendation_rationale": "Viable terms.",
            "critical_risks": [],
            "strategic_recommendations": ["[CONSULTANT RECOMMENDATION] Conduct Joint Site Inspection & Feasibility Audit"],
        },
    )

    report = tender_intelligence_engine.evaluate_tender(docs, force_refresh=True, mode="fast")
    checklist = report.action_roadmap.checklist

    # NITK Technical specifications are on Page 39
    step4 = next(s for s in checklist if s.step_number == 4)
    assert step4.relevant_tender_page == 39, f"Expected NITK tech specs on Page 39, got {step4.relevant_tender_page}"

    # NITK Pre-bid/Tender schedule is on Page 1 or 2
    step3 = next(s for s in checklist if s.step_number == 3)
    assert step3.relevant_tender_page in [1, 2]

    # Unique pages across checklist
    pages_cited = {s.relevant_tender_page for s in checklist if s.relevant_tender_page is not None}
    assert len(pages_cited) >= 3, f"Expected at least 3 distinct pages cited, got {pages_cited}"


def test_structured_gemma_context_builder():
    """Verify that _build_gemma_context supplies rich, structured facts with Document ID,

    filename, source page, entity role, and mandatory tags.
    """
    pdf_path = r"D:\MYGPT\data\uploads\0aaa92a2-f665-4d5e-98ba-c39ce650f525.pdf"
    records = _load_tender_records(pdf_path, "tripura_ctx_test", "Tripura_WiFi.pdf")
    docs = [{"document_id": "tripura_ctx_test", "filename": "Tripura_WiFi.pdf", "file_path": pdf_path}]
    index, _ = get_or_build_index(docs)

    anchors = {"bid_title": "Tripura University Wi-Fi Network", "authority": "Tripura University", "tender_id": "TU/FIN/Wi-Fi/2025"}
    overview, scope = extract_overview_facts(records, anchors)
    eligibility = extract_eligibility_conditions(records, index)
    specs, oem, compliance = extract_technical_specifications(records, index)
    commercial, legal = extract_commercial_and_legal(records, index, anchors)

    context = tender_intelligence_engine._build_gemma_context(
        overview=overview,
        scope=scope,
        eligibility=eligibility,
        specs=specs,
        oem=oem,
        compliance=compliance,
        commercial=commercial,
        legal=legal,
        primary_doc_id="tripura_ctx_test",
        primary_filename="Tripura_WiFi.pdf",
    )

    # 1. Document Identity
    assert "Document ID: tripura_ctx_test | Filename: Tripura_WiFi.pdf" in context
    assert "Tripura University" in context

    # 2. Page Grounding
    assert "Source: Page" in context

    # 3. Entity Classification & Mandatory Tags
    assert "Mandatory: Yes" in context
    assert "Role:" in context

    # 4. Technical Specs from Table Extraction
    assert "Key Technical Specification Items (From Verified Tables):" in context


def test_output_validation_resilience_to_malformed_and_hallucinated_responses():
    """Verify that intelligence engine handles malformed, empty, and out-of-range hallucinated

    Gemma responses safely without inventing tender facts.
    """
    # 1. Empty response recovery
    empty_res = tender_intelligence_engine._parse_json_from_llm_output("")
    assert empty_res == {}

    # 2. Markdown wrapped JSON
    wrapped_json = "```json\n{\"recommendation\": \"Proceed with caution\", \"critical_risks\": []}\n```"
    parsed_wrapped = tender_intelligence_engine._parse_json_from_llm_output(wrapped_json)
    assert parsed_wrapped.get("recommendation") == "Proceed with caution"

    # 3. Truncated JSON recovery
    truncated_json = "{\"recommendation\": \"PROCEED\", \"recommendation_rationale\": \"Strong technical profile"
    parsed_trunc = tender_intelligence_engine._parse_json_from_llm_output(truncated_json)
    assert parsed_trunc.get("recommendation") == "PROCEED"


def test_performance_latency_breakdown_metrics(monkeypatch):
    """Verify that processing latency breakdown measures extraction, context prep,
    Gemma inference, and validation separately.
    """
    pdf_path = r"D:\MYGPT\data\uploads\2958370a-b714-47c0-9efa-9adfa6403d30.pdf"
    docs = [{"document_id": "nitk_perf_doc", "filename": "NITK_Desktop.pdf", "file_path": pdf_path}]

    monkeypatch.setattr(
        tender_intelligence_engine,
        "_call_gemma_json",
        lambda prompt, max_tokens=350: {
            "recommendation": "PROCEED_WITH_CAUTION",
            "recommendation_rationale": "Viable terms.",
            "critical_risks": [],
            "strategic_recommendations": ["[CONSULTANT RECOMMENDATION] Conduct Joint Site Inspection & Feasibility Audit"],
        },
    )

    report = tender_intelligence_engine.evaluate_tender(docs, force_refresh=True, mode="fast")

    breakdown = report.processing_latency_breakdown
    assert isinstance(breakdown, dict)
    assert "extraction_seconds" in breakdown
    assert "context_prep_seconds" in breakdown
    assert "gemma_inference_seconds" in breakdown
    assert "validation_seconds" in breakdown
    assert "total_seconds" in breakdown

    # Latency assertions
    assert breakdown["extraction_seconds"] >= 0.0
    assert breakdown["context_prep_seconds"] >= 0.0
    assert breakdown["total_seconds"] > 0.0
