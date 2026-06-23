"""Build a tailored resume draft from the analysis output."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from docx import Document

from .analyzer import ResumeAnalyzer
from .schemas import AnalysisResult
from .text import extract_bullet_like_lines, extract_lines, has_email, has_phone, normalize_text


@dataclass(frozen=True)
class DraftResult:
    filename: str
    content_type: str
    data: bytes
    preview_text: str


def build_resume_draft(job_text: str, resume_text: str, analysis: AnalysisResult) -> DraftResult:
    job_text = normalize_text(job_text)
    resume_text = normalize_text(resume_text)
    lines = extract_lines(resume_text)
    bullets = extract_bullet_like_lines(resume_text)

    draft_lines = _build_text_draft(lines, bullets, job_text, resume_text, analysis)
    draft_text = "\n".join(draft_lines).strip() + "\n"

    document = Document()
    document.add_heading("Tailored Resume Draft", level=0)
    for section in _build_doc_sections(draft_lines):
        heading, entries = section
        document.add_heading(heading, level=1)
        for entry in entries:
            if entry.startswith("- "):
                document.add_paragraph(entry[2:], style="List Bullet")
            else:
                document.add_paragraph(entry)

    buffer = BytesIO()
    document.save(buffer)

    filename = _draft_filename(analysis)
    return DraftResult(
        filename=filename,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        data=buffer.getvalue(),
        preview_text=draft_text,
    )


def build_resume_draft_preview(job_text: str, resume_text: str, analysis: AnalysisResult) -> str:
    return build_resume_draft(job_text, resume_text, analysis).preview_text


def _build_text_draft(
    lines: list[str],
    bullets: list[str],
    job_text: str,
    resume_text: str,
    analysis: AnalysisResult,
) -> list[str]:
    header = _build_header(lines, resume_text)
    summary = _build_summary(analysis)
    skills = _build_skills(analysis)
    sections: list[str] = []
    sections.extend(header)
    sections.extend(["", "Summary", summary, "", "Skills", skills])

    project_lines = bullets[:]
    if not project_lines:
        project_lines = [line for line in lines if line and line not in header and line not in {"Education", "Skills"}][:4]
    if project_lines:
        sections.extend(["", "Projects"])
        sections.extend(f"- {line.lstrip('-• ').strip()}" for line in project_lines[:6])

    education_lines = _extract_heading_block(lines, "education")
    if education_lines:
        sections.extend(["", "Education"])
        sections.extend(education_lines)

    return sections


def _build_header(lines: list[str], resume_text: str) -> list[str]:
    candidates = []
    for line in lines[:5]:
        if has_email(line) or has_phone(line):
            candidates.append(line)
    if not candidates and lines:
        candidates.append(lines[0])
        candidates.extend([line for line in lines[1:5] if has_email(line) or has_phone(line)])
    if not candidates:
        candidates.append("Name")
    return candidates


def _build_summary(analysis: AnalysisResult) -> str:
    skills = []
    for values in analysis.matched_skills.values():
        skills.extend(values[:2])
    if not skills:
        skills = analysis.matched_keywords[:4]
    skills = list(dict.fromkeys(skills))[:5]
    role = analysis.job_title_guess or "the target role"
    if skills:
        return f"Candidate for {role} with strengths in {', '.join(skills)} and a focus on clear, ATS-friendly delivery."
    return f"Candidate for {role} with a focus on clear, ATS-friendly delivery."


def _build_skills(analysis: AnalysisResult) -> str:
    groups = []
    for category, values in analysis.matched_skills.items():
        if values:
            groups.append(f"{category.title()}: {', '.join(values)}")
    if not groups:
        groups = [", ".join(analysis.matched_keywords[:8])]
    return " | ".join(groups)


def _extract_heading_block(lines: list[str], heading: str) -> list[str]:
    result = []
    active = False
    for line in lines:
        lower = line.lower()
        if heading in lower and len(lower.split()) <= 3:
            active = True
            continue
        if active and any(word in lower for word in ("skills", "projects", "experience", "summary")) and heading not in lower:
            break
        if active:
            result.append(line)
    return result[:8]


def _build_doc_sections(lines: list[str]) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = []
    current_heading = "Draft"
    current_entries: list[str] = []
    for line in lines:
        if line in {"Summary", "Skills", "Projects", "Education"}:
            if current_entries:
                sections.append((current_heading, current_entries))
            current_heading = line
            current_entries = []
            continue
        current_entries.append(line)
    if current_entries:
        sections.append((current_heading, current_entries))
    return sections


def _draft_filename(analysis: AnalysisResult) -> str:
    slug = "tailored_resume"
    if analysis.job_title_guess:
        slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in analysis.job_title_guess)[:40].strip("_") or slug
    return f"{slug}_draft.docx"
