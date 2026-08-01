"""Baseline analysis tools for Goat Sensor Lab exports."""

from .schema import SAMPLE_COLUMNS, DataValidationError, read_samples, validate_samples
from .windowing import WindowConfig, make_feature_windows

__all__ = [
    "SAMPLE_COLUMNS",
    "DataValidationError",
    "WindowConfig",
    "make_feature_windows",
    "read_samples",
    "validate_samples",
]

__version__ = "0.1.0"
