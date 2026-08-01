"""Strict parser and validator for Goat Sensor Lab ``samples.csv`` files."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Sequence
from pathlib import Path

import numpy as np
import pandas as pd

SAMPLE_COLUMNS = [
    "schema_version",
    "session_id",
    "animal_id",
    "species",
    "placement",
    "source",
    "device_id",
    "sequence",
    "wall_time_epoch_ms",
    "monotonic_time_ns",
    "source_uptime_ms",
    "gyro_monotonic_time_ns",
    "acc_x_m_s2",
    "acc_y_m_s2",
    "acc_z_m_s2",
    "gyro_x_rad_s",
    "gyro_y_rad_s",
    "gyro_z_rad_s",
    "temperature_c",
    "battery_percent",
    "rssi_dbm",
    "ingestive_behavior",
    "posture_activity",
    "welfare_state",
    "invalid_data",
]

REQUIRED_INTEGER_COLUMNS = [
    "schema_version",
    "sequence",
    "wall_time_epoch_ms",
    "monotonic_time_ns",
]
OPTIONAL_INTEGER_COLUMNS = [
    "source_uptime_ms",
    "gyro_monotonic_time_ns",
    "battery_percent",
    "rssi_dbm",
]
REQUIRED_FLOAT_COLUMNS = ["acc_x_m_s2", "acc_y_m_s2", "acc_z_m_s2"]
OPTIONAL_FLOAT_COLUMNS = [
    "gyro_x_rad_s",
    "gyro_y_rad_s",
    "gyro_z_rad_s",
    "temperature_c",
]

ENUMS = {
    "species": {"GOAT", "SHEEP"},
    "placement": {"PHONE_HANDHELD_TEST", "NECK_COLLAR", "EAR_MOUNT", "BODY_HARNESS"},
    "source": {"ANDROID_PHONE", "XIAO_NRF52840_SENSE"},
    "ingestive_behavior": {"UNKNOWN", "FEEDING", "RUMINATION", "NEITHER"},
    "posture_activity": {"UNKNOWN", "LYING", "STANDING", "ACTIVE_MOVEMENT"},
    "welfare_state": {
        "UNKNOWN",
        "NORMAL",
        "SUSPECTED_ABNORMAL_INACTIVITY",
    },
}


class DataValidationError(ValueError):
    """Raised when an export violates the versioned samples schema."""

    def __init__(self, issues: Sequence[str]):
        self.issues = list(issues)
        super().__init__("Invalid samples.csv:\n- " + "\n- ".join(self.issues))


def _read_header(path: Path) -> list[str]:
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            return next(csv.reader(handle))
    except StopIteration as exc:
        raise DataValidationError([f"{path}: file is empty"]) from exc
    except OSError as exc:
        raise DataValidationError([f"{path}: cannot read file: {exc}"]) from exc


def _coerce_numeric(
    frame: pd.DataFrame,
    columns: Iterable[str],
    *,
    integer: bool,
    optional: bool,
    issues: list[str],
) -> None:
    for column in columns:
        raw = frame[column]
        blank = raw.str.strip().eq("")
        if not optional and blank.any():
            rows = (blank[blank].index[:5] + 2).tolist()
            issues.append(f"{column}: blank required value at CSV row(s) {rows}")
        numeric = pd.to_numeric(raw.mask(blank), errors="coerce")
        malformed = ~blank & numeric.isna()
        if malformed.any():
            rows = (malformed[malformed].index[:5] + 2).tolist()
            issues.append(f"{column}: non-numeric value at CSV row(s) {rows}")
        finite = numeric.notna() & ~np.isfinite(numeric)
        if finite.any():
            rows = (finite[finite].index[:5] + 2).tolist()
            issues.append(f"{column}: infinite value at CSV row(s) {rows}")
        if integer:
            fractional = numeric.notna() & numeric.mod(1).ne(0)
            if fractional.any():
                rows = (fractional[fractional].index[:5] + 2).tolist()
                issues.append(f"{column}: expected integer at CSV row(s) {rows}")
            frame[column] = numeric.astype("Int64")
        else:
            frame[column] = numeric.astype(float)


def validate_samples(frame: pd.DataFrame, *, source_name: str = "samples.csv") -> pd.DataFrame:
    """Validate and return a typed copy of a samples frame.

    Validation is deliberately strict: schema version, exact columns, enums, numeric values,
    per-session identity, sensor-vector completeness, and monotonic ordering are checked before
    any feature generation or modeling is allowed.
    """

    issues: list[str] = []
    if list(frame.columns) != SAMPLE_COLUMNS:
        missing = [column for column in SAMPLE_COLUMNS if column not in frame.columns]
        extra = [column for column in frame.columns if column not in SAMPLE_COLUMNS]
        if missing:
            issues.append(f"{source_name}: missing column(s): {missing}")
        if extra:
            issues.append(f"{source_name}: unexpected column(s): {extra}")
        if not missing and not extra:
            issues.append(f"{source_name}: columns are not in canonical schema order")
        raise DataValidationError(issues)
    if frame.empty:
        raise DataValidationError([f"{source_name}: no sample rows"])

    typed = frame.copy()
    for column in typed.columns:
        typed[column] = typed[column].astype(str)

    _coerce_numeric(
        typed,
        REQUIRED_INTEGER_COLUMNS,
        integer=True,
        optional=False,
        issues=issues,
    )
    _coerce_numeric(
        typed,
        OPTIONAL_INTEGER_COLUMNS,
        integer=True,
        optional=True,
        issues=issues,
    )
    _coerce_numeric(
        typed,
        REQUIRED_FLOAT_COLUMNS,
        integer=False,
        optional=False,
        issues=issues,
    )
    _coerce_numeric(
        typed,
        OPTIONAL_FLOAT_COLUMNS,
        integer=False,
        optional=True,
        issues=issues,
    )

    for column in ["session_id", "animal_id", "device_id"]:
        blank = typed[column].str.strip().eq("")
        if blank.any():
            rows = (blank[blank].index[:5] + 2).tolist()
            issues.append(f"{column}: blank identifier at CSV row(s) {rows}")

    for column, allowed in ENUMS.items():
        typed[column] = typed[column].str.strip()
        invalid = ~typed[column].isin(allowed)
        if invalid.any():
            examples = sorted(typed.loc[invalid, column].unique().tolist())[:5]
            issues.append(f"{column}: invalid value(s) {examples}; allowed={sorted(allowed)}")

    normalized_bool = typed["invalid_data"].str.strip().str.lower()
    bad_bool = ~normalized_bool.isin({"true", "false"})
    if bad_bool.any():
        examples = sorted(typed.loc[bad_bool, "invalid_data"].unique().tolist())[:5]
        issues.append(f"invalid_data: expected true/false, got {examples}")
    typed["invalid_data"] = normalized_bool.eq("true")

    if typed["schema_version"].notna().any() and not typed["schema_version"].eq(1).all():
        versions = sorted(typed["schema_version"].dropna().unique().tolist())
        issues.append(f"schema_version: only version 1 is supported, got {versions}")
    if typed["sequence"].dropna().lt(0).any():
        issues.append("sequence: must be non-negative")
    for column in ["wall_time_epoch_ms", "monotonic_time_ns"]:
        if typed[column].dropna().le(0).any():
            issues.append(f"{column}: must be positive")
    if typed["source_uptime_ms"].dropna().lt(0).any():
        issues.append("source_uptime_ms: must be non-negative when present")
    if typed["gyro_monotonic_time_ns"].dropna().le(0).any():
        issues.append("gyro_monotonic_time_ns: must be positive when present")

    battery = typed["battery_percent"].dropna()
    if ((battery < 0) | (battery > 100)).any():
        issues.append("battery_percent: must be between 0 and 100")
    rssi = typed["rssi_dbm"].dropna()
    if ((rssi < -127) | (rssi > 20)).any():
        issues.append("rssi_dbm: must be between -127 and 20 dBm")
    temperature = typed["temperature_c"].dropna()
    if ((temperature < -100) | (temperature > 150)).any():
        issues.append("temperature_c: outside broad sensor sanity range [-100, 150]")

    gyro_values = typed[["gyro_x_rad_s", "gyro_y_rad_s", "gyro_z_rad_s"]]
    partial_gyro = gyro_values.notna().any(axis=1) & ~gyro_values.notna().all(axis=1)
    if partial_gyro.any():
        rows = (partial_gyro[partial_gyro].index[:5] + 2).tolist()
        issues.append(f"gyroscope: x/y/z must be all present or all blank at row(s) {rows}")
    gyro_without_time = gyro_values.notna().all(axis=1) & typed["gyro_monotonic_time_ns"].isna()
    if gyro_without_time.any():
        rows = (gyro_without_time[gyro_without_time].index[:5] + 2).tolist()
        issues.append(f"gyroscope: timestamp missing at row(s) {rows}")
    orphan_gyro_time = gyro_values.isna().all(axis=1) & typed["gyro_monotonic_time_ns"].notna()
    if orphan_gyro_time.any():
        rows = (orphan_gyro_time[orphan_gyro_time].index[:5] + 2).tolist()
        issues.append(f"gyroscope: timestamp present without x/y/z at row(s) {rows}")

    identity_columns = ["animal_id", "species", "placement", "source", "device_id"]
    for session_id, session in typed.groupby("session_id", sort=False):
        for column in identity_columns:
            if session[column].nunique(dropna=False) != 1:
                issues.append(f"session {session_id}: multiple {column} values")
        if session["monotonic_time_ns"].diff().dropna().le(0).any():
            issues.append(f"session {session_id}: monotonic_time_ns is not strictly increasing")
        if session["sequence"].diff().dropna().le(0).any():
            issues.append(f"session {session_id}: sequence is not strictly increasing")
        gyro_times = session["gyro_monotonic_time_ns"].dropna()
        if gyro_times.diff().dropna().lt(0).any():
            issues.append(f"session {session_id}: gyro_monotonic_time_ns moves backward")

    sample_identity = ["session_id", "source", "device_id", "sequence"]
    duplicated = typed.duplicated(sample_identity, keep=False)
    if duplicated.any():
        pairs = typed.loc[duplicated, sample_identity].head(5).to_dict("records")
        issues.append(f"duplicate canonical sample identity row(s): {pairs}")

    if issues:
        raise DataValidationError(issues[:50])
    return typed


def read_samples(paths: str | Path | Sequence[str | Path]) -> pd.DataFrame:
    """Read one or more version-1 ``samples.csv`` files and validate each one."""

    if isinstance(paths, (str, Path)):
        path_list = [Path(paths)]
    else:
        path_list = [Path(path) for path in paths]
    if not path_list:
        raise DataValidationError(["at least one samples.csv path is required"])

    frames: list[pd.DataFrame] = []
    for path in path_list:
        header = _read_header(path)
        if len(header) != len(set(header)):
            duplicates = sorted({column for column in header if header.count(column) > 1})
            raise DataValidationError([f"{path}: duplicate header column(s): {duplicates}"])
        if header != SAMPLE_COLUMNS:
            placeholder = pd.DataFrame(columns=header)
            validate_samples(placeholder, source_name=str(path))
        raw = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        frames.append(validate_samples(raw, source_name=str(path)))

    combined = pd.concat(frames, ignore_index=True)
    combined_raw = combined.astype("string").fillna("")
    combined_raw["invalid_data"] = combined["invalid_data"].map(
        {True: "true", False: "false"}
    )
    return validate_samples(combined_raw, source_name="combined input files")


def validation_summary(frame: pd.DataFrame) -> dict[str, object]:
    """Return a compact, JSON-serializable summary of validated samples."""

    duration_seconds = 0.0
    for _, session in frame.groupby("session_id", sort=False):
        if len(session) > 1:
            duration_seconds += float(
                (session["monotonic_time_ns"].iloc[-1] - session["monotonic_time_ns"].iloc[0])
                / 1_000_000_000
            )
    return {
        "schema_version": 1,
        "rows": int(len(frame)),
        "sessions": int(frame["session_id"].nunique()),
        "animals": int(frame["animal_id"].nunique()),
        "species": sorted(frame["species"].unique().tolist()),
        "sources": sorted(frame["source"].unique().tolist()),
        "duration_seconds": duration_seconds,
        "invalid_rows": int(frame["invalid_data"].sum()),
        "gyro_rows": int(frame["gyro_x_rad_s"].notna().sum()),
    }
