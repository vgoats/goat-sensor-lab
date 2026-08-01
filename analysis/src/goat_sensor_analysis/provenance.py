"""Digest-verified experiment provenance and frozen-consensus label joins."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from jsonschema import Draft202012Validator, FormatChecker

from .schema import ENUMS, DataValidationError, read_samples

ANNOTATION_HEAD_LABELS = {
    "INGESTIVE_BEHAVIOR": ENUMS["ingestive_behavior"],
    "POSTURE_ACTIVITY": ENUMS["posture_activity"],
    "WELFARE_OBSERVATION": ENUMS["welfare_state"],
    "DATA_VALIDITY": {"VALID", "INVALID"},
}
HEAD_TO_SAMPLE_COLUMN = {
    "INGESTIVE_BEHAVIOR": "ingestive_behavior",
    "POSTURE_ACTIVITY": "posture_activity",
    "WELFARE_OBSERVATION": "welfare_state",
}
RESEARCH_DOMAIN_COLUMNS = (
    "experiment_id",
    "farm_id",
    "site_id",
    "shed_id",
    "pen_id",
    "calibration_id",
    "calibration_status",
    "calibration_applied_to_raw_export",
    "calibration_coefficients_sha256",
    "protocol_version",
    "ble_protocol_version",
    "hardware_revision",
    "firmware_version",
    "firmware_commit",
    "app_version",
    "app_commit",
    "requested_sample_rate_hz",
    "accelerometer_range_g",
    "gyroscope_range_deg_s",
    "placement_side",
    "orientation_description",
    "enclosure_id",
    "enclosure_version",
    "enclosure_mass_g",
    "ethogram_id",
    "ethogram_version",
    "consensus_method",
    "consensus_protocol_version",
    "consensus_code_revision",
    "label_provenance_mode",
)


@dataclass(frozen=True)
class ValidatedResearchProvenance:
    """Evidence that manifests and annotation inputs passed the research gate."""

    manifests: tuple[dict[str, Any], ...]
    verified_inputs: tuple[dict[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": "frozen_consensus",
            "manifests": list(self.manifests),
            "verified_inputs": list(self.verified_inputs),
        }


@dataclass(frozen=True)
class ResearchDataset:
    samples: pd.DataFrame
    provenance: ValidatedResearchProvenance


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _schema_path(filename: str) -> Path:
    return Path(__file__).resolve().parents[3] / "schema" / filename


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataValidationError([f"{path}: invalid JSON: {exc}"]) from exc
    if not isinstance(value, dict):
        raise DataValidationError([f"{path}: JSON root must be an object"])
    return value


def _validate_json_schema(value: dict[str, Any], schema_filename: str, source: Path) -> None:
    schema = _read_json(_schema_path(schema_filename))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(value), key=lambda error: list(error.absolute_path))
    if errors:
        issues = []
        for error in errors[:20]:
            location = "/".join(str(item) for item in error.absolute_path) or "<root>"
            issues.append(f"{source}: schema {schema_filename} at {location}: {error.message}")
        raise DataValidationError(issues)


def _validate_manifest_missingness(manifest: dict[str, Any], source: Path) -> None:
    null_pointers: set[str] = set()

    def walk(value: Any, pointer: str) -> None:
        if value is None:
            null_pointers.add(pointer)
        elif isinstance(value, dict):
            for key, child in value.items():
                if key == "missingness" and pointer == "":
                    continue
                escaped = key.replace("~", "~0").replace("/", "~1")
                walk(child, f"{pointer}/{escaped}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{pointer}/{index}")

    walk(manifest, "")
    missingness_pointers = [item["json_pointer"] for item in manifest["missingness"]]
    if len(missingness_pointers) != len(set(missingness_pointers)):
        raise DataValidationError([f"{source}: duplicate missingness JSON Pointer"])
    if set(missingness_pointers) != null_pointers:
        raise DataValidationError(
            [
                f"{source}: missingness must exactly explain null fields; "
                f"expected={sorted(null_pointers)}, got={sorted(missingness_pointers)}"
            ]
        )


def _validate_annotations(path: Path) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    schema = _read_json(_schema_path("annotations-v1.schema.json"))
    expected_columns = [column["name"] for column in schema["columns"]]
    try:
        frame = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except (OSError, pd.errors.ParserError) as exc:
        raise DataValidationError([f"{path}: cannot read annotations CSV: {exc}"]) from exc
    if list(frame.columns) != expected_columns:
        raise DataValidationError(
            [f"{path}: columns do not match annotations-v1.schema.json in exact order"]
        )
    if frame.empty:
        raise DataValidationError([f"{path}: annotations snapshot has no rows"])

    issues: list[str] = []
    for definition in schema["columns"]:
        column = definition["name"]
        blank = frame[column].str.strip().eq("")
        if not definition["nullable"] and blank.any():
            issues.append(f"{path}: {column} contains blank required values")
        if "enum" in definition:
            invalid = ~blank & ~frame[column].isin(definition["enum"])
            if invalid.any():
                issues.append(f"{path}: {column} contains values outside its schema enum")
        if definition["type"] in {"integer", "number"}:
            numeric = pd.to_numeric(frame[column].mask(blank), errors="coerce")
            if ((~blank) & numeric.isna()).any():
                issues.append(f"{path}: {column} contains malformed numeric values")
            if definition["type"] == "integer" and numeric.dropna().mod(1).ne(0).any():
                issues.append(f"{path}: {column} contains non-integer values")
        if definition["type"] == "boolean" and (~frame[column].isin({"true", "false"})).any():
            issues.append(f"{path}: {column} must contain lowercase true/false")

    if issues:
        raise DataValidationError(issues[:50])

    if frame["annotation_id"].duplicated().any():
        issues.append(f"{path}: annotation_id values are not unique")
    if not frame["annotation_schema_version"].eq("1").all():
        issues.append(f"{path}: annotation_schema_version must be 1")
    for row in frame.itertuples(index=False):
        if row.head in ANNOTATION_HEAD_LABELS and row.label not in ANNOTATION_HEAD_LABELS[row.head]:
            issues.append(f"{path}: label {row.label!r} is invalid for head {row.head}")
        if row.head != "EVENT":
            if not row.offset_monotonic_ns:
                issues.append(f"{path}: state annotation {row.annotation_id} has no offset")
            elif int(row.offset_monotonic_ns) <= int(row.onset_monotonic_ns):
                issues.append(f"{path}: annotation {row.annotation_id} has a non-positive interval")
        media_fields = (
            row.media_id,
            row.media_onset,
            row.media_offset,
            row.clock_mapping_id,
        )
        if row.media_clock == "NONE":
            if any(media_fields):
                issues.append(
                    f"{path}: annotation {row.annotation_id} uses media_clock NONE "
                    "but retains media or clock-mapping fields"
                )
        else:
            required_media = (row.media_id, row.media_onset, row.clock_mapping_id)
            if not all(required_media):
                issues.append(
                    f"{path}: annotation {row.annotation_id} has incomplete media provenance"
                )
            if row.head != "EVENT" and not row.media_offset:
                issues.append(
                    f"{path}: state annotation {row.annotation_id} has no media_offset"
                )
            if row.media_offset and float(row.media_offset) <= float(row.media_onset):
                issues.append(
                    f"{path}: annotation {row.annotation_id} has a non-positive media interval"
                )
        if row.adjudication_status == "ADJUDICATOR_RECORD" and not row.adjudication_id:
            issues.append(
                f"{path}: adjudicator record {row.annotation_id} has no adjudication_id"
            )
        annotation_invalid = row.invalid_data == "true"
        if row.head == "DATA_VALIDITY":
            if row.label == "INVALID" and not annotation_invalid:
                issues.append(
                    f"{path}: DATA_VALIDITY annotation {row.annotation_id} labeled INVALID "
                    "must set invalid_data=true"
                )
            elif row.label == "VALID" and annotation_invalid:
                issues.append(
                    f"{path}: DATA_VALIDITY annotation {row.annotation_id} labeled VALID "
                    "must set invalid_data=false"
                )

    annotation_index = frame.set_index("annotation_id", drop=False)
    superseded_by: dict[str, str] = {}
    for row in frame.itertuples(index=False):
        previous_id = row.supersedes_annotation_id
        if not previous_id:
            if int(row.revision) != 1:
                issues.append(
                    f"{path}: original annotation {row.annotation_id} must have revision 1"
                )
            continue
        if previous_id not in annotation_index.index:
            issues.append(
                f"{path}: annotation {row.annotation_id} supersedes unknown ID {previous_id}"
            )
            continue
        if previous_id in superseded_by:
            issues.append(f"{path}: annotation {previous_id} is superseded more than once")
        superseded_by[previous_id] = row.annotation_id
        previous = annotation_index.loc[previous_id]
        for key in ("session_id", "animal_id", "rater_id", "head"):
            if str(previous[key]) != str(getattr(row, key)):
                issues.append(
                    f"{path}: annotation {row.annotation_id} changes {key} across a revision"
                )
        if int(row.revision) != int(previous["revision"]) + 1:
            issues.append(
                f"{path}: annotation {row.annotation_id} revision does not increment by one"
            )
        if int(row.created_at_epoch_ms) <= int(previous["created_at_epoch_ms"]):
            issues.append(
                f"{path}: annotation {row.annotation_id} revision time is not increasing"
            )

    for annotation_id in frame["annotation_id"]:
        visited: set[str] = set()
        current = annotation_id
        while current in superseded_by:
            if current in visited:
                issues.append(f"{path}: annotation supersession cycle includes {current}")
                break
            visited.add(current)
            current = superseded_by[current]
    if issues:
        raise DataValidationError(issues[:50])
    active = frame[~frame["annotation_id"].isin(superseded_by)].copy()
    return frame, active, sha256_file(path)


def _required_domain(manifest: dict[str, Any], consensus: dict[str, Any]) -> dict[str, str]:
    candidates: dict[str, Any] = {
        "experiment_id": manifest["experiment_id"],
        "farm_id": manifest["session"]["farm_id"],
        "site_id": manifest["session"]["site_id"],
        "shed_id": manifest["session"]["shed_id"],
        "pen_id": manifest["session"]["pen_id"],
        "calibration_id": manifest["calibration"]["calibration_id"],
        "calibration_status": manifest["calibration"]["status"],
        "calibration_applied_to_raw_export": manifest["calibration"][
            "applied_to_raw_export"
        ],
        "calibration_coefficients_sha256": manifest["calibration"][
            "coefficient_artifact_sha256"
        ],
        "protocol_version": (
            f"{manifest['protocol']['protocol_id']}@{manifest['protocol']['version']}"
        ),
        "ble_protocol_version": manifest["sensor"]["ble_protocol_version"],
        "hardware_revision": manifest["sensor"]["hardware_revision"],
        "firmware_version": manifest["sensor"]["firmware_version"],
        "firmware_commit": manifest["sensor"]["firmware_commit"],
        "app_version": manifest["sensor"]["app_version"],
        "app_commit": manifest["sensor"]["app_commit"],
        "requested_sample_rate_hz": manifest["sensor"]["requested_sample_rate_hz"],
        "accelerometer_range_g": manifest["sensor"]["accelerometer_range_g"],
        "gyroscope_range_deg_s": manifest["sensor"]["gyroscope_range_deg_s"],
        "placement_side": manifest["sensor"]["placement_side"],
        "orientation_description": manifest["sensor"]["orientation_description"],
        "enclosure_id": manifest["sensor"]["enclosure_id"],
        "enclosure_version": manifest["sensor"]["enclosure_version"],
        "enclosure_mass_g": manifest["sensor"]["enclosure_mass_g"],
        "ethogram_id": manifest["annotation"]["ethogram_id"],
        "ethogram_version": manifest["annotation"]["ethogram_version"],
        "consensus_method": consensus["consensus_method"],
        "consensus_protocol_version": consensus["consensus_method_version"],
        "consensus_code_revision": consensus["code_revision"],
        "label_provenance_mode": "FROZEN_CONSENSUS",
    }
    missing = [
        key
        for key, value in candidates.items()
        if value is None or str(value).strip() == ""
    ]
    if missing:
        raise DataValidationError([f"research modeling domain key(s) missing: {missing}"])
    return {
        key: ("true" if value is True else "false" if value is False else str(value))
        for key, value in candidates.items()
    }


def _validate_consensus_sources(
    consensus: dict[str, Any], active_annotations: pd.DataFrame, source: Path
) -> None:
    annotation_index = active_annotations.set_index("annotation_id", drop=False)
    issues: list[str] = []
    for segment in consensus["segments"]:
        source_rows: list[pd.Series] = []
        for annotation_id in segment["source_annotation_ids"]:
            if annotation_id not in annotation_index.index:
                issues.append(
                    f"{source}: source_annotation_id {annotation_id} is unknown or not active"
                )
                continue
            row = annotation_index.loc[annotation_id]
            source_rows.append(row)
            for key in ("session_id", "animal_id", "head"):
                if str(row[key]) != str(segment[key]):
                    issues.append(
                        f"{source}: source annotation {annotation_id} does not match segment {key}"
                    )
            if row["ethogram_id"] != consensus["ethogram_id"] or row[
                "ethogram_version"
            ] != consensus["ethogram_version"]:
                issues.append(f"{source}: source annotation {annotation_id} ethogram mismatch")
            if row["adjudication_status"] in {"REJECTED", "EXCLUDED"}:
                issues.append(f"{source}: source annotation {annotation_id} is not accepted")
            segment_offset = segment["offset_monotonic_ns"]
            row_offset = row["offset_monotonic_ns"]
            if segment_offset is not None and (
                not row_offset
                or int(row["onset_monotonic_ns"]) > int(segment["onset_monotonic_ns"])
                or int(row_offset) < int(segment_offset)
            ):
                issues.append(
                    f"{source}: source annotation {annotation_id} does not cover its segment"
                )

        accepted_rows = [
            row
            for row in source_rows
            if row["adjudication_status"] in {"ACCEPTED", "ADJUDICATOR_RECORD"}
        ]
        accepted_independent_rows = [
            row
            for row in accepted_rows
            if row["adjudication_status"] != "ADJUDICATOR_RECORD"
        ]
        consensus_invalid = bool(segment["invalid_data"])
        any_accepted_invalid = any(
            str(row["invalid_data"]).lower() == "true" for row in accepted_rows
        )
        if any_accepted_invalid and not consensus_invalid:
            issues.append(
                f"{source}: segment {segment['consensus_id']} launders invalid_data=true "
                "from an accepted source into invalid_data=false"
            )

        if segment["head"] == "DATA_VALIDITY":
            if segment["label"] == "INVALID" and not consensus_invalid:
                issues.append(
                    f"{source}: DATA_VALIDITY segment {segment['consensus_id']} labeled "
                    "INVALID must set invalid_data=true"
                )
            elif segment["label"] == "VALID" and (
                consensus_invalid or any_accepted_invalid
            ):
                issues.append(
                    f"{source}: DATA_VALIDITY segment {segment['consensus_id']} labeled "
                    "VALID requires invalid_data=false for the consensus and all accepted sources"
                )

        if segment["resolution"] == "NO_CONSENSUS" and not consensus_invalid:
            issues.append(
                f"{source}: NO_CONSENSUS segment {segment['consensus_id']} must set "
                "invalid_data=true"
            )

        if segment["resolution"] == "ADJUDICATED":
            adjudication_id = segment["adjudication_id"]
            if not adjudication_id:
                issues.append(
                    f"{source}: ADJUDICATED segment {segment['consensus_id']} "
                    "has no adjudication_id"
                )
                continue
            independent_rows = [
                row
                for row in source_rows
                if row["adjudication_status"] != "ADJUDICATOR_RECORD"
            ]
            nonaccepted = [
                str(row["annotation_id"])
                for row in independent_rows
                if row["adjudication_status"] != "ACCEPTED"
            ]
            if nonaccepted:
                issues.append(
                    f"{source}: ADJUDICATED segment {segment['consensus_id']} cites "
                    f"non-accepted annotation(s) {nonaccepted}"
                )
            independent_raters = {str(row["rater_id"]) for row in independent_rows}
            if len(independent_raters) < 2:
                issues.append(
                    f"{source}: ADJUDICATED segment {segment['consensus_id']} "
                    "does not cite two independent raters"
                )
            adjudicator_rows = [
                row
                for row in source_rows
                if row["adjudication_status"] == "ADJUDICATOR_RECORD"
                and row["adjudication_id"] == adjudication_id
            ]
            if len(adjudicator_rows) != 1:
                issues.append(
                    f"{source}: ADJUDICATED segment {segment['consensus_id']} lacks exactly "
                    "one matching ADJUDICATOR_RECORD"
                )
            elif (
                adjudicator_rows[0]["label"] != segment["label"]
                or int(adjudicator_rows[0]["onset_monotonic_ns"])
                != int(segment["onset_monotonic_ns"])
                or int(adjudicator_rows[0]["offset_monotonic_ns"])
                != int(segment["offset_monotonic_ns"])
                or (str(adjudicator_rows[0]["invalid_data"]).lower() == "true")
                != consensus_invalid
            ):
                issues.append(
                    f"{source}: adjudicator record does not exactly materialize segment "
                    f"{segment['consensus_id']}"
                )
            elif str(adjudicator_rows[0]["rater_id"]) in independent_raters:
                issues.append(
                    f"{source}: adjudicator for segment {segment['consensus_id']} "
                    "must be distinct from the independent raters"
                )
            inconsistent_ids = {
                str(row["adjudication_id"])
                for row in source_rows
                if row["adjudication_id"]
            } - {str(adjudication_id)}
            if inconsistent_ids:
                issues.append(
                    f"{source}: segment {segment['consensus_id']} has inconsistent "
                    "adjudication IDs"
                )
        else:
            if segment["adjudication_id"] is not None:
                issues.append(
                    f"{source}: non-adjudicated segment {segment['consensus_id']} "
                    "must not claim an adjudication_id"
                )
            independent_rows = [
                row
                for row in source_rows
                if row["adjudication_status"] != "ADJUDICATOR_RECORD"
            ]
            nonaccepted = [
                str(row["annotation_id"])
                for row in independent_rows
                if row["adjudication_status"] != "ACCEPTED"
            ]
            if nonaccepted:
                issues.append(
                    f"{source}: non-adjudicated segment {segment['consensus_id']} cites "
                    f"non-accepted annotation(s) {nonaccepted}"
                )
            votes_by_rater: dict[str, str] = {}
            for row in independent_rows:
                rater_id = str(row["rater_id"])
                label = str(row["label"])
                prior = votes_by_rater.get(rater_id)
                if prior is not None and prior != label:
                    issues.append(
                        f"{source}: rater {rater_id} casts conflicting votes for segment "
                        f"{segment['consensus_id']}"
                    )
                votes_by_rater[rater_id] = label
            resolution = segment["resolution"]
            if resolution == "UNANIMOUS":
                if len(votes_by_rater) < 2 or set(votes_by_rater.values()) != {
                    str(segment["label"])
                }:
                    issues.append(
                        f"{source}: UNANIMOUS segment {segment['consensus_id']} is not "
                        "supported by two agreeing independent raters"
                    )
                independent_invalid = any(
                    str(row["invalid_data"]).lower() == "true"
                    for row in accepted_independent_rows
                )
                if consensus_invalid != independent_invalid:
                    issues.append(
                        f"{source}: UNANIMOUS segment {segment['consensus_id']} invalid_data "
                        "does not equal the contributing-rater OR"
                    )
            elif resolution == "MAJORITY":
                votes = list(votes_by_rater.values())
                winning_votes = votes.count(str(segment["label"]))
                if len(votes_by_rater) < 3 or winning_votes <= len(votes) / 2:
                    issues.append(
                        f"{source}: MAJORITY segment {segment['consensus_id']} does not "
                        "have a strict majority of at least three independent raters"
                    )
                independent_invalid = any(
                    str(row["invalid_data"]).lower() == "true"
                    for row in accepted_independent_rows
                )
                if consensus_invalid != independent_invalid:
                    issues.append(
                        f"{source}: MAJORITY segment {segment['consensus_id']} invalid_data "
                        "does not equal the contributing-rater OR"
                    )
        expected_resolution = consensus["consensus_method"]
        if (
            expected_resolution != "MIXED"
            and segment["resolution"] != "NO_CONSENSUS"
            and segment["resolution"] != expected_resolution
        ):
            issues.append(
                f"{source}: segment {segment['consensus_id']} resolution does not match "
                f"top-level consensus_method {expected_resolution}"
            )
    if issues:
        raise DataValidationError(issues[:50])


def _validate_annotation_media_links(
    annotations: pd.DataFrame,
    manifest: dict[str, Any],
    source: Path,
) -> None:
    cameras = manifest["cameras"]
    camera_ids = [camera["camera_id"] for camera in cameras]
    if len(camera_ids) != len(set(camera_ids)):
        raise DataValidationError([f"{source}: manifest camera_id values are not unique"])
    cameras_by_id = {camera["camera_id"]: camera for camera in cameras}
    issues: list[str] = []
    for row in annotations.itertuples(index=False):
        if row.media_clock == "NONE":
            continue
        camera = cameras_by_id.get(row.media_id)
        if camera is None:
            issues.append(
                f"{source}: annotation {row.annotation_id} cites unknown media_id {row.media_id}"
            )
            continue
        missing_immutable_fields = [
            key
            for key in (
                "media_uri",
                "media_sha256",
                "clock_mapping_id",
                "clock_mapping_uri",
                "clock_mapping_sha256",
            )
            if camera.get(key) is None or str(camera.get(key)).strip() == ""
        ]
        if missing_immutable_fields:
            issues.append(
                f"{source}: camera {row.media_id} lacks immutable media/mapping fields "
                f"{missing_immutable_fields}"
            )
        if row.clock_mapping_id != str(camera.get("clock_mapping_id")):
            issues.append(
                f"{source}: annotation {row.annotation_id} clock_mapping_id does not "
                f"match camera {row.media_id}"
            )
        if row.media_clock != str(camera.get("media_clock")):
            issues.append(
                f"{source}: annotation {row.annotation_id} media_clock does not "
                f"match camera {row.media_id}"
            )
    if issues:
        raise DataValidationError(issues[:50])


def _duration_weighted_double_annotation_coverage(
    annotations: pd.DataFrame,
    source: Path,
) -> dict[str, Any]:
    eligible = annotations[annotations["adjudication_status"].eq("ACCEPTED")]
    per_head: dict[str, float] = {}
    for head in ANNOTATION_HEAD_LABELS:
        rows = eligible[eligible["head"].eq(head)]
        if rows.empty:
            raise DataValidationError([f"{source}: no active independent annotations for {head}"])
        boundaries = sorted(
            {
                int(value)
                for row in rows.itertuples(index=False)
                for value in (row.onset_monotonic_ns, row.offset_monotonic_ns)
                if value
            }
        )
        covered_duration = 0
        double_duration = 0
        for onset, offset in zip(boundaries, boundaries[1:], strict=False):
            if offset <= onset:
                continue
            active_raters = {
                str(row.rater_id)
                for row in rows.itertuples(index=False)
                if int(row.onset_monotonic_ns) <= onset
                and int(row.offset_monotonic_ns) >= offset
            }
            if not active_raters:
                continue
            duration = offset - onset
            covered_duration += duration
            if len(active_raters) >= 2:
                double_duration += duration
        if covered_duration <= 0:
            raise DataValidationError([f"{source}: {head} has no positive active duration"])
        per_head[head] = double_duration / covered_duration
    return {
        "method": "duration_weighted_active_revision_minimum_across_heads",
        "per_head": per_head,
        "minimum_across_heads": min(per_head.values()),
    }


def _validate_annotation_quality_gate(
    active_annotations: pd.DataFrame,
    manifest: dict[str, Any],
    source: Path,
) -> dict[str, Any]:
    annotation_contract = manifest["annotation"]
    if annotation_contract["blinded_to_model_outputs"] is not True:
        raise DataValidationError([f"{source}: annotators were not blinded to model outputs"])
    if annotation_contract["raters_blinded_to_each_other"] is not True:
        raise DataValidationError([f"{source}: independent raters were not mutually blinded"])
    threshold = manifest["protocol"]["minimum_double_annotation_fraction"]
    planned = annotation_contract["planned_double_annotation_fraction"]
    declared_achieved = annotation_contract["achieved_double_annotation_fraction"]
    if planned is None or declared_achieved is None:
        raise DataValidationError([f"{source}: double-annotation fractions must be explicit"])
    coverage = _duration_weighted_double_annotation_coverage(active_annotations, source)
    computed = float(coverage["minimum_across_heads"])
    tolerance = 1e-9
    if float(planned) + tolerance < float(threshold):
        raise DataValidationError(
            [f"{source}: planned double-annotation coverage is below protocol minimum"]
        )
    if computed + tolerance < float(planned):
        raise DataValidationError(
            [f"{source}: computed active double-annotation coverage is below plan"]
        )
    if abs(float(declared_achieved) - computed) > tolerance:
        raise DataValidationError(
            [
                f"{source}: declared achieved double-annotation fraction does not equal "
                f"computed active coverage ({declared_achieved} != {computed})"
            ]
        )
    coverage["protocol_minimum"] = float(threshold)
    coverage["planned"] = float(planned)
    coverage["declared_achieved"] = float(declared_achieved)
    return coverage


def _join_consensus_session(
    session: pd.DataFrame,
    consensus: dict[str, Any],
    *,
    domain: dict[str, str],
    source: Path,
) -> pd.DataFrame:
    session_id = str(session["session_id"].iloc[0])
    animal_id = str(session["animal_id"].iloc[0])
    timestamps = session["monotonic_time_ns"].to_numpy(dtype="int64")
    joined = session.copy()
    invalid = pd.Series(False, index=joined.index, dtype=bool)

    for head in (*HEAD_TO_SAMPLE_COLUMN, "DATA_VALIDITY"):
        segments = [
            segment
            for segment in consensus["segments"]
            if segment["session_id"] == session_id
            and segment["animal_id"] == animal_id
            and segment["head"] == head
        ]
        if not segments:
            raise DataValidationError([f"{source}: no {head} consensus for session {session_id}"])
        segments.sort(key=lambda segment: segment["onset_monotonic_ns"])
        previous_end: int | None = None
        matches = pd.Series(0, index=joined.index, dtype=int)
        labels = pd.Series("", index=joined.index, dtype="string")
        for segment in segments:
            onset = int(segment["onset_monotonic_ns"])
            offset_value = segment["offset_monotonic_ns"]
            if offset_value is None or int(offset_value) <= onset:
                raise DataValidationError(
                    [f"{source}: consensus segment {segment['consensus_id']} has invalid interval"]
                )
            offset = int(offset_value)
            if previous_end is not None and onset < previous_end:
                raise DataValidationError(
                    [f"{source}: overlapping {head} consensus intervals for session {session_id}"]
                )
            previous_end = offset
            mask_array = (timestamps >= onset) & (timestamps < offset)
            mask = pd.Series(mask_array, index=joined.index)
            matches.loc[mask] += 1
            label = segment["label"]
            if segment["resolution"] == "NO_CONSENSUS":
                label = "INVALID" if head == "DATA_VALIDITY" else "UNKNOWN"
            if head in ANNOTATION_HEAD_LABELS and label not in ANNOTATION_HEAD_LABELS[head]:
                raise DataValidationError(
                    [f"{source}: label {label!r} is invalid for consensus head {head}"]
                )
            labels.loc[mask] = label
            if bool(segment["invalid_data"]) or segment["resolution"] == "NO_CONSENSUS":
                invalid.loc[mask] = True
        uncovered = matches.ne(1)
        if uncovered.any():
            count = int(uncovered.sum())
            raise DataValidationError(
                [f"{source}: {count} sample(s) lack exactly one {head} consensus interval"]
            )
        if head == "DATA_VALIDITY":
            invalid |= labels.eq("INVALID")
        else:
            joined[HEAD_TO_SAMPLE_COLUMN[head]] = labels.astype(str)

    joined["invalid_data"] = invalid.to_numpy()
    for column, value in domain.items():
        joined[column] = value
    return joined


def load_research_dataset(
    sample_paths: list[Path],
    manifest_paths: list[Path],
    annotation_paths: list[Path],
    consensus_paths: list[Path],
) -> ResearchDataset:
    """Load raw samples only after manifests and frozen consensus prove their provenance."""

    if not manifest_paths or not annotation_paths or not consensus_paths:
        raise DataValidationError(
            ["research training requires experiment manifests, annotations, and consensus inputs"]
        )

    sample_artifacts: dict[str, dict[str, Any]] = {}
    verified_inputs: list[dict[str, Any]] = []
    for path in sample_paths:
        digest = sha256_file(path)
        frame = read_samples(path)
        sample_artifacts[digest] = {"path": path, "frame": frame}
        verified_inputs.append(
            {
                "kind": "raw_export",
                "path": str(path),
                "sha256": digest,
                "bytes": path.stat().st_size,
            }
        )

    annotations_by_sha: dict[str, tuple[Path, pd.DataFrame, pd.DataFrame]] = {}
    for path in annotation_paths:
        frame, active, digest = _validate_annotations(path)
        if digest in annotations_by_sha:
            raise DataValidationError([f"duplicate annotations content supplied: {path}"])
        annotations_by_sha[digest] = (path, frame, active)
        verified_inputs.append(
            {
                "kind": "raw_annotations",
                "path": str(path),
                "sha256": digest,
                "bytes": path.stat().st_size,
            }
        )

    consensus_artifacts: list[dict[str, Any]] = []
    for path in consensus_paths:
        value = _read_json(path)
        _validate_json_schema(value, "annotation-consensus-v1.schema.json", path)
        annotations_entry = annotations_by_sha.get(value["input_annotations_sha256"])
        if annotations_entry is None:
            raise DataValidationError(
                [f"{path}: input_annotations_sha256 does not match supplied annotations bytes"]
            )
        _validate_consensus_sources(value, annotations_entry[2], path)
        digest = sha256_file(path)
        consensus_artifacts.append(
            {"path": path, "value": value, "sha256": digest, "annotations": annotations_entry}
        )
        verified_inputs.append(
            {
                "kind": "frozen_consensus",
                "path": str(path),
                "sha256": digest,
                "bytes": path.stat().st_size,
            }
        )

    manifests: list[dict[str, Any]] = []
    manifests_by_session: dict[str, tuple[Path, dict[str, Any], str]] = {}
    for path in manifest_paths:
        value = _read_json(path)
        _validate_json_schema(value, "experiment-manifest-v1.schema.json", path)
        _validate_manifest_missingness(value, path)
        session_id = value["session"]["session_id"]
        if session_id in manifests_by_session:
            raise DataValidationError([f"duplicate experiment manifest for session {session_id}"])
        digest = sha256_file(path)
        manifests_by_session[session_id] = (path, value, digest)
        verified_inputs.append(
            {
                "kind": "experiment_manifest",
                "path": str(path),
                "sha256": digest,
                "bytes": path.stat().st_size,
            }
        )

    joined_sessions: list[pd.DataFrame] = []
    used_sample_hashes: set[str] = set()
    used_annotation_hashes: set[str] = set()
    used_consensus_hashes: set[str] = set()
    all_sample_sessions = {
        str(session_id)
        for artifact in sample_artifacts.values()
        for session_id in artifact["frame"]["session_id"].unique()
    }
    all_sample_pairs = {
        (str(row.session_id), str(row.animal_id))
        for artifact in sample_artifacts.values()
        for row in artifact["frame"][["session_id", "animal_id"]]
        .drop_duplicates()
        .itertuples(index=False)
    }
    consensus_pairs = {
        (str(segment["session_id"]), str(segment["animal_id"]))
        for artifact in consensus_artifacts
        for segment in artifact["value"]["segments"]
        if segment["head"] != "EVENT"
    }
    annotation_pairs = {
        (str(row.session_id), str(row.animal_id))
        for _, annotations, _ in annotations_by_sha.values()
        for row in annotations[["session_id", "animal_id"]]
        .drop_duplicates()
        .itertuples(index=False)
    }
    if consensus_pairs != all_sample_pairs:
        raise DataValidationError(
            ["consensus session/animal coverage does not exactly match raw samples"]
        )
    if annotation_pairs != all_sample_pairs:
        raise DataValidationError(
            ["annotation session/animal coverage does not exactly match raw samples"]
        )
    if set(manifests_by_session) != all_sample_sessions:
        raise DataValidationError(
            [
                "experiment manifest session coverage does not exactly match raw samples: "
                f"manifests={sorted(manifests_by_session)}, samples={sorted(all_sample_sessions)}"
            ]
        )

    for session_id, (manifest_path, manifest, manifest_sha) in manifests_by_session.items():
        raw_sha = manifest["session"]["raw_export_sha256"]
        if raw_sha is None or raw_sha not in sample_artifacts:
            raise DataValidationError(
                [f"{manifest_path}: session.raw_export_sha256 does not match samples bytes"]
            )
        sample_artifact = sample_artifacts[raw_sha]
        raw_session = sample_artifact["frame"][
            sample_artifact["frame"]["session_id"].astype(str).eq(session_id)
        ].copy()
        if raw_session.empty:
            raise DataValidationError([f"{manifest_path}: session not found in bound raw export"])
        if set(raw_session["schema_version"].astype(int)) != {
            int(manifest["session"]["source_export_schema_version"])
        }:
            raise DataValidationError(
                [f"{manifest_path}: source_export_schema_version does not match raw export"]
            )
        used_sample_hashes.add(raw_sha)

        animal_id = manifest["animal"]["animal_id"]
        if set(raw_session["animal_id"].astype(str)) != {animal_id}:
            raise DataValidationError([f"{manifest_path}: animal_id does not match raw export"])
        for manifest_key, sample_column in (
            (("animal", "species"), "species"),
            (("sensor", "source"), "source"),
            (("sensor", "placement"), "placement"),
            (("sensor", "device_id"), "device_id"),
        ):
            expected = manifest[manifest_key[0]][manifest_key[1]]
            if set(raw_session[sample_column].astype(str)) != {str(expected)}:
                raise DataValidationError(
                    [f"{manifest_path}: {'.'.join(manifest_key)} does not match raw export"]
                )

        matching_consensus = [
            artifact
            for artifact in consensus_artifacts
            if any(
                segment["session_id"] == session_id and segment["animal_id"] == animal_id
                for segment in artifact["value"]["segments"]
            )
        ]
        if len(matching_consensus) != 1:
            raise DataValidationError(
                [f"session {session_id}: expected exactly one frozen consensus artifact"]
            )
        consensus_artifact = matching_consensus[0]
        consensus = consensus_artifact["value"]
        annotation_path, annotations, active_annotations = consensus_artifact["annotations"]
        annotation_sha = consensus["input_annotations_sha256"]
        used_annotation_hashes.add(annotation_sha)
        used_consensus_hashes.add(consensus_artifact["sha256"])

        if consensus["experiment_id"] != manifest["experiment_id"]:
            raise DataValidationError([f"{manifest_path}: consensus experiment_id mismatch"])
        for key in ("ethogram_id", "ethogram_version"):
            if consensus[key] != manifest["annotation"][key]:
                raise DataValidationError([f"{manifest_path}: consensus {key} mismatch"])
        session_annotations = annotations[
            annotations["session_id"].eq(session_id) & annotations["animal_id"].eq(animal_id)
        ]
        active_session_annotations = active_annotations[
            active_annotations["session_id"].eq(session_id)
            & active_annotations["animal_id"].eq(animal_id)
        ]
        if session_annotations.empty:
            raise DataValidationError([f"{annotation_path}: no rows for session {session_id}"])
        if set(session_annotations["ethogram_id"]) != {manifest["annotation"]["ethogram_id"]}:
            raise DataValidationError([f"{annotation_path}: ethogram_id mismatch"])
        if set(session_annotations["ethogram_version"]) != {
            manifest["annotation"]["ethogram_version"]
        }:
            raise DataValidationError([f"{annotation_path}: ethogram_version mismatch"])
        if set(active_session_annotations["rater_id"]) != set(
            manifest["annotation"]["rater_ids"]
        ):
            raise DataValidationError([f"{annotation_path}: rater IDs do not match manifest"])
        if consensus["consensus_method"] != manifest["annotation"]["consensus_method"]:
            raise DataValidationError([f"{manifest_path}: consensus method mismatch"])
        if consensus["consensus_method_version"] != manifest["annotation"][
            "consensus_method_version"
        ]:
            raise DataValidationError([f"{manifest_path}: consensus method version mismatch"])

        _validate_annotation_media_links(
            active_session_annotations,
            manifest,
            annotation_path,
        )
        annotation_coverage = _validate_annotation_quality_gate(
            active_session_annotations,
            manifest,
            annotation_path,
        )

        domain = _required_domain(manifest, consensus)
        joined_sessions.append(
            _join_consensus_session(
                raw_session,
                consensus,
                domain=domain,
                source=consensus_artifact["path"],
            )
        )
        manifests.append(
            {
                "experiment_id": manifest["experiment_id"],
                "session_id": session_id,
                "animal_id": animal_id,
                "manifest_sha256": manifest_sha,
                "raw_export_sha256": raw_sha,
                "raw_annotations_sha256": annotation_sha,
                "consensus_sha256": consensus_artifact["sha256"],
                "materialization_id": consensus["materialization_id"],
                "double_annotation_coverage": annotation_coverage,
            }
        )

    if used_sample_hashes != set(sample_artifacts):
        raise DataValidationError(["one or more supplied raw exports are not bound by a manifest"])
    if used_annotation_hashes != set(annotations_by_sha):
        raise DataValidationError(["one or more supplied annotation snapshots are unused"])
    if used_consensus_hashes != {artifact["sha256"] for artifact in consensus_artifacts}:
        raise DataValidationError(["one or more supplied consensus artifacts are unused"])

    samples = pd.concat(joined_sessions, ignore_index=True)
    return ResearchDataset(
        samples=samples,
        provenance=ValidatedResearchProvenance(
            manifests=tuple(manifests),
            verified_inputs=tuple(verified_inputs),
        ),
    )
