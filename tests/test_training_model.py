from __future__ import annotations

import unittest

from ats_resume_coach.training.model import (
    LocalTrainingError,
    _selected_text_columns,
    train_local_tfidf_model_from_paths,
)


class TrainingModelTest(unittest.TestCase):
    def test_resume_zip_requires_explicit_consent_flag(self) -> None:
        with self.assertRaises(LocalTrainingError):
            train_local_tfidf_model_from_paths(
                jobs_parquet="missing.parquet",
                authorized_resume_zip="resumes.zip",
                output_dir="models/test",
            )

    def test_selects_rich_job_columns(self) -> None:
        columns = [
            "company",
            "title",
            "description",
            "job_technologies",
            "labeled_disciplines",
        ]

        selected = _selected_text_columns(columns)

        self.assertEqual(
            selected,
            ["title", "description", "labeled_disciplines", "job_technologies"],
        )


if __name__ == "__main__":
    unittest.main()

