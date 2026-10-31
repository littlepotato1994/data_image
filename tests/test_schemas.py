import pytest
from pydantic import ValidationError

from app.schemas import GenerateRequest


def test_stl_requires_dimensions():
    with pytest.raises(ValidationError):
        GenerateRequest.model_validate({
            "mode": "reconstruct_stl",
            "images": [{"data_base64": "AA==", "mime_type": "image/png"}],
            "requirement": "make it printable",
        })


def test_render_defaults_are_valid():
    value = GenerateRequest.model_validate({
        "mode": "render_3d_views",
        "images": [{"data_base64": "AA==", "mime_type": "image/png"}],
        "requirement": "six views",
    })
    assert value.image_quality == "high"
    assert value.codex_model == "gpt-5.6-sol"


def test_acceleration_and_character_fields():
    value = GenerateRequest.model_validate({
        "mode": "reconstruct_stl",
        "images": [{"data_base64": "AA==", "mime_type": "image/png"}],
        "requirement": "printable",
        "dimensions_mm": {"height": 40},
        "acceleration_mode": "fast",
        "character_id": "monkey-001",
    })
    assert value.acceleration_mode == "fast"
    assert value.character_id == "monkey-001"
    assert value.reuse_character is True

    with pytest.raises(ValidationError):
        GenerateRequest.model_validate({
            "mode": "reconstruct_stl",
            "images": [{"data_base64": "AA==", "mime_type": "image/png"}],
            "requirement": "printable",
            "dimensions_mm": {"height": 40},
            "character_id": "../unsafe",
        })

