"""Convert Excel metadata templates to JSON format."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd


def _is_prefilled_zero(value: Any) -> bool:
    if pd.isna(value):
        return True
    return str(value).strip() in {"0", "0.0"}


def _rows_from_df(df: pd.DataFrame) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        row_dict: dict[str, Any] = {}
        for col in df.columns:
            value = row[col]
            if pd.isna(value):
                continue
            row_dict[col] = value
        if row_dict:
            data.append(row_dict)
    return data


def _enrich_rows(
    rows: list[dict[str, Any]],
    source_map: dict[str, dict[str, Any]],
    method_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for row in rows:
        row_out = dict(row)
        source_tag = row.get("source_tag")
        if source_tag:
            source_info = source_map.get(source_tag)
            if source_info:
                row_out["source"] = source_info
        method_tag = row.get("method_tag")
        if method_tag:
            method_info = method_map.get(method_tag)
            if method_info:
                row_out["method"] = method_info
        enriched.append(row_out)
    return enriched


def _warn_unused_tags(
    source_map: dict[str, dict[str, Any]],
    method_map: dict[str, dict[str, Any]],
    used_source_tags: set[str],
    used_method_tags: set[str],
) -> None:
    unused_sources = sorted(set(source_map.keys()) - used_source_tags)
    if unused_sources:
        print(
            f"Warning: Source tags not used in Evidence/Integration: {unused_sources}",
            file=sys.stderr,
        )
    unused_methods = sorted(set(method_map.keys()) - used_method_tags)
    if unused_methods:
        print(
            f"Warning: Method tags not used in Evidence/Integration: {unused_methods}",
            file=sys.stderr,
        )
def xlsx_to_json(xlsx_path: Path | str, output_path: Path | str | None = None) -> dict[str, Any]:
    """Convert Excel metadata template to JSON format.
    
    Args:
        xlsx_path: Path to the Excel file
        output_path: Optional path to save JSON file. If None, returns dict only.
    
    Returns:
        Dictionary with sheet names as keys and data as lists of dicts
    """
    xlsx_path = Path(xlsx_path)
    if not xlsx_path.exists():
        raise FileNotFoundError(f"Excel file not found: {xlsx_path}")
    
    result: dict[str, Any] = {}
    raw_data: dict[str, list[dict[str, Any]]] = {}
    
    # Read all sheets from Excel
    excel_file = pd.ExcelFile(xlsx_path)
    
    for sheet_name in excel_file.sheet_names:
        # Skip hidden validation sheets
        if sheet_name.lower() == "validation":
            continue
        
        # Get headers from row 1 (index 1 in original, but we skipped 3 rows)
        # Re-read to get headers properly
        df_with_headers = pd.read_excel(excel_file, sheet_name=sheet_name, header=1)
        # Skip the example row (row 2, index 2)
        df_with_headers = df_with_headers.iloc[1:]

        if sheet_name.lower().strip() == "evidence" and "evidence_category" in df_with_headers.columns:
            mask = df_with_headers["evidence_category"].apply(lambda v: not _is_prefilled_zero(v))
            df_with_headers = df_with_headers[mask]

        raw_data[sheet_name] = _rows_from_df(df_with_headers)

    source_map = {
        row["source_tag"]: row
        for row in raw_data.get("Source", [])
        if row.get("source_tag") is not None
    }
    method_map = {
        row["method_tag"]: row
        for row in raw_data.get("Method", [])
        if row.get("method_tag") is not None
    }

    used_source_tags: set[str] = set()
    used_method_tags: set[str] = set()
    for sheet in ("Evidence", "Integration"):
        for row in raw_data.get(sheet, []):
            source_tag = row.get("source_tag")
            if source_tag:
                used_source_tags.add(source_tag)
            method_tag = row.get("method_tag")
            if method_tag:
                used_method_tags.add(method_tag)

    for sheet_name in excel_file.sheet_names:
        if sheet_name.lower() == "validation":
            continue
        if sheet_name.lower().strip() in {"evidence", "integration"}:
            result[sheet_name] = _enrich_rows(
                raw_data.get(sheet_name, []),
                source_map,
                method_map,
            )
        elif sheet_name.lower().strip() in {"source", "method"}:
            continue
        else:
            result[sheet_name] = raw_data.get(sheet_name, [])

    _warn_unused_tags(source_map, method_map, used_source_tags, used_method_tags)
    
    # Save to file if output path provided
    if output_path:
        output_path = Path(output_path)
        with output_path.open("w") as f:
            json.dump(result, f, indent=2, default=str)
    
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m pegasus.template_convert.json_builder <xlsx_file> [output_json]")
        sys.exit(1)
    
    xlsx_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    result = xlsx_to_json(xlsx_file, output_file)
    if not output_file:
        print(json.dumps(result, indent=2, default=str))
