"""Optional runtime access to local private model artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ats_resume_coach.text import contains_phrase


NOISY_TERM_TOKENS = {"mid", "senior"}


@dataclass(frozen=True)
class LocalModelRuntime:
    vectorizer: Any
    clusterer: Any
    metadata: dict[str, Any]

    def signals(self, *, job_text: str, resume_text: str, limit: int = 20) -> dict[str, Any]:
        vector = self.vectorizer.transform([job_text])
        cluster_id = int(self.clusterer.predict(vector)[0])
        cluster_terms = [
            term
            for term in self.metadata.get("cluster_terms", {}).get(str(cluster_id), [])
            if _useful_model_term(term)
        ][:limit]
        matched_terms = [term for term in cluster_terms if contains_phrase(resume_text, term)]
        missing_terms = [term for term in cluster_terms if term not in matched_terms]
        return {
            "model_available": True,
            "cluster_id": cluster_id,
            "cluster_terms": cluster_terms,
            "matched_cluster_terms": matched_terms,
            "missing_cluster_terms": missing_terms,
        }


def load_optional_local_model(model_dir: str | Path) -> LocalModelRuntime | None:
    directory = Path(model_dir)
    artifact_path = directory / "tfidf_model.joblib"
    metadata_path = directory / "metadata.json"
    if not artifact_path.exists() or not metadata_path.exists():
        return None

    try:
        import joblib
    except ImportError:
        return None

    artifact = joblib.load(artifact_path)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    return LocalModelRuntime(
        vectorizer=artifact["vectorizer"],
        clusterer=artifact["clusterer"],
        metadata=metadata,
    )


def _useful_model_term(term: str) -> bool:
    tokens = term.split()
    if not tokens:
        return False
    if any(token in NOISY_TERM_TOKENS for token in tokens):
        return False
    if any(left == right for left, right in zip(tokens, tokens[1:])):
        return False
    return True
