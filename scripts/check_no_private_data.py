#!/usr/bin/env python3
"""Block common private-data mistakes before committing."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


BLOCKED_DIR_PREFIXES = (
    "data/raw/",
    "data/processed/",
    "models/",
    "artifacts/",
    "outputs/",
)
BLOCKED_EXTENSIONS = {
    ".csv",
    ".db",
    ".doc",
    ".docx",
    ".jsonl",
    ".parquet",
    ".pdf",
    ".sqlite",
    ".tsv",
    ".xlsx",
    ".zip",
}
HTML_EXTENSIONS = {".html", ".htm"}
ALLOWED_HTML_PREFIXES = ("ats_resume_coach/web/templates/",)
SUSPICIOUS_BASENAME_SIGNALS = (
    "cv-train",
    "job_training_dataset",
    "linkedin_export",
    "resume_dump",
)
MAX_FILE_BYTES = 5 * 1024 * 1024


def main() -> int:
    staged = _staged_files()
    errors = []
    for path in staged:
        errors.extend(check_path(path))

    if errors:
        print("Private-data guard blocked this commit:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        print("Move private files outside git or keep them under ignored local paths.", file=sys.stderr)
        return 1
    return 0


def check_path(path: str) -> list[str]:
    normalized = path.replace("\\", "/")
    file_path = Path(path)
    errors = []

    if normalized in {".env", ".env.local"} or (
        normalized.startswith(".env.") and normalized != ".env.example"
    ):
        errors.append(f"{path}: local env files must not be committed")

    if any(normalized.startswith(prefix) for prefix in BLOCKED_DIR_PREFIXES):
        errors.append(f"{path}: private data/model directory is blocked")

    suffix = file_path.suffix.lower()
    if suffix in BLOCKED_EXTENSIONS:
        errors.append(f"{path}: private or generated data extension is blocked")

    if suffix in HTML_EXTENSIONS and not normalized.startswith(ALLOWED_HTML_PREFIXES):
        errors.append(f"{path}: HTML job captures should stay local")

    basename = file_path.name.lower()
    if any(signal in basename for signal in SUSPICIOUS_BASENAME_SIGNALS):
        errors.append(f"{path}: filename looks like a private dataset")

    if file_path.exists() and file_path.is_file() and file_path.stat().st_size > MAX_FILE_BYTES:
        errors.append(f"{path}: file is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB")

    return errors


def _staged_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


if __name__ == "__main__":
    raise SystemExit(main())

