"""Deterministic ATS-style resume critique."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from .schemas import AnalysisResult, CritiqueItem, EditPlanItem, ScoreBreakdown
from .taxonomy import (
    ACTION_VERBS,
    ROLE_LEVEL_SIGNALS,
    SECTION_ALIASES,
    SKILL_ALIASES,
    WEAK_PHRASES,
)
from .text import (
    contains_phrase,
    extract_bullet_like_lines,
    extract_lines,
    has_email,
    has_metric,
    has_phone,
    keyword_candidates,
    normalize_for_match,
    normalize_text,
    tokenize,
)


class ResumeAnalyzer:
    """Analyze a resume against a job description."""

    def __init__(self, *, local_model: Any | None = None) -> None:
        self.local_model = local_model

    def analyze(self, job_text: str, resume_text: str) -> AnalysisResult:
        job_text = normalize_text(job_text)
        resume_text = normalize_text(resume_text)
        if not job_text:
            raise ValueError("Job text is required.")
        if not resume_text:
            raise ValueError("Resume text is required.")

        job_keywords = keyword_candidates(job_text)
        matched_keywords = [word for word in job_keywords if contains_phrase(resume_text, word)]
        missing_keywords = [word for word in job_keywords if word not in matched_keywords][:15]

        job_skills = self._match_skills(job_text)
        resume_skills = self._match_skills(resume_text)
        matched_skills, missing_skills = self._compare_skills(job_skills, resume_skills)

        sections = self._detect_sections(resume_text)
        contacts = self._detect_contact_signals(resume_text)
        bullet_stats = self._bullet_stats(resume_text)
        format_stats = self._format_stats(resume_text)

        score_breakdown = self._score(
            job_keywords=job_keywords,
            matched_keywords=matched_keywords,
            job_skills=job_skills,
            matched_skills=matched_skills,
            sections=sections,
            contacts=contacts,
            bullet_stats=bullet_stats,
            format_stats=format_stats,
        )
        overall_score = sum(score_breakdown.__dict__.values())

        critique = self._build_critique(
            score_breakdown=score_breakdown,
            missing_keywords=missing_keywords,
            missing_skills=missing_skills,
            sections=sections,
            contacts=contacts,
            bullet_stats=bullet_stats,
            format_stats=format_stats,
        )
        edit_plan = self._build_edit_plan(
            missing_keywords=missing_keywords,
            missing_skills=missing_skills,
            sections=sections,
            contacts=contacts,
            bullet_stats=bullet_stats,
            resume_text=resume_text,
        )
        model_signals = self._model_signals(job_text=job_text, resume_text=resume_text)
        if model_signals:
            self._add_model_critique(critique, model_signals)
            edit_plan.extend(self._model_edit_plan(model_signals))

        recommendations = self._recommendations(critique, missing_keywords, missing_skills, sections)

        return AnalysisResult(
            overall_score=overall_score,
            verdict=self._verdict(overall_score),
            score_breakdown=score_breakdown,
            job_title_guess=self._guess_title(job_text),
            role_level=self._role_level(job_text),
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            matched_keywords=matched_keywords[:20],
            missing_keywords=missing_keywords,
            critique=critique,
            edit_plan=edit_plan,
            recommendations=recommendations,
            bullet_rewrite_templates=self._bullet_templates(missing_keywords, missing_skills),
            model_signals=model_signals,
        )

    def _match_skills(self, text: str) -> dict[str, list[str]]:
        matched: dict[str, list[str]] = {}
        haystack = normalize_for_match(text)
        for category, skills in SKILL_ALIASES.items():
            found = []
            for skill, aliases in skills.items():
                if any(self._alias_present(haystack, alias) for alias in aliases):
                    found.append(skill)
            if found:
                matched[category] = sorted(found)
        return matched

    def _alias_present(self, normalized_text: str, alias: str) -> bool:
        alias = normalize_for_match(alias)
        if alias.strip() == "r":
            return bool(re.search(r"\br\b", normalized_text))
        if alias.strip() == "go":
            return " go language " in normalized_text or " golang " in normalized_text
        return alias.strip() in normalized_text

    def _compare_skills(
        self, job_skills: dict[str, list[str]], resume_skills: dict[str, list[str]]
    ) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
        matched: dict[str, list[str]] = {}
        missing: dict[str, list[str]] = {}
        for category, required in job_skills.items():
            resume_values = set(resume_skills.get(category, []))
            matched_values = sorted(skill for skill in required if skill in resume_values)
            missing_values = sorted(skill for skill in required if skill not in resume_values)
            if matched_values:
                matched[category] = matched_values
            if missing_values:
                missing[category] = missing_values
        return matched, missing

    def _detect_sections(self, resume_text: str) -> dict[str, bool]:
        return {
            section: any(contains_phrase(resume_text, alias) for alias in aliases)
            for section, aliases in SECTION_ALIASES.items()
        }

    def _detect_contact_signals(self, resume_text: str) -> dict[str, bool]:
        lowered = normalize_for_match(resume_text)
        return {
            "email": has_email(resume_text),
            "phone": has_phone(resume_text),
            "linkedin": "linkedin.com" in lowered or " linkedin " in lowered,
            "github": "github.com" in lowered or " github " in lowered,
            "portfolio": "portfolio" in lowered or "personal site" in lowered,
        }

    def _bullet_stats(self, resume_text: str) -> dict[str, int | float]:
        bullets = extract_bullet_like_lines(resume_text)
        if not bullets:
            return {
                "count": 0,
                "with_metric": 0,
                "with_action_verb": 0,
                "weak": 0,
                "quality_ratio": 0.0,
            }
        with_metric = sum(1 for bullet in bullets if has_metric(bullet))
        with_action_verb = sum(1 for bullet in bullets if self._has_action_verb(bullet))
        weak = sum(1 for bullet in bullets if self._has_weak_phrase(bullet))
        quality_ratio = ((with_metric + with_action_verb) / (len(bullets) * 2)) - (weak / len(bullets) * 0.25)
        return {
            "count": len(bullets),
            "with_metric": with_metric,
            "with_action_verb": with_action_verb,
            "weak": weak,
            "quality_ratio": max(0.0, min(1.0, quality_ratio)),
        }

    def _has_action_verb(self, bullet: str) -> bool:
        words = set(tokenize(bullet))
        return bool(words & ACTION_VERBS)

    def _has_weak_phrase(self, bullet: str) -> bool:
        lowered = normalize_for_match(bullet)
        return any(phrase in lowered for phrase in WEAK_PHRASES)

    def _format_stats(self, resume_text: str) -> dict[str, bool | int]:
        lines = extract_lines(resume_text)
        long_lines = sum(1 for line in lines if len(line) > 140)
        odd_characters = len(re.findall(r"[^\w\s.,;:()/%+@#&'\"-]", resume_text))
        return {
            "line_count": len(lines),
            "long_lines": long_lines,
            "odd_characters": odd_characters,
            "too_short": len(tokenize(resume_text)) < 120,
            "likely_single_block": len(lines) <= 3 and len(resume_text) > 600,
        }

    def _score(
        self,
        *,
        job_keywords: list[str],
        matched_keywords: list[str],
        job_skills: dict[str, list[str]],
        matched_skills: dict[str, list[str]],
        sections: dict[str, bool],
        contacts: dict[str, bool],
        bullet_stats: dict[str, int | float],
        format_stats: dict[str, bool | int],
    ) -> ScoreBreakdown:
        keyword_ratio = len(matched_keywords) / max(len(job_keywords), 1)
        required_skill_count = sum(len(values) for values in job_skills.values())
        matched_skill_count = sum(len(values) for values in matched_skills.values())
        skill_ratio = matched_skill_count / max(required_skill_count, 1)

        section_weights = {
            "education": 4,
            "experience": 3,
            "projects": 4,
            "skills": 3,
            "summary": 1,
        }
        section_score = sum(weight for section, weight in section_weights.items() if sections.get(section))
        contact_score = 0
        contact_score += 4 if contacts["email"] else 0
        contact_score += 2 if contacts["phone"] else 0
        contact_score += 2 if contacts["linkedin"] else 0
        contact_score += 2 if contacts["github"] or contacts["portfolio"] else 0

        bullet_score = round(float(bullet_stats["quality_ratio"]) * 10)
        if int(bullet_stats["count"]) == 0:
            bullet_score = 0
        elif int(bullet_stats["count"]) < 4:
            bullet_score = min(bullet_score, 6)

        format_score = 5
        if format_stats["too_short"]:
            format_score -= 2
        if format_stats["likely_single_block"]:
            format_score -= 2
        if int(format_stats["long_lines"]) > 4:
            format_score -= 1
        if int(format_stats["odd_characters"]) > 25:
            format_score -= 1

        return ScoreBreakdown(
            keyword_match=round(keyword_ratio * 40),
            skills_match=round(skill_ratio * 20) if required_skill_count else 12,
            sections=min(section_score, 15),
            contact=min(contact_score, 10),
            bullet_quality=max(0, min(bullet_score, 10)),
            ats_format=max(0, min(format_score, 5)),
        )

    def _build_critique(
        self,
        *,
        score_breakdown: ScoreBreakdown,
        missing_keywords: list[str],
        missing_skills: dict[str, list[str]],
        sections: dict[str, bool],
        contacts: dict[str, bool],
        bullet_stats: dict[str, int | float],
        format_stats: dict[str, bool | int],
    ) -> list[CritiqueItem]:
        items: list[CritiqueItem] = []

        if score_breakdown.keyword_match < 24:
            items.append(
                CritiqueItem(
                    severity="high",
                    category="keyword match",
                    message="The resume does not mirror enough important terms from the vacancy.",
                    recommendation="Add truthful, role-relevant keywords in skills, project bullets, and coursework.",
                )
            )
        if missing_skills:
            flat_skills = ", ".join(skill for values in missing_skills.values() for skill in values[:3])
            items.append(
                CritiqueItem(
                    severity="high" if score_breakdown.skills_match < 10 else "medium",
                    category="skills",
                    message=f"The job asks for skills not clearly visible in the resume: {flat_skills}.",
                    recommendation="If you have used these tools, name them explicitly near the relevant project or experience.",
                )
            )
        missing_sections = [section for section, present in sections.items() if not present]
        if "projects" in missing_sections:
            items.append(
                CritiqueItem(
                    severity="high",
                    category="intern positioning",
                    message="Projects are not clearly labeled, which is a major gap for internship applications.",
                    recommendation="Add a Projects section with 2-4 technical projects tied to the target role.",
                )
            )
        if "education" in missing_sections:
            items.append(
                CritiqueItem(
                    severity="medium",
                    category="education",
                    message="Education is not easy to detect.",
                    recommendation="Label the Education section and include degree, university, expected graduation, and relevant coursework.",
                )
            )
        if not contacts["email"] or not (contacts["linkedin"] or contacts["github"] or contacts["portfolio"]):
            items.append(
                CritiqueItem(
                    severity="medium",
                    category="contact",
                    message="Contact/profile links are incomplete for a technical internship resume.",
                    recommendation="Include email plus LinkedIn and GitHub or portfolio links in plain text.",
                )
            )
        if int(bullet_stats["count"]) == 0:
            items.append(
                CritiqueItem(
                    severity="high",
                    category="bullet quality",
                    message="The analyzer could not detect resume bullets.",
                    recommendation="Use concise bullets under each project or experience so ATS parsing and human scanning are easier.",
                )
            )
        elif float(bullet_stats["quality_ratio"]) < 0.45:
            items.append(
                CritiqueItem(
                    severity="medium",
                    category="bullet quality",
                    message="Many bullets look vague or lack measurable outcomes.",
                    recommendation="Start bullets with action verbs and add scope, tools, and a measurable result where possible.",
                )
            )
        if format_stats["likely_single_block"] or int(format_stats["long_lines"]) > 4:
            items.append(
                CritiqueItem(
                    severity="medium",
                    category="ATS format",
                    message="The extracted resume text looks hard for ATS systems to segment.",
                    recommendation="Use a single-column layout with clear section headings and avoid tables/text boxes.",
                )
            )
        if missing_keywords:
            items.append(
                CritiqueItem(
                    severity="low",
                    category="missing keywords",
                    message="Several vacancy terms are absent from the resume.",
                    recommendation=f"Review these terms and add only the truthful ones: {', '.join(missing_keywords[:8])}.",
                )
            )
        return items

    def _build_edit_plan(
        self,
        *,
        missing_keywords: list[str],
        missing_skills: dict[str, list[str]],
        sections: dict[str, bool],
        contacts: dict[str, bool],
        bullet_stats: dict[str, int | float],
        resume_text: str,
    ) -> list[EditPlanItem]:
        items: list[EditPlanItem] = []

        if not sections.get("summary"):
            items.append(
                EditPlanItem(
                    action="insert",
                    section="Summary",
                    current=None,
                    suggestion="Add a 1-2 sentence summary that mirrors the target role and your strongest truthful skills.",
                    reason="A short summary helps ATS and recruiters anchor the resume to the vacancy.",
                )
            )
        if not sections.get("skills"):
            items.append(
                EditPlanItem(
                    action="insert",
                    section="Skills",
                    current=None,
                    suggestion="Add a Skills section with only tools and technologies you can defend in interview.",
                    reason="ATS matching improves when key tools appear in a dedicated skills block.",
                )
            )
        if not sections.get("projects"):
            items.append(
                EditPlanItem(
                    action="insert",
                    section="Projects",
                    current=None,
                    suggestion="Add 2-4 project bullets that show the tools and results most relevant to the job.",
                    reason="Intern resumes usually need project evidence when work history is thin.",
                )
            )
        if not sections.get("education"):
            items.append(
                EditPlanItem(
                    action="insert",
                    section="Education",
                    current=None,
                    suggestion="Add degree, school, expected graduation date, and relevant coursework.",
                    reason="Education is an important signal for entry-level screening.",
                )
            )
        if not contacts["linkedin"] or not contacts["github"]:
            items.append(
                EditPlanItem(
                    action="insert",
                    section="Contact",
                    current=None,
                    suggestion="Add LinkedIn and GitHub or portfolio links in plain text.",
                    reason="Technical recruiters scan for public work samples and profile links.",
                )
            )
        if int(bullet_stats["count"]) == 0:
            items.append(
                EditPlanItem(
                    action="insert",
                    section="Projects/Experience",
                    current=None,
                    suggestion="Insert concise bullets under each project or experience item with an action verb and a result.",
                    reason="The resume text did not expose bullets, which hurts ATS readability.",
                )
            )
        else:
            for bullet in self._rewrite_candidates(resume_text)[:3]:
                if self._has_weak_phrase(bullet) or len(tokenize(bullet)) < 8 or not has_metric(bullet):
                    items.append(
                        EditPlanItem(
                            action="replace",
                            section="Projects/Experience",
                            current=bullet,
                            suggestion=self._rewrite_bullet(bullet, missing_skills, missing_keywords),
                            reason="This bullet is vague or hard for ATS to score; rewrite it with a clearer action-result structure.",
                        )
                    )
        if missing_keywords:
            items.append(
                EditPlanItem(
                    action="insert",
                    section="Keywords",
                    current=", ".join(missing_keywords[:8]),
                    suggestion="Add only truthful instances of the missing job terms in skills, summary, or bullets.",
                    reason="Mirror vacancy language where it reflects real experience.",
                )
            )
        if missing_skills:
            flat_skills = ", ".join(skill for values in missing_skills.values() for skill in values[:6])
            items.append(
                EditPlanItem(
                    action="insert",
                    section="Skills/Projects",
                    current=flat_skills,
                    suggestion="If these skills are truly yours, name them directly in the relevant project or skills section.",
                    reason="The resume currently under-signals skills the vacancy expects.",
                )
            )
        return items

    def _rewrite_candidates(self, resume_text: str) -> list[str]:
        candidates = []
        seen = set()
        for bullet in extract_bullet_like_lines(resume_text):
            normalized = normalize_for_match(bullet)
            if not re.match(r"^[-*•◦‣]\s+", bullet.strip()):
                continue
            if has_email(bullet) or has_phone(bullet):
                continue
            if len(tokenize(bullet)) < 6:
                continue
            if any(
                heading in normalized
                for heading in (
                    "education",
                    "experience",
                    "projects",
                    "skills",
                    "summary",
                    "profile",
                    "additional information",
                    "work experience",
                )
            ):
                continue
            if bullet.lower() in seen:
                continue
            candidates.append(bullet)
            seen.add(bullet.lower())
        return candidates

    def _model_signals(self, *, job_text: str, resume_text: str) -> dict[str, Any] | None:
        if not self.local_model:
            return None
        try:
            return self.local_model.signals(job_text=job_text, resume_text=resume_text)
        except Exception:
            return None

    def _add_model_critique(self, critique: list[CritiqueItem], model_signals: dict[str, Any]) -> None:
        missing_terms = model_signals.get("missing_cluster_terms") or []
        if len(missing_terms) >= 5:
            critique.append(
                CritiqueItem(
                    severity="low",
                    category="local model",
                    message="The local job model found cluster terms that are not visible in the resume.",
                    recommendation="Review these model-derived terms and add only the truthful ones: "
                    + ", ".join(missing_terms[:8])
                    + ".",
                )
            )

    def _model_edit_plan(self, model_signals: dict[str, Any]) -> list[EditPlanItem]:
        missing_terms = model_signals.get("missing_cluster_terms") or []
        if not missing_terms:
            return []
        return [
            EditPlanItem(
                action="insert",
                section="Model-derived keywords",
                current=", ".join(missing_terms[:8]),
                suggestion="If these model-derived terms are truthful for your background, work them into the summary, skills, or project bullets.",
                reason="The local job model found adjacent terms that the current resume does not expose.",
            )
        ]

    def _rewrite_bullet(self, bullet: str, missing_skills: dict[str, list[str]], missing_keywords: list[str]) -> str:
        cleaned = bullet.strip(" -•\t")
        if not cleaned:
            return "Write a concise bullet with an action verb, tools used, and a measurable result if true."
        if self._has_weak_phrase(cleaned):
            for phrase in WEAK_PHRASES:
                if phrase in normalize_for_match(cleaned):
                    cleaned = re.sub(re.escape(phrase), "built", cleaned, flags=re.IGNORECASE)
                    break
        if not self._has_action_verb(cleaned):
            cleaned = f"Built {cleaned[0].lower() + cleaned[1:]}" if cleaned else cleaned
        extras = []
        for values in missing_skills.values():
            extras.extend(values[:1])
        if extras:
            extras = extras[:2]
            cleaned = f"{cleaned} using {', '.join(extras)}"
        elif missing_keywords:
            cleaned = f"{cleaned} with focus on {', '.join(missing_keywords[:2])}"
        if not cleaned.endswith("."):
            cleaned += "."
        return cleaned

    def _recommendations(
        self,
        critique: list[CritiqueItem],
        missing_keywords: list[str],
        missing_skills: dict[str, list[str]],
        sections: dict[str, bool],
    ) -> list[str]:
        recommendations = []
        for item in critique[:5]:
            recommendations.append(item.recommendation)
        if missing_skills:
            top_skills = [skill for skills in missing_skills.values() for skill in skills][:5]
            recommendations.append(
                "Create a target-role skills line using exact job wording for skills you can defend: "
                + ", ".join(top_skills)
                + "."
            )
        if not sections.get("projects"):
            recommendations.append(
                "For internship applications, move the strongest technical or analytical projects above unrelated work history."
            )
        if missing_keywords:
            recommendations.append(
                "Use vacancy language naturally; do not keyword-stuff. Each added keyword should appear inside a concrete project, class, or result."
            )
        return _dedupe(recommendations)[:8]

    def _bullet_templates(
        self, missing_keywords: list[str], missing_skills: dict[str, list[str]]
    ) -> list[str]:
        skills = [skill for values in missing_skills.values() for skill in values]
        primary_skill = skills[0] if skills else (missing_keywords[0] if missing_keywords else "target tool")
        secondary_signal = missing_keywords[1] if len(missing_keywords) > 1 else "user need"
        return [
            f"Built [project] using {primary_skill} to solve [problem], improving [metric] by [number].",
            f"Analyzed [dataset/process] with {primary_skill} and documented findings that helped [audience] decide [outcome].",
            f"Implemented [feature/workflow] for {secondary_signal}, tested it with [method], and reduced [error/time] by [number].",
        ]

    def _guess_title(self, job_text: str) -> str | None:
        lines = [line for line in extract_lines(job_text) if 4 <= len(line) <= 90]
        for line in lines[:8]:
            lowered = line.lower()
            if any(signal in lowered for signal in ("intern", "trainee", "junior", "analyst", "developer", "engineer")):
                return line[:90]
        return lines[0][:90] if lines else None

    def _role_level(self, job_text: str) -> str:
        lowered = normalize_for_match(job_text)
        for level, signals in ROLE_LEVEL_SIGNALS.items():
            if any(signal in lowered for signal in signals):
                return level
        return "unspecified"

    def _verdict(self, score: int) -> str:
        if score >= 80:
            return "strong match with minor ATS polish needed"
        if score >= 65:
            return "usable but should be tailored before applying"
        if score >= 45:
            return "needs targeted revision for this vacancy"
        return "high risk of ATS or recruiter rejection without revision"


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
