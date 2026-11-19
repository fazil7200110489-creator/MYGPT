"""Universal Procurement and Document Classifier for MYGPT AI Tender Consultant.

Categorizes any procurement document into primary/secondary domains, contract types,
and document roles without hardcoded tender assumptions.
"""

import re
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from loguru import logger


class ProcurementCategory(str, Enum):
    IT_HARDWARE = "IT Hardware & Computing Equipment"
    SOFTWARE_DEV = "Software Development & Application Services"
    NETWORKING_TELECOM = "Networking & Telecommunications Infrastructure"
    CCTV_SURVEILLANCE = "CCTV, Surveillance & Security Systems"
    CYBERSECURITY = "Cybersecurity & Information Security"
    CLOUD_DATACENTER = "Cloud, Hosting & Data Centre Services"
    ELECTRICAL_ELECTRONICS = "Electrical & Power Infrastructure"
    CIVIL_CONSTRUCTION = "Civil Construction, Works & Infrastructure"
    MECHANICAL_EQUIPMENT = "Mechanical & Industrial Equipment"
    MEDICAL_HEALTHCARE = "Medical & Healthcare Equipment"
    LABORATORY_SCIENTIFIC = "Laboratory & Scientific Instruments"
    FURNITURE_OFFICE = "Furniture & Office Fit-out"
    VEHICLES_TRANSPORT = "Vehicles, Fleet & Transportation"
    MANPOWER_STAFFING = "Manpower, Staffing & HR Services"
    HOUSEKEEPING_FACILITY = "Housekeeping, Sanitation & Facility Management"
    SECURITY_SERVICES = "Physical Security & Guarding Services"
    CONSULTANCY_SERVICES = "Advisory, Consulting & Professional Services"
    AMC_MAINTENANCE = "Annual Maintenance & Support Services (AMC/CAMC)"
    TURNKEY_EPC = "Turnkey & Engineering, Procurement, Construction (EPC)"
    GENERAL_GOODS = "General Procurement of Goods"
    GENERAL_SERVICES = "General Procurement of Services"
    GENERAL_WORKS = "General Public Works"


class ContractType(str, Enum):
    SUPPLY_GOODS = "Supply of Goods"
    SERVICES = "Services & Service Level Agreement"
    WORKS = "Execution of Works"
    CONSULTANCY = "Consultancy & Professional Services"
    EPC_TURNKEY = "EPC & Turnkey Contract"
    HYBRID_SUPPLY_INSTALL = "Supply, Installation & Maintenance (Hybrid)"


class DocumentRole(str, Enum):
    MAIN_TENDER = "Main Tender Document / RFP"
    NIT_NOTICE = "Notice Inviting Tender (NIT / Brief Notice)"
    CORRIGENDUM = "Corrigendum / Addendum / Amendment"
    BOQ_SCHEDULE = "Bill of Quantities (BOQ) / Price Schedule"
    CONTRACT_AGREEMENT = "Draft Contract Agreement"
    TECHNICAL_SPECIFICATION = "Technical Specification Annexure"
    UNRELATED_DOCUMENT = "Unrelated / Non-Tender PDF"


# Domain Keyword Lexicons
_LEXICON_MAP: Dict[ProcurementCategory, List[str]] = {
    ProcurementCategory.CCTV_SURVEILLANCE: [
        "cctv", "surveillance", "ip camera", "bullet camera", "dome camera", "ptz",
        "anpr", "automatic number plate", "nvr", "vms", "video management",
        "body worn camera", "bwc", "command control center", "iccc", "surveillance system"
    ],
    ProcurementCategory.IT_HARDWARE: [
        "desktop", "workstation", "laptop", "server", "storage area network", "san",
        "nas", "computing system", "monitor", "ups", "printer", "scanner",
        "intel core", "xeon", "ram", "ssd", "hard disk", "it equipment"
    ],
    ProcurementCategory.NETWORKING_TELECOM: [
        "wi-fi", "wifi", "access point", "switch", "router", "core switch",
        "firewall", "structured cabling", "cat6", "optical fiber", "ofc",
        "wlan", "network controller", "poe switch", "telecom", "lan switch"
    ],
    ProcurementCategory.SOFTWARE_DEV: [
        "software development", "web application", "mobile app", "web portal", "portal development",
        "source code", "database", "api integration", "frontend", "backend",
        "sdlc", "user acceptance testing", "uat", "erp", "crm"
    ],
    ProcurementCategory.CIVIL_CONSTRUCTION: [
        "civil works", "construction", "building", "road", "bridge", "earthwork",
        "excavation", "concrete", "rcc", "reinforcement", "masonry", "pavement",
        "drainage", "plumbing", "finishing", "boq item", "sqm", "cu.m", "cubic meter"
    ],
    ProcurementCategory.MANPOWER_STAFFING: [
        "manpower", "staffing", "deployment of personnel", "unskilled", "semi-skilled",
        "skilled", "highly skilled", "minimum wages", "epf", "esic", "labour welfare",
        "attendance", "shift", "data entry operator", "security guard", "housekeeping staff"
    ],
    ProcurementCategory.AMC_MAINTENANCE: [
        "annual maintenance", "comprehensive maintenance", "amc", "camc", "o&m",
        "operation and maintenance", "preventive maintenance", "breakdown maintenance",
        "sla", "uptime guarantee", "response time", "resolution time", "spares"
    ],
    ProcurementCategory.ELECTRICAL_ELECTRONICS: [
        "electrical works", "transformer", "dg set", "generator", "substation",
        "ht panel", "lt panel", "cabling", "energy meter", "smart meter",
        "feeder", "switchgear", "led lighting", "solar", "photovoltaic"
    ],
    ProcurementCategory.MEDICAL_HEALTHCARE: [
        "medical equipment", "hospital", "patient monitor", "ventilator",
        "ultrasound", "x-ray", "mri", "ct scan", "biomedical", "surgical",
        "cdsco", "diagnostic", "pharmaceutical", "icu"
    ]
}


class UniversalProcurementClassifier:
    """Classifies procurement documents accurately into domains and contract types."""

    def __init__(self) -> None:
        pass

    def classify_document(
        self,
        text_sample: str,
        filename: str = "",
        total_pages: int = 1
    ) -> Dict[str, Any]:
        """Classifies a document based on text and structure.
        
        Args:
            text_sample: Aggregated text from front and middle pages.
            filename: Document filename.
            total_pages: Total number of pages.
            
        Returns:
            Dict containing primary_category, secondary_categories, contract_type,
            document_role, and domain_signals.
        """
        sample_low = (text_sample + " " + filename).lower()

        # 1. Document Role Classification
        doc_role = self._classify_role(sample_low, filename, total_pages)

        # 2. Procurement Category Scoring with word boundaries
        category_scores: Dict[ProcurementCategory, int] = {}
        for cat, keywords in _LEXICON_MAP.items():
            score = 0
            for kw in keywords:
                pattern = rf"\b{re.escape(kw)}\b"
                cnt = len(re.findall(pattern, sample_low))
                if cnt > 0:
                    weight = 4 if kw in filename.lower() else 1
                    # Give extra weight to matches appearing in title / first 1500 chars
                    if len(re.findall(pattern, sample_low[:1500])) > 0:
                        weight += 2
                    score += cnt * weight
            if score > 0:
                category_scores[cat] = score

        # Determine Primary & Secondary Categories
        sorted_cats = sorted(category_scores.items(), key=lambda x: x[1], reverse=True)
        primary_cat = sorted_cats[0][0] if sorted_cats else ProcurementCategory.GENERAL_GOODS
        secondary_cats = [c[0].value for c in sorted_cats[1:3]] if len(sorted_cats) > 1 else []

        # 3. Contract Type Classification
        contract_type = self._classify_contract_type(sample_low, primary_cat)

        logger.info(
            f"[UNIVERSAL_CLASSIFIER] File '{filename}' -> Category: {primary_cat.value} | "
            f"Type: {contract_type.value} | Role: {doc_role.value}"
        )

        return {
            "primary_category": primary_cat.value,
            "primary_category_code": primary_cat.name,
            "secondary_categories": secondary_cats,
            "contract_type": contract_type.value,
            "document_role": doc_role.value,
            "is_corrigendum": doc_role == DocumentRole.CORRIGENDUM,
            "is_works": contract_type in (ContractType.WORKS, ContractType.EPC_TURNKEY),
            "is_services": contract_type in (ContractType.SERVICES, ContractType.CONSULTANCY),
            "is_supply": contract_type in (ContractType.SUPPLY_GOODS, ContractType.HYBRID_SUPPLY_INSTALL),
        }

    def _classify_role(self, sample_low: str, filename: str, total_pages: int) -> DocumentRole:
        fn_low = filename.lower()
        if any(k in fn_low or k in sample_low[:1500] for k in ["corrigendum", "addendum", "amendment", "errata"]):
            return DocumentRole.CORRIGENDUM
        if any(k in fn_low for k in ["boq", "price_bid", "financial_bid", "schedule_of_rates", "sor"]):
            return DocumentRole.BOQ_SCHEDULE
        if any(k in sample_low[:1000] for k in ["notice inviting tender", "nit no", "e-tender notice", "invitation for bids"]):
            return DocumentRole.MAIN_TENDER
        if any(k in sample_low[:1000] for k in ["request for proposal", "rfp no", "tender document", "bidding document"]):
            return DocumentRole.MAIN_TENDER
        if any(k in sample_low[:1000] for k in ["draft contract", "articles of agreement", "form of contract"]):
            return DocumentRole.CONTRACT_AGREEMENT
        return DocumentRole.MAIN_TENDER

    def _classify_contract_type(self, sample_low: str, primary_cat: ProcurementCategory) -> ContractType:
        if primary_cat == ProcurementCategory.CIVIL_CONSTRUCTION:
            return ContractType.WORKS
        if primary_cat in (ProcurementCategory.MANPOWER_STAFFING, ProcurementCategory.HOUSEKEEPING_FACILITY, ProcurementCategory.SECURITY_SERVICES):
            return ContractType.SERVICES
        if primary_cat == ProcurementCategory.CONSULTANCY_SERVICES:
            return ContractType.CONSULTANCY
        if primary_cat == ProcurementCategory.AMC_MAINTENANCE:
            return ContractType.SERVICES

        has_supply = any(k in sample_low for k in ["supply", "procurement of goods", "equipment", "hardware", "material"])
        has_install = any(k in sample_low for k in ["installation", "commissioning", "deployment", "integration"])
        has_maintenance = any(k in sample_low for k in ["comprehensive maintenance", "warranty maintenance", "amc", "camc"])

        if has_supply and (has_install or has_maintenance):
            return ContractType.HYBRID_SUPPLY_INSTALL
        if has_supply:
            return ContractType.SUPPLY_GOODS
        if any(k in sample_low for k in ["turnkey", "epc", "design, supply, install"]):
            return ContractType.EPC_TURNKEY
        if any(k in sample_low for k in ["services", "service provider", "sla"]):
            return ContractType.SERVICES

        return ContractType.HYBRID_SUPPLY_INSTALL


universal_classifier = UniversalProcurementClassifier()

