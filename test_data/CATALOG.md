# Test Data Catalog

This catalog lists TSV/XLSX fixtures in `test_data/` and the expected validation outcome.

## List validation
| Test Function| Validator | Expected outcome | Notes |
| --- | --- | --- | --- |
| success | list | success | Example list file with valid headers and rows. |
| missing_variant_id | list | error | Header validation error: missing `PrimaryVariantID`. |
| missing_genesymbol | list | error | Header validation error: missing `GeneSymbol`. |
| invalid_variantid | list | error | invalid `PrimaryVariantID`:chr1:100000:TM:C; the `chr` prefix, valid alleles, and colon separators are required  |
| invalid_genesymbol | list | error | Invalidate value in the `GeneSymbol`. e.g. 1.0 |
| invalid_number_of_int| list | error | More than one "INT_" column |
| invalid_no_int| list | error | No "INT_" column in the list|
| invalid_no_evidence| list | error | Only integration result and no evidence|
| invalid_contains_other_column| list | warning | Unrecognised columns|
| invalid_value| list | error | Invaild value (not boolean)|
| invalid_more_than_one_list_in_dir| list | error | More than one lists in a folder|

## Matrix validation
| Test Function | Validator | Expected outcome | Notes |
| --- | --- | --- | --- |
| success | matrix | success | Example matrix file with valid headers and rows. |
| missing_variant_id | matrix | error | Header validation error: missing `PrimaryVariantID`. |
| missing_geneid | matrix | error | Header validation error: missing `GeneID`. |
| missing_genesymbol | matrix | error | Header validation error: missing `GeneSymbol`. |
| invalid_variantid | matrix| error | invalid `PrimaryVariantID`:chr1:100000:TM:C; the `chr` prefix, valid alleles, and colon separators are required  |
| invalid_rsid | matrix | error | invalid `rsID`:1234 |
| invalid_genesymbol | matrix | error | Invalidate value in the `GeneSymbol`. e.g. 1.0 |
| invalid_locusrange | matrix | error | Invalidate value in the `LocusRange`. Z:12345|
| invalid_contains_other_column| matrix | warning | Unrecognised columns|
| invalid_one_evidence| matrix | error | there is only one evidence|
| invalid_no_int| matrix | error | No "INT_" column in the matrix|
| invalid_more_than_one_matrix_in_dir| matrix | error | More than one matrices in a folder|

## Metadata validation
| Test File | Validator | Expected outcome | Notes |
| --- | --- | --- | --- |
| success | metadata | success | Example metadata file with valid headers and rows. |
| missing_essential_tab | metadata | failed | Dataset description tab is missing |
| missing_mandatory_columns_dataset | metadata | failed| missing trait_description in the dataset description|
| missing_mandatory_columns_identifier | metadata | failed| missing genome_build in the genomic identifer|
| missing_mandatory_columns_evidence | metadata | failed| missing column_header|
| missing_mandatory_columns_integration | metadata | failed| missing column_description|
| gwas_source_is_gwas_catalog | metadata | success | gwas_source is GCSTxxx while missing other gwas_ fields|
| gwas_source_is_not_gwas_catalog | metadata | failed | gwas_source is NOT GCSTxxx while missing other gwas_ fields|
| evidence_catgory_not_in_list | metadata| failed | evidence_category is UNKNOWN|
| evidence_catgory_only_one | metadata| failed | Only one evidence row available|
| no_integration_row | metadata| failed | integration tab is empty|
| more_than_one_author_conclusion|  metadata| failed | two rows in the intergation tab are labelled as author_conclusion is True|
| no_author_conclusion | metadata| failed | two integration rows, but both are author_conclusion=False|
| evidence_catgory_miss_source_tag | metadata| failed | one source tag used in the evidence but missed in the source tab|
| evidence_catgory_miss_method_tag | metadata| failed | one method tag used in the evidence but missed in the method tab|

## Cross validation
| Test| Validator | Expected outcome | Notes |
| --- | --- | --- | --- |
| success| cross | success| success example - toy data|
| missing_file | cross | failed | missing list file |
| missing_column_in_metadata | cross | failed | one column in the matrix is missed in metadata evidence tab |
| list_without_conclusion_column | cross | failed | the list must include the metadata-declared author-conclusion column |
| list_row_with_negative_conclusion | cross | failed | a listed variant-gene pair has no positive author conclusion in the matrix |
| list_row_with_mismatched_conclusion | cross | failed | the list conclusion does not copy the matching matrix value |
