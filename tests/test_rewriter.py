from __future__ import annotations

import unittest

from ats_resume_coach.analyzer import ResumeAnalyzer
from ats_resume_coach.rewriter import build_resume_draft


class ResumeRewriterTest(unittest.TestCase):
    def test_builds_docx_draft(self) -> None:
        job = "Software engineering intern using Python FastAPI SQL Git testing communication."
        resume = """
        Jane Jane@example.com github.com/jane
        Education
        BS Computer Science
        Projects
        - Built an API with Python and SQL that processed 1000 records.
        """

        analysis = ResumeAnalyzer().analyze(job, resume)
        draft = build_resume_draft(job, resume, analysis)

        self.assertEqual(draft.content_type, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        self.assertTrue(draft.data.startswith(b"PK"))
        self.assertIn("Summary", draft.preview_text)

    def test_analysis_contains_edit_plan(self) -> None:
        job = "Data analyst intern using Python SQL Excel communication visualization."
        resume = """
        Alex alex@example.com
        Education
        BS Data Science
        """

        analysis = ResumeAnalyzer().analyze(job, resume)
        actions = [item.action for item in analysis.edit_plan]
        sections = [item.section for item in analysis.edit_plan]

        self.assertIn("insert", actions)
        self.assertIn("Projects", sections)
        self.assertIn("Skills", sections)


if __name__ == "__main__":
    unittest.main()
