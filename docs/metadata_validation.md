In the metadata_validation.py, read the metadata xlxs file (e.g. toydata_metadata_template_PEGSt000000) each sheet and save them as a dict and validate using the pydantic schema defines in the peg_metadata_schema folder.
1. dataset_description: if mandatory trait_description exist, if other column exist, check the data type
2. genomic_identifer mandatory field exist and satisify the required type
3. check if the mandatory field exist. evidence_category and evidence_category_abbreviation in the controlled verbs, check if the column name follows the [evidence_category_abbreviation ]_(evidence_stream_tag)_..., variant_or_gene_centric only variant_centric or gene_centric, also at least two rows should be given
4. extract column header for main.py cross check usage
5. extract source_tag for source sheet validation
6. extract mentod_tag for method sheet validation
7. integration for mandatory fields exist
6. check if the integration_tag is used in the column header: INT_[tag]_[details]....; check if it is only one true value in the author_conclusion column, at least one row available data
5. extract source_tag for source sheet validation
6. extract mentod_tag for method sheet validation
7. check source and method: if tags == evidence's tags + integration tags, mandatory fields exist
