from __future__ import annotations

import json

from goat_sensor_analysis.cli import main


def test_validate_and_train_cli(samples_factory, research_bundle_factory, tmp_path, capsys):
    samples = samples_factory(
        animals=("GOAT-001", "GOAT-002", "GOAT-003"),
        sessions_per_animal=2,
        seconds_per_label=2,
        rate_hz=10,
    )
    bundle = research_bundle_factory(samples, tmp_path)
    samples_path = bundle["samples"]

    assert main(["validate", str(samples_path)]) == 0
    validation = json.loads(capsys.readouterr().out)
    assert validation["animals"] == 3
    assert validation["sessions"] == 6

    output = tmp_path / "artifacts"
    manifest_arguments = [
        argument
        for path in bundle["manifests"]
        for argument in ("--experiment-manifest", str(path))
    ]
    assert (
        main(
            [
                "train",
                str(samples_path),
                "--output",
                str(output),
                "--window-seconds",
                "2",
                "--min-samples",
                "15",
                "--splits",
                "3",
                "--trees",
                "10",
                "--bootstrap-replicates",
                "100",
                "--annotations",
                str(bundle["annotations"]),
                "--consensus",
                str(bundle["consensus"]),
                *manifest_arguments,
            ]
        )
        == 0
    )
    training = json.loads(capsys.readouterr().out)
    assert training["windows"] == 18
    assert set(training["heads"].values()) == {"trained_internal_cv"}
    assert (output / "windows.csv").exists()
    assert (output / "metrics.json").exists()
    manifest = json.loads((output / "reproducibility_manifest.json").read_text())
    assert {item["kind"] for item in manifest["dataset"]["input_files"]} == {
        "raw_export",
        "experiment_manifest",
        "raw_annotations",
        "frozen_consensus",
    }
    assert manifest["label_provenance"]["mode"] == "frozen_consensus"


def test_train_requires_research_provenance_by_default(samples_factory, tmp_path, capsys):
    samples_path = tmp_path / "samples.csv"
    samples_factory(seconds_per_label=2).to_csv(samples_path, index=False)

    result = main(
        [
            "train",
            str(samples_path),
            "--output",
            str(tmp_path / "output"),
            "--window-seconds",
            "2",
            "--min-samples",
            "15",
        ]
    )

    assert result == 2
    assert "requires --experiment-manifest" in capsys.readouterr().out
    assert not (tmp_path / "output").exists()


def test_engineering_live_labels_emit_no_research_artifacts(samples_factory, tmp_path, capsys):
    samples_path = tmp_path / "samples.csv"
    samples_factory(seconds_per_label=2).to_csv(samples_path, index=False)
    output = tmp_path / "engineering"

    assert (
        main(
            [
                "train",
                str(samples_path),
                "--output",
                str(output),
                "--window-seconds",
                "2",
                "--min-samples",
                "15",
                "--engineering-live-labels",
            ]
        )
        == 0
    )
    summary = json.loads(capsys.readouterr().out)
    assert summary["research_model_artifacts_emitted"] is False
    assert (output / "engineering_windows.csv").exists()
    assert (output / "engineering_summary.json").exists()
    assert not list(output.glob("*.joblib"))
    assert not (output / "metrics.json").exists()
    assert not (output / "reproducibility_manifest.json").exists()
    assert not (output / "windows.csv").exists()
