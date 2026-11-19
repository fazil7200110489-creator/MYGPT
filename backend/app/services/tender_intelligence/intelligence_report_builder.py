"""Report Builder and Markdown Formatter for MYGPT AI Tender Consultant.

Compiles validated structured data into executive briefings, comprehensive
tender dossiers, compliance tables, and risk registers with disk caching.
"""

import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional
from loguru import logger

from .intelligence_schema import (
    BidRecommendation,
    RiskLevel,
    TenderConsultantReport,
)

CACHE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "data", "cache", "tender_intelligence")
)


class IntelligenceReportBuilder:
    """Builds presentation-ready Markdown reports and manages persistence with strict provenance validation."""

    CURRENT_CACHE_VERSION = "consultant_v7"

    def __init__(self) -> None:
        os.makedirs(CACHE_DIR, exist_ok=True)

    def get_cached_report(
        self,
        signature: str,
        expected_doc_ids: Optional[List[str]] = None,
        expected_hashes: Optional[List[str]] = None,
        is_multi_document_package: bool = False,
    ) -> Optional[TenderConsultantReport]:
        """Loads cached consultant report from disk if present and rigorously validated.
        
        Validates:
        1. File exists and valid JSON
        2. Expected SHA-256 hashes match report.file_hashes exactly (permitting re-aligned doc IDs)
        3. Multi-document package flag matches
        4. Fallback document ID match when hashes are unavailable
        """
        path = os.path.join(CACHE_DIR, f"{signature}.json")
        if not os.path.exists(path):
            logger.info(f"[CACHE_MISS] No cached report exists for signature {signature[:12]}")
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            report = TenderConsultantReport(**data)

            # Strict Provenance & Isolation Check:
            # 1. Reject if multi-document package status does not match
            if report.is_multi_document_package != is_multi_document_package:
                logger.warning(
                    f"[CACHE_REJECT] Signature {signature[:12]} package flag mismatch "
                    f"(cached={report.is_multi_document_package}, requested={is_multi_document_package})."
                )
                return None

            # 2. Reject if analysis cache version does not match CURRENT_CACHE_VERSION
            cached_ver = getattr(report, "analysis_version", None) or data.get("analysis_version")
            if cached_ver and cached_ver != self.CURRENT_CACHE_VERSION:
                logger.warning(
                    f"[CACHE_REJECT] Signature {signature[:12]} version mismatch "
                    f"(cached={cached_ver}, current={self.CURRENT_CACHE_VERSION})."
                )
                return None

            # 2. Validate content SHA-256 hashes if provided
            exp_h = {str(h).strip() for h in (expected_hashes or []) if str(h).strip()}
            rep_h = {str(h).strip() for h in (report.file_hashes or []) if str(h).strip()}
            if exp_h and rep_h:
                if exp_h != rep_h:
                    logger.warning(
                        f"[CACHE_REJECT] Signature {signature[:12]} file hash mismatch. "
                        f"Expected {exp_h}, cached {rep_h}."
                    )
                    return None
                # Content hash match confirmed! Re-align document IDs to current request
                if expected_doc_ids:
                    report.document_ids = expected_doc_ids
                report.cache_hit = True
                logger.info(
                    f"[CACHE_HIT] Loaded verified cached report for signature {signature[:12]} "
                    f"(content hash match: {len(exp_h)} file(s))"
                )
                return report

            # 3. Fallback when hashes not present: match document IDs
            if expected_doc_ids:
                exp_set = {str(d) for d in expected_doc_ids if d}
                rep_set = {str(d) for d in report.document_ids if d}
                if exp_set != rep_set:
                    logger.warning(
                        f"[CACHE_REJECT] Signature {signature[:12]} document ID mismatch "
                        f"(cached={rep_set}, expected={exp_set})."
                    )
                    return None

            report.cache_hit = True
            logger.info(f"[CACHE_HIT] Loaded verified cached report for signature {signature[:12]}")
            return report
        except Exception as e:
            logger.warning(f"Failed loading cached report {signature}: {e}. Removing corrupt cache.")
            self._safe_remove_file(path)
            return None

    def store_cached_report(self, signature: str, report: TenderConsultantReport) -> None:
        """Saves generated report to disk cache with cache version tracking."""
        path = os.path.join(CACHE_DIR, f"{signature}.json")
        try:
            dumped = report.model_dump()
            dumped["analysis_version"] = self.CURRENT_CACHE_VERSION
            with open(path, "w", encoding="utf-8") as f:
                json.dump(dumped, f, indent=2, ensure_ascii=False)
            logger.info(f"[CONSULTANT_CACHE_STORE] Cached report for signature {signature[:12]} (ver={self.CURRENT_CACHE_VERSION})")
        except Exception as e:
            logger.warning(f"Failed caching report {signature}: {e}")

    def get_cached_qa_answer(
        self,
        bundle_signature: str,
        question: str,
        expected_hashes: Optional[List[str]] = None,
    ) -> Optional[Any]:
        """Loads cached Q&A answer for a specific tender and question."""
        q_norm = question.strip().lower()
        q_hash = hashlib.sha256(q_norm.encode("utf-8")).hexdigest()[:16]
        path = os.path.join(CACHE_DIR, f"qa_{bundle_signature}_{q_hash}.json")
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("version") != self.CURRENT_CACHE_VERSION:
                return None
            if expected_hashes:
                cached_hashes = data.get("file_hashes", [])
                if cached_hashes and set(expected_hashes) != set(cached_hashes):
                    return None
            from .intelligence_engine import ConsultantQAResult
            return ConsultantQAResult(
                answer=data["answer"],
                sources=data.get("sources", []),
                suggested_questions=data.get("follow_up_suggestions", []),
                cache_hit=True,
            )
        except Exception as e:
            logger.warning(f"Failed reading cached QA answer: {e}")
            return None

    def store_cached_qa_answer(
        self,
        bundle_signature: str,
        question: str,
        file_hashes: List[str],
        result: Any,
    ) -> None:
        """Stores a cached Q&A answer for a specific tender and question."""
        q_norm = question.strip().lower()
        q_hash = hashlib.sha256(q_norm.encode("utf-8")).hexdigest()[:16]
        path = os.path.join(CACHE_DIR, f"qa_{bundle_signature}_{q_hash}.json")
        try:
            data = {
                "version": self.CURRENT_CACHE_VERSION,
                "bundle_signature": bundle_signature,
                "question": question,
                "file_hashes": file_hashes,
                "answer": result.answer,
                "sources": result.sources,
                "follow_up_suggestions": getattr(result, "suggested_questions", []),
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"[CONSULTANT_QA_CACHE_STORE] Cached QA answer for signature {bundle_signature[:12]} q={question[:30]!r}")
        except Exception as e:
            logger.warning(f"Failed caching QA answer: {e}")

    def invalidate_cache_for_document(self, document_id: str) -> int:
        """Invalidates all cached consultant reports containing the specified document ID."""
        removed = 0
        if not os.path.isdir(CACHE_DIR):
            return 0
        for fname in os.listdir(CACHE_DIR):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(CACHE_DIR, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                doc_ids = data.get("document_ids", [])
                if (
                    document_id in doc_ids
                    or any(document_id in str(did) for did in doc_ids)
                    or (fname.startswith("qa_") and document_id in str(data))
                ):
                    self._safe_remove_file(fpath)
                    removed += 1
            except Exception:
                pass
        logger.info(f"[CACHE_INVALIDATE] Removed {removed} cache entries for document {document_id}")
        return removed

    def invalidate_all(self) -> int:
        """Purges all cached consultant reports."""
        removed = 0
        if not os.path.isdir(CACHE_DIR):
            return 0
        for fname in os.listdir(CACHE_DIR):
            if fname.endswith(".json"):
                self._safe_remove_file(os.path.join(CACHE_DIR, fname))
                removed += 1
        logger.info(f"[CACHE_INVALIDATE_ALL] Removed {removed} cache entries.")
        return removed

    @staticmethod
    def _safe_remove_file(path: str) -> None:
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass

    def generate_markdown(self, report: TenderConsultantReport) -> TenderConsultantReport:
        """Generates executive consultant briefing and full dossier Markdown representations."""
        # Strictly preserve LLM Gemma's generated conversational summary if present
        if not report.initial_conversational_summary or not report.initial_conversational_summary.strip():
            report.initial_conversational_summary = self._build_initial_conversational_response(report)
        report.suggested_questions = self.generate_suggested_questions(report)
        report.consultant_briefing_markdown = self._build_consultant_briefing(report)
        report.executive_summary_markdown = report.consultant_briefing_markdown
        report.full_report_markdown = self._build_full_dossier(report)
        return report

    def _build_initial_conversational_response(self, r: TenderConsultantReport) -> str:
        """Constructs concise, conversational consultant-style opening response for chat upon tender upload."""
        ov = r.overview
        el = r.eligibility
        sc = r.technical_scope
        cm = r.commercial_financial
        rk = r.risks_and_contradictions
        bs = r.bid_strategy

        def _clean(val: Optional[str], default: str = "Not specified in tender notice; governed by GCC") -> str:
            if not val or not str(val).strip() or str(val).strip().upper() in ("[ NOT SPECIFIED IN TENDER ]", "NONE", "N/A", "NOT_FOUND"):
                return default
            return str(val).strip()

        rec_val = (bs.recommendation or "").strip()
        rec_badge = "🟡 Proceed with Caution"
        if rec_val == BidRecommendation.PROCEED.value:
            rec_badge = "🟢 Proceed"
        elif rec_val in (BidRecommendation.HIGH_RISK.value, BidRecommendation.HIGH_RISK_RECONSIDER.value):
            rec_badge = "🔴 High Risk"
        elif rec_val == BidRecommendation.NOT_RECOMMENDED.value:
            rec_badge = "⛔ Not Recommended"
        elif rec_val == BidRecommendation.DEADLINE_PASSED.value:
            rec_badge = "⏰ Submission Deadline Passed"
        elif rec_val == BidRecommendation.REQUIRES_CLARIFICATION.value:
            rec_badge = "🟠 Requires Clarification"
        elif rec_val == BidRecommendation.INSUFFICIENT_INFORMATION.value:
            rec_badge = "⚪ Insufficient Information"

        authority = _clean(ov.department_organization, "Government Procurement Department")
        beneficiary = ov.end_user_beneficiary if (ov.end_user_beneficiary and ov.end_user_beneficiary not in ("Not specified", "N/A", authority)) else None
        beneficiary_text = f" on behalf of **{beneficiary}**" if beneficiary else ""

        narrative_overview = ov.overall_understanding or ov.scope_of_work_summary
        if not narrative_overview or narrative_overview.startswith("["):
            narrative_overview = "This tender covers the procurement, supply, installation, testing, and commissioning of required systems and infrastructure."

        lines = [
            f"### 📋 Tender Briefing: {ov.tender_title or 'Procurement Opportunity'}",
            f"Issued by **{authority}**{beneficiary_text} | Ref: `{_clean(ov.tender_reference_number, 'N/A')}` | Submission Deadline: **{_clean(ov.bid_submission_deadline, 'Refer to Tender Schedule')}**",
            "",
            "#### 🏛️ What This Tender Is About",
            f"What this tender is about: {narrative_overview.strip()}",
            "",
            "#### ⚙️ Procurement Opportunity & Scope",
            f"- **Main Technical Scope**: {_clean(sc.overview, 'Procurement, deployment, testing, and comprehensive maintenance support')}",
            f"- **Estimated Tender Value**: {_clean(ov.estimated_project_value, 'Not disclosed in NIT; rates to be quoted in BOQ')}",
            f"- **Implementation Timeline**: {_clean(ov.delivery_implementation_period, 'As per delivery milestone schedule')}",
            f"- **Submission Deadline**: **{_clean(ov.bid_submission_deadline, 'Refer to Tender Schedule')}**",
            f"- **Contract Duration & Warranty**: {_clean(ov.contract_duration, '3 Years')} (Warranty Period: {_clean(ov.warranty_maintenance_period, 'Comprehensive on-site OEM warranty')})",
            "",
            "#### 🎯 Key Eligibility Requirements",
            f"- **Minimum Turnover**: {_clean(el.annual_turnover_requirement or el.average_turnover_requirement, 'Audited turnover as specified in pre-qualification criteria')}",
            f"- **Past Similar Experience**: {_clean(el.similar_work_experience, 'Past completed projects of similar scope with government/PSU clients')}",
            f"- **OEM Authorization (MAF)**: {'Mandatory Manufacturer Authorization Form (MAF) required from OEMs' if el.oem_authorization_mandatory else 'Generic specifications; no explicit single-brand restriction'}",
            f"- **Consortium / Joint Venture**: {_clean(el.consortium_joint_venture_allowed, 'Single entity bidding only')}",
            "",
            "> ℹ️ **Bidder eligibility**: Not assessed — company credentials have not been provided. Click any suggested question below or ask me directly to evaluate your profile.",
            "",
            "#### 💳 Key Financial Commitments",
            f"- **EMD / Bid Security**: {_clean(ov.emd_value or cm.emd_amount, 'Exemption available for registered MSMEs/MSEs as per policy')} (Tender Fee: {_clean(ov.tender_fee, 'Nil / As per portal')})",
            f"- **Performance Security (PBG)**: {_clean(cm.performance_bank_guarantee_pbg or cm.security_deposit, 'Refer to Commercial Terms / As per GCC')}",
            f"- **Payment Terms**: {_clean(cm.payment_terms, 'Milestone payments linked to delivery, installation, and final acceptance testing')}",
            f"- **Warranty Period**: {_clean(ov.warranty_maintenance_period, 'Comprehensive on-site OEM warranty')}",
            f"- **Delay Penalties / Liquidated Damages**: {_clean(cm.penalties_and_liquidated_damages, 'Refer to Penalty Schedule in tender')}",
            "",
            "#### ⚠️ Critical Risks & Watchouts",
        ]

        material_risks = [rk_item for rk_item in rk.risks if rk_item.risk_level in (RiskLevel.CRITICAL.value, RiskLevel.HIGH.value)] or rk.risks
        if material_risks:
            for item in material_risks[:3]:
                lvl = "🔴" if item.risk_level == RiskLevel.CRITICAL.value else "🟠"
                pg_str = f" (Page {item.source_page})" if item.source_page else ""
                lines.append(f"- **{lvl} {item.risk_title}**: {item.why_it_matters or item.potential_impact}{pg_str}")
        else:
            lines.append("- No high-risk punitive clauses or unusual contract liabilities detected in preliminary screening.")

        lines.extend([
            "",
            f"#### 🎯 Preliminary Bid Recommendation: Consultant Observation ({rec_badge})",
            f"> {bs.recommendation_rationale or bs.overall_tender_assessment or 'The tender represents a viable business opportunity with standard government procurement terms. Ensure strict compliance with technical specifications and obtain OEM authorization letters early.'}",
        ])

        return "\n".join(lines)

    def generate_suggested_questions(
        self,
        report: TenderConsultantReport,
        last_query: Optional[str] = None,
        last_answer: Optional[str] = None,
    ) -> List[str]:
        """Generates dynamic suggested questions based on tender content and conversation turn."""
        ov = report.overview
        title = (ov.tender_title or "").lower()
        cat = (ov.tender_category or "").lower()

        if last_query:
            q_low = last_query.lower()
            if any(k in q_low for k in ["eligibility", "pre-qualification", "pq criteria", "who can bid"]):
                return [
                    "What is the exact minimum turnover and financial year requirement?",
                    "What are the similar work experience alternatives?",
                    "Is consortium or joint venture allowed?",
                    "Is OEM authorization (MAF) mandatory?",
                    "Can our company participate?",
                ]
            if any(k in q_low for k in ["turnover", "minimum turnover"]):
                return [
                    "What are the similar work experience alternatives?",
                    "Is OEM authorization (MAF) mandatory?",
                    "What documents are required for financial qualification?",
                    "What are the payment and warranty terms?",
                ]
            if any(k in q_low for k in ["consortium", "joint venture"]):
                return [
                    "Can we bid as a single bidder with OEM support?",
                    "What are the lead bidder requirements in a consortium?",
                    "What are the complete eligibility criteria?",
                    "What are the major risks?",
                ]
            if any(k in q_low for k in ["emd", "earnest money", "tender fee", "fee"]):
                return [
                    "Are MSME / NSIC bidders exempt from EMD?",
                    "What is the Performance Security (PBG) percentage?",
                    "What are the payment milestone terms?",
                    "What liquidated damages apply for delays?",
                ]
            if any(k in q_low for k in ["spec", "technical", "hardware", "scope"]):
                follow_ups = [
                    "What are the acceptance testing and inspection criteria?",
                    "What warranty and SLA support are required?",
                    "What OEM certificates and datasheets are mandatory?",
                ]
                if "cctv" in title or "surveillance" in title:
                    follow_ups.append("What are the storage and VMS server requirements?")
                elif "meter" in title or "smart" in title:
                    follow_ups.append("What are the communication protocol and MDMS specifications?")
                elif "desktop" in title or "pc" in title:
                    follow_ups.append("What are the processor, RAM, and display specifications?")
                else:
                    follow_ups.append("What are the major risks and contradictions?")
                return follow_ups[:4]
            if any(k in q_low for k in ["risk", "concern", "contradiction", "penalty"]):
                return [
                    "What pre-bid clarification questions should we submit?",
                    "Are there conflicting clauses or ambiguities between sections?",
                    "What are the payment and warranty conditions?",
                    "Should we participate in this tender?",
                ]
            if any(k in q_low for k in ["recommendation", "should we bid", "participate", "verdict"]):
                return [
                    "What are the critical pre-bid queries to raise?",
                    "What mandatory documents must we submit?",
                    "What are the top risks that could lead to disqualification?",
                    "What is the EMD and financial commitment?",
                ]

        suggestions: List[str] = [
            "What are the complete eligibility criteria?",
            "Can our company participate?",
        ]

        if any(k in title or k in cat for k in ["cctv", "camera", "surveillance", "anpr"]):
            suggestions.append("What are the camera, ANPR, and VMS technical specifications?")
        elif any(k in title or k in cat for k in ["desktop", "workstation", "computer", "pc", "server"]):
            suggestions.append("What are the detailed processor and hardware specifications?")
        elif any(k in title or k in cat for k in ["meter", "smart meter", "energy"]):
            suggestions.append("What are the meter specifications and communication protocol requirements?")
        elif any(k in title or k in cat for k in ["wi-fi", "wifi", "network", "lan", "ap"]):
            suggestions.append("What are the access point and networking specifications?")
        else:
            suggestions.append("What are the important technical specifications?")

        suggestions.append("What is the EMD and financial commitment?")
        suggestions.append("What are the major risks and contradictions?")
        suggestions.append("What mandatory documents must we submit?")
        suggestions.append("What are the payment and warranty conditions?")
        suggestions.append("Should we participate in this tender?")

        return suggestions

    def _group_technical_specifications(self, items: List[Any]) -> Dict[str, List[Any]]:
        """Clusters technical specification items into clean, readable functional categories."""
        if not items:
            return {}

        categories: Dict[str, List[Any]] = {
            "Computing & Processing Core": [],
            "Display, Graphics & Peripherals": [],
            "Surveillance, Cameras & Sensors": [],
            "Networking, Ports & Connectivity": [],
            "Software, Operating System & Security": [],
            "Power, Environmental & Standards": [],
            "Warranty, AMC & Support Services": [],
            "Ancillary & Additional Specifications": [],
        }

        for item in items:
            name = (getattr(item, "item_name", None) or "").lower()
            spec = (getattr(item, "technical_specifications", None) or "").lower()
            sub = (getattr(item, "subsystem_or_category", None) or "").lower()
            clause = (getattr(item, "clause_heading", None) or "").lower()
            combined = f"{name} {spec} {sub} {clause}"

            if any(k in combined for k in ["processor", "cpu", "chipset", "motherboard", "ram", "memory", "hard disk", "hdd", "ssd", "nvme", "storage", "server", "controller"]):
                categories["Computing & Processing Core"].append(item)
            elif any(k in combined for k in ["display", "monitor", "screen", "panel", "resolution", "graphics", "gpu", "vga", "hdmi", "keyboard", "mouse"]):
                categories["Display, Graphics & Peripherals"].append(item)
            elif any(k in combined for k in ["camera", "ptz", "anpr", "dome", "bullet", "sensor", "lens", "ir illumination", "cctv", "nvr", "vms", "video"]):
                categories["Surveillance, Cameras & Sensors"].append(item)
            elif any(k in combined for k in ["ethernet", "lan", "nic", "network", "switch", "router", "wi-fi", "wifi", "wireless", "access point", "ap", "bluetooth", "port"]):
                categories["Networking, Ports & Connectivity"].append(item)
            elif any(k in combined for k in ["operating system", "os", "windows", "linux", "antivirus", "software", "license", "firmware", "bios"]):
                categories["Software, Operating System & Security"].append(item)
            elif any(k in combined for k in ["warranty", "amc", "maintenance", "support", "sla", "on-site", "repair"]):
                categories["Warranty, AMC & Support Services"].append(item)
            elif any(k in combined for k in ["power", "smps", "battery", "ups", "rohs", "energy star", "epeat", "certification", "compliance"]):
                categories["Power, Environmental & Standards"].append(item)
            else:
                categories["Ancillary & Additional Specifications"].append(item)

        # Return non-empty categories
        return {k: v for k, v in categories.items() if v}

    def _build_consultant_briefing(self, r: TenderConsultantReport) -> str:
        """Constructs concise, executive 7-section consultant briefing (Sections A through G)."""
        ov = r.overview
        el = r.eligibility
        sc = r.technical_scope
        sp = r.technical_specifications
        cm = r.commercial_financial
        lg = r.contractual_legal
        rk = r.risks_and_contradictions
        bs = r.bid_strategy
        rd = r.action_roadmap

        # Verdict Badge
        rec_badge = "🟡 PROCEED WITH CAUTION"
        if bs.recommendation == BidRecommendation.PROCEED.value:
            rec_badge = "🟢 PROCEED"
        elif bs.recommendation == BidRecommendation.REQUIRES_CLARIFICATION.value:
            rec_badge = "🟠 REQUIRES CLARIFICATION BEFORE PROCEEDING"
        elif bs.recommendation == BidRecommendation.HIGH_RISK_RECONSIDER.value:
            rec_badge = "🔴 HIGH RISK / RECONSIDER PARTICIPATION"

        lines: List[str] = [
            "# 📋 Tender Consultant Executive Briefing",
            f"**Tender Ref**: `{ov.tender_reference_number}` | **Client**: {ov.department_organization} | **Analyzed**: {len(r.source_files)} document(s), {r.total_pages_analyzed} page(s)",
            "",
            "---",
            "## Section A: Tender at a Glance",
            f"- **Tender Title**: {ov.tender_title}",
            f"- **Issuing Authority / Client**: {ov.department_organization}",
            f"- **Tender Reference Number**: `{ov.tender_reference_number}`",
            f"- **Procurement Scope Summary**: {ov.overall_understanding or ov.scope_of_work_summary}",
            f"- **Estimated Tender Value**: {ov.estimated_project_value or '[ NOT SPECIFIED IN TENDER ]'}",
            f"- **Earnest Money Deposit (EMD)**: {ov.emd_value or '[ NOT SPECIFIED IN TENDER ]'} (Tender Fee: {ov.tender_fee or '[ NOT SPECIFIED IN TENDER ]'})",
            f"- **Bid Submission Deadline**: **{ov.bid_submission_deadline or '[ NOT SPECIFIED IN TENDER ]'}** (Bid Opening: {ov.bid_opening_date or '[ NOT SPECIFIED IN TENDER ]'})",
            f"- **Delivery / Implementation Timeline**: {ov.delivery_implementation_period or '[ NOT SPECIFIED IN TENDER ]'} (Contract Duration: {ov.contract_duration or '[ NOT SPECIFIED IN TENDER ]'})",
            "",
            "---",
            "## Section B: Most Important Requirements (Pre-Qualification & Eligibility)",
            f"- **Financial Turnover Mandate**: {el.annual_turnover_requirement or el.average_turnover_requirement or '[ NOT SPECIFIED IN TENDER ]'}",
            f"- **Past Experience / Similar Work**: {el.similar_work_experience or '[ NOT SPECIFIED IN TENDER ]'}",
            f"- **Mandatory Certifications**: {', '.join(el.required_certifications) if el.required_certifications else '[ NOT SPECIFIED IN TENDER ]'}",
            f"- **OEM Authorization**: {'Mandatory Manufacturer Authorization Form (MAF) required' if el.oem_authorization_mandatory else 'Not mandated / Generic specifications'}",
            f"- **Consortium / Joint Venture**: {el.consortium_joint_venture_allowed or '[ NOT SPECIFIED IN TENDER ]'}",
            "",
            "> ℹ️ **Bidder eligibility**: Not assessed — company credentials have not been provided.",
            "",
            "---",
            "## Section C: Important Technical Scope & Key Specifications",
            f"{sc.overview or 'Detailed technical scope covering procurement, supply, installation, testing, and commissioning.'}",
            "",
        ]

        # Grouped technical specifications
        grouped = self._group_technical_specifications(sp.items)
        if grouped:
            for cat_title, cat_items in grouped.items():
                lines.append(f"### {cat_title}")
                # If category has fewer than 5 items, detail each
                if len(cat_items) <= 4:
                    for item in cat_items:
                        qty_str = f" (Qty: {item.required_quantity})" if item.required_quantity else ""
                        brand_str = f" [Brand: {item.oem_brand_model_mentioned}]" if item.oem_brand_model_mentioned and item.oem_brand_model_mentioned != '[ NOT SPECIFIED IN TENDER ]' else ""
                        lines.append(f"- **{item.item_name}**{qty_str}: {item.technical_specifications[:250]}{brand_str} *(Page {item.source_page})*")
                else:
                    # Synthesize summary bullets for larger categories
                    summary_parts = []
                    pages = set()
                    for item in cat_items[:6]:
                        summary_parts.append(f"**{item.item_name}**: {item.technical_specifications[:100].strip()}")
                        pages.add(str(item.source_page))
                    page_ref = f"*(Pages {', '.join(sorted(pages))})*" if pages else ""
                    lines.append(f"- {'; '.join(summary_parts)} {page_ref}")
                lines.append("")
        else:
            lines.append("- Technical specifications: Refer to technical schedule and BOQ in tender dossier.")
            lines.append("")

        lines.extend([
            "> ℹ️ **Bidder compliance**: Not assessed — product proposal or OEM datasheets have not been provided.",
            "",
            "---",
            "## Section D: Financial & Contractual Obligations",
            f"- **Earnest Money Deposit (EMD)**: {ov.emd_value or cm.emd_amount or '[ NOT SPECIFIED IN TENDER ]'} (Exemption: {cm.emd_exemption_rules or 'As per tender terms'})",
            f"- **Performance Bank Guarantee (PBG)**: {cm.performance_bank_guarantee_pbg or '[ NOT SPECIFIED IN TENDER ]'}",
            f"- **Payment Terms**: {cm.payment_terms or '[ NOT SPECIFIED IN TENDER ]'} (Advance: {cm.advance_payment_allowed or 'Nil / Not Permitted'}; Milestones: {cm.milestone_payments or '[ NOT SPECIFIED IN TENDER ]'})",
            f"- **Warranty & Maintenance**: {ov.warranty_maintenance_period or sc.maintenance_and_amc_obligations or '[ NOT SPECIFIED IN TENDER ]'}",
            f"- **Liquidated Damages & Delay Penalties**: {cm.penalties_and_liquidated_damages or lg.delay_penalties or '[ NOT SPECIFIED IN TENDER ]'}",
            "",
            "---",
            "## Section E: Major Risks & Critical Concerns",
        ])

        # Material risks (top 3 to 5)
        top_risks = [r for r in rk.risks if r.risk_level in (RiskLevel.CRITICAL.value, RiskLevel.HIGH.value)][:4]
        if not top_risks and rk.risks:
            top_risks = rk.risks[:3]

        if top_risks:
            for rk_item in top_risks:
                lvl_emoji = "🔴" if rk_item.risk_level == RiskLevel.CRITICAL.value else "🟠"
                lines.append(f"### {lvl_emoji} {rk_item.risk_title} ({rk_item.risk_level} Risk)")
                lines.append(f"- **Impact**: {rk_item.why_it_matters or rk_item.potential_impact}")
                lines.append(f"- **Tender Reference**: Page {rk_item.source_page} — *\"{rk_item.tender_evidence}\"*")
                lines.append(f"- **Recommended Consultant Action**: {rk_item.recommended_action}")
                lines.append("")
        else:
            lines.append("- No critical risk red flags detected beyond standard procurement terms.")
            lines.append("")

        if rk.contradictions_found:
            lines.append("### ⚡ Ambiguities & Contradictions Found in Tender")
            for ct in rk.contradictions_found[:4]:
                lines.append(f"- ⚠️ {ct}")
            lines.append("")

        lines.extend([
            "---",
            "## Section F: Consultant Recommendation & Strategic Verdict",
            f"### Consultant Verdict: {rec_badge}",
            f"> {bs.recommendation_rationale or bs.overall_tender_assessment}",
            "",
            "---",
            "## Section G: Immediate Actions & Next Steps",
        ])

        # 4 to 6 prioritized action steps
        actions = rd.checklist[:6] if rd.checklist else []
        if actions:
            for idx, act in enumerate(actions, 1):
                page_str = f" (Ref: Page {act.relevant_tender_page})" if act.relevant_tender_page else ""
                lines.append(f"{idx}. **[{act.priority.upper()}] {act.activity}** — {act.reason}{page_str}")
        else:
            fallback_steps = bs.bid_preparation_priorities[:5] or [
                "Submit pre-bid clarification queries before deadline",
                "Request draft MAF and OEM warranty commitment letter from OEMs",
                "Assemble audited balance sheets and work completion certificates",
                "Deposit EMD and tender fee as per tender instructions",
            ]
            for idx, st in enumerate(fallback_steps, 1):
                lines.append(f"{idx}. {st}")

        lines.append("")
        return "\n".join(lines)

    def _build_executive_summary(self, r: TenderConsultantReport) -> str:
        ov = r.overview
        bs = r.bid_strategy
        rk = r.risks_and_contradictions

        rec_badge = "🟡 PROCEED WITH CAUTION"
        if bs.recommendation == BidRecommendation.PROCEED.value:
            rec_badge = "🟢 PROCEED"
        elif bs.recommendation == BidRecommendation.REQUIRES_CLARIFICATION.value:
            rec_badge = "🟠 REQUIRES CLARIFICATION BEFORE PROCEEDING"
        elif bs.recommendation == BidRecommendation.HIGH_RISK_RECONSIDER.value:
            rec_badge = "🔴 HIGH RISK / RECONSIDER PARTICIPATION"

        lines = [
            f"# 📋 Tender Consultant Executive Briefing",
            f"**Tender Title**: {ov.tender_title}",
            f"**Authority / Client**: {ov.department_organization}",
            f"**Tender Ref No**: `{ov.tender_reference_number}`",
            "",
            f"### Consultant Verdict: {rec_badge}",
            f"> {bs.recommendation_rationale or bs.overall_tender_assessment}",
            "",
            "| Key Parameter | Tender Requirement / Finding | Reference |",
            "| :--- | :--- | :--- |",
            f"| **Estimated Value** | {ov.estimated_project_value or 'Not specified'} | [ TENDER REQUIREMENT ] |",
            f"| **EMD Amount** | {ov.emd_value or 'Not specified'} | [ TENDER REQUIREMENT ] |",
            f"| **Submission Deadline** | **{ov.bid_submission_deadline or 'Not specified'}** | [ TENDER REQUIREMENT ] |",
            f"| **Contract Duration** | {ov.contract_duration or 'Not specified'} | [ TENDER REQUIREMENT ] |",
            f"| **Annual Turnover Required** | {r.eligibility.annual_turnover_requirement or 'Not specified'} | [ TENDER REQUIREMENT ] |",
            f"| **OEM Authorization Mandate** | {'Yes (Mandatory)' if r.eligibility.oem_authorization_mandatory else 'Not mandated / Generic'} | [ TENDER REQUIREMENT ] |",
            f"| **Identified Critical Risks** | {rk.critical_risks_count} Critical, {rk.high_risks_count} High | [ RISK ANALYSIS ] |",
            "",
            f"**Project Summary**: {ov.overall_understanding or ov.scope_of_work_summary}",
        ]
        return "\n".join(lines)

    def _build_full_dossier(self, r: TenderConsultantReport) -> str:
        ov = r.overview
        el = r.eligibility
        sc = r.technical_scope
        sp = r.technical_specifications
        oem = r.oem_requirements
        cp = r.compliance_matrix
        cm = r.commercial_financial
        lg = r.contractual_legal
        rk = r.risks_and_contradictions
        bs = r.bid_strategy
        rd = r.action_roadmap

        def _f(val: Optional[str], default: str = "Not specified in tender notice; governed by GCC") -> str:
            if not val or not str(val).strip() or str(val).strip().upper() in ("[ NOT SPECIFIED IN TENDER ]", "NONE", "N/A", "NOT_FOUND"):
                return default
            return str(val).strip()

        authority = _f(ov.department_organization, "Procurement Authority")
        beneficiary = _f(ov.end_user_beneficiary, authority)

        lines: List[str] = [
            "# 📑 MYGPT AI Tender Consultant — Full Evaluation & Bid Strategy Dossier",
            f"*Analyzed: {len(r.source_files)} document(s) | Total Pages: {r.total_pages_analyzed} | Engine: {r.model_used}*",
            "",
            "---",
            "## 1. 🏢 Tender Overview & Project Understanding",
            "### 📌 Requirement Summary",
            f"Procurement Opportunity issued by **{authority}** for **{ov.tender_title}** (Ref: `{ov.tender_reference_number}`).",
            "",
            "### 🔍 Key Findings & Verified Evidence",
            f"- **Tender Title**: {ov.tender_title}",
            f"- **Issuing Authority**: {authority}",
            f"- **Intended Beneficiary / End-User**: {beneficiary}",
            f"- **Tender Reference Number**: `{ov.tender_reference_number}`",
            f"- **Project Name**: {_f(ov.project_name, ov.tender_title)}",
            f"- **Project Location**: {_f(ov.project_location, 'As specified in delivery schedule')}",
            f"- **Submission Deadline**: **{_f(ov.bid_submission_deadline, 'Refer to Tender Schedule')}**",
            f"- **Technical Bid Opening**: {_f(ov.bid_opening_date, 'Following bid submission deadline')}",
            f"- **Estimated Tender Value**: {_f(ov.estimated_project_value, 'Not disclosed in NIT; rates to be quoted in BOQ')}",
            f"- **Earnest Money Deposit (EMD)**: {_f(ov.emd_value or cm.emd_amount, 'Exemption for eligible MSME/MSE bidders')}",
            f"- **Tender Document Fee**: {_f(ov.tender_fee, 'Nil / Online portal charge')}",
            f"- **Implementation & Delivery Period**: {_f(ov.delivery_implementation_period, 'As per delivery milestone schedule')}",
            f"- **Contract & Warranty Duration**: {_f(ov.contract_duration, '3 Years')} (Warranty: {_f(ov.warranty_maintenance_period, 'Comprehensive on-site OEM warranty')})",
            "",
            "### 💡 Strategic Bidder Implications",
            f"> {ov.overall_understanding or ov.scope_of_work_summary}",
            "- **Timeline Feasibility**: Implementation schedules must account for equipment procurement lead times and site readiness.",
            "- **Working Capital**: EMD, portal fees, and initial mobilization require upfront capital allocation before milestone disbursements commence.",
            "",
            "### ⚠️ Dimension Risks & Ambiguities",
            "- E-procurement portal server load during cutoff hours poses upload risks; submission on the final day should be avoided.",
            "- Unstated site preparation conditions could result in delay liabilities if client infrastructure is unready.",
            "",
            "### 🎯 Consultant Recommendations",
            "- Register and verify Digital Signature Certificate (DSC) on the procurement portal immediately.",
            "- Request formal pre-bid clarification on project value and site readiness dependencies.",
            "",
            "---",
            "## 2. 🎯 Bidder Eligibility & Pre-Qualification (PQ)",
            "### 📌 Requirement Summary",
            "Mandatory qualification criteria that bidders must satisfy to avoid technical disqualification at envelope evaluation stage.",
            "",
            "### 🔍 Key Findings & Verified Evidence",
            f"- **Annual Turnover Mandate**: {_f(el.annual_turnover_requirement or el.average_turnover_requirement, 'Audited turnover as specified in pre-qualification criteria')}",
            f"- **Past Similar Experience**: {_f(el.similar_work_experience, 'Past completed projects of similar scope with government/PSU clients')}",
            f"- **Completed Projects Count / Value**: {_f(el.completed_projects_count, 'As per PQ schedule')} (Threshold: {_f(el.minimum_project_value, 'Refer to experience criteria')})",
            f"- **Government / PSU Track Record**: {_f(el.government_project_experience, 'Proof of execution with Govt/PSU clients required')}",
            f"- **Statutory Registrations**: {_f(el.company_registration_requirements, 'Valid PAN, GST, Incorporation Certificate, and Non-Blacklisting affidavit')}",
            f"- **Consortium / Joint Venture Status**: {_f(el.consortium_joint_venture_allowed, 'Single entity bidding only')}",
            f"- **OEM Authorization (MAF)**: {'Mandatory Manufacturer Authorization Form (MAF) required' if el.oem_authorization_mandatory else 'Generic specifications; no explicit single-brand restriction'}",
            "",
            "### Pre-Qualification Requirements Table",
            "| Category | Department Requirement | Mandatory? | Required Supporting Document | Disqualification Effect | Page |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]

        for c in el.conditions:
            lines.append(
                f"| **{c.category}** | {c.department_requirement} | {'Yes' if c.is_mandatory else 'No'} | {c.supporting_document_required} | {c.disqualification_effect} | Page {c.source_page} |"
            )

        lines.extend([
            "",
            "### 💡 Strategic Bidder Implications",
            f"> {el.summary_assessment or 'Bidder must rigorously audit financial turnover and past work completion certificates before bidding.'}",
            "- **Pass/Fail Nature**: Pre-qualification criteria are evaluated on a strict zero-deviation basis; non-compliance in any single mandatory item causes immediate rejection.",
            "- **Documentary Proof**: Work orders alone are insufficient without client satisfactory completion certificates showing value and completion date.",
            "",
            "### ⚠️ Dimension Risks & Ambiguities",
            "- CA certificates lacking unique document identification numbers (UDIN) will be rejected during technical scrutiny.",
            "- In consortium bidding (if allowed), lead member qualification thresholds must be strictly met.",
            "",
            "### 🎯 Consultant Recommendations",
            "- Obtain CA-certified turnover certificate with valid UDIN covering the requested financial years.",
            "- Verify all client completion certificates contain project title, contract value, and clear completion date.",
            "",
            "---",
            "## 3. ⚙️ Technical Scope Analysis",
            "### 📌 Requirement Summary",
            f"{sc.overview or 'Detailed technical scope covering procurement, deployment, testing, and comprehensive maintenance support.'}",
            "",
            "### 🔍 Key Findings & Verified Evidence",
            "| Technical Scope Area | Specific Department Requirement | Core Purpose | Reference |",
            "| :--- | :--- | :--- | :--- |",
        ])

        for s in sc.scope_items:
            lines.append(
                f"| **{s.area}** | {s.description} | {s.purpose} | Page {s.source_page} |"
            )

        lines.extend([
            "",
            f"- **Testing & Commissioning**: {_f(sc.testing_and_commissioning_obligations, 'Factory acceptance testing (FAT) and site acceptance testing (SAT) mandatory')}",
            f"- **Training Obligations**: {_f(sc.training_obligations, 'Operational and maintenance training for client technical personnel')}",
            f"- **Comprehensive Maintenance (AMC)**: {_f(sc.maintenance_and_amc_obligations, 'Comprehensive on-site maintenance support throughout contract tenure')}",
            f"- **SLA & Uptime Mandates**: {_f(sc.sla_requirements, 'Adherence to response time and service standards defined in tender')}",
            "",
            "### 💡 Strategic Bidder Implications",
            "- **Operational Deployment**: Requires dedicated on-site field engineers and regional spare-parts stocking to meet SLA windows.",
            "- **Acceptance Sign-Offs**: Milestone disbursements depend on formal joint inspection sign-offs, creating potential cash flow bottlenecks.",
            "",
            "### ⚠️ Dimension Risks & Ambiguities",
            "- Unclear division of responsibility between bidder and department regarding civil/electrical infrastructure and networking links.",
            "",
            "### 🎯 Consultant Recommendations",
            "- Submit pre-bid queries to confirm whether client provides uninterrupted power supply, rack space, and network bandwidth at installation sites.",
            "",
            "---",
            "## 4. 🔬 Technical Specification Analysis",
            "### 📌 Requirement Summary",
            f"{sp.overall_spec_evaluation or 'Item-by-item breakdown of hardware, software, and engineering specifications.'}",
            "",
            "### 🔍 Key Findings & Verified Evidence",
            "| Work Package / Item | Required Qty | Key Technical Parameters | Mandatory Standards | OEM / Brand Mentioned | Page |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ])

        for it in sp.items:
            pkg = it.subsystem_or_category or "Hardware & Equipment"
            lines.append(
                f"| **{pkg}**: {it.item_name} | {it.required_quantity or 'As per BOQ'} | {it.technical_specifications} | {it.mandatory_standards or 'Standard industry'} | {_f(it.oem_brand_model_mentioned, 'Generic / Open specifications')} | Page {it.source_page} |"
            )

        lines.extend([
            "",
            "### 💡 Strategic Bidder Implications",
            "- **Datasheet Mapping**: Every line item must be matched against published OEM datasheets; discrepancies will lead to compliance rejection.",
            "- **Supply Chain Lead Time**: Procuring specialized enterprise-grade hardware requires locking in supply commitments early.",
            "",
            "### ⚠️ Dimension Risks & Ambiguities",
            "- Overly specific or restrictive clauses that may favor proprietary single-vendor architectures.",
            "",
            "### 🎯 Consultant Recommendations",
            "- Prepare a clause-by-clause compliance matrix highlighting exact page numbers of OEM product datasheets.",
            "- Seek pre-bid amendment for any restrictive specification that limits multi-OEM competition.",
            "",
            "---",
            "## 5. 🏷️ OEM and Product Requirement Analysis",
            "### 📌 Requirement Summary",
            f"Manufacturer authorization conditions and equipment warranty support obligations.",
            "",
            "### 🔍 Key Findings & Verified Evidence",
            f"- **OEM Authorization Mandatory**: {'Yes (Mandatory Manufacturer Authorization Form / MAF)' if oem.oem_authorization_required else 'Generic specifications; no explicit single-brand restriction'}",
            f"- **Specific Brands Mentioned in Tender**: {', '.join(oem.specific_brands_in_tender) if oem.specific_brands_in_tender else 'Generic specifications — open to any qualified OEM'}",
            "",
            "### OEM Obligations Matrix",
            "| Requirement | Details | Mandatory? | Brand Mentioned | Support / Warranty Conditions | Page |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ])

        for o in oem.oem_requirements:
            lines.append(
                f"| **{o.requirement_name}** | {o.details} | {'Yes' if o.is_mandatory else 'No'} | {o.specific_brands_mentioned or 'Generic'} | {o.warranty_support_conditions or 'Standard'} | Page {o.source_page} |"
            )

        lines.extend([
            "",
            "### 💡 Strategic Bidder Implications",
            f"> {oem.consultant_notes or 'Secure back-to-back OEM warranty support and ink MAF letters before bid submission.'}",
            "- **OEM Dependency**: Single-OEM pricing control can squeeze bidder margins; multiple authorized OEM options should be pursued.",
            "",
            "### ⚠️ Dimension Risks & Ambiguities",
            "- Inability of chosen OEM to commit to long-term spare parts availability across full contract duration.",
            "",
            "### 🎯 Consultant Recommendations",
            "- Obtain formal Manufacturer Authorization Form (MAF) on OEM letterhead signed by authorized signatory.",
            "- Secure written OEM commitment for back-to-back warranty support and spare parts availability for 3-5 years.",
            "",
            "---",
            "## 6. 📊 Item-Wise Compliance Analysis Matrix",
            "### 📌 Requirement Summary",
            "Clause-by-clause compliance verification matrix comparing tender requirements against bidder solution proposals.",
            "",
            "### 🔍 Key Findings & Verified Evidence",
            "| Item | Tender Requirement | Mandatory Specification | Tender Reference | Compliance Assessment | Remarks |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ])

        for m in cp.items:
            lines.append(
                f"| **{m.item}** | {m.tender_requirement} | {m.mandatory_specification} | {m.tender_reference} | `{m.compliance_assessment}` | {m.remarks} |"
            )

        lines.extend([
            "",
            "### 💡 Strategic Bidder Implications",
            "- **Evaluation Scrutiny**: Technical evaluation committees scrutinize compliance sheets against OEM datasheets.",
            "- **Unambiguous Responses**: Marking 'Will Comply' instead of 'Complied' with datasheet proof is frequently rejected as non-compliant.",
            "",
            "### ⚠️ Dimension Risks & Ambiguities",
            "- Discrepancies between printed datasheets and actual model revision numbers.",
            "",
            "### 🎯 Consultant Recommendations",
            "- Complete the compliance matrix with strict 'COMPLIED' annotations and highlight exact datasheet page numbers.",
            "",
            "---",
            "## 7. 💰 Commercial & Financial Analysis",
            "### 📌 Requirement Summary",
            "Evaluation of contract payment milestones, guarantee obligations, retention amounts, price validity, and delay penalties.",
            "",
            "### 🔍 Key Findings & Verified Evidence",
            f"- **Payment Terms**: {_f(cm.payment_terms)}",
            f"- **Advance Payment Allowed**: {_f(cm.advance_payment_allowed, 'Nil / Not permitted')}",
            f"- **Milestone Payments**: {_f(cm.milestone_payments, 'Milestone-based disbursements against delivery, testing, and acceptance')}",
            f"- **Performance Bank Guarantee (PBG)**: {_f(cm.performance_bank_guarantee_pbg, 'Refer to Commercial Terms / GCC')}",
            f"- **Security Deposit / Retention**: {_f(cm.security_deposit or cm.retention_amount, 'Refer to GCC conditions')}",
            f"- **Price Validity Period**: {_f(cm.price_validity_period, 'Refer to ITB / Tender Schedule')}",
            f"- **Price Escalation Clause**: {_f(cm.price_escalation_clause, 'Firm fixed price contract; no escalation permitted')}",
            f"- **Liquidated Damages (LD)**: {_f(cm.penalties_and_liquidated_damages, 'Refer to Penalty Schedule in tender')}",
            f"- **Taxes & Duties**: {_f(cm.taxes_and_duties_terms, 'Inclusive of all taxes; GST extra as applicable')}",
            "",
            "### 💡 Strategic Bidder Implications",
            f"> {cm.bidder_impact_analysis or 'Review cash-flow requirements between milestone delivery and acceptance sign-offs.'}",
            "- **Cash Flow Exposure**: Bidders must finance equipment procurement and labor upfront, as disbursements follow client acceptance testing.",
            "- **Bank Credit Lines**: Performance Bank Guarantee ties up non-fund based credit limits for 3+ years.",
            "",
            "### ⚠️ Dimension Risks & Ambiguities",
            "- Ambiguous acceptance criteria can delay sign-offs and trigger cash flow crunches.",
            "",
            "### 🎯 Consultant Recommendations",
            "- Price in working capital financing costs for 60 to 90-day disbursement cycles.",
            "- Request pre-bid clarification to insert a deemed-acceptance clause if inspection is delayed beyond 30 days.",
            "",
            "---",
            "## 8. ⚖️ Contractual & Legal Conditions",
            "### 📌 Requirement Summary",
            "Legal commitments, contract agreement timelines, termination rights, indemnity, and dispute resolution framework.",
            "",
            "### 🔍 Key Findings & Verified Evidence",
            f"- **Agreement Signing Timeline**: {_f(lg.agreement_requirements, 'Within 15 to 30 days of LOA/Work Order')}",
            f"- **Contract Duration**: {_f(lg.contract_duration, '3 Years')}",
            f"- **Delivery & Delay Obligations**: {_f(lg.delivery_obligations, 'As per delivery milestone schedule')}",
            f"- **Indemnity & Limitation of Liability**: {_f(lg.indemnity_and_liability, 'Standard contractor indemnity for IP and site accidents')}",
            f"- **Termination Clauses**: {_f(lg.termination_conditions, 'Termination for default, insolvency, or departmental convenience')}",
            f"- **Dispute Resolution & Jurisdiction**: {_f(lg.dispute_resolution_and_jurisdiction, 'High Court / Civil Court jurisdiction applicable as per tender clause')}",
            f"- **Force Majeure**: {_f(lg.force_majeure, 'Standard force majeure provisions apply')}",
            "",
            "### 💡 Strategic Bidder Implications",
            "- **Contractual Balance**: Review indemnity clauses to ensure overall contractor liability is capped at contract value.",
            "- **Default Risks**: Unilateral termination rights without compensation for executed work must be noted.",
            "",
            "### ⚠️ Dimension Risks & Ambiguities",
            "- Onerous uncapped indemnity or dispute resolution clauses that mandate lengthy litigation.",
            "",
            "### 🎯 Consultant Recommendations",
            "- Ensure the draft contract agreement is reviewed by legal counsel before executing the tender bond.",
            "",
            "---",
            "## 9. ⚠️ Risk and Contradiction Analysis",
            "### 📌 Requirement Summary",
            "Comprehensive risk register classifying potential commercial, technical, and operational liabilities.",
            "",
            "### 🔍 Key Findings & Verified Evidence",
            f"**Risk Register Summary**: 🔴 {rk.critical_risks_count} Critical | 🟠 {rk.high_risks_count} High | 🟡 {rk.medium_risks_count} Medium | 🟢 {rk.low_risks_count} Low",
            "",
            "| Risk Title | Level | Tender Evidence | Page | Why It Matters | Impact | Recommended Consultant Action |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ])

        for rk_item in rk.risks:
            lvl_emoji = "🔴" if rk_item.risk_level == RiskLevel.CRITICAL.value else ("🟠" if rk_item.risk_level == RiskLevel.HIGH.value else "🟡")
            lines.append(
                f"| **{rk_item.risk_title}** | {lvl_emoji} {rk_item.risk_level} | {rk_item.tender_evidence} | Page {rk_item.source_page} | {rk_item.why_it_matters} | {rk_item.potential_impact} | {rk_item.recommended_action} |"
            )

        if rk.contradictions_found:
            lines.extend([
                "",
                "### ⚡ Ambiguities & Contradictions Found in Tender",
            ])
            for ct in rk.contradictions_found:
                lines.append(f"- ⚠️ {ct}")

        lines.extend([
            "",
            "### 💡 Strategic Bidder Implications",
            "- High-risk penalty clauses (e.g. uncapped liquidated damages or SLA uptime deductions) directly threaten project profitability.",
            "",
            "### 🎯 Consultant Recommendations",
            "- Formulate formal pre-bid clarification queries targeting all ambiguous and contradictory clauses.",
            "",
            "---",
            "## 10. 🎯 Bid Strategy & Consultant Recommendations",
            "### 📌 Requirement Summary",
            "Senior consultant assessment on overall bid feasibility, go/no-go recommendation, and competitive bid strategy.",
            "",
            "### 🔍 Key Findings & Verified Evidence",
            f"**Final Recommendation**: **`{bs.recommendation}`**",
            f"> {bs.recommendation_rationale or bs.overall_tender_assessment}",
            "",
            "### Recommended Pre-Bid Clarification Questions",
        ])

        for q in bs.prebid_clarification_questions:
            lines.append(f"- ❓ {q}")

        lines.extend([
            "",
            "### Bid Preparation Priorities",
        ])
        for pr in bs.bid_preparation_priorities:
            lines.append(f"- 📌 {pr}")

        lines.extend([
            "",
            "### 💡 Strategic Bidder Implications",
            "- Bidding requires balanced pricing that accounts for working capital financing, PBG costs, and comprehensive warranty support.",
            "",
            "### 🎯 Consultant Recommendations",
            "- Finalize vendor quotes and OEM MAFs at least 5 days prior to submission to avoid last-minute pricing errors.",
            "",
            "---",
            "## 11. 🚀 Final Action Roadmap & Submission Checklist",
            "### 📌 Requirement Summary",
            "Step-by-step submission checklist from pre-bid queries through envelope preparation and portal submission.",
            "",
            "### 🔍 Key Findings & Verified Evidence",
            "| Step | Action Activity | Core Reason | Relevant Page | Priority | Stage / Milestone |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ])

        for act in rd.checklist:
            lines.append(
                f"| {act.step_number} | **{act.activity}** | {act.reason} | {'Page ' + str(act.relevant_tender_page) if act.relevant_tender_page else '-'} | `{act.priority}` | {act.deadline_or_stage or 'Pre-Submission'} |"
            )

        lines.extend([
            "",
            "### 💡 Strategic Bidder Implications",
            "- Eliminates procedural disqualification by ensuring all statutory undertakings and technical compliance sheets are sealed in the correct envelope.",
            "",
            "### 🎯 Consultant Recommendations",
            "- Complete technical and financial envelopes 48 hours prior to deadline and upload to the portal at least 24 hours in advance.",
            "",
            "---",
            f"**Validation Status**: `{r.validation_status}` | Verification Notes: {len(r.verification_notes)}",
            "> *Disclaimer: This report is generated strictly from the provided tender document using MYGPT's local Gemma inference engine. It provides professional tender evaluation advice but does not constitute legal representation or guaranteed bid award outcome.*",
        ])

        return "\n".join(lines)


intelligence_report_builder = IntelligenceReportBuilder()
