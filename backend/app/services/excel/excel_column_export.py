"""Column Listing, Column Extraction / Export, and Full Workbook Export Service.

Reads actual column values and full workbook data from Excel files and creates verified .xlsx workbooks with preview capabilities.
Zero mock data.
"""

import io
import os
import re
from typing import Dict, Any, List, Optional
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from loguru import logger

from backend.app.services.excel.excel_aggregator import excel_aggregator
from backend.app.services.excel.excel_parser import load_workbook_safe


class ExcelColumnExport:
    """Manages column inspection, single column extraction, and full workbook export."""

    def list_columns(self, file_path: str) -> Dict[str, Any]:
        """Returns the full list of columns found in the active workbook."""
        inspection = excel_aggregator.inspect_workbook(file_path)
        headers = inspection.get("headers", [])
        total_rows = inspection.get("total_valid_rows", inspection.get("total_rows", 0))

        return {
            "columns": headers,
            "column_count": len(headers),
            "total_rows": total_rows,
            "source_file": os.path.basename(file_path),
            "workbook_type": inspection.get("workbook_type")
        }

    def export_column(
        self,
        file_path: str,
        target_column_name: str,
        output_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Extracts values of a single column (e.g., 'RID') into a clean formatted .xlsx workbook.
        Strictly verifies column existence and refuses to generate empty files.
        """
        inspection = excel_aggregator.inspect_workbook(file_path)
        sheets = inspection.get("sheets") or {}
        all_headers = [str(h).strip() for h in inspection.get("headers", []) if h is not None]

        target_clean = str(target_column_name or "").strip()
        
        # Use SemanticExcelResolver for authentic workbook header resolution
        from backend.app.services.excel.semantic_excel_resolver import semantic_excel_resolver
        matched_header = semantic_excel_resolver.resolve_column(target_clean, all_headers)
        
        if not matched_header or matched_header not in all_headers:
            # Fallback to direct inspection
            for h in all_headers:
                if h.lower() == target_clean.lower():
                    matched_header = h
                    break

        # If column cannot be verified, return failure without generating empty spreadsheet
        if not matched_header:
            return {
                "success": False,
                "error": f"I couldn't identify the requested column '{target_column_name}' in the workbook.",
                "available_columns": all_headers,
                "record_count": 0,
                "source_file": os.path.basename(file_path)
            }

        # Collect rows from sheets
        extracted_values: List[Any] = []
        for s_name, s_info in sheets.items():
            for r in s_info.get("valid_rows", []):
                val = r.get(matched_header)
                if val is not None and str(val).strip():
                    extracted_values.append(val)

        if not extracted_values:
            return {
                "success": False,
                "error": f"No data records found for column '{matched_header}'.",
                "available_columns": all_headers,
                "record_count": 0,
                "source_file": os.path.basename(file_path)
            }

        # Create output workbook using openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        clean_title = re.sub(r'[\\/*?:\[\]]', '_', matched_header or "Export")[:30]
        ws.title = clean_title

        # Styling
        header_fill = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        thin_border = Border(
            left=Side(style='thin', color='E0E0E0'),
            right=Side(style='thin', color='E0E0E0'),
            top=Side(style='thin', color='E0E0E0'),
            bottom=Side(style='thin', color='E0E0E0')
        )

        # Headers: S.No, <Column Name>
        ws.cell(row=1, column=1, value="S.No")
        ws.cell(row=1, column=2, value=matched_header)

        for col_idx in (1, 2):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")

        ws.row_dimensions[1].height = 24

        max_len = len(str(matched_header))
        preview_rows: List[Dict[str, Any]] = []
        for idx, val in enumerate(extracted_values, start=2):
            c1 = ws.cell(row=idx, column=1, value=idx - 1)
            c2 = ws.cell(row=idx, column=2, value=str(val))
            c1.alignment = Alignment(horizontal="center")
            c2.alignment = Alignment(horizontal="left")
            c1.border = thin_border
            c2.border = thin_border
            max_len = max(max_len, len(str(val)))

            if len(preview_rows) < 20:
                preview_rows.append({"S.No": idx - 1, matched_header: str(val)})

        ws.column_dimensions['A'].width = 10
        ws.column_dimensions['B'].width = max(max_len + 4, 18)

        buf = io.BytesIO()
        wb.save(buf)
        wb.close()
        file_bytes = buf.getvalue()

        safe_col = re.sub(r'[^\w\.\-]', '_', matched_header)
        safe_filename = output_filename or f"{safe_col}.xlsx"
        if not safe_filename.endswith(".xlsx"):
            safe_filename += ".xlsx"

        return {
            "success": True,
            "filename": safe_filename,
            "column_name": matched_header,
            "record_count": len(extracted_values),
            "column_count": 2,
            "columns": ["S.No", matched_header],
            "preview_rows": preview_rows,
            "file_bytes": file_bytes,
            "file_size": len(file_bytes),
            "source_file": os.path.basename(file_path)
        }

    def export_full_workbook(
        self,
        file_path: str,
        output_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Exports the entire active workbook containing all actual sheets, columns, and records.
        Preserves original rows, headers, and values.
        """
        inspection = excel_aggregator.inspect_workbook(file_path)
        sheets = inspection.get("sheets") or {}
        all_headers = [str(h).strip() for h in inspection.get("headers", []) if h is not None]
        total_rows = inspection.get("total_valid_rows", inspection.get("total_rows", 0))

        if not sheets or total_rows == 0:
            return {
                "success": False,
                "error": "No valid data records found in the uploaded workbook.",
                "record_count": 0,
                "source_file": os.path.basename(file_path)
            }

        # Create a new styled workbook with all sheets
        wb_out = openpyxl.Workbook()
        # Remove default sheet
        wb_out.remove(wb_out.active)

        header_fill = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        thin_border = Border(
            left=Side(style='thin', color='E0E0E0'),
            right=Side(style='thin', color='E0E0E0'),
            top=Side(style='thin', color='E0E0E0'),
            bottom=Side(style='thin', color='E0E0E0')
        )

        all_preview_rows: List[Dict[str, Any]] = []
        primary_columns: List[str] = []
        total_exported_records = 0

        for s_idx, (s_name, s_info) in enumerate(sheets.items()):
            clean_s_name = re.sub(r'[\\/*?:\[\]]', '_', s_name)[:30] or f"Sheet{s_idx+1}"
            ws = wb_out.create_sheet(title=clean_s_name)
            s_headers = s_info.get("headers", [])
            if not s_headers:
                s_headers = all_headers

            if s_idx == 0:
                primary_columns = s_headers

            # Write headers
            ws.row_dimensions[1].height = 24
            col_widths: Dict[int, int] = {}
            for col_idx, h_text in enumerate(s_headers, start=1):
                cell = ws.cell(row=1, column=col_idx, value=str(h_text))
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center")
                col_widths[col_idx] = max(len(str(h_text)) + 3, 12)

            # Write rows
            valid_rows = s_info.get("valid_rows", [])
            for row_idx, r_dict in enumerate(valid_rows, start=2):
                row_preview: Dict[str, Any] = {}
                for col_idx, h_text in enumerate(s_headers, start=1):
                    val = r_dict.get(h_text, "")
                    val_str = "" if val is None else str(val)
                    cell = ws.cell(row=row_idx, column=col_idx, value=val_str)
                    cell.alignment = Alignment(horizontal="left", vertical="center")
                    cell.border = thin_border
                    col_widths[col_idx] = max(col_widths.get(col_idx, 12), min(len(val_str) + 2, 40))
                    if s_idx == 0 and len(all_preview_rows) < 20:
                        row_preview[str(h_text)] = val_str

                if s_idx == 0 and len(all_preview_rows) < 20 and row_preview:
                    all_preview_rows.append(row_preview)

                total_exported_records += 1

            # Set column widths
            for c_idx, width in col_widths.items():
                col_letter = openpyxl.utils.get_column_letter(c_idx)
                ws.column_dimensions[col_letter].width = width

        buf = io.BytesIO()
        wb_out.save(buf)
        wb_out.close()
        file_bytes = buf.getvalue()

        base_name = os.path.splitext(os.path.basename(file_path))[0]
        safe_filename = output_filename or f"Full_Export_{base_name}.xlsx"
        safe_filename = re.sub(r'[^\w\.\-]', '_', safe_filename)
        if not safe_filename.endswith(".xlsx"):
            safe_filename += ".xlsx"

        return {
            "success": True,
            "filename": safe_filename,
            "record_count": total_exported_records,
            "column_count": len(primary_columns),
            "columns": primary_columns,
            "sheets": list(sheets.keys()),
            "preview_rows": all_preview_rows,
            "file_bytes": file_bytes,
            "file_size": len(file_bytes),
            "source_file": os.path.basename(file_path)
        }

    def export_filtered_workbook(
        self,
        file_path: str,
        filter_criteria: Dict[str, Any],
        output_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Exports workbook rows matching filter criteria (e.g. mode='UPI' or 'QR', min_amount=10000)."""
        inspection = excel_aggregator.inspect_workbook(file_path)
        sheets = inspection.get("sheets") or {}
        all_headers = [str(h).strip() for h in inspection.get("headers", []) if h is not None]

        target_mode = str(filter_criteria.get("mode", "")).strip().upper() if filter_criteria.get("mode") else None
        min_amount = filter_criteria.get("min_amount")
        if min_amount is not None:
            try:
                min_amount = float(min_amount)
            except Exception:
                min_amount = None

        matched_rows: List[Dict[str, Any]] = []
        preview_rows: List[Dict[str, Any]] = []

        for s_name, s_info in sheets.items():
            schema = s_info.get("schema", {})
            mode_col = schema.get("mode_column")
            amount_col = schema.get("amount_column") or "Amount"

            for r in s_info.get("valid_rows", []):
                keep = True
                if target_mode:
                    row_mode = ""
                    if mode_col and r.get(mode_col):
                        row_mode = str(r.get(mode_col)).strip().upper()
                    else:
                        for k, v in r.items():
                            if "mode" in str(k).lower() and v:
                                row_mode = str(v).strip().upper()
                                break
                    if row_mode != target_mode:
                        keep = False

                if keep and min_amount is not None:
                    row_amt = parse_decimal_safe(r.get(amount_col))
                    if row_amt is None or float(row_amt) <= min_amount:
                        keep = False

                if keep:
                    matched_rows.append(r)
                    if len(preview_rows) < 20:
                        preview_rows.append(r)

        wb_out = openpyxl.Workbook()
        ws = wb_out.active
        clean_sheet_name = f"{target_mode or 'Filtered'}_Transactions"[:30]
        ws.title = clean_sheet_name

        header_fill = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        thin_border = Border(
            left=Side(style='thin', color='E0E0E0'),
            right=Side(style='thin', color='E0E0E0'),
            top=Side(style='thin', color='E0E0E0'),
            bottom=Side(style='thin', color='E0E0E0')
        )

        ws.row_dimensions[1].height = 24
        col_widths: Dict[int, int] = {}
        for col_idx, h_text in enumerate(all_headers, start=1):
            cell = ws.cell(row=1, column=col_idx, value=str(h_text))
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            col_widths[col_idx] = max(len(str(h_text)) + 3, 12)

        for row_idx, r_dict in enumerate(matched_rows, start=2):
            for col_idx, h_text in enumerate(all_headers, start=1):
                val = r_dict.get(h_text, "")
                val_str = "" if val is None else str(val)
                cell = ws.cell(row=row_idx, column=col_idx, value=val_str)
                cell.alignment = Alignment(horizontal="left", vertical="center")
                cell.border = thin_border
                col_widths[col_idx] = max(col_widths.get(col_idx, 12), min(len(val_str) + 2, 40))

        for c_idx, width in col_widths.items():
            col_letter = openpyxl.utils.get_column_letter(c_idx)
            ws.column_dimensions[col_letter].width = width

        buf = io.BytesIO()
        wb_out.save(buf)
        wb_out.close()
        file_bytes = buf.getvalue()

        safe_filename = output_filename or (f"{target_mode}_Transactions_Report.xlsx" if target_mode else "Filtered_Transactions_Report.xlsx")
        if not safe_filename.endswith(".xlsx"):
            safe_filename += ".xlsx"

        return {
            "success": True,
            "filename": safe_filename,
            "record_count": len(matched_rows),
            "column_count": len(all_headers),
            "columns": all_headers,
            "preview_rows": preview_rows,
            "file_bytes": file_bytes,
            "file_size": len(file_bytes),
            "source_file": os.path.basename(file_path)
        }

    def export_metric_result(
        self,
        file_path: str,
        result_title: str,
        metrics_dict: Dict[str, Any],
        output_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Exports a calculated summary/metric result (e.g. Total Amount ₹25,12,180.76) into a clean, well-formatted XLSX workbook."""
        wb = openpyxl.Workbook()
        ws = wb.active
        clean_title = re.sub(r'[\\/*?:\[\]]', '_', result_title or "Summary")[:30]
        ws.title = clean_title

        header_fill = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        thin_border = Border(
            left=Side(style='thin', color='E0E0E0'),
            right=Side(style='thin', color='E0E0E0'),
            top=Side(style='thin', color='E0E0E0'),
            bottom=Side(style='thin', color='E0E0E0')
        )

        ws.cell(row=1, column=1, value="Metric / Dimension")
        ws.cell(row=1, column=2, value="Value")
        for c_idx in (1, 2):
            cell = ws.cell(row=1, column=c_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 24

        preview_rows = []
        row_idx = 2
        for k, v in metrics_dict.items():
            if v is None:
                continue
            c1 = ws.cell(row=row_idx, column=1, value=str(k))
            c2 = ws.cell(row=row_idx, column=2, value=str(v))
            c1.alignment = Alignment(horizontal="left", vertical="center")
            c2.alignment = Alignment(horizontal="right" if any(c.isdigit() for c in str(v)) else "left", vertical="center")
            c1.border = thin_border
            c2.border = thin_border
            preview_rows.append({"Metric / Dimension": str(k), "Value": str(v)})
            row_idx += 1

        ws.column_dimensions['A'].width = 30
        ws.column_dimensions['B'].width = 32

        buf = io.BytesIO()
        wb.save(buf)
        wb.close()
        file_bytes = buf.getvalue()

        safe_title = re.sub(r'[^\w\.\-]', '_', result_title)
        safe_filename = output_filename or f"{safe_title}_Result.xlsx"
        if not safe_filename.endswith(".xlsx"):
            safe_filename += ".xlsx"

        return {
            "success": True,
            "filename": safe_filename,
            "record_count": len(preview_rows),
            "column_count": 2,
            "columns": ["Metric / Dimension", "Value"],
            "preview_rows": preview_rows,
            "file_bytes": file_bytes,
            "file_size": len(file_bytes),
            "source_file": os.path.basename(file_path) if file_path else ""
        }

    def export_multi_document_summary(
        self,
        summary_payload: Dict[str, Any],
        output_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generates a professional multi-sheet Excel summary report for two reconciled workbooks."""
        wb = openpyxl.Workbook()
        ws_overview = wb.active
        ws_overview.title = "Summary Overview"

        header_fill = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        section_fill = PatternFill(start_color="E8EEF5", end_color="E8EEF5", fill_type="solid")
        section_font = Font(name="Calibri", size=11, bold=True, color="1E3A5F")
        thin_border = Border(
            left=Side(style='thin', color='D0D7DE'),
            right=Side(style='thin', color='D0D7DE'),
            top=Side(style='thin', color='D0D7DE'),
            bottom=Side(style='thin', color='D0D7DE')
        )

        # Sheet 1: Overview
        file_a_name = summary_payload.get("file_a_name", "Document A")
        file_b_name = summary_payload.get("file_b_name", "Document B")
        headers = ["Dimension / Metric", f"File A ({file_a_name[:20]})", f"File B ({file_b_name[:20]})", "Combined / Status"]
        for col_idx, h_text in enumerate(headers, start=1):
            cell = ws_overview.cell(row=1, column=col_idx, value=h_text)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
        ws_overview.row_dimensions[1].height = 25

        rows = summary_payload.get("overview_rows", [])
        for r_idx, row_data in enumerate(rows, start=2):
            for c_idx, val in enumerate(row_data, start=1):
                cell = ws_overview.cell(row=r_idx, column=c_idx, value=str(val) if val is not None else "")
                cell.border = thin_border
                cell.alignment = Alignment(horizontal="right" if c_idx > 1 and any(c.isdigit() for c in str(val)) else "left", vertical="center")
                if c_idx == 1 and not row_data[1] and not row_data[2]:
                    cell.fill = section_fill
                    cell.font = section_font

        ws_overview.column_dimensions['A'].width = 32
        ws_overview.column_dimensions['B'].width = 28
        ws_overview.column_dimensions['C'].width = 28
        ws_overview.column_dimensions['D'].width = 28

        # Sheet 2: Highest Transactions
        ws_max = wb.create_sheet(title="Highest Transactions")
        max_headers = ["Attribute", "Details"]
        for col_idx, h_text in enumerate(max_headers, start=1):
            cell = ws_max.cell(row=1, column=col_idx, value=h_text)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
        ws_max.row_dimensions[1].height = 25

        max_rows = summary_payload.get("max_rows", [])
        for r_idx, (k, v) in enumerate(max_rows, start=2):
            c1 = ws_max.cell(row=r_idx, column=1, value=str(k))
            c2 = ws_max.cell(row=r_idx, column=2, value=str(v))
            c1.border = thin_border
            c2.border = thin_border
            c1.alignment = Alignment(horizontal="left", vertical="center")
            c2.alignment = Alignment(horizontal="left", vertical="center")

        ws_max.column_dimensions['A'].width = 30
        ws_max.column_dimensions['B'].width = 45

        # Sheet 3: Bank & Mode Info
        ws_info = wb.create_sheet(title="Bank & Mode Details")
        info_headers = ["Category", "Information / Values"]
        for col_idx, h_text in enumerate(info_headers, start=1):
            cell = ws_info.cell(row=1, column=col_idx, value=h_text)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
        ws_info.row_dimensions[1].height = 25

        info_rows = summary_payload.get("info_rows", [])
        for r_idx, (k, v) in enumerate(info_rows, start=2):
            c1 = ws_info.cell(row=r_idx, column=1, value=str(k))
            c2 = ws_info.cell(row=r_idx, column=2, value=str(v))
            c1.border = thin_border
            c2.border = thin_border
            c1.alignment = Alignment(horizontal="left", vertical="center")
            c2.alignment = Alignment(horizontal="left", vertical="center")

        ws_info.column_dimensions['A'].width = 30
        ws_info.column_dimensions['B'].width = 50

        buf = io.BytesIO()
        wb.save(buf)
        wb.close()
        file_bytes = buf.getvalue()

        safe_filename = output_filename or "Multi_Document_Summary_Report.xlsx"
        if not safe_filename.endswith(".xlsx"):
            safe_filename += ".xlsx"

        return {
            "success": True,
            "filename": safe_filename,
            "record_count": len(rows),
            "column_count": 4,
            "columns": headers,
            "sheets": ["Summary Overview", "Highest Transactions", "Bank & Mode Details"],
            "preview_rows": [{"Metric": r[0], "File A": r[1] if len(r) > 1 else "", "File B": r[2] if len(r) > 2 else "", "Combined": r[3] if len(r) > 3 else ""} for r in rows[:15]],
            "file_bytes": file_bytes,
            "file_size": len(file_bytes)
        }

    def export_table_result(
        self,
        headers: List[str],
        rows: List[Dict[str, Any]],
        title: str = "Table Export",
        output_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Exports tabular data (such as group aggregations or discrepancy lists) to an Excel workbook."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = re.sub(r'[\\/*?:\[\]]', '_', title)[:30]

        header_fill = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        thin_border = Border(
            left=Side(style='thin', color='D0D7DE'),
            right=Side(style='thin', color='D0D7DE'),
            top=Side(style='thin', color='D0D7DE'),
            bottom=Side(style='thin', color='D0D7DE')
        )

        for col_idx, h_text in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col_idx, value=str(h_text))
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 24

        col_widths = {c_idx: len(str(h)) + 4 for c_idx, h in enumerate(headers, start=1)}
        for r_idx, row_dict in enumerate(rows, start=2):
            for c_idx, h_text in enumerate(headers, start=1):
                val = row_dict.get(h_text, "")
                val_str = "" if val is None else str(val)
                cell = ws.cell(row=r_idx, column=c_idx, value=val_str)
                cell.border = thin_border
                cell.alignment = Alignment(horizontal="right" if any(c.isdigit() for c in val_str) else "left", vertical="center")
                col_widths[c_idx] = max(col_widths.get(c_idx, 12), min(len(val_str) + 2, 40))

        for c_idx, width in col_widths.items():
            col_letter = openpyxl.utils.get_column_letter(c_idx)
            ws.column_dimensions[col_letter].width = width

        buf = io.BytesIO()
        wb.save(buf)
        wb.close()
        file_bytes = buf.getvalue()

        safe_filename = output_filename or f"{re.sub(r'[^\w\.\-]', '_', title)}_Export.xlsx"
        if not safe_filename.endswith(".xlsx"):
            safe_filename += ".xlsx"

        return {
            "success": True,
            "filename": safe_filename,
            "record_count": len(rows),
            "column_count": len(headers),
            "columns": headers,
            "preview_rows": rows[:15],
            "file_bytes": file_bytes,
            "file_size": len(file_bytes)
        }

    def export_filtered_rows(
        self,
        file_path: str,
        rows: List[Dict[str, Any]],
        headers: Optional[List[str]] = None,
        target_columns: Optional[List[str]] = None,
        output_filename: Optional[str] = None,
        sheet_title: Optional[str] = None
    ) -> Dict[str, Any]:
        """Exports a list of row dicts into a formatted .xlsx workbook, optionally restricted to target_columns."""
        if not rows:
            return {
                "success": False,
                "error": "No matching records found to export.",
                "record_count": 0,
                "source_file": os.path.basename(file_path)
            }

        # Determine columns to include
        if target_columns and isinstance(target_columns, list) and len(target_columns) > 0 and str(target_columns[0]).upper() != "ALL":
            active_cols = target_columns
        elif headers:
            active_cols = headers
        else:
            active_cols = list(rows[0].keys())

        wb_out = openpyxl.Workbook()
        ws = wb_out.active
        clean_sheet_name = re.sub(r'[\\/*?:\[\]]', '_', sheet_title or "Export")[:30]
        ws.title = clean_sheet_name

        header_fill = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        thin_border = Border(
            left=Side(style='thin', color='E0E0E0'),
            right=Side(style='thin', color='E0E0E0'),
            top=Side(style='thin', color='E0E0E0'),
            bottom=Side(style='thin', color='E0E0E0')
        )

        ws.row_dimensions[1].height = 24
        col_widths: Dict[int, int] = {}
        for col_idx, h_text in enumerate(active_cols, start=1):
            cell = ws.cell(row=1, column=col_idx, value=str(h_text))
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            col_widths[col_idx] = max(len(str(h_text)) + 3, 12)

        preview_rows: List[Dict[str, Any]] = []
        for row_idx, r_dict in enumerate(rows, start=2):
            row_preview: Dict[str, Any] = {}
            for col_idx, h_text in enumerate(active_cols, start=1):
                val = r_dict.get(h_text, "")
                val_str = "" if val is None else str(val)
                cell = ws.cell(row=row_idx, column=col_idx, value=val_str)
                cell.alignment = Alignment(horizontal="left", vertical="center")
                cell.border = thin_border
                col_widths[col_idx] = max(col_widths.get(col_idx, 12), min(len(val_str) + 2, 40))
                if len(preview_rows) < 20:
                    row_preview[str(h_text)] = val_str
            if len(preview_rows) < 20 and row_preview:
                preview_rows.append(row_preview)

        for c_idx, width in col_widths.items():
            col_letter = openpyxl.utils.get_column_letter(c_idx)
            ws.column_dimensions[col_letter].width = width

        buf = io.BytesIO()
        wb_out.save(buf)
        wb_out.close()
        file_bytes = buf.getvalue()

        safe_filename = output_filename or "Filtered_Records.xlsx"
        if not safe_filename.endswith(".xlsx"):
            safe_filename += ".xlsx"

        return {
            "success": True,
            "filename": safe_filename,
            "record_count": len(rows),
            "column_count": len(active_cols),
            "columns": active_cols,
            "preview_rows": preview_rows,
            "file_bytes": file_bytes,
            "file_size": len(file_bytes),
            "source_file": os.path.basename(file_path)
        }


excel_column_export = ExcelColumnExport()
