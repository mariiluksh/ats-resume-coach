from __future__ import annotations

import unittest

from ats_resume_coach.analyzer import ResumeAnalyzer


class ResumeAnalyzerTest(unittest.TestCase):
    def test_strong_resume_matches_intern_job(self) -> None:
        job = """
        Software Engineering Intern
        Build REST APIs with Python, FastAPI, SQL, Git, testing, and clear communication.
        """
        resume = """
        Jane Doe jane@example.com 555-555-5555 github.com/jane linkedin.com/in/jane
        Education
        BS Computer Science, expected 2027
        Skills
        Python, FastAPI, SQL, Git, pytest, communication
        Projects
        - Built a REST API with Python, FastAPI, and SQL that processed 10,000 records.
        - Tested endpoints with pytest and documented setup steps for a team of 4.
        """

        result = ResumeAnalyzer().analyze(job, resume)

        self.assertGreaterEqual(result.overall_score, 70)
        self.assertIn("python", result.matched_skills["programming"])
        self.assertNotIn("python", result.missing_keywords)

    def test_missing_projects_are_flagged_for_intern_resume(self) -> None:
        job = "Data analyst intern role using Python, SQL, visualization, and Excel."
        resume = """
        Alex alex@example.com
        Education
        BS Data Science
        Skills
        Excel
        """

        result = ResumeAnalyzer().analyze(job, resume)

        categories = {item.category for item in result.critique}
        self.assertIn("intern positioning", categories)
        self.assertIn("python", result.missing_skills["programming"])

    def test_edit_plan_skips_headers_and_section_labels(self) -> None:
        job = "Commodities portfolio manager using Python risk analysis communication."
        resume = """
        Jane jane@example.com github.com/jane
        Education
        BS Computer Science
        Projects
        - Built an API with Python and SQL that processed 1000 records.
        """

        result = ResumeAnalyzer().analyze(job, resume)
        replace_items = [item for item in result.edit_plan if item.action == "replace"]

        self.assertLessEqual(len(replace_items), 1)
        self.assertTrue(all("Jane" not in (item.current or "") for item in replace_items))
        self.assertTrue(all("Education" not in (item.current or "") for item in replace_items))

    def test_job_headline_terms_are_not_promoted_as_noise(self) -> None:
        job = "Citadel commodities portfolio manager using Python analysis communication."
        resume = """
        Jane jane@example.com
        Education
        BS Computer Science
        Skills
        Python, SQL, communication
        """

        result = ResumeAnalyzer().analyze(job, resume)
        self.assertNotIn("citadel", result.missing_keywords)
        self.assertNotIn("commodities", result.missing_keywords)
        self.assertNotIn("portfolio", result.missing_keywords)


if __name__ == "__main__":
    unittest.main()
