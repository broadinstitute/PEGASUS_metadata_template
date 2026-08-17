from __future__ import annotations

from typing import Literal, Optional

from pydantic import (
    BaseModel, 
    Field, 
    HttpUrl,
    model_validator,
)

from pegasus.schema.core import (
    EVIDENCE_CATEGORY_MAP,
    EntityType,
    EvidenceCategory,
    EvidenceCategoryAbbreviation,
    Text,
    LongText,
    Identifier,
    ShortText,
)

# ----------------------------
# Sheet: Evidence
# ----------------------------

class Evidence(BaseModel):
    """
    supporting data types and experimental or computational evidence that link variants to genes or traits.
    """
    column_header: ShortText = Field(
        ...,    
        description="Unique column name used in the PEG evidence matrix.",                                
        json_schema_extra={"header": "column_header", "example": "QTL_eQTL-aorta (p_value)"}
    )
    column_description: LongText = Field(
        ...,    
        description="Free text explanation of the content in this column..",                                
        json_schema_extra={"header": "column_description", "example": "p-value from eQTL analysis in aorta tissue"}
    )
    evidence_stream_tag: Optional[ShortText] = Field(
        default=None,
        description="Specific analysis stream within the evidence category.",
        json_schema_extra={"header": "evidence_stream_tag", "example": "eQTL"}
    )
    evidence_category: EvidenceCategory  = Field(
        ...,    
        description="Full evidence category name from the controlled list.",                                
        json_schema_extra={"header": "evidence_category", "example": "Molecular QTL"}
    )
    evidence_category_abbreviation: EvidenceCategoryAbbreviation = Field(
        ...,    
        description="Short label assigned from the controlled list of evidence categories.",                                
        json_schema_extra={"header": "evidence_category_abbreviation", "example": "QTL"}
    )
    variant_or_gene_centric: EntityType = Field(
        ...,    
        description="Indicates whether the evidence originates from variant-level or gene-level analysis.",                                
        json_schema_extra={"header": "variant_or_gene_centric", "example": "variant-centric"}
    )
    source_tag: Optional[ShortText] = Field(
        default=None,
        description="Identifier for the data source, created in the source tab.",
        json_schema_extra={"header": "source_tag", "example": "source_gtex_aorta"}
    )
    method_tag: Optional[ShortText] = Field(
        default=None,
        description="Identifier for the analysis method, created in the method tab.",
        json_schema_extra={"header": "method_tag", "example": "soft_fastqtl"}
    )
    threshold: Optional[ShortText] = Field(
        default=None,
        description="Threshold applied to define significance or inclusion criteria.",
        json_schema_extra={"header": "threshold", "example": "p_value < 0.05"}
    )
    note: Optional[LongText] = Field(
        default=None,
        description="Additional free text clarifications to aid interpretation.",
        json_schema_extra={"header": "note", "example": ""}
    )

    @model_validator(mode="after")
    def _validate_category_pair(self) -> "Evidence":
        expected = EVIDENCE_CATEGORY_MAP.get(self.evidence_category_abbreviation.value)
        if expected is None:
            return self
        if self.evidence_category.value != expected:
            raise ValueError(
                "evidence_category_abbreviation must match evidence_category for the row. "
                f"Expected '{expected}', got '{self.evidence_category.value}'."
            )
        return self
