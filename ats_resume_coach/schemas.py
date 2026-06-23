"""Shared response models for the analyzer, API, and CLI."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ScoreBreakdown:
    keyword_match: int
    skills_match: int
    sections: int
    contact: int
    bullet_quality: int
    ats_format: int


@dataclass(frozen=True)
class CritiqueItem:
    severity: str
    category: str
    message: str
    recommendation: str


@dataclass(frozen=True)
class AnalysisResult:
    overall_score: int
    verdict: str
    score_breakdown: ScoreBreakdown
    job_title_guess: str | None
    role_level: str
    matched_skills: dict[str, list[str]]
    missing_skills: dict[str, list[str]]
    matched_keywords: list[str]
    missing_keywords: list[str]
    critique: list[CritiqueItem]
    recommendations: list[str]
    bullet_rewrite_templates: list[str]
    model_signals: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)
