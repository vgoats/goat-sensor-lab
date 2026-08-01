"""Leakage-safe, fixed-duration IMU window construction."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .features import extract_time_domain_features
from .provenance import RESEARCH_DOMAIN_COLUMNS

LABEL_COLUMNS = ["ingestive_behavior", "posture_activity", "welfare_state"]
WINDOW_METADATA_COLUMNS = [
    "window_id",
    "session_id",
    "animal_id",
    "species",
    "placement",
    "source",
    "device_id",
    *RESEARCH_DOMAIN_COLUMNS,
    "window_start_monotonic_ns",
    "window_end_monotonic_ns",
    "sample_count",
    "observed_sample_rate_hz",
    *LABEL_COLUMNS,
]


@dataclass(frozen=True)
class WindowConfig:
    duration_seconds: float = 10.0
    min_samples: int = 20
    gap_seconds: float = 1.0

    def __post_init__(self) -> None:
        if self.duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        if self.min_samples < 2:
            raise ValueError("min_samples must be at least 2")
        if self.gap_seconds <= 0:
            raise ValueError("gap_seconds must be positive")


def _segment_ids(session: pd.DataFrame, config: WindowConfig) -> pd.Series:
    labels_changed = session[LABEL_COLUMNS + ["invalid_data"]].ne(
        session[LABEL_COLUMNS + ["invalid_data"]].shift()
    ).any(axis=1)
    time_gap = session["monotonic_time_ns"].diff().fillna(0) > config.gap_seconds * 1e9
    sequence_break = session["sequence"].diff().fillna(1).ne(1)
    boundary = labels_changed | time_gap | sequence_break
    boundary.iloc[0] = True
    return boundary.cumsum()


def _full_window_count(run: pd.DataFrame, duration_ns: int) -> int:
    if len(run) < 2:
        return 0
    timestamps = run["monotonic_time_ns"].to_numpy(dtype=np.int64)
    median_interval = int(np.median(np.diff(timestamps)))
    represented_end = int(timestamps[-1]) + max(median_interval, 1)
    return max(0, (represented_end - int(timestamps[0])) // duration_ns)


def make_feature_windows(samples: pd.DataFrame, config: WindowConfig) -> pd.DataFrame:
    """Create complete, non-overlapping windows without crossing semantic boundaries.

    Windows are constructed independently inside each session and animal. Every change to any
    label head, any invalid-data transition, a sequence discontinuity, or a large sensor gap starts
    a new run. Invalid runs and incomplete tail windows are discarded.
    """

    duration_ns = int(round(config.duration_seconds * 1_000_000_000))
    records: list[dict[str, object]] = []
    ordered = samples.sort_values(
        ["animal_id", "session_id", "monotonic_time_ns"], kind="stable"
    ).copy()

    for (_, _), session in ordered.groupby(["animal_id", "session_id"], sort=False):
        session = session.copy()
        session["_segment_id"] = _segment_ids(session, config).to_numpy()
        for segment_id, run in session.groupby("_segment_id", sort=False):
            if bool(run["invalid_data"].iloc[0]):
                continue
            run = run.drop(columns="_segment_id")
            start_ns = int(run["monotonic_time_ns"].iloc[0])
            for window_index in range(_full_window_count(run, duration_ns)):
                window_start = start_ns + window_index * duration_ns
                window_end = window_start + duration_ns
                window = run[
                    (run["monotonic_time_ns"] >= window_start)
                    & (run["monotonic_time_ns"] < window_end)
                ]
                if len(window) < config.min_samples:
                    continue
                if any(window[column].nunique() != 1 for column in LABEL_COLUMNS):
                    raise AssertionError("window crossed a label boundary")
                observed_span = (
                    int(window["monotonic_time_ns"].iloc[-1])
                    - int(window["monotonic_time_ns"].iloc[0])
                ) / 1_000_000_000
                record: dict[str, object] = {
                    "window_id": (
                        f"{window['session_id'].iloc[0]}:{segment_id}:{window_index}"
                    ),
                    "session_id": window["session_id"].iloc[0],
                    "animal_id": window["animal_id"].iloc[0],
                    "species": window["species"].iloc[0],
                    "placement": window["placement"].iloc[0],
                    "source": window["source"].iloc[0],
                    "device_id": window["device_id"].iloc[0],
                    "window_start_monotonic_ns": window_start,
                    "window_end_monotonic_ns": window_end,
                    "sample_count": int(len(window)),
                    "observed_sample_rate_hz": (
                        (len(window) - 1) / observed_span if observed_span > 0 else np.nan
                    ),
                    **{column: window[column].iloc[0] for column in LABEL_COLUMNS},
                    **{
                        column: window[column].iloc[0]
                        for column in RESEARCH_DOMAIN_COLUMNS
                        if column in window.columns
                    },
                }
                record.update(extract_time_domain_features(window))
                records.append(record)
    return pd.DataFrame.from_records(records)
