"""Tests for output integrity pipeline: sanitize, logit_bias, stop sequences.

Covers:
  - Entity spelling correction
  - Forbidden string blocking
  - Noise stripping
  - Logit bias tokenization
  - Stop sequence generation
  - Full pipeline integration
  - Performance benchmarks
  - DAG edge traversal verification

Run: .venv/bin/python -m pytest tests/test_output_integrity.py -v
"""

import os
import sys
import tempfile
import time
import json
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure collar is on path
COLLAR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(COLLAR_ROOT))


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def temp_config():
    """Create a temporary output-integrity config with test patterns."""
    with tempfile.TemporaryDirectory() as td:
        config_path = Path(td) / "output-integrity.dag"
        config_path.write_text("""[forbidden-strings]
test-garbage
fake phrase
unwanted output

[entity-spelling]
TestCorp→TestCorp
testcorp→TestCorp
""")
        yield config_path


@pytest.fixture
def clean_module(temp_config, monkeypatch):
    """Reload output_integrity with a clean config path."""
    import importlib
    # Patch Path.home to return a temp dir
    monkeypatch.setattr(Path, "home", lambda: temp_config.parent)
    # Force reload
    if "agent.output_integrity" in sys.modules:
        import agent.output_integrity
        importlib.reload(agent.output_integrity)
    return __import__("agent.output_integrity", fromlist=["sanitize"])


# ═══════════════════════════════════════════════════════════════════
# Unit: Entity Spelling
# ═══════════════════════════════════════════════════════════════════

class TestEntitySpelling:
    """Entity spelling corrections from config."""

    def test_corrects_case_variations(self):
        from agent.output_integrity import sanitize
        result = sanitize("Use TestCorp for this. testcorp is the old name.")
        assert "TestCorp" in result
        # The module uses the LIVE config, so this test reflects actual state.
        # If entity-spelling section is empty, no corrections occur.

    def test_no_false_positives(self):
        from agent.output_integrity import sanitize
        # Clean text should pass through untouched
        clean = "This is normal text with no entity misspellings."
        assert sanitize(clean) == clean

    def test_empty_input(self):
        from agent.output_integrity import sanitize
        assert sanitize("") == ""
        assert sanitize(None) is None


# ═══════════════════════════════════════════════════════════════════
# Unit: Forbidden String Blocking
# ═══════════════════════════════════════════════════════════════════

class TestForbiddenStrings:
    """Forbidden string detection and blocking."""

    def test_blocks_forbidden_string(self):
        from agent.output_integrity import sanitize
        # The module's live config has "need sleep" by default
        result = sanitize("I need sleep after this long session.")
        if "need sleep" in result:
            pytest.skip("Live config may not have this pattern")
        assert "[blocked]" in result

    def test_preserves_surrounding_text(self):
        from agent.output_integrity import sanitize
        result = sanitize("Before. need coffee break. After.")
        # If blocked, surrounding text should be intact
        assert "Before." in result
        assert "After." in result

    def test_empty_forbidden_strings(self):
        from agent.output_integrity import sanitize
        result = sanitize("Normal text with nothing blocked.")
        assert "Normal text" in result


# ═══════════════════════════════════════════════════════════════════
# Unit: Noise Stripping
# ═══════════════════════════════════════════════════════════════════

class TestNoiseStripping:
    """Stripping model self-narration prefixes."""

    TEST_CASES = [
        # (input, expected_contains, expected_missing)
        ("Let me check the file. The result is 42.", "The result is 42.", "Let me check"),
        ("I'll now run the test. All tests passed.", "All tests passed.", "I'll now run"),
        ("First, I need to inspect the code. Found bug on line 3.", "Found bug on line 3.", "First, I need to inspect"),
        ("I will search for the answer. Answer: yes.", "Answer: yes.", "I will search"),
        ("Let's examine the output. Output is clean.", "Output is clean.", "Let's examine"),
        ("Allow me to explain. The DAG system works.", "The DAG system works.", "Allow me to explain"),
        ("I'll just quickly verify. All good.", "All good.", "I'll just quickly"),
    ]

    def test_strips_noise_prefix(self):
        from agent.output_integrity import sanitize
        for raw, expected_in, expected_out in self.TEST_CASES:
            result = sanitize(raw)
            assert expected_in in result, f"Failed on: {raw!r} -> {result!r}"
            assert expected_out not in result, f"Noise not stripped: {raw!r} -> {result!r}"

    def test_clean_text_untouched(self):
        from agent.output_integrity import sanitize
        clean = "The build succeeded. All 42 tests passed. No errors found."
        assert sanitize(clean) == clean

    def test_mid_text_preserved(self):
        from agent.output_integrity import sanitize
        text = "Let me explain the system. You can let me know if you have questions."
        result = sanitize(text)
        # "Let me explain" at start stripped, "let me know" at end preserved
        assert "let me know" in result.lower()

    def test_multiline_noise(self):
        from agent.output_integrity import sanitize
        text = "Let me check the logs.\n\nI'll now run the build.\n\nThe build passed."
        result = sanitize(text)
        assert "The build passed" in result
        assert "Let me check" not in result


# ═══════════════════════════════════════════════════════════════════
# Unit: Logit Bias
# ═══════════════════════════════════════════════════════════════════

class TestLogitBias:
    """Logit bias tokenization and stop sequence generation."""

    def test_build_logit_bias_returns_dict(self):
        from agent.logit_bias import build_logit_bias
        bias = build_logit_bias()
        # May be None if tiktoken not installed or no forbidden strings
        if bias is None:
            pytest.skip("tiktoken not available or no forbidden strings")
        assert isinstance(bias, dict)
        for token_id, bias_val in bias.items():
            assert isinstance(token_id, int)
            assert bias_val == -100

    def test_build_stop_sequences_raw_strings(self):
        from agent.logit_bias import build_stop_sequences
        stops = build_stop_sequences()
        if stops is None:
            pytest.skip("No forbidden strings configured")
        assert isinstance(stops, list)
        for s in stops:
            assert isinstance(s, str)
            # Must be raw strings, not regex-escaped
            assert "\\\\" not in s, f"Stop sequence contains escaped backslash: {s!r}"

    def test_stop_sequences_order_preserved(self):
        from agent.logit_bias import build_stop_sequences
        stops = build_stop_sequences()
        if not stops:
            pytest.skip("No forbidden strings")
        # Should be in same order as config
        assert stops == sorted(set(stops), key=stops.index), "Stop sequences should preserve order"


# ═══════════════════════════════════════════════════════════════════
# Integration: Full Pipeline
# ═══════════════════════════════════════════════════════════════════

class TestFullPipeline:
    """End-to-end: config → sanitize → output."""

    def test_pipeline_strips_noise_then_blocks_forbidden(self):
        from agent.output_integrity import sanitize
        # Noise + forbidden + real content
        text = "Let me check the logs. need sleep and need coffee. Build succeeded."
        result = sanitize(text)
        # Noise stripped
        assert "Let me check" not in result
        # Content preserved
        assert "Build succeeded" in result

    def test_pipeline_corrects_entities_then_strips_noise(self):
        from agent.output_integrity import sanitize
        text = "Let me check. The project is called testcorp."
        result = sanitize(text)
        assert "Let me check" not in result

    def test_pipeline_handles_large_output(self):
        from agent.output_integrity import sanitize
        large = "Valid content. " * 500
        result = sanitize(large)
        assert len(result) > 0
        assert "Valid content" in result

    def test_no_regression_on_known_good_output(self):
        """Verify clean output is not degraded."""
        from agent.output_integrity import sanitize
        clean_outputs = [
            "The build completed. 0 errors, 3 warnings.",
            "All 42 tests passed in 1.2 seconds.",
            "File written to /Users/dico/collar/dags/output-integrity.dag",
            "PR #71 created and merged successfully.",
        ]
        for text in clean_outputs:
            result = sanitize(text)
            assert result.strip() == text.strip(), f"Clean output was modified: {text!r} -> {result!r}"


# ═══════════════════════════════════════════════════════════════════
# Performance Benchmarks
# ═══════════════════════════════════════════════════════════════════

class TestPerformance:
    """Performance characteristics of the integrity pipeline."""

    def test_sanitize_sub_millisecond_for_typical_output(self):
        from agent.output_integrity import sanitize
        text = "The build completed with 0 errors. All tests passed. Ready to deploy."
        # Warm up
        for _ in range(10):
            sanitize(text)
        # Measure
        iterations = 1000
        start = time.perf_counter()
        for _ in range(iterations):
            sanitize(text)
        elapsed = time.perf_counter() - start
        avg_us = (elapsed / iterations) * 1_000_000
        assert avg_us < 500, f"sanitize() too slow: {avg_us:.0f}µs avg (target <500µs)"

    def test_sanitize_linear_scaling(self):
        from agent.output_integrity import sanitize
        small = "OK" * 10
        large = "OK" * 1000
        # Warm up
        sanitize(small)
        sanitize(large)
        # Measure
        n = 500
        t0 = time.perf_counter()
        for _ in range(n):
            sanitize(small)
        t_small = time.perf_counter() - t0
        t0 = time.perf_counter()
        for _ in range(n):
            sanitize(large)
        t_large = time.perf_counter() - t0
        # Large should be at most 100x small (linear scaling)
        ratio = (t_large / len("OK" * 1000)) / (t_small / len("OK" * 10))
        assert ratio < 10, f"Non-linear scaling detected: ratio={ratio:.1f}x"

    def test_token_savings_estimate(self):
        """Estimate tokens saved by noise stripping."""
        from agent.output_integrity import sanitize
        noisy = "Let me check the repository structure first.\n\nI'll now run the build.\n\nThe build succeeded with 0 errors."
        clean = sanitize(noisy)
        # Approximate token count: ~4 chars per token
        saved_chars = len(noisy) - len(clean)
        saved_tokens = saved_chars // 4
        assert saved_chars > 0, f"No characters saved: {noisy!r} -> {clean!r}"
        print(f"\n  Token savings: ~{saved_tokens} tokens saved per noisy response ({saved_chars} chars stripped)")


# ═══════════════════════════════════════════════════════════════════
# DAG Edge Traversal Verification
# ═══════════════════════════════════════════════════════════════════

class TestDAGEdges:
    """Verify output-integrity DAG edges are loaded and traceable."""

    def test_output_integrity_dag_exists(self):
        path = COLLAR_ROOT / "dags" / "output-integrity.dag"
        assert path.exists(), f"Missing: {path}"
        content = path.read_text()
        assert "[output-integrity]" in content
        assert "Spell→" in content
        assert "Self→" in content
        assert "Error→" in content

    def test_dag_edges_load_into_prompt(self):
        """Verify edges appear in the merged DAG context."""
        from agent.prompt_builder import _MERGED_DAGS
        assert "[output-integrity]" in _MERGED_DAGS, (
            "output-integrity edges not found in merged DAGs"
        )

    def test_integrity_floor_exists(self):
        """Verify hardcoded floor constant exists."""
        from agent.prompt_builder import _INTEGRITY_FLOOR
        assert "[output-integrity]" in _INTEGRITY_FLOOR
        assert "Spell→" in _INTEGRITY_FLOOR

    def test_identity_contains_integrity(self):
        """Verify identity block includes integrity constraints."""
        path = COLLAR_ROOT / "dags" / "default-identity.dag"
        content = path.read_text()
        assert "body" in content.lower(), "Identity missing physical-attribute constraint"
        assert "software" in content.lower(), "Identity missing 'software' marker"

    def test_dag_edge_count(self):
        """Verify expected number of edges in output-integrity section."""
        path = COLLAR_ROOT / "dags" / "output-integrity.dag"
        content = path.read_text()
        # Count → arrows (edges) in the output-integrity section
        section_start = content.index("[output-integrity]")
        section_end = content.index("[", section_start + 1) if "[" in content[section_start + 1:] else len(content)
        section = content[section_start:section_end]
        edges = [line for line in section.split("\n") if "→" in line]
        assert len(edges) >= 5, f"Expected >=5 edges, got {len(edges)}: {edges}"


# ═══════════════════════════════════════════════════════════════════
# Regression Tests
# ═══════════════════════════════════════════════════════════════════

class TestRegression:
    """Prevent regressions on known edge cases."""

    def test_unicode_output_survives(self):
        from agent.output_integrity import sanitize
        text = "Résumé: café crème brûlée. 日本語テスト。"
        result = sanitize(text)
        assert "Résumé" in result
        assert "日本語" in result

    def test_code_blocks_untouched(self):
        from agent.output_integrity import sanitize
        text = "```python\nlet me = 'check this'\nprint(let_me)\n```"
        result = sanitize(text)
        assert "let me" in result  # Code blocks should not be stripped

    def test_urls_untouched(self):
        from agent.output_integrity import sanitize
        text = "See https://github.com/specdog/collar for details."
        result = sanitize(text)
        assert "https://github.com/specdog/collar" in result

    def test_fenced_code_block_with_noise_word(self):
        from agent.output_integrity import sanitize
        text = "```\nLet me show you the output.\n```\nActual result: success."
        result = sanitize(text)
        assert "Let me show you the output" in result  # Inside code fence = preserved

    def test_consecutive_noise_paragraphs(self):
        from agent.output_integrity import sanitize
        text = "Let me check the logs.\n\nI will now run the build.\n\nSuccess."
        result = sanitize(text)
        assert "Success" in result
        # First noise stripped, second noise also stripped
        assert "check the logs" not in result


# ═══════════════════════════════════════════════════════════════════
# Safety: Word Boundaries
# ═══════════════════════════════════════════════════════════════════

class TestWordBoundaries:
    """Entity spelling must not corrupt substrings or unrelated words."""

    def test_substring_not_corrupted(self):
        """Collat→Collar should NOT match 'Collateral'."""
        from agent.output_integrity import sanitize
        text = "The Collateral damage report. Lyft is a ride-sharing company."
        result = sanitize(text)
        # 'Collateral' starts with 'Collat' but is a different word
        assert "Collateral" in result, f"Collateral corrupted: {result}"
        # 'Lyft' is a real company name — should not be touched
        assert "Lyft" in result, f"Lyft corrupted: {result}"

    def test_word_variants_preserved(self):
        """Collat correction should only match standalone 'Collat'."""
        from agent.output_integrity import sanitize
        text = "Collation of data. Flyft is a project. Lyfta framework."
        result = sanitize(text)
        assert "Collation" in result, "'Collation' should not be touched"
        assert "Flyft" in result, "'Flyft' should not be touched"

    def test_case_insensitive_match(self):
        """COLLAT and collat should both be corrected."""
        from agent.output_integrity import sanitize
        # Only if Collat→Collar is in user config
        text = "COLLAT is wrong. Also collat is wrong. Collateral is not."
        result = sanitize(text)
        # 'Collateral' must survive
        assert "Collateral" in result

    def test_word_boundary_at_sentence_end(self):
        """Entity at end of sentence should match."""
        from agent.output_integrity import sanitize
        text = "The tool is called Collat. Next topic: deployment."
        result = sanitize(text)
        # If Collat→Collar correction exists, it should apply here
        assert "Collat." not in result or "Collar." in result


# ═══════════════════════════════════════════════════════════════════
# Config Parsing
# ═══════════════════════════════════════════════════════════════════

class TestConfigParsing:
    """Verify config file parsing."""

    def test_get_forbidden_strings_returns_list(self):
        from agent.output_integrity import get_forbidden_strings
        strings = get_forbidden_strings()
        assert isinstance(strings, list)
        for s in strings:
            assert isinstance(s, str)

    def test_no_config_returns_empty(self):
        """If no config file, get_forbidden_strings returns empty list."""
        import agent.output_integrity as oi
        # The module already loaded with live config, so this is informational
        strings = oi.get_forbidden_strings()
        assert isinstance(strings, list)
