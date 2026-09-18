"""Excel Document Processor for Enterprise Sprints, Spreadsheets, Financial Data, and Generic Analytics.

Uses openpyxl for 100% authentic spreadsheet processing:
- Automated schema & domain detection (TRANSACTION, SPRINT, INVOICE, EMPLOYEE, GENERIC)
- Dynamic column recognition with deterministic priorities (Amount, Total Amount, Settled_Amount, etc.)
- Robust decimal parsing (converts numeric-looking strings safely, comma stripping, zero mock values)
- Generic Excel aggregations (EXCEL_TOTAL, EXCEL_AVERAGE, EXCEL_COUNT, EXCEL_MIN, EXCEL_MAX)
- Natural language filtering (by mode e.g. QR/UPI, threshold e.g. >10000, status e.g. AUTHORISED)
- Sprint/Task workbook splitting by owner (Fazil_Sprint.xlsx, Reka_Sprint.xlsx)
- Multi-tab combined split workbooks & high-quality corporate styling
- Zero mock data, zero fake rows — strictly derived from the uploaded workbook.
"""

import io
import os
import re
from decimal import Decimal
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple, Set, Union
from loguru import logger
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


class WorkbookType(str, Enum):
    TRANSACTION = "TRANSACTION"
    SPRINT = "SPRINT"
    INVOICE = "INVOICE"
    EMPLOYEE = "EMPLOYEE"
    GENERIC = "GENERIC"


def parse_decimal_safe(val: Any) -> Optional[Decimal]:
    """Safely converts string/float/int to Decimal ignoring commas, symbols, and whitespace."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return Decimal(str(val))
    if isinstance(val, Decimal):
        return val
    s = str(val).strip().replace(",", "").replace("$", "").replace("₹", "").replace("€", "").replace("£", "")
    if not s or s.lower() in ("null", "none", "nan", "-", "na", "n/a", ""):
        return None
    try:
        return Decimal(s)
    except Exception:
        return None


def format_inr(val: Union[Decimal, float, int]) -> str:
    """Formats a number into standard Indian Rupee notation (e.g. ₹15,19,715.76)."""
    try:
        dec_val = Decimal(str(val))
        s = f"{dec_val:.2f}"
        parts = s.split(".")
        int_part = parts[0]
        dec_part = parts[1]

        is_neg = False
        if int_part.startswith("-"):
            is_neg = True
            int_part = int_part[1:]

        if len(int_part) <= 3:
            formatted_int = int_part
        else:
            last3 = int_part[-3:]
            remaining = int_part[:-3]
            groups = []
            while len(remaining) > 2:
                groups.insert(0, remaining[-2:])
                remaining = remaining[:-2]
            if remaining:
                groups.insert(0, remaining)
            groups.append(last3)
            formatted_int = ",".join(groups)

        prefix = "-₹" if is_neg else "₹"
        return f"{prefix}{formatted_int}.{dec_part}"
    except Exception:
        return f"₹{val}"


class ExcelProcessor:
    """Production Excel spreadsheet inspection, analysis, filtering, and export service."""

    # Common aliases for column classification
    _OWNER_ALIASES = {"owner", "assignee", "assigned to", "developer", "lead", "resource", "member", "person"}
    _MODULE_ALIASES = {"module", "feature", "component", "epic", "section", "category", "project"}
    _TASK_ALIASES = {"task", "task name", "task title", "title", "story", "item", "work item", "action"}
    _DESC_ALIASES = {"description", "details", "summary", "notes", "scope"}
    _HOURS_ALIASES = {"estimated hours", "est hours", "est. hours", "hours", "estimate", "effort", "story points", "points"}
    _STATUS_ALIASES = {"status", "state", "progress", "condition"}

    _TRANSACTION_KEYWORDS = {"trnsctn", "transaction", "amount", "settled", "commission", "rid", "crn", "trn", "upi", "qr", "cheque", "bank", "aggregrator"}
    _INVOICE_KEYWORDS = {"invoice", "vendor", "subtotal", "tax", "gst", "total amount", "item", "unit price", "quantity", "qty"}
    _EMPLOYEE_KEYWORDS = {"employee", "emp_id", "emp name", "designation", "department", "salary", "joining date", "dob"}

    def detect_schema(self, headers: List[str], sample_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Classifies the workbook schema and identifies key functional columns."""
        h_lower = [str(h).strip().lower() for h in headers]
        h_set = set(h_lower)

        # 1. Check for SPRINT / TASK schema
        has_owner = any(any(a == h or a in h for a in self._OWNER_ALIASES) for h in h_lower)
        has_task_module = any(any(a == h or a in h for a in self._TASK_ALIASES | self._MODULE_ALIASES | self._HOURS_ALIASES) for h in h_lower)

        # 2. Check for TRANSACTION schema
        has_trans_mode = any("mode" in h or "trnsctn" in h or "transaction" in h or "unique_id" in h for h in h_lower)
        has_amount = any("amount" in h or "settled" in h for h in h_lower)
        trans_score = sum(1 for h in h_lower if any(k in h for k in self._TRANSACTION_KEYWORDS))

        # 3. Check for INVOICE schema
        has_invoice_num = any("invoice" in h or "inv" in h for h in h_lower)
        has_vendor = any("vendor" in h or "company" in h for h in h_lower)

        # 4. Check for EMPLOYEE schema
        has_emp = any(any(k in h for k in self._EMPLOYEE_KEYWORDS) for h in h_lower)

        if has_trans_mode and has_amount and trans_score >= 3:
            wb_type = WorkbookType.TRANSACTION
        elif has_owner and has_task_module:
            wb_type = WorkbookType.SPRINT
        elif has_invoice_num and has_amount:
            wb_type = WorkbookType.INVOICE
        elif has_emp and not has_trans_mode:
            wb_type = WorkbookType.EMPLOYEE
        elif has_amount:
            wb_type = WorkbookType.TRANSACTION
        elif has_owner:
            wb_type = WorkbookType.SPRINT
        else:
            wb_type = WorkbookType.GENERIC

        # Column mappings
        amount_cols: List[str] = []
        for h in headers:
            hl = str(h).strip().lower()
            if "amount" in hl or "settled" in hl or "value" in hl or "price" in hl or "fee" in hl:
                amount_cols.append(h)

        status_col = None
        for h in headers:
            if any(a == str(h).strip().lower() for a in ["status", "state", "condition"]):
                status_col = h
                break

        mode_col = None
        for h in headers:
            hl = str(h).strip().lower()
            if "mode" in hl or "type" in hl or "channel" in hl:
                mode_col = h
                break

        return {
            "workbook_type": wb_type.value,
            "amount_columns": amount_cols,
            "status_column": status_col,
            "mode_column": mode_col,
            "is_sprint": wb_type == WorkbookType.SPRINT,
            "is_transaction": wb_type == WorkbookType.TRANSACTION
        }

    def inspect_workbook(self, file_path: str) -> Dict[str, Any]:
        """Inspects an uploaded workbook, extracts sheets, headers, schema classification, and row data."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Excel file not found at: {file_path}")

        try:
            wb = openpyxl.load_workbook(file_path, data_only=True)
        except Exception as e:
            logger.error(f"Failed to open Excel workbook {file_path}: {e}")
            raise ValueError(f"Invalid Excel workbook: {str(e)}")

        sheet_names = wb.sheetnames
        sheets_data: Dict[str, Any] = {}
        all_owners: Set[str] = set()
        all_headers: List[str] = []
        total_rows_all = 0
        total_valid_rows = 0
        summary_lines: List[str] = []
        detected_types: Set[str] = set()

        for name in sheet_names:
            ws = wb[name]
            rows_raw = list(ws.iter_rows(values_only=True))
            if not rows_raw:
                continue

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

            # Detect column mappings
            col_map = self._detect_columns(headers)
            owner_col_idx = col_map.get("owner")

            data_rows: List[Dict[str, Any]] = []
            sheet_owners: Set[str] = set()
            mode_counts: Dict[str, int] = {}
            status_counts: Dict[str, int] = {}

            # Identify schema for this sheet
            schema_info = self.detect_schema(headers, [])
            detected_types.add(schema_info["workbook_type"])

            mode_col_name = schema_info.get("mode_column")
            status_col_name = schema_info.get("status_column")

            for row in rows_raw[header_row_idx + 1:]:
                # Check if row is not completely blank and has at least one meaningful value
                non_empty_cells = [c for c in row if c is not None and str(c).strip()]
                if not non_empty_cells:
                    continue

                row_dict: Dict[str, Any] = {}
                for col_idx, header in enumerate(headers):
                    val = row[col_idx] if col_idx < len(row) else None
                    row_dict[header] = val

                # Track owner only if sprint/task schema
                if schema_info["is_sprint"] and owner_col_idx is not None and owner_col_idx < len(row):
                    raw_owner = row[owner_col_idx]
                    if raw_owner is not None and str(raw_owner).strip():
                        owner_clean = str(raw_owner).strip()
                        sheet_owners.add(owner_clean)
                        all_owners.add(owner_clean)

                # Track mode distribution if transaction
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

            # Filter valid populated records (for UPI workbooks with blank summary rows at bottom)
            valid_rows = [r for r in data_rows if (r.get(status_col_name) if status_col_name else True)]
            if not valid_rows:
                valid_rows = data_rows

            total_rows_all += len(data_rows)
            total_valid_rows += len(valid_rows)

            sheets_data[name] = {
                "headers": headers,
                "col_map": col_map,
                "schema": schema_info,
                "row_count": len(data_rows),
                "valid_row_count": len(valid_rows),
                "owners": sorted(list(sheet_owners)) if schema_info["is_sprint"] else [],
                "modes": mode_counts,
                "statuses": status_counts,
                "rows": data_rows,
                "valid_rows": valid_rows
            }

            if schema_info["is_sprint"]:
                summary_lines.append(
                    f"Sheet '{name}': {len(data_rows)} tasks | Owners: {', '.join(sorted(sheet_owners)) if sheet_owners else 'None'}"
                )
            elif schema_info["is_transaction"]:
                modes_str = ", ".join([f"{k}: {v}" for k, v in mode_counts.items()])
                summary_lines.append(
                    f"Sheet '{name}': {len(valid_rows)} transactions | Modes: {modes_str}"
                )
            else:
                summary_lines.append(
                    f"Sheet '{name}': {len(data_rows)} rows"
                )

        wb.close()

        # Determine overall workbook type
        overall_type = WorkbookType.GENERIC.value
        if WorkbookType.TRANSACTION.value in detected_types:
            overall_type = WorkbookType.TRANSACTION.value
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
        """Calculates exact deterministic aggregations (SUM, AVG, COUNT, MIN, MAX) over numeric columns."""
        inspection = self.inspect_workbook(file_path)
        sheets = inspection.get("sheets", {})

        # Collect all candidate columns
        all_headers = inspection.get("headers", [])
        amount_candidates = [
            h for h in all_headers
            if any(k in str(h).lower() for k in ["amount", "settled", "total", "value", "price", "fee", "hours", "cost"])
        ]

        # Deterministic Priority Selection
        selected_col = None
        if target_column:
            # 1. Check exact match
            for h in all_headers:
                if h.lower() == target_column.lower():
                    selected_col = h
                    break
            # 2. Check contains match
            if not selected_col:
                for h in all_headers:
                    if target_column.lower() in h.lower():
                        selected_col = h
                        break

        if not selected_col:
            # Priority 1: Exact 'Amount'
            for h in all_headers:
                if h.strip().lower() == "amount":
                    selected_col = h
                    break
            # Priority 2: Exact 'Total Amount'
            if not selected_col:
                for h in all_headers:
                    if h.strip().lower() == "total amount":
                        selected_col = h
                        break
            # Priority 3: Semantic aliases
            if not selected_col:
                for h in all_headers:
                    hl = h.strip().lower()
                    if hl in ("settled_amount", "settled amount", "transaction amount", "gross amount", "net amount"):
                        selected_col = h
                        break
            # Priority 4: First available amount candidate
            if not selected_col and amount_candidates:
                selected_col = amount_candidates[0]

        if not selected_col and all_headers:
            selected_col = all_headers[0]

        # Gather numeric values across valid rows
        values: List[Decimal] = []
        rows_detected = 0
        status_filtered_count = 0

        for sheet_name, sheet_info in sheets.items():
            valid_rows = sheet_info.get("valid_rows") or sheet_info.get("rows", [])
            status_col = sheet_info.get("schema", {}).get("status_column")
            mode_col = sheet_info.get("schema", {}).get("mode_column")

            for r in valid_rows:
                # Apply filter criteria if provided
                if filter_criteria:
                    match = True
                    for f_key, f_val in filter_criteria.items():
                        if f_key == "mode" and mode_col:
                            row_mode = str(r.get(mode_col) or "").strip().upper()
                            if row_mode != str(f_val).strip().upper():
                                match = False
                                break
                        elif f_key == "status" and status_col:
                            row_st = str(r.get(status_col) or "").strip().upper()
                            if row_st != str(f_val).strip().upper():
                                match = False
                                break
                        elif f_key == "min_amount" and selected_col:
                            num = parse_decimal_safe(r.get(selected_col))
                            if num is None or num <= Decimal(str(f_val)):
                                match = False
                                break
                    if not match:
                        continue

                raw_val = r.get(selected_col)
                dec_val = parse_decimal_safe(raw_val)
                if dec_val is not None:
                    values.append(dec_val)
                rows_detected += 1

                if status_col and str(r.get(status_col) or "").strip().upper() == "AUTHORISED":
                    status_filtered_count += 1

        total_sum = sum(values) if values else Decimal("0")
        count_val = len(values)
        avg_val = (total_sum / Decimal(str(count_val))) if count_val > 0 else Decimal("0")
        min_val = min(values) if values else Decimal("0")
        max_val = max(values) if values else Decimal("0")

        return {
            "selected_column": selected_col,
            "all_amount_candidates": amount_candidates,
            "rows_detected": rows_detected,
            "authorised_count": status_filtered_count or rows_detected,
            "numeric_count": count_val,
            "total": total_sum,
            "average": avg_val,
            "min": min_val,
            "max": max_val,
            "formatted_total": format_inr(total_sum),
            "formatted_average": format_inr(avg_val),
            "workbook_type": inspection.get("workbook_type", WorkbookType.GENERIC.value),
            "source_file": os.path.basename(file_path)
        }

    def filter_and_export_by_owners(
        self,
        file_path: str,
        target_owners: List[str],
        base_name: str = "Sprint"
    ) -> Dict[str, Any]:
        """Filters rows from source workbook for each requested owner and generates
        separate XLSX files plus a combined multi-tab workbook.
        """
        inspection = self.inspect_workbook(file_path)
        sheets = inspection.get("sheets", {})

        generated_files: List[Dict[str, Any]] = []
        owner_results: Dict[str, Any] = {}

        owner_matchers = {
            owner: re.compile(rf"\b{re.escape(owner.strip())}\b", re.I)
            for owner in target_owners if owner.strip()
        }

        combined_wb = openpyxl.Workbook()
        combined_wb.remove(combined_wb.active)  # Remove default blank sheet

        for target_owner, matcher in owner_matchers.items():
            matched_rows_by_sheet: Dict[str, List[Dict[str, Any]]] = {}
            total_matched = 0
            headers_used: List[str] = []

            for sheet_name, sheet_info in sheets.items():
                col_map = sheet_info.get("col_map", {})
                owner_col_idx = col_map.get("owner")
                headers = sheet_info.get("headers", [])
                if not headers_used:
                    headers_used = headers

                matching_sheet_rows: List[Dict[str, Any]] = []
                for row_dict in sheet_info.get("rows", []):
                    owner_val = None
                    if owner_col_idx is not None and owner_col_idx < len(headers):
                        owner_val = row_dict.get(headers[owner_col_idx])
                    
                    if owner_val is None:
                        for k, v in row_dict.items():
                            if any(a in str(k).lower() for a in self._OWNER_ALIASES):
                                owner_val = v
                                break

                    if owner_val is not None and matcher.search(str(owner_val)):
                        matching_sheet_rows.append(row_dict)

                if matching_sheet_rows:
                    matched_rows_by_sheet[sheet_name] = matching_sheet_rows
                    total_matched += len(matching_sheet_rows)

            if total_matched == 0:
                owner_results[target_owner] = {
                    "found": False,
                    "row_count": 0,
                    "rows": [],
                    "message": f"No tasks found for owner '{target_owner}' in the uploaded workbook."
                }
                continue

            all_target_rows = [r for rows in matched_rows_by_sheet.values() for r in rows]
            total_est_hours = 0.0
            modules_found = set()
            statuses_count: Dict[str, int] = {}

            for r in all_target_rows:
                for k, v in r.items():
                    if any(a in str(k).lower() for a in self._HOURS_ALIASES):
                        try:
                            total_est_hours += float(str(v).replace("h", "").replace("hrs", "").strip())
                        except (ValueError, TypeError):
                            pass
                    if any(a in str(k).lower() for a in self._MODULE_ALIASES):
                        if v:
                            modules_found.add(str(v).strip())
                    if any(a in str(k).lower() for a in self._STATUS_ALIASES):
                        if v:
                            st = str(v).strip()
                            statuses_count[st] = statuses_count.get(st, 0) + 1

            clean_owner_title = target_owner.strip().title()
            owner_filename = f"{clean_owner_title}_{base_name}.xlsx"

            single_wb = openpyxl.Workbook()
            single_wb.remove(single_wb.active)

            for s_name, s_rows in matched_rows_by_sheet.items():
                ws = single_wb.create_sheet(title=s_name[:31])
                self._write_styled_sheet(ws, headers_used, s_rows)

            if len(single_wb.sheetnames) == 0:
                ws = single_wb.create_sheet(title=clean_owner_title[:31])
                self._write_styled_sheet(ws, headers_used, all_target_rows)

            out_buf = io.BytesIO()
            single_wb.save(out_buf)
            file_bytes = out_buf.getvalue()
            single_wb.close()

            generated_files.append({
                "filename": owner_filename,
                "file_bytes": file_bytes,
                "owner": clean_owner_title,
                "row_count": total_matched,
                "type": "XLSX",
                "size_kb": round(len(file_bytes) / 1024, 1),
                "total_hours": total_est_hours,
                "modules": sorted(list(modules_found)),
                "statuses": statuses_count,
                "sample_tasks": [r.get(headers_used[1]) or list(r.values())[1] for r in all_target_rows[:4] if len(r) > 1]
            })

            comb_ws = combined_wb.create_sheet(title=clean_owner_title[:31])
            self._write_styled_sheet(comb_ws, headers_used, all_target_rows)

            owner_results[clean_owner_title] = {
                "found": True,
                "row_count": total_matched,
                "total_hours": total_est_hours,
                "modules": sorted(list(modules_found)),
                "statuses": statuses_count,
                "filename": owner_filename
            }

        if len(generated_files) >= 2:
            comb_owners_str = "_".join([g["owner"] for g in generated_files])
            combined_filename = f"Sprint_Split_{comb_owners_str}.xlsx"
            comb_buf = io.BytesIO()
            combined_wb.save(comb_buf)
            comb_bytes = comb_buf.getvalue()
            combined_wb.close()

            generated_files.append({
                "filename": combined_filename,
                "file_bytes": comb_bytes,
                "owner": "Combined",
                "row_count": sum(g["row_count"] for g in generated_files[:-1]),
                "type": "XLSX",
                "size_kb": round(len(comb_bytes) / 1024, 1),
                "is_combined": True
            })

        return {
            "success": len(generated_files) > 0,
            "generated_files": generated_files,
            "owner_results": owner_results,
            "source_file": os.path.basename(file_path),
            "total_files_generated": len(generated_files)
        }

    def _detect_columns(self, headers: List[str]) -> Dict[str, Optional[int]]:
        """Identifies column index mappings for standard project/sprint fields."""
        col_map: Dict[str, Optional[int]] = {
            "module": None,
            "task": None,
            "description": None,
            "hours": None,
            "owner": None,
            "status": None
        }

        for idx, h in enumerate(headers):
            h_clean = str(h).strip().lower()
            if col_map["owner"] is None and any(a == h_clean or a in h_clean for a in self._OWNER_ALIASES):
                col_map["owner"] = idx
            elif col_map["module"] is None and any(a == h_clean or a in h_clean for a in self._MODULE_ALIASES):
                col_map["module"] = idx
            elif col_map["task"] is None and any(a == h_clean or a in h_clean for a in self._TASK_ALIASES):
                col_map["task"] = idx
            elif col_map["description"] is None and any(a == h_clean or a in h_clean for a in self._DESC_ALIASES):
                col_map["description"] = idx
            elif col_map["hours"] is None and any(a == h_clean or a in h_clean for a in self._HOURS_ALIASES):
                col_map["hours"] = idx
            elif col_map["status"] is None and any(a == h_clean or a in h_clean for a in self._STATUS_ALIASES):
                col_map["status"] = idx

        return col_map

    def _write_styled_sheet(
        self,
        ws: openpyxl.worksheet.worksheet.Worksheet,
        headers: List[str],
        rows: List[Dict[str, Any]]
    ) -> None:
        """Writes headers and data rows with enterprise styling and auto column widths."""
        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
        header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

        data_font = Font(name="Segoe UI", size=10, color="0F172A")
        alt_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
        thin_border = Border(
            left=Side(style="thin", color="E2E8F0"),
            right=Side(style="thin", color="E2E8F0"),
            top=Side(style="thin", color="E2E8F0"),
            bottom=Side(style="thin", color="E2E8F0")
        )

        ws.row_dimensions[1].height = 28

        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            cell.border = thin_border

        for row_idx, row_dict in enumerate(rows, start=2):
            ws.row_dimensions[row_idx].height = 22
            is_alt = (row_idx % 2 == 0)

            for col_idx, header in enumerate(headers, start=1):
                val = row_dict.get(header)
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.font = data_font
                cell.border = thin_border

                if is_alt:
                    cell.fill = alt_fill

                if isinstance(val, (int, float, Decimal)):
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="center")

        for col_idx, header in enumerate(headers, start=1):
            max_len = len(str(header))
            for row_dict in rows:
                v = row_dict.get(header)
                if v is not None:
                    max_len = max(max_len, len(str(v)))

            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = min(max(max_len + 4, 14), 60)


# Global singleton instance
excel_processor = ExcelProcessor()
