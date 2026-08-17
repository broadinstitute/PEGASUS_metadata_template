from __future__ import annotations
from typing import Annotated, Optional, Union
from enum import Enum
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)

# Variant_id, rsid, GeneId, GeneSymbol, LocusRange, LocusId, and evidence categories are reusuable models (PEG matrix and PEG list)

# ----------------------------
# Shared helpers
# ----------------------------
Text = Annotated[str, StringConstraints(strip_whitespace=True)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]
Identifier = Annotated[str, StringConstraints(strip_whitespace=True, max_length=128)]

# Common boolean representation: in Excel use TRUE/FALSE dropdown.
# In JSON/TSV parsing accept true/false/1/0 separately if needed.

# ----------------------------
# Controlled variant/gene Identifiers
# ----------------------------


# ----------------------------
# Controlled Ontology Identifiers
# ----------------------------
OntologyUnderscoreID = Annotated[
    str,
    StringConstraints(
        pattern=r"^[A-Za-z][A-Za-z0-9]*_\d+$"
    )
]
EFO_ID = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^EFO[:_]\d+$", max_length=128)]
UBERON_ID = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^UBERON[:_]\d+$", max_length=128)]
CL_ID = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^CL[:_]\d+$", max_length=128)]
NCBITAXON_ID = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^NCBITaxon:\d+$", max_length=128)]
PATO_ID = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^PATO[:_]\d+$", max_length=128)]
ECO_ID = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^ECO[:_]\d+$", max_length=128)]

PMID = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^PMID:\s*\d+$", max_length=32)]
DOI = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^10\.\d{4,9}/[-._;()/:A-Za-z0-9]+$", max_length=128)]
GCST = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^GCST\d+$", max_length=32)]
RSID = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^rs\d+$", max_length=32)]


# ----------------------------
# Controlled Enums
# ----------------------------

class GenomeBuild(str, Enum):
    GRCh37 = "GRCh37"
    GRCh38 = "GRCh38"

class EntityType(str, Enum):
    VARIANT = "variant-centric"
    GENE = "gene-centric"

class DiseaseStatus(str, Enum):
    healthy = "healthy"
    disease = "disease"

class SexComposition(str, Enum):
    male = "male"
    female = "female"
    mixed = "mixed"
    unknown = "unknown"

class VariantEvidenceCategory(str, Enum):
    # Use controlled list here (examples only)
    LD = "Linkage disequilibrium"
    FM = "Finemapping and credible sets"
    COLOC = "Colocalisation"
    QTL = "Molecular QTL"
    MR = "Mendelian Randomization (MR)"
    REG = "Regulatory region"
    CHROMATIN = "Chromatin interaction"
    FUNC = "Predicted functional impact"
    PROX = "Proximity to gene (distance)"
    GWAS = "Genome-wide association (GWAS) signal"
    PHEWAS = "PheWAS (Phenome-Wide Association Study)"

class GeneEvidenceCategory(str, Enum):
    PPI = "Protein–protein interaction"
    SET = "Pathway or gene sets"
    GENEBASE = "Gene-based association"
    EXP = "Expression"
    PERTURB = "Perturbation"
    KNOW = "Biological Knowledge Inference"
    TPWAS = "Genetically predicted trait association (TWAS/PWAS)"
    DRUG = "Drug related"

class AnyEvidenceCategory(str, Enum):
    CROSSP = "Cross-phenotype"
    LIT = "Literature curation"
    DB = "Association from curated database"
    OTHER = "Other"

EvidenceCategory = Union[
    VariantEvidenceCategory,
    GeneEvidenceCategory,
    AnyEvidenceCategory,
]

# Evidence category mapping (abbreviation -> full name)
EVIDENCE_CATEGORY_MAP: dict[str, str] = {
    member.name: member.value
    for enum_cls in (VariantEvidenceCategory, GeneEvidenceCategory, AnyEvidenceCategory)
    for member in enum_cls
}

class EvidenceCategoryAbbreviation(str, Enum):
    LD = "LD"
    FM = "FM"
    COLOC = "COLOC"
    QTL = "QTL"
    MR = "MR"
    REG = "REG"
    CHROMATIN = "CHROMATIN"
    FUNC = "FUNC"
    PROX = "PROX"
    GWAS = "GWAS"
    PHEWAS = "PHEWAS"
    PPI = "PPI"
    SET = "SET"
    GENEBASE = "GENEBASE"
    EXP = "EXP"
    PERTURB = "PERTURB"
    KNOW = "KNOW"
    TPWAS = "TPWAS"
    DRUG = "DRUG"
    CROSSP = "CROSSP"
    LIT = "LIT"
    DB = "DB"
    OTHER = "OTHER"

class AncestryCategory(str, Enum):
    ABORIGINAL_AUSTRALIAN = "Aboriginal Australian"
    AFRICAN_AMERICAN_AFRO_CARIBBEAN = "African American or Afro-Caribbean"
    AFRICAN_UNSPECIFIED = "African unspecified"
    ASIAN_UNSPECIFIED = "Asian unspecified"
    CENTRAL_ASIAN = "Central Asian"
    EAST_ASIAN = "East Asian"
    EUROPEAN = "European"
    GREATER_MIDDLE_EASTERN = "Greater Middle Eastern (Middle Eastern, North African, or Persian)"
    HISPANIC_LATIN_AMERICAN = "Hispanic or Latin American"
    NATIVE_AMERICAN = "Native American"
    NOT_REPORTED = "Not reported"
    OCEANIAN = "Oceanian"
    OTHER = "Other"
    OTHER_ADMIXED_ANCESTRY = "Other admixed ancestry"
    SOUTH_ASIAN = "South Asian"
    SOUTH_EAST_ASIAN = "South East Asian"
    SUB_SAHARAN_AFRICAN = "Sub-Saharan African"
