"""Environment configuration helpers."""

from __future__ import annotations

import os
from pathlib import Path


JOB_PARQUET_ENV = "ATS_JOB_PARQUET"
AUTHORIZED_RESUME_ZIP_ENV = "ATS_AUTHORIZED_RESUME_ZIP"
MODEL_DIR_ENV = "ATS_MODEL_DIR"


def env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    return Path(value).expanduser() if value else None


def default_model_dir() -> Path:
    return env_path(MODEL_DIR_ENV) or Path("models")

