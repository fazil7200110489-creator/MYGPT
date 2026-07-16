import re
from typing import Dict, Any, List, Optional

class InvoiceReasoner:
    """Document Specialist for parsing and reasoning over Invoices."""

    def reason(self, entities: Dict[str, Any], facts: List[str], intent: str) -> Any:
        """Extracts invoice details (total, vendor, dates, customer) based on intent."""
        intent_upper = intent.upper()

        if intent_upper in ["INVOICE_TOTAL", "TOTAL"]:
            # Retrieve amount
            amt = entities.get("amounts")
            if amt:
                # Find the largest numeric amount or the one labeled grand/total
                cleaned_amts = []
                for a in amt:
                    val = re.sub(r'[^\d.]', '', a)
                    try:
                        if val:
                            cleaned_amts.append(float(val))
                    except ValueError:
                        pass
                if cleaned_amts:
                    # Return the maximum amount which is typically the grand total
                    return str(max(cleaned_amts))
            return facts[0] if facts else None

        elif intent_upper == "GST":
            return entities.get("gst") or (facts[0] if facts else None)

        elif intent_upper in ["DATE", "DATES"]:
            return entities["dates"][0] if entities.get("dates") else None

        elif intent_upper == "INVOICE_NUMBER":
            return entities["invoice_numbers"][0] if entities.get("invoice_numbers") else None

        # Fallback keyword matching on facts for customer/vendor
        for fact in facts:
            if "vendor" in fact.lower() or "from" in fact.lower() or "issued by" in fact.lower():
                if ":" in fact:
                    return fact.split(":", 1)[1].strip()
            if "customer" in fact.lower() or "bill to" in fact.lower() or "to" in fact.lower():
                if ":" in fact:
                    return fact.split(":", 1)[1].strip()

        return facts[0] if facts else "No invoice data match found."
