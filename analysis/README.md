# Goat Sensor Analysis

Python 3.11+ baseline tooling for Goat Sensor Lab `samples.csv` exports. The package is built for
indoor, stall-fed goat and sheep experiments. It validates the capture contract, creates fixed
non-overlapping IMU windows, extracts time-domain features, and evaluates separate Random Forest
baselines for ingestive behavior, posture/activity, and welfare-risk screening.

This is a research baseline, not a production behavior model. In particular, welfare output is
**risk screening only, never a diagnosis**. A veterinarian or trained operator must confirm any
animal-health concern.

## Install

```bash
uv sync --directory analysis --extra dev --frozen
```

## Validate exports

```bash
goat-sensor-analysis validate /path/to/session/samples.csv
```

Validation fails before analysis when an export has missing, extra, duplicated, or reordered
columns; unsupported schema versions or enums; malformed numeric/boolean values; incomplete
gyroscope vectors; inconsistent session identity; duplicated sequences; or non-monotonic sensor
time. Multiple files can be supplied and are checked independently before concatenation.

## Train baselines

```bash
goat-sensor-analysis train \
  captures/session-001/samples.csv \
  --experiment-manifest captures/session-001/experiment-manifest-v1.json \
  --annotations annotations/annotations-v1.csv \
  --consensus annotations/annotation-consensus-v1.json \
  --output artifacts/baseline-v1 \
  --window-seconds 10 \
  --min-samples 200 \
  --evaluation both
```

Repeat `--experiment-manifest`, `--annotations`, and `--consensus` when a training dataset uses
multiple immutable artifacts. Research mode validates the repository schemas, verifies every
manifest `session.raw_export_sha256` against the exact `samples.csv` bytes, verifies each consensus
`input_annotations_sha256` against the exact annotations snapshot, requires a frozen consensus,
and checks experiment/session/animal/ethogram alignment. It then interval-joins every consensus
head to `monotonic_time_ns` and replaces the live labels embedded in `samples.csv`; those live
labels are never research ground truth.

Media-backed annotation rows must resolve their `media_id`, media clock, and `clock_mapping_id` to
the session manifest camera entry, which must carry immutable media and clock-mapping SHA-256
digests. Research training resolves append-only annotation revisions, uses active non-adjudicator
rater intervals to recompute duration-weighted double-annotation coverage, and requires both rater
blinding flags plus the registered protocol minimum. Manifest achieved coverage must equal the
computed value. An `ADJUDICATED` consensus segment must cite at least two independent active raters
and exactly one matching active `ADJUDICATOR_RECORD`.
`UNANIMOUS` and `MAJORITY` segments are independently rematerialized from accepted active rater
votes; majority requires a strict majority among at least three distinct raters. Their
`invalid_data` flag must equal the conservative OR of the contributing independent annotations,
while adjudicated output must exactly match the adjudicator record and can never clear an invalid
accepted source. `DATA_VALIDITY` labels and flags are checked together (`INVALID` is invalid;
`VALID` requires every accepted source to be valid), and `NO_CONSENSUS` always remains invalid.

For recorder diagnostics only:

```bash
goat-sensor-analysis train capture/samples.csv \
  --output diagnostics/session-001 \
  --window-seconds 10 \
  --engineering-live-labels
```

This explicit mode writes only `engineering_windows.csv` and `engineering_summary.json`. It cannot
write `.joblib`, `metrics.json`, `windows.csv`, or a research reproducibility manifest.

Outputs:

- `windows.csv`: one row per valid fixed-duration window and its extracted features.
- `metrics.json`: animal-held-out and session-held-out metrics with fold-level leakage audits.
- `reproducibility_manifest.json`: schema/feature/window configuration, input and derived-dataset
  hashes, modeling domain, evaluation settings, analysis-code hash, and package versions.
- `ingestive_random_forest.joblib`: feeding/rumination/neither baseline.
- `posture_random_forest.joblib`: lying/standing/active-movement baseline.
- `welfare_risk_random_forest.joblib`: research risk-screening baseline with disclaimer metadata.

Use `--overwrite` to replace a non-empty output directory. A model is marked
`insufficient_classes`, `insufficient_groups`, or `insufficient_class_coverage` instead of
manufacturing a score from inadequate data. A `.joblib` artifact is written only when every
animal-held-out training fold contains every evaluated class.

Modeling fails closed when species, source, placement, experiment, farm/site/shed/pen, calibration
state and coefficients, research/BLE protocol, hardware and firmware/app revision, requested sample
rate and sensor ranges, mount orientation, enclosure, ethogram, or consensus provenance is missing
or mixed.
Phone and `PHONE_HANDHELD_TEST` windows are excluded from research artifacts. Generated
models are labeled as internal grouped-cross-validation baselines; `deployment_eligible` remains
false until external animal/site validation and an operational release gate exist. The current
welfare head also rejects `CLINICALLY_CONFIRMED_ABNORMAL`: clinical outcomes require a separate
provenance-bearing contract, while suspected abnormal inactivity remains a review signal only.

## Window and leakage rules

Windows use `monotonic_time_ns`, not wall-clock time. They are anchored independently inside each
animal/session and never cross:

- ingestive, posture, or welfare label changes;
- valid/invalid-data transitions;
- any sequence discontinuity, including forward gaps from dropped packets;
- sensor gaps larger than `--gap-seconds`.

Only complete, non-overlapping windows with at least `--min-samples` are retained. Unknown labels
are excluded only from the corresponding model head, so a posture label can still be used when the
ingestive label is unknown.

Evaluation never performs a random row/window split. `animal_held_out` keeps every window from a
test animal outside training. `session_held_out` does the same for sessions. Every fold records its
train groups, test groups, and empty overlap in `metrics.json`.

## Features and metrics

Features include mean, standard deviation, extrema, quartiles, IQR, RMS, energy, mean absolute
value, range, and mean absolute deviation for all six IMU axes; acceleration/gyroscope vector
magnitudes; signal-magnitude area; inter-axis correlations; acceleration jerk; angular
acceleration. Sample count and observed sample rate are retained as window-quality metadata, not
fed to the classifier, to avoid teaching the model device- or dropout-specific shortcuts.

Reported evaluation includes macro-F1, balanced accuracy, per-class precision/recall/F1/support,
an animal-cluster bootstrap confidence interval, grouped out-of-fold log loss, multiclass Brier
score, expected calibration error, and a labeled confusion matrix. These scores only describe the supplied experiment population and
must not be presented as cross-farm or clinical performance without external animal- and
site-held-out validation.

## Tests

```bash
uv run --directory analysis pytest
uv run --directory analysis ruff check .
```

Synthetic tests assert strict schema failures, homogeneous label windows, dropped invalid/tail
windows, session and animal boundaries, required feature families, and zero train/test group
overlap for both evaluation strategies.
