from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    return default if value is None else value.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    service_api_key: str | None = os.getenv("SERVICE_API_KEY")
    codex_bin: str = os.getenv("CODEX_BIN", "codex")
    job_root: Path = Path(os.getenv("JOB_ROOT", "./var/jobs")).resolve()
    job_timeout_seconds: int = int(os.getenv("JOB_TIMEOUT_SECONDS", "1800"))
    max_input_bytes: int = int(os.getenv("MAX_INPUT_BYTES", str(50 * 1024 * 1024)))
    max_artifact_bytes: int = int(os.getenv("MAX_ARTIFACT_BYTES", str(64 * 1024 * 1024)))
    keep_jobs: bool = _bool("KEEP_JOBS", False)


settings = Settings()

