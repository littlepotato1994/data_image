from __future__ import annotations

import hashlib
import json
import shutil
import threading
import zipfile
from pathlib import Path
from typing import Any

from .base64io import decode_image
from .schemas import GenerateRequest, Mode
from fastapi import HTTPException

CACHE_VERSION = "accelerated-v1"


def image_digest(request: GenerateRequest, max_input_bytes: int) -> str:
    digest = hashlib.sha256()
    total = 0
    for image in request.images:
        data = decode_image(image, max_bytes=max_input_bytes)
        total += len(data)
        if total > max_input_bytes:
            raise HTTPException(413, f"combined input exceeds {max_input_bytes} bytes")
        digest.update(image.mime_type.encode("ascii"))
        digest.update(b"\0")
        digest.update(data)
        digest.update(b"\0")
    return digest.hexdigest()


def request_fingerprint(request: GenerateRequest, max_input_bytes: int) -> str:
    payload = request.model_dump(mode="json", exclude={"bypass_cache", "character_id"})
    payload["images"] = image_digest(request, max_input_bytes)
    payload["cache_version"] = CACHE_VERSION
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def resolved_character_id(request: GenerateRequest, digest: str) -> str | None:
    if request.mode != Mode.RECONSTRUCT_STL:
        return None
    return request.character_id or f"auto_{digest[:20]}"


class AccelerationCache:
    def __init__(self, root: Path):
        self.root = root
        self.exact = root / "exact"
        self.characters = root / "characters"
        self.exact.mkdir(parents=True, exist_ok=True)
        self.characters.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _exact_path(self, fingerprint: str) -> Path:
        return self.exact / f"{fingerprint}.json"

    def read_exact(self, fingerprint: str) -> dict[str, Any] | None:
        path = self._exact_path(fingerprint)
        if not path.is_file():
            return None
        with self._lock:
            return json.loads(path.read_text(encoding="utf-8"))

    def write_exact(self, fingerprint: str, response: dict[str, Any]) -> None:
        path = self._exact_path(fingerprint)
        temporary = path.with_suffix(".json.tmp")
        with self._lock:
            temporary.write_text(json.dumps(response, ensure_ascii=False), encoding="utf-8")
            temporary.replace(path)

    def restore_character(self, character_id: str, destination: Path) -> bool:
        source = self.characters / character_id
        archive = source / "source.zip"
        if not archive.is_file():
            return False
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copy2(archive, destination / "source.zip")
        validation = source / "validation.json"
        if validation.is_file():
            shutil.copy2(validation, destination / "validation.json")
        metadata = source / "metadata.json"
        if metadata.is_file():
            shutil.copy2(metadata, destination / "metadata.json")
        extracted = destination / "source"
        extracted.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as bundle:
            root = extracted.resolve()
            for member in bundle.infolist():
                target = (extracted / member.filename).resolve()
                if target != root and root not in target.parents:
                    raise ValueError("unsafe path in cached source.zip")
            bundle.extractall(extracted)
        return True

    def save_character(
        self,
        character_id: str,
        output_dir: Path,
        *,
        fingerprint: str,
        image_digest_value: str,
    ) -> None:
        source_zip = output_dir / "source.zip"
        if not source_zip.is_file():
            return
        destination = self.characters / character_id
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_zip, destination / "source.zip")
        validation = output_dir / "validation.json"
        if validation.is_file():
            shutil.copy2(validation, destination / "validation.json")
        metadata = {
            "character_id": character_id,
            "fingerprint": fingerprint,
            "image_digest": image_digest_value,
        }
        (destination / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
