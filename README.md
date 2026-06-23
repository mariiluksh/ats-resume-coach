# ATS Resume Coach

Open-source ATS resume critique service for intern and entry-level candidates.

The app accepts a job vacancy and a trainee resume, extracts text, compares role requirements against the resume, and returns an ATS-focused score with prioritized fixes.

## Privacy model

This repository is designed to be public. Private datasets and user documents stay local.

Never commit:

- `job_training_dataset_v1 (1).parquet`
- `cv-train.zip`
- extracted resumes
- uploaded resumes or vacancy files
- generated model artifacts
- `.env.local`

The repo includes `.gitignore` and a pre-commit privacy check to block common mistakes, but you should still review `git status` before every push.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m ats_resume_coach.cli serve
```

Then open `http://127.0.0.1:8000`.

## Local dataset setup

Copy `.env.example` to `.env.local` and point it to private local data:

```bash
ATS_JOB_PARQUET=/absolute/path/to/job_training_dataset_v1.parquet
ATS_RESUME_ZIP=/absolute/path/to/cv-train.zip
ATS_MODEL_DIR=./models
```

`.env.local`, `data/`, and `models/` are ignored by git.

## Analyze from CLI

```bash
python -m ats_resume_coach.cli analyze \
  --job-file path/to/job.txt \
  --resume-file path/to/resume.pdf
```

## Optional local profile training

This command reads private local datasets and writes ignored model artifacts under `models/`:

```bash
python -m ats_resume_coach.cli train-profile \
  --jobs-parquet "$ATS_JOB_PARQUET" \
  --resume-zip "$ATS_RESUME_ZIP" \
  --output models/local_keyword_profile.json
```

Do not commit files from `models/`.

