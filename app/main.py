from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .base64io import write_inputs
from .codex_service import run_codex_stl
from .config import settings
from .image_service import generate_views
from .schemas import (
    DEFAULT_CODEX_MODEL,
    GenerateRequest,
    GenerateResponse,
    Mode,
    UsageSummary,
)

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


@app.post("/v1/generate", response_model=GenerateResponse)
def generate(request: GenerateRequest, x_api_key: str | None = Header(None)) -> GenerateResponse:
    _authorize(x_api_key)
    request_id = uuid.uuid4().hex
    job_dir = settings.job_root / request_id
    input_dir = job_dir / "input"
    job_dir.mkdir(parents=True, exist_ok=False)
    try:
        input_paths = write_inputs(request.images, input_dir, settings.max_input_bytes)
        if request.mode == Mode.RENDER_3D_VIEWS:
            artifacts, image_tokens, warnings = generate_views(
                request, input_paths, job_dir / "output", settings
            )
            usage = UsageSummary(codex=image_tokens, total_tokens=image_tokens.total_tokens)
            response = GenerateResponse(
                request_id=request_id,
                mode=request.mode,
                summary=f"Generated {len(artifacts)} consistent 3D reference views.",
                artifacts=artifacts,
                usage=usage,
                warnings=warnings,
            )
        else:
            artifacts, codex_tokens, result, dimensions, thread_id = run_codex_stl(
                request, input_paths, job_dir, settings
            )
            usage = UsageSummary(codex=codex_tokens, total_tokens=codex_tokens.total_tokens)
            warnings = list(result.get("warnings", []))
            if codex_tokens.total_tokens == 0:
                warnings.append("This Codex CLI/provider did not expose token usage in JSONL events.")
            response = GenerateResponse(
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
        return response
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"unhandled job error: {exc}") from exc
    finally:
        if not settings.keep_jobs:
            shutil.rmtree(job_dir, ignore_errors=True)


def run() -> None:
    import uvicorn

    settings.job_root.mkdir(parents=True, exist_ok=True)
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    run()

