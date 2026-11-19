import time
import json
from backend.app.services.document_parser import document_parser
from backend.app.services.tender_intelligence.intelligence_engine import tender_intelligence_engine

pdf_path = r"D:\MYGPT\gemma_tender_manual_test\uploads\265f816f_Tendernotice_2 (5).pdf"
doc = {"filename": "Tendernotice_2 (5).pdf", "file_path": pdf_path}

print("=== Starting Fresh Tender Evaluation (Fast Hybrid) ===")
t0 = time.time()
report = tender_intelligence_engine.evaluate_tender([doc], force_refresh=True, mode="fast")
total_t = time.time() - t0

print("\n" + "=" * 60)
print(f"EVALUATION COMPLETED IN: {total_t:.2f} seconds (reported elapsed: {report.elapsed_seconds}s)")
print("=" * 60)
print(f"Model Used: {report.model_used}")
print(f"Total Pages Analyzed: {report.total_pages_analyzed}")
print(f"Validation Status: {report.validation_status}")
print(f"Cache Hit: {report.cache_hit}")

print("\n--- 1. Overview ---")
print(f"Title: {report.overview.tender_title}")
print(f"Authority: {report.overview.department_organization}")
print(f"Tender Ref: {report.overview.tender_reference_number}")
print(f"EMD Value: {report.overview.emd_value}")
print(f"Tender Fee: {report.overview.tender_fee}")
print(f"Deadline: {report.overview.bid_submission_deadline}")
print(f"Citations count: {len(report.overview.citations)}")

print("\n--- 2. Eligibility & PQ ---")
print(f"Turnover: {report.eligibility.annual_turnover_requirement}")
print(f"Average Turnover: {report.eligibility.average_turnover_requirement}")
print(f"Similar Work: {report.eligibility.similar_work_experience}")
print(f"OEM Auth Mandatory: {report.eligibility.oem_authorization_mandatory}")
print(f"Conditions Count: {len(report.eligibility.conditions)}")
for c in report.eligibility.conditions:
    print(f"  [{c.category}] (Page {c.source_page}): {c.department_requirement[:60]}...")

print("\n--- 3. Technical Scope ---")
print(f"Scope Items Count: {len(report.technical_scope.scope_items)}")
for s in report.technical_scope.scope_items:
    print(f"  [{s.area}] (Page {s.source_page}): {s.description[:60]}...")

print("\n--- 4. Technical Specifications ---")
print(f"Items Count: {len(report.technical_specifications.items)}")
for it in report.technical_specifications.items[:4]:
    print(f"  [{it.item_name}] (Page {it.source_page}): {it.technical_specifications[:60]}...")

print("\n--- 5. OEM Requirements ---")
print(f"Has OEM Conditions: {report.oem_requirements.has_oem_conditions}")
print(f"OEM Auth Required: {report.oem_requirements.oem_authorization_required}")
print(f"OEM Items Count: {len(report.oem_requirements.oem_requirements)}")

print("\n--- 6. Compliance Matrix ---")
print(f"Compliance Items Count: {len(report.compliance_matrix.items)}")
for cm in report.compliance_matrix.items[:3]:
    print(f"  [{cm.item}] Ref: {cm.tender_reference} | Status: {cm.compliance_assessment}")

print("\n--- 7. Commercial & Financial ---")
print(f"Payment Terms: {report.commercial_financial.payment_terms[:70]}...")
print(f"Advance Payment: {report.commercial_financial.advance_payment_allowed}")
print(f"Liquidated Damages: {report.commercial_financial.penalties_and_liquidated_damages[:70]}...")
print(f"PBG / Security: {report.commercial_financial.performance_bank_guarantee_pbg}")

print("\n--- 8. Contractual & Legal ---")
print(f"Contract Duration: {report.contractual_legal.contract_duration}")
print(f"Significant Clauses Count: {len(report.contractual_legal.significant_risk_clauses)}")

print("\n--- 9. Risks & Contradictions ---")
print(f"Critical Risks: {report.risks_and_contradictions.critical_risks_count}")
print(f"High Risks: {report.risks_and_contradictions.high_risks_count}")
print(f"Total Risks Count: {len(report.risks_and_contradictions.risks)}")
for r in report.risks_and_contradictions.risks:
    print(f"  [{r.risk_level}] (Page {r.source_page}) {r.risk_title}: {r.why_it_matters[:50]}...")

print("\n--- 10. Bid Strategy ---")
print(f"Recommendation: {report.bid_strategy.recommendation}")
print(f"Rationale: {report.bid_strategy.recommendation_rationale}")
print(f"Pre-bid Queries Count: {len(report.bid_strategy.prebid_clarification_questions)}")
for q in report.bid_strategy.prebid_clarification_questions:
    print(f"  - {q}")

print("\n--- 11. Action Roadmap ---")
print(f"Checklist Items Count: {len(report.action_roadmap.checklist)}")
for a in report.action_roadmap.checklist:
    print(f"  Step {a.step_number}: {a.activity} (Page {a.relevant_tender_page})")

print("\n--- Presentation Exports ---")
print(f"Executive Summary Markdown: {len(report.executive_summary_markdown)} chars")
print(f"Full Report Markdown: {len(report.full_report_markdown)} chars")
print("\n=== TEST PASSED SUCCESSFULLY ===")

