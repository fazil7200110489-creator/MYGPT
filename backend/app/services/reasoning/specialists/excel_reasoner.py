import re
from typing import Dict, Any, List, Optional

class ExcelReasoner:
    """Document Specialist for Excel tables, performing calculations without NLP."""

    def reason(self, entities: Dict[str, Any], facts: List[str], intent: str) -> Any:
        """Computes statistical metrics (len, sum, max, min, mean) on tabular data."""
        tables = entities.get("tables", [])
        if not tables:
            return "0"

        table = tables[0]
        rows = table.get("rows", [])
        headers = table.get("headers", [])
        stats = table.get("stats", {})

        intent_upper = intent.upper()

        # 1. COUNT intent: "how many transactions", "how many rows"
        if intent_upper == "COUNT":
            return str(len(rows))

        # Identify target numeric column (e.g. amount, price, salary, total)
        numeric_cols = list(stats.keys())
        if not numeric_cols:
            return "0"

        # Search for matched column, default to the first numeric column
        target_col = numeric_cols[0]
        for col in numeric_cols:
            col_lower = col.lower()
            if any(k in col_lower for k in ["amount", "price", "salary", "total", "quantity", "cost", "value"]):
                target_col = col
                break

        col_stats = stats[target_col]

        # 2. Perform calculations
        if intent_upper == "HIGHEST":
            val = col_stats["max"]
        elif intent_upper == "LOWEST":
            val = col_stats["min"]
        elif intent_upper == "AVERAGE":
            val = col_stats["avg"]
        elif intent_upper in ["INVOICE_TOTAL", "TOTAL"]:
            val = col_stats["sum"]
        else:
            # Default to count or first stat
            return str(len(rows))

        # Format number: remove trailing .00 if integer
        if isinstance(val, float):
            formatted = f"{val:.2f}"
            if formatted.endswith(".00"):
                formatted = formatted[:-3]
            return formatted

        return str(val)
