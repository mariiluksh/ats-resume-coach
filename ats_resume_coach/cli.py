"""Command-line interface."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from .analyzer import ResumeAnalyzer
from .config import AUTHORIZED_RESUME_ZIP_ENV, JOB_PARQUET_ENV, default_model_dir, env_path
from .ingest import fetch_url_text, read_file_text
from .local_model import load_optional_local_model


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ats-resume-coach")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve_parser = subparsers.add_parser("serve", help="Run the local web service.")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument("--reload", action="store_true", help="Restart the server when source files change.")

    analyze_parser = subparsers.add_parser("analyze", help="Analyze a resume against a job.")
    job_group = analyze_parser.add_mutually_exclusive_group(required=True)
    job_group.add_argument("--job-file", type=Path)
    job_group.add_argument("--job-url")
    job_group.add_argument("--job-text")
    resume_group = analyze_parser.add_mutually_exclusive_group(required=True)
    resume_group.add_argument("--resume-file", type=Path)
    resume_group.add_argument("--resume-text")
    analyze_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")

    train_parser = subparsers.add_parser(
        "train-profile",
        help="Build a local aggregate keyword profile from private datasets.",
    )
    train_parser.add_argument("--jobs-parquet", type=Path, default=env_path(JOB_PARQUET_ENV))
    train_parser.add_argument(
        "--authorized-resume-zip",
        type=Path,
        default=env_path(AUTHORIZED_RESUME_ZIP_ENV),
        help="Optional zip of resumes you have permission to process.",
    )
    train_parser.add_argument("--output", type=Path, default=default_model_dir() / "local_keyword_profile.json")
    train_parser.add_argument("--limit-jobs", type=int, default=5000)
    train_parser.add_argument("--limit-resumes", type=int, default=1000)
    train_parser.add_argument("--top-n", type=int, default=120)

    model_parser = subparsers.add_parser(
        "train-model",
        help="Train a local private TF-IDF model from job data and optional authorized resumes.",
    )
    model_parser.add_argument("--jobs-parquet", type=Path, default=env_path(JOB_PARQUET_ENV))
    model_parser.add_argument(
        "--authorized-resume-zip",
        type=Path,
        default=env_path(AUTHORIZED_RESUME_ZIP_ENV),
        help="Optional zip of resumes you own or have explicit permission to process.",
    )
    model_parser.add_argument(
        "--confirm-resume-consent",
        action="store_true",
        help="Required before processing any resume zip.",
    )
    model_parser.add_argument("--output-dir", type=Path, default=default_model_dir() / "local_tfidf")
    model_parser.add_argument("--limit-jobs", type=int)
    model_parser.add_argument("--limit-resumes", type=int, default=1000)
    model_parser.add_argument("--max-features", type=int, default=20000)
    model_parser.add_argument("--min-df", type=int, default=3)
    model_parser.add_argument("--clusters", type=int, default=12)

    rewrite_parser = subparsers.add_parser(
        "rewrite",
        help="Generate a tailored resume draft as a docx file.",
    )
    rewrite_job_group = rewrite_parser.add_mutually_exclusive_group(required=True)
    rewrite_job_group.add_argument("--job-file", type=Path)
    rewrite_job_group.add_argument("--job-url")
    rewrite_job_group.add_argument("--job-text")
    rewrite_resume_group = rewrite_parser.add_mutually_exclusive_group(required=True)
    rewrite_resume_group.add_argument("--resume-file", type=Path)
    rewrite_resume_group.add_argument("--resume-text")
    rewrite_parser.add_argument("--output", type=Path, default=Path("tailored_resume_draft.docx"))

    args = parser.parse_args(argv)

    if args.command == "serve":
        return _serve(args.host, args.port, reload=args.reload)
    if args.command == "analyze":
        return _analyze(args)
    if args.command == "train-profile":
        return _train_profile(args)
    if args.command == "train-model":
        return _train_model(args)
    if args.command == "rewrite":
        return _rewrite(args)
    parser.error("Unknown command.")
    return 2


def _serve(host: str, port: int, *, reload: bool) -> int:
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "ats_resume_coach.api:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    if reload:
        command.append("--reload")
    return subprocess.call(command)


def _analyze(args: argparse.Namespace) -> int:
    if args.job_file:
        job_text = read_file_text(args.job_file)
    elif args.job_url:
        job_text = fetch_url_text(args.job_url)
    else:
        job_text = args.job_text

    if args.resume_file:
        resume_text = read_file_text(args.resume_file)
    else:
        resume_text = args.resume_text

    local_model = load_optional_local_model(default_model_dir() / "local_tfidf")
    result = ResumeAnalyzer(local_model=local_model).analyze(job_text, resume_text)
    indent = 2 if args.pretty else None
    print(json.dumps(result.to_dict(), indent=indent))
    return 0


def _train_profile(args: argparse.Namespace) -> int:
    if not args.jobs_parquet:
        raise SystemExit(f"Missing --jobs-parquet or {JOB_PARQUET_ENV}.")
    from .training.profile import train_profile_from_paths

    output = train_profile_from_paths(
        jobs_parquet=args.jobs_parquet,
        authorized_resume_zip=args.authorized_resume_zip,
        output=args.output,
        limit_jobs=args.limit_jobs,
        limit_resumes=args.limit_resumes,
        top_n=args.top_n,
    )
    print(f"Wrote local keyword profile to {output}")
    return 0


def _train_model(args: argparse.Namespace) -> int:
    if not args.jobs_parquet:
        raise SystemExit(f"Missing --jobs-parquet or {JOB_PARQUET_ENV}.")
    from .training.model import train_local_tfidf_model_from_paths

    summary = train_local_tfidf_model_from_paths(
        jobs_parquet=args.jobs_parquet,
        authorized_resume_zip=args.authorized_resume_zip,
        confirm_resume_consent=args.confirm_resume_consent,
        output_dir=args.output_dir,
        limit_jobs=args.limit_jobs,
        limit_resumes=args.limit_resumes,
        max_features=args.max_features,
        min_df=args.min_df,
        clusters=args.clusters,
    )
    print(json.dumps(asdict(summary), indent=2))
    return 0


def _rewrite(args: argparse.Namespace) -> int:
    source_docx = None
    source_filename = None
    if args.job_file:
        job_text = read_file_text(args.job_file)
    elif args.job_url:
        job_text = fetch_url_text(args.job_url)
    else:
        job_text = args.job_text

    if args.resume_file:
        resume_text = read_file_text(args.resume_file)
        source_filename = args.resume_file.name
        if args.resume_file.suffix.lower() == ".docx":
            source_docx = args.resume_file.read_bytes()
    else:
        resume_text = args.resume_text

    local_model = load_optional_local_model(default_model_dir() / "local_tfidf")
    analysis = ResumeAnalyzer(local_model=local_model).analyze(job_text, resume_text)
    from .rewriter import build_resume_draft

    draft = build_resume_draft(
        job_text,
        resume_text,
        analysis,
        source_docx=source_docx,
        source_filename=source_filename,
    )
    args.output.write_bytes(draft.data)
    print(f"Wrote tailored resume draft to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
