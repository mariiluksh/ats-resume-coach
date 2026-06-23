"""Text normalization and lightweight extraction helpers."""

from __future__ import annotations

import html
import re
from collections import Counter


STOPWORDS = {
    "a",
    "about",
    "above",
    "after",
    "again",
    "all",
    "also",
    "am",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "because",
    "been",
    "being",
    "but",
    "by",
    "can",
    "candidate",
    "company",
    "could",
    "day",
    "do",
    "each",
    "for",
    "from",
    "had",
    "has",
    "have",
    "he",
    "her",
    "here",
    "him",
    "his",
    "how",
    "i",
    "if",
    "in",
    "intern",
    "internship",
    "into",
    "is",
    "it",
    "its",
    "job",
    "more",
    "must",
    "new",
    "no",
    "not",
    "of",
    "on",
    "or",
    "our",
    "own",
    "please",
    "position",
    "role",
    "she",
    "should",
    "so",
    "such",
    "team",
    "than",
    "that",
    "the",
    "their",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "to",
    "us",
    "we",
    "what",
    "when",
    "where",
    "which",
    "who",
    "will",
    "with",
    "work",
    "working",
    "would",
    "you",
    "your",
}

TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+#.\-]{1,}")
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:\+?\d[\s().-]*){7,}\d")
METRIC_RE = re.compile(
    r"\b(?:\d+(?:\.\d+)?%|\d+(?:\.\d+)?x|\$?\d+(?:,\d{3})*(?:\.\d+)?\s?"
    r"(?:users?|records?|requests?|rows?|hours?|days?|weeks?|seconds?|ms|projects?|people|clients?)?)\b",
    re.IGNORECASE,
)


def normalize_text(text: str) -> str:
    text = html.unescape(text or "")
    text = text.replace("\u00a0", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_for_match(text: str) -> str:
    normalized = normalize_text(text).lower()
    normalized = normalized.replace("node js", "node.js")
    normalized = normalized.replace("react js", "react.js")
    return f" {normalized} "


def tokenize(text: str) -> list[str]:
    raw_tokens = TOKEN_RE.findall(normalize_text(text).lower())
    return [token.strip(".-") for token in raw_tokens if token.strip(".-")]


def keyword_candidates(text: str, limit: int = 35) -> list[str]:
    tokens = [
        token
        for token in tokenize(text)
        if len(token) > 2 and token not in STOPWORDS and not token.isdigit()
    ]
    counts = Counter(tokens)
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [token for token, _ in ranked[:limit]]


def contains_phrase(text: str, phrase: str) -> bool:
    haystack = normalize_for_match(text)
    needle = normalize_for_match(phrase).strip()
    if not needle:
        return False
    if len(needle) <= 2:
        return f" {needle} " in haystack
    return needle in haystack


def extract_lines(text: str) -> list[str]:
    return [line.strip() for line in normalize_text(text).splitlines() if line.strip()]


def extract_bullet_like_lines(text: str) -> list[str]:
    lines = extract_lines(text)
    bullets = []
    for line in lines:
        if re.match(r"^[-*•◦‣]\s+", line):
            bullets.append(re.sub(r"^[-*•◦‣]\s+", "", line).strip())
        elif len(line.split()) >= 5 and line[:1].isupper() and any(char in line for char in ".,;"):
            bullets.append(line)
    return bullets


def has_metric(text: str) -> bool:
    return bool(METRIC_RE.search(text))


def has_email(text: str) -> bool:
    return bool(EMAIL_RE.search(text))


def has_phone(text: str) -> bool:
    return bool(PHONE_RE.search(text))

