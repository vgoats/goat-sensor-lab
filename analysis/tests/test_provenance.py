from __future__ import annotations

import hashlib
import json

import pandas as pd
import pytest

from goat_sensor_analysis.provenance import load_research_dataset
from goat_sensor_analysis.schema import DataValidationError


def _load(bundle):
    return load_research_dataset(
        [bundle["samples"]],
        bundle["manifests"],
        [bundle["annotations"]],
        [bundle["consensus"]],
    )


def _write_annotations_and_rebind_consensus(bundle, annotations):
    annotations_path = bundle["annotations"]
    annotations.to_csv(annotations_path, index=False)
    consensus_path = bundle["consensus"]
    consensus = json.loads(consensus_path.read_text())
    consensus["input_annotations_sha256"] = hashlib.sha256(
        annotations_path.read_bytes()
    ).hexdigest()
    consensus_path.write_text(json.dumps(consensus), encoding="utf-8")


def test_live_labels_are_replaced_by_interval_joined_frozen_consensus(
    samples_factory, research_bundle_factory, tmp_path
):
    samples = samples_factory(seconds_per_label=2, rate_hz=10)
    assert samples["ingestive_behavior"].iloc[0] == "FEEDING"
    bundle = research_bundle_factory(
        samples,
        tmp_path,
        first_ingestive_override="NEITHER",
    )

    research = _load(bundle)

    assert research.samples["ingestive_behavior"].iloc[0] == "NEITHER"
    assert research.samples["label_provenance_mode"].eq("FROZEN_CONSENSUS").all()
    assert research.samples["farm_id"].eq("FARM-001").all()
    assert research.samples["calibration_id"].eq("CAL-001").all()
    assert research.samples["calibration_status"].eq("PROJECT_CALIBRATED").all()
    assert research.samples["firmware_commit"].eq("b" * 40).all()
    assert research.samples["requested_sample_rate_hz"].eq("10.0").all()
    assert research.provenance.manifests[0]["raw_annotations_sha256"]
    assert research.provenance.manifests[0]["consensus_sha256"]


def test_consensus_annotation_digest_must_match_exact_bytes(
    samples_factory, research_bundle_factory, tmp_path
):
    bundle = research_bundle_factory(samples_factory(seconds_per_label=2), tmp_path)
    annotations = bundle["annotations"]
    annotations.write_bytes(annotations.read_bytes() + b"\n")

    with pytest.raises(DataValidationError, match="input_annotations_sha256"):
        _load(bundle)


def test_manifest_raw_export_digest_must_match_exact_bytes(
    samples_factory, research_bundle_factory, tmp_path
):
    bundle = research_bundle_factory(samples_factory(seconds_per_label=2), tmp_path)
    samples_path = bundle["samples"]
    samples_path.write_bytes(samples_path.read_bytes() + b"\n")

    with pytest.raises(DataValidationError, match="raw_export_sha256"):
        _load(bundle)


def test_manifest_samples_schema_version_must_match_export(
    samples_factory, research_bundle_factory, tmp_path
):
    bundle = research_bundle_factory(samples_factory(seconds_per_label=2), tmp_path)
    manifest_path = bundle["manifests"][0]
    manifest = json.loads(manifest_path.read_text())
    manifest["session"]["source_export_schema_version"] = 2
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(DataValidationError, match="source_export_schema_version"):
        _load(bundle)


def test_consensus_must_be_frozen_by_schema(
    samples_factory, research_bundle_factory, tmp_path
):
    bundle = research_bundle_factory(samples_factory(seconds_per_label=2), tmp_path)
    consensus_path = bundle["consensus"]
    consensus = json.loads(consensus_path.read_text())
    consensus["frozen"] = False
    consensus_path.write_text(json.dumps(consensus), encoding="utf-8")

    with pytest.raises(DataValidationError, match="frozen"):
        _load(bundle)


@pytest.mark.parametrize(
    ("target", "replacement", "message"),
    [
        ("experiment_id", "EXP-WRONG", "experiment_id mismatch"),
        ("animal.animal_id", "GOAT-WRONG", "animal_id does not match"),
        ("annotation.ethogram_version", "2.0.0", "ethogram_version mismatch"),
    ],
)
def test_manifest_consensus_and_export_alignment_is_exact(
    samples_factory,
    research_bundle_factory,
    tmp_path,
    target,
    replacement,
    message,
):
    bundle = research_bundle_factory(samples_factory(seconds_per_label=2), tmp_path)
    manifest_path = bundle["manifests"][0]
    manifest = json.loads(manifest_path.read_text())
    if "." in target:
        parent, key = target.split(".")
        manifest[parent][key] = replacement
    else:
        manifest[target] = replacement
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(DataValidationError, match=message):
        _load(bundle)


def test_consensus_intervals_must_cover_each_sample_exactly_once(
    samples_factory, research_bundle_factory, tmp_path
):
    bundle = research_bundle_factory(samples_factory(seconds_per_label=2), tmp_path)
    consensus_path = bundle["consensus"]
    consensus = json.loads(consensus_path.read_text())
    first = consensus["segments"][0]
    first["onset_monotonic_ns"] += 1
    first["resolution"] = "PROTOCOL_RULE"
    first["adjudication_id"] = None
    first["source_annotation_ids"] = [
        annotation_id
        for annotation_id in first["source_annotation_ids"]
        if annotation_id.endswith("-R1")
    ]
    consensus["consensus_method"] = "MIXED"
    consensus_path.write_text(json.dumps(consensus), encoding="utf-8")

    manifest_path = bundle["manifests"][0]
    manifest = json.loads(manifest_path.read_text())
    manifest["annotation"]["consensus_method"] = "MIXED"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(DataValidationError, match="lack exactly one"):
        _load(bundle)


def test_required_research_domain_keys_fail_closed(
    samples_factory, research_bundle_factory, tmp_path
):
    bundle = research_bundle_factory(samples_factory(seconds_per_label=2), tmp_path)
    manifest_path = bundle["manifests"][0]
    manifest = json.loads(manifest_path.read_text())
    manifest["calibration"]["calibration_id"] = None
    manifest["missingness"].append(
        {
            "json_pointer": "/calibration/calibration_id",
            "status": "UNKNOWN",
            "reason": "Deliberately missing for the fail-closed test",
        }
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(DataValidationError, match="modeling domain key.*calibration_id"):
        _load(bundle)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("camera_id", "VIDEO-WRONG", "unknown media_id"),
        ("clock_mapping_id", "CLOCK-WRONG", "clock_mapping_id does not match"),
        ("media_clock", "VIDEO_PTS_MS", "media_clock does not match"),
    ],
)
def test_annotation_media_and_clock_references_must_match_manifest(
    samples_factory,
    research_bundle_factory,
    tmp_path,
    field,
    value,
    message,
):
    bundle = research_bundle_factory(samples_factory(seconds_per_label=2), tmp_path)
    manifest_path = bundle["manifests"][0]
    manifest = json.loads(manifest_path.read_text())
    manifest["cameras"][0][field] = value
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(DataValidationError, match=message):
        _load(bundle)


def test_annotations_media_none_rule_is_enforced(
    samples_factory, research_bundle_factory, tmp_path
):
    bundle = research_bundle_factory(samples_factory(seconds_per_label=2), tmp_path)
    annotations_path = bundle["annotations"]
    annotations = pd.read_csv(annotations_path, dtype=str, keep_default_na=False)
    annotations.loc[0, "media_clock"] = "NONE"
    annotations.to_csv(annotations_path, index=False)

    with pytest.raises(DataValidationError, match="media_clock NONE"):
        _load(bundle)


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("blinded_to_model_outputs", "not blinded to model outputs"),
        ("raters_blinded_to_each_other", "not mutually blinded"),
    ],
)
def test_annotation_blinding_is_required(
    samples_factory,
    research_bundle_factory,
    tmp_path,
    field,
    message,
):
    bundle = research_bundle_factory(samples_factory(seconds_per_label=2), tmp_path)
    manifest_path = bundle["manifests"][0]
    manifest = json.loads(manifest_path.read_text())
    manifest["annotation"][field] = False
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(DataValidationError, match=message):
        _load(bundle)


def test_planned_double_annotation_must_meet_protocol_minimum(
    samples_factory, research_bundle_factory, tmp_path
):
    bundle = research_bundle_factory(samples_factory(seconds_per_label=2), tmp_path)
    manifest_path = bundle["manifests"][0]
    manifest = json.loads(manifest_path.read_text())
    manifest["annotation"]["planned_double_annotation_fraction"] = 0.5
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(DataValidationError, match="below protocol minimum"):
        _load(bundle)


def test_double_annotation_manifest_claim_cannot_exceed_active_revision_coverage(
    samples_factory, research_bundle_factory, tmp_path
):
    bundle = research_bundle_factory(samples_factory(seconds_per_label=2), tmp_path)
    annotations_path = bundle["annotations"]
    annotations = pd.read_csv(annotations_path, dtype=str, keep_default_na=False)
    annotations = annotations[
        ~(
            annotations["head"].eq("DATA_VALIDITY")
            & annotations["rater_id"].eq("RATER-2")
        )
    ]
    annotations.to_csv(annotations_path, index=False)

    consensus_path = bundle["consensus"]
    consensus = json.loads(consensus_path.read_text())
    consensus["input_annotations_sha256"] = hashlib.sha256(
        annotations_path.read_bytes()
    ).hexdigest()
    consensus["consensus_method"] = "MIXED"
    for segment in consensus["segments"]:
        if segment["head"] == "DATA_VALIDITY":
            segment["resolution"] = "PROTOCOL_RULE"
            segment["adjudication_id"] = None
            segment["source_annotation_ids"] = [
                annotation_id
                for annotation_id in segment["source_annotation_ids"]
                if annotation_id.endswith("-R1")
            ]
    consensus_path.write_text(json.dumps(consensus), encoding="utf-8")

    manifest_path = bundle["manifests"][0]
    manifest = json.loads(manifest_path.read_text())
    manifest["annotation"]["consensus_method"] = "MIXED"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(DataValidationError, match="computed active.*below plan"):
        _load(bundle)


def test_adjudicated_consensus_requires_matching_adjudicator_record(
    samples_factory, research_bundle_factory, tmp_path
):
    bundle = research_bundle_factory(samples_factory(seconds_per_label=2), tmp_path)
    consensus_path = bundle["consensus"]
    consensus = json.loads(consensus_path.read_text())
    segment = consensus["segments"][0]
    segment["source_annotation_ids"] = [
        annotation_id
        for annotation_id in segment["source_annotation_ids"]
        if not annotation_id.endswith("-ADJ")
    ]
    consensus_path.write_text(json.dumps(consensus), encoding="utf-8")

    with pytest.raises(DataValidationError, match="ADJUDICATOR_RECORD"):
        _load(bundle)


def test_adjudicated_consensus_cannot_overclaim_single_rater(
    samples_factory, research_bundle_factory, tmp_path
):
    bundle = research_bundle_factory(samples_factory(seconds_per_label=2), tmp_path)
    consensus_path = bundle["consensus"]
    consensus = json.loads(consensus_path.read_text())
    segment = consensus["segments"][0]
    segment["source_annotation_ids"] = [
        annotation_id
        for annotation_id in segment["source_annotation_ids"]
        if not annotation_id.endswith("-R2")
    ]
    consensus_path.write_text(json.dumps(consensus), encoding="utf-8")

    with pytest.raises(DataValidationError, match="two independent raters"):
        _load(bundle)


def test_unanimous_consensus_must_recompute_agreement(
    samples_factory, research_bundle_factory, tmp_path
):
    bundle = research_bundle_factory(samples_factory(seconds_per_label=2), tmp_path)
    consensus_path = bundle["consensus"]
    consensus = json.loads(consensus_path.read_text())
    consensus["consensus_method"] = "UNANIMOUS"
    for segment in consensus["segments"]:
        segment["resolution"] = "UNANIMOUS"
        segment["adjudication_id"] = None
        segment["source_annotation_ids"] = [
            annotation_id
            for annotation_id in segment["source_annotation_ids"]
            if not annotation_id.endswith("-ADJ")
        ]
    consensus["segments"][0]["label"] = "RUMINATION"
    consensus_path.write_text(json.dumps(consensus), encoding="utf-8")

    for manifest_path in bundle["manifests"]:
        manifest = json.loads(manifest_path.read_text())
        manifest["annotation"]["consensus_method"] = "UNANIMOUS"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(DataValidationError, match="UNANIMOUS segment"):
        _load(bundle)


def test_majority_consensus_requires_three_raters_and_strict_vote_majority(
    samples_factory, research_bundle_factory, tmp_path
):
    bundle = research_bundle_factory(samples_factory(seconds_per_label=2), tmp_path)
    consensus_path = bundle["consensus"]
    consensus = json.loads(consensus_path.read_text())
    consensus["consensus_method"] = "MAJORITY"
    for segment in consensus["segments"]:
        segment["resolution"] = "MAJORITY"
        segment["adjudication_id"] = None
        segment["source_annotation_ids"] = [
            annotation_id
            for annotation_id in segment["source_annotation_ids"]
            if not annotation_id.endswith("-ADJ")
        ]
    consensus_path.write_text(json.dumps(consensus), encoding="utf-8")

    for manifest_path in bundle["manifests"]:
        manifest = json.loads(manifest_path.read_text())
        manifest["annotation"]["consensus_method"] = "MAJORITY"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(DataValidationError, match="MAJORITY segment"):
        _load(bundle)


def test_adjudicated_consensus_cannot_launder_invalid_source(
    samples_factory, research_bundle_factory, tmp_path
):
    bundle = research_bundle_factory(samples_factory(seconds_per_label=2), tmp_path)
    annotations = pd.read_csv(
        bundle["annotations"], dtype=str, keep_default_na=False
    )
    annotations.loc[annotations["annotation_id"].eq("ANN-0001-R1"), "invalid_data"] = (
        "true"
    )
    _write_annotations_and_rebind_consensus(bundle, annotations)

    with pytest.raises(DataValidationError, match="launders invalid_data=true"):
        _load(bundle)


def test_adjudicated_consensus_must_materialize_adjudicator_invalid_flag(
    samples_factory, research_bundle_factory, tmp_path
):
    bundle = research_bundle_factory(samples_factory(seconds_per_label=2), tmp_path)
    consensus_path = bundle["consensus"]
    consensus = json.loads(consensus_path.read_text())
    consensus["segments"][0]["invalid_data"] = True
    consensus_path.write_text(json.dumps(consensus), encoding="utf-8")

    with pytest.raises(
        DataValidationError, match="adjudicator record does not exactly materialize"
    ):
        _load(bundle)


def test_unanimous_consensus_invalid_flag_must_equal_contributing_or(
    samples_factory, research_bundle_factory, tmp_path
):
    bundle = research_bundle_factory(samples_factory(seconds_per_label=2), tmp_path)
    consensus_path = bundle["consensus"]
    consensus = json.loads(consensus_path.read_text())
    segment = consensus["segments"][0]
    segment["resolution"] = "UNANIMOUS"
    segment["adjudication_id"] = None
    segment["invalid_data"] = True
    segment["source_annotation_ids"] = [
        annotation_id
        for annotation_id in segment["source_annotation_ids"]
        if not annotation_id.endswith("-ADJ")
    ]
    consensus["consensus_method"] = "MIXED"
    consensus_path.write_text(json.dumps(consensus), encoding="utf-8")
    manifest_path = bundle["manifests"][0]
    manifest = json.loads(manifest_path.read_text())
    manifest["annotation"]["consensus_method"] = "MIXED"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(DataValidationError, match="UNANIMOUS segment.*invalid_data"):
        _load(bundle)


def test_majority_consensus_invalid_flag_must_equal_contributing_or(
    samples_factory, research_bundle_factory, tmp_path
):
    bundle = research_bundle_factory(samples_factory(seconds_per_label=2), tmp_path)
    annotations = pd.read_csv(
        bundle["annotations"], dtype=str, keep_default_na=False
    )
    third_vote = annotations["annotation_id"].eq("ANN-0001-ADJ")
    annotations.loc[third_vote, "rater_id"] = "RATER-3"
    annotations.loc[third_vote, "adjudication_status"] = "ACCEPTED"
    annotations.loc[third_vote, "adjudication_id"] = ""
    _write_annotations_and_rebind_consensus(bundle, annotations)

    consensus_path = bundle["consensus"]
    consensus = json.loads(consensus_path.read_text())
    segment = consensus["segments"][0]
    segment["resolution"] = "MAJORITY"
    segment["adjudication_id"] = None
    segment["invalid_data"] = True
    consensus["consensus_method"] = "MIXED"
    consensus_path.write_text(json.dumps(consensus), encoding="utf-8")
    manifest_path = bundle["manifests"][0]
    manifest = json.loads(manifest_path.read_text())
    manifest["annotation"]["consensus_method"] = "MIXED"
    manifest["annotation"]["rater_ids"].append("RATER-3")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(DataValidationError, match="MAJORITY segment.*invalid_data"):
        _load(bundle)


@pytest.mark.parametrize(
    ("label", "invalid_data", "message"),
    [
        ("INVALID", False, "labeled INVALID must set invalid_data=true"),
        ("VALID", True, "labeled VALID requires invalid_data=false"),
    ],
)
def test_consensus_data_validity_label_and_flag_must_agree(
    samples_factory,
    research_bundle_factory,
    tmp_path,
    label,
    invalid_data,
    message,
):
    bundle = research_bundle_factory(samples_factory(seconds_per_label=2), tmp_path)
    consensus_path = bundle["consensus"]
    consensus = json.loads(consensus_path.read_text())
    segment = next(
        item for item in consensus["segments"] if item["head"] == "DATA_VALIDITY"
    )
    segment["label"] = label
    segment["invalid_data"] = invalid_data
    consensus_path.write_text(json.dumps(consensus), encoding="utf-8")

    with pytest.raises(DataValidationError, match=message):
        _load(bundle)


@pytest.mark.parametrize(
    ("label", "invalid_data", "message"),
    [
        ("INVALID", "false", "labeled INVALID must set invalid_data=true"),
        ("VALID", "true", "labeled VALID must set invalid_data=false"),
    ],
)
def test_source_data_validity_label_and_flag_must_agree(
    samples_factory,
    research_bundle_factory,
    tmp_path,
    label,
    invalid_data,
    message,
):
    bundle = research_bundle_factory(samples_factory(seconds_per_label=2), tmp_path)
    annotations = pd.read_csv(
        bundle["annotations"], dtype=str, keep_default_na=False
    )
    target = annotations["head"].eq("DATA_VALIDITY")
    annotations.loc[target, "label"] = label
    annotations.loc[target, "invalid_data"] = invalid_data
    _write_annotations_and_rebind_consensus(bundle, annotations)

    with pytest.raises(DataValidationError, match=message):
        _load(bundle)


def test_no_consensus_is_always_invalid(
    samples_factory, research_bundle_factory, tmp_path
):
    bundle = research_bundle_factory(samples_factory(seconds_per_label=2), tmp_path)
    consensus_path = bundle["consensus"]
    consensus = json.loads(consensus_path.read_text())
    segment = consensus["segments"][0]
    segment["resolution"] = "NO_CONSENSUS"
    segment["adjudication_id"] = None
    segment["source_annotation_ids"] = [
        annotation_id
        for annotation_id in segment["source_annotation_ids"]
        if not annotation_id.endswith("-ADJ")
    ]
    consensus["consensus_method"] = "MIXED"
    consensus_path.write_text(json.dumps(consensus), encoding="utf-8")
    manifest_path = bundle["manifests"][0]
    manifest = json.loads(manifest_path.read_text())
    manifest["annotation"]["consensus_method"] = "MIXED"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(DataValidationError, match="NO_CONSENSUS segment.*invalid_data=true"):
        _load(bundle)


def test_consensus_cannot_cite_a_superseded_annotation_revision(
    samples_factory, research_bundle_factory, tmp_path
):
    bundle = research_bundle_factory(samples_factory(seconds_per_label=2), tmp_path)
    annotations_path = bundle["annotations"]
    annotations = pd.read_csv(annotations_path, dtype=str, keep_default_na=False)
    original = annotations.iloc[0].copy()
    replacement = original.copy()
    replacement["annotation_id"] = f"{original['annotation_id']}-REV2"
    replacement["revision"] = "2"
    replacement["supersedes_annotation_id"] = original["annotation_id"]
    replacement["created_at_epoch_ms"] = str(int(original["created_at_epoch_ms"]) + 1)
    annotations = pd.concat([annotations, replacement.to_frame().T], ignore_index=True)
    annotations.to_csv(annotations_path, index=False)

    consensus_path = bundle["consensus"]
    consensus = json.loads(consensus_path.read_text())
    consensus["input_annotations_sha256"] = hashlib.sha256(
        annotations_path.read_bytes()
    ).hexdigest()
    consensus_path.write_text(json.dumps(consensus), encoding="utf-8")

    with pytest.raises(DataValidationError, match="unknown or not active"):
        _load(bundle)
