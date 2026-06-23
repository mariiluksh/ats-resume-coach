"""Build local keyword profiles from private datasets."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from ats_resume_coach.analyzer import ResumeAnalyzer
from ats_resume_coach.text import keyword_candidates
from ats_resume_coach.training.datasets import (
    LocalDocument,
    iter_authorized_resume_documents,
    iter_job_documents,
)


def build_profile(
    *,
    job_documents: Iterable[LocalDocument],
    resume_documents: Iterable[LocalDocument] = (),
    top_n: int = 120,
) -> dict:
    analyzer = ResumeAnalyzer()
    job_terms: Counter[str] = Counter()
    resume_terms: Counter[str] = Counter()
    skill_terms: Counter[str] = Counter()
    job_count = 0
    resume_count = 0

    for document in job_documents:
        job_count += 1
        job_terms.update(keyword_candidates(document.text, limit=50))
        for values in analyzer._match_skills(document.text).values():
            skill_terms.update(values)

    for document in resume_documents:
        resume_count += 1
        resume_terms.update(keyword_candidates(document.text, limit=50))

    distinctive_job_terms = {
        term: count
        for term, count in job_terms.most_common()
        if count >= 2 and count >= resume_terms.get(term, 0)
    }

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "document_counts": {
            "jobs": job_count,
            "authorized_resumes": resume_count,
        },
        "top_job_terms": dict(job_terms.most_common(top_n)),
        "top_distinctive_job_terms": dict(list(distinctive_job_terms.items())[:top_n]),
        "top_skill_terms": dict(skill_terms.most_common(top_n)),
        "notes": [
            "This artifact is derived from local/private data and must remain uncommitted.",
            "It contains aggregate keywords only, not source documents.",
        ],
    }


def train_profile_from_paths(
    *,
    jobs_parquet: str | Path,
    output: str | Path,
    authorized_resume_zip: str | Path | None = None,
    limit_jobs: int | None = 5000,
    limit_resumes: int | None = 1000,
    top_n: int = 120,
) -> Path:
    job_documents = iter_job_documents(jobs_parquet, limit=limit_jobs)
    resume_documents = (
        iter_authorized_resume_documents(authorized_resume_zip, limit=limit_resumes)
        if authorized_resume_zip
        else ()
    )
    profile = build_profile(
        job_documents=job_documents,
        resume_documents=resume_documents,
        top_n=top_n,
    )

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(profile, indent=2, sort_keys=True), encoding="utf-8")
    return output_path

