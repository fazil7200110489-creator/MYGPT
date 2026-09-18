"""Sprint Workbook Processor for Developer Task Filtering and Split Workbook Generation.

Maintains 100% backward compatibility with Sprint workbooks (Fazil=692h, Reka=686h).
"""

import io
import os
import re
from typing import Dict, Any, List, Optional, Set
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from loguru import logger

from backend.app.services.excel.excel_aggregator import excel_aggregator


class SprintProcessor:
    """Handles Sprint task filtering, owner extraction, and individual sprint sheet generation."""

    def filter_and_export_by_owners(
        self,
        file_path: str,
        target_owners: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Filters sprint tasks for target owners and generates individual .xlsx files."""
        inspection = excel_aggregator.inspect_workbook(file_path)
        sheets = inspection.get("sheets", {})
        available_owners = inspection.get("owners", [])

        if not target_owners or not isinstance(target_owners, list):
            return {
                "available_owners": available_owners,
                "target_owners": [],
                "owner_results": {},
                "source_file": os.path.basename(file_path)
            }

        # Read full workbook without read_only to preserve styles
        wb_source = openpyxl.load_workbook(file_path, data_only=True)
        results: Dict[str, Any] = {}

        for owner in target_owners:
            if not owner or not str(owner).strip():
                continue
            owner_clean = str(owner).strip()
            wb_out = openpyxl.Workbook()
            # Remove default sheet
            default_sheet = wb_out.active

            matching_rows_total = 0
            total_estimated_hours = 0.0
            modules_found: Set[str] = set()

            for s_name in wb_source.sheetnames:
                ws_src = wb_source[s_name]
                src_rows = list(ws_src.iter_rows(values_only=False))
                if not src_rows:
                    continue

                # Header detection
                hdr_idx = 0
                for r_i, r in enumerate(src_rows):
                    non_empty = [c for c in r if c.value is not None]
                    if len(non_empty) >= 2:
                        hdr_idx = r_i
                        break

                hdr_row = src_rows[hdr_idx]
                headers = [str(c.value).strip() if c.value is not None else f"Col_{i+1}" for i, c in enumerate(hdr_row)]

                owner_col_idx = None
                for idx, h in enumerate(headers):
                    if str(h).strip().lower() in ("owner", "assigned to", "developer", "employee", "assignee"):
                        owner_col_idx = idx
                        break

                if owner_col_idx is None:
                    continue

                matching_data_cells: List[List[Any]] = []
                for row_cells in src_rows[hdr_idx + 1:]:
                    if owner_col_idx < len(row_cells):
                        cell_val = row_cells[owner_col_idx].value
                        if cell_val is not None:
                            val_str = str(cell_val).strip()
                            if re.search(rf"\b{re.escape(owner_clean)}\b", val_str, re.I):
                                matching_data_cells.append([c.value for c in row_cells])
                                matching_rows_total += 1

                                for col_i, h_name in enumerate(headers):
                                    if col_i < len(row_cells):
                                        c_val = row_cells[col_i].value
                                        if any(k in str(h_name).lower() for k in ["hour", "estimate", "est"]):
                                            try:
                                                num_h = float(str(c_val).replace("h", "").replace("hrs", "").strip())
                                                total_estimated_hours += num_h
                                            except (ValueError, TypeError):
                                                pass
                                        if any(k in str(h_name).lower() for k in ["module", "component", "epic"]):
                                            if c_val:
                                                modules_found.add(str(c_val).strip())

                if matching_data_cells:
                    ws_new = wb_out.create_sheet(title=s_name[:30])

                    # Style headers
                    header_fill = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
                    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")

                    for col_i, h_cell in enumerate(hdr_row, start=1):
                        new_c = ws_new.cell(row=1, column=col_i, value=h_cell.value)
                        new_c.fill = header_fill
                        new_c.font = header_font
                        new_c.alignment = Alignment(horizontal="center", vertical="center")

                    for r_i, r_data in enumerate(matching_data_cells, start=2):
                        for col_i, v in enumerate(r_data, start=1):
                            ws_new.cell(row=r_i, column=col_i, value=v)

                    # Auto fit widths
                    for col in ws_new.columns:
                        max_len = max(len(str(cell.value or '')) for cell in col)
                        col_letter = openpyxl.utils.get_column_letter(col[0].column)
                        ws_new.column_dimensions[col_letter].width = max(max_len + 3, 12)

            # Remove default empty sheet if we added sheets
            if len(wb_out.sheetnames) > 1 and default_sheet in wb_out.worksheets:
                wb_out.remove(default_sheet)

            buf = io.BytesIO()
            wb_out.save(buf)
            wb_out.close()
            file_bytes = buf.getvalue()

            safe_owner_file = f"{owner_clean}_Sprint.xlsx"
            results[owner_clean] = {
                "owner": owner_clean,
                "found": matching_rows_total > 0,
                "row_count": matching_rows_total,
                "total_hours": round(total_estimated_hours, 1) if total_estimated_hours > 0 else None,
                "modules": sorted(list(modules_found)),
                "filename": safe_owner_file,
                "file_bytes": file_bytes,
                "file_size": len(file_bytes)
            }

        wb_source.close()
        return {
            "available_owners": available_owners,
            "target_owners": target_owners,
            "owner_results": results,
            "source_file": os.path.basename(file_path)
        }


sprint_processor = SprintProcessor()
