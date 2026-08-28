# PEGASUS Metadata Template Toolkit

This repository provides a Python CLI tool and schemas for working with PEGASUS metadata packages.
It focuses on three linked files:

- `list_*.tsv`
- `matrix_*.tsv`
- `metadata_*.xlsx` (or `.xls`)

## What This Repo Is

`pegasus` is a validation and template-conversion toolkit for PEGASUS data submission files.  
It includes:

- Pydantic/Pandera schemas for PEG list, matrix, and metadata formats
- Validators for file-level and cross-file consistency checks
- Converters between Excel metadata templates and JSON/YAML
- A generator for Excel templates from schema definitions

## What It Can Be Used For

- Validate incoming PEGASUS submission files before downstream use
- Catch structural issues early (missing required fields, invalid IDs, bad column formats)
- Verify metadata, list, and matrix stay aligned
- Convert spreadsheet-based metadata into machine-readable JSON/YAML
- Generate a fresh metadata template workbook from current schema definitions

## Repository Layout

- `src/pegasus/main.py`: CLI entrypoint
- `src/pegasus/validation/`: list/matrix/metadata validation logic
- `src/pegasus/schema/`: schema definitions and constants
- `src/pegasus/template_convert/`: Excel/JSON/YAML conversion utilities
- `templates/metadata_peg_template.xlsx`: generated metadata template asset
- `test_data/`: sample files for local testing
- `tests/`: unit tests

## Setup

### Requirements

- Python 3.11+
- Poetry

### Install

```bash
poetry install
```

Run commands with either:

- `poetry run pegasus_tool ...`
- `poetry run python -m pegasus.main ...`

## How To Use

### 1) Validate Files

Validate all PEGASUS files in a folder:

```bash
poetry run pegasus_tool validate test_data/toy_data/
```

Validate one type only:

```bash
poetry run pegasus_tool validate test_data/toy_data/ --type matrix
```

Validate a specific file:

```bash
poetry run pegasus_tool validate test_data/toy_data/list_toydata_PEGSt000000.tsv --type list
```

JSON output for UI/workflow integration:

```bash
poetry run pegasus_tool validate test_data/toy_data/ --format json
```

Control number of reported errors:

```bash
poetry run pegasus_tool validate test_data/toy_data/ --error-limit 100
```

### 2) Convert Metadata Template Formats

Excel to JSON:

```bash
poetry run pegasus_tool convert xlsx-to-json test_data/toy_data/metadata_toydata_PEGSt000000.xlsx output.json
```

Excel to YAML:

```bash
poetry run pegasus_tool convert xlsx-to-yaml test_data/toy_data/metadata_toydata_PEGSt000000.xlsx output.yaml
```

Generate Excel template from schema:

```bash
poetry run pegasus_tool convert schema-to-xlsx generated_template.xlsx
```

### 3) File Naming Convention (Important)

Directory-level detection and cross-validation rely on these prefixes:

- `list_*.tsv`
- `matrix_*.tsv`
- `metadata_*.xlsx` or `metadata_*.xls`

If multiple files of the same type are found in one directory, validation returns an error.

## Validation Behavior Summary

- List validation: required identifiers + evidence/integration header checks + row-level checks
- Matrix validation: fixed-column and format checks, plus evidence/integration header checks
- `PrimaryVariantID` format: `chr<chromosome>:<position>:<REF>:<ALT>` (for example, `chr10:114754071:T:C`); the `chr` prefix is required
- Metadata validation: per-sheet required columns and cross-sheet consistency rules
- Cross-validation (directory mode): list/matrix/metadata column alignment checks

### Representing Missing Values in Metadata

For optional fields in the metadata Excel file, missing values can be represented as:

- **Blank cell** (leave empty) — recommended
- `NA`
- `N/A`
- `NONE`

All of the above are treated as absent and will pass validation for any optional field. Do **not** use these strings in required fields, as the field will be treated as empty and fail validation.

Detailed rule notes are documented in:

- `docs/metadata_validation.md`
- `docs/decisions.md`

## Run Tests

```bash
poetry run python -m unittest discover -s tests
```
