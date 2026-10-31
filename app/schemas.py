from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

DEFAULT_CODEX_MODEL = "gpt-5.6-sol"


class Mode(str, Enum):
    RENDER_3D_VIEWS = "render_3d_views"
    RECONSTRUCT_STL = "reconstruct_stl"


class Base64Image(BaseModel):
    data_base64: str = Field(description="Raw Base64 only; a data URL is also accepted")
    mime_type: Literal["image/png", "image/jpeg", "image/webp"] = "image/png"

    @field_validator("data_base64")
    @classmethod
    def nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("data_base64 cannot be empty")
        return value


class DimensionsMM(BaseModel):
    width: float | None = Field(None, gt=0, le=1000)
    depth: float | None = Field(None, gt=0, le=1000)
    height: float | None = Field(None, gt=0, le=1000)
    preserve_reference_proportions: bool = True

    @model_validator(mode="after")
    def any_dimension(self):
        if self.width is None and self.depth is None and self.height is None:
            raise ValueError("at least one dimension is required")
        return self


class GenerateRequest(BaseModel):
    mode: Mode
    images: list[Base64Image] = Field(min_length=1, max_length=6)
    requirement: str = Field(min_length=1, max_length=30_000)
    codex_model: str = Field(DEFAULT_CODEX_MODEL, min_length=1, max_length=100)
    dimensions_mm: DimensionsMM | None = None
    views: list[Literal["front", "back", "left", "right", "left_front", "right_rear"]] | None = None
    image_size: Literal["1024x1024", "1536x1024", "1024x1536", "auto"] = "1024x1024"
    image_quality: Literal["low", "medium", "high", "auto"] = "high"
    include_editable_source: bool = True
    acceleration_mode: Literal["fast", "balanced", "quality"] = "balanced"

    @model_validator(mode="after")
    def validate_mode(self):
        if self.mode == Mode.RECONSTRUCT_STL and self.dimensions_mm is None:
            raise ValueError("dimensions_mm is required for reconstruct_stl")
        return self


class Artifact(BaseModel):
    kind: Literal["image", "stl", "preview", "source", "report", "archive"]
    filename: str
    mime_type: str
    data_base64: str
    byte_length: int
    sha256: str


class TokenUsage(BaseModel):
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    input_text_tokens: int = 0
    input_image_tokens: int = 0
    output_image_tokens: int = 0
    raw: dict[str, Any] | None = None


class UsageSummary(BaseModel):
    codex: TokenUsage = Field(default_factory=TokenUsage)
    image_generation: TokenUsage = Field(default_factory=TokenUsage)
    total_tokens: int = 0
    note: str = "Token counts are provider-reported usage; they are not a price estimate."


class GenerateResponse(BaseModel):
    request_id: str
    mode: Mode
    summary: str
    classification: str | None = None
    dimensions_mm: dict[str, float] | None = None
    artifacts: list[Artifact]
    usage: UsageSummary
    warnings: list[str] = Field(default_factory=list)
    codex_thread_id: str | None = None


class JobSubmission(BaseModel):
    job_id: str
    status: Literal["queued"] = "queued"
    status_url: str
    result_url: str


class JobStatusResponse(BaseModel):
    job_id: str
    mode: Mode
    status: Literal["queued", "running", "completed", "failed"]
    stage: str
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None

