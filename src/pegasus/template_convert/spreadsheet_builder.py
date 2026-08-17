from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Literal, Type, get_args, get_origin

import re
import xlsxwriter
from pydantic import BaseModel

from pegasus.schema.peg_metadata_schema.metadata_basic_schema import (
    DatasetDescription,
    GenomicIdentifier,
)
from pegasus.schema.core import (
    AnyEvidenceCategory,
    GeneEvidenceCategory,
    VariantEvidenceCategory,
)
from pegasus.schema.peg_metadata_schema.metadata_evidence_schema import (
    Evidence,
)
from pegasus.schema.peg_metadata_schema.metadata_method_schema import Method
from pegasus.schema.peg_metadata_schema.metadata_integration_schme import (
    Integration,
)
from pegasus.schema.peg_metadata_schema.metadata_source_schema import Source

def _to_text(x) -> str:
    if x is None:
        return ""
    return str(x)

def _longest_word_len(s: str) -> int:
    # Words / tokens; keeps hyphenated chunks reasonably
    tokens = re.findall(r"\S+", s)
    return max((len(t) for t in tokens), default=0)

def _normalize_annotation(annotation: Any) -> Any:
    """Peel off Optional/Annotated wrappers to find the core type for validation."""
    ann = annotation
    while True:
        origin = get_origin(ann)
        args = get_args(ann)

        if origin is Annotated:
            ann = args[0]
            continue

        if origin is Literal:
            break

        if origin is None:
            break

        if args:
            non_none = [a for a in args if a is not type(None)]
            if len(non_none) == 1:
                ann = non_none[0]
                continue

        break

    return ann

def _enum_or_literal_options(annotation: Any) -> list[str] | None:
    """Return dropdown options if the field uses an Enum, Literal, or bool."""
    ann = _normalize_annotation(annotation)

    if get_origin(ann) is Literal:
        return [_to_text(v).upper() if isinstance(v, bool) else _to_text(v) for v in get_args(ann)]

    if isinstance(ann, type) and issubclass(ann, Enum):
        return [_to_text(member.value) for member in ann]

    if ann is bool:
        return ["TRUE", "FALSE"]

    return None

def _allows_none(annotation: Any, default: Any) -> bool:
    """Check if field allows None via type hints or default."""
    if default is None:
        return True
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is Annotated:
        origin = get_origin(args[0])
        args = get_args(args[0])
    if origin is not None:
        if origin is Literal:
            return any(a is None for a in args)
        if str(origin).endswith("Union"):
            return any(a is type(None) for a in args)
    return False

def _col_letter(idx: int) -> str:
    """0-indexed column to Excel letter."""
    name = ""
    i = idx
    while True:
        i, rem = divmod(i, 26)
        name = chr(rem + ord("A")) + name
        if i == 0:
            break
        i -= 1
    return name

def _required_columns_for_model(model: Type[BaseModel]) -> dict[str, str]:
    """Map required header name -> column letter for a model."""
    required: dict[str, str] = {}
    col_idx = 0
    for name, field in model.model_fields.items():
        extra = field.json_schema_extra or {}
        header = extra.get("header", name)
        allow_none = _allows_none(field.annotation, field.default)
        is_required = (field.is_required() and not allow_none) or (
            not field.is_required() and not allow_none and field.default is not None
        )
        if is_required:
            required[header] = _col_letter(col_idx)
        col_idx += 1
    return required

def estimate_column_width(
    description,
    header,
    example,
    min_width: int = 14,
    max_width: int = 40,
    cap: int = 22,  # do NOT let descriptions make columns huge
) -> int:
    desc_s = _to_text(description)
    header_s = _to_text(header)
    example_s = _to_text(example)

    header_len = len(header_s)
    # Descriptions should wrap: only care about the longest "unbreakable" token
    # and cap its influence.
    desc_need = min(_longest_word_len(desc_s) + 2, cap)
    example_len = min(_longest_word_len(example_s) + 2, cap)

    raw = max(header_len + 2, example_len + 2, min_width, desc_need)
    return min(raw, max_width)

def write_model_sheet(
    workbook: xlsxwriter.Workbook,
    model: Type[BaseModel],
    rows: int = 200,
):
    sheet_name = model.__name__[:31]
    ws = workbook.add_worksheet(sheet_name)

    fields = model.model_fields  # Pydantic v2

    headers: list[str] = []
    examples: list[str] = []
    required_flags: list[bool] = []
    descriptions: list[str] = []
    dropdown_options: list[list[str] | None] = []

    for name, field in fields.items():
        extra = field.json_schema_extra or {}
        headers.append(extra.get("header", name))
        examples.append(extra.get("example", ""))
        allow_none = _allows_none(field.annotation, field.default)
        required_flags.append(
            (field.is_required() and not allow_none)
            or (not field.is_required() and not allow_none and field.default is not None)
        )
        desc = getattr(field, "description", None) or extra.get("description", "") or ""
        descriptions.append(str(desc))
        dropdown_options.append(_enum_or_literal_options(field.annotation))

    ncols = len(headers)

    # ---- Formats (match screenshot vibe) ----
    desc_fmt = workbook.add_format(
        {
            "bg_color": "#F2F2F2",
            "font_color": "#8E8E8E",
            "text_wrap": True,
            "valign": "vcenter",
            "align": "left",
            "border": 1,
        }
    )

    header_required_fmt = workbook.add_format(
        {
            "bg_color": "#F8CBAD",  # clearer mandatory highlight
            "bold": True,
            "valign": "vcenter",
            "align": "left",
            "border": 1,
        }
    )

    header_optional_fmt = workbook.add_format(
        {
            "bg_color": "#E7E6E6",  # softer neutral for optional
            "bold": True,
            "valign": "vcenter",
            "align": "left",
            "border": 1,
        }
    )

    example_divider_fmt = workbook.add_format(
        {
            "font_color": "#B7B7B7",
            "text_wrap": True,
            "valign": "vcenter",
            "align": "left",
            "border": 1,
            "bottom": 2,  # thick bottom border
        }
    )

    body_fmt = workbook.add_format({"valign": "vcenter"})

    # ---- Row 1: descriptions ----
    ws.set_row(0, 42)
    for col, desc in enumerate(descriptions):
        ws.write(0, col, desc, desc_fmt)

    # ---- Row 2: headers ----
    ws.set_row(1, 22)
    for col, header in enumerate(headers):
        fmt = header_required_fmt if required_flags[col] else header_optional_fmt
        ws.write(1, col, header, fmt)

    # ---- Row 3: examples + divider ----
    ws.set_row(2, 36)
    for col, example in enumerate(examples):
        ws.write(2, col, example, example_divider_fmt)

    # ---- Freeze first 3 rows ----
    ws.freeze_panes(3, 0)

    # ---- Column widths ----
    for col in range(ncols):
        width = estimate_column_width(
            description=descriptions[col],
            header=headers[col],
            example=examples[col],
        )
        ws.set_column(col, col, width)

    # ---- Dropdowns for controlled fields ----
    for col, options in enumerate(dropdown_options):
        if not options:
            continue
        ws.data_validation(
            3,
            col,
            rows - 1,
            col,
            {
                "validate": "list",
                "source": options,
                "ignore_blank": True,
            },
        )

    # ---- Evidence-specific paired fields (category <-> abbreviation) ----
    if model is Evidence:
        # Build mapping from abbreviations (enum names) to full category strings (enum values)
        cat_pairs = {
            e.name: e.value
            for enum_cls in (VariantEvidenceCategory, GeneEvidenceCategory, AnyEvidenceCategory)
            for e in enum_cls
        }

        validation_ws = workbook.add_worksheet("validation")
        validation_ws.hide()
        validation_ws.write(0, 0, "evidence_category_abbreviation")
        validation_ws.write(0, 1, "evidence_category")
        for r_idx, (abbr, full) in enumerate(sorted(cat_pairs.items()), start=1):
            validation_ws.write(r_idx, 0, abbr)
            validation_ws.write(r_idx, 1, full)

        last_row = len(cat_pairs) + 1  # 1-based in sheet (header row 1)
        abbr_range = f"=validation!$A$2:$A${last_row}"
        cat_range = f"=validation!$B$2:$B${last_row}"
        lookup_range = f"validation!$A$2:$B${last_row}"

        abbr_col = headers.index("evidence_category_abbreviation") if "evidence_category_abbreviation" in headers else None
        cat_col = headers.index("evidence_category") if "evidence_category" in headers else None

        for col_idx, source in ((abbr_col, abbr_range), (cat_col, cat_range)):
            if col_idx is not None:
                ws.data_validation(3, col_idx, rows - 1, col_idx, {"validate": "list", "source": source, "ignore_blank": True})

        if abbr_col is not None and cat_col is not None:
            for r in range(3, rows):
                abbr_cell = f"${_col_letter(abbr_col)}{r+1}"
                cat_cell = f"${_col_letter(cat_col)}{r+1}"
                ws.write_formula(
                    r,
                    cat_col,
                    f'=IF({abbr_cell}="","",IFERROR(VLOOKUP({abbr_cell},{lookup_range},2,FALSE),""))',
                    body_fmt,
                )
                ws.write_formula(
                    r,
                    abbr_col,
                    f'=IF({cat_cell}="","",IFERROR(INDEX(validation!$A$2:$A${last_row},MATCH({cat_cell},validation!$B$2:$B${last_row},0)),""))',
                    body_fmt,
                )

        # Enforce that evidence source_tag and method_tag reference described entries
        source_tag_col = headers.index("source_tag") if "source_tag" in headers else None
        method_tag_col = headers.index("method_tag") if "method_tag" in headers else None

        source_required = _required_columns_for_model(Source)
        method_required = _required_columns_for_model(Method)
        source_tag_letter = source_required.get("source_tag") or "A"
        method_tag_letter = method_required.get("method_tag") or "A"

        source_range = f"Source!${source_tag_letter}$4:${source_tag_letter}${rows}"
        method_range = f"Method!${method_tag_letter}$4:${method_tag_letter}${rows}"

        if source_tag_col is not None:
            ws.data_validation(
                3,
                source_tag_col,
                rows - 1,
                source_tag_col,
                {"validate": "list", "source": source_range, "ignore_blank": True},
            )
            for r in range(3, rows):
                match_expr = f'MATCH(${_col_letter(source_tag_col)}{r+1},{source_range},0)'
                presence = f'ISNUMBER({match_expr})'
                checks = ",".join(
                    [
                        f'INDEX(Source!${letter}$4:${letter}${rows},{match_expr})<>""'
                        for letter in source_required.values()
                    ]
                )
                formula = (
                    f'=IF(${_col_letter(source_tag_col)}{r+1}="",TRUE,AND({presence},{checks}))'
                )
                ws.data_validation(
                    r,
                    source_tag_col,
                    r,
                    source_tag_col,
                    {
                        "validate": "custom",
                        "value": formula,
                        "error_title": "Unknown source_tag",
                        "error_message": "Enter a source_tag defined in the Source sheet with its required fields filled.",
                    },
                )

        if method_tag_col is not None:
            ws.data_validation(
                3,
                method_tag_col,
                rows - 1,
                method_tag_col,
                {"validate": "list", "source": method_range, "ignore_blank": True},
            )
            for r in range(3, rows):
                match_expr = f'MATCH(${_col_letter(method_tag_col)}{r+1},{method_range},0)'
                presence = f'ISNUMBER({match_expr})'
                checks = ",".join(
                    [
                        f'INDEX(Method!${letter}$4:${letter}${rows},{match_expr})<>""'
                        for letter in method_required.values()
                    ]
                )
                formula = (
                    f'=IF(${_col_letter(method_tag_col)}{r+1}="",TRUE,AND({presence},{checks}))'
                )
                ws.data_validation(
                    r,
                    method_tag_col,
                    r,
                    method_tag_col,
                    {
                        "validate": "custom",
                        "value": formula,
                        "error_title": "Unknown method_tag",
                        "error_message": "Enter a method_tag defined in the Method sheet with its required fields filled.",
                    },
                )

    # ---- Data entry rows start at row 4 (index 3) ----
    for r in range(3, rows):
        ws.set_row(r, 18, body_fmt)

def generate_excel_from_pydantic(out_path: str | Path):
    workbook = xlsxwriter.Workbook(str(out_path))
    try:
        for model in (
            DatasetDescription,
            GenomicIdentifier,
            Evidence,
            Integration,
            Source,
            Method,
        ):
            write_model_sheet(workbook, model)
    finally:
        workbook.close()


if __name__ == "__main__":
    # Run from repo root with: python -m pegasus.template_creation.spreadsheet_builder
    generate_excel_from_pydantic("peg_template.xlsx")
    print("peg_template.xlsx generated")
