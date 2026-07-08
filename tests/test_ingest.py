from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from ats_resume_coach.ingest import IngestError, extract_text_from_bytes
from ats_resume_coach.training.datasets import iter_authorized_resume_documents


class IngestTest(unittest.TestCase):
    def test_invalid_pdf_raises_ingest_error(self) -> None:
        with self.assertRaises(IngestError):
            extract_text_from_bytes(b"not a valid pdf", filename="resume.pdf")

    def test_invalid_docx_raises_ingest_error(self) -> None:
        with self.assertRaises(IngestError):
            extract_text_from_bytes(b"not a real docx", filename="resume.docx")

    def test_resume_zip_skips_unreadable_members(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_path = Path(tmpdir) / "resumes.zip"
            with ZipFile(archive_path, "w") as archive:
                archive.writestr("broken.pdf", b"not a valid pdf")
                archive.writestr("resume.txt", "Jane jane@example.com\nPython SQL FastAPI")

            documents = list(iter_authorized_resume_documents(archive_path))

        self.assertEqual(len(documents), 1)
        self.assertIn("Python SQL FastAPI", documents[0].text)


if __name__ == "__main__":
    unittest.main()
