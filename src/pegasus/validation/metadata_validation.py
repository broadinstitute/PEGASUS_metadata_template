"""Simple metadata validation for PEGASUS Excel templates."""

from __future__ import annotations

import datetime
import re
import warnings
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, ValidationError

from pegasus.schema.core import (
    AnyEvidenceCategory,
    GeneEvidenceCategory,
    VariantEvidenceCategory,
)
from pegasus.schema.peg_metadata_schema.metadata_basic_schema import (
    DatasetDescription,
    GenomicIdentifier,
)
from pegasus.schema.peg_metadata_schema.metadata_evidence_schema import Evidence
from pegasus.schema.peg_metadata_schema.metadata_integration_schme import Integration
from pegasus.schema.peg_metadata_schema.metadata_method_schema import Method
from pegasus.schema.peg_metadata_schema.metadata_source_schema import Source


# Identifies the most useful field to surface in row-level error messages per sheet
_SHEET_KEY_FIELDS: dict[str, str] = {
    "DatasetDescription": "trait_description",
    "Evidence": "evidence_category",
    "Integration": "column_header",
    "Source": "source_tag",
    "Method": "method_tag",
}

# Pydantic v2 error types where showing an expected-format example adds the most value
_FORMAT_ERROR_TYPES = frozenset({
    "string_pattern_mismatch",
    "string_too_long",
    "literal_error",
    "enum",
    "no_union_match",
    "union_tag_invalid",
    "value_error",
})


def _format_excel_datetime(value: datetime.datetime | datetime.date) -> str:
    """Render an Excel date cell as a string.

    Date-formatted cells come back as datetimes with a midnight time component;
    those read better as a plain ISO date than as a full timestamp. pandas
    Timestamps are datetime subclasses and so are covered here too.
    """
    if isinstance(value, datetime.datetime):
        if (value.hour, value.minute, value.second, value.microsecond) == (0, 0, 0, 0):
            return value.date().isoformat()
        return value.isoformat()
    return value.isoformat()


class PegMetadataValidation:
    """Validate PEGASUS metadata Excel files."""

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.errors: list[dict] = []
        self.sheet_data: dict[str, Any] = {}
        self.sheet_models = {
            "DatasetDescription": DatasetDescription,
            "GenomicIdentifier": GenomicIdentifier,
            "Evidence": Evidence,
            "Integration": Integration,
            "Source": Source,
            "Method": Method,
        }

    def validate_metadata(self, error_limit: int = 50) -> list[dict]:
        """Validate the metadata Excel file."""
        try:
            # Suppress openpyxl data validation warning
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message=".*Data Validation extension is not supported.*")
                excel_file = pd.ExcelFile(self.file_path)
        except Exception as e:
            self.errors.append({
                "step": "File Reading",
                "type": "error",
                "message": f"Could not read Excel file: {e}",
            })
            return self.errors
        
        # Check required sheets exist
        available_sheets = {name.lower().strip(): name for name in excel_file.sheet_names}
        missing_sheets = [
            name for name in self.sheet_models if name.lower().strip() not in available_sheets
        ]

        if missing_sheets:
            self.errors.append({
                "step": "Sheet Validation",
                "type": "error",
                "message": f"Missing required sheets: {missing_sheets}",
            })
            return self.errors
        
        # Validate each sheet
        for sheet_name, model in self.sheet_models.items():
            sheet_key = sheet_name.lower().strip()
            
            if sheet_key not in available_sheets:
                continue
            
            data = self._validate_sheet(
                excel_file, available_sheets[sheet_key], model, error_limit
            )
            self.sheet_data[sheet_name] = data

        # Cross-sheet validation
        self._validate_cross_sheet()

        return self.errors

    def _validate_sheet(
        self,
        excel_file: pd.ExcelFile,
        sheet_name: str,
        model: type[BaseModel],
        error_limit: int,
    ) -> dict[str, Any]:
        """Validate a single sheet."""
        # Read sheet (skip first 3 rows: description, header, example)
        try:
            df = pd.read_excel(excel_file, sheet_name=sheet_name, header=1)
            df = df.iloc[1:]  # Skip example row
            df = df.dropna(how="all")  # Remove completely empty rows
        except Exception as e:
            self.errors.append({
                "step": f"{sheet_name} - Sheet Reading",
                "type": "error",
                "message": f"Could not read sheet: {e}",
            })
            return {
                "records": [],
                "valid_records": [],
                "found_fields": set(),
                "required_fields": set(),
            }

        # Build header mapping and example lookup (used to enrich error messages)
        header_map = {}
        field_examples: dict[str, Any] = {}
        for field_name, field in model.model_fields.items():
            extra = field.json_schema_extra or {}
            header = str(extra.get("header", field_name))
            header_map[header.lower()] = field_name
            header_map[str(field_name).lower()] = field_name
            if "example" in extra:
                field_examples[field_name] = extra["example"]

        # Map columns
        column_map = {}
        unknown_cols = []
        for col in df.columns:
            if pd.isna(col) or str(col).startswith("Unnamed"):
                continue
            col_str = str(col).strip() if col is not None else ""
            col_lower = col_str.lower()
            field_name = header_map.get(col_lower)
            if field_name:
                column_map[col] = field_name
            else:
                unknown_cols.append(str(col))

        # Check for missing required fields
        required_fields = {
            name
            for name, field in model.model_fields.items()
            if field.is_required() and field.default is None
        }
        found_fields = set(column_map.values())
        missing_required = required_fields - found_fields

        if missing_required:
            self.errors.append({
                "step": f"{sheet_name} - Header Validation",
                "type": "error",
                "message": f"Missing required columns: {sorted(missing_required)}",
            })
            return {
                "records": [],
                "valid_records": [],
                "found_fields": set(),
                "required_fields": required_fields,
            }

        if unknown_cols:
            self.errors.append({
                "step": f"{sheet_name} - Header Validation",
                "type": "warning",
                "message": f"Unknown columns (ignored): {unknown_cols}",
            })
        else:
            self.errors.append({
                "step": f"{sheet_name} - Header Validation",
                "type": "info",
                "message": "All required columns found.",
            })

        # Rename columns and validate rows
        df = df.rename(columns=column_map)
        df = df[[c for c in df.columns if c in found_fields]]
        df = self._drop_prefilled_rows(sheet_name, df)

        records = []
        valid_records = []
        row_errors = []

        for idx, row in df.iterrows():
            record = {}
            for field_name in found_fields:
                value = row.get(field_name)
                if pd.isna(value) or (isinstance(value, str) and value.strip().upper() in ("NA", "N/A", "NONE", "")):
                    record[field_name] = None
                else:
                    # Must check bool before int/float — bool is a subclass of int
                    if isinstance(value, bool):
                        record[field_name] = value
                    elif isinstance(value, str) and value.strip().lower() in ("true", "yes"):
                        record[field_name] = True
                    elif isinstance(value, str) and value.strip().lower() in ("false", "no"):
                        record[field_name] = False
                    elif isinstance(value, (datetime.datetime, datetime.date)):
                        # Excel date-formatted cells arrive as datetimes, which
                        # would otherwise fail every string-typed field.
                        record[field_name] = _format_excel_datetime(value)
                    elif isinstance(value, float) and value.is_integer():
                        # e.g. Excel reads 2019 as 2019.0 — keep as integer string
                        record[field_name] = str(int(value))
                    elif isinstance(value, (int, float)):
                        record[field_name] = str(value)
                    else:
                        # Strip leading/trailing whitespace from strings silently
                        record[field_name] = value.strip() if isinstance(value, str) else value

            if not any(v is not None for v in record.values()):
                continue  # Skip completely empty rows

            records.append(record)

            try:
                model.model_validate(record)
                valid_records.append(record)
            except ValidationError as exc:
                key_field = _SHEET_KEY_FIELDS.get(sheet_name)
                key_value = record.get(key_field) if key_field else None
                row_err: dict[str, Any] = {
                    # read_excel(header=1) puts index label 0 at spreadsheet row 3.
                    # The iloc[1:] above drops the example row but preserves the
                    # original labels, so this offset already accounts for it.
                    "row": int(idx) + 3,
                }
                if key_value is not None:
                    row_err["key"] = f"{key_field}={key_value!r}"
                row_err["error"] = [
                    self._enrich_error(e, field_examples)
                    for e in self._deduplicate_errors(exc.errors())
                ]
                row_errors.append(row_err)
                if len(row_errors) >= error_limit:
                    break

        if row_errors:
            self.errors.append({
                "step": f"{sheet_name} - Row Validation",
                "type": "error",
                "message": "Validation failed for one or more rows.",
                "details": row_errors,
            })
        else:
            self.errors.append({
                "step": f"{sheet_name} - Row Validation",
                "type": "info",
                "message": "All rows validated successfully.",
            })

        return {
            "records": records,
            "valid_records": valid_records,
            "found_fields": found_fields,
            "required_fields": required_fields,
        }

    @staticmethod
    def _deduplicate_errors(errors: list[dict]) -> list[dict]:
        """Collapse multiple Pydantic errors for the same field into one.

        Union types (e.g. GCST | PMID | HttpUrl | DOI) produce one error per
        branch when all branches fail, each with a different loc path such as
        ('gwas_source',), ('gwas_source', 'function-wrap[wrap_val()]'), etc.
        We group by the first loc element (the field name) so each field is
        reported exactly once, keeping the most specific error.
        """
        seen: dict[str, dict] = {}
        for e in errors:
            loc = e.get("loc", ())
            key = str(loc[0]) if loc else ""
            if key not in seen:
                seen[key] = e
            else:
                # Prefer a concrete string pattern error over generic union/URL errors
                existing_type = seen[key].get("type", "")
                new_type = e.get("type", "")
                if new_type == "string_pattern_mismatch" and existing_type != "string_pattern_mismatch":
                    seen[key] = e
        return list(seen.values())

    @staticmethod
    def _enrich_error(e: dict, field_examples: dict[str, Any]) -> dict:
        """Return an enriched error dict with the failing value and, for format
        errors, a human-readable expected-format hint drawn from the schema example."""
        loc = list(e.get("loc", []))
        field_name = str(loc[0]) if loc else None
        error_type = e.get("type", "")
        entry: dict[str, Any] = {
            # Show only the field name — union branch paths (e.g. 'function-wrap[wrap_val()]') add noise
            "loc": [loc[0]] if loc else loc,
            "msg": e.get("msg", ""),
        }
        # For a missing field pydantic reports the whole row as the input, which
        # would dump every cell into the message. The field name already says it.
        if error_type != "missing":
            # repr() makes hidden whitespace (spaces, tabs) visible in the output
            entry["value"] = repr(e.get("input"))
        if field_name and error_type in _FORMAT_ERROR_TYPES:
            example = field_examples.get(field_name)
            if example is not None:
                entry["expected_example"] = str(example)
        # Only pattern-constrained fields (GCST, PMID, rsID, ...) forbid internal
        # whitespace. Enum and Literal fields have legitimate values containing
        # spaces — "Molecular QTL" — so the hint would be actively wrong there.
        if error_type == "string_pattern_mismatch" and isinstance(e.get("input"), str):
            if re.search(r"\s", e["input"]):
                example = field_examples.get(field_name) if field_name else None
                example_str = f" The correct format for this field is e.g. '{example}'." if example else ""
                entry["hint"] = (
                    f"Value contains whitespace — spaces inside this field are not allowed.{example_str}"
                )
        return entry

    @staticmethod
    def _drop_prefilled_rows(sheet_name: str, df: pd.DataFrame) -> pd.DataFrame:
        if sheet_name.lower().strip() != "evidence":
            return df
        if "evidence_category" not in df.columns:
            return df
        mask = df["evidence_category"].apply(
            lambda v: not (
                pd.isna(v)
                or str(v).strip() in {"0", "0.0"}
            )
        )
        return df[mask]

    def cross_check_column_names(self) -> dict[str, list[str]]:
        """Return the declared column names from the Evidence and Integration sheets.

        Rows whose ``column_header`` is missing or blank are skipped. A workbook
        can carry residue rows — cells left holding ``#REF!``, for instance —
        that are non-empty enough to survive the empty-row filter but still
        declare no column name. Letting those through puts ``None`` into the
        caller's name sets, which cannot then be ordered against real names.
        """
        headers: dict[str, list[str]] = {}
        for sheet_name in ("Evidence", "Integration"):
            names = []
            for record in self.sheet_data.get(sheet_name, {}).get("records", []):
                name = record.get("column_header")
                if isinstance(name, str) and name.strip():
                    names.append(name.strip())
            headers[sheet_name] = names
        return headers
    
    def return_author_conclusion_rows(self) -> list[dict]:
        """Return rows with author_conclusion=TRUE in Integration sheet."""
        integration_data = self.sheet_data.get("Integration", {}).get("records", [])
        author_conclusion_rows = [
            row for row in integration_data if row.get("author_conclusion") is True
        ]
        
        if len(author_conclusion_rows) != 1:
            raise ValueError(
                f"Expected exactly one author_conclusion=TRUE row, found {len(author_conclusion_rows)}"
                )
        
        return author_conclusion_rows

    def _validate_cross_sheet(self) -> None:
        """Validate cross-sheet references."""
        evidence = self.sheet_data.get("Evidence", {}).get("valid_records", [])
        integration = self.sheet_data.get("Integration", {}).get("valid_records", [])
        source = self.sheet_data.get("Source", {}).get("valid_records", [])
        method = self.sheet_data.get("Method", {}).get("valid_records", [])

        # Check row counts
        if len(evidence) <= 2:
            self.errors.append({
                "step": "Evidence - Row Count",
                "type": "error",
                "message": f"Evidence must have more than 2 rows. Found {len(evidence)}.",
            })

        if len(integration) <= 1:
            self.errors.append({
                "step": "Integration - Row Count",
                "type": "error",
                "message": f"Integration must have more than 1 row. Found {len(integration)}.",
            })

        # Check author_conclusion
        author_conclusion_count = sum(
            1 for r in integration if r.get("author_conclusion") is True
        )
        if author_conclusion_count != 1:
            self.errors.append({
                "step": "Integration - Author Conclusion",
                "type": "error",
                "message": f"Exactly one row must have author_conclusion=TRUE. Found {author_conclusion_count}.",
            })

        # Check tag references
        source_tags = {r.get("source_tag") for r in source if r.get("source_tag")}
        method_tags = {r.get("method_tag") for r in method if r.get("method_tag")}

        evidence_source_tags = {r.get("source_tag") for r in evidence if r.get("source_tag")}
        evidence_method_tags = {r.get("method_tag") for r in evidence if r.get("method_tag")}
        integration_method_tags = {r.get("method_tag") for r in integration if r.get("method_tag")}

        missing_source = sorted(evidence_source_tags - source_tags)
        if missing_source:
            self.errors.append({
                "step": "Evidence - Tag Reference",
                "type": "error",
                "message": f"source_tag values used in Evidence but missing from Source: {missing_source}",
            })

        missing_method = sorted((evidence_method_tags | integration_method_tags) - method_tags)
        if missing_method:
            self.errors.append({
                "step": "Integration - Tag Reference",
                "type": "error",
                "message": f"method_tag values used but missing from Method: {missing_method}",
            })

# Test code (remove in production)
if __name__ == "__main__":
    test = PegMetadataValidation(file_path=Path("/Users/yueji/Documents/GitHub/PEGASUS_metadata_template/test_data/metadata_peg.xlsx"))
    print(test.validate_metadata())
