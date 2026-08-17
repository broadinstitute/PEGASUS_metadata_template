from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, StringConstraints
from pegasus.schema.core import Text, LongText, Identifier, ShortText

# ----------------------------
# Sheet: Integration
# ----------------------------

class Integration(BaseModel):
    """
     information about how different streams of evidence are combined (e.g., scoring, weighting, prioritisation).
    """
    integration_tag: Identifier = Field(
        ...,    
        description="Author-assigned analysis name that can be cited as evidence in the integrated_analysis_name field.",        
        json_schema_extra={"header": "integration_tag", "example": "pops"}
    )

    column_header: ShortText = Field(
        ...,    
        description="Unique column name used in the PEG evidence matrix.",                                
        json_schema_extra={"header": "column_header", "example": "INT_pops"}
    )

    column_description: LongText = Field(
        ...,    
        description="Free text explanation of the content in this column.",                                
        json_schema_extra={"header": "column_description", "example": "Integrated score based on multiple evidence types for the gene"}
    )

    author_conclusion: bool = Field(
        ...,
        description="Indicates when values in this column reflect the authors’ conclusions for defining the PEG list. NOTE: only **ONE** column per matrix can be assiged as `True`. We recommend including the string 'author_conclusion' in the appropirate column header.",
        json_schema_extra={"header": "author_conclusion", "example": "TRUE"}
    )

    evidence_streams_included: Optional[LongText] = Field(
        default=None,
        description="A list of variant-centric or gene-centric evidence stream names combined in the integration.",
        json_schema_extra={"header": "evidence_streams_included", "example": "FUNC | eQTL | pQTL | FM | 3d |PHEWAS |TWAS"}
    )

    integrations_included: Optional[LongText] = Field(
        default=None,
        description="A list of integration_tag values from other integration analyses that are included in this integration analysis",
        json_schema_extra={"header": "integrations_included", "example": "pops | flames"}
    )

    method_tag: Identifier = Field(
        ...,        
        description="Identifier for the analysis method (from Method tab).",
        json_schema_extra={"header": "method_tag", "example": "soft_pops"}
    )

    threshold: Optional[ShortText] = Field(
        default=None,        
        description="Threshold applied to define significance or inclusion criteria.",
        json_schema_extra={"header": "threshold", "example": "0.05"}
    )

    note: Optional[LongText] = Field(
        default=None,        
        description="Extra details to aid interpretation.",
        json_schema_extra={"header": "note", "example": ""}
    )
