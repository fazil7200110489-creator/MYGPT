"""Deterministic Excel Aggregation and Numerical Operations Engine.

Executes SUM, AVG, COUNT, MIN, MAX, mode breakdowns, and threshold filters.
Zero mock values. Strictly reads actual workbook cell contents.
"""

import os
import re
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional, Set
from loguru import logger

from backend.app.services.excel.excel_parser import parse_decimal_safe, format_inr, load_workbook_safe
from backend.app.services.excel.workbook_detector import workbook_detector, WorkbookType


class ExcelAggregator:
    """Calculates deterministic statistics, counts, and numerical operations."""

    def inspect_workbook(self, file_path: str) -> Dict[str, Any]:
        """Inspects all sheets, counts valid records, extracts column headers, modes, and statuses."""
        wb = load_workbook_safe(file_path, data_only=True, read_only=True)
        sheet_names = wb.sheetnames

        sheets_data: Dict[str, Any] = {}
        all_headers: List[str] = []
        all_owners: Set[str] = set()
        total_rows_all = 0
        total_valid_rows = 0
        detected_types: Set[str] = set()
        summary_lines: List[str] = []

        for name in sheet_names:
            ws = wb[name]
            rows_raw = list(ws.iter_rows(values_only=True))
            if not rows_raw:
                continue

            total_rows_all += len(rows_raw)

            # Find header row
            header_row_idx = 0
            headers: List[str] = []
            for idx, row in enumerate(rows_raw):
                non_empty = [str(c).strip() for c in row if c is not None and str(c).strip()]
                if len(non_empty) >= 2:
                    header_row_idx = idx
                    headers = [str(c).strip() if c is not None else f"Column_{i+1}" for i, c in enumerate(row)]
                    break

            if not headers and rows_raw:
                headers = [f"Column_{i+1}" for i in range(len(rows_raw[0]))]

            if not all_headers:
                all_headers = [h for h in headers if not h.startswith("Column_")]

            # Detect schema for this sheet
            schema_info = workbook_detector.detect_schema(headers, [])
            detected_types.add(schema_info["workbook_type"])

            mode_col_name = schema_info.get("mode_column")
            status_col_name = schema_info.get("status_column")
            owner_col_name = schema_info.get("owner_column")

            data_rows: List[Dict[str, Any]] = []
            sheet_owners: Set[str] = set()
            mode_counts: Dict[str, int] = {}
            status_counts: Dict[str, int] = {}

            for row in rows_raw[header_row_idx + 1:]:
                non_empty_cells = [c for c in row if c is not None and str(c).strip()]
                if not non_empty_cells:
                    continue

                row_dict: Dict[str, Any] = {}
                for col_idx, header in enumerate(headers):
                    val = row[col_idx] if col_idx < len(row) else None
                    row_dict[header] = val

                # Track owners if sprint
                if schema_info["is_sprint"] and owner_col_name and row_dict.get(owner_col_name):
                    raw_owner = str(row_dict.get(owner_col_name)).strip()
                    if raw_owner:
                        sheet_owners.add(raw_owner)
                        all_owners.add(raw_owner)

                # Track mode distribution
                if mode_col_name and row_dict.get(mode_col_name):
                    m_val = str(row_dict.get(mode_col_name)).strip().upper()
                    if m_val:
                        mode_counts[m_val] = mode_counts.get(m_val, 0) + 1

                # Track status distribution
                if status_col_name and row_dict.get(status_col_name):
                    st_val = str(row_dict.get(status_col_name)).strip().upper()
                    if st_val:
                        status_counts[st_val] = status_counts.get(st_val, 0) + 1

                data_rows.append(row_dict)

            # Filter valid populated records (for UPI/EBO workbooks with blank summary rows at bottom)
            valid_rows = [r for r in data_rows if (r.get(status_col_name) if status_col_name else True)]
            if not valid_rows:
                valid_rows = data_rows

            total_valid_rows += len(valid_rows)

            sheets_data[name] = {
                "headers": headers,
                "row_count": len(data_rows),
                "valid_row_count": len(valid_rows),
                "valid_rows": valid_rows,
                "rows": data_rows,
                "modes": mode_counts,
                "statuses": status_counts,
                "owners": sorted(list(sheet_owners)),
                "schema": schema_info
            }

            if schema_info["is_sprint"]:
                summary_lines.append(f"Sheet '{name}': {len(valid_rows)} tasks | Owners: {', '.join(sorted(sheet_owners)) or 'None'}")
            elif schema_info["is_transaction"] or schema_info["is_ebo"]:
                modes_str = ", ".join([f"{k}: {v}" for k, v in mode_counts.items()])
                summary_lines.append(f"Sheet '{name}': {len(valid_rows)} transactions | Modes: {modes_str}")
            else:
                summary_lines.append(f"Sheet '{name}': {len(data_rows)} rows")

        wb.close()

        # Determine overall workbook type
        overall_type = WorkbookType.GENERIC.value
        if WorkbookType.TRANSACTION.value in detected_types:
            overall_type = WorkbookType.TRANSACTION.value
        elif WorkbookType.EBO_TOPUP.value in detected_types:
            overall_type = WorkbookType.EBO_TOPUP.value
        elif WorkbookType.SPRINT.value in detected_types:
            overall_type = WorkbookType.SPRINT.value
        elif WorkbookType.INVOICE.value in detected_types:
            overall_type = WorkbookType.INVOICE.value
        elif WorkbookType.EMPLOYEE.value in detected_types:
            overall_type = WorkbookType.EMPLOYEE.value

        return {
            "worksheet_names": sheet_names,
            "sheets": sheets_data,
            "headers": all_headers,
            "owners": sorted(list(all_owners)) if overall_type == WorkbookType.SPRINT.value else [],
            "total_rows": total_rows_all,
            "total_valid_rows": total_valid_rows,
            "workbook_type": overall_type,
            "text_summary": "\n".join(summary_lines)
        }

    def calculate_aggregation(
        self,
        file_path: str,
        target_column: Optional[str] = None,
        operation: str = "SUM",
        filter_criteria: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Calculates exact deterministic aggregations (SUM, AVG, COUNT, MIN, MAX) over numeric or ID columns."""
        import re
        inspection = self.inspect_workbook(file_path)
        sheets = inspection.get("sheets") or {}

        all_headers = [str(h).strip() for h in inspection.get("headers", []) if h is not None]
        amount_candidates = [
            h for h in all_headers
            if any(k in h.lower() for k in ["amount", "settled", "total", "value", "price", "fee", "hours", "cost"])
        ]

        # Priority Selection
        selected_col = None
        is_count_op = (operation.upper() == "COUNT")

        if target_column:
            t_clean = str(target_column).strip().lower()
            t_norm = re.sub(r"[_\s\-]+", "", t_clean)

            # 1. Exact match (case-insensitive)
            for h in all_headers:
                if h.lower() == t_clean:
                    selected_col = h
                    break

            # 2. Normalized token match (strip spaces, underscores, hyphens)
            if not selected_col:
                for h in all_headers:
                    h_norm = re.sub(r"[_\s\-]+", "", h.lower())
                    if t_norm and t_norm == h_norm:
                        selected_col = h
                        break

            # 3. Substring match
            if not selected_col:
                for h in all_headers:
                    if t_clean in h.lower():
                        selected_col = h
                        break

            # 4. ID Aliases if user asked for transaction IDs / IDs
            if not selected_col and any(k in t_clean for k in ["transaction id", "transaction_id", "txn", "rid", "unique id", "id", "reference"]):
                for alias in ["bank transaction id", "vendor reference id", "ebo id", "unique_id", "rid", "trn", "crn", "transaction id", "reference no", "transaction number"]:
                    for h in all_headers:
                        if alias in h.lower() or re.sub(r"[_\s\-]+", "", alias) == re.sub(r"[_\s\-]+", "", h.lower()):
                            selected_col = h
                            break
                    if selected_col:
                        break

        # Default column selection if not explicitly matched
        if not selected_col:
            if is_count_op:
                # Priority for COUNT: Key / ID column first, then first header
                for id_cand in ["bank transaction id", "vendor reference id", "ebo id", "transaction id", "rid", "unique_id", "trn", "crn", "reference no", "id"]:
                    for h in all_headers:
                        if id_cand in h.lower():
                            selected_col = h
                            break
                    if selected_col:
                        break
                if not selected_col and all_headers:
                    selected_col = all_headers[0]
            else:
                # Priority for SUM/AVG/MIN/MAX: Exact 'Amount', 'Total Amount', etc.
                for h in all_headers:
                    if h.strip().lower() == "amount":
                        selected_col = h
                        break
                if not selected_col:
                    for h in all_headers:
                        if h.strip().lower() == "total amount":
                            selected_col = h
                            break
                if not selected_col:
                    for cand in ["settled_amount", "transaction amount", "requested amount", "payment amount", "net amount", "total"]:
                        for h in all_headers:
                            if cand in h.strip().lower():
                                selected_col = h
                                break
                        if selected_col:
                            break
                if not selected_col and amount_candidates:
                    selected_col = amount_candidates[0]
                elif not selected_col and all_headers:
                    selected_col = all_headers[0]

        values: List[Decimal] = []
        non_empty_rows = 0
        rows_detected = 0
        status_filtered_count = 0
        max_row: Optional[Dict[str, Any]] = None
        min_row: Optional[Dict[str, Any]] = None
        max_val_found: Optional[Decimal] = None
        min_val_found: Optional[Decimal] = None

        for s_name, s_info in sheets.items():
            schema_info = s_info.get("schema") or {}
            status_col = schema_info.get("status_column")
            mode_col = schema_info.get("mode_column")

            for r in s_info.get("valid_rows", []):
                # Filter by mode if requested
                if isinstance(filter_criteria, dict) and "mode" in filter_criteria and mode_col:
                    target_mode = str(filter_criteria["mode"]).strip().upper()
                    row_mode = str(r.get(mode_col) or "").strip().upper()
                    if row_mode != target_mode:
                        continue

                val_raw = r.get(selected_col)
                if val_raw is not None and str(val_raw).strip():
                    non_empty_rows += 1

                dec_val = parse_decimal_safe(val_raw)

                # Filter by min_amount threshold if requested
                if isinstance(filter_criteria, dict) and "min_amount" in filter_criteria and dec_val is not None:
                    if dec_val < Decimal(str(filter_criteria["min_amount"])):
                        continue

                if dec_val is not None:
                    values.append(dec_val)
                    if max_val_found is None or dec_val > max_val_found:
                        max_val_found = dec_val
                        max_row = dict(r)
                    if min_val_found is None or dec_val < min_val_found:
                        min_val_found = dec_val
                        min_row = dict(r)

                rows_detected += 1

                if status_col and str(r.get(status_col) or "").strip().upper() in ("AUTHORISED", "SUCCESS"):
                    status_filtered_count += 1

        total_sum = sum(values) if values else Decimal("0")
        count_val = len(values)
        avg_val = (total_sum / Decimal(str(count_val))) if count_val > 0 else Decimal("0")
        min_val = min_val_found if min_val_found is not None else (min(values) if values else Decimal("0"))
        max_val = max_val_found if max_val_found is not None else (max(values) if values else Decimal("0"))

        # For COUNT operation, authorised_count is status_filtered_count or non_empty_rows or rows_detected
        auth_cnt = status_filtered_count if status_filtered_count > 0 else (non_empty_rows if non_empty_rows > 0 else rows_detected)

        return {
            "selected_column": selected_col,
            "all_amount_candidates": amount_candidates,
            "rows_detected": rows_detected,
            "authorised_count": auth_cnt,
            "numeric_count": count_val if not is_count_op else (non_empty_rows if non_empty_rows > 0 else rows_detected),
            "total": total_sum,
            "average": avg_val,
            "min": min_val,
            "max": max_val,
            "max_row": max_row,
            "min_row": min_row,
            "formatted_total": format_inr(total_sum),
            "formatted_average": format_inr(avg_val),
            "formatted_max": format_inr(max_val),
            "formatted_min": format_inr(min_val),
            "workbook_type": inspection.get("workbook_type", WorkbookType.GENERIC.value),
            "source_file": os.path.basename(file_path)
        }

    def calculate_group_aggregation(
        self,
        file_path: str,
        group_column: Optional[str] = None,
        target_column: Optional[str] = None,
        agg_type: str = "max"
    ) -> Dict[str, Any]:
        """Groups workbook records by group_column and computes aggregate (max/min/sum/avg) per group with real row records."""
        inspection = self.inspect_workbook(file_path)
        sheets = inspection.get("sheets", {})
        all_headers = inspection.get("headers", [])

        # Resolve columns
        resolved_group = group_column or "Transaction Mode"
        if resolved_group not in all_headers:
            for h in all_headers:
                if re.sub(r'[^a-z0-9]', '', h.lower()) == re.sub(r'[^a-z0-9]', '', resolved_group.lower()):
                    resolved_group = h
                    break
            else:
                for h in all_headers:
                    if any(k in h.lower() for k in ["mode", "channel", "type", "agent", "store"]):
                        resolved_group = h
                        break

        resolved_target = target_column or "Amount"
        if resolved_target not in all_headers:
            for h in all_headers:
                if re.sub(r'[^a-z0-9]', '', h.lower()) == re.sub(r'[^a-z0-9]', '', resolved_target.lower()):
                    resolved_target = h
                    break
            else:
                for h in all_headers:
                    if any(k in h.lower() for k in ["amount", "settled", "total", "val"]):
                        resolved_target = h
                        break

        groups: Dict[str, List[Dict[str, Any]]] = {}
        for s_name, s_info in sheets.items():
            for r in s_info.get("valid_rows", []):
                g_val = str(r.get(resolved_group) or "Unknown").strip()
                if not g_val:
                    g_val = "Unknown"
                if g_val not in groups:
                    groups[g_val] = []
                groups[g_val].append(dict(r))

        group_results = []
        overall_top_group = None
        overall_top_val = None

        for g_name, g_rows in groups.items():
            vals = []
            top_r = None
            top_v = None
            for r in g_rows:
                dec = parse_decimal_safe(r.get(resolved_target))
                if dec is not None:
                    vals.append(dec)
                    if agg_type in ("max", "highest", "top"):
                        if top_v is None or dec > top_v:
                            top_v = dec
                            top_r = r
                    elif agg_type in ("min", "lowest", "bottom"):
                        if top_v is None or dec < top_v:
                            top_v = dec
                            top_r = r

            g_sum = sum(vals) if vals else Decimal("0")
            g_avg = (g_sum / Decimal(str(len(vals)))) if vals else Decimal("0")
            effective_v = top_v if top_v is not None else (g_sum if agg_type == "sum" else g_avg)

            if overall_top_val is None or (effective_v > overall_top_val if agg_type in ("max", "highest", "sum") else effective_v < overall_top_val):
                overall_top_val = effective_v
                overall_top_group = g_name

            group_results.append({
                "group": g_name,
                "count": len(g_rows),
                "numeric_count": len(vals),
                "aggregate_value": effective_v,
                "formatted_value": format_inr(effective_v),
                "total": g_sum,
                "formatted_total": format_inr(g_sum),
                "average": g_avg,
                "formatted_average": format_inr(g_avg),
                "top_row": top_r or (g_rows[0] if g_rows else {})
            })

        # Sort groups descending by aggregate value
        group_results.sort(key=lambda x: x["aggregate_value"], reverse=(agg_type not in ("min", "lowest", "bottom")))

        return {
            "group_column": resolved_group,
            "target_column": resolved_target,
            "agg_type": agg_type,
            "total_groups": len(group_results),
            "groups": group_results,
            "top_group": overall_top_group,
            "top_value": overall_top_val,
            "formatted_top_value": format_inr(overall_top_val) if overall_top_val is not None else "₹0.00",
            "source_file": os.path.basename(file_path)
        }

    def parse_date_safe(self, val: Any) -> Optional[date]:
        """Safely parses a cell value into a Python date object."""
        if val is None:
            return None
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, date):
            return val
        s = str(val).strip()
        if not s or s.lower() in ("none", "null", "nan", "nat", ""):
            return None
        
        # Excel serial date numbers (e.g. 45150)
        try:
            if s.isdigit() and 20000 <= int(s) <= 70000:
                excel_base = date(1899, 12, 30)
                return excel_base + timedelta(days=int(s))
        except Exception:
            pass

        clean_s = s.split("T")[0].split(" ")[0] if (" " in s or "T" in s) else s
        formats = [
            "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d",
            "%d-%b-%Y", "%d-%B-%Y", "%b %d, %Y", "%B %d, %Y", "%Y%m%d"
        ]
        for fmt in formats:
            try:
                return datetime.strptime(clean_s, fmt).date()
            except Exception:
                continue

        # Regex fallback for YYYY-MM-DD
        m1 = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
        if m1:
            try:
                return date(int(m1.group(1)), int(m1.group(2)), int(m1.group(3)))
            except Exception:
                pass
        
        # Regex fallback for DD-MM-YYYY or MM-DD-YYYY
        m2 = re.search(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", s)
        if m2:
            try:
                p1, p2, yr = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
                if p2 > 12:  # p2 is day, p1 is month
                    return date(yr, p1, p2)
                else:  # assume p1 is day, p2 is month
                    return date(yr, p2, p1)
            except Exception:
                pass
        return None

    def filter_rows(
        self,
        file_path: str,
        filters: Optional[Any] = None,
        target_columns: Optional[List[str]] = None,
        reference_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """Filters workbook rows using generic condition operators and returns matching records with extracted columns."""
        inspection = self.inspect_workbook(file_path)
        sheets = inspection.get("sheets", {})
        all_headers = inspection.get("headers", [])
        
        ref_today = reference_date or date.today()
        
        # Normalize filters into list of dicts
        filter_list: List[Dict[str, Any]] = []
        if isinstance(filters, list):
            filter_list = [f for f in filters if isinstance(f, dict)]
        elif isinstance(filters, dict):
            if "column" in filters or "operator" in filters:
                filter_list = [filters]
            else:
                for k, v in filters.items():
                    if k == "mode":
                        filter_list.append({"column": "Transaction Mode", "operator": "EQUALS", "value": v})
                    elif k == "min_amount":
                        filter_list.append({"column": "Amount", "operator": "GREATER_THAN", "value": v})
                    else:
                        filter_list.append({"column": k, "operator": "EQUALS", "value": v})

        # Resolve column names for filters against actual workbook headers
        from backend.app.services.excel.semantic_excel_resolver import semantic_excel_resolver
        
        resolved_filters = []
        for f in filter_list:
            col_raw = f.get("column") or f.get("field") or "Expiry_Date"
            resolved_col = semantic_excel_resolver.resolve_column(col_raw, all_headers) or col_raw
            op = str(f.get("operator", "EQUALS")).strip().upper()
            val = f.get("value")
            resolved_filters.append({
                "column": resolved_col,
                "operator": op,
                "value": val
            })

        # Resolve target columns if provided
        resolved_target_cols = []
        if target_columns:
            if isinstance(target_columns, str):
                if target_columns.upper() != "ALL":
                    resolved_target_cols = [semantic_excel_resolver.resolve_column(target_columns, all_headers) or target_columns]
            elif isinstance(target_columns, list):
                for tc in target_columns:
                    if str(tc).upper() != "ALL":
                        resolved_c = semantic_excel_resolver.resolve_column(str(tc), all_headers) or str(tc)
                        resolved_target_cols.append(resolved_c)

        matched_rows: List[Dict[str, Any]] = []
        total_rows_scanned = 0

        for s_name, s_info in sheets.items():
            for r in s_info.get("rows", []):
                total_rows_scanned += 1
                row_matches = True

                for flt in resolved_filters:
                    col_name = flt["column"]
                    op = flt["operator"]
                    expected_val = flt["value"]
                    cell_val = r.get(col_name)

                    if op in ("BEFORE_TODAY", "EXPIRED", "LESS_THAN_TODAY"):
                        d_val = self.parse_date_safe(cell_val)
                        if d_val is None or d_val >= ref_today:
                            row_matches = False
                            break
                    elif op in ("AFTER_TODAY", "ACTIVE", "VALID", "GREATER_THAN_TODAY"):
                        d_val = self.parse_date_safe(cell_val)
                        if d_val is None or d_val < ref_today:
                            row_matches = False
                            break
                    elif op == "TODAY":
                        d_val = self.parse_date_safe(cell_val)
                        if d_val is None or d_val != ref_today:
                            row_matches = False
                            break
                    elif op == "TOMORROW":
                        d_val = self.parse_date_safe(cell_val)
                        if d_val is None or d_val != (ref_today + timedelta(days=1)):
                            row_matches = False
                            break
                    elif op in ("THIS_WEEK", "CURRENT_WEEK"):
                        d_val = self.parse_date_safe(cell_val)
                        if d_val is None:
                            row_matches = False
                            break
                        w_start = ref_today - timedelta(days=ref_today.weekday())
                        w_end = w_start + timedelta(days=6)
                        if not (w_start <= d_val <= w_end):
                            row_matches = False
                            break
                    elif op in ("THIS_MONTH", "CURRENT_MONTH"):
                        d_val = self.parse_date_safe(cell_val)
                        if d_val is None or d_val.year != ref_today.year or d_val.month != ref_today.month:
                            row_matches = False
                            break
                    elif op == "LAST_MONTH":
                        d_val = self.parse_date_safe(cell_val)
                        if d_val is None:
                            row_matches = False
                            break
                        lm_y = ref_today.year if ref_today.month > 1 else ref_today.year - 1
                        lm_m = ref_today.month - 1 if ref_today.month > 1 else 12
                        if d_val.year != lm_y or d_val.month != lm_m:
                            row_matches = False
                            break
                    elif op == "NEXT_MONTH":
                        d_val = self.parse_date_safe(cell_val)
                        if d_val is None:
                            row_matches = False
                            break
                        nm_y = ref_today.year if ref_today.month < 12 else ref_today.year + 1
                        nm_m = ref_today.month + 1 if ref_today.month < 12 else 1
                        if d_val.year != nm_y or d_val.month != nm_m:
                            row_matches = False
                            break
                    elif op in ("EQUALS", "EQ", "==", "="):
                        if expected_val is not None:
                            if str(cell_val or "").strip().lower() != str(expected_val).strip().lower():
                                row_matches = False
                                break
                    elif op in ("NOT_EQUALS", "NEQ", "!=", "<>"):
                        if expected_val is not None:
                            if str(cell_val or "").strip().lower() == str(expected_val).strip().lower():
                                row_matches = False
                                break
                    elif op in ("CONTAINS", "LIKE"):
                        if expected_val is not None:
                            if str(expected_val).strip().lower() not in str(cell_val or "").strip().lower():
                                row_matches = False
                                break
                    elif op in ("GREATER_THAN", "GT", ">", "ABOVE", "MORE_THAN"):
                        c_dec = parse_decimal_safe(cell_val)
                        e_dec = parse_decimal_safe(expected_val)
                        if c_dec is None or e_dec is None or c_dec <= e_dec:
                            row_matches = False
                            break
                    elif op in ("GREATER_THAN_OR_EQUALS", "GTE", ">="):
                        c_dec = parse_decimal_safe(cell_val)
                        e_dec = parse_decimal_safe(expected_val)
                        if c_dec is None or e_dec is None or c_dec < e_dec:
                            row_matches = False
                            break
                    elif op in ("LESS_THAN", "LT", "<", "BELOW", "UNDER", "LESS"):
                        c_dec = parse_decimal_safe(cell_val)
                        e_dec = parse_decimal_safe(expected_val)
                        if c_dec is None or e_dec is None or c_dec >= e_dec:
                            row_matches = False
                            break
                    elif op in ("LESS_THAN_OR_EQUALS", "LTE", "<="):
                        c_dec = parse_decimal_safe(cell_val)
                        e_dec = parse_decimal_safe(expected_val)
                        if c_dec is None or e_dec is None or c_dec > e_dec:
                            row_matches = False
                            break

                if row_matches:
                    matched_rows.append(dict(r))

        return {
            "success": True,
            "source_file": os.path.basename(file_path),
            "headers": all_headers,
            "matched_rows": matched_rows,
            "total_matched": len(matched_rows),
            "total_rows": total_rows_scanned,
            "resolved_filters": resolved_filters,
            "target_columns": resolved_target_cols,
            "preview_rows": matched_rows[:10]
        }

    def get_date_extremes(self, file_path: str, target_column: Optional[str] = None, find_max: bool = True) -> Dict[str, Any]:
        """Calculates earliest or latest date in a column with corresponding row record."""
        inspection = self.inspect_workbook(file_path)
        sheets = inspection.get("sheets", {})
        all_headers = inspection.get("headers", [])
        
        from backend.app.services.excel.semantic_excel_resolver import semantic_excel_resolver
        col_to_check = semantic_excel_resolver.resolve_column(target_column or "Expiry_Date", all_headers, concept_hint="date") or "Expiry_Date"

        extreme_date: Optional[date] = None
        extreme_row: Optional[Dict[str, Any]] = None
        valid_date_count = 0

        for s_name, s_info in sheets.items():
            for r in s_info.get("rows", []):
                val = r.get(col_to_check)
                d = self.parse_date_safe(val)
                if d is not None:
                    valid_date_count += 1
                    if extreme_date is None:
                        extreme_date = d
                        extreme_row = dict(r)
                    elif find_max and d > extreme_date:
                        extreme_date = d
                        extreme_row = dict(r)
                    elif not find_max and d < extreme_date:
                        extreme_date = d
                        extreme_row = dict(r)

        return {
            "success": extreme_date is not None,
            "column": col_to_check,
            "target_column": col_to_check,
            "find_max": find_max,
            "formatted_date": str(extreme_date) if extreme_date else "N/A",
            "date_value": str(extreme_date) if extreme_date else "N/A",
            "extreme_date": str(extreme_date) if extreme_date else "N/A",
            "row": extreme_row or {},
            "extreme_row": extreme_row or {},
            "valid_date_count": valid_date_count,
            "source_file": os.path.basename(file_path)
        }


excel_aggregator = ExcelAggregator()

