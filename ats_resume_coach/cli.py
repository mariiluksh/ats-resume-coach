"""Command-line interface."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .analyzer import ResumeAnalyzer
from .ingest import fetch_url_text, read_file_text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ats-resume-coach")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve_parser = subparsers.add_parser("serve", help="Run the local web service.")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)

    analyze_parser = subparsers.add_parser("analyze", help="Analyze a resume against a job.")
    job_group = analyze_parser.add_mutually_exclusive_group(required=True)
    job_group.add_argument("--job-file", type=Path)
    job_group.add_argument("--job-url")
    job_group.add_argument("--job-text")
    resume_group = analyze_parser.add_mutually_exclusive_group(required=True)
    resume_group.add_argument("--resume-file", type=Path)
    resume_group.add_argument("--resume-text")
    analyze_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")

    args = parser.parse_args(argv)

    if args.command == "serve":
        return _serve(args.host, args.port)
    if args.command == "analyze":
        return _analyze(args)
    parser.error("Unknown command.")
    return 2


def _serve(host: str, port: int) -> int:
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "ats_resume_coach.api:app",
        "--host",
        host,
        "--port",
        str(port),
        "--reload",
    ]
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

    result = ResumeAnalyzer().analyze(job_text, resume_text)
    indent = 2 if args.pretty else None
    print(json.dumps(result.to_dict(), indent=indent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

