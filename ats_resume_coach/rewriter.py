"""Build a tailored resume draft from the analysis output."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from docx import Document
from docx.document import Document as DocxDocument
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph

from .schemas import AnalysisResult
from .text import extract_bullet_like_lines, extract_lines, has_email, has_phone, normalize_text


@dataclass(frozen=True)
class DraftResult:
    filename: str
    content_type: str
    data: bytes
    preview_text: str


DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
SECTION_HEADINGS = {
    "education",
    "experience",
    "work experience",
    "professional experience",
    "employment",
    "projects",
    "technical projects",
    "skills",
    "technical skills",
    "core skills",
    "summary",
    "profile",
    "professional summary",
    "certifications",
    "awards",
    "leadership",
    "publications",
}
SUMMARY_HEADINGS = {"summary", "profile", "professional summary"}
SKILLS_HEADINGS = {"skills", "technical skills", "core skills"}


def build_resume_draft(
    job_text: str,
    resume_text: str,
    analysis: AnalysisResult,
    *,
    source_docx: bytes | None = None,
    source_filename: str | None = None,
) -> DraftResult:
    job_text = normalize_text(job_text)
    resume_text = normalize_text(resume_text)
    if source_docx:
        return _build_style_preserving_docx(
            source_docx=source_docx,
            source_filename=source_filename,
            job_text=job_text,
            resume_text=resume_text,
            analysis=analysis,
        )

    lines = extract_lines(resume_text)
    bullets = extract_bullet_like_lines(resume_text)

    draft_lines = _build_text_draft(lines, bullets, job_text, resume_text, analysis)
    draft_text = "\n".join(draft_lines).strip() + "\n"

    document = Document()
    for section in _build_doc_sections(draft_lines):
        heading, entries = section
        if heading != "Header":
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
        content_type=DOCX_CONTENT_TYPE,
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
    sections.extend(["", "Professional Summary", summary])
    if skills:
        sections.extend(["", "Core Skills", skills])

    for heading, entries in _extract_resume_sections(lines, header):
        normalized_heading = _normalize_heading(heading)
        if normalized_heading in SUMMARY_HEADINGS | SKILLS_HEADINGS:
            continue
        sections.extend(["", heading])
        sections.extend(entries)

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


def _build_style_preserving_docx(
    *,
    source_docx: bytes,
    source_filename: str | None,
    job_text: str,
    resume_text: str,
    analysis: AnalysisResult,
) -> DraftResult:
    document = Document(BytesIO(source_docx))
    summary = _build_summary(analysis)
    skills = _build_skills(analysis)
    preview_lines = ["Preserved original DOCX resume content.", "Professional Summary", summary]
    if skills:
        preview_lines.extend(["Core Skills", skills])

    heading_style = _existing_heading_style(document)
    body_style = _existing_body_style(document)
    anchor = _top_insert_anchor(document, resume_text)

    insertion_anchor = anchor
    if not _has_section(document, SUMMARY_HEADINGS):
        insertion_anchor = _insert_resume_section(
            insertion_anchor,
            "Professional Summary",
            [summary],
            heading_style=heading_style,
            body_style=body_style,
        )

    if skills and not _has_section(document, SKILLS_HEADINGS):
        insertion_anchor = _insert_resume_section(
            insertion_anchor,
            "Core Skills",
            [skills],
            heading_style=heading_style,
            body_style=body_style,
        )

    buffer = BytesIO()
    document.save(buffer)

    return DraftResult(
        filename=_tailored_filename(source_filename, analysis),
        content_type=DOCX_CONTENT_TYPE,
        data=buffer.getvalue(),
        preview_text="\n".join(preview_lines).strip() + "\n",
    )


def _extract_resume_sections(lines: list[str], header: list[str]) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = []
    current_heading: str | None = None
    current_entries: list[str] = []
    header_values = set(header)

    for line in lines:
        if line in header_values:
            continue
        if _looks_like_heading(line):
            if current_heading and current_entries:
                sections.append((current_heading, current_entries))
            current_heading = _display_heading(line)
            current_entries = []
            continue
        if current_heading is None:
            current_heading = "Experience"
        current_entries.append(_format_source_line(line))

    if current_heading and current_entries:
        sections.append((current_heading, current_entries))
    return sections


def _build_doc_sections(lines: list[str]) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = []
    current_heading = "Header"
    current_entries: list[str] = []
    for line in lines:
        if _is_output_section_heading(line):
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
    return f"{slug}.docx"


def _tailored_filename(source_filename: str | None, analysis: AnalysisResult) -> str:
    if source_filename:
        stem = Path(source_filename).stem
        cleaned = "".join(ch if ch.isalnum() or ch in {" ", "-", "_"} else "_" for ch in stem).strip()
        if cleaned:
            return f"{cleaned}_tailored.docx"
    return _draft_filename(analysis)


def _normalize_heading(text: str) -> str:
    return " ".join(text.lower().strip().strip(":").split())


def _looks_like_heading(line: str) -> bool:
    normalized = _normalize_heading(line)
    if normalized in SECTION_HEADINGS:
        return True
    words = normalized.split()
    return 1 <= len(words) <= 4 and line.upper() == line and any(word in SECTION_HEADINGS for word in words)


def _is_output_section_heading(line: str) -> bool:
    return line in {"Professional Summary", "Core Skills"} or _normalize_heading(line) in SECTION_HEADINGS


def _display_heading(line: str) -> str:
    normalized = _normalize_heading(line)
    if normalized in {"technical skills", "skills"}:
        return "Core Skills"
    if normalized in SUMMARY_HEADINGS:
        return "Professional Summary"
    return line.strip().strip(":").title()


def _format_source_line(line: str) -> str:
    cleaned = line.strip()
    if cleaned.startswith(("•", "-", "*")):
        return "- " + cleaned.lstrip("•-* \t")
    return cleaned


def _has_section(document: DocxDocument, headings: set[str]) -> bool:
    return any(_normalize_heading(paragraph.text) in headings for paragraph in document.paragraphs)


def _top_insert_anchor(document: DocxDocument, resume_text: str) -> Paragraph:
    paragraphs = [paragraph for paragraph in document.paragraphs if paragraph.text.strip()]
    if not paragraphs:
        return document.add_paragraph()

    for index, paragraph in enumerate(paragraphs[:8]):
        if has_email(paragraph.text) or has_phone(paragraph.text):
            return paragraph
        if index > 0 and _looks_like_heading(paragraph.text):
            return paragraphs[index - 1]

    lines = extract_lines(resume_text)
    if len(lines) >= 2:
        for paragraph in paragraphs[:8]:
            if paragraph.text.strip() == lines[1]:
                return paragraph
    return paragraphs[0]


def _existing_heading_style(document: DocxDocument) -> str:
    for paragraph in document.paragraphs:
        if paragraph.text.strip() and _looks_like_heading(paragraph.text):
            return paragraph.style.name
    return "Heading 1"


def _existing_body_style(document: DocxDocument) -> str:
    for paragraph in document.paragraphs:
        if paragraph.text.strip() and not _looks_like_heading(paragraph.text):
            return paragraph.style.name
    return "Normal"


def _insert_resume_section(
    anchor: Paragraph,
    heading: str,
    entries: list[str],
    *,
    heading_style: str,
    body_style: str,
) -> Paragraph:
    heading_paragraph = _insert_paragraph_after(anchor, heading, heading_style)
    last = heading_paragraph
    for entry in entries:
        last = _insert_paragraph_after(last, entry, body_style)
    return last


def _insert_paragraph_after(anchor: Paragraph, text: str, style: str | None = None) -> Paragraph:
    new_element = OxmlElement("w:p")
    anchor._p.addnext(new_element)
    paragraph = Paragraph(new_element, anchor._parent)
    if style:
        paragraph.style = style
    paragraph.add_run(text)
    return paragraph
