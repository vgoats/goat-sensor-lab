"""Command-line entry point for validation and baseline training."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from .artifacts import atomic_write_csv, atomic_write_text
from .modeling import train_baselines, validate_modeling_domain, validate_modeling_targets
from .provenance import load_research_dataset
from .schema import DataValidationError, read_samples, validation_summary
from .windowing import WindowConfig, make_feature_windows


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="goat-sensor-analysis")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="strictly validate samples.csv exports")
    validate.add_argument("samples", nargs="+", type=Path)

    train = subparsers.add_parser("train", help="build windows and grouped Random Forest baselines")
    train.add_argument("samples", nargs="+", type=Path)
    train.add_argument("--output", type=Path, required=True)
    train.add_argument("--window-seconds", type=float, default=10.0)
    train.add_argument("--min-samples", type=int, default=20)
    train.add_argument("--gap-seconds", type=float, default=1.0)
    train.add_argument("--splits", type=int, default=5)
    train.add_argument("--trees", type=int, default=300)
    train.add_argument("--seed", type=int, default=42)
    train.add_argument("--bootstrap-replicates", type=int, default=500)
    train.add_argument(
        "--evaluation",
        choices=["both", "animal", "session"],
        default="both",
    )
    train.add_argument("--overwrite", action="store_true")
    train.add_argument(
        "--experiment-manifest",
        action="append",
        type=Path,
        default=[],
        help="validated experiment manifest; repeat once per session",
    )
    train.add_argument(
        "--annotations",
        action="append",
        type=Path,
        default=[],
        help="immutable annotations-v1.csv snapshot; repeat for multiple snapshots",
    )
    train.add_argument(
        "--consensus",
        action="append",
        type=Path,
        default=[],
        help="frozen annotation-consensus-v1 JSON; repeat for multiple materializations",
    )
    train.add_argument(
        "--engineering-live-labels",
        action="store_true",
        help="create diagnostic windows from live labels without any model artifacts",
    )
    return parser


def _prepare_output(path: Path, overwrite: bool) -> None:
    if path.exists() and any(path.iterdir()):
        if not overwrite:
            raise ValueError(f"output directory is not empty: {path}; use --overwrite")
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate":
            samples = read_samples(args.samples)
            print(json.dumps(validation_summary(samples), indent=2, sort_keys=True))
            return 0

        config = WindowConfig(
            duration_seconds=args.window_seconds,
            min_samples=args.min_samples,
            gap_seconds=args.gap_seconds,
        )
        research_inputs_supplied = bool(
            args.experiment_manifest or args.annotations or args.consensus
        )
        if args.engineering_live_labels and research_inputs_supplied:
            raise ValueError(
                "--engineering-live-labels cannot be combined with research provenance inputs"
            )
        if args.engineering_live_labels:
            samples = read_samples(args.samples)
            windows = make_feature_windows(samples, config)
            if windows.empty:
                raise ValueError(
                    "no complete valid windows; record longer labels or reduce window size"
                )
            _prepare_output(args.output, args.overwrite)
            atomic_write_csv(args.output / "engineering_windows.csv", windows)
            engineering_summary = {
                "mode": "engineering_live_labels",
                "windows": int(len(windows)),
                "research_model_artifacts_emitted": False,
                "warning": (
                    "Live samples labels are diagnostic only and are not frozen research "
                    "ground truth. No model was trained."
                ),
            }
            atomic_write_text(
                args.output / "engineering_summary.json",
                json.dumps(engineering_summary, indent=2, sort_keys=True) + "\n",
            )
            print(json.dumps({"output": str(args.output), **engineering_summary}, indent=2))
            return 0

        if not args.experiment_manifest or not args.annotations or not args.consensus:
            raise ValueError(
                "research training requires --experiment-manifest, --annotations, and "
                "--consensus; use --engineering-live-labels only for diagnostic windows"
            )
        research_dataset = load_research_dataset(
            args.samples,
            args.experiment_manifest,
            args.annotations,
            args.consensus,
        )
        windows = make_feature_windows(research_dataset.samples, config)
        if windows.empty:
            raise ValueError(
                "no complete valid windows; record longer labels or reduce window size"
            )
        validate_modeling_domain(windows)
        validate_modeling_targets(windows)
        _prepare_output(args.output, args.overwrite)
        atomic_write_csv(args.output / "windows.csv", windows)
        evaluation_map = {
            "both": {"animal_held_out", "session_held_out"},
            "animal": {"animal_held_out"},
            "session": {"session_held_out"},
        }
        result = train_baselines(
            windows,
            args.output,
            window_config=config,
            evaluations=evaluation_map[args.evaluation],
            requested_splits=args.splits,
            seed=args.seed,
            trees=args.trees,
            bootstrap_replicates=args.bootstrap_replicates,
            dataset_hashes=list(research_dataset.provenance.verified_inputs),
            research_provenance=research_dataset.provenance,
        )
        print(
            json.dumps(
                {
                    "output": str(args.output),
                    "windows": int(len(windows)),
                    "heads": {
                        head: details["status"] for head, details in result["heads"].items()
                    },
                    "welfare_disclaimer": result["welfare_disclaimer"],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    except (DataValidationError, ValueError) as exc:
        print(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
