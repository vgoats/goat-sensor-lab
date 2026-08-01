from __future__ import annotations

import pandas as pd
import pytest

from goat_sensor_analysis.schema import (
    SAMPLE_COLUMNS,
    DataValidationError,
    read_samples,
    validate_samples,
)


def test_valid_export_is_typed(samples_factory):
    samples = samples_factory()

    assert list(samples.columns) == SAMPLE_COLUMNS
    assert str(samples["sequence"].dtype) == "Int64"
    assert samples["invalid_data"].dtype == bool
    assert samples["acc_x_m_s2"].dtype == float


def test_missing_column_is_rejected(samples_factory):
    samples = samples_factory().drop(columns="acc_x_m_s2")

    with pytest.raises(DataValidationError, match="missing column"):
        validate_samples(samples)


def test_partial_gyroscope_vector_is_rejected(samples_factory):
    samples = samples_factory().astype(object)
    samples.loc[0, "gyro_y_rad_s"] = ""

    with pytest.raises(DataValidationError, match="x/y/z must be all present"):
        validate_samples(samples)


def test_orphan_gyroscope_timestamp_is_rejected(samples_factory):
    samples = samples_factory().astype(object)
    samples.loc[0, ["gyro_x_rad_s", "gyro_y_rad_s", "gyro_z_rad_s"]] = ""

    with pytest.raises(DataValidationError, match="timestamp present without x/y/z"):
        validate_samples(samples)


def test_gyroscope_timestamp_cannot_move_backward(samples_factory):
    samples = samples_factory().astype(object)
    samples.loc[2, "gyro_monotonic_time_ns"] = samples.loc[0, "gyro_monotonic_time_ns"]

    with pytest.raises(DataValidationError, match="gyro_monotonic_time_ns moves backward"):
        validate_samples(samples)


def test_non_monotonic_session_is_rejected(samples_factory):
    samples = samples_factory().astype(object)
    samples.loc[2, "monotonic_time_ns"] = samples.loc[1, "monotonic_time_ns"]

    with pytest.raises(DataValidationError, match="not strictly increasing"):
        validate_samples(samples)


def test_unknown_enum_value_is_rejected(samples_factory):
    samples = samples_factory().astype(object)
    samples.loc[0, "species"] = "COW"

    with pytest.raises(DataValidationError, match="species: invalid"):
        validate_samples(samples)


def test_negative_source_uptime_is_rejected(samples_factory):
    samples = samples_factory().astype(object)
    samples.loc[0, "source_uptime_ms"] = "-1"

    with pytest.raises(DataValidationError, match="source_uptime_ms: must be non-negative"):
        validate_samples(samples)


def test_empty_frame_is_rejected():
    with pytest.raises(DataValidationError, match="no sample rows"):
        validate_samples(pd.DataFrame(columns=SAMPLE_COLUMNS))


def _write_split(path, rows):
    rows.to_csv(path, index=False)
    return path


def test_combined_files_recheck_session_identity(samples_factory, tmp_path):
    samples = samples_factory().astype(object)
    split = len(samples) // 2
    first = samples.iloc[:split].copy()
    second = samples.iloc[split:].copy()
    second.loc[:, "species"] = "SHEEP"

    with pytest.raises(DataValidationError, match="multiple species values"):
        read_samples(
            [
                _write_split(tmp_path / "first.csv", first),
                _write_split(tmp_path / "second.csv", second),
            ]
        )


def test_combined_files_recheck_monotonic_time_and_sequence(samples_factory, tmp_path):
    samples = samples_factory().astype(object)
    split = len(samples) // 2
    earlier = samples.iloc[:split].copy()
    later = samples.iloc[split:].copy()

    with pytest.raises(DataValidationError, match="not strictly increasing"):
        read_samples(
            [
                _write_split(tmp_path / "later.csv", later),
                _write_split(tmp_path / "earlier.csv", earlier),
            ]
        )


def test_combined_files_reject_duplicate_canonical_identity(samples_factory, tmp_path):
    samples = samples_factory().iloc[:20].copy()

    with pytest.raises(DataValidationError, match="duplicate canonical sample identity"):
        read_samples(
            [
                _write_split(tmp_path / "one.csv", samples),
                _write_split(tmp_path / "two.csv", samples),
            ]
        )
