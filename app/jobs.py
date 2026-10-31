from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    def __init__(self, directory: Path):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _status_path(self, job_id: str) -> Path:
        return self.directory / f"{job_id}.status.json"

    def _result_path(self, job_id: str) -> Path:
        return self.directory / f"{job_id}.result.json"

    @staticmethod
    def _atomic_write(path: Path, value: dict[str, Any]) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)

    def create(self, job_id: str, mode: str) -> dict[str, Any]:
        value = {
            "job_id": job_id,
            "mode": mode,
            "status": "queued",
            "stage": "waiting_for_worker",
            "created_at": utc_now(),
            "started_at": None,
            "completed_at": None,
            "error": None,
        }
        with self._lock:
            self._atomic_write(self._status_path(job_id), value)
        return value

    def read(self, job_id: str) -> dict[str, Any] | None:
        path = self._status_path(job_id)
        if not path.is_file():
            return None
        with self._lock:
            return json.loads(path.read_text(encoding="utf-8"))

    def update(self, job_id: str, **changes: Any) -> dict[str, Any]:
        with self._lock:
            path = self._status_path(job_id)
            value = json.loads(path.read_text(encoding="utf-8"))
            value.update(changes)
            self._atomic_write(path, value)
        return value

    def write_result(self, job_id: str, value: dict[str, Any]) -> None:
        with self._lock:
            self._atomic_write(self._result_path(job_id), value)

    def read_result(self, job_id: str) -> dict[str, Any] | None:
        path = self._result_path(job_id)
        if not path.is_file():
            return None
        with self._lock:
            return json.loads(path.read_text(encoding="utf-8"))
