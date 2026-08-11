# Repo plan (schema + validation)
## Validation rules (current behavior)

### High level decision
1. To keep the tool light weight, we decide not to validate if the HGNC or Ensembl id are validate or now. (Ensembl AP is not stable, also check if they are correct pair need prepared mapping files and also need to make sure they are the latest version).

### Common header conventions
- Evidence columns are detected by prefix:
  - The part before the first `_` must match a valid evidence category name from `core.py`.
- Integration columns must start with `INT_`.
- “Other identifiers” are any headers starting with `Var_`, `Gene_`, or `Locus_`.

### PEG matrix (`matrix_validation.py`)
Header checks:
- All headers must be recognized; unrecognized columns trigger a warning and stop validation.
- At least **one** `INT_` column is required.
- At least **two** evidence columns are required.

Fixed-column checks (Pandera, `MatrixIdentifiesPandera`):
- `PrimaryVariantID`: required, `[chr]<1-22|X|Y|M|MT>:pos:REF:ALT` regex; the literal `chr` prefix is optional, while colon separators remain mandatory.
- `rsID`: optional, `rs<digits>` regex.
- `GeneID`: required (no regex; must be non-null string).
- `GeneSymbol`: required and must start with a letter; valid HGNC-style mixed-case symbols, internal hyphens, and periods are accepted (for example `C1orf54` and `RP11-378J18.8`).
- `LocusRange`: optional, `chr<1-22|X|Y|M|MT>:start-end` regex.
- `LocusID`: optional (no regex).

Validation strategy:
- Fixed columns are validated in chunks (first 50k rows, then remaining).
- Errors are grouped by column and check, with row numbers and sample values.

### PEG list (`list_validation.py`)
Header checks:
- Required identifier columns must be present (from `ListIdentifiers`):
  - `PrimaryVariantID` (alias: `primary_variant_id`, `rsID`)
  - `GeneSymbol` (alias: `gene_symbol`, `Gene symbol`)
- At least **one** `INT_` column is required.
- At least **one** evidence column is required.
- Unrecognized columns are allowed but reported as warnings and skipped in row validation.

Row checks (Pydantic, `PegListSchema` + `ListIdentifiers`):
- `PrimaryVariantID`: must match `[chr]chromosome:position:REF:ALT`; both `10:114754071:T:C` and `chr10:114754071:T:C` are valid, while mixed separators are invalid.
- `GeneSymbol`: must be a non-numeric string.
- Evidence columns: values must parse to **boolean** (`TRUE`/`FALSE` or actual bool).
- Integration columns: accepted as strings (no strict validation yet).

## PEG metadata (`metadata_validation.py`)
Sheet handling:
- Reads Excel sheets with header row at row 2; skips the example row.
- Required sheets: DatasetDescription, GenomicIdentifier, Evidence, Integration, Source, Method.
- Unknown columns produce warnings; missing required columns are errors.
- String-typed fields accept numeric cell values (coerced to strings).

DatasetDescription conditional rule:
- If `gwas_source` is GCST*, then other GWAS fields remain optional.
- If `gwas_source` is present and not GCST*, the following become required:
  - `gwas_samples_description`
  - `gwas_sample_size`
  - `gwas_case_control_study`
  - `gwas_sample_ancestry`
  - `gwas_sample_ancestry_label`

Evidence sheet rules:
- Prefilled Evidence rows are ignored when `evidence_category` is 0 or 0.0.
- `evidence_category_abbreviation` must map to `evidence_category` per `EVIDENCE_CATEGORY_MAP`.

Cross-sheet rules:
- Evidence must have >2 validated rows.
- Integration must have >1 validated row.
- Exactly one Integration row must have `author_conclusion = TRUE`.
- Every `source_tag` referenced in Evidence must exist in Source.
- Every `method_tag` referenced in Evidence or Integration must exist in Method.

### Cross-file checks (CLI)
- The CLI runs cross-file checks only when the input path is a directory **and** all three files exist:
  - `list_*.tsv`, `matrix_*.tsv`, `metadata_*.xlsx`/`.xls`.
- Cross-checks include:
  - Matrix evidence columns must match the combined Evidence + Integration columns from metadata.
  - Metadata must include an `author_conclusion = TRUE` row.
  - The metadata conclusion column must exist in both the matrix and the list.
  - Every list `PrimaryVariantID` + `GeneSymbol` pair must match a matrix row and copy its positive conclusion value. Blank, `NA`, `N/A`, `NONE`, `-`, `FALSE`, `0`, `N`, and `NO` are treated as non-positive.

## Notes / gaps to address later
- Metadata validator is wired and enforces per-sheet + cross-sheet rules.
- Unknown matrix headers produce warnings and are ignored, while recognized columns continue through row validation.
- PEG list and matrix PrimaryVariantID validators accept the same colon-delimited format with an optional `chr` prefix.

## Where the schema lives
- `src/pegasus/schema/core.py`
  - Shared Pydantic types and enums (IDs, ontology patterns, controlled vocabularies).
  - Evidence categories are defined here via enums:
    - `VariantEvidenceCategory`, `GeneEvidenceCategory`, `AnyEvidenceCategory`.
- `src/pegasus/schema/peg_matrix_schem.py`
  - **PEG matrix** fixed-column schema.
  - Pydantic model (`MatrixIdentifiesPydantic`) for docs/field definitions.
  - Pandera model (`MatrixIdentifiesPandera`) for table validation.
- `src/pegasus/schema/peg_list_schema.py`
  - **PEG list** schema using Pydantic (`PegListSchema`, `ListIdentifiers`).
- `src/pegasus/schema/constant.py`
  - Derived constants used for validation:
    - `evidence_category` (all evidence enum names)
    - `matrix_identifier_keys` / `list_identifier_keys`
    - `other_genetic_identifiers` prefixes (`Var_`, `Gene_`, `Locus_`)
- `src/pegasus/schema/peg_metadata_schema/`
  - Metadata sheet schemas (Pydantic) for dataset-level context.
  - Files include `metadata_basic_schema.py`, `metadata_method_schema.py`, etc.

## Where validation lives
- `src/pegasus/validation/matrix_validation.py`
  - PEG **matrix** TSV validation using Pandera + header rules.
- `src/pegasus/validation/list_validation.py`
  - PEG **list** TSV validation using Pydantic + header rules.
- `src/pegasus/validation/metadata_validation.py`
  - PEG **metadata** XLSX validation using Pydantic row checks plus cross-sheet rules.

## Why Pandera for PEG Matrix while Pydantic for PEG List
- PEG matrix is large, tabular, and contains fixed-column; Pandera is optimized for DataFrame validation and can validate in chunks for scale.
- PEG list is smaller and more flexible (dynamic evidence/int columns); Pydantic models are simpler to apply row-by-row with custom alias handling.
- The matrix uses Pandera for strict column-level checks, while the list uses Pydantic to validate structured dicts after header classification.
- Reference: # Reference:https://www.union.ai/blog-post/pandera-0-17-adds-support-for-pydantic-v
