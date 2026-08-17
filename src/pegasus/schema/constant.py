from pegasus.schema.core import AnyEvidenceCategory, GeneEvidenceCategory, VariantEvidenceCategory
from pegasus.schema.peg_list_schema import ListIdentifiers
from pegasus.schema.peg_matrix_schem import MatrixIdentifiesPydantic


other_genetic_identifiers = {
    "Var_",
    "Gene_",
    "Locus_"
}    

evidence_category = set(
    e.name
    for e in (
        list(VariantEvidenceCategory)
        + list(GeneEvidenceCategory)
        + list(AnyEvidenceCategory)
        )
        )

matrix_identifier_keys = set(
    MatrixIdentifiesPydantic.model_fields.keys()
        )

list_identifier_keys = set(
    ListIdentifiers.model_fields.keys()
        )