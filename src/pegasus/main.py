#!/usr/bin/env python3
"""
PEGASUS CLI tool.

Supports validation of PEG list, matrix, and metadata files,
and conversion between Excel, JSON, and YAML formats.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from pegasus.template_convert.json_builder import xlsx_to_json
from pegasus.template_convert.yaml_builder import xlsx_to_yaml, yaml_dump_no_aliases
from pegasus.validation.list_validation import PegListValidation
from pegasus.validation.matrix_validation import PegMatrixValidation
from pegasus.validation.metadata_validation import PegMetadataValidation

console = Console()

FILE_PATTERNS = {
    "list": {"prefix": "list_", "suffixes": {".tsv"}},
    "matrix": {"prefix": "matrix_", "suffixes": {".tsv"}},
    "metadata": {"prefix": "metadata_", "suffixes": {".xlsx", ".xls"}},
}

#----------------------------------------------
# Input file detection and related file finding
#----------------------------------------------
def detect_file_type(file_path: Path) -> str | None:
    """Detect file type based on filename pattern."""
    filename = file_path.name.lower()
    suffix = file_path.suffix

    for file_type, pattern in FILE_PATTERNS.items():
        if filename.startswith(pattern["prefix"]) and suffix in pattern["suffixes"]:
            return file_type

    # Fallback: check if contains keywords (for backward compatibility)
    for file_type, pattern in FILE_PATTERNS.items():
        if file_type in filename and suffix in pattern["suffixes"]:
            return file_type
    return None


def find_related_files(input_path: Path) -> dict[str, Path | None]:
    """Find related list, matrix, and metadata files.
    
    If input_path is a file, searches in the same directory.
    If input_path is a directory, searches within it.
    
    Looks for files starting with:
    - list_*.tsv for list files
    - matrix_*.tsv for matrix files
    - metadata_*.xlsx or metadata_*.xls for metadata files
    """
    if input_path.is_file():
        search_dir = input_path.parent
    elif input_path.is_dir():
        search_dir = input_path
    else:
        # Path doesn't exist, return empty
        return {"list": None, "matrix": None, "metadata": None}
    
    related_files: dict[str, Path | None] = {key: None for key in FILE_PATTERNS}
    
    # Find files by prefix pattern
    for file_path in search_dir.iterdir():
        if not file_path.is_file():
            continue

        filename_lower = file_path.name.lower()
        for file_type, pattern in FILE_PATTERNS.items():
            if not filename_lower.startswith(pattern["prefix"]):
                continue
            if file_path.suffix not in pattern["suffixes"]:
                continue
            if related_files[file_type] is None or (input_path.is_file() and file_path == input_path):
                related_files[file_type] = file_path
    
    return related_files


def find_duplicate_files(input_path: Path) -> dict[str, list[Path]]:
    """Find duplicate list/matrix/metadata files in a directory."""
    if input_path.is_file():
        search_dir = input_path.parent
    elif input_path.is_dir():
        search_dir = input_path
    else:
        return {key: [] for key in FILE_PATTERNS}

    matches: dict[str, list[Path]] = {key: [] for key in FILE_PATTERNS}
    for file_path in search_dir.iterdir():
        if not file_path.is_file():
            continue
        filename_lower = file_path.name.lower()
        for file_type, pattern in FILE_PATTERNS.items():
            if not filename_lower.startswith(pattern["prefix"]):
                continue
            if file_path.suffix not in pattern["suffixes"]:
                continue
            matches[file_type].append(file_path)

    return {key: paths for key, paths in matches.items() if len(paths) > 1}

#----------------------------------------------
# standalone validation functions
#----------------------------------------------
def validate_list(file_path: Path, error_limit: int = 50) -> list[dict]:
    """Validate a PEG list file."""
    validator = PegListValidation(file_path)
    return validator.validate_peglist(error_limit=error_limit)


def validate_matrix(file_path: Path, progress: bool = False) -> list[dict]:
    """Validate a PEG matrix file."""
    validator = PegMatrixValidation(file_path)
    return validator.validate_pegmatrix(progress=progress)


def validate_metadata(file_path: Path, error_limit: int = 50) -> list[dict]:
    """Validate a PEG metadata file."""
    validator = PegMetadataValidation(file_path)
    return validator.validate_metadata(error_limit=error_limit)

#----------------------------------------------
# cross validation functions
#----------------------------------------------

def cross_validate_list_matrix(
    list_file: Path,
    matrix_file: Path,
    metadata_file: Path | None = None,
) -> list[dict]:
    """Cross-validate PEG list, matrix, and metadata files.

    Returns a list of validation results in the same format as other validators.
    """
    results = []
    step_num = 0
    total_steps = 4  # Total number of cross-validation checks

    matrix_validator = PegMatrixValidation(matrix_file)
    if metadata_file is None:
        results.append({
            "step": "Cross-validation skipped",
            "type": "warning",
            "message": "Metadata file missing; skipping cross validation.",
        })
        return results

    metadata_validator = PegMetadataValidation(metadata_file)
    metadata_validator.validate_metadata()

    matrix_columns = matrix_validator.classify_headers()

    # Check 1: Evidence column consistency between matrix and metadata
    step_num += 1
    metadata_columns = metadata_validator.cross_check_column_names()
    metadata_columns = metadata_columns["Evidence"] + metadata_columns["Integration"]

    matrix_evidence = set(matrix_columns["evidence"]+ matrix_columns["int"])
    metadata_evidence = set(metadata_columns)

    extra = matrix_evidence - metadata_evidence
    missing = metadata_evidence - matrix_evidence
    if extra or missing:
        error_msg = "Mismatch in evidence columns between matrix and metadata files."
        details = []
        # Sort on the string form: a stray non-string column name must not be
        # able to raise a TypeError out of a validation run.
        if extra:
            details.append(f"Matrix has extra evidence columns not in metadata: {sorted(map(str, extra))}")
        if missing:
            details.append(f"Metadata has extra evidence columns not in matrix: {sorted(map(str, missing))}")

        results.append({
            "step": f"{step_num}/{total_steps} - Evidence Column Consistency",
            "type": "error",
            "message": error_msg,
            "details": details,
        })
    else:
        results.append({
            "step": f"{step_num}/{total_steps} - Evidence Column Consistency",
            "type": "info",
            "message": f"Matrix and metadata evidence columns match ({len(matrix_evidence)} columns).",
        })

    # Check 2: Author conclusion records exist in metadata
    step_num += 1
    try:
        author_conclusion = metadata_validator.return_author_conclusion_rows()
    except ValueError as exc:
        # return_author_conclusion_rows raises unless there is exactly one such
        # row. Report that as a validation result instead of letting the
        # exception escape and kill the CLI.
        results.append({
            "step": f"{step_num}/{total_steps} - Author Conclusion Records",
            "type": "error",
            "message": str(exc),
        })
        return results

    results.append({
        "step": f"{step_num}/{total_steps} - Author Conclusion Records",
        "type": "info",
        "message": f"Found {len(author_conclusion)} author conclusion record(s) in metadata.",
    })

    conclusion_column_names = author_conclusion[0].get("column_header")
    # A stream/tag consistency check belongs here eventually, reading
    # evidence_streams_included and integrations_included off this row. Both
    # fields are optional, so a blank cell means "no tags declared".

    # Check 3: Conclusion column exists in matrix file
    step_num += 1
    all_matrix_headers = [h for headers in matrix_columns.values() for h in headers]
    if conclusion_column_names not in all_matrix_headers:
        results.append({
            "step": f"{step_num}/{total_steps} - Conclusion Column in Matrix",
            "type": "error",
            "message": f"Conclusion column '{conclusion_column_names}' not found in matrix file.",
        })
    else:
        results.append({
            "step": f"{step_num}/{total_steps} - Conclusion Column in Matrix",
            "type": "info",
            "message": f"Conclusion column '{conclusion_column_names}' found in matrix file.",
        })

    # Check 4: Every list selection is supported by a positive conclusion in
    # the matrix. The conclusion is matrix-level information and does not need
    # to be duplicated in the list.
    step_num += 1
    selection_step = f"{step_num}/{total_steps} - List Rows Match Positive Matrix Conclusions"
    if conclusion_column_names not in all_matrix_headers:
        results.append({
            "step": selection_step,
            "type": "error",
            "message": (
                "List selections cannot be checked because the matrix conclusion "
                f"column '{conclusion_column_names}' is missing."
            ),
        })
        return results

    with matrix_file.open(newline="", encoding="utf-8-sig") as handle:
        matrix_rows = list(csv.DictReader(handle, delimiter="\t"))
    with list_file.open(newline="", encoding="utf-8-sig") as handle:
        selected_rows = list(csv.DictReader(handle, delimiter="\t"))

    conclusions_by_key: dict[tuple[str, str], list[str]] = {}
    for row in matrix_rows:
        key = (
            (row.get("PrimaryVariantID") or "").strip(),
            (row.get("GeneSymbol") or "").strip(),
        )
        conclusions_by_key.setdefault(key, []).append(
            (row.get(conclusion_column_names) or "").strip()
        )

    false_like_values = {"", "NA", "N/A", "NONE", "-", "FALSE", "0", "N", "NO"}
    missing_keys: list[str] = []
    non_positive_keys: list[str] = []
    for row in selected_rows:
        key = (
            (row.get("PrimaryVariantID") or "").strip(),
            (row.get("GeneSymbol") or "").strip(),
        )
        values = conclusions_by_key.get(key)
        display_key = f"{key[0]} / {key[1]}"
        if values is None:
            missing_keys.append(display_key)
        elif not any(value.upper() not in false_like_values for value in values):
            non_positive_keys.append(display_key)

    if missing_keys or non_positive_keys:
        details = []
        if missing_keys:
            details.append(f"List rows missing from matrix: {missing_keys}")
        if non_positive_keys:
            details.append(
                f"List rows without a positive '{conclusion_column_names}' value: "
                f"{non_positive_keys}"
            )
        results.append({
            "step": selection_step,
            "type": "error",
            "message": "One or more list rows are not supported by a positive matrix conclusion.",
            "details": details,
        })
    else:
        results.append({
            "step": selection_step,
            "type": "info",
            "message": (
                f"All {len(selected_rows)} list row(s) map to matrix rows with a positive "
                f"'{conclusion_column_names}' value."
            ),
        })

    return results
#----------------------------------------------
# Error formatting and UI response creation
#----------------------------------------------
def format_errors_rich(errors: list[dict]) -> None:
    """Format and print validation errors using rich."""
    for error in errors:
        step = error.get("step", "Unknown")
        error_type = error.get("type", "unknown").lower()
        message = error.get("message", "")
        
        # Choose color and icon based on error type
        if error_type == "error":
            color = "red"
            icon = "❌"
            border_style = "red"
        elif error_type == "warning":
            color = "yellow"
            icon = "⚠️"
            border_style = "yellow"
        else:  # info
            color = "green"
            icon = "✓"
            border_style = "green"
        
        # Create the main message text
        text = Text()
        text.append(f"{icon} ", style=color)
        text.append(step, style=f"bold {color}")
        text.append(": ", style=color)
        text.append(message, style=color)
        
        # Print the main message as a panel
        console.print(Panel(
            text,
            border_style=border_style,
            title=f"[{error_type.upper()}]",
            title_align="left",
        ))
        
        # Add details if present (printed separately)
        if "details" in error:
            details = error["details"]
            if isinstance(details, dict):
                if "errors" in details:
                    # Create a table for column errors
                    table = Table(show_header=True, header_style="bold magenta", box=None, padding=(0, 2))
                    table.add_column("Column", style="cyan")
                    table.add_column("Check", style="yellow")
                    table.add_column("Rows", style="red")
                    table.add_column("Hint", style="dim")
                    
                    for err_detail in details["errors"][:10]:  # Limit to 10 errors
                        if isinstance(err_detail, dict):
                            column = err_detail.get("column", "")
                            check = err_detail.get("check", "")
                            rows = err_detail.get("rows", [])
                            hint = err_detail.get("hint", "")
                            rows_str = ", ".join(map(str, rows[:10]))
                            if len(rows) > 10:
                                rows_str += f" ... (+{len(rows) - 10} more)"
                            table.add_row(column, check, rows_str, hint or "")
                    
                    console.print(table)
                elif "row" in details:
                    row_num = details.get("row", "?")
                    error_msg = details.get("error", "")
                    console.print(Text(f"  Row {row_num}: ", style="dim") + Text(str(error_msg), style="red"))
            elif isinstance(details, list):
                # Check if it's a list of strings (simple messages) or list of dicts (row errors)
                if details and isinstance(details[0], str):
                    # List of simple string messages (e.g., from cross-validation)
                    for detail in details:
                        console.print(Text(f"  • {detail}", style=color))
                else:
                    # List of row errors
                    for detail in details[:5]:  # Limit to first 5 details
                        if isinstance(detail, dict):
                            row = detail.get("row", "?")
                            key = detail.get("key", "")
                            error_msg = detail.get("error", "")
                            if isinstance(error_msg, list):
                                # Format pydantic errors
                                error_text = Text()
                                row_label = f"  Row {row}"
                                if key:
                                    row_label += f" ({key})"
                                error_text.append(row_label + ":\n", style="dim")
                                for err in error_msg[:3]:  # Limit to 3 errors per row
                                    if isinstance(err, dict):
                                        loc = " -> ".join(str(x) for x in err.get("loc", []))
                                        msg = err.get("msg", "")
                                        value = err.get("value", "")
                                        hint = err.get("hint", "")
                                        expected = err.get("expected_example", "")
                                        error_text.append(f"    {loc}: {msg}", style="red")
                                        if value:
                                            error_text.append(f"  [got: {value}]", style="yellow")
                                        error_text.append("\n")
                                        if expected:
                                            error_text.append(f"      expected example: {expected}\n", style="cyan")
                                        if hint:
                                            error_text.append(f"      hint: {hint}\n", style="yellow")
                                console.print(error_text)
                            else:
                                console.print(Text(f"  Row {row}: ", style="dim") + Text(str(error_msg), style="red"))


def create_ui_response(
    all_results: dict[str, list[dict]],
    file_paths: dict[str, Path | None],
) -> dict:
    """Create a lightweight response structure for UI consumption.
    
    Returns a simplified JSON structure optimized for UI display:
    
    {
        "status": "success" | "error",
        "summary": {
            "total_files": int,
            "files_with_errors": int,
            "total_errors": int,
            "total_warnings": int,
            "total_info": int
        },
        "files": {
            "list" | "matrix" | "metadata": {
                "path": str | null,
                "status": "success" | "error",
                "errors": [{"step": str, "message": str, ...}],
                "warnings": [{"step": str, "message": str, ...}],
                "info": [{"step": str, "message": str, ...}],
                "counts": {"errors": int, "warnings": int, "info": int}
            }
        }
    }
    
    Error details are simplified and limited to prevent large responses:
    - Column errors: limited to 20, rows limited to 50 per error
    - Row errors: limited to 20 rows, 5 errors per row
    """
    response = {
        "status": "success",
        "summary": {
            "total_files": 0,
            "files_with_errors": 0,
            "total_errors": 0,
            "total_warnings": 0,
            "total_info": 0,
        },
        "files": {},
    }
    
    for file_type, results in all_results.items():
        file_path = file_paths.get(file_type)
        file_info = {
            "path": str(file_path) if file_path else None,
            "status": "success",
            "errors": [],
            "warnings": [],
            "info": [],
            "counts": {
                "errors": 0,
                "warnings": 0,
                "info": 0,
            },
        }
        
        for result in results:
            result_type = result.get("type", "unknown").lower()
            step = result.get("step", "Unknown")
            message = result.get("message", "")
            
            # Create lightweight message
            msg = {
                "step": step,
                "message": message,
            }
            
            # Add simplified details if present
            if "details" in result:
                details = result["details"]
                if isinstance(details, dict):
                    if "errors" in details:
                        # For column errors, create simplified list
                        msg["column_errors"] = []
                        for err_detail in details["errors"][:20]:  # Limit for UI
                            if isinstance(err_detail, dict):
                                msg["column_errors"].append({
                                    "column": err_detail.get("column", ""),
                                    "check": err_detail.get("check", ""),
                                    "rows": err_detail.get("rows", [])[:50],  # Limit rows
                                    "hint": err_detail.get("hint", ""),
                                })
                    elif "row" in details:
                        msg["row"] = details.get("row")
                        msg["row_error"] = str(details.get("error", ""))
                elif isinstance(details, list):
                    # List of row errors
                    msg["row_errors"] = []
                    for detail in details[:20]:  # Limit for UI
                        if isinstance(detail, dict):
                            row = detail.get("row", "?")
                            error_msg = detail.get("error", "")
                            if isinstance(error_msg, list):
                                # Flatten pydantic errors
                                errors = []
                                for err in error_msg[:5]:
                                    if isinstance(err, dict):
                                        errors.append({
                                            "field": " -> ".join(str(x) for x in err.get("loc", [])),
                                            "message": err.get("msg", ""),
                                        })
                                msg["row_errors"].append({"row": row, "errors": errors})
                            else:
                                msg["row_errors"].append({"row": row, "error": str(error_msg)})
            
            # Add to appropriate list
            if result_type == "error":
                file_info["errors"].append(msg)
                file_info["counts"]["errors"] += 1
                file_info["status"] = "error"
                response["summary"]["total_errors"] += 1
            elif result_type == "warning":
                file_info["warnings"].append(msg)
                file_info["counts"]["warnings"] += 1
                response["summary"]["total_warnings"] += 1
            else:  # info
                file_info["info"].append(msg)
                file_info["counts"]["info"] += 1
                response["summary"]["total_info"] += 1
        
        response["files"][file_type] = file_info
        response["summary"]["total_files"] += 1
        if file_info["status"] == "error":
            response["summary"]["files_with_errors"] += 1
            response["status"] = "error"
    
    return response

def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="PEGASUS tool for validation and template conversion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute", required=True)
    
    #----------------------
    # Validation subcommand
    #----------------------
    validate_parser = subparsers.add_parser(
        "validate",
        description="Validate PEG list, matrix, and metadata files",
        help="Validate PEG files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
        Examples:
            # Validate a specific list file
            python -m pegasus.main validate /path/to/list_file.tsv --type list
            
            # Validate all files in a directory (looks for list_*, matrix_*, metadata_*)
            python -m pegasus.main validate /path/to/directory
            
            # Validate only matrix file from directory
            python -m pegasus.main validate /path/to/directory --type matrix
            
            # Validate a specific file (auto-detects type)
            python -m pegasus.main validate /path/to/list_data.tsv
            
            # Output as JSON
            python -m pegasus.main validate /path/to/directory --format json
        """,
    )
    
    validate_parser.add_argument(
        "file_path",
        type=Path,
        help="Path to a file or directory to validate. For directories, looks for list_*, matrix_*, metadata_* files.",
    )
    
    validate_parser.add_argument(
        "--type",
        choices=["list", "matrix", "metadata", "all"],
        default=None,
        help="Type of file to validate. If not specified, will auto-detect or validate all related files.",
    )
    
    validate_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    
    validate_parser.add_argument(
        "--error-limit",
        type=int,
        default=50,
        help="Maximum number of errors to report per validation (default: 50)",
    )
    
    validate_parser.add_argument(
        "--progress",
        action="store_true",
        help="Show progress messages during validation",
    )
    
    #--------------------
    # Convert subcommand
    #--------------------
    convert_parser = subparsers.add_parser(
        "convert",
        description="Convert between Excel, JSON, and YAML formats",
        help="Convert template formats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
        Examples:
            # Convert Excel to JSON
            python -m pegasus.main convert xlsx-to-json template.xlsx output.json
            
            # Convert Excel to YAML
            python -m pegasus.main convert xlsx-to-yaml template.xlsx output.yaml
            
            # Generate Excel from schema (requires schema models)
            python -m pegasus.main convert schema-to-xlsx output.xlsx
        """,
    )
    
    convert_parser.add_argument(
        "conversion_type",
        choices=["xlsx-to-json", "xlsx-to-yaml", "schema-to-xlsx"],
        help="Type of conversion to perform",
    )
    
    convert_parser.add_argument(
        "input_path",
        type=Path,
        nargs="?",
        help="Input file path. For schema-to-xlsx there is no input, so this is "
             "treated as the output path instead.",
    )

    convert_parser.add_argument(
        "output_path",
        type=Path,
        nargs="?",
        help="Output file path (optional, will print to stdout if not provided)",
    )

    convert_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists",
    )

    args = parser.parse_args()
    
    # Handle conversion command
    if args.command == "convert":
        return handle_convert(args)
    
    if args.command == "validate":
        # Handle validation command (rest of the code)
        return handle_validate(args)
    

def handle_convert(args: argparse.Namespace) -> int:
    """Handle conversion commands."""
    try:
        if args.conversion_type == "xlsx-to-json":
            if not args.input_path:
                console.print("[bold red]Error:[/bold red] Input Excel file required for xlsx-to-json")
                return 1
            
            if not args.input_path.exists():
                console.print(f"[bold red]Error:[/bold red] File not found: {args.input_path}")
                return 1
            
            console.print(f"[cyan]Converting Excel to JSON:[/cyan] {args.input_path}")
            result = xlsx_to_json(args.input_path, args.output_path)
            
            if args.output_path:
                console.print(f"[bold green]✓[/bold green] JSON saved to: {args.output_path}")
            else:
                # Print to stdout
                print(json.dumps(result, indent=2, default=str))
            
            return 0
        
        elif args.conversion_type == "xlsx-to-yaml":
            if not args.input_path:
                console.print("[bold red]Error:[/bold red] Input Excel file required for xlsx-to-yaml")
                return 1
            
            if not args.input_path.exists():
                console.print(f"[bold red]Error:[/bold red] File not found: {args.input_path}")
                return 1
            
            try:
                console.print(f"[cyan]Converting Excel to YAML:[/cyan] {args.input_path}")
                result = xlsx_to_yaml(args.input_path, args.output_path)
                
                if args.output_path:
                    console.print(f"[bold green]✓[/bold green] YAML saved to: {args.output_path}")
                else:
                    # Print to stdout
                    print(yaml_dump_no_aliases(result))
                
                return 0
            except ImportError:
                console.print("[bold red]Error:[/bold red] PyYAML is required for YAML conversion")
                console.print("[yellow]Install with: pip install pyyaml[/yellow]")
                return 1
        
        elif args.conversion_type == "schema-to-xlsx":
            # There is no input for this conversion, so a lone positional is the
            # destination. That makes it easy to name a file you meant to keep —
            # refuse to clobber an existing one unless asked explicitly.
            output_path = args.output_path or args.input_path
            if not output_path:
                console.print("[bold red]Error:[/bold red] Output Excel file path required for schema-to-xlsx")
                return 1
            if output_path.exists() and not getattr(args, "force", False):
                console.print(f"[bold red]Error:[/bold red] Output file already exists: {output_path}")
                console.print("[yellow]Pass --force to overwrite it.[/yellow]")
                return 1
            args.output_path = output_path

            console.print(f"[cyan]Generating Excel template from schema:[/cyan] {args.output_path}")
            from pegasus.template_convert.spreadsheet_builder import generate_excel_from_pydantic
            generate_excel_from_pydantic(args.output_path)
            console.print(f"[bold green]✓[/bold green] Excel template generated: {args.output_path}")
            return 0
    
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        return 1


def handle_validate(args: argparse.Namespace) -> int:
    """Handle validation commands."""
    
    def error_response(message: str, suggestion: str | None = None) -> int:
        if args.format == "json":
            payload = {"status": "error", "message": message}
            if suggestion:
                payload["suggestion"] = suggestion
            print(json.dumps(payload, indent=2))
        else:
            console.print(f"[bold red]Error:[/bold red] {message}")
            if suggestion:
                console.print(f"[yellow]{suggestion}[/yellow]")
        return 1

    # Check if path exists (file or directory)
    if not args.file_path.exists():
        return error_response(f"Path not found: {args.file_path}")
    
    if args.file_path.is_dir():
        duplicates = find_duplicate_files(args.file_path)
        if duplicates:
            details = ", ".join(
                f"{key}({len(paths)})" for key, paths in sorted(duplicates.items())
            )
            message = f"Multiple PEGASUS files found for: {details}"
            suggestion = "Keep only one list_*, matrix_*, and metadata_* file per directory."
            return error_response(message, suggestion)

    # Collect validation results and file paths
    all_results: dict[str, list[dict]] = {}
    file_paths: dict[str, Path | None] = {}
    has_errors = False
    dir_related_files: dict[str, Path | None] | None = None

    # Access column names via: metadata_validator.sheet_data[sheet_name]["found_fields"]
    metadata_validator: PegMetadataValidation | None = None

    validators = {
        "list": lambda p: validate_list(p, error_limit=args.error_limit),
        "matrix": lambda p: validate_matrix(p, progress=args.progress),
        "metadata": lambda p: validate_metadata(p, error_limit=args.error_limit),
    }
    

    def run_validation(file_type: str, file_path: Path) -> None:
        nonlocal has_errors, metadata_validator
        
        # For metadata, store the validator instance for cross-file validation
        if file_type == "metadata":
            validator = PegMetadataValidation(file_path)
            results = validator.validate_metadata(error_limit=args.error_limit)
            metadata_validator = validator
        else:
            results = validators[file_type](file_path)
        
        all_results[file_type] = results
        file_paths[file_type] = file_path
        if any(e.get("type") == "error" for e in results):
            has_errors = True
    
    # Determine what to validate
    validation_type = args.type
    
    # If path is a directory, always look for all files
    if args.file_path.is_dir():
        if validation_type and validation_type != "all":
            # User specified a type but gave a directory - find that specific file type
            related_files = find_related_files(args.file_path)
            dir_related_files = related_files
            target_file = related_files.get(validation_type)
            if not target_file:
                return error_response(
                    f"No {validation_type} file found in directory",
                    f"Looking for files starting with: {validation_type}_*",
                )
            
            # Validate the specific file type
            run_validation(validation_type, target_file)
        else:
            # Validate all files found in directory
            related_files = find_related_files(args.file_path)
            dir_related_files = related_files
            
            if not any(related_files.values()):
                return error_response(
                    "No PEGASUS files found in directory",
                    "Looking for files starting with: list_*, matrix_*, metadata_*",
                )
            
            # Validate all found files
            for file_type, file_path in related_files.items():
                if file_path:
                    run_validation(file_type, file_path)
    
    else:
        # Path is a file
        if validation_type is None:
            # Auto-detect from filename
            detected = detect_file_type(args.file_path)
            if detected:
                validation_type = detected
            else:
                # Default: try to validate all related files in the same directory
                validation_type = "all"
        
        if validation_type == "all":
            # Find and validate all related files in the same directory
            related_files = find_related_files(args.file_path)
            
            # Also check if the provided file itself matches a pattern
            detected = detect_file_type(args.file_path)
            if detected:
                related_files[detected] = args.file_path
            
            if not any(related_files.values()):
                return error_response(
                    f"Could not determine file type for {args.file_path}",
                    "Please specify --type list, --type matrix, or --type metadata",
                )
            
            # Validate all found files
            for file_type, file_path in related_files.items():
                if file_path:
                    run_validation(file_type, file_path)
        
        else:
            run_validation(validation_type, args.file_path)

    # Cross-validate only when input is a directory and all three files exist
    if args.file_path.is_dir() and dir_related_files:
        list_file = dir_related_files.get("list")
        matrix_file = dir_related_files.get("matrix")
        metadata_file = dir_related_files.get("metadata")
        if list_file and matrix_file and metadata_file:
            cross_results = cross_validate_list_matrix(list_file, matrix_file, metadata_file)
            all_results["cross_validation"] = cross_results
            file_paths["cross_validation"] = None  # No single file path for cross-validation
            if any(e.get("type") == "error" for e in cross_results):
                has_errors = True
    
    # Output results
    if args.format == "json":
        # Use lightweight UI response format
        ui_response = create_ui_response(all_results, file_paths)
        print(json.dumps(ui_response, indent=2))
    else:
        # Rich terminal output
        for file_type, results in all_results.items():
            console.print()
            # Format display name (replace underscores with hyphens)
            display_name = file_type.replace("_", "-").upper()
            fp = file_paths.get(file_type)
            filename_str = f"  {fp.name}" if fp else ""
            console.print(Panel(
                f"[bold]{display_name} Validation Results[/bold]{filename_str}",
                border_style="blue",
                title="[bold blue]PEGASUS[/bold blue]",
            ))
            console.print()
            format_errors_rich(results)
            console.print()
        
        # Print summary
        if has_errors:
            console.print("[bold red]❌ Validation completed with errors[/bold red]")
        else:
            console.print("[bold green]✓ Validation completed successfully[/bold green]")
    
    # Return exit code: 0 for success, 1 for errors
    return 1 if has_errors else 0


def entry_point() -> None:
    """Entry point for the pegasus_tool console script."""
    sys.exit(main())


if __name__ == "__main__":
    entry_point()

"""
pegasus_tool validate /path/to/directory
pegasus_tool validate /path/to/file.tsv --type list
pegasus_tool convert xlsx-to-json template.xlsx output.json
"""
