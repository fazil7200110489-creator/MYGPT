"""Domain Detector — Multi-Industry Taxonomy Engine for Resume Intelligence.

Identifies the professional domain/industry of a candidate resume based on structured
entities (skills, designations, experience, projects) and document context text.

Supported Domains:
    - Software Development
    - Data Analytics
    - HR & Talent Acquisition
    - Finance & Accounts
    - Civil Engineering
    - Electrical Engineering
    - Mechanical Engineering
    - Healthcare
    - Education & Academia
    - Sales & Business Development
    - Marketing
    - Procurement & Supply Chain
    - Tender & Bidding
    - Logistics & Warehousing
    - Customer Support
    - Manufacturing & Operations
    - Legal & Compliance
    - Banking & Financial Services
    - Network & Infrastructure
    - QA & Testing
    - UI/UX Design
"""

import os
import json
import re
from typing import Dict, Any, List, Set, Tuple
from loguru import logger

def _load_domain_taxonomy_from_json() -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    config_path = os.path.join(base_dir, "config", "domain_taxonomy.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                keywords = data.get("domain_keywords", {})
                recommendations = data.get("domain_recommendations", {})
                if keywords:
                    logger.info("Loaded domain taxonomy dynamically from domain_taxonomy.json")
                    return keywords, recommendations
        except Exception as e:
            logger.warning(f"Failed to load domain_taxonomy.json: {e}")
    return DOMAIN_TAXONOMY, {}

# Declarative fallback domain taxonomy mapping
DOMAIN_TAXONOMY: Dict[str, List[str]] = {
    "Finance & Accounts": [
        "tally", "gst", "sap fico", "accounting", "auditing", "balance sheet",
        "taxation", "bookkeeping", "financial reporting", "accounts payable",
        "accounts receivable", "general ledger", "income tax", "tds",
        "bank reconciliation", "trial balance", "financial analysis", "quickbooks",
        "tally erp", "tally prime", "voucher", "accountant", "chartered accountant",
        "ca", "tax auditor", "statutory audit"
    ],
    "HR & Talent Acquisition": [
        "recruitment", "payroll", "hrms", "employee relations", "onboarding",
        "talent acquisition", "hr generalist", "performance management", "labor laws",
        "hr compliance", "hr policies", "hr operations", "attendance", "compensation",
        "benefits", "staffing", "sourcing", "human resources", "hr executive",
        "exit interview", "hr analytics", "workforce planning"
    ],
    "Civil Engineering": [
        "autocad", "boq", "primavera", "site execution", "structural design",
        "surveying", "estimation", "quantity surveying", "staad pro", "site supervision",
        "concrete", "rcc", "construction management", "building codes",
        "structural engineering", "civil engineer", "site engineer", "bill of quantities",
        "reinforcement", "site management", "mep", "revit structure"
    ],
    "Electrical Engineering": [
        "mv panel", "lv panel", "transformer", "fire fighting systems", "plc", "scada",
        "switchgear", "single line diagram", "electrical design", "cabling", "earthing",
        "substation", "circuit breaker", "relays", "cad electrical", "power distribution",
        "hvac electrical", "electrical engineer", "vfd", "high voltage", "low voltage"
    ],
    "Mechanical Engineering": [
        "solidworks", "catia", "hvac", "piping", "cad/cam", "maintenance",
        "thermodynamics", "autodesk inventor", "ansys", "hydraulics", "pneumatics",
        "cnc", "manufacturing engineering", "plant maintenance", "pump", "compressor",
        "mechanical engineer", "chiller", "machining", "fabrication"
    ],
    "Data Analytics": [
        "sql", "python", "power bi", "tableau", "data visualization", "pandas",
        "numpy", "etl", "data modeling", "business intelligence", "statistics",
        "data warehousing", "looker", "bigquery", "data analyst", "bi developer",
        "dbt", "data analysis", "dashboards"
    ],
    "Software Development": [
        "react", "node", "express", "angular", "vue", "django", "flask", "fastapi",
        "spring boot", "mongodb", "postgresql", "mysql", "docker", "kubernetes",
        "aws", "azure", "git", "rest api", "microservices", "full stack",
        "frontend", "backend", "web developer", "app developer", "flutter", "dart",
        "java", "c++", "c#", ".net", ".net web api", "php", "yii2", "python"
    ],
    "QA & Testing": [
        "selenium", "automation testing", "manual testing", "test cases", "junit",
        "cypress", "postman", "regression testing", "bug tracking", "jira",
        "test planning", "qa engineer", "quality assurance", "test execution",
        "appium", "jmeter", "performance testing"
    ],
    "UI/UX Design": [
        "figma", "wireframing", "user research", "prototyping", "adobe xd",
        "usability testing", "sketch", "user flows", "interaction design",
        "visual design", "ui designer", "ux designer", "ui/ux", "information architecture"
    ],
    "Network & Infrastructure": [
        "ccna", "cisco", "routing", "switching", "network security", "firewall",
        "active directory", "vpn", "dns", "dhcp", "system administration",
        "linux admin", "windows server", "network engineer", "sysadmin", "wan", "lan"
    ],
    "Healthcare": [
        "nursing", "patient care", "clinical", "ehr", "medical billing",
        "diagnosis", "icu", "hospital", "triage", "pharmacology", "vital signs",
        "outpatient", "surgery", "medical records", "registered nurse", "physician",
        "healthcare", "patient assessment"
    ]
}


class DomainDetector:
    """Domain Detector identifies the candidate's professional domain/industry."""

    def __init__(self, taxonomy: Optional[Dict[str, List[str]]] = None):
        keywords, recs = _load_domain_taxonomy_from_json()
        self.taxonomy = taxonomy or keywords or DOMAIN_TAXONOMY
        self.domain_recommendations = recs

    def detect_domain(self, entities: Dict[str, Any], text: str = "") -> str:
        """Detect dominant domain from structured entities and text context.

        Args:
            entities: Structured entities dictionary extracted from document.
            text: Raw document text context.

        Returns:
            Name of detected domain (e.g. "Finance & Accounts", "Civil Engineering",
            "Software Development"), or "General" if undetermined.
        """
        # Collect candidate tokens from structured entities with component weights
        desig_text = ""
        exp_text = ""
        skills_text = ""
        edu_text = ""

        if isinstance(entities, dict):
            # 1. Designation (Highest weight)
            desig = entities.get("designation")
            if desig and isinstance(desig, str):
                desig_text = desig.lower()

            # 2. Skills
            skills = entities.get("skills") or []
            if isinstance(skills, list):
                skills_text = " ".join(str(s).lower() for s in skills if isinstance(s, (str, int)))

            # 3. Work Experience & Responsibilities
            exp_list = entities.get("experience") or entities.get("work_experience") or []
            if isinstance(exp_list, list):
                exp_text = " ".join(str(e).lower() for e in exp_list if e)

            # 4. Education & Specialization
            edu_list = entities.get("education") or []
            if isinstance(edu_list, list):
                edu_text = " ".join(str(e).lower() for e in edu_list if e)

        full_text_lower = text.lower()
        domain_scores: Dict[str, float] = {}

        for domain, triggers in self.taxonomy.items():
            score = 0.0
            for trigger in triggers:
                trig_lower = trigger.lower()
                pattern = r"\b" + re.escape(trig_lower) + r"\b" if " " not in trig_lower else trig_lower

                # Designation match (Weight: 10.0) — highest signal
                if trig_lower in desig_text or (pattern != trig_lower and re.search(pattern, desig_text)):
                    score += 10.0

                # Work Experience & Responsibilities match (Weight: 3.0)
                if trig_lower in exp_text or (pattern != trig_lower and re.search(pattern, exp_text)):
                    score += 3.0

                # Education & Specialization match (Weight: 2.0)
                if trig_lower in edu_text or (pattern != trig_lower and re.search(pattern, edu_text)):
                    score += 2.0

                # Skills & Tools match (Weight: 1.0) — reduced to prevent false positives
                if trig_lower in skills_text or (pattern != trig_lower and re.search(pattern, skills_text)):
                    score += 1.0

                # Document Context match (Weight: 0.5)
                if trig_lower in full_text_lower or (pattern != trig_lower and re.search(pattern, full_text_lower)):
                    score += 0.5

            if score > 0:
                domain_scores[domain] = score

        if not domain_scores:
            return "General"

        # Return top scoring domain
        best_domain = max(domain_scores.items(), key=lambda x: x[1])[0]
        return best_domain


# Module singleton
domain_detector = DomainDetector()
