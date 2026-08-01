"""Atomic writers for reproducible analysis artifacts."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import joblib
import pandas as pd


def _temporary_path(destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
        delete=False,
    )
    handle.close()
    return Path(handle.name)


def atomic_write_text(destination: Path, content: str) -> None:
    """Replace a text artifact only after its complete contents reach disk."""

    temporary = _temporary_path(destination)
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_write_csv(destination: Path, frame: pd.DataFrame) -> None:
    """Replace a CSV artifact atomically."""

    temporary = _temporary_path(destination)
    try:
        frame.to_csv(temporary, index=False, lineterminator="\n")
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_dump_joblib(destination: Path, value: Any) -> None:
    """Replace a joblib artifact atomically, preserving an older good file on failure."""

    temporary = _temporary_path(destination)
    try:
        joblib.dump(value, temporary)
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
