"""Excel Parsing and Data Conversion Utilities.

Zero mock data. Defensive conversion of dirty numerical strings, currencies, and null representations.
"""

import re
import os
from decimal import Decimal, InvalidOperation
from typing import Any, Optional, Dict, List, Tuple
import openpyxl
from loguru import logger


def parse_decimal_safe(val: Any) -> Optional[Decimal]:
    """Safely converts any value (string, float, int, formatted currency) into a Decimal.
    
    Handles:
    - Commas ("1,519,715.76" -> 1519715.76)
    - Currency symbols ("$2,250.00", "₹50,000.00", "INR 100")
    - Whitespace and padding ("  1000.0  ")
    - Scientific notation and edge cases
    - None, "", "N/A", "NULL", "-", "None" -> None
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        if isinstance(val, float) and (val != val):  # NaN check
            return None
        return Decimal(str(val))
    if isinstance(val, Decimal):
        return val

    s = str(val).strip()
    if not s or s.upper() in ("NONE", "NULL", "N/A", "NA", "-", "--", "N.A."):
        return None

    # Strip currency symbols and letters
    cleaned = re.sub(r"[₹$€£¥\s]", "", s)
    cleaned = re.sub(r"(?i)^(inr|usd|eur|gbp)\s*", "", cleaned)
    # Remove thousands separators
    cleaned = cleaned.replace(",", "")

    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def format_inr(amount: Any) -> str:
    """Formats a numeric amount in standard Indian Numbering Format with Indian Rupee symbol (₹).
    
    Example:
    1519715.76 -> ₹15,19,715.76
    1087.06 -> ₹1,087.06
    50000 -> ₹50,000.00
    """
    if amount is None:
        return "₹0.00"
    dec = parse_decimal_safe(amount)
    if dec is None:
        return str(amount)

    sign = "-" if dec < 0 else ""
    abs_dec = abs(dec)
    formatted_base = f"{abs_dec:.2f}"
    parts = formatted_base.split(".")
    integer_part = parts[0]
    fractional_part = parts[1]

    if len(integer_part) <= 3:
        grouped = integer_part
    else:
        last3 = integer_part[-3:]
        remaining = integer_part[:-3]
        groups = []
        while len(remaining) > 2:
            groups.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            groups.insert(0, remaining)
        grouped = ",".join(groups) + "," + last3

    return f"{sign}₹{grouped}.{fractional_part}"


def load_workbook_safe(file_path: str, data_only: bool = True, read_only: bool = True) -> openpyxl.Workbook:
    """Safely loads an Excel workbook with error handling."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Workbook file not found: {file_path}")
    return openpyxl.load_workbook(file_path, data_only=data_only, read_only=read_only)
