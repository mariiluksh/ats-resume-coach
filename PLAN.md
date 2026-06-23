# ATS Resume Coach Plan

## Goal

Build an open-source service that accepts a job vacancy and an intern/entry-level resume, then returns ATS-focused critique and concrete improvement recommendations. The service must be publishable to GitHub without exposing private datasets, resumes, job exports, extracted documents, model files, or local paths.

## Privacy boundary

- Public repo: source code, tests, docs, UI templates, dependency metadata, privacy checks, empty data/model placeholders.
- Local-only: `job_training_dataset_v1 (1).parquet`, `cv-train.zip`, extracted resumes, uploaded resumes, job HTML/PDF captures, generated model artifacts, local `.env.*` files.
- Guardrails:
  - `.gitignore` blocks raw data directories, model artifacts, document formats, parquet/zip exports, CSV/JSONL dumps, and local env files.
  - A pre-commit privacy check blocks staged files from sensitive directories, risky extensions, and large files.
  - The app processes user uploads in memory and does not persist them by default.

## Product flow

1. User provides a job vacancy as URL, pasted text, HTML/PDF/TXT upload, or saved file.
2. User provides a trainee resume as PDF/DOCX/TXT/HTML upload or pasted text.
3. The service extracts text, normalizes it, and identifies:
   - job role signals,
   - required skills and tools,
   - missing resume keywords,
   - ATS formatting risks,
   - weak or vague bullets,
   - missing sections/contact basics,
   - intern-friendly project/education opportunities.
4. The service returns:
   - overall ATS readiness score,
   - score breakdown,
   - prioritized critique items,
   - missing keywords/skills,
   - rewrite suggestions and bullet templates,
   - a compact JSON API response for integrations.

## Implementation steps

1. Repository setup
   - Create isolated folder `ats-resume-coach`.
   - Add privacy-first `.gitignore`, `.env.example`, ignored `.env.local`, and empty `data/`/`models/` placeholders.
   - Initialize a separate Git repo after the guardrails exist.

2. Core analyzer
   - Build deterministic, dependency-light text normalization and keyword extraction.
   - Add intern-oriented skill taxonomy.
   - Score resume/job match across keywords, skills, sections, contact basics, formatting, and bullet quality.
   - Return structured results suitable for API/UI/CLI.

3. Service layer
   - Add FastAPI app with:
     - `GET /` web form,
     - `POST /analyze` HTML response,
     - `POST /api/analyze` JSON response,
     - health endpoint.
   - Support job URL fetch and text extraction from PDF, DOCX, HTML, and plain text.
   - Keep uploads in memory; no default persistence.

4. Local data/training tools
   - Add local-only readers for the parquet job export and resume zip.
   - Add optional baseline profile trainer using TF-IDF/keyphrase extraction.
   - Save outputs under ignored `models/`.
   - Avoid committing any trained artifacts or derived private examples.

5. CLI and documentation
   - Add CLI commands for local analysis and optional profile training.
   - Document setup, privacy model, local dataset usage, and GitHub publishing flow.

6. Verification
   - Add unit tests for scoring and privacy guard behavior.
   - Run tests locally.
   - Install the pre-commit hook in the new repo.

7. GitHub
   - Make logical local commits.
   - Create a new GitHub repo, not connected to any existing project.
   - Push only the sanitized repository.
   - If GitHub auth is unavailable, leave local commits ready and document the exact next command.

## Initial limitations

- The first version uses deterministic analysis and optional local TF-IDF profiling, not neural network training.
- The app does not scrape authenticated job boards. Job URL fetches work for publicly accessible pages.
- Recommendations are coaching-oriented; the user should review all wording before sending applications.

