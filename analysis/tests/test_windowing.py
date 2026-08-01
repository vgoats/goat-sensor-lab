from __future__ import annotations

from goat_sensor_analysis.windowing import LABEL_COLUMNS, WindowConfig, make_feature_windows


def test_windows_never_cross_label_or_invalid_boundaries(samples_factory):
    samples = samples_factory(seconds_per_label=4, rate_hz=10, include_invalid_tail=True)
    windows = make_feature_windows(
        samples,
        WindowConfig(duration_seconds=2, min_samples=15, gap_seconds=1),
    )

    assert len(windows) == 6
    assert windows["sample_count"].eq(20).all()
    assert set(windows["ingestive_behavior"]) == {"FEEDING", "RUMINATION", "NEITHER"}
    assert not windows["window_id"].duplicated().any()
    for _, rows in windows.groupby("window_id"):
        assert all(rows[column].nunique() == 1 for column in LABEL_COLUMNS)


def test_windows_stay_within_animal_and_session(samples_factory):
    samples = samples_factory(
        animals=("GOAT-001", "GOAT-002"),
        sessions_per_animal=2,
        seconds_per_label=2,
        rate_hz=10,
    )
    windows = make_feature_windows(
        samples,
        WindowConfig(duration_seconds=2, min_samples=15, gap_seconds=1),
    )

    assert len(windows) == 12
    assert windows["animal_id"].nunique() == 2
    assert windows["session_id"].nunique() == 4
    assert all(
        window_id.startswith(session_id)
        for window_id, session_id in zip(windows["window_id"], windows["session_id"], strict=True)
    )


def test_incomplete_tail_is_discarded(samples_factory):
    samples = samples_factory(seconds_per_label=3, rate_hz=10)
    windows = make_feature_windows(
        samples,
        WindowConfig(duration_seconds=2, min_samples=15, gap_seconds=1),
    )

    assert len(windows) == 3
    assert windows["sample_count"].eq(20).all()


def test_features_include_axes_magnitudes_and_gyro(samples_factory):
    windows = make_feature_windows(
        samples_factory(seconds_per_label=2, rate_hz=10),
        WindowConfig(duration_seconds=2, min_samples=15),
    )

    expected = {
        "acc_x_m_s2_mean",
        "acc_magnitude_m_s2_mean",
        "gyro_x_rad_s_std",
        "gyro_magnitude_rad_s_rms",
        "jerk_magnitude_m_s3_mean",
        "angular_accel_magnitude_rad_s2_mean",
    }
    assert expected.issubset(windows.columns)


def test_forward_sequence_gap_starts_a_new_run(samples_factory):
    samples = samples_factory(seconds_per_label=4, rate_hz=10)
    first_label_rows = samples["ingestive_behavior"] == "FEEDING"
    samples.loc[first_label_rows & (samples["sequence"] >= 20), "sequence"] += 1

    windows = make_feature_windows(
        samples,
        WindowConfig(duration_seconds=3, min_samples=15, gap_seconds=1),
    )

    feeding = windows[windows["ingestive_behavior"] == "FEEDING"]
    assert feeding.empty
