import csv
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REAL_DATA = ROOT / "test_data" / "real_data"
MATRIX = REAL_DATA / "matrix_Aragam_PEGSt000007.tsv"
PEG_LIST = REAL_DATA / "list_Aragam_PEGSt000007.tsv"
VARIANT_ID_PATTERN = re.compile(
    r"^chr(?:[1-9]|1[0-9]|2[0-2]|X|Y|M|MT):[1-9]\d*:[ATGC]+:[ATGC]+$"
)


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def truthy(value: str) -> bool:
    return value.strip().upper() in {"TRUE", "1", "Y", "YES"}


def present(value: str) -> bool:
    return value.strip().upper() not in {"", "NA", "N/A", "NONE", "-", "FALSE", "0"}


class TestAragamRealDataConsistency(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.matrix = read_tsv(MATRIX)
        cls.peg_list = read_tsv(PEG_LIST)
        cls.matrix_by_key = {
            (row["PrimaryVariantID"], row["GeneSymbol"]): row
            for row in cls.matrix
        }

    def test_primary_variant_ids_require_chr_prefix_and_colon_format(self) -> None:
        for row in self.matrix + self.peg_list:
            self.assertRegex(row["PrimaryVariantID"], VARIANT_ID_PATTERN)

    def test_false_and_missing_values_are_not_evidence(self) -> None:
        for value in ("", "NA", "N/A", "NONE", "-", "FALSE", "0"):
            self.assertFalse(present(value), value)
        self.assertTrue(present("Hypocholesterolemia"))

    def test_matrix_has_unique_variant_gene_ids(self) -> None:
        keys = [(row["PrimaryVariantID"], row["GeneID"]) for row in self.matrix]
        self.assertEqual(len(keys), len(set(keys)))

    def test_rsids_do_not_contain_annotations(self) -> None:
        self.assertFalse(any("*" in row["rsID"] for row in self.matrix))

    def test_list_evidence_matches_matrix_and_counts(self) -> None:
        mapping = {
            "PROX": ("PROX", truthy),
            "FUNC": ("FUNC_VEP_consequence", present),
            "QTL": ("QTL_eQTL_summary", truthy),
            "DB": ("DB_ClinVar", present),
            "LIT_RareVariant": ("LIT_RareVariant", truthy),
            "LIT_MRorDrug": ("LIT_MRorDrug", truthy),
            "PERTURB": ("PERTURB_mouse_modelId", present),
            "INT_PoPS": ("INT_PoPS_500kb_summary", truthy),
        }
        for selected in self.peg_list:
            key = (selected["PrimaryVariantID"], selected["GeneSymbol"])
            matrix = self.matrix_by_key[key]
            for list_field, (matrix_field, check) in mapping.items():
                self.assertEqual(truthy(selected[list_field]), check(matrix[matrix_field]), key)
            self.assertEqual(
                int(selected["INT_n_predictors"]),
                sum(truthy(selected[field]) for field in mapping),
                key,
            )
            self.assertEqual(
                selected["INT_author_conclusion"].strip().upper(),
                matrix["INT_author_conclusion"].strip().upper(),
                key,
            )
            self.assertEqual(selected["INT_author_conclusion"].strip().upper(), "YES", key)
            self.assertTrue(truthy(matrix["INT_author_conclusion"]), key)

    def test_reported_pcsk9_qtl_error_is_corrected(self) -> None:
        row = next(row for row in self.peg_list if row["GeneSymbol"] == "PCSK9")
        self.assertEqual(row["QTL"], "FALSE")
        self.assertEqual(row["DB"], "TRUE")
        self.assertEqual(row["INT_n_predictors"], "7")


if __name__ == "__main__":
    unittest.main()
