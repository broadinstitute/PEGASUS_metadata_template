import argparse
import sys
import tempfile
import unittest
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "src"))

from pegasus.validation.list_validation import PegListValidation
from pegasus.main import handle_validate


def _has_type(results, kind: str) -> bool:
    return any(result.get("type") == kind for result in results)


class TestListValidation(unittest.TestCase):
    def _write_tmp(self, directory: Path, name: str, content: str) -> Path:
        path = directory / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_success(self) -> None:
        content = (
            "PrimaryVariantID\tGeneSymbol\tGWAS\tFUNC\tQTL\tEXP\tPERTURB\tINT_Combined_score\n"
            "chr1:100000:A:G\tVTI1A\tTRUE\tFALSE\tTRUE\tFALSE\tTRUE\tSTRONG\n"
            "chr2:20000:T:C\tGENE2\tFALSE\tTRUE\tFALSE\tTRUE\tFALSE\tMODERATE\n"
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            tsv_path = self._write_tmp(Path(tmp_dir), "success.tsv", content)
            results = PegListValidation(tsv_path).validate_peglist()
            self.assertFalse(_has_type(results, "error"))

    def test_invalid_without_chr_prefix(self) -> None:
        content = (
            "PrimaryVariantID\tGeneSymbol\tGWAS\tFUNC\tQTL\tEXP\tPERTURB\tINT_Combined_score\n"
            "1:100000:A:G\tVTI1A\tTRUE\tFALSE\tTRUE\tFALSE\tTRUE\tSTRONG\n"
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            tsv_path = self._write_tmp(Path(tmp_dir), "invalid_without_chr.tsv", content)
            results = PegListValidation(tsv_path).validate_peglist()
            self.assertTrue(_has_type(results, "error"))

    def test_success_with_valid_mixed_case_and_dotted_gene_symbols(self) -> None:
        content = (
            "PrimaryVariantID\tGeneSymbol\tGWAS\tFUNC\tQTL\tEXP\tPERTURB\tINT_Combined_score\n"
            "chr1:100000:A:G\tC1orf54\tTRUE\tFALSE\tTRUE\tFALSE\tTRUE\tSTRONG\n"
            "chr1:100001:A:G\tRP11-378J18.8\tTRUE\tFALSE\tTRUE\tFALSE\tTRUE\tSTRONG\n"
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            tsv_path = self._write_tmp(Path(tmp_dir), "valid_gene_symbols.tsv", content)
            results = PegListValidation(tsv_path).validate_peglist()
            self.assertFalse(_has_type(results, "error"))

    def test_missing_variant_id(self) -> None:
        content = (
            "GeneSymbol\tGWAS\tFUNC\tQTL\tEXP\tPERTURB\tINT_Combined_score\n"
            "VTI1A\tTRUE\tFALSE\tTRUE\tFALSE\tTRUE\tSTRONG\n"
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            tsv_path = self._write_tmp(Path(tmp_dir), "missing_variant_id.tsv", content)
            results = PegListValidation(tsv_path).validate_peglist()
            self.assertTrue(_has_type(results, "error"))
            self.assertTrue(
                any("Missing identifier columns" in r.get("message", "") for r in results)
            )

    def test_missing_genesymbol(self) -> None:
        content = (
            "PrimaryVariantID\tGWAS\tFUNC\tQTL\tEXP\tPERTURB\tINT_Combined_score\n"
            "chr1:100000:A:G\tTRUE\tFALSE\tTRUE\tFALSE\tTRUE\tSTRONG\n"
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            tsv_path = self._write_tmp(Path(tmp_dir), "missing_genesymbol.tsv", content)
            results = PegListValidation(tsv_path).validate_peglist()
            self.assertTrue(_has_type(results, "error"))
            self.assertTrue(
                any("Missing identifier columns" in r.get("message", "") for r in results)
            )

    def test_invalid_variantid(self) -> None:
        content = (
            "PrimaryVariantID\tGeneSymbol\tGWAS\tFUNC\tQTL\tEXP\tPERTURB\tINT_Combined_score\n"
            "chr1:100000:TM:C\tVTI1A\tTRUE\tFALSE\tTRUE\tFALSE\tTRUE\tSTRONG\n"
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            tsv_path = self._write_tmp(Path(tmp_dir), "invalid_variantid.tsv", content)
            results = PegListValidation(tsv_path).validate_peglist()
            self.assertTrue(_has_type(results, "error"))
            self.assertTrue(
                any(r.get("step") == "2/2 - Row Validation" for r in results)
            )

    def test_invalid_variantid_with_mixed_separators(self) -> None:
        content = (
            "PrimaryVariantID\tGeneSymbol\tGWAS\tFUNC\tQTL\tEXP\tPERTURB\tINT_Combined_score\n"
            "1:100000_A_G\tVTI1A\tTRUE\tFALSE\tTRUE\tFALSE\tTRUE\tSTRONG\n"
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            tsv_path = self._write_tmp(Path(tmp_dir), "mixed_separators.tsv", content)
            results = PegListValidation(tsv_path).validate_peglist()
            self.assertTrue(_has_type(results, "error"))

    def test_invalid_variantid_without_chromosome(self) -> None:
        content = (
            "PrimaryVariantID\tGeneSymbol\tGWAS\tFUNC\tQTL\tEXP\tPERTURB\tINT_Combined_score\n"
            ":100000:A:G\tVTI1A\tTRUE\tFALSE\tTRUE\tFALSE\tTRUE\tSTRONG\n"
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            tsv_path = self._write_tmp(Path(tmp_dir), "missing_chromosome.tsv", content)
            results = PegListValidation(tsv_path).validate_peglist()
            self.assertTrue(_has_type(results, "error"))

    def test_invalid_genesymbol(self) -> None:
        content = (
            "PrimaryVariantID\tGeneSymbol\tGWAS\tFUNC\tQTL\tEXP\tPERTURB\tINT_Combined_score\n"
            "chr1:100000:A:G\t1.0\tTRUE\tFALSE\tTRUE\tFALSE\tTRUE\tSTRONG\n"
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            tsv_path = self._write_tmp(Path(tmp_dir), "invalid_genesymbol.tsv", content)
            results = PegListValidation(tsv_path).validate_peglist()
            self.assertTrue(_has_type(results, "error"))
            self.assertTrue(
                any(r.get("step") == "2/2 - Row Validation" for r in results)
            )

    def test_invalid_number_of_int(self) -> None:
        content = (
            "PrimaryVariantID\tGeneSymbol\tGWAS\tFUNC\tQTL\tEXP\tPERTURB\tINT_A\tINT_B\n"
            "chr1:100000:A:G\tVTI1A\tTRUE\tFALSE\tTRUE\tFALSE\tTRUE\tSTRONG\tWEAK\n"
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            tsv_path = self._write_tmp(Path(tmp_dir), "invalid_number_of_int.tsv", content)
            results = PegListValidation(tsv_path).validate_peglist()
            self.assertFalse(_has_type(results, "error"))

    def test_invalid_no_evidence(self) -> None:
        content = (
            "PrimaryVariantID\tGeneSymbol\tINT_Combined_score\n"
            "chr1:100000:A:G\tVTI1A\tSTRONG\n"
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            tsv_path = self._write_tmp(Path(tmp_dir), "invalid_no_evidence.tsv", content)
            results = PegListValidation(tsv_path).validate_peglist()
            self.assertTrue(_has_type(results, "error"))
            self.assertTrue(
                any("No evidence columns found." in r.get("message", "") for r in results)
            )

    def test_invalid_contains_other_column(self) -> None:
        content = (
            "PrimaryVariantID\tGeneSymbol\tGWAS\tFUNC\tQTL\tEXP\tPERTURB\tINT_Combined_score\tUNKNOWN\n"
            "chr1:100000:A:G\tVTI1A\tTRUE\tFALSE\tTRUE\tFALSE\tTRUE\tSTRONG\tX\n"
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            tsv_path = self._write_tmp(Path(tmp_dir), "invalid_contains_other_column.tsv", content)
            results = PegListValidation(tsv_path).validate_peglist()
            self.assertTrue(_has_type(results, "warning"))
            self.assertFalse(_has_type(results, "error"))

    def test_invalid_value(self) -> None:
        content = (
            "PrimaryVariantID\tGeneSymbol\tGWAS\tFUNC\tQTL\tEXP\tPERTURB\tINT_Combined_score\n"
            "chr1:100000:A:G\tVTI1A\tMAYBE\tFALSE\tTRUE\tFALSE\tTRUE\tSTRONG\n"
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            tsv_path = self._write_tmp(Path(tmp_dir), "invalid_value.tsv", content)
            results = PegListValidation(tsv_path).validate_peglist()
            self.assertTrue(_has_type(results, "error"))

    def test_invalid_more_than_one_list_in_dir(self) -> None:
        content = (
            "PrimaryVariantID\tGeneSymbol\tGWAS\tFUNC\tQTL\tEXP\tPERTURB\tINT_Combined_score\n"
            "chr1:100000:A:G\tVTI1A\tTRUE\tFALSE\tTRUE\tFALSE\tTRUE\tSTRONG\n"
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            self._write_tmp(tmp_path, "list_a.tsv", content)
            self._write_tmp(tmp_path, "list_b.tsv", content)
            args = argparse.Namespace(
                file_path=tmp_path,
                type="list",
                format="json",
                progress=False,
                error_limit=50,
            )
            exit_code = handle_validate(args)
            self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
