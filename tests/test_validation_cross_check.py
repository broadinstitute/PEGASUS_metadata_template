import argparse
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "src"))

from pegasus import main as pegasus_main


class _DummyMetadataValidator:
    def __init__(self, path: Path) -> None:
        self.path = path

    def validate_metadata(self, error_limit: int = 50) -> list[dict]:
        return []


class TestCrossValidationDirectory(unittest.TestCase):
    def _write_tmp(self, directory: Path, name: str) -> Path:
        path = directory / name
        path.write_text("", encoding="utf-8")
        return path

    def _args(self, path: Path, file_type: str | None = None) -> argparse.Namespace:
        return argparse.Namespace(
            command="validate",
            file_path=path,
            type=file_type,
            format="json",
            error_limit=50,
            progress=False,
        )

    def test_cross_validation_runs_for_directory_with_all_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            list_file = self._write_tmp(tmp_path, "list_data.tsv")
            matrix_file = self._write_tmp(tmp_path, "matrix_data.tsv")
            metadata_file = self._write_tmp(tmp_path, "metadata_data.xlsx")

            with (
                patch.object(pegasus_main, "validate_list", return_value=[]),
                patch.object(pegasus_main, "validate_matrix", return_value=[]),
                patch.object(pegasus_main, "PegMetadataValidation", _DummyMetadataValidator),
                patch.object(pegasus_main, "cross_validate_list_matrix") as mock_cross_validate,
            ):
                exit_code = pegasus_main.handle_validate(self._args(tmp_path))

            self.assertEqual(exit_code, 0)
            mock_cross_validate.assert_called_once_with(list_file, matrix_file, metadata_file)

    def test_cross_validation_skipped_when_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            self._write_tmp(tmp_path, "list_data.tsv")
            self._write_tmp(tmp_path, "matrix_data.tsv")

            with (
                patch.object(pegasus_main, "validate_list", return_value=[]),
                patch.object(pegasus_main, "validate_matrix", return_value=[]),
                patch.object(pegasus_main, "PegMetadataValidation", _DummyMetadataValidator),
                patch.object(pegasus_main, "cross_validate_list_matrix") as mock_cross_validate,
            ):
                exit_code = pegasus_main.handle_validate(self._args(tmp_path))

            self.assertEqual(exit_code, 0)
            mock_cross_validate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
