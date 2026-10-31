from __future__ import annotations

import shutil
import threading
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .base64io import write_inputs
from .codex_service import run_codex_stl
from .config import settings
from .image_service import generate_views
from .jobs import JobStore, utc_now
from .schemas import (
    DEFAULT_CODEX_MODEL,
    GenerateRequest,
    GenerateResponse,
    JobStatusResponse,
    JobSubmission,
    Mode,
    UsageSummary,
)

job_store = JobStore(settings.job_root / "_status")
job_worker = threading.Semaphore(1)

app = FastAPI(
    title="Codex 3D Artifact API",
    version="0.1.0",
    description="Base64 in/out API for six-view 3D renders and Codex-driven printable STL reconstruction.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["content-type", "authorization"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "image_backend": "codex_builtin_imagegen",
        "default_codex_model": DEFAULT_CODEX_MODEL,
    }


def _authorize(x_api_key: str | None) -> None:
    if settings.service_api_key and x_api_key != settings.service_api_key:
        raise HTTPException(401, "invalid X-API-Key")


def _execute(request: GenerateRequest, request_id: str, job_dir: Path) -> GenerateResponse:
    input_dir = job_dir / "input"
    job_dir.mkdir(parents=True, exist_ok=False)
    input_paths = write_inputs(request.images, input_dir, settings.max_input_bytes)
    if request.mode == Mode.RENDER_3D_VIEWS:
        artifacts, image_tokens, warnings = generate_views(
            request, input_paths, job_dir / "output", settings
        )
        usage = UsageSummary(codex=image_tokens, total_tokens=image_tokens.total_tokens)
        return GenerateResponse(
            request_id=request_id,
            mode=request.mode,
            summary=f"Generated {len(artifacts)} consistent 3D reference views.",
            artifacts=artifacts,
            usage=usage,
            warnings=warnings,
        )

    artifacts, codex_tokens, result, dimensions, thread_id = run_codex_stl(
        request, input_paths, job_dir, settings
    )
    usage = UsageSummary(codex=codex_tokens, total_tokens=codex_tokens.total_tokens)
    warnings = list(result.get("warnings", []))
    if codex_tokens.total_tokens == 0:
        warnings.append("This Codex CLI/provider did not expose token usage in JSONL events.")
    return GenerateResponse(
        request_id=request_id,
        mode=request.mode,
        summary=result["summary"],
        classification=result["classification"],
        dimensions_mm={
            "width": float(dimensions["width"]),
            "depth": float(dimensions["depth"]),
            "height": float(dimensions["height"]),
        },
        artifacts=artifacts,
        usage=usage,
        warnings=warnings,
        codex_thread_id=thread_id,
    )


@app.post("/v1/generate", response_model=GenerateResponse)
def generate(request: GenerateRequest, x_api_key: str | None = Header(None)) -> GenerateResponse:
    _authorize(x_api_key)
    request_id = uuid.uuid4().hex
    job_dir = settings.job_root / request_id
    try:
        return _execute(request, request_id, job_dir)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"unhandled job error: {exc}") from exc
    finally:
        if not settings.keep_jobs:
            shutil.rmtree(job_dir, ignore_errors=True)


def _run_job(request: GenerateRequest, job_id: str) -> None:
    job_dir = settings.job_root / job_id
    with job_worker:
        job_store.update(job_id, status="running", stage="codex_running", started_at=utc_now())
        try:
            response = _execute(request, job_id, job_dir)
            job_store.write_result(job_id, response.model_dump(mode="json"))
            job_store.update(
                job_id,
                status="completed",
                stage="result_ready",
                completed_at=utc_now(),
            )
        except HTTPException as exc:
            job_store.update(
                job_id,
                status="failed",
                stage="failed",
                error=str(exc.detail),
                completed_at=utc_now(),
            )
        except Exception as exc:
            job_store.update(
                job_id,
                status="failed",
                stage="failed",
                error=f"unhandled job error: {exc}",
                completed_at=utc_now(),
            )
        finally:
            if not settings.keep_jobs:
                shutil.rmtree(job_dir, ignore_errors=True)


@app.post("/v1/jobs", status_code=202, response_model=JobSubmission)
def submit_job(
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
    x_api_key: str | None = Header(None),
) -> JobSubmission:
    _authorize(x_api_key)
    job_id = uuid.uuid4().hex
    job_store.create(job_id, request.mode.value)
    background_tasks.add_task(_run_job, request, job_id)
    return JobSubmission(
        job_id=job_id,
        status_url=f"/v1/jobs/{job_id}",
        result_url=f"/v1/jobs/{job_id}/result",
    )


@app.get("/v1/jobs/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str, x_api_key: str | None = Header(None)) -> JobStatusResponse:
    _authorize(x_api_key)
    value = job_store.read(job_id)
    if value is None:
        raise HTTPException(404, "job not found")
    return JobStatusResponse.model_validate(value)


@app.get("/v1/jobs/{job_id}/result", response_model=GenerateResponse)
def get_job_result(job_id: str, x_api_key: str | None = Header(None)):
    _authorize(x_api_key)
    status = job_store.read(job_id)
    if status is None:
        raise HTTPException(404, "job not found")
    if status["status"] == "failed":
        raise HTTPException(409, status.get("error") or "job failed")
    if status["status"] != "completed":
        return JSONResponse(status_code=202, content=status)
    result = job_store.read_result(job_id)
    if result is None:
        raise HTTPException(500, "completed job result is missing")
    return GenerateResponse.model_validate(result)


def run() -> None:
    import uvicorn

    settings.job_root.mkdir(parents=True, exist_ok=True)
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    run()

