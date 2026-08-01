from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from goat_sensor_analysis.schema import SAMPLE_COLUMNS, validate_samples


def make_samples(
    *,
    animals: Iterable[str] = ("GOAT-001",),
    sessions_per_animal: int = 1,
    seconds_per_label: int = 4,
    rate_hz: int = 10,
    include_invalid_tail: bool = False,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    labels = [
        ("FEEDING", "STANDING", "NORMAL"),
        ("RUMINATION", "LYING", "SUSPECTED_ABNORMAL_INACTIVITY"),
        ("NEITHER", "ACTIVE_MOVEMENT", "NORMAL"),
    ]
    for animal_number, animal_id in enumerate(animals):
        for session_number in range(sessions_per_animal):
            session_id = f"S-{animal_id}-{session_number}"
            sequence = 0
            base_ns = (animal_number * 100 + session_number + 1) * 1_000_000_000_000
            interval_ns = int(1_000_000_000 / rate_hz)
            for label_number, (ingestive, posture, welfare) in enumerate(labels):
                count = seconds_per_label * rate_hz
                for _offset in range(count):
                    t = sequence / rate_hz
                    rows.append(
                        {
                            "schema_version": "1",
                            "session_id": session_id,
                            "animal_id": animal_id,
                            "species": "GOAT",
                            "placement": "NECK_COLLAR",
                            "source": "XIAO_NRF52840_SENSE",
                            "device_id": f"XIAO-{animal_id}",
                            "sequence": str(sequence),
                            "wall_time_epoch_ms": str(1_700_000_000_000 + sequence * 100),
                            "monotonic_time_ns": str(base_ns + sequence * interval_ns),
                            "source_uptime_ms": str(sequence * 100),
                            "gyro_monotonic_time_ns": str(base_ns + sequence * interval_ns),
                            "acc_x_m_s2": str(np.sin(t + label_number) + animal_number),
                            "acc_y_m_s2": str(np.cos(t * 0.5 + label_number)),
                            "acc_z_m_s2": str(9.81 + 0.1 * np.sin(t * 2)),
                            "gyro_x_rad_s": str(0.1 * np.sin(t * 3 + label_number)),
                            "gyro_y_rad_s": str(0.2 * np.cos(t * 2 + label_number)),
                            "gyro_z_rad_s": str(0.05 * np.sin(t)),
                            "temperature_c": "",
                            "battery_percent": "80",
                            "rssi_dbm": "-55",
                            "ingestive_behavior": ingestive,
                            "posture_activity": posture,
                            "welfare_state": welfare,
                            "invalid_data": "false",
                        }
                    )
                    sequence += 1
            if include_invalid_tail:
                for _ in range(seconds_per_label * rate_hz):
                    previous = dict(rows[-1])
                    previous.update(
                        sequence=str(sequence),
                        wall_time_epoch_ms=str(1_700_000_000_000 + sequence * 100),
                        monotonic_time_ns=str(base_ns + sequence * interval_ns),
                        source_uptime_ms=str(sequence * 100),
                        gyro_monotonic_time_ns=str(base_ns + sequence * interval_ns),
                        invalid_data="true",
                    )
                    rows.append(previous)
                    sequence += 1
    return validate_samples(pd.DataFrame(rows, columns=SAMPLE_COLUMNS))


@pytest.fixture
def samples_factory():
    return make_samples


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_research_bundle(
    samples: pd.DataFrame,
    directory: Path,
    *,
    first_ingestive_override: str | None = None,
) -> dict[str, object]:
    """Write a complete digest-bound research fixture using repository schemas."""

    samples_path = directory / "samples.csv"
    samples.to_csv(samples_path, index=False)
    raw_export_sha256 = _sha256(samples_path)
    schema_root = Path(__file__).resolve().parents[2] / "schema"
    annotation_schema = json.loads(
        (schema_root / "annotations-v1.schema.json").read_text(encoding="utf-8")
    )
    annotation_columns = [column["name"] for column in annotation_schema["columns"]]
    annotation_rows: list[dict[str, object]] = []
    segments: list[dict[str, object]] = []
    segment_number = 0
    first_ingestive_replaced = False
    head_columns = {
        "INGESTIVE_BEHAVIOR": "ingestive_behavior",
        "POSTURE_ACTIVITY": "posture_activity",
        "WELFARE_OBSERVATION": "welfare_state",
        "DATA_VALIDITY": "invalid_data",
    }

    for session_id, session in samples.groupby("session_id", sort=False):
        session = session.reset_index(drop=True)
        times = session["monotonic_time_ns"].astype("int64").to_numpy()
        interval = int(np.median(np.diff(times)))
        for head, column in head_columns.items():
            raw_values = session[column].tolist()
            values = [
                ("INVALID" if bool(value) else "VALID") if head == "DATA_VALIDITY" else str(value)
                for value in raw_values
            ]
            starts = [0] + [
                index
                for index in range(1, len(values))
                if values[index] != values[index - 1]
            ]
            for group_index, start in enumerate(starts):
                end = starts[group_index + 1] if group_index + 1 < len(starts) else len(values)
                onset = int(times[start])
                offset = int(times[end]) if end < len(times) else int(times[-1]) + interval
                label = values[start]
                if (
                    head == "INGESTIVE_BEHAVIOR"
                    and first_ingestive_override is not None
                    and not first_ingestive_replaced
                ):
                    label = first_ingestive_override
                    first_ingestive_replaced = True
                segment_number += 1
                consensus_id = f"CONS-{segment_number:04d}"
                adjudication_id = f"ADJ-{segment_number:04d}"
                animal_id = str(session["animal_id"].iloc[0])
                source_annotation_ids: list[str] = []
                for suffix, rater_id, adjudication_status in (
                    ("R1", "RATER-1", "ACCEPTED"),
                    ("R2", "RATER-2", "ACCEPTED"),
                    ("ADJ", "ADJUDICATOR-1", "ADJUDICATOR_RECORD"),
                ):
                    annotation_id = f"ANN-{segment_number:04d}-{suffix}"
                    source_annotation_ids.append(annotation_id)
                    annotation_rows.append(
                        {
                        "annotation_schema_version": "1",
                        "annotation_id": annotation_id,
                        "session_id": session_id,
                        "animal_id": animal_id,
                        "rater_id": rater_id,
                        "head": head,
                        "label": label,
                        "onset_monotonic_ns": str(onset),
                        "offset_monotonic_ns": str(offset),
                        "media_id": "VIDEO-1",
                        "media_clock": "VIDEO_FRAME_INDEX",
                        "media_onset": "0",
                        "media_offset": "1",
                        "clock_mapping_id": "CLOCK-1",
                        "ethogram_id": "ETHOGRAM-1",
                        "ethogram_version": "1.0.0",
                        "confidence": "HIGH",
                        "visibility": "CLEAR",
                        "invalid_data": "false",
                        "revision": "1",
                        "supersedes_annotation_id": "",
                        "annotation_tool": "fixture",
                        "annotation_tool_version": "1.0.0",
                        "created_at_epoch_ms": "1700000000000",
                        "adjudication_status": adjudication_status,
                        "adjudication_id": adjudication_id,
                        "notes": "",
                        }
                    )
                segments.append(
                    {
                        "consensus_id": consensus_id,
                        "session_id": session_id,
                        "animal_id": animal_id,
                        "head": head,
                        "label": label,
                        "onset_monotonic_ns": onset,
                        "offset_monotonic_ns": offset,
                        "source_annotation_ids": source_annotation_ids,
                        "resolution": "ADJUDICATED",
                        "adjudication_id": adjudication_id,
                        "confidence": "HIGH",
                        "visibility": "CLEAR",
                        "invalid_data": False,
                    }
                )

    annotations_path = directory / "annotations-v1.csv"
    pd.DataFrame(annotation_rows, columns=annotation_columns).to_csv(
        annotations_path, index=False
    )
    annotations_sha256 = _sha256(annotations_path)
    consensus = {
        "consensus_schema_version": 1,
        "materialization_id": "MATERIALIZATION-001",
        "frozen": True,
        "experiment_id": "EXP-001",
        "generated_at": "2026-08-01T00:00:00Z",
        "input_annotations_sha256": annotations_sha256,
        "input_annotation_schema_version": 1,
        "ethogram_id": "ETHOGRAM-1",
        "ethogram_version": "1.0.0",
        "consensus_method": "ADJUDICATED",
        "consensus_method_version": "1.0.0",
        "code_revision": "a" * 40,
        "segments": segments,
    }
    consensus_path = directory / "annotation-consensus-v1.json"
    consensus_path.write_text(json.dumps(consensus, indent=2) + "\n", encoding="utf-8")

    manifest_paths: list[Path] = []
    for session_id, session in samples.groupby("session_id", sort=False):
        animal_id = str(session["animal_id"].iloc[0])
        manifest = {
            "manifest_schema_version": 1,
            "experiment_id": "EXP-001",
            "manifest_revision": 1,
            "supersedes_manifest_sha256": None,
            "created_at": "2026-08-01T00:00:00Z",
            "protocol": {
                "protocol_id": "PROTO-001",
                "version": "1.0.0",
                "title": "Fixture protocol",
                "registration_uri": "https://example.test/protocol",
                "registered_at": "2026-08-01T00:00:00Z",
                "ethics_approval_ids": ["ETHICS-001"],
                "primary_endpoint": "Grouped behavior classification",
                "analysis_plan_uri": "https://example.test/analysis",
                "sample_size_method": "Fixture only",
                "inclusion_criteria": ["Enrolled animal"],
                "exclusion_criteria": ["Invalid mount"],
                "randomization_method": "Pre-specified",
                "blinding_method": "Annotators blinded to models",
                "minimum_double_annotation_fraction": 1.0,
                "stopping_rules": ["Animal distress"],
                "habituation_plan": "Supervised habituation",
                "counterbalancing_plan": "Balanced device order",
            },
            "session": {
                "session_id": session_id,
                "farm_id": "FARM-001",
                "site_id": "SITE-001",
                "shed_id": "SHED-001",
                "pen_id": "PEN-001",
                "timezone": "Asia/Kolkata",
                "start_time": "2026-08-01T00:00:00Z",
                "end_time": "2026-08-01T00:10:00Z",
                "source_export_schema_version": 1,
                "raw_export_sha256": raw_export_sha256,
            },
            "animal": {
                "animal_id": animal_id,
                "species": str(session["species"].iloc[0]),
                "breed": "TEST",
                "sex": "UNKNOWN",
                "birth_date": "2024-01-01",
                "age_days_at_start": 500,
                "body_mass_kg": 30.0,
                "life_stage": "ADULT",
                "health_status": "Study normal",
                "treatments": [],
            },
            "sensor": {
                "source": str(session["source"].iloc[0]),
                "device_id": str(session["device_id"].iloc[0]),
                "hardware_revision": "XIAO-SENSE-1",
                "firmware_version": "1.0.0",
                "firmware_commit": "b" * 40,
                "app_version": "1.0.0",
                "app_commit": "c" * 40,
                "ble_protocol_version": 2,
                "placement": str(session["placement"].iloc[0]),
                "placement_side": "LEFT",
                "orientation_description": "Fixture orientation",
                "enclosure_id": "ENC-001",
                "enclosure_version": "1.0.0",
                "enclosure_mass_g": 20.0,
                "requested_sample_rate_hz": 10.0,
                "achieved_sample_rate_hz": 10.0,
                "accelerometer_range_g": 4.0,
                "gyroscope_range_deg_s": 500.0,
                "capabilities_sha256": "d" * 64,
                "device_dropped_samples": 0,
            },
            "calibration": {
                "status": "PROJECT_CALIBRATED",
                "calibration_id": "CAL-001",
                "method_uri": "https://example.test/calibration",
                "performed_at": "2026-08-01T00:00:00Z",
                "coefficient_artifact_uri": "https://example.test/calibration.json",
                "coefficient_artifact_sha256": "e" * 64,
                "applied_to_raw_export": False,
                "operator_id": "OP-001",
                "temperature_c": 25.0,
            },
            "cameras": [
                {
                    "camera_id": "VIDEO-1",
                    "position": "OVERHEAD",
                    "media_uri": "https://example.test/video.mp4",
                    "media_sha256": "f" * 64,
                    "frame_rate_hz": 30.0,
                    "resolution": "1920x1080",
                    "clock_source": "CAMERA_CLOCK",
                    "media_clock": "VIDEO_FRAME_INDEX",
                    "clock_mapping_id": "CLOCK-1",
                    "clock_mapping_uri": "https://example.test/clock-mapping.json",
                    "clock_mapping_sha256": "1" * 64,
                    "dropped_frame_assessment": "No drops observed",
                }
            ],
            "video_absence_reason": None,
            "annotation": {
                "ethogram_id": "ETHOGRAM-1",
                "ethogram_version": "1.0.0",
                "tool": "fixture",
                "tool_version": "1.0.0",
                "rater_ids": ["RATER-1", "RATER-2", "ADJUDICATOR-1"],
                "planned_double_annotation_fraction": 1.0,
                "achieved_double_annotation_fraction": 1.0,
                "consensus_method": "ADJUDICATED",
                "consensus_method_version": "1.0.0",
                "blinded_to_model_outputs": True,
                "raters_blinded_to_each_other": True,
            },
            "husbandry": {
                "ration_description": "Fixture ration",
                "feed_delivery_schedule": "08:00",
                "water_access": "Ad libitum",
                "housing_conditions": "Indoor stall",
                "ambient_conditions_uri": "https://example.test/ambient.csv",
            },
            "study_design": {
                "study_arm": "BASELINE",
                "device_allocation_method": "Pre-specified",
                "mount_order": "Neck only",
                "session_order_method": "Chronological",
                "operator_id": "OP-001",
            },
            "missingness": [
                {
                    "json_pointer": "/supersedes_manifest_sha256",
                    "status": "NOT_APPLICABLE",
                    "reason": "Initial revision",
                },
                {
                    "json_pointer": "/video_absence_reason",
                    "status": "NOT_APPLICABLE",
                    "reason": "Video is present",
                },
            ],
            "notes": ["Synthetic fixture"],
        }
        manifest_path = directory / f"manifest-{session_id}.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        manifest_paths.append(manifest_path)

    return {
        "samples": samples_path,
        "manifests": manifest_paths,
        "annotations": annotations_path,
        "consensus": consensus_path,
    }


@pytest.fixture
def research_bundle_factory():
    return write_research_bundle
