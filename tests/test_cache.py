import json
import zipfile

from app.cache import AccelerationCache, image_digest, request_fingerprint, resolved_character_id
from app.schemas import GenerateRequest


def _request(**changes):
    value = {
        "mode": "reconstruct_stl",
        "images": [{"data_base64": "aW1hZ2U=", "mime_type": "image/png"}],
        "requirement": "printable",
        "dimensions_mm": {"height": 40},
    }
    value.update(changes)
    return GenerateRequest.model_validate(value)


def test_fingerprint_and_automatic_character_id_are_stable():
    first = _request()
    second = _request(character_id="manual-id")
    assert request_fingerprint(first, 1000) == request_fingerprint(second, 1000)
    digest = image_digest(first, 1000)
    assert resolved_character_id(first, digest).startswith("auto_")
    assert resolved_character_id(second, digest) == "manual-id"


def test_cache_exact_and_character_source_round_trip(tmp_path):
    cache = AccelerationCache(tmp_path / "cache")
    cache.write_exact("abc", {"request_id": "one"})
    assert cache.read_exact("abc") == {"request_id": "one"}

    output = tmp_path / "output"
    output.mkdir()
    with zipfile.ZipFile(output / "source.zip", "w") as bundle:
        bundle.writestr("build_model.py", "print('ok')")
    (output / "validation.json").write_text(json.dumps({"passed": True}))
    cache.save_character(
        "monkey-001", output, fingerprint="fp", image_digest_value="image-digest"
    )
    restored = tmp_path / "restored"
    assert cache.restore_character("monkey-001", restored) is True
    assert (restored / "source" / "build_model.py").is_file()
    assert (restored / "validation.json").is_file()
