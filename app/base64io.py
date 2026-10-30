from __future__ import annotations

import base64
import binascii
import hashlib
from pathlib import Path

from fastapi import HTTPException

from .schemas import Artifact, Base64Image

EXTENSIONS = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}


def decode_image(item: Base64Image, *, max_bytes: int) -> bytes:
    value = item.data_base64.strip()
    if value.startswith("data:"):
        try:
            header, value = value.split(",", 1)
        except ValueError as exc:
            raise HTTPException(422, "invalid data URL") from exc
        if ";base64" not in header:
            raise HTTPException(422, "data URL must use base64")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(422, "invalid Base64 image") from exc
    if not decoded or len(decoded) > max_bytes:
        raise HTTPException(413, f"image must be 1..{max_bytes} bytes")
    return decoded


def write_inputs(images: list[Base64Image], directory: Path, max_total: int) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    total = 0
    for index, image in enumerate(images, 1):
        data = decode_image(image, max_bytes=max_total)
        total += len(data)
        if total > max_total:
            raise HTTPException(413, f"combined input exceeds {max_total} bytes")
        path = directory / f"reference_{index:02d}{EXTENSIONS[image.mime_type]}"
        path.write_bytes(data)
        paths.append(path)
    return paths


def artifact(path: Path, kind: str, mime: str, max_bytes: int) -> Artifact:
    data = path.read_bytes()
    if len(data) > max_bytes:
        raise HTTPException(500, f"artifact {path.name} exceeds configured response limit")
    return Artifact(
        kind=kind,
        filename=path.name,
        mime_type=mime,
        data_base64=base64.b64encode(data).decode("ascii"),
        byte_length=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )

