#!/usr/bin/env python3
"""Validate the canonical Goat Sensor Lab samples.csv schema without third-party packages."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Any

EXPECTED_COLUMNS = (
    ("schema_version", "integer", False, None),
    ("session_id", "string", False, None),
    ("animal_id", "string", False, None),
    ("species", "string", False, None),
    ("placement", "string", False, None),
    ("source", "string", False, None),
    ("device_id", "string", False, None),
    ("sequence", "integer", False, "count"),
    ("wall_time_epoch_ms", "integer", False, "ms"),
    ("monotonic_time_ns", "integer", False, "ns"),
    ("source_uptime_ms", "integer", True, "ms"),
    ("gyro_monotonic_time_ns", "integer", True, "ns"),
    ("acc_x_m_s2", "number", False, "m/s^2"),
    ("acc_y_m_s2", "number", False, "m/s^2"),
    ("acc_z_m_s2", "number", False, "m/s^2"),
    ("gyro_x_rad_s", "number", True, "rad/s"),
    ("gyro_y_rad_s", "number", True, "rad/s"),
    ("gyro_z_rad_s", "number", True, "rad/s"),
    ("temperature_c", "number", True, "degC"),
    ("battery_percent", "integer", True, "%"),
    ("rssi_dbm", "integer", True, "dBm"),
    ("ingestive_behavior", "string", False, None),
    ("posture_activity", "string", False, None),
    ("welfare_state", "string", False, None),
    ("invalid_data", "boolean", False, None),
)
ALLOWED_TYPES = {"integer", "number", "string", "boolean"}
ALLOWED_CONSTRAINTS = {"const", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"}


class SchemaError(ValueError):
    """Raised when the canonical schema is malformed or drifts from the contract."""


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SchemaError(f"{label} must be an object")
    return value


def _require(obj: dict[str, Any], key: str, label: str) -> Any:
    if key not in obj:
        raise SchemaError(f"{label} is missing required key {key!r}")
    return obj[key]


def _check_constraint_types(column: dict[str, Any], label: str) -> None:
    constraints = column.get("constraints", {})
    if not isinstance(constraints, dict):
        raise SchemaError(f"{label}.constraints must be an object")
    unknown = set(constraints) - ALLOWED_CONSTRAINTS
    if unknown:
        raise SchemaError(f"{label}.constraints has unknown key(s): {sorted(unknown)}")
    value_type = column["type"]
    for key, value in constraints.items():
        if value_type == "integer" and not isinstance(value, int):
            raise SchemaError(f"{label}.constraints.{key} must be an integer")
        if value_type == "number" and not isinstance(value, (int, float)):
            raise SchemaError(f"{label}.constraints.{key} must be numeric")
        if key == "const" and value_type == "boolean" and not isinstance(value, bool):
            raise SchemaError(f"{label}.constraints.const must be boolean")


def validate_schema(document: Any) -> None:
    """Validate the canonical document and its exact version-1 column contract."""

    schema = _object(document, "schema")
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        raise SchemaError("schema.$schema must identify JSON Schema draft 2020-12")
    if schema.get("format") != "csv":
        raise SchemaError("schema.format must be 'csv'")
    if schema.get("schema_version") != 1 or isinstance(schema.get("schema_version"), bool):
        raise SchemaError("schema.schema_version must be 1")
    columns = _require(schema, "columns", "schema")
    if not isinstance(columns, list) or not columns:
        raise SchemaError("schema.columns must be a non-empty array")
    if len(columns) != len(EXPECTED_COLUMNS):
        raise SchemaError(f"schema.columns must contain exactly {len(EXPECTED_COLUMNS)} columns")

    seen_names: set[str] = set()
    seen_positions: set[int] = set()
    for index, raw_column in enumerate(columns, start=1):
        column = _object(raw_column, f"column {index}")
        label = f"column {index}"
        name = _require(column, "name", label)
        position = _require(column, "position", label)
        value_type = _require(column, "type", label)
        required = _require(column, "required", label)
        nullable = _require(column, "nullable", label)
        _require(column, "unit", label)
        description = _require(column, "description", label)
        if not isinstance(name, str) or not name:
            raise SchemaError(f"{label}.name must be a non-empty string")
        if name in seen_names:
            raise SchemaError(f"duplicate column name: {name}")
        seen_names.add(name)
        if not isinstance(position, int) or isinstance(position, bool):
            raise SchemaError(f"{label}.position must be an integer")
        if position != index or position in seen_positions:
            raise SchemaError(f"{label}.position must be unique and equal to its 1-based order")
        seen_positions.add(position)
        if value_type not in ALLOWED_TYPES:
            raise SchemaError(f"{label}.type is unsupported: {value_type!r}")
        if not isinstance(required, bool) or not isinstance(nullable, bool):
            raise SchemaError(f"{label}.required and nullable must be booleans")
        if not required:
            raise SchemaError(f"{label}.required must be true for every CSV column")
        if not isinstance(description, str) or not description:
            raise SchemaError(f"{label}.description must be a non-empty string")
        expected_name, expected_type, expected_nullable, expected_unit = EXPECTED_COLUMNS[index - 1]
        if (name, value_type, nullable, column["unit"]) != (
            expected_name,
            expected_type,
            expected_nullable,
            expected_unit,
        ):
            raise SchemaError(
                f"{label} does not match the version-1 contract: "
                f"expected {(expected_name, expected_type, expected_nullable, expected_unit)!r}"
            )
        enum = column.get("enum")
        if enum is not None:
            if value_type != "string" or not isinstance(enum, list) or not enum:
                raise SchemaError(f"{label}.enum must be a non-empty array for string columns")
            if not all(isinstance(item, str) and item for item in enum):
                raise SchemaError(f"{label}.enum must contain unique non-empty strings")
            if len(enum) != len(set(enum)):
                raise SchemaError(f"{label}.enum must contain unique non-empty strings")
        csv_literals = column.get("csv_literals")
        if csv_literals is not None:
            if value_type != "boolean" or csv_literals != ["true", "false"]:
                raise SchemaError(f"{label}.csv_literals must be ['true', 'false'] for booleans")
        _check_constraint_types(column, label)

    if [column["name"] for column in columns] != [expected[0] for expected in EXPECTED_COLUMNS]:
        raise SchemaError("schema.columns are not in the canonical CSV order")
    row_rules = _require(schema, "row_rules", "schema")
    if not isinstance(row_rules, list) or not row_rules or not all(
        isinstance(rule, str) and rule for rule in row_rules
    ):
        raise SchemaError("schema.row_rules must be a non-empty array of strings")


def load_and_validate(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise SchemaError(f"cannot read {path}: {exc}") from exc
    validate_schema(document)
    return _object(document, "schema")


def _python_sample_columns(path: Path) -> list[str]:
    try:
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        raise SchemaError(f"cannot read Python runtime contract {path}: {exc}") from exc
    for statement in module.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
        if not any(isinstance(target, ast.Name) and target.id == "SAMPLE_COLUMNS" for target in targets):
            continue
        try:
            value = ast.literal_eval(statement.value)
        except (ValueError, TypeError) as exc:
            raise SchemaError("Python SAMPLE_COLUMNS must be a literal list of strings") from exc
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise SchemaError("Python SAMPLE_COLUMNS must be a literal list of strings")
        return value
    raise SchemaError(f"Python runtime contract {path} does not define SAMPLE_COLUMNS")


def _android_sample_columns(path: Path) -> list[str]:
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SchemaError(f"cannot read Android runtime contract {path}: {exc}") from exc
    match = re.search(
        r"private\s+const\s+val\s+SAMPLE_HEADER\s*=\s*(.*?)"
        r"private\s+const\s+val\s+EVENT_HEADER",
        source,
        flags=re.DOTALL,
    )
    if match is None:
        raise SchemaError(f"Android runtime contract {path} does not define SAMPLE_HEADER")
    literals = re.findall(r'"(?:[^"\\]|\\.)*"', match.group(1))
    try:
        header = "".join(json.loads(literal) for literal in literals)
    except json.JSONDecodeError as exc:
        raise SchemaError(f"Android SAMPLE_HEADER has an invalid string literal: {exc}") from exc
    if not header:
        raise SchemaError("Android SAMPLE_HEADER is empty")
    return header.split(",")


def verify_repository_contract(repository_root: Path, expected_columns: list[str]) -> None:
    """Verify both runtime column lists exactly match the canonical document."""

    runtime_columns = {
        "Python SAMPLE_COLUMNS": _python_sample_columns(
            repository_root / "analysis" / "src" / "goat_sensor_analysis" / "schema.py"
        ),
        "Android SAMPLE_HEADER": _android_sample_columns(
            repository_root
            / "app"
            / "src"
            / "main"
            / "java"
            / "com"
            / "vgoats"
            / "sensorlab"
            / "data"
            / "ExperimentRecorder.kt"
        ),
    }
    for label, columns in runtime_columns.items():
        if columns != expected_columns:
            missing = [column for column in expected_columns if column not in columns]
            extra = [column for column in columns if column not in expected_columns]
            raise SchemaError(
                f"{label} disagrees with canonical columns; missing={missing}, extra={extra}, "
                f"order_matches={not missing and not extra}"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "schema",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "schema" / "samples-v1.schema.json",
        help="schema JSON path (default: repository schema/samples-v1.schema.json)",
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root containing Android and Python implementations",
    )
    args = parser.parse_args(argv)
    try:
        document = load_and_validate(args.schema)
        expected_columns = [column["name"] for column in document["columns"]]
        verify_repository_contract(args.repository_root, expected_columns)
    except SchemaError as exc:
        print(f"schema verification failed: {exc}", file=sys.stderr)
        return 1
    print(f"schema OK: {args.schema}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
