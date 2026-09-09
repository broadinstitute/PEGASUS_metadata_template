from __future__ import annotations

import re
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field, AliasChoices, StrictBool, StrictStr, field_validator

# peg list is focused and lightweight compared to peg matrix, we directly use pydantic at here
# refernce: # Reference:https://www.union.ai/blog-post/pandera-0-17-adds-support-for-pydantic-v2

VARIANT_ID_PATTERN = re.compile(
    r"^chr(?:[1-9]|1[0-9]|2[0-2]|X|Y|M|MT):[1-9]\d*:[ATGC]+:[ATGC]+$"
)
HGNC_SYMBOL_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9]*(?:[.-][A-Za-z0-9]+)*$")


class ListIdentifiers(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    PrimaryVariantID: str = Field(
        ...,
        description="The variant to which variant-centric evidence relates. Used as the primary row ID; may be a lead variant, a variant in LD, or a fine-mapped SNP (defined in metadata).",
        examples=["chr10:114754071:T:C"],
        validation_alias=AliasChoices("primary_variant_id", "PrimaryVariantID", "rsID"),
    )
    GeneSymbol: StrictStr = Field(
        ...,
        description="The gene under consideration in this row. Primary symbol must be the HGNC-approved gene symbol. Alternative/legacy symbols may be provided via GENE_[xyz] (e.g. GENE_alias).",
        examples=["VTI1A"],
        validation_alias=AliasChoices("gene_symbol", "GeneSymbol", "Gene symbol"),
    )

    @field_validator("PrimaryVariantID")
    @classmethod
    def _isinstance_primary_variant(cls, value: str) -> str:
        if VARIANT_ID_PATTERN.match(value):
            return value
        raise ValueError(
            "PrimaryVariantID must be chr<chromosome>:<position>:<REF>:<ALT> "
            "(e.g., chr10:114754071:T:C)"
        )

    @field_validator("GeneSymbol")
    @classmethod
    def _isinstance_gene_symbol(cls, value: str) -> str:
        if HGNC_SYMBOL_PATTERN.match(value):
            return value
        raise ValueError(
            "Gene symbol must follow the HGNC-approved gene symbol format "
            "(e.g. BRCA1, C1orf54, or RP11-378J18.8)."
        )

class PegListSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    identifier: ListIdentifiers = Field(
        ...,
        description="Controlled variant/gene identifiers for matrix rows.",
    )
    evidence: Dict[str, StrictBool] = Field(
        default_factory=dict,
        description="Evidence columns keyed by <ControlledCategory>_(stream)_(description1)_(description2)...",
    )
    integration: Dict[str, Any] = Field(
        default_factory=dict,
        description="Integration columns keyed by INT_(tag)_[details].",
    )

    @field_validator("evidence")
    @classmethod
    def _validate_boolean_values(cls, value: Dict[str, bool]) -> Dict[str, bool]:
        for key, item in value.items():
            if not isinstance(item, bool):
                raise ValueError(f"Column '{key}' must be a boolean (TRUE/FALSE).")
        return value
