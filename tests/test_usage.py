from app.schemas import TokenUsage
from app.usage import add_usage, codex_usage, image_usage


def test_codex_usage_selects_latest_cumulative_record():
    events = [
        {"type": "turn.started"},
        {"usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}},
        {"type": "turn.completed", "usage": {
            "input_tokens": 20, "cached_input_tokens": 3,
            "output_tokens": 8, "total_tokens": 28,
        }},
    ]
    usage = codex_usage(events)
    assert usage.input_tokens == 20
    assert usage.cached_input_tokens == 3
    assert usage.output_tokens == 8
    assert usage.total_tokens == 28


def test_image_usage_and_sum():
    one = image_usage({
        "input_tokens": 5, "output_tokens": 10, "total_tokens": 15,
        "input_tokens_details": {"text_tokens": 2, "image_tokens": 3},
        "output_tokens_details": {"image_tokens": 10},
    })
    total = add_usage(one, one)
    assert total == TokenUsage(
        input_tokens=10, output_tokens=20, total_tokens=30,
        input_text_tokens=4, input_image_tokens=6, output_image_tokens=20,
    )

