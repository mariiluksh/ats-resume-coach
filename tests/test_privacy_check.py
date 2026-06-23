from __future__ import annotations

import unittest

from scripts.check_no_private_data import check_path


class PrivacyCheckTest(unittest.TestCase):
    def test_blocks_raw_data_and_private_extensions(self) -> None:
        errors = check_path("data/raw/job_training_dataset_v1.parquet")
        self.assertTrue(any("private data/model directory" in error for error in errors))
        self.assertTrue(any("extension is blocked" in error for error in errors))

    def test_blocks_local_env_files(self) -> None:
        self.assertTrue(check_path(".env.local"))
        self.assertFalse(check_path(".env.example"))

    def test_allows_application_template_html(self) -> None:
        self.assertFalse(check_path("ats_resume_coach/web/templates/index.html"))

    def test_blocks_job_capture_html_elsewhere(self) -> None:
        self.assertTrue(check_path("samples/job-posting.html"))


if __name__ == "__main__":
    unittest.main()

