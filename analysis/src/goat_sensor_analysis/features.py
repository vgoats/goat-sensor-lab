"""Time-domain feature extraction for accelerometer and gyroscope windows."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

AXES = [
    "acc_x_m_s2",
    "acc_y_m_s2",
    "acc_z_m_s2",
    "gyro_x_rad_s",
    "gyro_y_rad_s",
    "gyro_z_rad_s",
]


def _stats(prefix: str, values: np.ndarray) -> dict[str, float]:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return {
            f"{prefix}_{name}": math.nan
            for name in [
                "mean",
                "std",
                "min",
                "max",
                "median",
                "q25",
                "q75",
                "iqr",
                "rms",
                "mean_abs",
                "range",
                "energy",
                "mad",
            ]
        }
    q25, q75 = np.quantile(finite, [0.25, 0.75])
    mean = float(np.mean(finite))
    return {
        f"{prefix}_mean": mean,
        f"{prefix}_std": float(np.std(finite)),
        f"{prefix}_min": float(np.min(finite)),
        f"{prefix}_max": float(np.max(finite)),
        f"{prefix}_median": float(np.median(finite)),
        f"{prefix}_q25": float(q25),
        f"{prefix}_q75": float(q75),
        f"{prefix}_iqr": float(q75 - q25),
        f"{prefix}_rms": float(np.sqrt(np.mean(np.square(finite)))),
        f"{prefix}_mean_abs": float(np.mean(np.abs(finite))),
        f"{prefix}_range": float(np.max(finite) - np.min(finite)),
        f"{prefix}_energy": float(np.mean(np.square(finite))),
        f"{prefix}_mad": float(np.mean(np.abs(finite - mean))),
    }


def _correlation(left: np.ndarray, right: np.ndarray) -> float:
    valid = np.isfinite(left) & np.isfinite(right)
    if valid.sum() < 2 or np.std(left[valid]) == 0 or np.std(right[valid]) == 0:
        return math.nan
    return float(np.corrcoef(left[valid], right[valid])[0, 1])


def extract_time_domain_features(window: pd.DataFrame) -> dict[str, float]:
    """Extract orientation-sensitive axes plus orientation-robust vector features."""

    output: dict[str, float] = {}
    arrays = {column: window[column].to_numpy(dtype=float) for column in AXES}
    for column, values in arrays.items():
        output.update(_stats(column, values))

    acceleration = np.column_stack([arrays[column] for column in AXES[:3]])
    gyroscope = np.column_stack([arrays[column] for column in AXES[3:]])
    acceleration_magnitude = np.linalg.norm(acceleration, axis=1)
    gyroscope_magnitude = np.linalg.norm(gyroscope, axis=1)
    gyroscope_magnitude[~np.isfinite(gyroscope).all(axis=1)] = np.nan
    output.update(_stats("acc_magnitude_m_s2", acceleration_magnitude))
    output.update(_stats("gyro_magnitude_rad_s", gyroscope_magnitude))
    output["acc_signal_magnitude_area"] = float(np.mean(np.abs(acceleration).sum(axis=1)))
    valid_gyro = np.isfinite(gyroscope).all(axis=1)
    output["gyro_signal_magnitude_area"] = (
        float(np.mean(np.abs(gyroscope[valid_gyro]).sum(axis=1)))
        if valid_gyro.any()
        else math.nan
    )

    for prefix, matrix in [("acc", acceleration), ("gyro", gyroscope)]:
        output[f"{prefix}_corr_xy"] = _correlation(matrix[:, 0], matrix[:, 1])
        output[f"{prefix}_corr_xz"] = _correlation(matrix[:, 0], matrix[:, 2])
        output[f"{prefix}_corr_yz"] = _correlation(matrix[:, 1], matrix[:, 2])

    time_seconds = window["monotonic_time_ns"].to_numpy(dtype=np.float64) / 1_000_000_000
    delta_time = np.diff(time_seconds)
    positive_time = delta_time > 0
    if len(window) > 1 and positive_time.all():
        jerk = np.diff(acceleration, axis=0) / delta_time[:, None]
        output.update(_stats("jerk_magnitude_m_s3", np.linalg.norm(jerk, axis=1)))
        if np.isfinite(gyroscope).all():
            angular_acceleration = np.diff(gyroscope, axis=0) / delta_time[:, None]
            output.update(
                _stats(
                    "angular_accel_magnitude_rad_s2",
                    np.linalg.norm(angular_acceleration, axis=1),
                )
            )
        else:
            output.update(_stats("angular_accel_magnitude_rad_s2", np.array([])))
    else:
        output.update(_stats("jerk_magnitude_m_s3", np.array([])))
        output.update(_stats("angular_accel_magnitude_rad_s2", np.array([])))
    return output
