from __future__ import annotations

from pathlib import Path

from agent.logit_bias import build_stop_sequences
from dag_cli.auth import PROVIDER_REGISTRY
from dag_cli.models import CANONICAL_PROVIDERS
from dag_cli.model_normalize import normalize_model_for_provider
from dag_cli.models import get_default_model_for_provider, provider_model_ids
from dag_cli.model_switch import resolve_alias


def test_cerebras_is_registered() -> None:
    assert "cerebras" in PROVIDER_REGISTRY


def test_cerebras_is_canonical_provider() -> None:
    assert any(p.slug == "cerebras" for p in CANONICAL_PROVIDERS)


def test_cerebras_default_model() -> None:
    assert get_default_model_for_provider("cerebras") == "gemma-4-31b"


def test_cerebras_prefix_is_stripped() -> None:
    assert normalize_model_for_provider("cerebras/gemma-4-31b", "cerebras") == "gemma-4-31b"


def test_cerebras_model_catalog_contains_public_models() -> None:
    models = provider_model_ids("cerebras")
    assert models[:4] == [
        "gemma-4-31b",
        "gpt-oss-120b",
        "glm-4.7",
        "qwen3-32b",
    ]


def test_cli_default_points_to_cerebras() -> None:
    cli_text = Path(__file__).resolve().parents[1] / "cli.py"
    content = cli_text.read_text(encoding="utf-8")
    assert '"provider": "cerebras"' in content
    assert '"default": "gemma-4-31b"' in content


def test_cerebras_stop_sequences_are_capped(monkeypatch) -> None:
    monkeypatch.setattr("agent.logit_bias.get_forbidden_strings", lambda: ["a", "b", "c", "d", "e"])
    assert build_stop_sequences("cerebras") == ["a", "b", "c", "d"]


def test_old_cerebras_slug_resolves_to_new_slug() -> None:
    assert resolve_alias("gemma-4-31b-it", "cerebras") == ("cerebras", "gemma-4-31b", "gemma-4-31b-it")
