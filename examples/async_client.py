#!/usr/bin/env python3
"""Submit a Base64 job, poll by job ID, and download completed artifacts."""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def call(url: str, *, method: str, payload=None):
    headers = {"Content-Type": "application/json"}
    if os.getenv("SERVICE_API_KEY"):
        headers["X-API-Key"] = os.environ["SERVICE_API_KEY"]
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=3600) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code} {exc.reason}: {detail}") from None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["render_3d_views", "reconstruct_stl"])
    parser.add_argument("images", nargs="+", type=Path)
    parser.add_argument("--requirement", required=True)
    parser.add_argument("--height", type=float)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, default=Path("async_output"))
    parser.add_argument("--poll-interval", type=float, default=5.0)
    parser.add_argument("--codex-model", default="gpt-5.6-sol")
    args = parser.parse_args()

    images = []
    for path in args.images:
        mime = mimetypes.guess_type(path.name)[0] or "image/png"
        if mime not in {"image/png", "image/jpeg", "image/webp"}:
            raise SystemExit(f"Unsupported image type: {path}")
        images.append({
            "mime_type": mime,
            "data_base64": base64.b64encode(path.read_bytes()).decode("ascii"),
        })

    payload = {
        "mode": args.mode,
        "codex_model": args.codex_model,
        "images": images,
        "requirement": args.requirement,
    }
    if args.mode == "reconstruct_stl":
        if not args.height:
            raise SystemExit("--height is required for reconstruct_stl")
        payload["dimensions_mm"] = {
            "height": args.height,
            "preserve_reference_proportions": True,
        }

    base_url = args.url.rstrip("/")
    _, submitted = call(f"{base_url}/v1/jobs", method="POST", payload=payload)
    job_id = submitted["job_id"]
    print(json.dumps(submitted, ensure_ascii=False, indent=2), flush=True)

    while True:
        _, status = call(f"{base_url}/v1/jobs/{job_id}", method="GET")
        print(json.dumps({
            "job_id": job_id,
            "status": status["status"],
            "stage": status["stage"],
            "error": status.get("error"),
        }, ensure_ascii=False), flush=True)
        if status["status"] == "completed":
            break
        if status["status"] == "failed":
            raise SystemExit(status.get("error") or "job failed")
        time.sleep(max(args.poll_interval, 1.0))

    _, result = call(f"{base_url}/v1/jobs/{job_id}/result", method="GET")
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "response.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for item in result["artifacts"]:
        (args.output / item["filename"]).write_bytes(base64.b64decode(item["data_base64"]))
    print(json.dumps({"usage": result["usage"], "output": str(args.output)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
