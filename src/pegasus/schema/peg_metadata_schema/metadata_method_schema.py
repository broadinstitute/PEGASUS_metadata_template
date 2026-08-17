from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl

from pegasus.schema.core import Text, LongText, Identifier, ShortText

# ----------------------------
# Sheet: Method
# ----------------------------

class Method(BaseModel):
    """
    a description of the methodology, pipelines, or softwares used to generate the data.
    """
    method_tag: ShortText = Field(
        ...,    
        description="Unique identifier for the method, used in the PEG evidence and integration metadata.",                                
        json_schema_extra={"header": "method_tag", "example": "soft_fastqtl"}
    )
    method_mode: Literal["software", "manual"] = Field(
        ...,    
        description="Specifies whether the method is a published software tool or a manual approach.",                                
        json_schema_extra={"header": "method_mode", "example": "software"}
    )
    method_mode_ontology_term_id: Literal[
        "ECO_0000218",
        "ECO_0000203",
        "ECO_0007674",
        "ECO_0007673",
    ] = Field(
        ...,    
        description="Manual assertion:ECO_0000218; Automatic assertion:ECO_0000203;Manually integrated combinatorial evidence: ECO_0007674;Automatically integrated combinatorial evidence: ECO_0007673 ",                                
        json_schema_extra={"header": "method_mode_ontology_term_id", "example": "ECO_0000203"}
    )
    software_name: Optional[ShortText] = Field(
        default=None,
        description="Name of the software used.",                                
        json_schema_extra={"header": "software_name", "example": "FastQTL"}
    )
    software_version: Optional[ShortText] = Field(
        default=None,
        description="Version of the software used.",                                
        json_schema_extra={"header": "software_version", "example": "v1.0"}
    )
    software_url: Optional[HttpUrl] = Field(
        default=None,
        description="Link to the official software resource.",                                
        json_schema_extra={"header": "software_url", "example": "https://github.com/francois-a/fastqtl"}
    )
    software_doi: Optional[Text] = Field(
        default=None,
        description="DOI of the software or associated publication.",                                
        json_schema_extra={"header": "software_doi", "example": "10.1093/BIOINFORMATICS/BTV722"}
    )
    method_description: Optional[LongText] = Field(
        default=None,
        description="Detailed description of the method, workflow, or customisation applied.",                                
        json_schema_extra={"header": "method_description", "example": "Custom scoring model combining eQTL and chromatin interaction data."}
    )
    note: Optional[LongText] = Field(
        default=None,
        description="Additional free text clarifications to aid interpretation.",
        json_schema_extra={"header": "note", "example": ""}
    )
