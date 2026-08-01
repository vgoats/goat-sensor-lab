"""Grouped Random Forest baselines with explicit leakage audits."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    log_loss,
)
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline

from .artifacts import atomic_dump_joblib, atomic_write_text
from .provenance import RESEARCH_DOMAIN_COLUMNS, ValidatedResearchProvenance
from .windowing import WINDOW_METADATA_COLUMNS, WindowConfig

HEADS = {
    "ingestive": "ingestive_behavior",
    "posture": "posture_activity",
    "welfare_risk": "welfare_state",
}
EVALUATIONS = {
    "animal_held_out": "animal_id",
    "session_held_out": "session_id",
}
WELFARE_DISCLAIMER = (
    "Welfare output is research risk screening only. It is not a diagnosis and requires "
    "human and veterinary confirmation."
)
REQUIRED_MODELING_DOMAINS = ("species", "source", "placement", *RESEARCH_DOMAIN_COLUMNS)
ENGINEERING_SOURCES = {"ANDROID_PHONE"}
ENGINEERING_PLACEMENTS = {"PHONE_HANDHELD_TEST"}
UNSUPPORTED_WELFARE_TRAINING_LABELS = {"CLINICALLY_CONFIRMED_ABNORMAL"}


class InsufficientClassCoverageError(ValueError):
    """Raised when a grouped training fold cannot learn every evaluated class."""


def feature_columns(windows: pd.DataFrame) -> list[str]:
    excluded = set(WINDOW_METADATA_COLUMNS)
    return [column for column in windows.columns if column not in excluded]


def validate_modeling_domain(
    windows: pd.DataFrame,
) -> dict[str, str]:
    """Require one explicit sensor domain before fitting any research artifact."""

    missing = [column for column in REQUIRED_MODELING_DOMAINS if column not in windows.columns]
    if missing:
        raise ValueError(f"modeling data is missing domain column(s): {missing}")

    domains: dict[str, str] = {}
    for column in REQUIRED_MODELING_DOMAINS:
        values = windows[column].astype("string").str.strip()
        if values.isna().any() or values.eq("").any():
            raise ValueError(f"modeling domain {column} contains missing values")
        unique = sorted(values.unique().tolist())
        if len(unique) != 1:
            raise ValueError(f"mixed modeling domain for {column}: {unique}")
        domains[column] = unique[0]

    if (
        domains["source"] in ENGINEERING_SOURCES
        or domains["placement"] in ENGINEERING_PLACEMENTS
    ):
        raise ValueError(
            "phone/PHONE_HANDHELD_TEST windows are engineering data and are excluded "
            "from research model artifacts"
        )
    if domains["label_provenance_mode"] != "FROZEN_CONSENSUS":
        raise ValueError("research model labels must come from frozen consensus")
    return domains


def validate_modeling_targets(windows: pd.DataFrame) -> None:
    """Reject clinical outcomes until a provenance-bearing outcomes contract exists."""

    clinical_labels = (
        set(windows["welfare_state"].astype(str)) & UNSUPPORTED_WELFARE_TRAINING_LABELS
    )
    if clinical_labels:
        raise ValueError(
            "welfare model training does not accept CLINICALLY_CONFIRMED_ABNORMAL without "
            "a separate clinical-outcomes provenance contract"
        )


def make_group_splits(
    rows: pd.DataFrame,
    group_column: str,
    requested_splits: int,
) -> list[tuple[np.ndarray, np.ndarray]]:
    groups = rows[group_column].astype(str).to_numpy()
    unique_groups = np.unique(groups)
    if unique_groups.size < 2:
        raise ValueError(f"{group_column}: need at least two distinct groups")
    split_count = min(requested_splits, int(unique_groups.size))
    if split_count < 2:
        raise ValueError("evaluation needs at least two folds")
    splitter = GroupKFold(n_splits=split_count)
    placeholder = np.zeros(len(rows))
    splits = list(splitter.split(placeholder, groups=groups))
    for train_index, test_index in splits:
        overlap = set(groups[train_index]) & set(groups[test_index])
        if overlap:
            raise AssertionError(f"group leakage detected for {group_column}: {overlap}")
    return splits


def _pipeline(seed: int, trees: int) -> Pipeline:
    return Pipeline(
        [
            (
                "imputer",
                SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
            ),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=trees,
                    class_weight="balanced_subsample",
                    random_state=seed,
                    n_jobs=-1,
                    min_samples_leaf=2,
                ),
            ),
        ]
    )


def _calibration_metrics(
    expected: np.ndarray,
    probabilities: np.ndarray,
    labels: list[str],
    *,
    bins: int = 10,
) -> dict[str, Any]:
    if len(labels) < 2 or len(expected) == 0 or not np.isfinite(probabilities).all():
        return {
            "status": "not_available",
            "reason": "calibration requires finite grouped out-of-fold probabilities",
        }

    label_index = {label: index for index, label in enumerate(labels)}
    encoded = np.array([label_index[str(label)] for label in expected], dtype=int)
    one_hot = np.eye(len(labels), dtype=float)[encoded]
    confidence = probabilities.max(axis=1)
    predicted_index = probabilities.argmax(axis=1)
    correct = predicted_index == encoded
    edges = np.linspace(0.0, 1.0, bins + 1)
    expected_calibration_error = 0.0
    populated_bins = 0
    for index in range(bins):
        if index == bins - 1:
            in_bin = (confidence >= edges[index]) & (confidence <= edges[index + 1])
        else:
            in_bin = (confidence >= edges[index]) & (confidence < edges[index + 1])
        if not in_bin.any():
            continue
        populated_bins += 1
        expected_calibration_error += float(in_bin.mean()) * abs(
            float(correct[in_bin].mean()) - float(confidence[in_bin].mean())
        )

    return {
        "status": "valid",
        "method": "grouped_out_of_fold_probabilities",
        "log_loss": float(log_loss(expected, probabilities, labels=labels)),
        "multiclass_brier_score": float(np.mean(np.sum((probabilities - one_hot) ** 2, axis=1))),
        "expected_calibration_error": expected_calibration_error,
        "bins": bins,
        "populated_bins": populated_bins,
    }


def _animal_cluster_bootstrap(
    rows: pd.DataFrame,
    expected: np.ndarray,
    predicted: np.ndarray,
    labels: list[str],
    *,
    seed: int,
    replicates: int,
) -> dict[str, Any]:
    animals = rows["animal_id"].astype(str).to_numpy()
    unique_animals = np.unique(animals)
    if unique_animals.size < 2:
        return {
            "status": "not_available",
            "reason": "animal-cluster bootstrap requires at least two animals",
        }

    indexes_by_animal = {
        animal: np.flatnonzero(animals == animal) for animal in unique_animals
    }
    random = np.random.default_rng(seed)
    macro_f1_values: list[float] = []
    balanced_accuracy_values: list[float] = []
    required_labels = set(labels)
    for _ in range(replicates):
        sampled_animals = random.choice(
            unique_animals,
            size=unique_animals.size,
            replace=True,
        )
        sampled_indexes = np.concatenate(
            [indexes_by_animal[animal] for animal in sampled_animals]
        )
        sampled_expected = expected[sampled_indexes]
        if set(sampled_expected.tolist()) != required_labels:
            continue
        sampled_predicted = predicted[sampled_indexes]
        macro_f1_values.append(
            float(
                f1_score(
                    sampled_expected,
                    sampled_predicted,
                    labels=labels,
                    average="macro",
                    zero_division=0,
                )
            )
        )
        balanced_accuracy_values.append(
            float(balanced_accuracy_score(sampled_expected, sampled_predicted))
        )

    minimum_valid = max(20, replicates // 10)
    if len(macro_f1_values) < minimum_valid:
        return {
            "status": "not_available",
            "reason": "too few class-complete animal bootstrap replicates",
            "replicates_requested": replicates,
            "replicates_valid": len(macro_f1_values),
        }

    def interval(values: list[float]) -> dict[str, float]:
        lower, upper = np.quantile(np.asarray(values), [0.025, 0.975])
        return {"lower": float(lower), "upper": float(upper)}

    return {
        "status": "valid",
        "method": "animal_cluster_bootstrap",
        "confidence_level": 0.95,
        "replicates_requested": replicates,
        "replicates_valid": len(macro_f1_values),
        "macro_f1": interval(macro_f1_values),
        "balanced_accuracy": interval(balanced_accuracy_values),
    }


def _evaluate(
    rows: pd.DataFrame,
    *,
    target: str,
    features: list[str],
    group_column: str,
    requested_splits: int,
    seed: int,
    trees: int,
    bootstrap_replicates: int,
) -> dict[str, Any]:
    labels = sorted(rows[target].unique().tolist())
    expected = np.empty(len(rows), dtype=object)
    predicted = np.empty(len(rows), dtype=object)
    probabilities = np.full((len(rows), len(labels)), np.nan, dtype=float)
    fold_audits: list[dict[str, Any]] = []
    splits = make_group_splits(rows, group_column, requested_splits)
    group_values = rows[group_column].astype(str).to_numpy()

    for fold_index, (train_index, test_index) in enumerate(splits):
        train_labels = set(rows.iloc[train_index][target].tolist())
        missing_from_training = [label for label in labels if label not in train_labels]
        if missing_from_training:
            raise InsufficientClassCoverageError(
                f"{group_column} fold {fold_index}: training data is missing evaluated "
                f"class(es) {missing_from_training}"
            )
        model = _pipeline(seed + fold_index, trees)
        model.fit(rows.iloc[train_index][features], rows.iloc[train_index][target])
        expected[test_index] = rows.iloc[test_index][target].to_numpy()
        predicted[test_index] = model.predict(rows.iloc[test_index][features])
        fold_probabilities = model.predict_proba(rows.iloc[test_index][features])
        class_to_column = {str(label): index for index, label in enumerate(model.classes_)}
        for label_index, label in enumerate(labels):
            probabilities[test_index, label_index] = fold_probabilities[
                :, class_to_column[label]
            ]
        train_groups = sorted(set(group_values[train_index]))
        test_groups = sorted(set(group_values[test_index]))
        fold_audits.append(
            {
                "fold": fold_index,
                "train_groups": train_groups,
                "test_groups": test_groups,
                "group_overlap": sorted(set(train_groups) & set(test_groups)),
                "train_windows": int(len(train_index)),
                "test_windows": int(len(test_index)),
            }
        )

    evaluation = {
        "status": "valid",
        "group_column": group_column,
        "folds": len(splits),
        "windows": int(len(rows)),
        "classes": labels,
        "macro_f1": float(f1_score(expected, predicted, labels=labels, average="macro")),
        "balanced_accuracy": float(balanced_accuracy_score(expected, predicted)),
        "per_class": classification_report(
            expected,
            predicted,
            labels=labels,
            output_dict=True,
            zero_division=0,
        ),
        "confusion_matrix": {
            "labels": labels,
            "matrix": confusion_matrix(expected, predicted, labels=labels).tolist(),
        },
        "leakage_audit": fold_audits,
    }
    evaluation["confidence_intervals"] = _animal_cluster_bootstrap(
        rows,
        expected,
        predicted,
        labels,
        seed=seed + 10_000,
        replicates=bootstrap_replicates,
    )
    evaluation["calibration"] = _calibration_metrics(expected, probabilities, labels)
    return evaluation


def _artifact_path(output: Path, head: str) -> Path:
    return output / f"{head}_random_forest.joblib"


def _remove_artifact(output: Path, head: str) -> None:
    _artifact_path(output, head).unlink(missing_ok=True)


def _sha256_json(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _windows_sha256(windows: pd.DataFrame) -> str:
    sort_columns = [
        column for column in ("animal_id", "session_id", "window_id") if column in windows.columns
    ]
    ordered = windows.sort_values(sort_columns, kind="stable") if sort_columns else windows
    payload = ordered.to_csv(index=False, lineterminator="\n", float_format="%.17g")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _analysis_code_sha256() -> str:
    digest = hashlib.sha256()
    package_dir = Path(__file__).parent
    for filename in ("artifacts.py", "features.py", "modeling.py", "schema.py", "windowing.py"):
        path = package_dir / filename
        digest.update(filename.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _reproducibility_manifest(
    windows: pd.DataFrame,
    *,
    features: list[str],
    domains: dict[str, str],
    window_config: WindowConfig,
    evaluations: set[str],
    requested_splits: int,
    seed: int,
    trees: int,
    bootstrap_replicates: int,
    dataset_hashes: list[dict[str, Any]] | None,
    research_provenance: ValidatedResearchProvenance,
) -> dict[str, Any]:
    feature_schema = {"columns": features, "sha256": _sha256_json(features)}
    return {
        "manifest_version": 1,
        "schema": {
            "samples_schema_version": 1,
            "window_metadata_columns": WINDOW_METADATA_COLUMNS,
            "feature_schema": feature_schema,
        },
        "window": {
            "duration_seconds": window_config.duration_seconds,
            "min_samples": window_config.min_samples,
            "gap_seconds": window_config.gap_seconds,
        },
        "dataset": {
            "windows_sha256": _windows_sha256(windows),
            "window_rows": int(len(windows)),
            "animals": int(windows["animal_id"].nunique()),
            "sessions": int(windows["session_id"].nunique()),
            "input_files": dataset_hashes or [],
        },
        "modeling_domains": domains,
        "label_provenance": research_provenance.as_dict(),
        "evaluation": {
            "strategies": sorted(evaluations),
            "requested_splits": requested_splits,
            "animal_bootstrap_replicates": bootstrap_replicates,
            "seed": seed,
        },
        "model": {"family": "RandomForestClassifier", "trees": trees},
        "software": {
            "python": platform.python_version(),
            "goat_sensor_analysis": _package_version("goat-sensor-analysis"),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "joblib": _package_version("joblib"),
            "analysis_code_sha256": _analysis_code_sha256(),
        },
    }


def train_baselines(
    windows: pd.DataFrame,
    output_dir: str | Path,
    *,
    window_config: WindowConfig,
    evaluations: set[str] | None = None,
    requested_splits: int = 5,
    seed: int = 42,
    trees: int = 300,
    bootstrap_replicates: int = 500,
    dataset_hashes: list[dict[str, Any]] | None = None,
    research_provenance: ValidatedResearchProvenance | None = None,
) -> dict[str, Any]:
    """Evaluate and fit one internal-CV baseline artifact per behavior head."""

    output = Path(output_dir)
    if not isinstance(research_provenance, ValidatedResearchProvenance) or not (
        research_provenance.manifests
    ):
        raise ValueError(
            "research model artifacts require validated experiment manifests and frozen consensus"
        )
    output.mkdir(parents=True, exist_ok=True)
    if bootstrap_replicates < 100:
        raise ValueError("bootstrap_replicates must be at least 100")
    domains = validate_modeling_domain(windows)
    validate_modeling_targets(windows)
    features = feature_columns(windows)
    if not features:
        raise ValueError("no feature columns found")
    selected_evaluations = evaluations or set(EVALUATIONS)
    unknown_evaluations = selected_evaluations - set(EVALUATIONS)
    if unknown_evaluations:
        raise ValueError(f"unknown evaluation(s): {sorted(unknown_evaluations)}")

    manifest = _reproducibility_manifest(
        windows,
        features=features,
        domains=domains,
        window_config=window_config,
        evaluations=selected_evaluations,
        requested_splits=requested_splits,
        seed=seed,
        trees=trees,
        bootstrap_replicates=bootstrap_replicates,
        dataset_hashes=dataset_hashes,
        research_provenance=research_provenance,
    )
    manifest_content = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    manifest_sha256 = hashlib.sha256(manifest_content.encode("utf-8")).hexdigest()
    atomic_write_text(output / "reproducibility_manifest.json", manifest_content)

    result: dict[str, Any] = {
        "model_family": "RandomForestClassifier",
        "seed": seed,
        "trees": trees,
        "window": {
            "duration_seconds": window_config.duration_seconds,
            "min_samples": window_config.min_samples,
            "gap_seconds": window_config.gap_seconds,
        },
        "feature_count": len(features),
        "modeling_domains": domains,
        "deployment_eligible": False,
        "reproducibility_manifest": {
            "file": "reproducibility_manifest.json",
            "sha256": manifest_sha256,
        },
        "heads": {},
        "welfare_disclaimer": WELFARE_DISCLAIMER,
    }

    for head, target in HEADS.items():
        rows = windows[windows[target] != "UNKNOWN"].reset_index(drop=True)
        head_result: dict[str, Any] = {
            "target": target,
            "windows": int(len(rows)),
            "classes": sorted(rows[target].unique().tolist()),
            "evaluations": {},
            "internal_cv_valid": False,
            "evaluation_complete": False,
            "deployment_eligible": False,
        }
        if head == "welfare_risk":
            head_result["disclaimer"] = WELFARE_DISCLAIMER
        if rows[target].nunique() < 2:
            _remove_artifact(output, head)
            head_result["status"] = "insufficient_classes"
            result["heads"][head] = head_result
            continue

        for evaluation_name in sorted(selected_evaluations):
            group_column = EVALUATIONS[evaluation_name]
            try:
                head_result["evaluations"][evaluation_name] = _evaluate(
                    rows,
                    target=target,
                    features=features,
                    group_column=group_column,
                    requested_splits=requested_splits,
                    seed=seed,
                    trees=trees,
                    bootstrap_replicates=bootstrap_replicates,
                )
            except InsufficientClassCoverageError as exc:
                head_result["evaluations"][evaluation_name] = {
                    "status": "insufficient_class_coverage",
                    "reason": str(exc),
                }
            except ValueError as exc:
                head_result["evaluations"][evaluation_name] = {
                    "status": "insufficient_groups",
                    "reason": str(exc),
                }

        head_result["evaluation_complete"] = bool(selected_evaluations) and all(
            evaluation.get("status") == "valid"
            for evaluation in head_result["evaluations"].values()
        )
        animal_evaluation = head_result["evaluations"].get("animal_held_out")
        head_result["internal_cv_valid"] = bool(
            isinstance(animal_evaluation, dict) and animal_evaluation.get("status") == "valid"
        )
        if not head_result["internal_cv_valid"]:
            _remove_artifact(output, head)
            head_result["status"] = "internal_cv_incomplete"
            result["heads"][head] = head_result
            continue

        final_model = _pipeline(seed, trees)
        final_model.fit(rows[features], rows[target])
        artifact = {
            "head": head,
            "target": target,
            "features": features,
            "classes": sorted(rows[target].unique().tolist()),
            "pipeline": final_model,
            "welfare_disclaimer": WELFARE_DISCLAIMER if head == "welfare_risk" else None,
            "claim_scope": "internal grouped cross-validation baseline only",
            "internal_cv_valid": True,
            "deployment_eligible": False,
            "reproducibility_manifest_sha256": manifest_sha256,
        }
        atomic_dump_joblib(_artifact_path(output, head), artifact)
        head_result["status"] = "trained_internal_cv"
        result["heads"][head] = head_result

    atomic_write_text(
        output / "metrics.json",
        json.dumps(result, indent=2, sort_keys=True) + "\n",
    )
    return result
