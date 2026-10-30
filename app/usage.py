from __future__ import annotations

from typing import Any

from .schemas import TokenUsage


def _get(value: Any, name: str, default: int = 0) -> int:
    if isinstance(value, dict):
        raw = value.get(name, default)
    else:
        raw = getattr(value, name, default)
    return int(raw or 0)


def image_usage(value: Any) -> TokenUsage:
    if value is None:
        return TokenUsage()
    raw = value if isinstance(value, dict) else (
        value.model_dump() if hasattr(value, "model_dump") else vars(value)
    )
    inp = raw.get("input_tokens_details") or {}
    out = raw.get("output_tokens_details") or {}
    return TokenUsage(
        input_tokens=_get(raw, "input_tokens"),
        output_tokens=_get(raw, "output_tokens"),
        total_tokens=_get(raw, "total_tokens"),
        input_text_tokens=_get(inp, "text_tokens"),
        input_image_tokens=_get(inp, "image_tokens"),
        output_image_tokens=_get(out, "image_tokens"),
        raw=raw,
    )


def add_usage(a: TokenUsage, b: TokenUsage) -> TokenUsage:
    return TokenUsage(
        input_tokens=a.input_tokens + b.input_tokens,
        cached_input_tokens=a.cached_input_tokens + b.cached_input_tokens,
        output_tokens=a.output_tokens + b.output_tokens,
        total_tokens=a.total_tokens + b.total_tokens,
        input_text_tokens=a.input_text_tokens + b.input_text_tokens,
        input_image_tokens=a.input_image_tokens + b.input_image_tokens,
        output_image_tokens=a.output_image_tokens + b.output_image_tokens,
    )


def codex_usage(events: list[dict[str, Any]]) -> TokenUsage:
    """Find the largest cumulative token record in Codex JSONL events.

    Codex event field nesting has evolved. Recursively inspect dictionaries and
    select the record with the greatest reported total to avoid summing cumulative
    snapshots more than once.
    """
    candidates: list[dict[str, Any]] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            keys = set(value)
            if keys & {"input_tokens", "output_tokens", "total_tokens"}:
                candidates.append(value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(events)
    if not candidates:
        return TokenUsage()

    def total(item: dict[str, Any]) -> int:
        explicit = _get(item, "total_tokens")
        return explicit or _get(item, "input_tokens") + _get(item, "output_tokens")

    raw = max(candidates, key=total)
    details = raw.get("input_tokens_details") or {}
    return TokenUsage(
        input_tokens=_get(raw, "input_tokens"),
        cached_input_tokens=_get(raw, "cached_input_tokens") or _get(details, "cached_tokens"),
        output_tokens=_get(raw, "output_tokens"),
        total_tokens=total(raw),
        raw=raw,
    )

