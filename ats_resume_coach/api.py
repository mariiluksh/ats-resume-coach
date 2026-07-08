"""FastAPI application for ATS Resume Coach."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from secrets import token_urlsafe
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .analyzer import ResumeAnalyzer
from .config import default_model_dir
from .ingest import IngestError, extract_text_from_bytes, fetch_url_text
from .local_model import load_optional_local_model
from .rewriter import build_resume_draft


PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(PACKAGE_DIR / "web" / "templates"))
EMPTY_FORM = {"job_url": "", "job_text": "", "resume_text": "", "resume_source_token": ""}
MAX_SOURCE_CACHE_ITEMS = 20


@dataclass(frozen=True)
class ResumeSource:
    text: str
    docx_bytes: bytes | None = None
    filename: str | None = None
    content_type: str | None = None


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

    analyzer = ResumeAnalyzer(local_model=load_optional_local_model(default_model_dir() / "local_tfidf"))
    resume_source_cache: dict[str, ResumeSource] = {}

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(
            request,
            "index.html",
            {"result": None, "error": None, "form": EMPTY_FORM},
        )

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
        resume_source_token: Annotated[str | None, Form()] = None,
    ) -> HTMLResponse:
        try:
            resolved_job_text = await _resolve_job_text(job_url=job_url, job_text=job_text, job_file=job_file)
            resolved_resume = await _resolve_resume_source(
                resume_text=resume_text,
                resume_file=resume_file,
                resume_source_token=resume_source_token,
                resume_source_cache=resume_source_cache,
            )
            new_resume_source_token = _cache_resume_source(resolved_resume, resume_source_cache)
            result = analyzer.analyze(resolved_job_text, resolved_resume.text)
            return TEMPLATES.TemplateResponse(
                request,
                "index.html",
                {
                    "result": result.to_dict(),
                    "error": None,
                    "form": _form_state(
                        job_url=job_url,
                        job_text=job_text,
                        resume_text=resume_text,
                        resolved_job_text=resolved_job_text,
                        resolved_resume_text=resolved_resume.text,
                        resume_source_token=new_resume_source_token or resume_source_token,
                    ),
                },
            )
        except (ValueError, IngestError) as exc:
            return TEMPLATES.TemplateResponse(
                request,
                "index.html",
                {
                    "result": None,
                    "error": str(exc),
                    "form": _form_state(
                        job_url=job_url,
                        job_text=job_text,
                        resume_text=resume_text,
                        resume_source_token=resume_source_token,
                    ),
                },
                status_code=400,
            )
        except Exception as exc:
            return TEMPLATES.TemplateResponse(
                request,
                "index.html",
                {
                    "result": None,
                    "error": f"Unexpected error while processing the resume: {exc}",
                    "form": _form_state(
                        job_url=job_url,
                        job_text=job_text,
                        resume_text=resume_text,
                        resume_source_token=resume_source_token,
                    ),
                },
                status_code=500,
            )

    @app.post("/rewrite")
    async def rewrite_resume(
        request: Request,
        job_url: Annotated[str | None, Form()] = None,
        job_text: Annotated[str | None, Form()] = None,
        resume_text: Annotated[str | None, Form()] = None,
        job_file: Annotated[UploadFile | None, File()] = None,
        resume_file: Annotated[UploadFile | None, File()] = None,
        resume_source_token: Annotated[str | None, Form()] = None,
    ) -> Response:
        try:
            resolved_job_text = await _resolve_job_text(job_url=job_url, job_text=job_text, job_file=job_file)
            resolved_resume = await _resolve_resume_source(
                resume_text=resume_text,
                resume_file=resume_file,
                resume_source_token=resume_source_token,
                resume_source_cache=resume_source_cache,
            )
            analysis = analyzer.analyze(resolved_job_text, resolved_resume.text)
            draft = build_resume_draft(
                resolved_job_text,
                resolved_resume.text,
                analysis,
                source_docx=resolved_resume.docx_bytes,
                source_filename=resolved_resume.filename,
            )
        except (ValueError, IngestError) as exc:
            return TEMPLATES.TemplateResponse(
                request,
                "index.html",
                {
                    "result": None,
                    "error": str(exc),
                    "form": _form_state(
                        job_url=job_url,
                        job_text=job_text,
                        resume_text=resume_text,
                        resume_source_token=resume_source_token,
                    ),
                },
                status_code=400,
            )
        except Exception as exc:
            return TEMPLATES.TemplateResponse(
                request,
                "index.html",
                {
                    "result": None,
                    "error": f"Unexpected error while rewriting the resume: {exc}",
                    "form": _form_state(
                        job_url=job_url,
                        job_text=job_text,
                        resume_text=resume_text,
                        resume_source_token=resume_source_token,
                    ),
                },
                status_code=500,
            )

        headers = {"Content-Disposition": f'attachment; filename="{draft.filename}"'}
        return Response(content=draft.data, media_type=draft.content_type, headers=headers)

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


async def _resolve_resume_source(
    *,
    resume_text: str | None,
    resume_file: UploadFile | None,
    resume_source_token: str | None,
    resume_source_cache: dict[str, ResumeSource],
) -> ResumeSource:
    if resume_file and resume_file.filename:
        content = await _read_upload_bytes(resume_file)
        filename = resume_file.filename or ""
        content_type = resume_file.content_type or ""
        text = extract_text_from_bytes(content, filename=filename, content_type=content_type)
        if _is_docx_upload(filename, content_type):
            return ResumeSource(text=text, docx_bytes=content, filename=filename, content_type=content_type)
        return ResumeSource(text=text, filename=filename, content_type=content_type)

    cached = resume_source_cache.get(resume_source_token or "")
    if cached and cached.docx_bytes:
        return ResumeSource(
            text=resume_text if resume_text and resume_text.strip() else cached.text,
            docx_bytes=cached.docx_bytes,
            filename=cached.filename,
            content_type=cached.content_type,
        )

    if resume_text and resume_text.strip():
        return ResumeSource(text=resume_text)
    raise ValueError("Provide a resume file or pasted resume text.")


async def _read_upload(upload: UploadFile) -> str:
    content = await _read_upload_bytes(upload)
    return extract_text_from_bytes(
        content,
        filename=upload.filename or "",
        content_type=upload.content_type or "",
    )


async def _read_upload_bytes(upload: UploadFile) -> bytes:
    content = await upload.read()
    if not content:
        raise IngestError(f"Uploaded file is empty: {upload.filename}")
    if len(content) > 8 * 1024 * 1024:
        raise IngestError("Uploaded files must be 8 MB or smaller.")
    return content


def _is_docx_upload(filename: str, content_type: str) -> bool:
    return Path(filename).suffix.lower() == ".docx" or "wordprocessingml" in content_type


def _cache_resume_source(source: ResumeSource, cache: dict[str, ResumeSource]) -> str:
    if not source.docx_bytes:
        return ""
    while len(cache) >= MAX_SOURCE_CACHE_ITEMS:
        cache.pop(next(iter(cache)))
    token = token_urlsafe(18)
    cache[token] = source
    return token


def _form_state(
    *,
    job_url: str | None,
    job_text: str | None,
    resume_text: str | None,
    resolved_job_text: str | None = None,
    resolved_resume_text: str | None = None,
    resume_source_token: str | None = None,
) -> dict[str, str]:
    return {
        "job_url": job_url or "",
        "job_text": resolved_job_text if resolved_job_text and not (job_text or "").strip() else job_text or "",
        "resume_text": (
            resolved_resume_text
            if resolved_resume_text and not (resume_text or "").strip()
            else resume_text or ""
        ),
        "resume_source_token": resume_source_token or "",
    }


app = create_app()
