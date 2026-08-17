from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Iterable, List

from pydantic import ValidationError

from pegasus.schema.peg_list_schema import PegListSchema, ListIdentifiers
from pegasus.schema.constant import evidence_category, other_genetic_identifiers, list_identifier_keys 

class PegListValidation:
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.errors: List[dict] = []
        self._identifier_aliases = self._build_identifier_aliases()
        self.evidence_category_keys = evidence_category
        self.list_identifier_keys = list_identifier_keys
        self.other_identifiers = other_genetic_identifiers
        self.headers = self.read_header()


    def _build_identifier_aliases(self) -> Dict[str, str]:
        aliases: Dict[str, str] = {}
        for field_name, field_info in ListIdentifiers.model_fields.items():
            aliases[field_name] = field_name
            validation_alias = field_info.validation_alias
            if validation_alias is None:
                continue
            if hasattr(validation_alias, "choices"):
                for alias in validation_alias.choices:
                    aliases[str(alias)] = field_name
            else:
                aliases[str(validation_alias)] = field_name
        return aliases

    def read_header(self) -> List[str]:
        with self.file_path.open("r", newline="") as handle:
            reader = csv.reader(handle, delimiter="\t")
            header = next(reader, [])
        return list(header)

    def classify_headers(self) -> dict[str, list[str]]:
        """Classify headers into all categories in one pass."""

        genetic = []
        other_id = []
        int_cols = []
        evidence = []
        other = []

        genetic = [x for x in self.headers if x in self.list_identifier_keys]
        other_id =[x for x in self.headers if any(x.startswith(prefix) for prefix in self.other_identifiers)]
        int_cols = [x for x in self.headers if x.startswith("INT_")]
        evidence = [x for x in self.headers
                    if x in self.evidence_category_keys
                    or ( "_" in x and x.split("_", 1)[0] in self.evidence_category_keys )
                    ]
        other = [x for x in self.headers if x not in genetic + other_id + int_cols + evidence]
    
        return {
            "genetic": genetic,
            "other_identifiers": other_id,
            "int": int_cols,
            "evidence": evidence,
            "other": other,
        }


    def validate_peglist(self, error_limit: int = 50) -> List[dict]:
        headers = self.read_header()
        classified = self.classify_headers()

        missing_identifiers = []
        for field_name in ListIdentifiers.model_fields:
            if not any(
                self._identifier_aliases[header] == field_name
                for header in classified["genetic"]
            ):
                missing_identifiers.append(field_name)
        
        if missing_identifiers:
            self.errors.append(
                {
                    "step": "1/2 - Header Validation (identifiers)",
                    "type": "error",
                    "message": f"Missing identifier columns: {missing_identifiers}",
                }
            )
            return self.errors
        
        if not classified["int"]:
            self.errors.append(
                {
                    "step": "1/2 - Header Validation (integration)",
                    "type": "error",
                    "message": "No integration columns found.",
                }
            )
            return self.errors

        if not classified["evidence"]:
            self.errors.append(
                {
                    "step": "1/2 - Header Validation",
                    "type": "error",
                    "message": "No evidence columns found.",
                }
            )
            return self.errors
        
        self.errors.append(
            {
                "step": "1/2 - Header Validation",
                "type": "info",
                "message": "Required identifier columns found.",
            }
        )

        if classified["other"]:
            self.errors.append(
                {
                    "step": "1/2 - Header Validation",
                    "type": "warning",
                    "message": f"The following columns are not recognized and will be ignored in validation: {classified['other']}",
                }
            )

        row_errors = []
        with self.file_path.open("r", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            for idx, row in enumerate(reader, start=2):
                identifier: Dict[str, str] = {}
                for header in classified["genetic"]:
                    canonical = self._identifier_aliases[header]
                    identifier[canonical] = row.get(header, "")

                evidence = {
                    h: self._parse_bool_value(row.get(h, ""))
                    for h in classified["evidence"]
                }
                integration = {h: row.get(h, "") for h in classified["int"]}

                try:
                    PegListSchema.model_validate(
                        {
                            "identifier": identifier,
                            "evidence": evidence,
                            "integration": integration,
                        }
                    )
                except ValidationError as exc:
                    row_errors.append(
                        {
                            "row": idx,
                            "error": self._normalize_errors(exc.errors()),
                        }
                    )
                    if len(row_errors) >= error_limit:
                        break

        if row_errors:
            self.errors.append(
                {
                    "step": "2/2 - Row Validation",
                    "type": "error",
                    "message": "Validation failed for one or more rows.",
                    "details": row_errors,
                }
            )
        else:
            self.errors.append(
                {
                    "step": "2/2 - Row Validation",
                    "type": "info",
                    "message": "All rows validated successfully.",
                }
            )

        return self.errors

    @staticmethod
    def _parse_bool_value(value: object) -> object:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized == "true":
                return True
            if normalized == "false":
                return False
        return value

    @staticmethod
    def _normalize_errors(errors: List[dict]) -> List[dict]:
        normalized = []
        for err in errors:
            err = dict(err)
            err.pop("url", None)
            ctx = err.get("ctx")
            if isinstance(ctx, dict):
                err["ctx"] = {
                    key: (str(value) if isinstance(value, Exception) else value)
                    for key, value in ctx.items()
                }
            elif isinstance(ctx, Exception):
                err["ctx"] = str(ctx)
            msg = err.get("msg")
            ctx = err.get("ctx")
            if isinstance(ctx, dict) and "error" in ctx:
                ctx_error = str(ctx.get("error"))
                if ctx_error == msg or (msg and ctx_error and ctx_error in msg):
                    err.pop("ctx", None)
            normalized.append(err)
        return normalized
