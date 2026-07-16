import re
import json
from typing import Dict, Any, List, Optional

class EntityExtractor:
    """Extracts logical entities from raw context text and integrates pre-computed knowledge facts."""

    def extract(self, text: str, knowledge: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Combines regex extraction over raw text with structured facts from the knowledge store."""
        entities: Dict[str, Any] = {
            "name": None,
            "phones": [],
            "emails": [],
            "addresses": [],
            "companies": [],
            "organizations": [],
            "skills": [],
            "projects": [],
            "education": [],
            "certifications": [],
            "experience": [],
            "dates": [],
            "amounts": [],
            "invoice_numbers": [],
            "gst": None,
            "tables": [],
            "technologies": []
        }

        # 1. Integrate pre-computed knowledge entities and facts if available
        if knowledge:
            # Extract root level keys
            for key, val in knowledge.items():
                if key not in ["entities", "tables", "metadata", "sections"]:
                    entities[key] = val
            
            # Map legacy names if they exist
            k_entities = knowledge.get("entities", {})
            k_facts = knowledge.get("facts", {})
            tables = knowledge.get("tables", [])

            # Inject legacy properties for backward compatibility
            entities["name"] = k_facts.get("name") or entities.get("candidate_name") or k_entities.get("people", [None])[0]
            entities["phones"] = k_facts.get("phones") or [entities.get("phone")] if entities.get("phone") else k_entities.get("phones", [])
            entities["emails"] = k_facts.get("emails") or [entities.get("email")] if entities.get("email") else k_entities.get("emails", [])
            entities["addresses"] = [entities.get("address")] if entities.get("address") else k_entities.get("addresses", [])
            entities["companies"] = entities.get("companies") or k_entities.get("companies", [])
            entities["projects"] = entities.get("projects") or []
            entities["education"] = entities.get("education") or []
            entities["certifications"] = entities.get("certifications") or []
            entities["experience"] = entities.get("work_experience") or []
            entities["dates"] = k_facts.get("dates") or k_entities.get("dates", [])
            entities["amounts"] = k_entities.get("amounts", [])
            entities["invoice_numbers"] = [k_facts.get("invoice_number")] if k_facts.get("invoice_number") else []
            entities["gst"] = k_facts.get("gst") or k_facts.get("tax")
            entities["tables"] = tables

        # 2. Extract from raw text context if pre-computed fields are empty
        if not entities["emails"]:
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
            entities["emails"] = list(set(emails))
            
        if not entities["phones"]:
            phones = re.findall(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}', text)
            entities["phones"] = list(set([p.strip() for p in phones]))

        if not entities["name"]:
            # Heuristic for name
            name_match = re.search(r'(?i)\bname\s*:\s*([A-Za-z\s]{2,40})(?:\n|,|$)', text)
            if name_match:
                entities["name"] = name_match.group(1).strip()
            else:
                # Find first Capitalized Firstname Lastname
                capital_name = re.search(r'\b([A-Z][a-z]+)\s+([A-Z][a-z]+)\b', text)
                if capital_name:
                    entities["name"] = capital_name.group(0)

        if not entities["dates"]:
            dates = re.findall(
                r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b'
                r'|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+\d{2,4}\b',
                text, re.IGNORECASE
            )
            entities["dates"] = list(set(dates))

        if not entities["amounts"]:
            amounts = re.findall(r'[\$\u20b9\u20ac\u00a3]\s*[\d,]+\.?\d*', text)
            entities["amounts"] = list(set(amounts))

        if not entities["invoice_numbers"]:
            inv_match = re.search(r'(?i)(?:invoice\s*number\s*:\s*|invoice\s*id\s*:\s*|invoice\s*#\s*|inv\s*#\s*)([a-z0-9-]+)', text)
            if inv_match:
                entities["invoice_numbers"] = [inv_match.group(1).strip()]

        # Ensure lists are clean of duplicates while preserving order
        for key in ["phones", "emails", "companies", "skills", "projects", "education", "certifications", "experience", "dates", "amounts"]:
            val_list = entities[key]
            if isinstance(val_list, list):
                seen = set()
                cleaned = []
                for item in val_list:
                    if item and str(item).strip().lower() not in seen:
                        seen.add(str(item).strip().lower())
                        cleaned.append(item)
                entities[key] = cleaned

        return entities
