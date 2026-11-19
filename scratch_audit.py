import sys, json, time
sys.path.insert(0, 'backend')
from app.services.document_manager import DocumentManager
from app.services.tender.tender_extractor import TenderExtractor
from app.services.tender_intelligence.intelligence_retriever import intelligence_retriever
from app.services.tender_intelligence.intelligence_extractors import (
    extract_overview_facts,
    extract_eligibility_conditions,
    extract_technical_specifications,
    extract_commercial_and_legal,
)

dm = DocumentManager()
ext = TenderExtractor()

benchmarks = {
    "NITK_Desktop_41p": "DOC4THighEndDesktop",
    "Women_Safety_CCTV_170p": "womensafetycctv",
    "EESL_Energy_149p": "RfP_EMST",
    "Tripura_WiFi_33p": "Tendernotice_2 (5)",
}

audit_summary = {}

for b_name, kw in benchmarks.items():
    print(f"\n==========================================")
    print(f"EVALUATING: {b_name} (Search keyword: '{kw}')")
    print(f"==========================================")
    docs = [d for d in dm.list_documents() if kw.lower() in d.get('filename','').lower()]
    if not docs:
        print(f"ERROR: Document for {b_name} not found in database!")
        continue
    doc = dm.get_document(docs[0]['id'])
    
    # 1. Prepare records & index
    index, records, _ = intelligence_retriever.prepare_index([doc])
    print(f"Loaded {len(records)} page records.")
    
    # 2. Extract anchors with TenderExtractor
    extraction_res = ext.extract_from_documents([doc], use_llm=False, bypass_cache=True)
    flat = extraction_res.all_fields_flat()
    anchors = {
        "bid_title": flat.get("bid_title", {}).value or "Not specified",
        "authority": flat.get("department_organization", {}).value or "Not specified",
        "tender_id": flat.get("tender_id", {}).value or "Not specified",
        "estimated_value": flat.get("estimated_tender_value", {}).value or "Not specified",
        "emd_value": flat.get("bid_emd_value", {}).value or "Not specified",
        "submission_deadline": flat.get("bid_submission_end", {}).value or "Not specified",
        "technical_bid_opening_date": flat.get("technical_bid_opening_date", {}).value or flat.get("bid_opening_date", {}).value or "Not specified",
        "tender_publication_date": flat.get("tender_publication_date", {}).value or "Not specified",
        "category": flat.get("category", {}).value or "Not specified",
        "state": flat.get("state", {}).value or "Not specified",
    }
    print(f"Anchors: EMD={anchors['emd_value']}, Deadline={anchors['submission_deadline']}, Authority={anchors['authority'][:40]}")
    
    # 3. Intelligence Extractors
    overview, scope = extract_overview_facts(records, anchors)
    eligibility = extract_eligibility_conditions(records, index)
    specs, oem, compliance = extract_technical_specifications(records, index)
    commercial, legal = extract_commercial_and_legal(records, index, anchors)
    
    # Inspect Specs for TOC or Metadata leaks
    sample_spec_names = [it.item_name for it in specs.items[:15]]
    has_toc = any("section" in s.lower() or "contents" in s.lower() for s in sample_spec_names)
    has_top_sheet = any(s in ["NameofGoods", "TheestimatedamountputtoTender", "EMDAmount(2%ofestimatedamount)", "TimeforSupplyofitem", "DateofissuanceofIFB"] for s in sample_spec_names)
    
    audit_summary[b_name] = {
        "anchors": anchors,
        "overview": {
            "title": overview.tender_title,
            "ref_no": overview.tender_reference_number,
            "authority": overview.department_organization,
            "inviting_authority": overview.tender_inviting_authority,
            "est_value": overview.estimated_project_value,
            "emd_value": overview.emd_value,
            "submission_deadline": overview.bid_submission_deadline,
            "opening_date": overview.bid_opening_date,
            "pub_date": overview.tender_publishing_date,
            "warranty": overview.warranty_maintenance_period,
        },
        "eligibility": {
            "turnover": eligibility.annual_turnover_requirement,
            "similar_experience": eligibility.similar_work_experience,
            "min_project_value": eligibility.minimum_project_value,
            "oem_mandatory": eligibility.oem_authorization_mandatory,
            "conditions_count": len(eligibility.conditions),
        },
        "specs": {
            "total_specs": len(specs.items),
            "subsystems_count": len(specs.subsystems),
            "sample_specs": sample_spec_names[:6],
            "has_toc_leak": has_toc,
            "has_top_sheet_leak": has_top_sheet,
        },
        "commercial": {
            "estimated_value": commercial.estimated_value,
            "emd_amount": commercial.emd_amount,
            "emd_amount_and_mode": commercial.emd_amount_and_mode,
            "pbg": commercial.performance_bank_guarantee_pbg,
            "liquidated_damages": commercial.penalties_and_liquidated_damages,
        }
    }
    
    print(f"--- RESULTS FOR {b_name} ---")
    print(f"  Overview EMD: {overview.emd_value}")
    print(f"  Commercial EMD: {commercial.emd_amount}")
    print(f"  Submission Deadline: {overview.bid_submission_deadline}")
    print(f"  Opening Date: {overview.bid_opening_date}")
    print(f"  Authority: {overview.department_organization}")
    print(f"  Similar Exp: {eligibility.similar_work_experience[:80] if eligibility.similar_work_experience else None}")
    print(f"  Min Project Val: {eligibility.minimum_project_value}")
    print(f"  LD: {commercial.penalties_and_liquidated_damages[:100] if commercial.penalties_and_liquidated_damages else None}")
    print(f"  Specs Count: {len(specs.items)} (TOC Leak: {has_toc}, TopSheet Leak: {has_top_sheet})")

with open("post_repair_audit_results.json", "w", encoding="utf-8") as f:
    json.dump(audit_summary, f, indent=2)

print("\nWrote post_repair_audit_results.json successfully.")
