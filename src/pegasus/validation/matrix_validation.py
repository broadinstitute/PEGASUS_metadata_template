from __future__ import annotations

import petl as etl
import pandas as pd
import pandera as pa
import json
from pathlib import Path
from typing import List

from pegasus.schema.peg_matrix_schem import MatrixIdentifiesPandera
from pegasus.schema.constant import other_genetic_identifiers, evidence_category, matrix_identifier_keys

class PegMatrixValidation: 

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.errors = []
        self.matrix_identifier_keys = matrix_identifier_keys
        self.evidence_category_keys = evidence_category
        self.Other_identifiers = other_genetic_identifiers
        self._column_hints = {
            name: col.description
            for name, col in MatrixIdentifiesPandera.to_schema().columns.items()
            if col.description
        }
        self.headers = self.read_header()

    
    def read_header(self) -> List[str]:
        """Read the header of a TSV file."""
        table = etl.fromcsv(self.file_path,delimiter="\t")
        header = etl.header(table)
        return list(header)

    def classify_headers(self) -> dict[str, list[str]]:
        """Classify headers into all categories in one pass."""

        headers = self.headers

        genetic = list(dict.fromkeys(x for x in headers if x in self.matrix_identifier_keys))

        other_id =[x for x in headers if any(x.startswith(prefix) for prefix in self.Other_identifiers)]

        int_cols = [x for x in headers if x.startswith("INT_")]

        evidence = [x for x in headers
                    if x in self.evidence_category_keys
                    or ("_" in x and x.split("_", 1)[0] in self.evidence_category_keys)]

        other = [x for x in headers if x not in genetic + other_id + int_cols + evidence]
    
        return {
            "genetic": genetic,
            "other_identifiers": other_id,
            "int": int_cols,
            "evidence": evidence,
            "other": other,
        }

    def read_fixed_columns(self, fields: list) -> pd.DataFrame:
        table = etl.fromcsv(self.file_path, delimiter="\t")
        table_fixed = etl.cut(table, fields)
        df = etl.todataframe(table_fixed)
        str_cols = df.select_dtypes(include="object").columns
        df[str_cols] = df[str_cols].apply(lambda col: col.str.strip())
        return df
    
    def _collect_row_errors(
        self,
        err: pa.errors.SchemaErrors,
        row_offset: int = 0,
        limit_per_group: int = 50,
    ) -> List[dict]:
        failure_cases = err.failure_cases
        if failure_cases.empty:
            return []

        grouped_errors: List[dict] = []
        grouped = failure_cases.groupby(["column", "check"], dropna=False)
        for (column, check), group in grouped:
            rows = []
            values = []
            for _, row in group.iterrows():
                index = row.get("index")
                if isinstance(index, int):
                    row_number = index + 1 + row_offset
                else:
                    row_number = None
                rows.append(row_number)
                values.append(row.get("failure_case"))
                if len(rows) >= limit_per_group:
                    break

            grouped_errors.append(
                {
                    "column": column,
                    "check": check,
                    "hint": self._column_hints.get(column),
                    "rows": rows,
                    "values": values,
                }
            )

        return grouped_errors

    def _validate_fixed_df(
        self,
        dataframe: pd.DataFrame,
        message: str = "Data table is invalid",
        row_offset: int = 0,
        error_limit: int = 10,
    ) -> dict:
        """Validate a pandas dataframe using Pandera.

        Returns a dict with summary + error list for frontend use.
        """
        try:
            MatrixIdentifiesPandera.validate(dataframe, lazy=True)
        except pa.errors.SchemaErrors as err:
            failure_cases = err.failure_cases
            by_column = (
                failure_cases["column"]
                .value_counts(dropna=False)
                .to_dict()
                if "column" in failure_cases
                else {}
            )
            errors = self._collect_row_errors(
                err,
                row_offset=row_offset,
                limit_per_group=error_limit,
            )
            return {
                "valid": False,
                "message": message,
                "error_count": int(len(failure_cases)),
                "by_column": by_column,
                "errors": errors,
            }

        return {
            "valid": True,
            "message": "Data table is valid.",
            "error_count": 0,
            "errors": [],
        }

    def validate_fixed_columns(
        self,
        to_validate_df: pd.DataFrame,
        first_n: int = 50000,
        progress: bool = False,
    ) -> dict:
        first_chunk = to_validate_df.iloc[:first_n]
        rest_chunk = to_validate_df.iloc[first_n:]

        if progress:
            print(f"Validating first {min(len(first_chunk), first_n)} rows...")
        result = self._validate_fixed_df(
            first_chunk,
            message="Fixed-column validation failed in first chunk.",
            row_offset=0,
        )
        if not result["valid"]:
            return result

        if not rest_chunk.empty:
            if progress:
                print(f"First chunk passed. Validating remaining {len(rest_chunk)} rows...")
            result = self._validate_fixed_df(
                rest_chunk,
                message="Fixed-column validation failed in remaining rows.",
                row_offset=first_n,
            )
            if not result["valid"]:
                return result

        return {
            "valid": True,
            "message": "Fixed columns validated.",
            "error_count": 0,
            "errors": [],
        }
    
    def validate_pegmatrix(self, progress: bool = False):
        # check if others exist, if exist, warn user they are not in schema
        if progress:
            print("Step 1/4: Reading header and classifying columns...")
        header = self.read_header()
        classified_headers = self.classify_headers()
        if classified_headers["other"]:
            self.errors.append(
                {
                    "step": "1/4 - Header Classification",
                    "type": "warning",
                    "message": f"The following columns are not recognized and will be ignored in validation: {classified_headers['other']}",
                }
            )
        else:
            self.errors.append(
                {
                    "step": "1/4 - Header Classification",
                    "type": "info",
                    "message": "All columns are recognized.",
                }
            )

        # Check if there is at least one INT_column
        if progress:
            print("Step 2/4: Validating INT columns...")
        int_columns = classified_headers["int"]
        if len(int_columns) == 0:
            self.errors.append(
                {
                    "step": "2/4 - INT Column Validation",
                    "type": "error",
                    "message": f"No INT_column found. At least one INT_column is required.",
                }
            )
            return self.errors
        else:
            self.errors.append(
                {
                    "step": "2/4 - INT Column Validation",
                    "type": "info",
                    "message": f"Found {len(int_columns)} INT_column(s).",
                }
            )
        
        # Check if there are more than 2 evidence columns
        if progress:
            print("Step 3/4: Validating evidence columns...")
        evidence_columns = classified_headers["evidence"]
        if len(evidence_columns) < 2:
            self.errors.append(
                {
                    "step": "3/4 - Evidence Column Validation",
                    "type": "error",
                    "message": f"Less than 2 evidence columns found. At least two evidence columns are required.",
                }
            )
            return self.errors
        else:
            self.errors.append(
                {
                    "step": "3/4 - Evidence Column Validation",
                    "type": "info",
                    "message": f"Found {len(evidence_columns)} evidence column(s).",
                }
            )
        
        # Validate fixed columns
        if progress:
            print("Step 4/4: Validating fixed columns...")
        fixed_df = self.read_fixed_columns(fields=list(classified_headers["genetic"]))
        fixed_validation_result = self.validate_fixed_columns(fixed_df, progress=progress)
        if not fixed_validation_result["valid"]:
            self.errors.append(
                {
                    "step": "4/4 - Fixed Column Validation",
                    "type": "error",
                    "message": fixed_validation_result["message"],
                    "details": fixed_validation_result,
                }
            )
            return self.errors
        else:
            self.errors.append(
                {
                    "step": "4/4 - Fixed Column Validation",
                    "type": "info",
                    "message": "All fixed columns are valid.",
                }
            )

        return self.errors
