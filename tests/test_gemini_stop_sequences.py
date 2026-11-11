from __future__ import annotations

from agent.gemini_cloudcode_adapter import build_gemini_request as build_cloudcode_request
from agent.gemini_native_adapter import build_gemini_request as build_native_request


def test_native_gemini_stop_sequences_are_capped_and_deduped() -> None:
    request = build_native_request(
        messages=[{"role": "user", "content": "hello"}],
        stop=["a", "b", "a", "c", "d", "e", "f"],
    )

    assert request["generationConfig"]["stopSequences"] == ["a", "b", "c", "d", "e"]


def test_cloudcode_gemini_stop_sequences_are_capped_and_deduped() -> None:
    request = build_cloudcode_request(
        messages=[{"role": "user", "content": "hello"}],
        stop=["a", "b", "a", "c", "d", "e", "f"],
    )

    assert request["generationConfig"]["stopSequences"] == ["a", "b", "c", "d", "e"]
