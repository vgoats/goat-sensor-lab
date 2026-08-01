import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from verify_samples_schema import (
    SchemaError,
    load_and_validate,
    validate_schema,
    verify_repository_contract,
)


ROOT = Path(__file__).parents[2]
SCHEMA_PATH = ROOT / "schema" / "samples-v1.schema.json"


class VerifySamplesSchemaTest(unittest.TestCase):
    def test_canonical_schema_is_valid(self):
        document = load_and_validate(SCHEMA_PATH)
        verify_repository_contract(ROOT, [column["name"] for column in document["columns"]])

    def test_duplicate_column_is_rejected(self):
        document = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        document["columns"][1]["name"] = document["columns"][0]["name"]
        with self.assertRaises(SchemaError):
            validate_schema(document)

    def test_wrong_column_order_is_rejected(self):
        document = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        document["columns"][0], document["columns"][1] = document["columns"][1], document["columns"][0]
        with self.assertRaises(SchemaError):
            validate_schema(document)

    def test_cli_returns_nonzero_for_invalid_schema(self):
        document = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        document["schema_version"] = 2
        with tempfile.TemporaryDirectory() as directory:
            invalid_path = Path(directory) / "invalid.json"
            invalid_path.write_text(json.dumps(document), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "verify_samples_schema.py"), str(invalid_path)],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("schema verification failed", result.stderr)


if __name__ == "__main__":
    unittest.main()
