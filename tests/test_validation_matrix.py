import argparse
import sys
import tempfile
import unittest
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "src"))

from pegasus.main import handle_validate
from pegasus.validation.matrix_validation import PegMatrixValidation


BASE_HEADERS = [
    "PrimaryVariantID",
    "rsID",
    "GeneID",
    "GeneSymbol",
    "LocusRange",
    "LocusID",
    "GWAS_pvalue",
    "QTL_eqtl_pvalue",
    "INT_score",
]

BASE_ROW = [
    "chr1:100000:A:G",
    "rs1234",
    "ENSG00000123456",
    "VTI1A",
    "chr1:99500-115000",
    "Locus1",
    "4e-8",
    "7e-6",
    "STRONG",
]


def _has_type(results, kind: str) -> bool:
    return any(result.get("type") == kind for result in results)


def _has_step(results, step: str) -> bool:
    return any(result.get("step") == step for result in results)


def _build_tsv(headers: list[str], row: list[str]) -> str:
    return "\t".join(headers) + "\n" + "\t".join(row) + "\n"


def _write_tmp(tmp_path: Path, filename: str, content: str) -> Path:
    file_path = tmp_path / filename
    file_path.write_text(content)
    return file_path


class TestMatrixCatalogValidation(unittest.TestCase):
    def test_success(self) -> None:
        content = _build_tsv(BASE_HEADERS, BASE_ROW)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tsv_path = _write_tmp(Path(tmp_dir), "matrix_success.tsv", content)
            results = PegMatrixValidation(tsv_path).validate_pegmatrix()
        self.assertFalse(_has_type(results, "error"))

    def test_success_without_chr_prefix(self) -> None:
        row = BASE_ROW.copy()
        row[BASE_HEADERS.index("PrimaryVariantID")] = "1:100000:A:G"
        content = _build_tsv(BASE_HEADERS, row)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tsv_path = _write_tmp(Path(tmp_dir), "matrix_without_chr.tsv", content)
            results = PegMatrixValidation(tsv_path).validate_pegmatrix()
        self.assertFalse(_has_type(results, "error"))

    def test_success_with_valid_mixed_case_and_dotted_gene_symbol(self) -> None:
        for symbol in ("C1orf54", "RP11-378J18.8"):
            row = BASE_ROW.copy()
            row[BASE_HEADERS.index("GeneSymbol")] = symbol
            content = _build_tsv(BASE_HEADERS, row)
            with tempfile.TemporaryDirectory() as tmp_dir:
                tsv_path = _write_tmp(Path(tmp_dir), "matrix_gene_symbol.tsv", content)
                results = PegMatrixValidation(tsv_path).validate_pegmatrix()
            self.assertFalse(_has_type(results, "error"), symbol)

    def test_locus_id_is_a_genetic_identifier(self) -> None:
        """LocusID must classify as an identifier, not fall through to "other".

        The schema field was renamed from Locus_ID to LocusID. The old spelling
        still matched the "Locus_" prefix and landed in other_identifiers, so the
        renamed field was never actually exercised.
        """
        content = _build_tsv(BASE_HEADERS, BASE_ROW)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tsv_path = _write_tmp(Path(tmp_dir), "matrix_locus_id.tsv", content)
            classified = PegMatrixValidation(tsv_path).classify_headers()

        self.assertIn("LocusID", classified["genetic"])
        self.assertNotIn("LocusID", classified["other"])

    def test_missing_variant_id(self) -> None:
        headers = BASE_HEADERS.copy()
        row = BASE_ROW.copy()
        idx = headers.index("PrimaryVariantID")
        headers.pop(idx)
        row.pop(idx)
        content = _build_tsv(headers, row)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tsv_path = _write_tmp(Path(tmp_dir), "matrix_missing_variant_id.tsv", content)
            results = PegMatrixValidation(tsv_path).validate_pegmatrix()
        self.assertTrue(_has_type(results, "error"))
        self.assertTrue(_has_step(results, "4/4 - Fixed Column Validation"))

    def test_missing_geneid(self) -> None:
        headers = BASE_HEADERS.copy()
        row = BASE_ROW.copy()
        idx = headers.index("GeneID")
        headers.pop(idx)
        row.pop(idx)
        content = _build_tsv(headers, row)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tsv_path = _write_tmp(Path(tmp_dir), "matrix_missing_geneid.tsv", content)
            results = PegMatrixValidation(tsv_path).validate_pegmatrix()
        self.assertTrue(_has_type(results, "error"))
        self.assertTrue(_has_step(results, "4/4 - Fixed Column Validation"))

    def test_missing_genesymbol(self) -> None:
        headers = BASE_HEADERS.copy()
        row = BASE_ROW.copy()
        idx = headers.index("GeneSymbol")
        headers.pop(idx)
        row.pop(idx)
        content = _build_tsv(headers, row)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tsv_path = _write_tmp(Path(tmp_dir), "matrix_missing_genesymbol.tsv", content)
            results = PegMatrixValidation(tsv_path).validate_pegmatrix()
        self.assertTrue(_has_type(results, "error"))
        self.assertTrue(_has_step(results, "4/4 - Fixed Column Validation"))

    def test_invalid_variantid(self) -> None:
        row = BASE_ROW.copy()
        row[BASE_HEADERS.index("PrimaryVariantID")] = "chr1:100000:TM:C"
        content = _build_tsv(BASE_HEADERS, row)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tsv_path = _write_tmp(Path(tmp_dir), "matrix_invalid_variantid.tsv", content)
            results = PegMatrixValidation(tsv_path).validate_pegmatrix()
        self.assertTrue(_has_type(results, "error"))
        self.assertTrue(_has_step(results, "4/4 - Fixed Column Validation"))

    def test_invalid_variantid_with_mixed_separators(self) -> None:
        row = BASE_ROW.copy()
        row[BASE_HEADERS.index("PrimaryVariantID")] = "1:100000_A_G"
        content = _build_tsv(BASE_HEADERS, row)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tsv_path = _write_tmp(Path(tmp_dir), "matrix_mixed_separators.tsv", content)
            results = PegMatrixValidation(tsv_path).validate_pegmatrix()
        self.assertTrue(_has_type(results, "error"))
        self.assertTrue(_has_step(results, "4/4 - Fixed Column Validation"))

    def test_invalid_rsid(self) -> None:
        row = BASE_ROW.copy()
        row[BASE_HEADERS.index("rsID")] = "1234"
        content = _build_tsv(BASE_HEADERS, row)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tsv_path = _write_tmp(Path(tmp_dir), "matrix_invalid_rsid.tsv", content)
            results = PegMatrixValidation(tsv_path).validate_pegmatrix()
        self.assertTrue(_has_type(results, "error"))
        self.assertTrue(_has_step(results, "4/4 - Fixed Column Validation"))

    def test_invalid_genesymbol(self) -> None:
        row = BASE_ROW.copy()
        row[BASE_HEADERS.index("GeneSymbol")] = "1.0"
        content = _build_tsv(BASE_HEADERS, row)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tsv_path = _write_tmp(Path(tmp_dir), "matrix_invalid_genesymbol.tsv", content)
            results = PegMatrixValidation(tsv_path).validate_pegmatrix()
        self.assertTrue(_has_type(results, "error"))
        self.assertTrue(_has_step(results, "4/4 - Fixed Column Validation"))

    def test_invalid_locusrange(self) -> None:
        row = BASE_ROW.copy()
        row[BASE_HEADERS.index("LocusRange")] = "Z:12345"
        content = _build_tsv(BASE_HEADERS, row)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tsv_path = _write_tmp(Path(tmp_dir), "matrix_invalid_locusrange.tsv", content)
            results = PegMatrixValidation(tsv_path).validate_pegmatrix()
        self.assertTrue(_has_type(results, "error"))
        self.assertTrue(_has_step(results, "4/4 - Fixed Column Validation"))

    def test_invalid_contains_other_column(self) -> None:
        headers = BASE_HEADERS + ["UNKNOWN"]
        row = BASE_ROW + ["X"]
        content = _build_tsv(headers, row)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tsv_path = _write_tmp(Path(tmp_dir), "matrix_unknown_column.tsv", content)
            results = PegMatrixValidation(tsv_path).validate_pegmatrix()
        self.assertTrue(_has_type(results, "warning"))
        self.assertFalse(_has_type(results, "error"))
        self.assertTrue(_has_step(results, "1/4 - Header Classification"))

    def test_unknown_column_does_not_skip_fixed_column_validation(self) -> None:
        headers = BASE_HEADERS + ["UNKNOWN"]
        row = BASE_ROW.copy() + ["X"]
        row[BASE_HEADERS.index("PrimaryVariantID")] = "invalid"
        content = _build_tsv(headers, row)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tsv_path = _write_tmp(Path(tmp_dir), "matrix_unknown_and_invalid.tsv", content)
            results = PegMatrixValidation(tsv_path).validate_pegmatrix()

        self.assertTrue(_has_type(results, "warning"))
        self.assertTrue(_has_type(results, "error"))
        self.assertTrue(_has_step(results, "4/4 - Fixed Column Validation"))

    def test_invalid_one_evidence(self) -> None:
        headers = [h for h in BASE_HEADERS if h != "QTL_eqtl_pvalue"]
        row = [v for i, v in enumerate(BASE_ROW) if BASE_HEADERS[i] != "QTL_eqtl_pvalue"]
        content = _build_tsv(headers, row)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tsv_path = _write_tmp(Path(tmp_dir), "matrix_invalid_one_evidence.tsv", content)
            results = PegMatrixValidation(tsv_path).validate_pegmatrix()
        self.assertTrue(_has_type(results, "error"))
        self.assertTrue(_has_step(results, "3/4 - Evidence Column Validation"))

    def test_invalid_no_int(self) -> None:
        headers = [h for h in BASE_HEADERS if h != "INT_score"]
        row = [v for i, v in enumerate(BASE_ROW) if BASE_HEADERS[i] != "INT_score"]
        content = _build_tsv(headers, row)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tsv_path = _write_tmp(Path(tmp_dir), "matrix_invalid_no_int.tsv", content)
            results = PegMatrixValidation(tsv_path).validate_pegmatrix()
        self.assertTrue(_has_type(results, "error"))
        self.assertTrue(_has_step(results, "2/4 - INT Column Validation"))

    def test_invalid_more_than_one_matrix_in_dir(self) -> None:
        content = _build_tsv(BASE_HEADERS, BASE_ROW)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            _write_tmp(tmp_path, "matrix_a.tsv", content)
            _write_tmp(tmp_path, "matrix_b.tsv", content)
            args = argparse.Namespace(
                file_path=tmp_path,
                type="matrix",
                format="json",
                progress=False,
                error_limit=50,
            )
            exit_code = handle_validate(args)
            self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
