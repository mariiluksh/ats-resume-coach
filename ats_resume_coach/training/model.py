"""Train local-only TF-IDF models from private datasets."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from ats_resume_coach.text import STOPWORDS, normalize_text
from ats_resume_coach.training.datasets import (
    JOB_TEXT_COLUMNS,
    LocalDocument,
    iter_authorized_resume_documents,
)


class LocalTrainingError(ValueError):
    """Raised when local model training cannot proceed safely."""


MODEL_STOPWORDS = {
    "applicant",
    "apply",
    "applying",
    "career",
    "careers",
    "description",
    "employer",
    "hiring",
    "ll",
    "opportunity",
    "posting",
    "recruiter",
    "recruiting",
    "strong",
    "unknown",
    "ve",
}
NOISY_TERM_TOKENS = {"mid", "senior"}


@dataclass(frozen=True)
class LocalModelSummary:
    artifact_path: str
    metadata_path: str
    job_count: int
    resume_count: int
    feature_count: int
    cluster_count: int
    top_terms: list[str]


def train_local_tfidf_model_from_paths(
    *,
    jobs_parquet: str | Path,
    output_dir: str | Path,
    authorized_resume_zip: str | Path | None = None,
    confirm_resume_consent: bool = False,
    limit_jobs: int | None = None,
    limit_resumes: int | None = None,
    max_features: int = 20000,
    min_df: int = 3,
    clusters: int = 12,
) -> LocalModelSummary:
    """Train a local private model and save it under output_dir.

    The artifact intentionally stores vectorized features and indices, not raw
    source text. It is still derived from private data and must stay ignored.
    """

    if authorized_resume_zip and not confirm_resume_consent:
        raise LocalTrainingError(
            "Resume corpus training requires --confirm-resume-consent. "
            "Use only resumes you own or have explicit permission to process."
        )

    try:
        import joblib
        import pandas as pd
        from sklearn.cluster import MiniBatchKMeans
        from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.neighbors import NearestNeighbors
    except ImportError as exc:
        raise RuntimeError("Training requires optional ML dependencies. Install with .[ml].") from exc

    jobs_path = Path(jobs_parquet)
    if not jobs_path.exists():
        raise FileNotFoundError(jobs_path)

    dataframe = pd.read_parquet(jobs_path)
    job_docs = _job_documents_from_dataframe(dataframe, limit=limit_jobs)
    resume_docs = (
        list(iter_authorized_resume_documents(authorized_resume_zip, limit=limit_resumes))
        if authorized_resume_zip
        else []
    )

    documents = job_docs + resume_docs
    if not documents:
        raise LocalTrainingError("No training documents were loaded.")

    texts = [document.text for document in documents]
    source_types = ["job"] * len(job_docs) + ["authorized_resume"] * len(resume_docs)

    vectorizer = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(1, 2),
        min_df=min_df,
        max_df=0.88,
        max_features=max_features,
        stop_words=sorted(set(ENGLISH_STOP_WORDS) | STOPWORDS | MODEL_STOPWORDS),
        sublinear_tf=True,
    )
    matrix = vectorizer.fit_transform(texts)

    neighbor_count = min(10, matrix.shape[0])
    neighbors = NearestNeighbors(n_neighbors=neighbor_count, metric="cosine")
    neighbors.fit(matrix)

    cluster_count = min(max(1, clusters), matrix.shape[0])
    clusterer = MiniBatchKMeans(
        n_clusters=cluster_count,
        random_state=42,
        n_init=10,
        batch_size=min(2048, max(100, matrix.shape[0])),
    )
    cluster_labels = clusterer.fit_predict(matrix)

    feature_names = vectorizer.get_feature_names_out()
    top_terms = _global_top_terms(matrix, feature_names, limit=60)
    cluster_terms = _cluster_top_terms(clusterer.cluster_centers_, feature_names, limit=15)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    artifact_path = output_path / "tfidf_model.joblib"
    metadata_path = output_path / "metadata.json"

    artifact = {
        "vectorizer": vectorizer,
        "neighbors": neighbors,
        "matrix": matrix,
        "clusterer": clusterer,
        "cluster_labels": cluster_labels,
        "source_types": source_types,
        "created_at": datetime.now(UTC).isoformat(),
    }
    joblib.dump(artifact, artifact_path)

    metadata = {
        "generated_at": artifact["created_at"],
        "artifact": artifact_path.name,
        "privacy": "Derived from local/private data. Do not commit.",
        "inputs": {
            "jobs_parquet_name": jobs_path.name,
            "authorized_resume_zip_name": Path(authorized_resume_zip).name if authorized_resume_zip else None,
        },
        "document_counts": {
            "jobs": len(job_docs),
            "authorized_resumes": len(resume_docs),
        },
        "feature_count": int(matrix.shape[1]),
        "cluster_count": int(cluster_count),
        "top_terms": top_terms,
        "cluster_terms": cluster_terms,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")

    return LocalModelSummary(
        artifact_path=str(artifact_path),
        metadata_path=str(metadata_path),
        job_count=len(job_docs),
        resume_count=len(resume_docs),
        feature_count=int(matrix.shape[1]),
        cluster_count=int(cluster_count),
        top_terms=top_terms[:20],
    )


def _job_documents_from_dataframe(dataframe, *, limit: int | None) -> list[LocalDocument]:
    columns = _selected_text_columns(dataframe.columns)
    if not columns:
        raise LocalTrainingError("Could not identify job text columns in the parquet file.")

    docs: list[LocalDocument] = []
    frame = dataframe[columns].head(limit) if limit else dataframe[columns]
    for index, row in frame.iterrows():
        values = []
        for value in row.values:
            if value is None:
                continue
            string_value = str(value).strip()
            if string_value and string_value.lower() not in {"nan", "none", "[]"}:
                values.append(string_value)
        text = normalize_text("\n".join(values))
        if text:
            docs.append(LocalDocument(source=f"job:{index}", text=text))
    return docs


def _selected_text_columns(columns: Iterable[str]) -> list[str]:
    lower_to_original = {column.lower(): column for column in columns}
    preferred = [
        "title",
        "description",
        "search_keyword",
        "role_kind",
        "seniority",
        "tech_tags",
        "labeled_disciplines",
        "labeled_archetypes",
        "job_technologies",
        "remote_status",
        "sponsorship_likelihood",
    ]
    selected = [lower_to_original[name] for name in preferred if name in lower_to_original]
    if selected:
        return selected
    return [lower_to_original[name] for name in JOB_TEXT_COLUMNS if name in lower_to_original]


def _global_top_terms(matrix, feature_names, *, limit: int) -> list[str]:
    scores = matrix.sum(axis=0).A1
    ranked_indices = scores.argsort()[::-1]
    terms = []
    for index in ranked_indices:
        term = str(feature_names[index])
        if scores[index] > 0 and _useful_model_term(term):
            terms.append(term)
        if len(terms) >= limit:
            break
    return terms


def _cluster_top_terms(cluster_centers, feature_names, *, limit: int) -> dict[str, list[str]]:
    result = {}
    for cluster_index, center in enumerate(cluster_centers):
        ranked_indices = center.argsort()[::-1]
        terms = []
        for index in ranked_indices:
            term = str(feature_names[index])
            if center[index] > 0 and _useful_model_term(term):
                terms.append(term)
            if len(terms) >= limit:
                break
        result[str(cluster_index)] = terms
    return result


def _useful_model_term(term: str) -> bool:
    tokens = term.split()
    if not tokens:
        return False
    if any(token in NOISY_TERM_TOKENS for token in tokens):
        return False
    if any(left == right for left, right in zip(tokens, tokens[1:])):
        return False
    return True
