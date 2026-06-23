"""FastAPI application for ATS Resume Coach."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .analyzer import ResumeAnalyzer
from .ingest import IngestError, extract_text_from_bytes, fetch_url_text


PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(PACKAGE_DIR / "web" / "templates"))


def create_app() -> FastAPI:
    app = FastAPI(
        title="ATS Resume Coach",
        description="ATS resume critique service for intern and entry-level candidates.",
        version="0.1.0",
    )
    app.mount(
        "/static",
        StaticFiles(directory=str(PACKAGE_DIR / "web" / "static")),
        name="static",
    )

    analyzer = ResumeAnalyzer()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse("index.html", {"request": request, "result": None, "error": None})

    @app.post("/api/analyze")
    async def analyze_api(
        job_url: Annotated[str | None, Form()] = None,
        job_text: Annotated[str | None, Form()] = None,
        resume_text: Annotated[str | None, Form()] = None,
        job_file: Annotated[UploadFile | None, File()] = None,
        resume_file: Annotated[UploadFile | None, File()] = None,
    ) -> dict:
        try:
            result = analyzer.analyze(
                await _resolve_job_text(job_url=job_url, job_text=job_text, job_file=job_file),
                await _resolve_resume_text(resume_text=resume_text, resume_file=resume_file),
            )
        except (ValueError, IngestError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return result.to_dict()

    @app.post("/analyze", response_class=HTMLResponse)
    async def analyze_html(
        request: Request,
        job_url: Annotated[str | None, Form()] = None,
        job_text: Annotated[str | None, Form()] = None,
        resume_text: Annotated[str | None, Form()] = None,
        job_file: Annotated[UploadFile | None, File()] = None,
        resume_file: Annotated[UploadFile | None, File()] = None,
    ) -> HTMLResponse:
        try:
            result = analyzer.analyze(
                await _resolve_job_text(job_url=job_url, job_text=job_text, job_file=job_file),
                await _resolve_resume_text(resume_text=resume_text, resume_file=resume_file),
            )
            return TEMPLATES.TemplateResponse(
                "index.html",
                {"request": request, "result": result.to_dict(), "error": None},
            )
        except (ValueError, IngestError) as exc:
            return TEMPLATES.TemplateResponse(
                "index.html",
                {"request": request, "result": None, "error": str(exc)},
                status_code=400,
            )

    return app


async def _resolve_job_text(
    *,
    job_url: str | None,
    job_text: str | None,
    job_file: UploadFile | None,
) -> str:
    if job_file and job_file.filename:
        return await _read_upload(job_file)
    if job_text and job_text.strip():
        return job_text
    if job_url and job_url.strip():
        return fetch_url_text(job_url.strip())
    raise ValueError("Provide a job URL, job file, or pasted job text.")


async def _resolve_resume_text(*, resume_text: str | None, resume_file: UploadFile | None) -> str:
    if resume_file and resume_file.filename:
        return await _read_upload(resume_file)
    if resume_text and resume_text.strip():
        return resume_text
    raise ValueError("Provide a resume file or pasted resume text.")


async def _read_upload(upload: UploadFile) -> str:
    content = await upload.read()
    if not content:
        raise IngestError(f"Uploaded file is empty: {upload.filename}")
    if len(content) > 8 * 1024 * 1024:
        raise IngestError("Uploaded files must be 8 MB or smaller.")
    return extract_text_from_bytes(
        content,
        filename=upload.filename or "",
        content_type=upload.content_type or "",
    )


app = create_app()

