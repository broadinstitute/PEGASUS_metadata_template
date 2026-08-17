"""Template conversion utilities for PEGASUS metadata."""

from .json_builder import xlsx_to_json
from .yaml_builder import xlsx_to_yaml

try:
    from .spreadsheet_builder import generate_excel_from_pydantic
except ModuleNotFoundError:
    generate_excel_from_pydantic = None

__all__ = [
    "xlsx_to_json",
    "xlsx_to_yaml",
    "generate_excel_from_pydantic",
]
