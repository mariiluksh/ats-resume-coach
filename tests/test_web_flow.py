from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from ats_resume_coach.api import create_app


JOB_TEXT = "Software engineering intern using Python FastAPI SQL Git testing communication."
RESUME_TEXT = """
Jane jane@example.com github.com/jane
Education
BS Computer Science
Projects
- Built an API with Python and SQL that processed 1000 records.
"""


class WebFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_app())

    def test_analyze_preserves_pasted_text_for_rewrite(self) -> None:
        response = self.client.post(
            "/analyze",
            data={"job_text": JOB_TEXT, "resume_text": RESUME_TEXT},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(JOB_TEXT, response.text)
        self.assertIn("Jane jane@example.com", response.text)

    def test_analyze_preserves_uploaded_text_for_rewrite(self) -> None:
        response = self.client.post(
            "/analyze",
            files={
                "job_file": ("job.txt", JOB_TEXT.encode(), "text/plain"),
                "resume_file": ("resume.txt", RESUME_TEXT.encode(), "text/plain"),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(JOB_TEXT, response.text)
        self.assertIn("Jane jane@example.com", response.text)

    def test_rewrite_downloads_docx_from_form_text(self) -> None:
        response = self.client.post(
            "/rewrite",
            data={"job_text": JOB_TEXT, "resume_text": RESUME_TEXT},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["content-type"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        self.assertTrue(response.content.startswith(b"PK"))

    def test_rewrite_validation_error_renders_html_form(self) -> None:
        response = self.client.post("/rewrite", data={})

        self.assertEqual(response.status_code, 400)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("Provide a job URL, job file, or pasted job text.", response.text)


if __name__ == "__main__":
    unittest.main()
