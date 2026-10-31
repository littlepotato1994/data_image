#!/usr/bin/env python3
"""Minimal Base64 client for /v1/generate, using only the Python standard library."""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["render_3d_views", "reconstruct_stl"])
    parser.add_argument("images", nargs="+", type=Path)
    parser.add_argument("--requirement", required=True)
    parser.add_argument("--codex-model", default="gpt-5.6-sol")
    parser.add_argument("--height", type=float)
    parser.add_argument("--url", default="http://127.0.0.1:8000/v1/generate")
    parser.add_argument("--output", type=Path, default=Path("client_output"))
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
        "images": images,
        "requirement": args.requirement,
        "codex_model": args.codex_model,
    }
    if args.mode == "reconstruct_stl":
        if not args.height:
            raise SystemExit("--height is required for reconstruct_stl")
        payload["dimensions_mm"] = {
            "height": args.height,
            "preserve_reference_proportions": True,
        }

    headers = {"Content-Type": "application/json"}
    if os.getenv("SERVICE_API_KEY"):
        headers["X-API-Key"] = os.environ["SERVICE_API_KEY"]
    request = Request(
        args.url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=3600) as response:
            result = json.load(response)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code} {exc.reason}: {body}") from None

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "response.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for item in result["artifacts"]:
        (args.output / item["filename"]).write_bytes(base64.b64decode(item["data_base64"]))
    print(json.dumps({"usage": result["usage"], "output": str(args.output)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

