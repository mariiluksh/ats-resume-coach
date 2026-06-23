# ATS Resume Coach

Open-source ATS resume critique service for intern and entry-level candidates.

The app accepts a job vacancy and a trainee resume, extracts text, compares role requirements against the resume, and returns an ATS-focused score with prioritized fixes.
It also generates a tailored resume draft you can download after review.

## Privacy model

This repository is designed to be public. Private datasets and user documents stay local.

Never commit:

- `job_training_dataset_v1 (1).parquet`
- `cv-train.zip`
- extracted resumes
- uploaded resumes or vacancy files
- generated model artifacts
- `.env.local`

Only process resumes you own or have explicit permission to use. The app does not require a resume training corpus to run.

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
# Optional. Use only resumes you have permission to process.
ATS_AUTHORIZED_RESUME_ZIP=/absolute/path/to/authorized-resumes.zip
ATS_MODEL_DIR=./models
```

`.env.local`, `data/`, and `models/` are ignored by git.

## Analyze from CLI

```bash
python -m ats_resume_coach.cli analyze \
  --job-file path/to/job.txt \
  --resume-file path/to/resume.pdf
```

To generate a tailored draft file from the CLI:

```bash
python -m ats_resume_coach.cli rewrite \
  --job-file path/to/job.txt \
  --resume-file path/to/resume.pdf \
  --output tailored_resume_draft.docx
```

In the web app, use the `Rewrite and download` button after entering the vacancy and resume.

## Optional local profile training

This command reads private local datasets and writes ignored model artifacts under `models/`:

```bash
python -m ats_resume_coach.cli train-profile \
  --jobs-parquet "$ATS_JOB_PARQUET" \
  --authorized-resume-zip "$ATS_AUTHORIZED_RESUME_ZIP" \
  --output models/local_keyword_profile.json
```

Do not commit files from `models/`.

## Local TF-IDF model training

For a stronger local baseline, train a private TF-IDF model from the job parquet:

```bash
python -m ats_resume_coach.cli train-model \
  --jobs-parquet "$ATS_JOB_PARQUET" \
  --output-dir models/local_tfidf
```

This writes `models/local_tfidf/tfidf_model.joblib` and `models/local_tfidf/metadata.json`. Both are ignored because trained artifacts are derived from private data.

When `models/local_tfidf/` exists, the CLI and web/API analyzer load it automatically and include local model cluster signals in the result.

Resume corpora are optional and require an explicit consent flag:

```bash
python -m ats_resume_coach.cli train-model \
  --jobs-parquet "$ATS_JOB_PARQUET" \
  --authorized-resume-zip "$ATS_AUTHORIZED_RESUME_ZIP" \
  --confirm-resume-consent \
  --output-dir models/local_tfidf
```

Use `--authorized-resume-zip` only for resumes you own or have explicit permission to process.
