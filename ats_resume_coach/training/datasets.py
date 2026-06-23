"""Local dataset readers for private, uncommitted data."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence
from zipfile import ZipFile

from ats_resume_coach.ingest import IngestError, extract_text_from_bytes
from ats_resume_coach.text import normalize_text


JOB_TEXT_COLUMNS = (
    "title",
    "job_title",
    "position",
    "company",
    "location",
    "description",
    "job_description",
    "requirements",
    "qualifications",
    "skills",
    "seniority",
    "employment_type",
)


@dataclass(frozen=True)
class LocalDocument:
    source: str
    text: str


def iter_job_documents(
    parquet_path: str | Path,
    *,
    text_columns: Sequence[str] | None = None,
    limit: int | None = None,
) -> Iterable[LocalDocument]:
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("Reading parquet data requires pandas and pyarrow. Install with .[ml].") from exc

    path = Path(parquet_path)
    if not path.exists():
        raise FileNotFoundError(path)

    dataframe = pd.read_parquet(path)
    columns = list(text_columns or _guess_job_columns(dataframe.columns))
    if not columns:
        raise ValueError("Could not identify text-like columns in the parquet file.")

    count = 0
    for index, row in dataframe[columns].iterrows():
        parts = [str(value) for value in row.values if value is not None and str(value).strip() and str(value) != "nan"]
        text = normalize_text("\n".join(parts))
        if text:
            yield LocalDocument(source=f"{path.name}:row:{index}", text=text)
            count += 1
        if limit is not None and count >= limit:
            break


def iter_authorized_resume_documents(
    resume_zip_path: str | Path,
    *,
    limit: int | None = None,
    max_member_bytes: int = 8 * 1024 * 1024,
) -> Iterable[LocalDocument]:
    """Yield resume texts from a zip the user has permission to process."""

    path = Path(resume_zip_path)
    if not path.exists():
        raise FileNotFoundError(path)

    count = 0
    with ZipFile(path) as archive:
        for member in archive.infolist():
            if member.is_dir() or member.file_size > max_member_bytes:
                continue
            suffix = Path(member.filename).suffix.lower()
            if suffix not in {".pdf", ".docx", ".txt", ".md", ".html", ".htm"}:
                continue
            try:
                text = extract_text_from_bytes(archive.read(member), filename=member.filename)
            except (IngestError, NotImplementedError, ValueError):
                continue
            text = normalize_text(text)
            if text:
                yield LocalDocument(source=f"{path.name}:{Path(member.filename).name}", text=text)
                count += 1
            if limit is not None and count >= limit:
                break


def _guess_job_columns(columns: Iterable[str]) -> list[str]:
    lower_to_original = {column.lower(): column for column in columns}
    guessed = [lower_to_original[name] for name in JOB_TEXT_COLUMNS if name in lower_to_original]
    if guessed:
        return guessed
    return [column for column in columns if any(signal in column.lower() for signal in ("title", "description", "skill", "require"))]

