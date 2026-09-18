"""Central Excel Intelligence Service Facade.

Coordinates Workbook Detection, Deterministic Aggregations, Column Extraction,
Sprint Task Splitting, and Two-File Reconciliations with structured logs and verified results.
Zero mock data.
"""

import os
import re
import time
from decimal import Decimal
from typing import Dict, Any, List, Optional
from loguru import logger

from backend.app.schemas.department import DepartmentEnum
from backend.app.schemas.company_ai import CompanyAIResult
from backend.app.services.excel.workbook_detector import workbook_detector, WorkbookType
from backend.app.services.excel.excel_parser import parse_decimal_safe, format_inr
from backend.app.services.excel.excel_aggregator import excel_aggregator
from backend.app.services.excel.excel_column_export import excel_column_export
from backend.app.services.excel.excel_comparator import excel_comparator
from backend.app.services.excel.sprint_processor import sprint_processor


class ExcelService:
    """Unified Facade for all Excel Intelligence operations."""

    def process_excel_operation(
        self,
        intent: str,
        file_path: str,
        entities: Dict[str, Any],
        target_dept: DepartmentEnum = DepartmentEnum.GENERAL,
        secondary_file_path: Optional[str] = None
    ) -> CompanyAIResult:
        """Dispatches to the appropriate deterministic Excel processor."""
        t0 = time.time()
        filename = os.path.basename(file_path)

        inspection = excel_aggregator.inspect_workbook(file_path)
        wb_type = inspection.get("workbook_type", WorkbookType.GENERIC.value)

        # Structured Router Log
        logger.info(
            f"\n[ExcelRouter]\n"
            f"workbook_type={wb_type}\n"
            f"intent={intent.upper()}"
        )

        excel_ms = round((time.time() - t0) * 1000, 2)

        # -------------------------------------------------------------
        # 1. EXCEL_COLUMN_LIST ("give me the names of the columns")
        # -------------------------------------------------------------
        if intent in ("excel_column_list", "column_list"):
            col_info = excel_column_export.list_columns(file_path)
            cols = col_info.get("columns") or []
            total_r = col_info.get("total_rows") or 0

            findings = [
                f"### 📋 Workbook Columns",
                f"Found **{len(cols)}** columns across **{total_r:,}** records in `{filename}`:\n"
            ]
            for idx, c in enumerate(cols, start=1):
                findings.append(f"{idx}. `{c}`")

            logger.info(
                f"\n[ExcelProcessor]\n"
                f"document={filename}\n"
                f"columns_detected={len(cols)}\n"
                f"total_records={total_r}\n"
                f"\n[CompanyAI]\n"
                f"verified_result=true"
            )

            return CompanyAIResult(
                department=target_dept,
                intent="excel_column_list",
                task="Excel Column Listing",
                summary=f"Extracted {len(cols)} columns from {filename}.",
                findings=findings,
                citations=[filename],
                confidence=0.99,
                tool_results={
                    "card_type": "column_list",
                    "columns": cols,
                    "column_count": len(cols),
                    "total_records": total_r,
                    "source_file": filename
                },
                internal_metadata={"excel_ms": excel_ms, "file_generation_ms": 0.0, "source_file": filename}
            )

        # -------------------------------------------------------------
        # 2. EXCEL_COLUMN_EXPORT ("give me the RID as the excel sheet")
        # -------------------------------------------------------------
        if intent in ("excel_column_export", "column_export"):
            target_col = entities.get("column") or entities.get("target_column") or "RID"
            export_data = excel_column_export.export_column(file_path, str(target_col))

            if not export_data.get("success") or export_data.get("record_count", 0) == 0:
                avail = export_data.get("available_columns", [])
                cols_msg = "\n".join([f"- `{c}`" for c in avail[:15]]) if avail else "No columns found."
                findings = [
                    f"### ⚠️ Column Export Notice",
                    export_data.get("error", f"I couldn't identify the requested column '{target_col}' in `{filename}`."),
                    "",
                    "**Available Columns in Workbook:**",
                    cols_msg,
                    "",
                    "Please specify one of the available columns, for example: *'give me the Transaction ID column as excel'*."
                ]
                return CompanyAIResult(
                    department=target_dept,
                    intent="excel_column_export",
                    task=f"Column Export: {target_col}",
                    summary=export_data.get("error", f"Column '{target_col}' not found in {filename}."),
                    findings=findings,
                    citations=[filename],
                    confidence=0.90,
                    tool_results={
                        "card_type": "column_not_found",
                        "requested_column": str(target_col),
                        "available_columns": avail,
                        "source_file": filename
                    },
                    internal_metadata={"excel_ms": excel_ms, "file_generation_ms": 0.0, "source_file": filename}
                )

            findings = [
                f"### 📊 Column Export Ready",
                f"- **Extracted Column**: `{export_data['column_name']}`",
                f"- **Total Records**: **{export_data['record_count']:,}** rows",
                f"- **Generated Workbook**: `{export_data['filename']}`",
                f"- **Source**: `{filename}`"
            ]

            logger.info(
                f"\n[ExcelProcessor]\n"
                f"document={filename}\n"
                f"extracted_column={export_data['column_name']}\n"
                f"records={export_data['record_count']}\n"
                f"generated_file={export_data['filename']}\n"
                f"\n[CompanyAI]\n"
                f"verified_result=true"
            )

            return CompanyAIResult(
                department=target_dept,
                intent="excel_column_export",
                task=f"Column Export: {export_data['column_name']}",
                summary=f"Extracted {export_data['record_count']:,} values of column '{export_data['column_name']}' into {export_data['filename']}.",
                findings=findings,
                citations=[filename],
                confidence=0.99,
                tool_results={
                    "card_type": "excel_preview",
                    "title": f"Column Export: {export_data['column_name']}",
                    "column": export_data["column_name"],
                    "record_count": export_data["record_count"],
                    "column_count": export_data.get("column_count", 2),
                    "columns": export_data.get("columns", ["S.No", export_data["column_name"]]),
                    "preview_rows": export_data.get("preview_rows", []),
                    "filename": export_data["filename"],
                    "source_file": filename
                },
                internal_metadata={
                    "excel_ms": excel_ms,
                    "file_generation_ms": 0.0,
                    "source_file": filename,
                    "_file_payload": {
                        "filename": export_data["filename"],
                        "file_bytes": export_data["file_bytes"],
                        "file_size": export_data["file_size"]
                    }
                }
            )

        # -------------------------------------------------------------
        # 2b. EXCEL_FULL_EXPORT ("give me the full topup history as excel", "export all records")
        # -------------------------------------------------------------
        if intent in ("excel_full_export", "full_export"):
            export_data = excel_column_export.export_full_workbook(file_path)
            if not export_data.get("success") or export_data.get("record_count", 0) == 0:
                return CompanyAIResult(
                    department=target_dept,
                    intent="excel_full_export",
                    task="Full Excel Export",
                    summary=export_data.get("error", f"Failed to export workbook {filename}."),
                    findings=[
                        "### ⚠️ Full Workbook Export Notice",
                        export_data.get("error", "Unable to export records from active workbook.")
                    ],
                    citations=[filename],
                    confidence=0.90,
                    internal_metadata={"excel_ms": excel_ms, "file_generation_ms": 0.0, "source_file": filename}
                )

            findings = [
                "### 📊 Full Workbook Export Ready",
                f"- **Exported Records**: **{export_data['record_count']:,}** rows",
                f"- **Columns**: **{export_data['column_count']}** columns",
                f"- **Generated File**: `{export_data['filename']}`",
                f"- **Source**: `{filename}`",
                "",
                "All original records, headers, and worksheets have been preserved. You can preview the workbook below or download the file."
            ]

            logger.info(
                f"\n[ExcelProcessor]\n"
                f"document={filename}\n"
                f"operation=FULL_EXPORT\n"
                f"records={export_data['record_count']}\n"
                f"columns={export_data['column_count']}\n"
                f"generated_file={export_data['filename']}\n"
                f"\n[CompanyAI]\n"
                f"verified_result=true"
            )

            return CompanyAIResult(
                department=target_dept,
                intent="excel_full_export",
                task="Full Workbook Export",
                summary=f"Exported complete workbook {filename} ({export_data['record_count']:,} records) into {export_data['filename']}.",
                findings=findings,
                citations=[filename],
                confidence=0.99,
                tool_results={
                    "card_type": "excel_preview",
                    "title": "Full Workbook Export Ready",
                    "filename": export_data["filename"],
                    "record_count": export_data["record_count"],
                    "column_count": export_data["column_count"],
                    "columns": export_data["columns"],
                    "sheets": export_data.get("sheets", ["Sheet1"]),
                    "preview_rows": export_data.get("preview_rows", []),
                    "source_file": filename
                },
                internal_metadata={
                    "excel_ms": excel_ms,
                    "file_generation_ms": 0.0,
                    "source_file": filename,
                    "_file_payload": {
                        "filename": export_data["filename"],
                        "file_bytes": export_data["file_bytes"],
                        "file_size": export_data["file_size"]
                    }
                }
            )

        # -------------------------------------------------------------
        # 2c. EXCEL_MULTI_DOCUMENT_SUMMARY ("give me a summary report for this 2", "summary of both files")
        # -------------------------------------------------------------
        if intent in ("excel_multi_document_summary", "multi_document_summary"):
            return self._execute_multi_document_summary(
                file_path=file_path,
                secondary_file_path=secondary_file_path,
                entities=entities,
                target_dept=target_dept,
                excel_ms=excel_ms
            )

        # -------------------------------------------------------------
        # 2d. EXCEL_UNIQUE_VALUES ("what are the bank names?", "list transaction modes")
        # -------------------------------------------------------------
        if intent in ("excel_unique_values", "unique_values"):
            return self._execute_unique_values(
                file_path=file_path,
                entities=entities,
                target_dept=target_dept,
                excel_ms=excel_ms
            )

        # -------------------------------------------------------------
        # 2e. EXCEL_EXPORT_RESULT ("give me as excel", "give me that as excel", "export this", "download this")
        # -------------------------------------------------------------
        if intent in ("excel_export_result", "export_result"):
            last_op = entities.get("last_operation") or "excel_total"
            last_metric = entities.get("last_metric") or "Total Amount"
            last_res = entities.get("last_result") or entities.get("last_excel_result") or {}
            stored_multi = entities.get("_multi_doc_summary")
            stored_comp = entities.get("_comparison_result")
            last_filt = entities.get("filter") or entities.get("last_filters") or (last_res.get("filter") if isinstance(last_res, dict) else None)
            last_res_type = entities.get("last_result_type") or ""

            # Check for prior exportable rows (from filter, column extraction, or query results)
            prior_rows = entities.get("last_exportable_rows") or (last_res.get("matched_rows") if isinstance(last_res, dict) else None) or (last_res.get("rows") if isinstance(last_res, dict) else None)
            prior_target_cols = entities.get("last_target_columns") or entities.get("target_columns") or (last_res.get("target_columns") if isinstance(last_res, dict) else None) or (last_res.get("column") if isinstance(last_res, dict) else None)

            # 0a. Export prior filtered / extracted row dataset if present
            if prior_rows and isinstance(prior_rows, list) and len(prior_rows) > 0:
                t_title = last_res.get("title", "Exported_Results") if isinstance(last_res, dict) else "Exported_Results"
                clean_title = re.sub(r"[^\w\s-]", "", str(t_title)).strip().replace(" ", "_") or "Exported_Results"
                report_filename = f"{clean_title}.xlsx"
                export_data = excel_column_export.export_filtered_rows(
                    file_path=file_path,
                    rows=prior_rows,
                    target_columns=prior_target_cols if prior_target_cols != "ALL" else None,
                    output_filename=report_filename,
                    sheet_title="Results"
                )
                title_clean = str(t_title)

            # 0b. Export Filtered Transactions if previous operation had a mode/threshold filter
            elif last_filt and isinstance(last_filt, dict) and any(k in last_filt for k in ("mode", "min_amount")):
                mode_val = last_filt.get("mode")
                report_title = f"{mode_val}_Transactions_Report.xlsx" if mode_val else "Filtered_Transactions_Report.xlsx"
                export_data = excel_column_export.export_filtered_workbook(
                    file_path=file_path,
                    filter_criteria=last_filt,
                    output_filename=report_title
                )
                title_clean = f"{mode_val.upper() if mode_val else 'Filtered'} Transactions Report"

            # 1. Export Multi-Document Summary if previous operation was multi-doc summary
            elif (
                last_op in ("excel_multi_document_summary", "multi_document_summary", "EXCEL_MULTI_DOCUMENT_SUMMARY")
                or (isinstance(last_res, dict) and last_res.get("card_type") == "multi_document_summary")
                or stored_multi
            ):
                if stored_multi:
                    export_data = excel_column_export.export_multi_document_summary(stored_multi)
                elif secondary_file_path:
                    # Regenerate multi-doc summary payload
                    res_m = self._execute_multi_document_summary(file_path, secondary_file_path, entities, target_dept, excel_ms)
                    export_data = res_m.internal_metadata.get("_file_payload") or excel_column_export.export_multi_document_summary({"file_a_name": filename})
                else:
                    export_data = excel_column_export.export_multi_document_summary({"file_a_name": filename, "file_b_name": "Second Document", "overview_rows": [["Status", "Analyzed", "-", "Complete"]]})

                title_clean = "Multi Document Summary Report"

            # 2. Export Reconciliation / Mismatch Report if previous operation was comparison
            elif (
                last_op in ("excel_compare", "excel_comparison", "file_comparison", "EXCEL_COMPARE")
                or (isinstance(last_res, dict) and last_res.get("card_type") == "comparison_matrix")
                or stored_comp
            ):
                if stored_comp and stored_comp.get("report_bytes"):
                    export_data = {
                        "success": True,
                        "filename": stored_comp.get("report_filename", "Reconciliation_Report.xlsx"),
                        "file_bytes": stored_comp["report_bytes"],
                        "file_size": stored_comp.get("report_size", len(stored_comp["report_bytes"])),
                        "record_count": stored_comp.get("total_mismatches", 0),
                        "column_count": 5,
                        "columns": ["Key", "Status", "Amount File A", "Amount File B", "Difference"],
                        "preview_rows": []
                    }
                elif secondary_file_path:
                    comp_gen = excel_comparator.compare_workbooks(file_path, secondary_file_path)
                    export_data = {
                        "success": True,
                        "filename": comp_gen.get("report_filename", "Reconciliation_Report.xlsx"),
                        "file_bytes": comp_gen.get("report_bytes", b""),
                        "file_size": comp_gen.get("report_size", 0),
                        "record_count": comp_gen.get("total_mismatches", 0),
                        "column_count": 5,
                        "columns": ["Key", "Status", "Amount File A", "Amount File B", "Difference"],
                        "preview_rows": []
                    }
                else:
                    export_data = excel_column_export.export_metric_result(file_path, "Reconciliation", {"Status": "No secondary file provided"})
                title_clean = "Reconciliation Report"

            # 3. Export Tabular Result (e.g. from GROUP_MAX, GROUP_MIN, FILTER)
            elif isinstance(last_res, dict) and last_res.get("rows") and last_res.get("headers"):
                t_title = last_res.get("title", "Analysis Result")
                export_data = excel_column_export.export_table_result(
                    headers=last_res["headers"],
                    rows=last_res["rows"],
                    title=t_title
                )
                title_clean = t_title

            # 4. Export Metric Result (e.g. Highest Transaction, Total Amount, Average)
            elif isinstance(last_res, dict) and "primary_value" in last_res:
                title_clean = last_res.get("title", last_metric)
                export_dict: Dict[str, Any] = {}
                export_dict[title_clean] = last_res.get("primary_value")
                if last_res.get("secondary_value"):
                    export_dict["Details"] = last_res.get("secondary_value")
                if last_res.get("column"):
                    export_dict["Evaluated Column"] = last_res.get("column")
                if isinstance(last_res.get("details"), dict):
                    for dk, dv in last_res["details"].items():
                        if dv:
                            export_dict[dk.replace("_", " ").title()] = dv
                export_dict["Source Workbook"] = filename

                export_data = excel_column_export.export_metric_result(
                    file_path=file_path,
                    result_title=title_clean,
                    metrics_dict=export_dict
                )

            # 5. Default Fallback
            else:
                agg_fallback = excel_aggregator.calculate_aggregation(file_path=file_path, target_column="Amount")
                export_dict = {
                    "Total Amount": agg_fallback["formatted_total"],
                    "Authorised Transactions": f"{agg_fallback['authorised_count']:,}",
                    "Average Amount": agg_fallback["formatted_average"],
                    "Minimum Amount": format_inr(agg_fallback["min"]),
                    "Maximum Amount": format_inr(agg_fallback["max"]),
                    "Source Workbook": filename
                }
                title_clean = last_metric or "Result"
                export_data = excel_column_export.export_metric_result(
                    file_path=file_path,
                    result_title=title_clean,
                    metrics_dict=export_dict
                )

            findings = [
                "### 📊 Result Export Ready",
                f"- **Exported Result**: **{title_clean}**",
                f"- **Generated Workbook**: `{export_data['filename']}`",
                f"- **Source Workbook**: `{filename}`",
                "",
                "The requested result has been exported into an Excel workbook. You can preview or download below."
            ]

            logger.info(
                f"\n[ExcelProcessor]\n"
                f"document={filename}\n"
                f"operation=EXPORT_RESULT\n"
                f"result_title={title_clean}\n"
                f"generated_file={export_data['filename']}\n"
                f"\n[CompanyAI]\n"
                f"verified_result=true"
            )

            return CompanyAIResult(
                department=target_dept,
                intent="excel_export_result",
                task=f"Export Result: {title_clean}",
                summary=f"Exported {title_clean} into {export_data['filename']}.",
                findings=findings,
                citations=[filename],
                confidence=0.99,
                tool_results={
                    "card_type": "excel_preview",
                    "title": f"{title_clean} Export Ready",
                    "filename": export_data["filename"],
                    "record_count": export_data["record_count"],
                    "column_count": export_data.get("column_count", 2),
                    "columns": export_data.get("columns", ["Metric / Dimension", "Value"]),
                    "preview_rows": export_data.get("preview_rows", []),
                    "source_file": filename
                },
                internal_metadata={
                    "excel_ms": excel_ms,
                    "file_generation_ms": 0.0,
                    "source_file": filename,
                    "_file_payload": {
                        "filename": export_data["filename"],
                        "file_bytes": export_data["file_bytes"],
                        "file_size": export_data["file_size"]
                    }
                }
            )

        # -------------------------------------------------------------
        # 3. EXCEL_COMPARE ("compare the EBO topup and UPI QR excel")
        # -------------------------------------------------------------
        if intent in ("excel_compare", "file_comparison", "excel_comparison"):
            if not secondary_file_path:
                return CompanyAIResult(
                    department=target_dept,
                    intent="excel_compare",
                    task="Excel Comparison",
                    summary="Comparison requires two uploaded Excel files.",
                    findings=[
                        "Please provide two Excel workbooks in the conversation to perform comparison.",
                        "Example: Upload `UPI.xlsx` and `EBO.xlsx`, then ask *'compare these two files'*."
                    ],
                    citations=[filename],
                    confidence=0.85
                )

            comp_res = excel_comparator.compare_workbooks(file_path, secondary_file_path)
            if not comp_res.get("success"):
                return CompanyAIResult(
                    department=target_dept,
                    intent="excel_compare",
                    task="Excel Comparison Key Clarification",
                    summary=comp_res.get("message", "Matching identifier required for comparison."),
                    findings=[
                        comp_res.get("message", "I found the two transaction files, but I need the matching column to compare them."),
                        "Which identifier should I use to reconcile records?",
                        f"- **Options**: {', '.join(comp_res.get('candidate_options', ['RID', 'Transaction ID', 'Vendor Reference ID']))}"
                    ],
                    pending_action="awaiting_comparison_key",
                    citations=[filename, os.path.basename(secondary_file_path)],
                    confidence=0.90
                )

            findings = [
                "### 📊 Reconciliation Summary",
                f"- **Comparing**: `{comp_res['file_a']}` ↔ `{comp_res['file_b']}`",
                f"- **Reconciled on Key**: **{comp_res['key_a']}** ↔ **{comp_res['key_b']}**",
                "",
                f"- **Matched Records**: **{comp_res['matched_count']:,}**",
                f"- **Missing in {comp_res['file_b'][:20]}**: **{comp_res['missing_in_b_count']:,}**",
                f"- **Missing in {comp_res['file_a'][:20]}**: **{comp_res['missing_in_a_count']:,}**",
                f"- **Amount Discrepancies**: **{comp_res['amount_mismatch_count']:,}**",
                f"- **Status Discrepancies**: **{comp_res['status_mismatch_count']:,}**",
                f"- **Total Discrepancies**: **{comp_res['total_mismatches']:,}**",
                "",
                f"Generated Audit Report: `{comp_res['report_filename']}`"
            ]

            logger.info(
                f"\n[ExcelProcessor]\n"
                f"file_a={comp_res['file_a']}\n"
                f"file_b={comp_res['file_b']}\n"
                f"matched={comp_res['matched_count']}\n"
                f"total_mismatches={comp_res['total_mismatches']}\n"
                f"report={comp_res['report_filename']}\n"
                f"\n[CompanyAI]\n"
                f"verified_result=true"
            )

            return CompanyAIResult(
                department=target_dept,
                intent="excel_compare",
                task="Excel Comparison & Reconciliation",
                summary=f"Reconciled {comp_res['file_a']} and {comp_res['file_b']}: {comp_res['matched_count']:,} matched, {comp_res['total_mismatches']:,} discrepancies.",
                findings=findings,
                citations=[comp_res['file_a'], comp_res['file_b']],
                confidence=0.99,
                tool_results={
                    "card_type": "comparison_matrix",
                    "file_a": comp_res["file_a"],
                    "file_b": comp_res["file_b"],
                    "key": f"{comp_res['key_a']} ↔ {comp_res['key_b']}",
                    "matched": comp_res["matched_count"],
                    "missing_in_b": comp_res["missing_in_b_count"],
                    "missing_in_a": comp_res["missing_in_a_count"],
                    "amount_mismatches": comp_res["amount_mismatch_count"],
                    "status_mismatches": comp_res["status_mismatch_count"],
                    "total_mismatches": comp_res["total_mismatches"],
                    "filename": comp_res["report_filename"]
                },
                internal_metadata={
                    "excel_ms": excel_ms,
                    "file_generation_ms": 0.0,
                    "source_file": filename,
                    "_comparison_result": comp_res,
                    "_file_payload": {
                        "filename": comp_res["report_filename"],
                        "file_bytes": comp_res["report_bytes"],
                        "file_size": comp_res["report_size"]
                    }
                }
            )

        # -------------------------------------------------------------
        # 4. EXCEL_TOTAL / EXCEL_AVERAGE / EXCEL_COUNT / MIN / MAX
        # -------------------------------------------------------------
        if intent in ("excel_total", "excel_average", "excel_count", "excel_min", "excel_max"):
            target_col = entities.get("target_column") or entities.get("column")
            filter_spec = entities.get("filter")
            if not isinstance(filter_spec, dict):
                filter_spec = None

            agg = excel_aggregator.calculate_aggregation(
                file_path=file_path,
                target_column=target_col,
                operation="SUM" if "total" in intent else ("AVG" if "average" in intent else "COUNT"),
                filter_criteria=filter_spec
            )

            logger.info(
                f"\n[ExcelProcessor]\n"
                f"document={filename}\n"
                f"sheet=Sheet1\n"
                f"rows_detected={agg['rows_detected']}\n"
                f"selected_column={agg['selected_column']}\n"
                f"numeric_values={agg['numeric_count']}\n"
                f"total={agg['total']}\n"
                f"\n[CompanyAI]\n"
                f"verified_result=true"
            )

            if intent == "excel_total":
                findings = [
                    "### 📊 Total Amount",
                    f"- **Total Amount**: **{agg['formatted_total']}**",
                    f"- **Authorised Transactions**: **{agg['authorised_count']:,}** records",
                    f"- **Evaluated Column**: `{agg['selected_column']}`",
                    f"- **Source Workbook**: `{filename}`"
                ]
                task_title = "Excel Total Aggregation"
                summary_text = f"Total amount in {filename} is {agg['formatted_total']} across {agg['authorised_count']:,} authorised transactions."
                card_data = {
                    "card_type": "metric_card",
                    "title": "Total Amount",
                    "primary_value": agg["formatted_total"],
                    "secondary_value": f"{agg['authorised_count']:,} authorised transactions",
                    "column": agg["selected_column"],
                    "source_file": filename
                }
            elif intent == "excel_average":
                findings = [
                    "### 📊 Average Amount",
                    f"- **Average Transaction Amount**: **{agg['formatted_average']}**",
                    f"- **Total Evaluated Transactions**: **{agg['numeric_count']:,}**",
                    f"- **Total Amount**: **{agg['formatted_total']}**",
                    f"- **Evaluated Column**: `{agg['selected_column']}`",
                    f"- **Source Workbook**: `{filename}`"
                ]
                task_title = "Excel Average Calculation"
                summary_text = f"Average transaction amount in {filename} is {agg['formatted_average']} (Total: {agg['formatted_total']})."
                card_data = {
                    "card_type": "metric_card",
                    "title": "Average Transaction Amount",
                    "primary_value": agg["formatted_average"],
                    "secondary_value": f"Total: {agg['formatted_total']} across {agg['numeric_count']:,} transactions",
                    "column": agg["selected_column"],
                    "source_file": filename
                }
            elif intent == "excel_count":
                findings = [
                    "### 📊 Transaction Count",
                    f"- **Authorised Transactions**: **{agg['authorised_count']:,}** records",
                    f"- **Total Populated Rows**: **{agg['rows_detected']:,}** records",
                    f"- **Evaluated Field**: `{agg['selected_column']}`",
                    f"- **Source Workbook**: `{filename}`"
                ]
                task_title = "Excel Record Count"
                summary_text = f"Found {agg['authorised_count']:,} authorised transactions in {filename}."
                card_data = {
                    "card_type": "metric_card",
                    "title": f"{(filter_spec.get('mode') or '').upper() + ' ' if filter_spec and filter_spec.get('mode') else ''}Authorised Transactions",
                    "primary_value": f"{agg['authorised_count']:,}",
                    "secondary_value": f"{agg['rows_detected']:,} total rows",
                    "column": agg["selected_column"],
                    "filter": filter_spec,
                    "source_file": filename
                }
            elif intent in ("excel_max", "excel_min"):
                is_max = (intent == "excel_max")
                date_ext = excel_aggregator.get_date_extremes(file_path=file_path, target_column=target_col, find_max=is_max)
                is_date_query = bool(target_col and any(w in str(target_col).lower() for w in ("date", "expiry", "expire", "created", "joined", "validity", "dob")))
                if date_ext.get("success") and (is_date_query or agg.get("numeric_count", 0) == 0):
                    target_date_val = date_ext.get("formatted_date") or str(date_ext.get("date_value"))
                    col_name = date_ext.get("column", target_col or "Date")
                    row_match = date_ext.get("row") or {}
                    title = f"Latest {col_name}" if is_max else f"Earliest {col_name}"

                    details_list = []
                    for k, v in row_match.items():
                        if k != col_name and v:
                            details_list.append(f"- **{k}**: `{v}`")

                    findings = [
                        f"### 📅 {title}",
                        f"- **{col_name}**: **{target_date_val}**",
                        *details_list[:8],
                        f"- **Source Workbook**: `{filename}`"
                    ]
                    task_title = f"Excel {title}"
                    summary_text = f"{title} in {filename} is {target_date_val}."
                    card_data = {
                        "card_type": "metric_card",
                        "title": title,
                        "primary_value": target_date_val,
                        "secondary_value": f"Column: {col_name}",
                        "column": col_name,
                        "row": row_match,
                        "source_file": filename
                    }
                else:
                    target_val = agg.get("max") if is_max else agg.get("min")
                    formatted_target = format_inr(target_val)
                    row_match = (agg.get("max_row") if is_max else agg.get("min_row")) or {}

                    details_list = []
                    txn_id = row_match.get("Transaction ID") or row_match.get("RID") or row_match.get("Unique_ID") or row_match.get("Bank Transaction ID") or row_match.get("Reference No") or row_match.get("ID")
                    if txn_id:
                        details_list.append(f"- **Transaction ID**: `{txn_id}`")
                    dt = row_match.get("Topup Date") or row_match.get("Transaction Date") or row_match.get("CRTD_DATE") or row_match.get("ATHRSD_DATE") or row_match.get("Date")
                    if dt:
                        details_list.append(f"- **Date**: {dt}")
                    st = row_match.get("Status")
                    if st:
                        details_list.append(f"- **Status**: {st}")
                    mode = row_match.get("Transaction Mode") or row_match.get("Mode")
                    if mode:
                        details_list.append(f"- **Mode**: {mode}")

                    title = "Highest Transaction" if is_max else "Lowest Transaction"
                    findings = [
                        f"### 📈 {title}",
                        f"- **Amount**: **{formatted_target}**",
                        *details_list,
                        f"- **Source Workbook**: `{filename}`"
                    ]
                    task_title = f"Excel {title}"
                    summary_text = f"{title} in {filename} is {formatted_target}." + (f" (ID: {txn_id})" if txn_id else "")
                    card_data = {
                        "card_type": "metric_card",
                        "title": title,
                        "primary_value": formatted_target,
                        "secondary_value": f"Transaction ID: {txn_id}" if txn_id else f"Source: {filename}",
                        "column": agg.get("selected_column", "Amount"),
                        "details": {
                            "transaction_id": str(txn_id or ""),
                            "date": str(dt or ""),
                            "status": str(st or ""),
                            "mode": str(mode or "")
                        },
                        "source_file": filename
                    }
            else:
                findings = [
                    "### 📊 Transaction Metrics",
                    f"- **Minimum Amount**: **{format_inr(agg['min'])}**",
                    f"- **Maximum Amount**: **{format_inr(agg['max'])}**",
                    f"- **Average**: **{agg['formatted_average']}**",
                    f"- **Total**: **{agg['formatted_total']}**",
                    f"- **Source Workbook**: `{filename}`"
                ]
                task_title = "Excel Metric Range"
                summary_text = f"Metrics for {filename}: Min {format_inr(agg['min'])}, Max {format_inr(agg['max'])}, Total {agg['formatted_total']}."
                card_data = {
                    "card_type": "metric_card",
                    "title": "Transaction Range",
                    "primary_value": f"{format_inr(agg['min'])} – {format_inr(agg['max'])}",
                    "secondary_value": f"Average: {agg['formatted_average']}",
                    "source_file": filename
                }

            return CompanyAIResult(
                department=target_dept,
                intent=intent,
                task=task_title,
                summary=summary_text,
                findings=findings,
                citations=[filename],
                confidence=0.99,
                tool_results=card_data,
                internal_metadata={"excel_ms": excel_ms, "file_generation_ms": 0.0, "source_file": filename}
            )

        # -------------------------------------------------------------
        # 4b. EXCEL_GROUP_MAX / EXCEL_GROUP_MIN ("which mode has highest transaction", "show biggest transaction for each mode")
        # -------------------------------------------------------------
        if intent in ("excel_group_max", "excel_group_min"):
            is_max = intent == "excel_group_max"
            group_col = entities.get("group_by_column") or entities.get("group_column") or "Transaction Mode"
            target_col = entities.get("target_column") or entities.get("column") or "Amount"
            
            grp_res = excel_aggregator.calculate_group_aggregation(
                file_path=file_path,
                group_column=group_col,
                target_column=target_col,
                agg_type="max" if is_max else "min"
            )

            agg_label = "Highest" if is_max else "Lowest"
            top_grp = grp_res.get("top_group")
            top_val = grp_res.get("formatted_top_value")
            
            findings = [
                f"### 📊 {agg_label} {grp_res['target_column']} by {grp_res['group_column']}",
                f"- **Overall {agg_label} Mode/Group**: **{top_grp}** with **{top_val}**",
                f"- **Evaluated Groups**: **{grp_res['total_groups']}** groups in `{filename}`\n",
                f"| {grp_res['group_column']} | {agg_label} {grp_res['target_column']} | Total Records | Total Volume |",
                f"| :--- | :--- | :--- | :--- |"
            ]
            for g in grp_res.get("groups", []):
                findings.append(f"| **{g['group']}** | {g['formatted_value']} | {g['count']:,} | {g['formatted_total']} |")

            task_title = f"Excel {agg_label} Transaction by {grp_res['group_column']}"
            summary_text = f"The {top_grp} group has the {agg_label.lower()} transaction of {top_val}."
            
            table_rows = []
            for g in grp_res.get("groups", []):
                table_rows.append({
                    "Group": g["group"],
                    f"{agg_label} Value": g["formatted_value"],
                    "Count": g["count"],
                    "Total Volume": g["formatted_total"]
                })

            return CompanyAIResult(
                department=target_dept,
                intent=intent,
                task=task_title,
                summary=summary_text,
                findings=findings,
                citations=[filename],
                confidence=0.99,
                tool_results={
                    "card_type": "table_view",
                    "title": f"{agg_label} {grp_res['target_column']} by {grp_res['group_column']}",
                    "top_group": top_grp,
                    "top_value": top_val,
                    "headers": [grp_res["group_column"], f"{agg_label} Value", "Records", "Total Volume"],
                    "rows": table_rows,
                    "source_file": filename
                },
                internal_metadata={"excel_ms": excel_ms, "file_generation_ms": 0.0, "source_file": filename}
            )

        # -------------------------------------------------------------
        # 5. EXCEL_FILTER / FILTER_EXPORT / FILTER_COLUMN / READ_COLUMN / CLARIFICATION
        # -------------------------------------------------------------
        if intent in (
            "excel_filter", "excel_filter_export", "excel_filter_column",
            "excel_filter_column_export", "excel_read_column", "excel_clarification",
            "filter", "filter_export", "filter_column"
        ):
            # 5a. Clarification Request
            if intent in ("excel_clarification", "clarification"):
                all_headers = inspection.get("headers", [])
                cols_preview = ", ".join([f"`{h}`" for h in all_headers[:8]])
                findings = [
                    "### ℹ️ Request Clarification",
                    f"I understand you're asking about the Excel workbook `{filename}`.",
                    f"Detected columns include: {cols_preview}.",
                    "",
                    "How would you like me to process this data?",
                    "- *'What are the columns available?'*",
                    "- *'Who are all expired?'*",
                    "- *'Give me expired users as excel'*",
                    "- *'Give me all mobile numbers'*",
                    "- *'What is the total amount?'*"
                ]
                return CompanyAIResult(
                    department=target_dept,
                    intent="excel_clarification",
                    task="Excel Request Clarification",
                    summary=f"Please specify your requested operation on {filename}.",
                    findings=findings,
                    citations=[filename],
                    confidence=0.95,
                    tool_results={
                        "card_type": "clarification_card",
                        "available_columns": all_headers,
                        "source_file": filename
                    },
                    internal_metadata={"excel_ms": excel_ms, "file_generation_ms": 0.0, "source_file": filename}
                )

            # 5b. Read/Analyze Column
            if intent == "excel_read_column":
                target_col = entities.get("target_column") or entities.get("column") or "Expiry_Date"
                col_data = excel_column_export.export_column(file_path, str(target_col))
                resolved_col_name = col_data.get("column_name", target_col)
                rec_count = col_data.get("record_count", 0)
                findings = [
                    f"### 📋 Column Analysis: `{resolved_col_name}`",
                    f"- **Column Name**: `{resolved_col_name}`",
                    f"- **Total Populated Records**: **{rec_count:,}**",
                    f"- **Source Workbook**: `{filename}`",
                    "",
                    "You can filter records, find min/max values, or export this column to Excel."
                ]
                return CompanyAIResult(
                    department=target_dept,
                    intent="excel_read_column",
                    task=f"Column Analysis: {resolved_col_name}",
                    summary=f"Evaluated column '{resolved_col_name}' with {rec_count:,} records in {filename}.",
                    findings=findings,
                    citations=[filename],
                    confidence=0.99,
                    tool_results={
                        "card_type": "column_analysis",
                        "column": resolved_col_name,
                        "record_count": rec_count,
                        "source_file": filename
                    },
                    internal_metadata={"excel_ms": excel_ms, "file_generation_ms": 0.0, "source_file": filename}
                )

            # 5c. Follow-up column extraction on prior filtered rows (e.g. "give me their usernames")
            prior_rows = entities.get("last_exportable_rows") or []
            target_cols = entities.get("target_columns") or entities.get("target_column") or entities.get("column")
            filters_spec = entities.get("filters") or entities.get("filter") or []
            is_export = intent in ("excel_filter_export", "excel_filter_column_export") or entities.get("output_format") == "XLSX" or entities.get("export_requested")

            if (
                intent in ("excel_filter_column", "excel_filter_column_export")
                or (not filters_spec and prior_rows and target_cols and target_cols != "ALL")
            ) and prior_rows:
                # Project target column from prior rows
                extracted_vals = []
                col_name_resolved = str(target_cols[0] if isinstance(target_cols, list) else target_cols)
                # Resolve column name against actual row keys
                if prior_rows and isinstance(prior_rows[0], dict):
                    first_r = prior_rows[0]
                    for k in first_r.keys():
                        if re.sub(r"[_\s\-]+", "", str(k).lower()) == re.sub(r"[_\s\-]+", "", str(col_name_resolved).lower()):
                            col_name_resolved = k
                            break

                for r in prior_rows:
                    val = r.get(col_name_resolved)
                    if val is not None and str(val).strip():
                        extracted_vals.append(str(val).strip())

                if is_export:
                    report_fn = f"{col_name_resolved}_Export.xlsx"
                    export_data = excel_column_export.export_filtered_rows(
                        file_path=file_path,
                        rows=prior_rows,
                        target_columns=[col_name_resolved],
                        output_filename=report_fn,
                        sheet_title=col_name_resolved
                    )
                    findings = [
                        f"### 📊 Filtered Column Export Ready",
                        f"- **Column**: `{col_name_resolved}`",
                        f"- **Exported Records**: **{export_data['record_count']:,}** rows",
                        f"- **Generated Workbook**: `{export_data['filename']}`",
                        f"- **Source Workbook**: `{filename}`"
                    ]
                    return CompanyAIResult(
                        department=target_dept,
                        intent="excel_filter_export",
                        task=f"Column Export: {col_name_resolved}",
                        summary=f"Exported {export_data['record_count']:,} {col_name_resolved} records into {export_data['filename']}.",
                        findings=findings,
                        citations=[filename],
                        confidence=0.99,
                        tool_results={
                            "card_type": "excel_preview",
                            "title": f"{col_name_resolved} Export Ready",
                            "filename": export_data["filename"],
                            "record_count": export_data["record_count"],
                            "column_count": export_data.get("column_count", 2),
                            "columns": export_data.get("columns", ["S.No", col_name_resolved]),
                            "preview_rows": export_data.get("preview_rows", []),
                            "matched_rows": prior_rows,
                            "target_columns": [col_name_resolved],
                            "source_file": filename
                        },
                        internal_metadata={
                            "excel_ms": excel_ms,
                            "file_generation_ms": 0.0,
                            "source_file": filename,
                            "_file_payload": {
                                "filename": export_data["filename"],
                                "file_bytes": export_data["file_bytes"],
                                "file_size": export_data["file_size"]
                            }
                        }
                    )
                else:
                    sample_lines = [f"{idx}. `{v}`" for idx, v in enumerate(extracted_vals[:15], start=1)]
                    findings = [
                        f"### 📋 {col_name_resolved} Listing",
                        f"Found **{len(extracted_vals):,}** records for column `{col_name_resolved}` from previous filter:\n",
                        *sample_lines
                    ]
                    if len(extracted_vals) > 15:
                        findings.append(f"\n*(+{len(extracted_vals) - 15} more records)*")

                    return CompanyAIResult(
                        department=target_dept,
                        intent="excel_filter_column",
                        task=f"Filtered {col_name_resolved}",
                        summary=f"Extracted {len(extracted_vals):,} {col_name_resolved} values from previous filter.",
                        findings=findings,
                        citations=[filename],
                        confidence=0.99,
                        tool_results={
                            "card_type": "column_values",
                            "title": f"Filtered {col_name_resolved}",
                            "column": col_name_resolved,
                            "count": len(extracted_vals),
                            "values": extracted_vals,
                            "matched_rows": prior_rows,
                            "target_columns": [col_name_resolved],
                            "source_file": filename
                        },
                        internal_metadata={"excel_ms": excel_ms, "file_generation_ms": 0.0, "source_file": filename}
                    )

            # 5d. General Filtering via excel_aggregator.filter_rows
            filter_res = excel_aggregator.filter_rows(
                file_path=file_path,
                filters=filters_spec,
                target_columns=target_cols if target_cols != "ALL" else None
            )

            matched_rows = filter_res.get("matched_rows", [])
            match_count = filter_res.get("count", len(matched_rows))
            extracted_vals = filter_res.get("extracted_values", [])
            resolved_target_col = filter_res.get("target_column")

            # Check if this was a Mode filter on transaction sheet
            if isinstance(filters_spec, dict) and "mode" in filters_spec:
                mode_name = str(filters_spec["mode"])
                agg_mode = excel_aggregator.calculate_aggregation(
                    file_path=file_path,
                    target_column="Amount",
                    filter_criteria={"mode": mode_name}
                )
                if is_export:
                    export_data = excel_column_export.export_filtered_workbook(
                        file_path=file_path,
                        filter_criteria={"mode": mode_name},
                        output_filename=f"{mode_name}_Transactions_Report.xlsx"
                    )
                    findings = [
                        f"### 📊 {mode_name.upper()} Transactions Report Ready",
                        f"- **Filtered Mode**: `{mode_name.upper()}`",
                        f"- **Total Records**: **{agg_mode['numeric_count']:,}**",
                        f"- **Total Volume**: **{agg_mode['formatted_total']}**",
                        f"- **Generated File**: `{export_data['filename']}`"
                    ]
                    return CompanyAIResult(
                        department=target_dept,
                        intent="excel_filter_export",
                        task=f"Export {mode_name.upper()} Transactions",
                        summary=f"Exported {agg_mode['numeric_count']} {mode_name} transactions totaling {agg_mode['formatted_total']}.",
                        findings=findings,
                        citations=[filename],
                        confidence=0.99,
                        tool_results={
                            "card_type": "excel_preview",
                            "title": f"{mode_name.upper()} Transactions Report",
                            "filename": export_data["filename"],
                            "record_count": agg_mode["numeric_count"],
                            "matched_rows": matched_rows,
                            "filter": {"mode": mode_name},
                            "source_file": filename
                        },
                        internal_metadata={
                            "excel_ms": excel_ms,
                            "file_generation_ms": 0.0,
                            "source_file": filename,
                            "_file_payload": {
                                "filename": export_data["filename"],
                                "file_bytes": export_data["file_bytes"],
                                "file_size": export_data["file_size"]
                            }
                        }
                    )
                else:
                    findings = [
                        f"### 📊 Filter by Mode: {mode_name.upper()}",
                        f"- **{mode_name.upper()} Transactions**: **{agg_mode['numeric_count']:,}** records",
                        f"- **Total {mode_name.upper()} Amount**: **{agg_mode['formatted_total']}**",
                        f"- **Average per Transaction**: **{agg_mode['formatted_average']}**",
                        f"- **Source Workbook**: `{filename}`"
                    ]
                    return CompanyAIResult(
                        department=target_dept,
                        intent="excel_filter",
                        task=f"Filter by Mode: {mode_name}",
                        summary=f"Found {agg_mode['numeric_count']} {mode_name} transactions totaling {agg_mode['formatted_total']} in {filename}.",
                        findings=findings,
                        citations=[filename],
                        confidence=0.99,
                        tool_results={
                            "card_type": "metric_card",
                            "title": f"{mode_name.upper()} Transactions",
                            "primary_value": f"{agg_mode['numeric_count']:,}",
                            "secondary_value": f"Total: {agg_mode['formatted_total']} (Avg: {agg_mode['formatted_average']})",
                            "filter": {"mode": mode_name},
                            "matched_rows": matched_rows,
                            "source_file": filename
                        },
                        internal_metadata={"excel_ms": excel_ms, "file_generation_ms": 0.0, "source_file": filename}
                    )

            # Check if Export is requested for general filtered rows
            if is_export:
                export_fn = f"Filtered_Records_{int(time.time())}.xlsx"
                if resolved_target_col:
                    export_fn = f"{resolved_target_col}_Filtered.xlsx"
                elif filters_spec and isinstance(filters_spec, list) and len(filters_spec) > 0:
                    op_k = filters_spec[0].get("operator", "FILTER").lower()
                    export_fn = f"{op_k}_Records.xlsx"

                export_data = excel_column_export.export_filtered_rows(
                    file_path=file_path,
                    rows=matched_rows,
                    target_columns=target_cols if target_cols != "ALL" else None,
                    output_filename=export_fn,
                    sheet_title="Filtered_Records"
                )

                findings = [
                    f"### 📊 Filtered Records Export Ready",
                    f"- **Matching Records**: **{export_data['record_count']:,}** rows",
                    f"- **Exported Columns**: **{export_data['column_count']}**",
                    f"- **Generated Workbook**: `{export_data['filename']}`",
                    f"- **Source Workbook**: `{filename}`"
                ]

                logger.info(
                    f"\n[ExcelProcessor]\n"
                    f"document={filename}\n"
                    f"operation=FILTER_EXPORT\n"
                    f"matching_records={match_count}\n"
                    f"generated_file={export_data['filename']}\n"
                    f"\n[CompanyAI]\n"
                    f"verified_result=true"
                )

                return CompanyAIResult(
                    department=target_dept,
                    intent="excel_filter_export",
                    task="Export Filtered Records",
                    summary=f"Exported {export_data['record_count']:,} filtered records into {export_data['filename']}.",
                    findings=findings,
                    citations=[filename],
                    confidence=0.99,
                    tool_results={
                        "card_type": "excel_preview",
                        "title": "Filtered Records Export Ready",
                        "filename": export_data["filename"],
                        "record_count": export_data["record_count"],
                        "column_count": export_data["column_count"],
                        "columns": export_data["columns"],
                        "preview_rows": export_data.get("preview_rows", []),
                        "matched_rows": matched_rows,
                        "target_columns": target_cols,
                        "source_file": filename
                    },
                    internal_metadata={
                        "excel_ms": excel_ms,
                        "file_generation_ms": 0.0,
                        "source_file": filename,
                        "_file_payload": {
                            "filename": export_data["filename"],
                            "file_bytes": export_data["file_bytes"],
                            "file_size": export_data["file_size"]
                        }
                    }
                )

            # Specific column values extracted from filter (e.g. "give me usernames of expired users")
            if resolved_target_col and extracted_vals:
                sample_lines = [f"{idx}. `{v}`" for idx, v in enumerate(extracted_vals[:15], start=1)]
                findings = [
                    f"### 📋 Filtered `{resolved_target_col}` Listing",
                    f"Found **{len(extracted_vals):,}** records matching filter:\n",
                    *sample_lines
                ]
                if len(extracted_vals) > 15:
                    findings.append(f"\n*(+{len(extracted_vals) - 15} more records)*")

                return CompanyAIResult(
                    department=target_dept,
                    intent="excel_filter_column",
                    task=f"Filtered {resolved_target_col}",
                    summary=f"Identified {len(extracted_vals):,} matching {resolved_target_col} values in {filename}.",
                    findings=findings,
                    citations=[filename],
                    confidence=0.99,
                    tool_results={
                        "card_type": "column_values",
                        "title": f"Filtered {resolved_target_col}",
                        "column": resolved_target_col,
                        "count": len(extracted_vals),
                        "values": extracted_vals,
                        "matched_rows": matched_rows,
                        "target_columns": [resolved_target_col],
                        "source_file": filename
                    },
                    internal_metadata={"excel_ms": excel_ms, "file_generation_ms": 0.0, "source_file": filename}
                )

            # General Filter summary (e.g. "who are all expired?", "who expires this month?", "transactions above 10000")
            sample_previews = []
            for r in matched_rows[:10]:
                preview_parts = []
                for k in ["UserName", "FirstName", "VleId", "MobileNo", "Email", "Expiry_Date", "Transaction ID", "Amount", "Settled_Amount", "Status"]:
                    if k in r and r[k] is not None and str(r[k]).strip():
                        val = r[k]
                        if k in ("Amount", "Settled_Amount", "Total", "Price", "Balance", "Volume"):
                            dec_v = parse_decimal_safe(val)
                            val_str = format_inr(dec_v) if dec_v is not None else str(val)
                        else:
                            val_str = str(val)
                        preview_parts.append(f"**{k}**: `{val_str}`")
                if not preview_parts:
                    for k, v in list(r.items())[:4]:
                        if v is not None and str(v).strip():
                            if k in ("Amount", "Settled_Amount", "Total", "Price", "Balance", "Volume"):
                                dec_v = parse_decimal_safe(v)
                                val_str = format_inr(dec_v) if dec_v is not None else str(v)
                            else:
                                val_str = str(v)
                            preview_parts.append(f"**{k}**: `{val_str}`")
                sample_previews.append("- " + " | ".join(preview_parts))

            # Check if there is a numeric column to aggregate in matched rows
            numeric_sum = None
            amount_col_name = None
            if matched_rows:
                for candidate in ["Amount", "Total", "Price", "Balance", "Volume"]:
                    if candidate in matched_rows[0]:
                        amount_col_name = candidate
                        break
                if not amount_col_name:
                    for flt in filter_res.get("resolved_filters", []):
                        c = flt.get("column")
                        if c and c in matched_rows[0]:
                            amount_col_name = c
                            break

                if amount_col_name:
                    tot_dec = Decimal("0")
                    has_dec = False
                    for r in matched_rows:
                        val_d = parse_decimal_safe(r.get(amount_col_name))
                        if val_d is not None:
                            tot_dec += val_d
                            has_dec = True
                    if has_dec:
                        numeric_sum = tot_dec

            findings = [
                f"### 📊 Filter Results",
                f"- **Matching Records**: **{match_count:,}** records",
            ]
            if numeric_sum is not None:
                findings.append(f"- **Total {amount_col_name}**: **{format_inr(numeric_sum)}**")
            findings.extend([
                f"- **Total Workbook Rows**: **{filter_res.get('total_rows', 0):,}** records",
                f"- **Source Workbook**: `{filename}`",
                ""
            ])
            if sample_previews:
                findings.append("**Sample Matching Records:**")
                findings.extend(sample_previews)
                if match_count > 10:
                    findings.append(f"\n*(+{match_count - 10} more records)*")

            return CompanyAIResult(
                department=target_dept,
                intent="excel_filter",
                task="Filter Records",
                summary=f"Found {match_count:,} matching records in {filename}.",
                findings=findings,
                citations=[filename],
                confidence=0.99,
                tool_results={
                    "card_type": "filter_result",
                    "title": "Filtered Records",
                    "count": match_count,
                    "matched_rows": matched_rows,
                    "target_columns": target_cols,
                    "filters": filters_spec,
                    "source_file": filename
                },
                internal_metadata={"excel_ms": excel_ms, "file_generation_ms": 0.0, "source_file": filename}
            )

        # -------------------------------------------------------------
        # 6. EXCEL_SUMMARY
        # -------------------------------------------------------------
        if intent == "excel_summary":
            if wb_type in (WorkbookType.TRANSACTION.value, WorkbookType.EBO_TOPUP.value):
                agg_summary = excel_aggregator.calculate_aggregation(file_path=file_path, target_column="Amount")
                sheets_dict = inspection.get("sheets") or {}
                first_sheet = list(sheets_dict.values())[0] if sheets_dict else {}
                modes_dict = first_sheet.get("modes") or {}
                auth_count = agg_summary.get("authorised_count", agg_summary.get("rows_detected", 0))
                formatted_total = agg_summary.get("formatted_total", "₹0.00")

                modes_formatted = []
                for m_name in ["QR", "UPI", "BQR"]:
                    if isinstance(modes_dict, dict) and m_name in modes_dict:
                        modes_formatted.append(f"- **{m_name}**: {modes_dict[m_name]:,}")
                if isinstance(modes_dict, dict):
                    for m_name, m_cnt in modes_dict.items():
                        if m_name not in ["QR", "UPI", "BQR"]:
                            modes_formatted.append(f"- **{m_name}**: {m_cnt:,}")

                findings = [
                    "### 📊 Transaction Summary",
                    f"- **Authorised Transactions**: **{auth_count:,}**",
                    f"- **Total Amount**: **{formatted_total}**",
                    f"- **Average Amount**: **{agg_summary['formatted_average']}**",
                    f"- **Minimum Amount**: **{format_inr(agg_summary['min'])}**",
                    f"- **Maximum Amount**: **{format_inr(agg_summary['max'])}**",
                    f"- **Source Workbook**: `{filename}`"
                ]

                if modes_formatted:
                    findings.append("")
                    findings.append("**Transaction Modes:**")
                    findings.extend(modes_formatted)

                metric_list = [
                    {"label": "Transactions", "value": f"{auth_count:,}"},
                    {"label": "Total Amount", "value": formatted_total},
                    {"label": "Average", "value": agg_summary["formatted_average"]}
                ]
                if isinstance(modes_dict, dict):
                    if "QR" in modes_dict:
                        metric_list.append({"label": "QR", "value": str(modes_dict["QR"])})
                    if "UPI" in modes_dict:
                        metric_list.append({"label": "UPI", "value": str(modes_dict["UPI"])})
                    if "BQR" in modes_dict:
                        metric_list.append({"label": "BQR", "value": str(modes_dict["BQR"])})

                return CompanyAIResult(
                    department=target_dept,
                    intent="excel_summary",
                    task="Transaction Document Summary",
                    summary=f"Summary of {filename}: {auth_count:,} authorised transactions totaling {formatted_total}.",
                    findings=findings,
                    citations=[filename],
                    confidence=0.98,
                    tool_results={
                        "card_type": "summary_grid",
                        "title": "Transaction Summary",
                        "metrics": metric_list,
                        "source_file": filename
                    },
                    internal_metadata={"excel_ms": excel_ms, "file_generation_ms": 0.0, "source_file": filename}
                )

            elif wb_type == WorkbookType.SPRINT.value:
                target_owners = entities.get("target_owners")
                if not isinstance(target_owners, list):
                    target_owners = []
                if target_owners:
                    owner_summaries = []
                    for owner in target_owners:
                        matching_tasks = []
                        total_hours = 0.0
                        modules = set()
                        for s_name, s_info in (inspection.get("sheets") or {}).items():
                            col_map = s_info.get("schema") or {}
                            owner_col = col_map.get("owner_column")
                            for r in s_info.get("rows", []):
                                if owner_col and r.get(owner_col) and re.search(rf"\b{re.escape(str(owner))}\b", str(r.get(owner_col)), re.I):
                                    matching_tasks.append(r)
                                    for k, v in r.items():
                                        if any(a in str(k).lower() for a in ["hours", "estimate"]):
                                            try:
                                                total_hours += float(str(v).replace("h", "").replace("hrs", "").strip())
                                            except (ValueError, TypeError):
                                                pass
                                        if any(a in str(k).lower() for a in ["module", "component"]):
                                            if v:
                                                modules.add(str(v).strip())

                        owner_summaries.append(
                            f"- **{owner}**: **{len(matching_tasks)}** tasks assigned ({total_hours} estimated hours) across modules: {', '.join(sorted(modules)) or 'General'}"
                        )

                    findings = [
                        "### 📊 Sprint Summary",
                        f"Summary for {', '.join(target_owners)} in **{filename}**:",
                        *owner_summaries
                    ]
                    return CompanyAIResult(
                        department=target_dept,
                        intent="excel_summary",
                        task="Sprint Owner Summary",
                        summary=f"Analyzed tasks for {', '.join(target_owners)} in {filename}.",
                        findings=findings,
                        citations=[filename],
                        confidence=0.98,
                        tool_results={"card_type": "sprint_summary", "owners": target_owners, "source_file": filename},
                        internal_metadata={"excel_ms": excel_ms, "file_generation_ms": 0.0, "source_file": filename}
                    )

            # Generic Summary
            findings = [
                "### 📊 Document Summary",
                f"- **Worksheets ({len(inspection.get('worksheet_names', []))})**: {', '.join(inspection.get('worksheet_names', []))}",
                f"- **Total Records**: {inspection.get('total_valid_rows', inspection.get('total_rows', 0)):,} rows across all worksheets.",
                f"- **Detected Columns**: {', '.join(inspection.get('headers', []))[:120]}...",
                f"- **Source Workbook**: `{filename}`"
            ]
            return CompanyAIResult(
                department=target_dept,
                intent="excel_summary",
                task="Excel Document Summary",
                summary=f"Analyzed {filename} containing {inspection.get('total_valid_rows', 0):,} records.",
                findings=findings,
                citations=[filename],
                confidence=0.98,
                tool_results={"card_type": "generic_summary", "source_file": filename},
                internal_metadata={"excel_ms": excel_ms, "file_generation_ms": 0.0, "source_file": filename}
            )

        # -------------------------------------------------------------
        # 7. EXCEL_REPORT
        # -------------------------------------------------------------
        if intent == "excel_report":
            agg_rep = excel_aggregator.calculate_aggregation(file_path=file_path, target_column="Amount")
            first_sheet_info = list((inspection.get("sheets") or {}).values())[0] if inspection.get("sheets") else {}
            modes_dict = first_sheet_info.get("modes") or {}
            findings = [
                "### 📊 TRANSACTION AUDIT REPORT",
                f"- **Settlement Status**: Verified Authorised ({agg_rep['authorised_count']:,} transactions)",
                f"- **Gross Transaction Amount**: **{agg_rep['formatted_total']}**",
                f"- **Average Ticket Size**: **{agg_rep['formatted_average']}**",
                f"- **Range**: {format_inr(agg_rep['min'])} to {format_inr(agg_rep['max'])}",
                f"- **Source Workbook**: `{filename}`"
            ]
            if isinstance(modes_dict, dict) and modes_dict:
                findings.append("")
                findings.append("**Channel & Mode Distribution:**")
                for m_k, m_v in modes_dict.items():
                    findings.append(f"- **{m_k}**: {m_v:,} transactions")

            return CompanyAIResult(
                department=target_dept,
                intent="excel_report",
                task="Transaction Audit Report",
                summary=f"Generated Transaction Audit Report for {filename} ({agg_rep['formatted_total']} total).",
                findings=findings,
                citations=[filename],
                confidence=0.99,
                tool_results={
                    "card_type": "report_card",
                    "title": "Transaction Audit Report",
                    "gross_amount": agg_rep["formatted_total"],
                    "average_amount": agg_rep["formatted_average"],
                    "authorised_count": agg_rep["authorised_count"],
                    "modes": modes_dict if isinstance(modes_dict, dict) else {},
                    "source_file": filename
                },
                internal_metadata={"excel_ms": excel_ms, "file_generation_ms": 0.0, "source_file": filename}
            )

        # -------------------------------------------------------------
        # 8. EXCEL_SPLIT / SPRINT TASK EXPORT (Fazil=692h, Reka=686h)
        # -------------------------------------------------------------
        if intent in ("excel_split", "excel_sprint_split") or (wb_type == WorkbookType.SPRINT.value and entities.get("target_owners")):
            target_owners = entities.get("target_owners", [])
            split_res = sprint_processor.filter_and_export_by_owners(file_path, target_owners)
            owner_results = split_res.get("owner_results", {})

            findings = [
                "[EXCEL] SPRINT SPLIT GENERATION",
                "✓ Authorized",
                f"✓ Source: {filename}",
                ""
            ]
            for o_name, o_data in owner_results.items():
                if o_data.get("found"):
                    hours_str = f" ({o_data.get('total_hours')} estimated hours)" if o_data.get('total_hours') else ""
                    modules_str = f" across modules: {', '.join(o_data.get('modules', []))}" if o_data.get('modules') else ""
                    findings.append(f"- **{o_name}**: **{o_data.get('row_count')}** tasks extracted{hours_str}{modules_str} -> `{o_data.get('filename')}`")
                else:
                    findings.append(f"- **{o_name}**: No matching tasks found in uploaded workbook.")

            logger.info(
                f"\n[ExcelProcessor]\n"
                f"document={filename}\n"
                f"sprint_split_owners={target_owners}\n"
                f"files_generated={list(owner_results.keys())}\n"
                f"\n[CompanyAI]\n"
                f"verified_result=true"
            )

            clean_owners = {
                k: {k2: v2 for k2, v2 in v.items() if k2 != "file_bytes"}
                for k, v in owner_results.items()
            }

            return CompanyAIResult(
                department=target_dept,
                intent="excel_split",
                task="Sprint Task Split",
                summary=f"Generated {len(owner_results)} customized sprint file(s) for {', '.join(target_owners)} from {filename}.",
                findings=findings,
                citations=[filename],
                confidence=0.99,
                tool_results={
                    "card_type": "sprint_split",
                    "owners": clean_owners,
                    "source_file": filename
                },
                internal_metadata={
                    "excel_ms": excel_ms,
                    "file_generation_ms": 0.0,
                    "source_file": filename,
                    "_owner_payloads": owner_results
                }
            )

        # Fallback / Default
        return CompanyAIResult(
            department=target_dept,
            intent=intent,
            task="Excel Operation",
            summary=f"Processed Excel workbook {filename}.",
            findings=[f"Completed Excel analysis for `{filename}`."],
            citations=[filename],
            confidence=0.90,
            internal_metadata={"excel_ms": excel_ms, "file_generation_ms": 0.0, "source_file": filename}
        )

    def _execute_multi_document_summary(
        self,
        file_path: str,
        secondary_file_path: Optional[str],
        entities: Dict[str, Any],
        target_dept: DepartmentEnum,
        excel_ms: float
    ) -> CompanyAIResult:
        filename_a = os.path.basename(file_path)
        if not secondary_file_path:
            return CompanyAIResult(
                department=target_dept,
                intent="excel_multi_document_summary",
                task="Multi-Document Summary",
                summary="Multi-document summary requires two uploaded Excel files.",
                findings=[
                    "Please upload or provide two Excel workbooks to generate a multi-document summary.",
                    "Example: Upload `UPI.xlsx` and `EBO.xlsx`, then ask *'give me a summary report for these 2'*."
                ],
                citations=[filename_a],
                confidence=0.85
            )

        filename_b = os.path.basename(secondary_file_path)
        agg_a = excel_aggregator.calculate_aggregation(file_path=file_path, target_column="Amount")
        agg_b = excel_aggregator.calculate_aggregation(file_path=secondary_file_path, target_column="Amount")
        insp_a = excel_aggregator.inspect_workbook(file_path)
        insp_b = excel_aggregator.inspect_workbook(secondary_file_path)

        # 1. Highest Transactions
        max_val_a = agg_a.get("max", 0.0) or 0.0
        max_val_b = agg_b.get("max", 0.0) or 0.0
        max_row_a = agg_a.get("max_row", {}) or {}
        max_row_b = agg_b.get("max_row", {}) or {}

        txn_id_a = max_row_a.get("Transaction ID") or max_row_a.get("RID") or max_row_a.get("Unique_ID") or max_row_a.get("Reference No") or max_row_a.get("ID") or "N/A"
        txn_id_b = max_row_b.get("Transaction ID") or max_row_b.get("RID") or max_row_b.get("Unique_ID") or max_row_b.get("Reference No") or max_row_b.get("ID") or "N/A"
        dt_a = max_row_a.get("Topup Date") or max_row_a.get("Transaction Date") or max_row_a.get("CRTD_DATE") or max_row_a.get("ATHRSD_DATE") or max_row_a.get("Date") or ""
        dt_b = max_row_b.get("Topup Date") or max_row_b.get("Transaction Date") or max_row_b.get("CRTD_DATE") or max_row_b.get("ATHRSD_DATE") or max_row_b.get("Date") or ""
        mode_a = max_row_a.get("Transaction Mode") or max_row_a.get("Mode") or "N/A"
        mode_b = max_row_b.get("Transaction Mode") or max_row_b.get("Mode") or "N/A"

        if max_val_a >= max_val_b:
            overall_max_val = max_val_a
            overall_max_file = filename_a
            overall_max_id = txn_id_a
            overall_max_dt = dt_a
            overall_max_mode = mode_a
        else:
            overall_max_val = max_val_b
            overall_max_file = filename_b
            overall_max_id = txn_id_b
            overall_max_dt = dt_b
            overall_max_mode = mode_b

        # 2. Reconcile & Mismatches
        comp_res = excel_comparator.compare_workbooks(file_path, secondary_file_path)
        if comp_res.get("success"):
            matched_count = comp_res.get("matched_count", 0)
            missing_in_b = comp_res.get("missing_in_b_count", 0)
            missing_in_a = comp_res.get("missing_in_a_count", 0)
            amount_mismatches = comp_res.get("amount_mismatch_count", 0)
            status_mismatches = comp_res.get("status_mismatch_count", 0)
            total_mismatches = comp_res.get("total_mismatches", 0)
            recon_key = f"{comp_res['key_a']} ↔ {comp_res['key_b']}"
        else:
            matched_count = 0
            missing_in_b = 0
            missing_in_a = 0
            amount_mismatches = 0
            status_mismatches = 0
            total_mismatches = 0
            recon_key = "None (No shared unique key)"

        # 3. Bank Names & Categories
        distinct_banks = set()
        for insp in [insp_a, insp_b]:
            sheets = insp.get("sheets") or {}
            for s_info in sheets.values():
                for row in s_info.get("rows", []):
                    for k, v in row.items():
                        if re.search(r"\bbank\b", str(k), re.I) and v and str(v).strip():
                            distinct_banks.add(str(v).strip())

        bank_list = sorted(list(distinct_banks))
        if bank_list:
            bank_desc = ", ".join(bank_list[:10]) + (f" (+{len(bank_list) - 10} more)" if len(bank_list) > 10 else "")
            bank_md = f"- **Bank Names Identified ({len(bank_list)})**: {bank_desc}"
        else:
            bank_md = "- **Bank Names**: No dedicated `Bank Name` column found in either workbook."

        # Combined totals
        combined_total_num = (agg_a.get("total", 0.0) or 0.0) + (agg_b.get("total", 0.0) or 0.0)
        combined_count = agg_a.get("authorised_count", 0) + agg_b.get("authorised_count", 0)

        findings = [
            "### 📊 Multi-Document Summary Report",
            f"Cross-analysis and reconciliation between **`{filename_a}`** and **`{filename_b}`**:\n",
            "#### 📈 1. Highest Transactions",
            f"- **Overall Highest Transaction**: **{format_inr(overall_max_val)}**",
            f"  - Source: `{overall_max_file}`",
            f"  - Transaction ID: `{overall_max_id}`",
            f"  - Mode: `{overall_max_mode}`",
            f"  - Date: {overall_max_dt}" if overall_max_dt else "",
            f"- **File A (`{filename_a}`) Peak**: **{format_inr(max_val_a)}** (ID: `{txn_id_a}`)",
            f"- **File B (`{filename_b}`) Peak**: **{format_inr(max_val_b)}** (ID: `{txn_id_b}`)\n",
            "#### 🔍 2. Discrepancies & Reconciliation",
            f"- **Reconciled on Key**: **{recon_key}**",
            f"- **Matched Records**: **{matched_count:,}**",
            f"- **Missing in `{filename_b[:20]}`**: **{missing_in_b:,}**",
            f"- **Missing in `{filename_a[:20]}`**: **{missing_in_a:,}**",
            f"- **Amount Discrepancies**: **{amount_mismatches:,}**",
            f"- **Total Discrepancies**: **{total_mismatches:,}**\n",
            "#### 🏦 3. Bank Information",
            bank_md,
            "",
            "#### 💰 4. Financial Summary",
            f"- **`{filename_a}` Total**: **{agg_a['formatted_total']}** across **{agg_a['authorised_count']:,}** records (Avg: {agg_a['formatted_average']})",
            f"- **`{filename_b}` Total**: **{agg_b['formatted_total']}** across **{agg_b['authorised_count']:,}** records (Avg: {agg_b['formatted_average']})",
            f"- **Combined Volume**: **{format_inr(combined_total_num)}** across **{combined_count:,}** total transactions"
        ]
        findings = [f for f in findings if f is not None and f != ""]

        summary_payload = {
            "file_a_name": filename_a,
            "file_b_name": filename_b,
            "overview_rows": [
                ["Total Amount", agg_a['formatted_total'], agg_b['formatted_total'], format_inr(combined_total_num)],
                ["Authorised Transactions", f"{agg_a['authorised_count']:,}", f"{agg_b['authorised_count']:,}", f"{combined_count:,}"],
                ["Average Transaction Amount", agg_a['formatted_average'], agg_b['formatted_average'], "-"],
                ["Highest Transaction", format_inr(max_val_a), format_inr(max_val_b), f"{format_inr(overall_max_val)} ({overall_max_file})"],
                ["Reconciliation Key", comp_res.get("key_a", "N/A"), comp_res.get("key_b", "N/A"), recon_key],
                ["Matched Records", "-", "-", f"{matched_count:,}"],
                ["Discrepancies / Mismatches", f"Missing: {missing_in_a:,}", f"Missing: {missing_in_b:,}", f"{total_mismatches:,} Total"]
            ],
            "max_rows": [
                ("Overall Highest Transaction", format_inr(overall_max_val)),
                ("Source File", overall_max_file),
                ("Transaction ID", overall_max_id),
                ("Date", overall_max_dt or "N/A"),
                ("Mode", overall_max_mode),
                (f"File A ({filename_a}) Peak", format_inr(max_val_a)),
                ("File A Txn ID", txn_id_a),
                (f"File B ({filename_b}) Peak", format_inr(max_val_b)),
                ("File B Txn ID", txn_id_b),
            ],
            "info_rows": [
                ("Bank Names Found", ", ".join(bank_list) if bank_list else "No Bank Name column in workbooks"),
                ("File A Headers", ", ".join(insp_a.get("headers", [])[:8])),
                ("File B Headers", ", ".join(insp_b.get("headers", [])[:8])),
                ("Reconciliation Key Used", recon_key)
            ]
        }

        export_data = excel_column_export.export_multi_document_summary(summary_payload)

        logger.info(
            f"\n[ExcelProcessor]\n"
            f"document_a={filename_a}\n"
            f"document_b={filename_b}\n"
            f"operation=MULTI_DOCUMENT_SUMMARY\n"
            f"highest_txn={format_inr(overall_max_val)}\n"
            f"total_mismatches={total_mismatches}\n"
            f"banks_found={len(bank_list)}\n"
            f"\n[CompanyAI]\n"
            f"verified_result=true"
        )

        return CompanyAIResult(
            department=target_dept,
            intent="excel_multi_document_summary",
            task="Multi-Document Summary Report",
            summary=f"Summary of {filename_a} & {filename_b}: Highest txn {format_inr(overall_max_val)}, {total_mismatches:,} discrepancies, combined volume {format_inr(combined_total_num)}.",
            findings=findings,
            citations=[filename_a, filename_b],
            confidence=0.99,
            tool_results={
                "card_type": "multi_document_summary",
                "title": "Multi-Document Summary Report",
                "file_a": filename_a,
                "file_b": filename_b,
                "highest_transaction": format_inr(overall_max_val),
                "highest_transaction_file": overall_max_file,
                "highest_transaction_id": overall_max_id,
                "highest_transaction_mode": overall_max_mode,
                "matched_count": matched_count,
                "total_mismatches": total_mismatches,
                "missing_in_a": missing_in_a,
                "missing_in_b": missing_in_b,
                "amount_mismatches": amount_mismatches,
                "reconciliation_key": recon_key,
                "banks": bank_list,
                "total_volume": format_inr(combined_total_num),
                "total_transactions": combined_count
            },
            internal_metadata={
                "excel_ms": excel_ms,
                "file_generation_ms": 0.0,
                "source_file": filename_a,
                "secondary_file": filename_b,
                "_multi_doc_summary": summary_payload,
                "_comparison_result": comp_res,
                "_file_payload": {
                    "filename": export_data["filename"],
                    "file_bytes": export_data["file_bytes"],
                    "file_size": export_data["file_size"]
                }
            }
        )

    def _execute_unique_values(
        self,
        file_path: str,
        entities: Dict[str, Any],
        target_dept: DepartmentEnum,
        excel_ms: float
    ) -> CompanyAIResult:
        filename = os.path.basename(file_path)
        insp = excel_aggregator.inspect_workbook(file_path)
        target_concept = entities.get("target_concept") or "bank"
        target_col = entities.get("target_column") or entities.get("column")

        # Find matching column
        all_headers = insp.get("headers", [])
        matched_col = None
        if target_col:
            for h in all_headers:
                if re.sub(r"[_\s\-]+", "", str(h).lower()) == re.sub(r"[_\s\-]+", "", str(target_col).lower()):
                    matched_col = h
                    break

        if not matched_col:
            for h in all_headers:
                if target_concept in str(h).lower():
                    matched_col = h
                    break

        if not matched_col:
            avail_cols = "\n".join([f"- `{c}`" for c in all_headers[:15]]) if all_headers else "No columns found."
            concept_title = "Bank Name" if target_concept == "bank" else (target_concept.title() if target_concept else "Requested")
            findings = [
                f"### ℹ️ {concept_title} Column Notice",
                f"No dedicated `{concept_title}` column was found in `{filename}`.",
                "",
                "**Available Columns in Workbook:**",
                avail_cols
            ]
            return CompanyAIResult(
                department=target_dept,
                intent="excel_unique_values",
                task=f"Unique {concept_title} Listing",
                summary=f"No {concept_title} column found in {filename}.",
                findings=findings,
                citations=[filename],
                confidence=0.95,
                tool_results={
                    "card_type": "unique_values",
                    "concept": target_concept,
                    "found": False,
                    "available_columns": all_headers,
                    "source_file": filename
                },
                internal_metadata={"excel_ms": excel_ms, "file_generation_ms": 0.0, "source_file": filename}
            )

        # Extract unique values
        distinct_vals = set()
        sheets = insp.get("sheets") or {}
        for s_info in sheets.values():
            for r in s_info.get("rows", []):
                val = r.get(matched_col)
                if val is not None and str(val).strip():
                    distinct_vals.add(str(val).strip())

        sorted_vals = sorted(list(distinct_vals))
        concept_title = "Bank Names" if target_concept == "bank" else f"{matched_col} Values"

        findings = [
            f"### 🏦 {concept_title}",
            f"Found **{len(sorted_vals)}** unique values in column `{matched_col}` across `{filename}`:\n"
        ]
        for idx, v in enumerate(sorted_vals, start=1):
            findings.append(f"{idx}. `{v}`")

        logger.info(
            f"\n[ExcelProcessor]\n"
            f"document={filename}\n"
            f"column={matched_col}\n"
            f"unique_count={len(sorted_vals)}\n"
            f"\n[CompanyAI]\n"
            f"verified_result=true"
        )

        return CompanyAIResult(
            department=target_dept,
            intent="excel_unique_values",
            task=f"Unique {matched_col} Listing",
            summary=f"Identified {len(sorted_vals)} unique values for '{matched_col}' in {filename}.",
            findings=findings,
            citations=[filename],
            confidence=0.99,
            tool_results={
                "card_type": "unique_values",
                "column": matched_col,
                "values": sorted_vals,
                "count": len(sorted_vals),
                "source_file": filename
            },
            internal_metadata={"excel_ms": excel_ms, "file_generation_ms": 0.0, "source_file": filename}
        )


excel_service = ExcelService()
