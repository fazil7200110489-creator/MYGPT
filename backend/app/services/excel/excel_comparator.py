"""Generic Two-File Excel Comparison and Reconciliation Engine.

Performs robust key discovery, record reconciliation, mismatch categorization,
and generates multi-sheet reconciliation audit workbooks.
Zero mock values.
"""

import io
import os
import re
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple, Set
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from loguru import logger

from backend.app.services.excel.excel_aggregator import excel_aggregator
from backend.app.services.excel.excel_parser import parse_decimal_safe, format_inr, load_workbook_safe


class ExcelComparator:
    """Compares two Excel workbooks, reconciles transactions, and builds mismatch reports."""

    KEY_ALIASES = [
        {"keys_a": ["rid", "trn", "crn", "unique_id"], "keys_b": ["bank transaction id", "vendor reference id", "transaction id"]},
        {"keys_a": ["trnsctn_nmbr", "transaction number", "trans_no"], "keys_b": ["vendor reference id", "reference id"]},
        {"keys_a": ["invoice_number", "invoice #", "inv_no"], "keys_b": ["invoice_number", "invoice #", "inv_no", "po_number"]},
        {"keys_a": ["employee_id", "emp_id", "employee code"], "keys_b": ["employee_id", "emp_id", "employee code"]}
    ]

    def _clean_key_val(self, val: Any) -> str:
        if val is None:
            return ""
        s = str(val).strip()
        if s.endswith(".0") and s[:-2].replace("-", "").isdigit():
            s = s[:-2]
        return s.lower()

    def discover_matching_keys(
        self,
        file_path_a: str,
        file_path_b: str,
        user_specified_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Discovers the optimal matching key between two workbooks using semantic concepts,
        uniqueness validation, and value overlap. Never selects categorical columns like branch codes.
        """
        insp_a = excel_aggregator.inspect_workbook(file_path_a)
        insp_b = excel_aggregator.inspect_workbook(file_path_b)

        headers_a = insp_a.get("headers", [])
        headers_b = insp_b.get("headers", [])

        # 1. User specified key
        if user_specified_key:
            ka = self._find_col(headers_a, user_specified_key)
            kb = self._find_col(headers_b, user_specified_key)
            if ka and kb:
                return {
                    "found": True,
                    "key_a": ka,
                    "key_b": kb,
                    "method": "user_specified",
                    "confidence": "HIGH",
                    "reason": f"Matched by user-specified identifier '{user_specified_key}'."
                }

        # Sample rows for uniqueness and overlap validation
        first_sheet_a = list(insp_a.get("sheets", {}).values())[0] if insp_a.get("sheets") else {}
        rows_a = first_sheet_a.get("valid_rows", [])
        first_sheet_b = list(insp_b.get("sheets", {}).values())[0] if insp_b.get("sheets") else {}
        rows_b = first_sheet_b.get("valid_rows", [])

        # Semantic concept patterns
        identity_patterns = [
            r"\b(unique_id|txn_id|txnid|transaction_id|trans_id|trnsctn_nmbr|bank_transaction_id|bank_txn_id|vendor_reference_id|reference_id|ref_id|utr|rrn|order_id|invoice_number|rid|trn|crn)\b",
            r"\b(transaction\s+id|bank\s+transaction\s+id|vendor\s+ref|reference\s+no|transaction\s+number)\b"
        ]
        categorical_reject_patterns = [
            r"\b(branch|store|outlet|location|status|state|mode|channel|type|date|time|remarks?|description|s\.?no|serial|index|currency|country|city)\b"
        ]

        def is_identity_col(col_name: str) -> bool:
            c = col_name.lower().strip()
            if any(re.search(pat, c, re.I) for pat in categorical_reject_patterns):
                return False
            return any(re.search(pat, c, re.I) for pat in identity_patterns)

        def is_categorical(col_name: str) -> bool:
            c = col_name.lower().strip()
            return any(re.search(pat, c, re.I) for pat in categorical_reject_patterns)

        candidate_cols_a = [h for h in headers_a if not is_categorical(h)]
        candidate_cols_b = [h for h in headers_b if not is_categorical(h)]

        # Precompute uniqueness sets
        sets_a: Dict[str, Set[str]] = {}
        for ca in candidate_cols_a:
            vals = {self._clean_key_val(r.get(ca)) for r in rows_a if r.get(ca) and self._clean_key_val(r.get(ca))}
            if vals:
                sets_a[ca] = vals

        sets_b: Dict[str, Set[str]] = {}
        for cb in candidate_cols_b:
            vals = {self._clean_key_val(r.get(cb)) for r in rows_b if r.get(cb) and self._clean_key_val(r.get(cb))}
            if vals:
                sets_b[cb] = vals

        # Score candidate pairs
        scored_pairs = []
        for ca, set_a in sets_a.items():
            uniq_ratio_a = len(set_a) / max(len(rows_a), 1)
            is_id_a = is_identity_col(ca)
            for cb, set_b in sets_b.items():
                uniq_ratio_b = len(set_b) / max(len(rows_b), 1)
                is_id_b = is_identity_col(cb)

                overlap = len(set_a.intersection(set_b))
                score = 0.0

                if is_id_a and is_id_b:
                    score += 50.0
                elif is_id_a or is_id_b:
                    score += 25.0

                # Check alias mapping
                for alias_group in self.KEY_ALIASES:
                    if any(ka.lower() in ca.lower() for ka in alias_group["keys_a"]) and any(kb.lower() in cb.lower() for kb in alias_group["keys_b"]):
                        score += 40.0
                        break

                # Exact column name bonus (only if not categorical)
                if ca.strip().lower() == cb.strip().lower():
                    score += 30.0

                # High uniqueness bonus
                if uniq_ratio_a >= 0.7 and uniq_ratio_b >= 0.7:
                    score += 30.0
                elif uniq_ratio_a < 0.2 or uniq_ratio_b < 0.2:
                    score -= 50.0  # Penalize non-unique columns like branch code

                # Overlap score
                score += min(overlap * 2.0, 50.0)

                if score > 0 and (overlap >= 2 or (is_id_a and is_id_b and uniq_ratio_a > 0.5)):
                    scored_pairs.append({
                        "key_a": ca,
                        "key_b": cb,
                        "overlap": overlap,
                        "score": score,
                        "uniq_a": uniq_ratio_a,
                        "uniq_b": uniq_ratio_b
                    })

        scored_pairs.sort(key=lambda x: x["score"], reverse=True)

        if scored_pairs and scored_pairs[0]["score"] >= 40:
            best = scored_pairs[0]
            return {
                "found": True,
                "key_a": best["key_a"],
                "key_b": best["key_b"],
                "overlap_count": best["overlap"],
                "confidence": "HIGH",
                "reason": f"Both columns identify individual transactions with verified value overlap ({best['key_a']} ↔ {best['key_b']}).",
                "method": "semantic_overlap_ranking"
            }

        # Fallback to Known Aliases if found
        for alias_group in self.KEY_ALIASES:
            for ka_cand in alias_group["keys_a"]:
                for kb_cand in alias_group["keys_b"]:
                    ka = self._find_col(headers_a, ka_cand)
                    kb = self._find_col(headers_b, kb_cand)
                    if ka and kb and not (is_categorical(ka) or is_categorical(kb)):
                        return {
                            "found": True,
                            "key_a": ka,
                            "key_b": kb,
                            "confidence": "HIGH",
                            "reason": f"Matched canonical transaction identity pair ({ka} ↔ {kb}).",
                            "method": "alias_pattern"
                        }

        return {
            "found": False,
            "headers_a": headers_a,
            "headers_b": headers_b,
            "method": "ambiguous"
        }

    def compare_workbooks(
        self,
        file_path_a: str,
        file_path_b: str,
        key_column_a: Optional[str] = None,
        key_column_b: Optional[str] = None
    ) -> Dict[str, Any]:
        """Compares two Excel workbooks and returns full structured reconciliation analysis."""
        key_discovery = self.discover_matching_keys(file_path_a, file_path_b)
        if not key_discovery["found"] and not (key_column_a and key_column_b):
            return {
                "success": False,
                "needs_clarification": True,
                "message": "I found the two transaction files, but I need the matching column to compare them. Which identifier should I use?",
                "candidate_options": ["RID", "Transaction ID", "Vendor Reference ID", "Bank Transaction ID"],
                "headers_a": key_discovery.get("headers_a", []),
                "headers_b": key_discovery.get("headers_b", [])
            }

        final_key_a = key_column_a or key_discovery["key_a"]
        final_key_b = key_column_b or key_discovery["key_b"]

        insp_a = excel_aggregator.inspect_workbook(file_path_a)
        insp_b = excel_aggregator.inspect_workbook(file_path_b)

        sheet_a = list(insp_a.get("sheets", {}).values())[0] if insp_a.get("sheets") else {}
        rows_a = sheet_a.get("valid_rows", [])
        amount_col_a = self._find_amount_col(insp_a.get("headers", []))

        sheet_b = list(insp_b.get("sheets", {}).values())[0] if insp_b.get("sheets") else {}
        rows_b = sheet_b.get("valid_rows", [])
        amount_col_b = self._find_amount_col(insp_b.get("headers", []))

        # Index records from B by key
        map_b: Dict[str, Dict[str, Any]] = {}
        for r in rows_b:
            k_val = r.get(final_key_b)
            k_clean = self._clean_key_val(k_val)
            if k_clean:
                map_b[k_clean] = r

        matched_records: List[Dict[str, Any]] = []
        amount_mismatches: List[Dict[str, Any]] = []
        status_mismatches: List[Dict[str, Any]] = []
        missing_in_b: List[Dict[str, Any]] = []
        visited_b_keys: Set[str] = set()

        for r_a in rows_a:
            k_val_a = r_a.get(final_key_a)
            k_clean = self._clean_key_val(k_val_a)
            if not k_clean:
                continue

            if k_clean in map_b:
                visited_b_keys.add(k_clean)
                r_b = map_b[k_clean]

                # Check Amount
                amt_a = parse_decimal_safe(r_a.get(amount_col_a)) if amount_col_a else None
                amt_b = parse_decimal_safe(r_b.get(amount_col_b)) if amount_col_b else None

                has_amt_diff = (amt_a is not None and amt_b is not None and amt_a != amt_b)

                # Check Status with semantic normalization
                st_a = str(r_a.get("STATUS") or r_a.get("status") or "").strip().upper()
                st_b = str(r_b.get("STATUS") or r_b.get("status") or "").strip().upper()

                success_synonyms = {"AUTH", "AUTHORISED", "AUTHORIZED", "SUCCESS", "SUCCESSFUL", "PAID", "SETTLED", "COMPLETED", "APPROVED"}
                both_success = (st_a in success_synonyms and st_b in success_synonyms)
                has_st_diff = (st_a and st_b and st_a != st_b and not both_success)

                if has_amt_diff:
                    amount_mismatches.append({
                        "key": str(k_val_a),
                        "row_a": r_a,
                        "row_b": r_b,
                        "amount_a": amt_a,
                        "amount_b": amt_b,
                        "diff": abs((amt_a or Decimal(0)) - (amt_b or Decimal(0)))
                    })
                elif has_st_diff:
                    status_mismatches.append({
                        "key": str(k_val_a),
                        "row_a": r_a,
                        "row_b": r_b,
                        "status_a": st_a,
                        "status_b": st_b
                    })
                else:
                    matched_records.append({
                        "key": str(k_val_a),
                        "row_a": r_a,
                        "row_b": r_b,
                        "amount": amt_a or amt_b
                    })
            else:
                missing_in_b.append({
                    "key": str(k_val_a),
                    "row": r_a
                })

        missing_in_a: List[Dict[str, Any]] = []
        for k_clean, r_b in map_b.items():
            if k_clean not in visited_b_keys:
                missing_in_a.append({
                    "key": str(r_b.get(final_key_b)),
                    "row": r_b
                })

        filename_a = os.path.basename(file_path_a)
        filename_b = os.path.basename(file_path_b)

        # Generate 5-sheet report
        report_bytes = self._generate_mismatch_report_xlsx(
            filename_a=filename_a,
            filename_b=filename_b,
            key_a=final_key_a,
            key_b=final_key_b,
            matched=matched_records,
            missing_in_b=missing_in_b,
            missing_in_a=missing_in_a,
            amount_mismatches=amount_mismatches,
            status_mismatches=status_mismatches,
            headers_a=insp_a.get("headers", []),
            headers_b=insp_b.get("headers", [])
        )

        report_filename = "EBO_UPI_Mismatch_Report.xlsx"

        return {
            "success": True,
            "needs_clarification": False,
            "file_a": filename_a,
            "file_b": filename_b,
            "key_a": final_key_a,
            "key_b": final_key_b,
            "total_records_a": len(rows_a),
            "total_records_b": len(rows_b),
            "matched_count": len(matched_records),
            "missing_in_b_count": len(missing_in_b),
            "missing_in_a_count": len(missing_in_a),
            "amount_mismatch_count": len(amount_mismatches),
            "status_mismatch_count": len(status_mismatches),
            "total_mismatches": len(amount_mismatches) + len(status_mismatches) + len(missing_in_b) + len(missing_in_a),
            "report_filename": report_filename,
            "report_bytes": report_bytes,
            "report_size": len(report_bytes)
        }

    def _generate_mismatch_report_xlsx(
        self,
        filename_a: str,
        filename_b: str,
        key_a: str,
        key_b: str,
        matched: List[Dict[str, Any]],
        missing_in_b: List[Dict[str, Any]],
        missing_in_a: List[Dict[str, Any]],
        amount_mismatches: List[Dict[str, Any]],
        status_mismatches: List[Dict[str, Any]],
        headers_a: List[str],
        headers_b: List[str]
    ) -> bytes:
        """Generates a professional 5-sheet reconciliation Excel workbook."""
        wb = openpyxl.Workbook()

        header_fill = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        title_font = Font(name="Calibri", size=14, bold=True, color="1E3A5F")
        sub_font = Font(name="Calibri", size=10, italic=True, color="555555")
        thin_border = Border(
            left=Side(style='thin', color='E0E0E0'),
            right=Side(style='thin', color='E0E0E0'),
            top=Side(style='thin', color='E0E0E0'),
            bottom=Side(style='thin', color='E0E0E0')
        )

        # 1. Summary Sheet
        ws_sum = wb.active
        ws_sum.title = "Summary"
        ws_sum.cell(row=1, column=1, value="Excel Reconciliation & Mismatch Audit Report").font = title_font
        ws_sum.cell(row=2, column=1, value=f"Comparing: {filename_a} vs {filename_b} | Key: {key_a} ↔ {key_b}").font = sub_font

        summary_kpis = [
            ("Reconciliation Metric", "Count / Value"),
            ("Total Records in File A", f"{len(matched) + len(missing_in_b) + len(amount_mismatches) + len(status_mismatches):,}"),
            ("Total Records in File B", f"{len(matched) + len(missing_in_a) + len(amount_mismatches) + len(status_mismatches):,}"),
            ("Matched Records", f"{len(matched):,}"),
            (f"Missing in {filename_b[:20]}", f"{len(missing_in_b):,}"),
            (f"Missing in {filename_a[:20]}", f"{len(missing_in_a):,}"),
            ("Amount Mismatches", f"{len(amount_mismatches):,}"),
            ("Status Mismatches", f"{len(status_mismatches):,}"),
            ("Total Discrepancies", f"{len(amount_mismatches) + len(status_mismatches) + len(missing_in_b) + len(missing_in_a):,}")
        ]

        for r_idx, (k, v) in enumerate(summary_kpis, start=4):
            c1 = ws_sum.cell(row=r_idx, column=1, value=k)
            c2 = ws_sum.cell(row=r_idx, column=2, value=v)
            if r_idx == 4:
                c1.fill = header_fill
                c1.font = header_font
                c2.fill = header_fill
                c2.font = header_font
            else:
                c1.border = thin_border
                c2.border = thin_border
                c2.alignment = Alignment(horizontal="right")
        ws_sum.column_dimensions['A'].width = 35
        ws_sum.column_dimensions['B'].width = 25

        # 2. Matched Sheet
        ws_mat = wb.create_sheet(title="Matched")
        ws_mat.cell(row=1, column=1, value="S.No")
        ws_mat.cell(row=1, column=2, value=f"Key ({key_a})")
        ws_mat.cell(row=1, column=3, value="Amount")
        for col_i in range(1, 4):
            c = ws_mat.cell(row=1, column=col_i)
            c.fill = header_fill
            c.font = header_font
        for r_idx, rec in enumerate(matched[:2000], start=2):
            ws_mat.cell(row=r_idx, column=1, value=r_idx - 1).border = thin_border
            ws_mat.cell(row=r_idx, column=2, value=rec["key"]).border = thin_border
            ws_mat.cell(row=r_idx, column=3, value=float(rec["amount"]) if rec.get("amount") else "").border = thin_border
        ws_mat.column_dimensions['A'].width = 10
        ws_mat.column_dimensions['B'].width = 30
        ws_mat.column_dimensions['C'].width = 20

        # 3. Missing in UPI (File A)
        ws_mis_a = wb.create_sheet(title="Missing_In_UPI")
        ws_mis_a.cell(row=1, column=1, value="S.No")
        ws_mis_a.cell(row=1, column=2, value=f"Missing Key in {filename_a[:15]}")
        for col_i in (1, 2):
            c = ws_mis_a.cell(row=1, column=col_i)
            c.fill = header_fill
            c.font = header_font
        for r_idx, rec in enumerate(missing_in_a[:2000], start=2):
            ws_mis_a.cell(row=r_idx, column=1, value=r_idx - 1).border = thin_border
            ws_mis_a.cell(row=r_idx, column=2, value=rec["key"]).border = thin_border
        ws_mis_a.column_dimensions['A'].width = 10
        ws_mis_a.column_dimensions['B'].width = 35

        # 4. Missing in EBO (File B)
        ws_mis_b = wb.create_sheet(title="Missing_In_EBO")
        ws_mis_b.cell(row=1, column=1, value="S.No")
        ws_mis_b.cell(row=1, column=2, value=f"Missing Key in {filename_b[:15]}")
        for col_i in (1, 2):
            c = ws_mis_b.cell(row=1, column=col_i)
            c.fill = header_fill
            c.font = header_font
        for r_idx, rec in enumerate(missing_in_b[:2000], start=2):
            ws_mis_b.cell(row=r_idx, column=1, value=r_idx - 1).border = thin_border
            ws_mis_b.cell(row=r_idx, column=2, value=rec["key"]).border = thin_border
        ws_mis_b.column_dimensions['A'].width = 10
        ws_mis_b.column_dimensions['B'].width = 35

        # 5. Mismatches (Amount / Status)
        ws_diff = wb.create_sheet(title="Mismatches")
        diff_hdrs = ["S.No", "Key Identifier", "Discrepancy Type", f"Value in {filename_a[:15]}", f"Value in {filename_b[:15]}", "Variance / Diff"]
        for col_i, h in enumerate(diff_hdrs, start=1):
            c = ws_diff.cell(row=1, column=col_i, value=h)
            c.fill = header_fill
            c.font = header_font
        diff_r = 2
        for rec in amount_mismatches:
            ws_diff.cell(row=diff_r, column=1, value=diff_r - 1).border = thin_border
            ws_diff.cell(row=diff_r, column=2, value=rec["key"]).border = thin_border
            ws_diff.cell(row=diff_r, column=3, value="AMOUNT_MISMATCH").border = thin_border
            ws_diff.cell(row=diff_r, column=4, value=float(rec["amount_a"]) if rec.get("amount_a") else "").border = thin_border
            ws_diff.cell(row=diff_r, column=5, value=float(rec["amount_b"]) if rec.get("amount_b") else "").border = thin_border
            ws_diff.cell(row=diff_r, column=6, value=float(rec["diff"]) if rec.get("diff") else "").border = thin_border
            diff_r += 1
        for rec in status_mismatches:
            ws_diff.cell(row=diff_r, column=1, value=diff_r - 1).border = thin_border
            ws_diff.cell(row=diff_r, column=2, value=rec["key"]).border = thin_border
            ws_diff.cell(row=diff_r, column=3, value="STATUS_MISMATCH").border = thin_border
            ws_diff.cell(row=diff_r, column=4, value=rec.get("status_a", "")).border = thin_border
            ws_diff.cell(row=diff_r, column=5, value=rec.get("status_b", "")).border = thin_border
            ws_diff.cell(row=diff_r, column=6, value="-").border = thin_border
            diff_r += 1

        ws_diff.column_dimensions['A'].width = 10
        ws_diff.column_dimensions['B'].width = 30
        ws_diff.column_dimensions['C'].width = 20
        ws_diff.column_dimensions['D'].width = 22
        ws_diff.column_dimensions['E'].width = 22
        ws_diff.column_dimensions['F'].width = 18

        buf = io.BytesIO()
        wb.save(buf)
        wb.close()
        return buf.getvalue()

    def _find_col(self, headers: List[str], target: str) -> Optional[str]:
        for h in headers:
            if h.strip().lower() == target.strip().lower():
                return h
        for h in headers:
            if target.strip().lower() in h.strip().lower():
                return h
        return None

    def _find_amount_col(self, headers: List[str]) -> Optional[str]:
        for cand in ["amount", "total amount", "transaction amount", "requested amount", "settled_amount"]:
            for h in headers:
                if cand == h.strip().lower():
                    return h
        for cand in ["amount", "total"]:
            for h in headers:
                if cand in h.strip().lower():
                    return h
        return None


excel_comparator = ExcelComparator()
