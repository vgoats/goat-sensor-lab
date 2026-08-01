from __future__ import annotations

import json

import pytest

from goat_sensor_analysis.modeling import make_group_splits, train_baselines
from goat_sensor_analysis.provenance import ValidatedResearchProvenance
from goat_sensor_analysis.windowing import WindowConfig, make_feature_windows


def _windows(samples_factory):
    samples = samples_factory(
        animals=("GOAT-001", "GOAT-002", "GOAT-003", "GOAT-004"),
        sessions_per_animal=2,
        seconds_per_label=2,
        rate_hz=10,
    )
    config = WindowConfig(duration_seconds=2, min_samples=15)
    windows = make_feature_windows(samples, config)
    domains = {
        "experiment_id": "EXP-001",
        "farm_id": "FARM-001",
        "site_id": "SITE-001",
        "shed_id": "SHED-001",
        "pen_id": "PEN-001",
        "calibration_id": "CAL-001",
        "calibration_status": "PROJECT_CALIBRATED",
        "calibration_applied_to_raw_export": "false",
        "calibration_coefficients_sha256": "e" * 64,
        "protocol_version": "PROTO-001@1",
        "ble_protocol_version": "2",
        "hardware_revision": "XIAO-SENSE-1",
        "firmware_version": "1.0.0",
        "firmware_commit": "b" * 40,
        "app_version": "1.0.0",
        "app_commit": "c" * 40,
        "requested_sample_rate_hz": "10.0",
        "accelerometer_range_g": "4.0",
        "gyroscope_range_deg_s": "500.0",
        "placement_side": "LEFT",
        "orientation_description": "Fixture orientation",
        "enclosure_id": "ENC-001",
        "enclosure_version": "1.0.0",
        "enclosure_mass_g": "20.0",
        "ethogram_id": "ETHOGRAM-GOAT-1",
        "ethogram_version": "1.0.0",
        "consensus_method": "ADJUDICATED",
        "consensus_protocol_version": "1.0.0",
        "consensus_code_revision": "a" * 40,
        "label_provenance_mode": "FROZEN_CONSENSUS",
    }
    for column, value in domains.items():
        windows[column] = value
    return windows, config


def _provenance():
    return ValidatedResearchProvenance(
        manifests=(
            {
                "experiment_id": "EXP-001",
                "session_id": "S-001",
                "animal_id": "GOAT-001",
                "manifest_sha256": "b" * 64,
                "raw_export_sha256": "c" * 64,
                "raw_annotations_sha256": "d" * 64,
                "consensus_sha256": "e" * 64,
                "materialization_id": "CONSENSUS-001",
            },
        ),
        verified_inputs=(),
    )


def test_group_splits_have_no_animal_or_session_leakage(samples_factory):
    windows, _ = _windows(samples_factory)

    for group_column in ["animal_id", "session_id"]:
        groups = windows[group_column].to_numpy()
        for train_index, test_index in make_group_splits(windows, group_column, 4):
            assert set(groups[train_index]).isdisjoint(set(groups[test_index]))


def test_research_artifacts_require_validated_provenance(samples_factory, tmp_path):
    windows, config = _windows(samples_factory)

    with pytest.raises(ValueError, match="validated experiment manifests and frozen consensus"):
        train_baselines(
            windows,
            tmp_path,
            window_config=config,
            requested_splits=4,
            trees=8,
            bootstrap_replicates=100,
        )

    assert not list(tmp_path.glob("*.joblib"))


def test_train_writes_separate_heads_and_grouped_metrics(samples_factory, tmp_path):
    windows, config = _windows(samples_factory)

    metrics = train_baselines(
        windows,
        tmp_path,
        window_config=config,
        requested_splits=4,
        trees=12,
        seed=7,
        bootstrap_replicates=100,
        dataset_hashes=[{"path": "fixture.csv", "sha256": "a" * 64, "bytes": 123}],
        research_provenance=_provenance(),
    )

    assert set(metrics["heads"]) == {"ingestive", "posture", "welfare_risk"}
    for head in metrics["heads"].values():
        assert head["status"] == "trained_internal_cv"
        assert head["internal_cv_valid"] is True
        assert head["evaluation_complete"] is True
        assert head["deployment_eligible"] is False
        for evaluation in head["evaluations"].values():
            assert 0 <= evaluation["macro_f1"] <= 1
            assert 0 <= evaluation["balanced_accuracy"] <= 1
            assert all(not fold["group_overlap"] for fold in evaluation["leakage_audit"])
            assert "matrix" in evaluation["confusion_matrix"]
            confidence_intervals = evaluation["confidence_intervals"]
            assert confidence_intervals["status"] == "valid"
            assert 0 <= confidence_intervals["macro_f1"]["lower"] <= 1
            assert 0 <= confidence_intervals["macro_f1"]["upper"] <= 1
            calibration = evaluation["calibration"]
            assert calibration["status"] == "valid"
            assert calibration["log_loss"] >= 0
            assert 0 <= calibration["expected_calibration_error"] <= 1
    assert "not a diagnosis" in metrics["welfare_disclaimer"]
    assert metrics["deployment_eligible"] is False
    assert (tmp_path / "ingestive_random_forest.joblib").exists()
    assert (tmp_path / "posture_random_forest.joblib").exists()
    assert (tmp_path / "welfare_risk_random_forest.joblib").exists()
    persisted = json.loads((tmp_path / "metrics.json").read_text())
    assert persisted["heads"]["welfare_risk"]["disclaimer"] == metrics["welfare_disclaimer"]
    manifest = json.loads((tmp_path / "reproducibility_manifest.json").read_text())
    assert manifest["schema"]["samples_schema_version"] == 1
    assert manifest["dataset"]["windows_sha256"]
    assert manifest["dataset"]["input_files"][0]["sha256"] == "a" * 64
    assert manifest["software"]["analysis_code_sha256"]


def test_rare_class_only_in_held_out_animal_blocks_deployable_artifact(samples_factory, tmp_path):
    windows, config = _windows(samples_factory)
    rare_animal = "GOAT-004"
    windows.loc[:, "ingestive_behavior"] = "FEEDING"
    windows.loc[windows["animal_id"] == rare_animal, "ingestive_behavior"] = "RUMINATION"
    stale_artifact = tmp_path / "ingestive_random_forest.joblib"
    stale_artifact.write_bytes(b"stale")

    metrics = train_baselines(
        windows,
        tmp_path,
        window_config=config,
        requested_splits=4,
        trees=12,
        seed=7,
        bootstrap_replicates=100,
        research_provenance=_provenance(),
    )

    ingestive = metrics["heads"]["ingestive"]
    animal_evaluation = ingestive["evaluations"]["animal_held_out"]
    assert animal_evaluation["status"] == "insufficient_class_coverage"
    assert "RUMINATION" in animal_evaluation["reason"]
    assert ingestive["status"] == "internal_cv_incomplete"
    assert ingestive["internal_cv_valid"] is False
    assert ingestive["evaluation_complete"] is False
    assert ingestive["deployment_eligible"] is False
    assert not stale_artifact.exists()
    assert (tmp_path / "posture_random_forest.joblib").exists()


@pytest.mark.parametrize(
    ("column", "values"),
    [
        ("species", ("GOAT", "SHEEP")),
        ("source", ("XIAO_NRF52840_SENSE", "ANDROID_PHONE")),
        ("placement", ("NECK_COLLAR", "EAR_MOUNT")),
        ("site_id", ("SITE-A", "SITE-B")),
        ("farm_id", ("FARM-A", "FARM-B")),
        ("calibration_id", ("CAL-A", "CAL-B")),
        ("calibration_status", ("PROJECT_CALIBRATED", "FACTORY_SPECIFICATION_ONLY")),
        ("protocol_version", ("PROTO@1", "PROTO@2")),
        ("requested_sample_rate_hz", ("13.0", "26.0")),
        ("firmware_version", ("1.0.0", "1.1.0")),
        ("firmware_commit", ("a" * 40, "b" * 40)),
        ("enclosure_id", ("ENC-A", "ENC-B")),
        ("enclosure_version", ("ENC-A", "ENC-B")),
        ("ethogram_version", ("1.0.0", "2.0.0")),
        ("consensus_protocol_version", ("1.0.0", "2.0.0")),
    ],
)
def test_mixed_modeling_domains_fail_closed(samples_factory, tmp_path, column, values):
    windows, config = _windows(samples_factory)
    midpoint = len(windows) // 2
    windows[column] = values[0]
    windows.loc[midpoint:, column] = values[1]

    with pytest.raises(ValueError, match=f"mixed modeling domain for {column}"):
        train_baselines(
            windows,
            tmp_path,
            window_config=config,
            requested_splits=4,
            trees=8,
            bootstrap_replicates=100,
            research_provenance=_provenance(),
        )

    assert not list(tmp_path.glob("*.joblib"))


def test_phone_windows_are_excluded_from_research_artifacts_by_default(
    samples_factory, tmp_path
):
    windows, config = _windows(samples_factory)
    windows.loc[:, "source"] = "ANDROID_PHONE"
    windows.loc[:, "placement"] = "PHONE_HANDHELD_TEST"

    with pytest.raises(ValueError, match="excluded from research model artifacts"):
        train_baselines(
            windows,
            tmp_path,
            window_config=config,
            requested_splits=4,
            trees=8,
            bootstrap_replicates=100,
            research_provenance=_provenance(),
        )

    assert not list(tmp_path.glob("*.joblib"))


def test_clinically_confirmed_welfare_label_requires_separate_provenance_contract(
    samples_factory, tmp_path
):
    windows, config = _windows(samples_factory)
    windows.loc[0, "welfare_state"] = "CLINICALLY_CONFIRMED_ABNORMAL"

    with pytest.raises(ValueError, match="clinical-outcomes provenance contract"):
        train_baselines(
            windows,
            tmp_path,
            window_config=config,
            requested_splits=4,
            trees=8,
            bootstrap_replicates=100,
            research_provenance=_provenance(),
        )

    assert not list(tmp_path.glob("*.joblib"))


def test_grouped_bootstrap_and_calibration_are_deterministic(samples_factory, tmp_path):
    windows, config = _windows(samples_factory)
    first = train_baselines(
        windows,
        tmp_path / "first",
        window_config=config,
        requested_splits=4,
        trees=12,
        seed=19,
        bootstrap_replicates=100,
        research_provenance=_provenance(),
    )
    second = train_baselines(
        windows,
        tmp_path / "second",
        window_config=config,
        requested_splits=4,
        trees=12,
        seed=19,
        bootstrap_replicates=100,
        research_provenance=_provenance(),
    )

    first_evaluation = first["heads"]["ingestive"]["evaluations"]["animal_held_out"]
    second_evaluation = second["heads"]["ingestive"]["evaluations"]["animal_held_out"]
    assert first_evaluation["confidence_intervals"] == second_evaluation["confidence_intervals"]
    assert first_evaluation["calibration"] == second_evaluation["calibration"]


def test_joblib_artifact_replacement_is_atomic(samples_factory, tmp_path, monkeypatch):
    windows, config = _windows(samples_factory)
    artifact = tmp_path / "ingestive_random_forest.joblib"
    artifact.write_bytes(b"previous-good-artifact")

    def fail_after_partial_write(_value, destination):
        destination.write_bytes(b"partial")
        raise RuntimeError("simulated serialization failure")

    monkeypatch.setattr("goat_sensor_analysis.artifacts.joblib.dump", fail_after_partial_write)
    with pytest.raises(RuntimeError, match="simulated serialization failure"):
        train_baselines(
            windows,
            tmp_path,
            window_config=config,
            requested_splits=4,
            trees=8,
            bootstrap_replicates=100,
            research_provenance=_provenance(),
        )

    assert artifact.read_bytes() == b"previous-good-artifact"
    assert not list(tmp_path.glob(".*.tmp"))
